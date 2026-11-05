"""Independent saved-output arithmetic and provenance checks, no new fitting."""
from pathlib import Path
import json,hashlib
import numpy as np
P=Path(__file__).resolve().parent;ROOT=P.parents[2];S=ROOT/'work/b1_finish_ev_20261030/final_chain'
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
checks=[]
def check(name,ok):
 if not ok:raise AssertionError(name)
 checks.append(name)
receipt=read(P/'receipt.json');points=read(P/'pointwise_decomposition.json');dec=read(P/'decomposition.json')
check('all96 original/oracle calls available without dropping',receipt['fit_calls']==96 and receipt['statuses']=={'causal':96})
check('all64 measured calls exact to saved originals',receipt['exact_replay_calls']==64 and receipt['maximum_replay_absolute_difference']==0)
for seed in range(7240200,7240208):
 for scenario in ('positive','zero'):
  factor=read(S/f'factor_inputs/{seed}_{scenario}.json');users=[r['user_id'] for r in factor['records']];groups={}
  fits=[read(P/f'fits/{seed}_{scenario}_{label}.json') for label in ('ride_revised_duration','cpop_duration','raw_duration','raw_eta','true_duration','true_eta')]
  base=fits[0]['audit'];base_cfg=fits[0]['configuration']
  check(f'same256events128users {seed} {scenario}',len(users)==256 and len(set(users))==128)
  for u,k in zip(users,base['fold_by_event']):groups.setdefault(u,set()).add(k)
  check(f'userfold integrity {seed} {scenario}',all(len(v)==1 for v in groups.values()))
  check(f'same folds densities weights config all6fits {seed} {scenario}',all(f['audit']['fold_by_event']==base['fold_by_event'] and f['audit']['stabilized_weight']==base['stabilized_weight'] and f['audit']['observed_dose_density']==base['observed_dose_density'] and f['configuration']==base_cfg for f in fits))
  check(f'original unchanged configexceptaudit {seed} {scenario}',{k:v for k,v in base_cfg.items() if k!='return_audit'}=={k:v for k,v in read(S/f'effects/{seed}_{scenario}_cpop_duration.json')['configuration'].items() if k!='return_audit'})
for i,r in enumerate(points):
 check(f'point total identity {i}',abs(r['measured_estimator']-r['intervention_truth']-r['total_error'])<1e-10)
 check(f'point A+B identity {i}',abs(r['total_error']-r['measurement_chain_component']-r['oracle_estimator_component'])<1e-10)
 check(f'point square identity {i}',abs(r['total_error']**2-r['measurement_chain_component']**2-r['oracle_estimator_component']**2-r['squared_error_cross_term'])<1e-7)
for i,r in enumerate(dec):
 check(f'curve mean squares identity {i}',abs(r['mse_total']-r['mse_measurement']-r['mse_oracle_estimation']-r['squared_error_cross_term'])<1e-7)
before=read(P/'input_source_sha256_before.json')
check('378 scientific/source inputs still unchanged',len(before)==378 and all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in before.items()))
check('allJSON finite by strict parser',all(json.loads(p.read_text(encoding='utf-8'),parse_constant=lambda x:(_ for _ in ()).throw(ValueError(x))) is not None for p in P.rglob('*.json')))
out=dict(passed=True,checks=len(checks),scope='Saved-output arithmetic/provenance only; not independent scientific trials',
    decomposition_points=len(points),protected_files=len(before),original_sources_unchanged=True,code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
(P/'verification_receipt.json').write_text(json.dumps(out,ensure_ascii=False,allow_nan=False,indent=2),encoding='utf-8')
print(json.dumps(out,ensure_ascii=False))
