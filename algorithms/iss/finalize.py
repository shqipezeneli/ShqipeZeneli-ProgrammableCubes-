"""Package a resumable checkpoint; never modifies a previous experiment."""
from pathlib import Path
import ast,hashlib,json,shutil,zipfile,datetime
R=Path(__file__).resolve().parents[1];P=R.parent.parent
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
records=[json.loads((R/'outputs/baseline_verified.json').read_text())]
records += [json.loads(p.read_text()) for p in (R/'outputs').glob('best_*.json')]
best=min(records,key=lambda r:r['official_fitness'])
best=dict(best);best['relative_solution']=best['relative_solution'].replace('\\','/')
verified=json.loads((R/'state/independent_final_verification.json').read_text())
assert best['sha256']==verified['sha256']==sha(R/best['relative_solution'])
for p in (R/'code').glob('*.py'):ast.parse(p.read_text(encoding='utf-8'),filename=str(p))
alias=R/'outputs/zgjidhja_me_e_mire.npy'
if alias.exists():assert sha(alias)==best['sha256'],'Existing saved solution must not be overwritten.'
else:
    with alias.open('xb') as handle:handle.write((R/best['relative_solution']).read_bytes())
events=[json.loads(line) for line in (R/'logs/events.jsonl').read_text(encoding='utf-8').splitlines()]
experiments=[e['result'] for e in events if e['event']=='phase_ended']
frontiers=[]
for p in (R/'state').glob('group_*.json'):
    row=json.loads(p.read_text())
    if row.get('frontier',0) and row.get('saved_frontier'):
        row['saved_frontier']=row['saved_frontier'].replace('\\','/');frontiers.append(row)
summary={'date':'2026-11-18','scenario':'ISS','status':'checkpoint_saved_optimization_not_exhausted','baseline':{'correct_cubes':140,'commands':530,'official_fitness':-.9249794238683127},'best':{k:best[k] for k in ('correct_cubes','commands','official_fitness','sha256','relative_solution')},'genuine_improvement':best['official_fitness']<-.9249794238683127-1e-12,'cube_gain':best['correct_cubes']-140,'commands_removed':530-best['commands'],'fitness_improvement':-.9249794238683127-best['official_fitness'],'independent_official_verification':verified,'completed_finite_experiments':experiments,'saved_multi_cube_frontiers':frontiers,'unfinished':['Extend saved quota-limited multi-cube frontiers where their solution SHA matches the current best; otherwise rebuild those groups from the improved best.','Investigate additional support relocations beyond newly unlocked support cubes.','Explore larger groups or deeper paths; the search is not an exhaustive proof.'],'resume_note':'Initial old frontier was absent. Deterministic traversal reconstructed the old last logged query 7778 (relative 7452), skipping known-completed direct graphs. Later branch and window cursors and full group frontiers are saved. A partial current graph may be repeated.','execution_notes':['An initial logging-key collision was corrected before accepting any candidate. See console_continue.py.log.','The slow continuation was checkpointed and replaced with a compiled equivalent BFS. Complete reachable-state and parent-path equality is checked on all 148 cube graphs before using it.','Prepared pruning is the previous polish.py route compression, followed by safe deletion of 1-4 commands and removal of ineffective suffix commands.'],'protected_files_checked':None}
manifest=json.loads((R/'provenance/preexisting_manifest.json').read_text())
changed=[];missing=[]
for row in manifest:
    p=P/row['path']
    if not p.is_file():missing.append(row['path'])
    elif sha(p)!=row['sha256']:changed.append(row['path'])
