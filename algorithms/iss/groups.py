"""Temporary scaffolds and bounded, checkpointed multi-cube best-first trials."""
import runtime as r
import core as c
import fast_routes as f
import heapq,itertools,json,time,pickle,sys,os
import numpy as np
from numba import njit
from numba.typed import List

@njit(cache=True)
def neighbours(positions):
    result=List()
    for i in range(len(positions)):
        ids=[]
        for j in range(len(positions)):
            if i!=j and abs(positions[i,0]-positions[j,0])+abs(positions[i,1]-positions[j,1])+abs(positions[i,2]-positions[j,2])==1:ids.append(j)
        result.append(np.asarray(ids,dtype=np.int64))
    return result

def bad(s):return [i for i in range(148) if tuple(s[i]) not in c.target_sets[int(c.types[i])]]
def direct(state,seq,detail):
    for a in bad(state):
        parents=f.graph(state,a,r.beat)
        for goal in sorted(c.target_sets[int(c.types[a])]):
            path=f.route(parents,goal,a)
            if path:
                nxt=state.copy();nxt[a]=goal
                if r.accept(seq+path,nxt,dict(**detail,last_cube=a)):return True
    return False

r.initialize()
from compiled_routes import install
install(f,c,r.beat)
token=r.phase_start('temporary_displacement');parked_cases=0;unlocked_cases=0
while True:
    seq,state,_,sha=r.load_best();changed=False
    base_neighbours=neighbours(state)
    ens=c.ProgrammableCubes(state)
    for a in range(148):assert list(base_neighbours[a])==list(ens.cube_neighbours[a])
    critical={a for a in range(148) if not c.check_connectivity_of_cubes(base_neighbours,a)}
    checkpoint=c.RUN/'state/scaffold_cursor.json';prior=json.loads(checkpoint.read_text()) if checkpoint.exists() else {}
    begin=prior.get('next_case',0) if prior.get('solution_sha256')==sha else 0
    case=0
    for a in bad(state):
        parents=f.graph(state,a,r.beat);fixed=set(map(tuple,c.np.delete(state,a,axis=0)));sites=[]
        for point in parents:
            if point==tuple(state[a]):continue
            contacts=sum(tuple(point[k]+(sign if k==axis else 0) for k in range(3)) in fixed for axis in range(3) for sign in (-1,1))
            if contacts>=2:sites.append((-contacts,point))
        for _,point in sorted(sites):
            index=case;case+=1
            if index<begin:continue
            parked_cases+=1;r.METRICS.update(parked_cases=parked_cases,unlocked_cases=unlocked_cases,nodes=f.expanded);r.beat()
            r.cursor('scaffold_cursor',dict(solution_sha256=sha,next_case=index,parked_cube=a,position=list(map(int,point)),status='in_progress'))
            park=f.route(parents,point,a);nxt=state.copy();nxt[a]=point
            if c.correct(nxt)>c.correct(state) and r.accept(seq+park,nxt,dict(method='scaffold_site_is_target',parked_cube=a)):changed=True;break
            if direct(nxt,seq+park,dict(method='temporary_scaffold',parked_cube=a)):changed=True;break
            adjacency=neighbours(nxt)
            unlocked=[b for b in sorted(critical) if b!=a and c.check_connectivity_of_cubes(adjacency,b)]
            occupied=set(map(tuple,nxt))
            # Test newly movable supports first: these could not move before parking.
            for b in unlocked:
                unlocked_cases+=1;parents_b=f.graph(nxt,b,r.beat)
                for goal in sorted(c.target_sets[int(c.types[b])]-occupied):
                    path=f.route(parents_b,goal,b)
                    if not path:continue
                    n2=nxt.copy();n2[b]=goal
                    if c.correct(n2)>c.correct(state) and r.accept(seq+park+path,n2,dict(method='unlocked_support_reaches_target',parked_cube=a,support_cube=b)):changed=True;break
                    if direct(n2,seq+park+path,dict(method='scaffold_unlocked_support',parked_cube=a,support_cube=b)):changed=True;break
                if changed:break
            r.cursor('scaffold_cursor',dict(solution_sha256=sha,next_case=index+1,status='completed_case'))
            if changed:break
        if changed:break
    if not changed:break
r.phase_end(token,'completed',parked_cases=parked_cases,unlocked_support_cases=unlocked_cases,scope='All >=2-contact sites for initially incorrect cubes; then newly unlocked supports. Other support relocations remain a possible extension.')

token=r.phase_start('multi_cube_best_first');total_nodes=0;group_results=[]
seq,baseline,_,sha=r.load_best();analysis=c.analyze(baseline)
groups=[]
for row in analysis['cubes']:
    a=row['cube_id'];near=row['face_neighbours']
    groups.append(tuple(sorted(set([a]+near))))
    for b in near:
        nb=list(map(int,neighbours(baseline)[b]))
        groups.append(tuple(sorted(set([a,b]+nb))))
