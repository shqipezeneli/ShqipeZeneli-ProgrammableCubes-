"""Independent fresh-process official verification; no optimization."""
import runtime as r
import core as c
import json,time,uuid
r.initialize();token=r.phase_start('independent_final_verification')
commands,positions,value,sha=r.load_best()
result=c.validate(c.chromosome(commands))
assert c.np.array_equal(positions,c.np.asarray(result['positions']))
assert abs(value-result['official_fitness'])<1e-12
assert not result['ineffective_commands']
result.update(independent_fresh_process=True,sha256=sha,relative_solution=r.best_record()['relative_solution'])
path=c.RUN/'outputs'/('independent_verification_'+uuid.uuid4().hex[:8]+'.json')
c.write_new(path,result)
r.atomic(c.RUN/'outputs/remaining_latest.json',c.analyze(result['positions']))
r.atomic(c.RUN/'state/independent_final_verification.json',result)
r.phase_end(token,'completed',verification_file=str(path.relative_to(c.RUN)),prefixes=result['prefixes_checked'])
r.emit('official_verification_passed',fitness=value,correct_cubes=result['correct_cubes'],commands=result['commands'],ineffective_commands=0,solution=result['relative_solution'])
