"""Execute the previously prepared typed-route compression, then safe deletion."""
import runtime as r
import core as c
import fast_routes as f
from itertools import permutations,product
import json
r.initialize()
from compiled_routes import install
install(f,c,r.beat)
token=r.phase_start('prepared_command_pruning')
attempts=0;windows=0;accepted=0
def typed_key(s):return tuple(tuple(sorted(map(tuple,s[c.types==t]))) for t in range(3))
def states_for(seq):
    ens=c.ProgrammableCubes(c.initial);states=[ens.cube_position.copy()]
    for a,m in seq:
        assert ens.apply_single_update_step(a,m)
        states.append(ens.cube_position.copy())
    return states
while True:
    seq,final,score,sha=r.load_best();states=states_for(seq)
    bounds=[0]+[i for i in range(1,len(seq)) if seq[i][0]!=seq[i-1][0]]+[len(seq)]
    choices=[]
    for a in range(len(bounds)-1):
        for b in range(a+1,min(a+6,len(bounds))):
            i,j=bounds[a],bounds[b];actors=sorted({p[0] for p in seq[i:j]})
            if len(actors)>3:break
            if j-i>=2:choices.append((-(j-i),i,j,actors))
    statefile=c.RUN/'state/pruning_window.json'
    prior=json.loads(statefile.read_text()) if statefile.exists() else {}
    begin=prior.get('next_window',0) if prior.get('solution_sha256')==sha else 0
    changed=False
    for index,(_,i,j,actors) in enumerate(sorted(choices)):
        if index<begin:continue
        windows+=1;r.METRICS.update(windows=windows,attempts=attempts,route_queries=f.queries,nodes=f.expanded);r.beat()
        r.cursor('pruning_window',dict(solution_sha256=sha,next_window=index,window=[i,j],status='in_progress'))
        grouped=[[a for a in actors if int(c.types[a])==t] for t in range(3)]
        winner=None
        for pp in product(*[list(permutations(g)) for g in grouped]):
            assignment={old:tuple(states[j][new]) for g,p in zip(grouped,pp) for old,new in zip(g,p)}
            for order in permutations(actors):
                attempts+=1;state=states[i].copy();path=[]
                for cube in order:
                    goal=assignment[cube]
                    if tuple(state[cube])==goal:continue
                    step=f.route(f.graph(state,cube,r.beat),goal,cube)
                    if step is None:break
                    path+=step;state[cube]=goal
                    if len(path)>=j-i:break
                else:
                    if len(path)<j-i and (winner is None or len(path)<len(winner[0])):winner=(path,state.copy())
        if winner:
            path,state=winner
            lookup={(int(c.types[a]),tuple(p)):a for a,p in enumerate(state)}
            mapping={a:lookup[(int(c.types[a]),tuple(p))] for a,p in enumerate(states[j])}
            candidate=seq[:i]+path+[[mapping[a],m] for a,m in seq[j:]]
            _,positions=c.full(c.chromosome(candidate))
            assert typed_key(positions)==typed_key(final)
            if r.accept(candidate,positions,dict(method='prepared_interchangeable_route_compression',window=[i,j],removed=len(seq)-len(candidate))):
                accepted+=1;changed=True;break
        r.cursor('pruning_window',dict(solution_sha256=sha,next_window=index+1,total_windows=len(choices),status='completed_window'))
    if not changed:break
r.phase_end(token,'completed',windows=windows,ordering_attempts=attempts,improvements=accepted,route_queries=f.queries,nodes=f.expanded)

token=r.phase_start('safe_command_deletion');cases=0;accepted=0
while True:
    seq,_,_,sha=r.load_best();states=states_for(seq);changed=False
    candidates=[(width,i) for width in (1,2,3,4) for i in range(len(seq)-width+1)]
    statefile=c.RUN/'state/deletion_window.json';prior=json.loads(statefile.read_text()) if statefile.exists() else {}
    begin=prior.get('next_case',0) if prior.get('solution_sha256')==sha else 0
    for index,(width,i) in enumerate(candidates):
        if index<begin:continue
        cases+=1;r.METRICS.update(deletion_cases=cases);r.beat()
        r.cursor('deletion_window',dict(solution_sha256=sha,next_case=index,status='in_progress',width=width,start=i))
        ens=c.ProgrammableCubes(states[i]);clean=seq[:i]
        for cube,move in seq[i+width:]:
            if ens.apply_single_update_step(cube,move):clean.append([cube,move])
        if r.accept(clean,ens.cube_position.copy(),dict(method='safe_segment_deletion',start=i,width=width,removed=len(seq)-len(clean))):accepted+=1;changed=True;break
        r.cursor('deletion_window',dict(solution_sha256=sha,next_case=index+1,total_cases=len(candidates),status='completed_case'))
    if not changed:break
r.phase_end(token,'completed',deletion_cases=cases,improvements=accepted)
