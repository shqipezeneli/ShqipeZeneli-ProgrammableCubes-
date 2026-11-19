"""Single-cube graph using unchanged ESA move-pattern checks.

Removing the moving cube leaves the same fixed graph at every BFS node.
Occupancy is constructed by exact integer cell lookup, then the official
first-valid-pattern function selects the displacement. Every saved solution
still undergoes a full independent official replay and prefix verification.
"""
import core as c
from programmable_cubes_UDP import check_if_move_is_valid
from CubeMoveset import MoveSetRev
from collections import deque, OrderedDict

M=MoveSetRev()
DIFF=[[tuple(map(int,p)) for p in axis] for axis in M.diffs_to_surrounding]
DISP=[tuple(map(int,p)) for p in M.displacements]
cache=OrderedDict(); expanded=0; queries=0

def destinations(point,fixed):
    result=[]
    for axis in range(3):
        occupancy=c.np.asarray([tuple(point[k]+d[k] for k in range(3)) in fixed for d in DIFF[axis]])
        for direction in range(2):
            legal,which=check_if_move_is_valid(direction,occupancy,M.move_pattern_mapping,M.move_patterns_occupied,M.move_patterns_empty)
            if legal:
                d=DISP[axis*int(M.number_moves)+which]
                result.append((axis*2+direction,tuple(point[k]+d[k] for k in range(3))))
    return result

def graph(state,cube,heartbeat=lambda:None):
    global expanded,queries
    queries+=1; key=(state.tobytes(),cube)
    if key in cache:cache.move_to_end(key);return cache[key]
    ens=c.ProgrammableCubes(state)
    root=tuple(map(int,state[cube])); parent={root:None}
    if c.check_connectivity_of_cubes(ens.cube_neighbours,cube):
        fixed={tuple(map(int,p)) for i,p in enumerate(state) if i!=cube}
        queue=deque([root])
        while queue:
            point=queue.popleft();expanded+=1;heartbeat()
            for move,dest in destinations(point,fixed):
                if dest not in parent:parent[dest]=(point,move);queue.append(dest)
    cache[key]=parent
    if len(cache)>256:cache.popitem(last=False)
    return parent

def route(parent,goal,cube):
    goal=tuple(goal)
    if goal not in parent:return None
    path=[]
    while parent[goal] is not None:
        prev,move=parent[goal];path.append([int(cube),move]);goal=prev
    return path[::-1]

def verify_adapter(state,heartbeat=lambda:None):
    checked=0
    for cube in range(148):
        graph_data=graph(state,cube,heartbeat)
        points=list(graph_data)[::max(1,len(graph_data)//3)]
        for point in points:
            s=state.copy();s[cube]=point;ens=c.ProgrammableCubes(s)
            removable=c.check_connectivity_of_cubes(ens.cube_neighbours,cube)
            fixed={tuple(map(int,p)) for i,p in enumerate(s) if i!=cube}
            predicted=dict(destinations(point,fixed)) if removable else {}
            for move in range(6):
                effective=bool(ens.apply_single_update_step(cube,move))
                assert effective==(move in predicted),(cube,point,move)
                if effective:assert tuple(ens.cube_position[cube])==predicted[move]
                ens.reset(s);checked+=1
            heartbeat()
    return checked