sim_changed=[str(p.relative_to(R/'simulation')) for p in (R/'simulation').rglob('*') if p.is_file() and sha(p)!=sha(P/'ESA_Simulation_backup'/p.relative_to(R/'simulation'))]
safety={'files_checked':len(manifest),'changed':changed,'missing':missing,'simulator_copy_changes':sim_changed,'no_preexisting_file_modified':not changed and not missing,'secrets_and_internal_directories_excluded_from_reads':True}
(R/'reports/SAFETY.json').write_text(json.dumps(safety,indent=2),encoding='utf-8')
assert safety['no_preexisting_file_modified'] and not sim_changed
summary['protected_files_checked']=len(manifest)
summary['remaining_cube_ids']=json.loads((R/'outputs/remaining_latest.json').read_text())['incorrect_cube_ids']
summary['unfinished'][0]='Continue the saved multi-cube heaps via code/launch.py extend.py, using each heap\'s stored verified prefix and comparing candidates with the GLOBAL latest best. Do not rebuild the heap. Historical starting solutions remain valid search branches.'
summary['optimization_phase_count']=sum(e['phase'] not in ('independent_final_verification','saved_frontier_integrity') for e in experiments)
summary['multi_cube_trial_count']=sum(len(e.get('groups',[])) for e in experiments if e['phase']=='multi_cube_best_first')
birth=getattr(R.stat(),'st_birthtime',R.stat().st_ctime)
now=datetime.datetime.now(datetime.timezone.utc)
summary['session_timing']={'directory_created_utc':datetime.datetime.fromtimestamp(birth,datetime.timezone.utc).isoformat(),'report_saved_utc':now.isoformat(),'wall_seconds_since_directory_creation':now.timestamp()-birth,'completed_phase_seconds':sum(e['wall_seconds'] for e in experiments),'note':'Phase timings exclude preparation, imports, interrupted attempts, equivalence checks and packaging. Full wall timing starts at creation of the isolated directory.'}
(R/'reports/EXPERIMENTS.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
lines=['# Vazhdimi i ISS — checkpoint i ri','',f"Rezultati i verifikuar: **{best['correct_cubes']}/148 kube**, **{best['commands']} komanda**, fitness **{best['official_fitness']}**.",'',f"Pikënisja: 140/148, 530 komanda, fitness -0.9249794238683127. Përmirësimi i fitness-it: {summary['fitness_improvement']:.16f}.",'','Pa komanda joefektive. Çdo prefiks u kontrollua nga simulatori zyrtar në proces të veçantë.','', '## Eksperimentet e kryera','', '| Metoda | Statusi | Kube | Komanda | Fitness | Sekonda |','|---|---|---:|---:|---:|---:|']
for e in experiments:lines.append(f"| {e['phase']} | {e['status']} | {e['correct_cubes']} | {e['commands']} | {e['official_fitness']:.16f} | {e['wall_seconds']:.3f} |")
lines+=['','Kohët më sipër janë kohët e fazave që përfunduan; koha e përgatitjes, rindërtimi i parë, procesi i ndërprerë për përshpejtim dhe kompilimi regjistrohen veçmas në logs/events.jsonl dhe logs/console_continue.py.log. Nuk numërohen si prova të përfunduara.','','## Çfarë mbetet','']+['- '+x for x in summary['unfinished']]
lines+=['','ISS nuk shpallet i përfunduar. Provat me kuotë/depth të kufizuar nuk provojnë që nuk ekziston një zgjidhje më e mirë.','',f"Zgjidhja: `{best['relative_solution']}`; kopje e lehtë për Kaggle: `outputs/zgjidhja_me_e_mire.npy`.",'','Vazhdimi: lexo RESUME_STATE.json dhe KAGGLE_CELLS.md. Notebook-u origjinal dhe checkpoint-et e mëparshme janë ruajtur të paprekura.']
(R/'reports/PROGRESI.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
(R/'reports/RESUME_STATE.json').write_text(json.dumps({'status':'resumable_not_finished','best':summary['best'],'unfinished':summary['unfinished'],'commands':{'verify':'python -B code/launch.py verify.py','check_saved_heaps':'python -B code/launch.py extend.py --check-only','resume_saved_group':'python -B code/launch.py extend.py --group 94,118,127,128','prune':'python -B code/launch.py prune.py','vacancies_from_current_best':'python -B code/launch.py continue.py'},'frontier_files':[x.get('saved_frontier') for x in frontiers],'next_steps':'extend.py loads saved heap, seen g-scores, paths, coordinates and stored prefix without constructing a new root. It verifies the file SHA and officially replays that prefix. An older starting solution is kept as a historical search branch; acceptance always compares with the current global best. A finite extension adds up to 6000 states and preserves its own new snapshot without overwriting the original saved frontier.'},ensure_ascii=False,indent=2),encoding='utf-8')
archive=R/'ESA_ISS_CHECKPOINT_20261118_6edc5bdc.zip'
with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as z:
    for folder in ('code','logs','outputs','reports','state','simulation','provenance'):
        for p in (R/folder).rglob('*'):
            if p.is_file():z.write(p,Path(R.name)/p.relative_to(R))
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    assert hashlib.sha256(z.read(R.name+'/'+str(Path(best['relative_solution']).as_posix()))).hexdigest()==best['sha256']
receipt={'checkpoint_zip':str(archive),'zip_sha256':sha(archive),'zip_bytes':archive.stat().st_size,'best':summary['best'],'genuine_improvement':summary['genuine_improvement'],'protected_files_unchanged':len(manifest)}
(R/'reports/ZIP_RECEIPT.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
print(json.dumps(receipt,indent=2))
