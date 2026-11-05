from common import *
assert not read('assessment.json')['adopted']
assert all(v for k,v in read('assessment.json')['checks'].items() if k!='false_reduction10')
paths=[HERE/p for p in ['confirmation_plan.json','confirm_data.py','confirm_evaluate.py','selected.json']]
paths += [HERE/f'verifier{read("selected.json")["config"]["leaves"]}.json']
write('confirmation_freeze.json',dict(source_sha256={p.relative_to(ROOT).as_posix():sha(p) for p in paths},configuration=read('selected.json')['config'],no_confirmation_draw_yet=True,first_gate_failure_preserved=True))
print('One fixed larger confirmation frozen; same model and configuration',flush=True)
