from pathlib import Path
import os,sys,subprocess
R=Path(__file__).resolve().parents[1]
env=os.environ.copy()
for key,sub in {'TMP':'tmp','TEMP':'tmp','TMPDIR':'tmp','NUMBA_CACHE_DIR':'cache/numba','MPLCONFIGDIR':'cache/matplotlib','XDG_CACHE_HOME':'cache/general','PYTHONPYCACHEPREFIX':'cache/pycache'}.items():
    p=R/sub;p.mkdir(parents=True,exist_ok=True);env[key]=str(p)
env.update(PYTHONDONTWRITEBYTECODE='1',MPLBACKEND='Agg',NUMBA_NUM_THREADS='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
script=sys.argv[1] if len(sys.argv)>1 else 'continue.py'
if script not in ('continue.py','prune.py','groups.py','verify.py','extend.py'):raise SystemExit('Unknown worker')
with (R/'logs'/('console_'+script+'.log')).open('a',encoding='utf-8') as log:
    p=subprocess.Popen([sys.executable,'-B','-u',str(R/'code'/script),*sys.argv[2:]],cwd=R/'simulation',env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8')
    try:
        for line in p.stdout:print(line,end='',flush=True);log.write(line);log.flush()
        rc=p.wait()
    except BaseException:
        p.terminate();p.wait();raise
raise SystemExit(rc)
