"""Adapter i ri: kodi zyrtar ESA mbetet i pandryshuar ne simulation/."""
import json
import math
import os
from pathlib import Path
import sys
import time

RUN=Path(__file__).resolve().parents[1]
sys.dont_write_bytecode=True

def check_write(path):
    if isinstance(path,(str,bytes,os.PathLike)) and not Path(os.fsdecode(path)).resolve().is_relative_to(RUN):
        raise PermissionError('Shkrim jashte run-it te ri: '+os.fsdecode(path))

def audit(event,args):
    if event=='open':
        path,mode,flags=args
        if (isinstance(mode,str) and any(c in mode for c in 'wax+')) or (
            isinstance(flags,int) and flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND)):
            check_write(path)
    elif event in ('os.remove','os.rmdir','os.mkdir','os.chmod','os.utime','os.truncate'):
        check_write(args[0])
    elif event in ('os.rename','os.link','os.symlink'):
        check_write(args[0]); check_write(args[1])
    elif event in ('socket.connect','socket.bind','socket.getaddrinfo','subprocess.Popen','os.system'):
        raise PermissionError('Rrjeti dhe nenproceset nuk lejohen ne worker.')

sys.addaudithook(audit)
import numpy as np
from scipy.optimize import linear_sum_assignment
sys.path.insert(0,str(RUN/'simulation'))
from programmable_cubes_UDP import programmable_cubes_UDP,ProgrammableCubes,fitness_function,check_connectivity_of_cubes
from validation import validate_chromosome,connected_unique

udp=programmable_cubes_UDP('ISS')
initial=np.load('data/ISS/Initial_Config.npy',allow_pickle=False)
types=udp.initial_cube_types
target=udp.target_cube_positions
target_types=udp.target_cube_types
target_sets=[set(map(tuple,target[target_types==t])) for t in range(3)]
calls=0
limit=float("inf")

def write_new(path,value):
    with Path(path).open('x',encoding='utf-8') as handle:
        json.dump(value,handle,ensure_ascii=False,indent=2)

def chromosome(commands):
    return np.asarray([value for pair in commands for value in pair]+[-1],dtype=np.int64)

def full(raw):
    global calls
    k=np.asarray(raw)
    if k.ndim!=1 or k.dtype.kind not in 'iu': raise ValueError('Kromozom jo integer.')
    validate_chromosome(k,148,udp.setup['max_cmds'])
    if calls>=limit: raise RuntimeError('U arrit kufiri i vleresimeve.')
    calls+=1
    score=float(udp.fitness(k)[0])
    if not math.isfinite(score): raise ValueError('Fitness jo i fundem.')
    return score,udp.final_cube_positions.copy()

def score(cubes,length):
    global calls
    if calls>=limit: raise RuntimeError('U arrit kufiri i vleresimeve.')
    calls+=1
    return -float(fitness_function(cubes,length/udp.setup['max_cmds'],udp.setup['fitness_offset'],
        udp.setup['num_cube_types'],types,target_types,target))

def correct(positions):
    return sum(len(set(map(tuple,positions[types==t]))&target_sets[t]) for t in range(3))

def validate(raw,save_prefixes=None):
    before=calls; start=time.perf_counter()
    score_full,final=full(raw)
    count=correct(final)
    length=(len(raw)-1)//2
    theoretical=-((.9*count/148+.1*(1-length/6000))-udp.setup['fitness_offset'])/(1-udp.setup['fitness_offset'])
    if not math.isclose(score_full,theoretical,abs_tol=1e-12,rel_tol=0):
        raise ValueError('Numri i kubeve nuk perputhet me fitness zyrtar.')
    _,previous=full(np.array([-1],dtype=np.int64))
    prefixes=[previous.copy()]; ineffective=[]
    for i in range(1,length+1):
        _,positions=full(np.concatenate((raw[:2*i],[-1])))
        if np.array_equal(previous,positions): ineffective.append(i)
        if not connected_unique(positions): raise ValueError('Gjendje e palidhur ose pozicione te perseritura.')
        previous=positions; prefixes.append(positions.copy())
    if not np.array_equal(previous,final) or not connected_unique(final):
        raise ValueError('Prefikset nuk perputhen me gjendjen finale.')
    if save_prefixes:
        with Path(save_prefixes).open('xb') as handle: np.save(handle,np.asarray(prefixes),allow_pickle=False)
    return {'official_fitness':score_full,'correct_cubes':int(count),'commands':length,
            'ineffective_commands':ineffective,'rules_valid':True,'prefixes_checked':length,
            'validation_evaluations':calls-before,'validation_seconds':time.perf_counter()-start,
            'positions':final.tolist()}

def analyze(positions):
    positions=np.asarray(positions)
    ids=[i for i in range(148) if tuple(positions[i]) not in target_sets[int(types[i])]]
    occupancy={tuple(p):i for i,p in enumerate(positions)}
    unmatched=[]; rows=[]
    cubes=ProgrammableCubes(positions)
    for t in range(3):
        targets=[p for p in sorted(target_sets[t]) if p not in set(map(tuple,positions[types==t]))]
        cube_ids=[i for i in ids if int(types[i])==t]
        distances=np.abs(positions[cube_ids,None,:]-np.asarray(targets)[None,:,:]).sum(axis=2) if targets else np.zeros((0,0))
        assignment={}
        if targets:
            ii,jj=linear_sum_assignment(distances)
            assignment={cube_ids[int(i)]:(targets[int(j)],int(distances[i,j])) for i,j in zip(ii,jj)}
        for p in targets:
            unmatched.append({'type':t,'position':list(map(int,p)),'occupied_by':occupancy.get(p)})
        for cube in cube_ids:
            legal=[]
            can_remove=bool(check_connectivity_of_cubes(cubes.cube_neighbours,cube))
            neighbours=list(map(int,cubes.cube_neighbours[cube]))
            for move in range(6):
                if cubes.apply_single_update_step(cube,move):
                    legal.append({'command':move,'destination':cubes.cube_position[cube].tolist()})
                    cubes.reset(positions)
            destination,distance=assignment[cube]
            rows.append({'cube_id':cube,'type':t,'position':positions[cube].tolist(),
                'assigned_missing_target':list(map(int,destination)),'manhattan_distance':distance,
                'removable_without_disconnect':can_remove,'face_neighbours':neighbours,
                'legal_commands':legal})
    return {'incorrect_cube_count':len(ids),'incorrect_cube_ids':ids,'cubes':rows,'missing_targets':unmatched}
