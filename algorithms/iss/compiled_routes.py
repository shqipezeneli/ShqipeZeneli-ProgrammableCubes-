"""Compiled single-cube BFS, calling the unchanged ESA pattern selector."""
import numpy as np
from numba import njit
from programmable_cubes_UDP import check_if_move_is_valid

@njit(cache=True)
def bfs(fixed,root,diffs,displacements,mapping,required,empty):
    low=np.empty(3,dtype=np.int64);shape=np.empty(3,dtype=np.int64)
    for k in range(3):low[k]=np.min(fixed[:,k])-3;shape[k]=np.max(fixed[:,k])-low[k]+4
    occupied=np.zeros((shape[0],shape[1],shape[2]),dtype=np.bool_)
    for point in fixed:
        occupied[point[0]-low[0],point[1]-low[1],point[2]-low[2]]=True
    parent=np.full((shape[0],shape[1],shape[2]),-1,dtype=np.int64)
    moves=np.full((shape[0],shape[1],shape[2]),-1,dtype=np.int64)
    queue=np.empty((shape[0]*shape[1]*shape[2],3),dtype=np.int64)
    queue[0]=root-low;parent[queue[0,0],queue[0,1],queue[0,2]]=0
    head=0;tail=1
    while head<tail:
        point=queue[head].copy()
        for axis in range(3):
            occ=np.zeros(24,dtype=np.bool_)
            for i in range(24):
                x=point[0]+diffs[axis,i,0];y=point[1]+diffs[axis,i,1];z=point[2]+diffs[axis,i,2]
                if 0<=x<shape[0] and 0<=y<shape[1] and 0<=z<shape[2]:occ[i]=occupied[x,y,z]
            for direction in range(2):
                legal,which=check_if_move_is_valid(direction,occ,mapping,required,empty)
                if legal and which is not None:
                    d=displacements[axis*16+which]
                    x=point[0]+d[0];y=point[1]+d[1];z=point[2]+d[2]
                    if 0<=x<shape[0] and 0<=y<shape[1] and 0<=z<shape[2] and parent[x,y,z]<0:
                        parent[x,y,z]=head;moves[x,y,z]=axis*2+direction
                        queue[tail,0]=x;queue[tail,1]=y;queue[tail,2]=z;tail+=1
        head+=1
    return queue[:tail]+low,parent,moves,low

def install(f,c,beat):
    original=f.graph
    diffs=np.asarray(f.DIFF,dtype=np.int64);displacements=np.asarray(f.DISP,dtype=np.int64)
    def graph(state,cube,heartbeat=lambda:None):
        f.queries+=1;key=(state.tobytes(),cube)
        if key in f.cache:f.cache.move_to_end(key);return f.cache[key]
        root=tuple(map(int,state[cube]));parents={root:None};ens=c.ProgrammableCubes(state)
        if c.check_connectivity_of_cubes(ens.cube_neighbours,cube):
            fixed=np.delete(state,cube,axis=0)
            points,pp,mm,low=bfs(fixed,state[cube],diffs,displacements,f.M.move_pattern_mapping,f.M.move_patterns_occupied,f.M.move_patterns_empty)
            for i in range(1,len(points)):
                p=tuple(map(int,points[i]));x,y,z=points[i]-low
                parents[p]=(tuple(map(int,points[pp[x,y,z]])),int(mm[x,y,z]))
            f.expanded+=len(points)
        f.cache[key]=parents
        if len(f.cache)>256:f.cache.popitem(last=False)
        heartbeat();return parents
    # Complete reachability and exact parent-path comparisons at each ISS cube.
    import runtime as r
    _,state,_,_=r.load_best();comparisons=0
    for cube in range(148):
        reference=original(state,cube,beat)
        f.cache.pop((state.tobytes(),cube),None)
        result=graph(state,cube,beat)
        assert reference==result,('Compiled route mismatch',cube)
        comparisons+=len(result);beat()
    f.graph=graph
    r.emit('compiled_bfs_equivalence_passed',cube_graphs=148,reachable_states=comparisons)
    return comparisons
