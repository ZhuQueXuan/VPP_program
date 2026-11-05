"""Existing-truth prognostic balance probe; not a new estimator or candidate."""
from pathlib import Path
import sys,json,hashlib
import numpy as np
import pandas as pd
from scipy.special import logit
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT/'B1算法'))
sys.path.insert(0,str(ROOT/'work/b1_ev_mainline_20261030'))
from simulation import potential_outcome
from b1_algorithm.effects.continuous import local_linear_weights
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def corr(a,b):return float(np.corrcoef(a,b)[0,1])
S=ROOT/'work/b1_finish_ev_20261030/final_chain';rows=[];events=[]
protected=[ROOT/'work/b1_ev_mainline_20261030/simulation.py',ROOT/'B1算法/b1_algorithm/effects/continuous.py']
before={str(p):sha(p) for p in protected}
for seed in range(7240200,7240208):
 for scenario in ('positive','zero'):
  rec=read(S/f'factor_inputs/{seed}_{scenario}.json');alltruth=read(S/f'evaluator/{seed}_{scenario}_truth.json');truth=[alltruth[i] for i in rec['target_indices']]
  d=np.array([r['offered_incentive'] for r in rec['records']]);x=np.array([[r[k] for k in ('deadline_slack','demand_urgency')] for r in rec['records']])
  fitted=read(HERE/f'fits/{seed}_{scenario}_true_duration.json');h=fitted['diagnostics']['bandwidth'];grid=np.array(fitted['causal_curve']['incentive_values'])
  common=np.array([potential_outcome(.8,t)['cumulative_response_seconds'] for t in truth])
  z=np.column_stack([np.ones(len(d)),x]);coef=np.linalg.lstsq(z,common,rcond=None)[0]
  cd=np.cov(np.column_stack([d,x]),rowvar=False,ddof=0)[0,1:]
  prognostic_contributions=coef[1:]*cd
  common_by_dose=local_linear_weights(d,grid,h)@common
  assignment=logit(d/2.4);assignment_coef=np.linalg.lstsq(z,assignment,rcond=None)[0]
  assignment_residual=assignment-.6*x[:,0]-.8*x[:,1]
  rows.append(dict(seed=seed,scenario=scenario,events=len(d),corr_dose_L=corr(d,x[:,0]),corr_dose_U=corr(d,x[:,1]),corr_common_potential_L=corr(common,x[:,0]),
    corr_common_potential_U=corr(common,x[:,1]),corr_dose_common_potential=corr(d,common),
    common_potential_projection_intercept=float(coef[0]),common_potential_projection_L=float(coef[1]),common_potential_projection_U=float(coef[2]),
    dose_cov_L_times_common_projection=float(prognostic_contributions[0]),dose_cov_U_times_common_projection=float(prognostic_contributions[1]),
    sum_linear_projection_covariances=float(prognostic_contributions.sum()),
    opposite_projection_covariance_sign=bool(prognostic_contributions.prod()<0),
    full_sample_assignment_logit_coefficients=assignment_coef.tolist(),DGP_assignment_residual_sd=float(assignment_residual.std()),
    common_potential_unadjusted_local_curve=(common_by_dose-common.mean()).tolist(),grid=grid.tolist(),
    warning='A descriptive linear prognostic projection/covariance only; not actual nonlinear confounding bias, no causal percentages. Common-potential local curve diagnoses selection balance, not a new response estimator.'))
  events.extend(dict(seed=seed,scenario=scenario,task_id=t['task_id'],dose=float(d[i]),L=float(x[i,0]),U=float(x[i,1]),common_dose=.8,
      common_potential_duration=float(common[i])) for i,t in enumerate(truth))
result=dict(schema='b1.existing-truth-confounding-probe.v1',oracle_evaluator_only=True,scope='Already-seen paired final panel',
    source_before=before,source_unchanged=before=={str(p):sha(p) for p in protected},rows=rows,
    opposite_projection_covariance_blocks=sum(r['opposite_projection_covariance_sign'] for r in rows),
    conclusion='In this panel L/U generally predict assigned dose in the same direction but their prognostic response directions oppose; descriptive covariance terms partly offset. This does not validate ignoring confounding.')
(HERE/'confounding_probe.json').write_text(json.dumps(result,ensure_ascii=False,allow_nan=False,indent=2),encoding='utf-8')
pd.DataFrame(rows).to_csv(HERE/'confounding_probe.csv',index=False,encoding='utf-8-sig')
pd.DataFrame(events).to_csv(HERE/'common_potential_events.csv',index=False,encoding='utf-8-sig')
print(json.dumps(dict(rows=len(rows),events=len(events),opposite_sign_blocks=result['opposite_projection_covariance_blocks'],source_unchanged=result['source_unchanged'])))