groups=[g for g in dict.fromkeys(groups) if 2<=len(g)<=4]
groups.sort(key=lambda g:(-sum(i in analysis['incorrect_cube_ids'] for i in g),len(g),g))
extend='--extend' in sys.argv
for group_index,group in enumerate(groups):
    seq,baseline,old,sha=r.load_best()
    group_key=','.join(map(str,group));stem='group_'+group_key.replace(',','_')
    statepath=c.RUN/'state'/(stem+'_'+sha[:10]+'.json')
    legacy=c.RUN/'state'/(stem+'.json')
    prior=json.loads(statepath.read_text()) if statepath.exists() else (json.loads(legacy.read_text()) if legacy.exists() else {})
    if prior.get('solution_sha256')==sha and prior.get('status')=='trial_completed' and (not extend or not prior.get('frontier',0)):continue
    fixed={tuple(p) for i,p in enumerate(baseline) if i not in group}
    goals={t:c.np.asarray(sorted(c.target_sets[t]-fixed),dtype=c.np.int64).reshape(-1,3) for t in {int(c.types[a]) for a in group}}
    def heuristic(s):
        d=0
        for t,target in goals.items():
            ids=[a for a in group if int(c.types[a])==t]
            if len(target)<len(ids):return 10000
            cost=c.np.abs(s[ids,None,:]-target[None,:,:]).sum(axis=2)
            ii,jj=c.linear_sum_assignment(cost);d+=int(cost[ii,jj].sum())
        return d
    serial=itertools.count();key=tuple(map(tuple,baseline[list(group)]));heap=[(heuristic(baseline),0,next(serial),key,[])];seen={key:0};expanded=0;improved=False
    frontier_path=c.RUN/'state'/(stem+'_'+sha[:10]+'_frontier.pkl')
    resume_frontier=c.RUN/prior.get('saved_frontier',frontier_path.relative_to(c.RUN).as_posix()).replace('\\','/')
    if prior.get('solution_sha256')==sha and resume_frontier.exists() and prior.get('frontier_sha256')==r.digest(resume_frontier):
        with resume_frontier.open('rb') as h:saved=pickle.load(h)
        heap=saved['heap'];seen=saved['seen'];expanded=saved['expanded']
        serial=itertools.count(max([node[2] for node in heap]+[0])+1)
        r.emit('group_frontier_resumed',group=list(group),expanded=expanded,frontier=len(heap))
    # This is a finite trial, not an exhaustive proof. Frontier is saved if quota is reached.
    quota=6000;initial_expanded=expanded;depth_limit=46
    def save_frontier(status):
        tmp=frontier_path.with_suffix('.tmp')
        with tmp.open('wb') as handle:pickle.dump(dict(group=group,baseline=baseline,commands=seq,solution_sha256=sha,heap=heap,seen=seen,expanded=expanded),handle)
        os.replace(tmp,frontier_path)
        r.atomic(statepath,dict(solution_sha256=sha,group=list(group),expanded=expanded,frontier=len(heap),status=status,saved_frontier=frontier_path.relative_to(c.RUN).as_posix(),frontier_sha256=r.digest(frontier_path)))
    while heap and expanded-initial_expanded<quota:
        rank,depth,_,key,path=heapq.heappop(heap)
        if seen.get(key,10**9)<depth:continue
        expanded+=1;total_nodes+=1
        state=baseline.copy();state[list(group)]=c.np.asarray(key)
        if c.correct(state)>c.correct(baseline):
            if r.accept(seq+path,state,dict(method='multi_cube_best_first',group=list(group),expanded=expanded)):
                improved=True;break
        if depth>=depth_limit:continue
        adjacency=neighbours(state);occupied=set(map(tuple,state))
        for a in group:
            if not c.check_connectivity_of_cubes(adjacency,a):continue
            fixed_now=occupied-{tuple(state[a])}
            for move,point in f.destinations(tuple(map(int,state[a])),fixed_now):
                nxt=state.copy();nxt[a]=point;nkey=tuple(map(tuple,nxt[list(group)]));nd=depth+1
                if seen.get(nkey,10**9)<=nd:continue
                seen[nkey]=nd;npath=path+[[a,move]]
                correct_loss=c.correct(baseline)-c.correct(nxt)
                priority=heuristic(nxt)+1.4*correct_loss+.06*nd
                heapq.heappush(heap,(priority,nd,next(serial),nkey,npath))
        r.METRICS.update(group=list(group),group_nodes=expanded,total_group_nodes=total_nodes,frontier=len(heap));r.beat()
        if expanded%500==0:save_frontier('running')
    result=dict(group=list(group),solution_sha256=sha,expanded=expanded,frontier=len(heap),improved=improved,status='trial_completed',termination='improvement' if improved else ('quota' if heap else 'frontier_exhausted'),depth_limit=depth_limit,quota=quota)
    if heap and not improved:
        # Full tuple heap, best g-scores and command paths survive interruption between trials.
        save_frontier('trial_completed')
        result['saved_frontier']=frontier_path.relative_to(c.RUN).as_posix();result['frontier_sha256']=r.digest(frontier_path)
    r.atomic(statepath,result);group_results.append(result);r.emit('group_trial_completed',result=result)
r.phase_end(token,'completed_finite_trials',groups=group_results,total_nodes=total_nodes,unfinished='Quota-limited frontiers are saved for extension; no claim of exhaustive ISS optimization.')
