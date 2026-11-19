"""Reconstruct the old logged query boundary, then save explicit branch cursors."""
import runtime as r
import core as c
import fast_routes as f
import json,time
r.initialize()
from compiled_routes import install
install(f,c,r.beat)
token=r.phase_start('vacancy_continuation')
seq,position,value,solution_hash=r.load_best()
input_sha=r.digest(c.RUN/'outputs/input_140.npy')
relative_query=0;reconstruct_until=7452 if solution_hash==input_sha else 0
resume_file=c.RUN/'state/vacancy_branch.json'
if resume_file.exists():
    saved=json.loads(resume_file.read_text())
    if saved.get('solution_sha256')==solution_hash:
        reconstruct_until=max(reconstruct_until,saved['relative_query']+1)
reconstructed=False;skipped=0;branches=0

def bad(s):return [i for i in range(148) if tuple(s[i]) not in c.target_sets[int(c.types[i])]]
def graph(s,cube):
    global relative_query,reconstructed
    relative_query+=1
    if not reconstructed and relative_query>=reconstruct_until:
        reconstructed=True
        r.cursor('old_boundary_reconstructed',dict(relative_query=relative_query,old_absolute_query=relative_query+326 if solution_hash==input_sha else None,branches=branches,solution_sha256=solution_hash,limitation='Last logged query or durable branch cursor; an interrupted current graph may repeat.'))
        r.emit('old_boundary_reconstructed',relative_query=relative_query,old_absolute_query=relative_query+326 if solution_hash==input_sha else None)
    r.METRICS.update(relative_query=relative_query,nodes=f.expanded,branches=branches)
    return f.graph(s,cube,r.beat)
def direct(state,commands,detail):
    global relative_query,skipped
    for a in bad(state):
        if relative_query+1<reconstruct_until:
            relative_query+=1;skipped+=1;continue
        parents=graph(state,a)
        found=[]
        for goal in c.target_sets[int(c.types[a])]:
            path=f.route(parents,goal,a)
            if path:found.append((len(path),goal,path))
        for _,goal,path in sorted(found):
            nxt=state.copy();nxt[a]=goal
            if r.accept(commands+path,nxt,dict(**detail,last_cube=a)):return True
    return False
def relocations(state,exclude=(),only_type=None):
    occupied=set(map(tuple,state));items=[]
    for b in range(148):
        if b in exclude or tuple(state[b]) not in c.target_sets[int(c.types[b])]:continue
        t=int(c.types[b])
        if only_type is not None and t!=only_type:continue
        for goal in c.target_sets[t]-occupied:items.append((int(c.np.abs(state[b]-goal).sum()),b,goal))
    for _,b,goal in sorted(items):
        path=f.route(graph(state,b),goal,b)
        if path:
            nxt=state.copy();nxt[b]=goal
            yield b,goal,path,nxt

while True:
    state=position.copy();commands=[p[:] for p in seq];changed=direct(state,commands,{'method':'direct'})
    if not changed:
        for b,goal,path,nxt in relocations(state):
            detail={'method':'one_vacancy','first_cube':b,'first_goal':list(map(int,goal))}
            if reconstructed:r.cursor('vacancy_branch',dict(solution_sha256=solution_hash,detail=detail,relative_query=relative_query,status='in_progress'))
            if direct(nxt,commands+path,detail):changed=True;break
            for d,g2,p2,n2 in relocations(nxt,(b,),int(c.types[b])):
                branches+=1;detail=dict(method='two_vacancies',first_cube=b,first_goal=list(map(int,goal)),second_cube=d,second_goal=list(map(int,g2)))
                if reconstructed:r.cursor('vacancy_branch',dict(solution_sha256=solution_hash,detail=detail,relative_query=relative_query,status='in_progress'))
                if direct(n2,commands+path+p2,detail):changed=True;break
                if reconstructed:r.cursor('vacancy_branch',dict(solution_sha256=solution_hash,detail=detail,relative_query=relative_query,status='completed'))
            if changed:break
    if not changed:break
    reconstruct_until=0
    seq,position,value,solution_hash=r.load_best()
    relative_query=0
r.phase_end(token,'completed',relative_queries=relative_query,skipped_previously_completed_direct_graphs=skipped,nodes=f.expanded,branches=branches,reconstructed_old_boundary=reconstructed)

# Stage separately so the prepared command-pruning pass is not delayed.
r.cursor('continuation_next',dict(next_phase='prepared_command_pruning',later_phase='temporary_scaffolds',status='vacancy_sweep_completed'))
