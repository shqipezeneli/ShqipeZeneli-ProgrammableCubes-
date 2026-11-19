"""Resume saved heaps exactly, including their historical verified prefix.

An older heap is valid even when a newer global best exists. It must beat
that global best before its candidate can be selected. No root is rebuilt.
"""
import runtime as r
import core as c
import fast_routes as f
import json,pickle,heapq,itertools,sys,os,uuid
from numba import njit
from numba.typed import List
import numpy as np

@njit(cache=True)
def neighbours(positions):
    result=List()
    for i in range(len(positions)):
        ids=[]
        for j in range(len(positions)):
            if i!=j and abs(positions[i,0]-positions[j,0])+abs(positions[i,1]-positions[j,1])+abs(positions[i,2]-positions[j,2])==1:ids.append(j)
        result.append(np.asarray(ids,dtype=np.int64))
    return result

r.initialize();check_only='--check-only' in sys.argv
requested=None
if '--group' in sys.argv:requested=tuple(map(int,sys.argv[sys.argv.index('--group')+1].split(',')))
records=[]
for p in (c.RUN/'state').glob('group_*.json'):
    row=json.loads(p.read_text())
    if row.get('frontier',0) and row.get('saved_frontier'):records.append(row)
for p in (c.RUN/'state').glob('extension_*.json'):
    row=json.loads(p.read_text())
    if row.get('frontier',0) and row.get('saved_frontier'):records.append(row)
# Select the furthest saved point per original group and starting solution.
latest={}
for row in records:
    key=(tuple(row['group']),row['solution_sha256'])
    if key not in latest or row['expanded']>latest[key]['expanded']:latest[key]=row
token=r.phase_start('saved_frontier_integrity' if check_only else 'saved_frontier_extension');results=[]
for (group,base_sha),record in latest.items():
    if requested is not None and group!=requested:continue
    p=(c.RUN/record['saved_frontier'].replace('\\','/')).resolve()
    assert p.is_relative_to(c.RUN/'state') and p.suffix=='.pkl'
    assert r.digest(p)==record['frontier_sha256']
    with p.open('rb') as h:saved=pickle.load(h)
    baseline=saved['baseline'];commands=saved['commands'];heap=saved['heap'];seen=saved['seen'];expanded=saved['expanded']
    assert tuple(saved['group'])==group and saved['solution_sha256']==base_sha
    _,actual=c.full(c.chromosome(commands));assert c.np.array_equal(actual,baseline)
    assert len(heap)==record['frontier']
    assert all(heap[(i-1)//2][:3]<=node[:3] for i,node in enumerate(heap) if i)
    if check_only:
        results.append(dict(group=list(group),expanded=expanded,frontier=len(heap),prefix_officially_replayed=True,sha256_passed=True));r.beat();continue
    r.emit('saved_frontier_resumed',group=list(group),expanded=expanded,frontier=len(heap),starting_solution_sha256=base_sha)
    fixed={tuple(p) for i,p in enumerate(baseline) if i not in group}
    goals={t:c.np.asarray(sorted(c.target_sets[t]-fixed),dtype=c.np.int64).reshape(-1,3) for t in {int(c.types[a]) for a in group}}
    def heuristic(s):
        distance=0
        for t,target in goals.items():
            ids=[a for a in group if int(c.types[a])==t]
            if len(target)<len(ids):return 10000
            costs=c.np.abs(s[ids,None,:]-target[None,:,:]).sum(axis=2);ii,jj=c.linear_sum_assignment(costs);distance+=int(costs[ii,jj].sum())
        return distance
    serial=itertools.count(max([node[2] for node in heap]+[0])+1);initial=expanded;name='extension_'+('_'.join(map(str,group)))+'_'+uuid.uuid4().hex[:8]
    frontier=c.RUN/'state'/(name+'.pkl');metadata=c.RUN/'state'/(name+'.json');improved=False
    def save():
        tmp=frontier.with_suffix('.tmp')
        with tmp.open('wb') as h:pickle.dump(dict(group=group,baseline=baseline,commands=commands,solution_sha256=base_sha,heap=heap,seen=seen,expanded=expanded),h)
        os.replace(tmp,frontier)
        r.atomic(metadata,dict(group=list(group),solution_sha256=base_sha,expanded=expanded,frontier=len(heap),saved_frontier=frontier.relative_to(c.RUN).as_posix(),frontier_sha256=r.digest(frontier)))
    while heap and expanded-initial<6000:
        _,depth,_,key,path=heapq.heappop(heap)
        if seen.get(key,10**9)<depth:continue
        expanded+=1;state=baseline.copy();state[list(group)]=c.np.asarray(key)
        if c.correct(state)>c.correct(baseline):
            if r.accept(commands+path,state,dict(method='saved_frontier_extension',group=list(group),expanded=expanded)):improved=True;break
        if depth<46:
            adjacency=neighbours(state);occupied=set(map(tuple,state))
            for a in group:
                if not c.check_connectivity_of_cubes(adjacency,a):continue
                for move,point in f.destinations(tuple(map(int,state[a])),occupied-{tuple(state[a])}):
                    nxt=state.copy();nxt[a]=point;nkey=tuple(map(tuple,nxt[list(group)]));nd=depth+1
                    if seen.get(nkey,10**9)<=nd:continue
                    seen[nkey]=nd;loss=c.correct(baseline)-c.correct(nxt)
                    heapq.heappush(heap,(heuristic(nxt)+1.4*loss+.06*nd,nd,next(serial),nkey,path+[[a,move]]))
        r.METRICS.update(group=list(group),expanded=expanded,frontier=len(heap));r.beat()
        if expanded%500==0:save()
    save();results.append(dict(group=list(group),expanded=expanded,additional_nodes=expanded-initial,frontier=len(heap),improved=improved,saved_frontier=frontier.relative_to(c.RUN).as_posix()))
r.phase_end(token,'completed_checks' if check_only else 'completed_finite_extension',groups=results,search_finished=False)
