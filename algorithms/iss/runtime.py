"""Durable ISS-only experiment state. Only fully verified improvements count."""
import core as c
import time,json,hashlib,os,datetime

START=time.monotonic();LAST=0;PHASE='startup';METRICS={};STOP=False
def digest(p):return hashlib.sha256(c.Path(p).read_bytes()).hexdigest()
def atomic(path,value):
    path=c.Path(path);tmp=path.with_suffix(path.suffix+'.tmp')
    with tmp.open('w',encoding='utf-8') as f:json.dump(value,f,ensure_ascii=False,indent=2);f.flush();os.fsync(f.fileno())
    os.replace(tmp,path)
def emit(event,**kw):
    global LAST
    row={'event':event,'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'phase':PHASE,'elapsed_seconds':round(time.monotonic()-START,3),'official_evaluations':c.calls,**METRICS,**kw}
    line=json.dumps(row,ensure_ascii=False)
    with (c.RUN/'logs/events.jsonl').open('a',encoding='utf-8') as f:f.write(line+'\n');f.flush()
    print(line,flush=True);LAST=time.monotonic()
def beat():
    if time.monotonic()-LAST>=10:emit('heartbeat')
def cursor(name,value):atomic(c.RUN/'state'/f'{name}.json',value)
def best_record():
    candidates=[json.loads((c.RUN/'outputs/baseline_verified.json').read_text())]
    for p in (c.RUN/'outputs').glob('best_*.json'):candidates.append(json.loads(p.read_text()))
    result=dict(min(candidates,key=lambda r:r['official_fitness']))
    result['relative_solution']=result['relative_solution'].replace('\\','/')
    return result
def load_best():
    r=best_record();p=c.RUN/r['relative_solution']
    assert p.resolve().is_relative_to(c.RUN/'outputs') and p.suffix=='.npy'
    assert digest(p)==r['sha256']
    raw=c.np.load(p,allow_pickle=False)
    return raw[:-1].reshape(-1,2).tolist(),c.np.asarray(r['positions']),r['official_fitness'],r['sha256']
def accept(seq,state,detail):
    _,_,old,_=load_best()
    proposed=c.score(c.ProgrammableCubes(state),len(seq))
    if proposed>=old-1e-12:return False
    emit('candidate_verification',fitness=proposed,correct_cubes=c.correct(state),commands=len(seq),detail=detail)
    k=c.chromosome(seq);v=c.validate(k)
    assert not v['ineffective_commands']
    assert abs(v['official_fitness']-proposed)<1e-12
    assert c.np.array_equal(c.np.asarray(v['positions']),state)
    n=max([int(p.stem[5:]) for p in (c.RUN/'outputs').glob('best_*.json')]+[0])+1
    path=c.RUN/'outputs'/f'best_{n:04d}.npy'
    with path.open('xb') as f:c.np.save(f,k,allow_pickle=False)
    v.update(relative_solution=path.relative_to(c.RUN).as_posix(),sha256=digest(path),detail=detail,phase=PHASE,elapsed_seconds=time.monotonic()-START)
    c.write_new(path.with_suffix('.json'),v)
    atomic(c.RUN/'state/latest_best.json',v)
    emit('improvement_verified',fitness=proposed,correct_cubes=v['correct_cubes'],commands=len(seq),solution=str(path))
    return True
def initialize():
    p=c.RUN/'outputs/baseline_verified.json'
    if p.exists():return
    raw=c.np.load(c.RUN/'outputs/input_140.npy',allow_pickle=False)
    v=c.validate(raw,c.RUN/'outputs/input_140_prefixes.npy')
    assert v['correct_cubes']==140 and v['commands']==530 and not v['ineffective_commands']
    assert abs(v['official_fitness']+.9249794238683127)<1e-12
    v.update(relative_solution='outputs/input_140.npy',sha256=digest(c.RUN/'outputs/input_140.npy'))
    c.write_new(p,v)
    c.write_new(c.RUN/'outputs/remaining_140.json',c.analyze(v['positions']))
    emit('baseline_verified',fitness=v['official_fitness'],correct_cubes=140,commands=530)

def phase_start(name):
    global PHASE
    PHASE=name;emit('phase_started');return time.monotonic(),c.calls,best_record()['official_fitness']
def phase_end(token,status,**kw):
    t,calls,initial=token;r=best_record()
    row=dict(phase=PHASE,status=status,wall_seconds=time.monotonic()-t,official_evaluations=c.calls-calls,initial_fitness=initial,official_fitness=r['official_fitness'],correct_cubes=r['correct_cubes'],commands=r['commands'],**kw)
    cursor(PHASE+'_result',row);emit('phase_ended',result=row)
