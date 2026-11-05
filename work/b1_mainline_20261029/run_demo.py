"""Run small research API examples and domain checks; no main experiments."""
from pathlib import Path
import json
import numpy as np
from b1_research_api import identify_response,estimate_incentive_effects

ROOT=Path(__file__).resolve().parent
events=json.loads((ROOT/'process/main/events.json').read_text(encoding='utf-8'))
example=next(e for e in events if e['rep']==0 and e['mechanism']=='slow' and e['delta_min']==1 and e['sigma_kw']==.15)
z=np.load(ROOT/'process/main/all_curves.npz')
y=z[f"{example['event_id']}_y"]
s=np.arange(-15.,45.);e=s+1;p=3.-y;b=np.full(len(s),3.)
outputs={m:identify_response(s,e,p,b,.15,method=m) for m in ['task_template','grid_average']}
assert np.isclose(outputs['task_template']['eta_raw'],outputs['grid_average']['eta_raw'])
assert all(o['physical_timing'] is None for o in outputs.values())
checks=[]
for label,call in [
 ('request_out_of_domain',lambda:identify_response(s,e,p,b,.15,method='task_template',request_kw=3)),
 ('missing_power',lambda:identify_response(s,e,np.where(s==0,np.nan,p),b,.15,method='task_template')),
 ('boolean_noise',lambda:identify_response(s,e,p,b,True,method='task_template')),
 ('invalid_bootstrap',lambda:estimate_incentive_effects(None,None,None,None,n_boot=True)),
 ('invalid_alpha',lambda:estimate_incentive_effects(None,None,None,None,alpha=1.)),
]:
 try: call()
 except ValueError: checks.append(label)
 else: raise AssertionError(label+' was not rejected')
c=np.load(ROOT/'causal/results/external_prediction_reference.npz')
effect=estimate_incentive_effects(c['X'],c['d'],c['y'],c['groups'],seed=291000,n_boot=999)
assert effect['identified'] and effect['curve'] is not None
result=dict(status='passed',example_selection='first fixed seed, slow mechanism, 1min,.15kW; not best-case selection',
       process=outputs,causal=effect,boundary_checks_passed=checks,
       scope='component API demonstration; causal example is separate from the one-event process example')
(ROOT/'demo_output.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print('Research API demonstration and five domain checks passed; demo_output.json saved.')
