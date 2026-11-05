"""Functional/math checks: invariance, differentiation, identity and refusal."""
import os
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
import sys,json,hashlib
from pathlib import Path
from dataclasses import replace
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'B1算法'))
from b1_algorithm.effects.continuous import fit_continuous_effects,ContinuousEffectConfig,local_linear_weights
import b1_algorithm.effects.continuous as core
import b1_algorithm.effects.frozen as f

checks=[]
def check(name,condition):
    assert condition,name
    checks.append(name)
def rejects(name,fn):
    try:fn()
    except (ValueError,TypeError,KeyError,OSError):checks.append(name);return
    raise AssertionError(name)

rng=np.random.default_rng(7310000);n=800
x=rng.normal(size=(n,2));d=rng.uniform(.001,2.399,n);users=[f'u{i//2}' for i in range(n)]
y=100+180*(1-np.exp(-d))+20*x[:,0]+rng.normal(0,25,n)
task=dict(task_id='math-EV30',outcome_name='duration',outcome_unit='seconds',target_population='simulated',window_minutes=[0,30],q_kw=1.5,task_pre_treatment=True,reference_status='known',reference_uncertainty='known_reference')
assumptions={v:True for v in ('pre_treatment_X','consistent_treatment','no_interference','same_outcome_definition','randomized_assignment')}
options=dict(dose_domain=[0,2.4],reference_dose=.8,incentive_unit='CNY',task=task,continuous_assignment=True,assumptions=assumptions,known_density=np.full(n,1/2.4),config=ContinuousEffectConfig(seed=42,n_boot=199,bandwidth=.3))
grid=np.array([.4,.73,.8,1.17,1.8,2.0])
m=f.fit_continuous_model(x,d,y,users,**options)
q=f.query_continuous_model(m,grid); direct=fit_continuous_effects(x,d,y,users,grid=grid,**options)
check('causal identity status',q['status']==direct['status']=='causal')
for key in ('mean_outcomes','contrasts'):
    check('exact shared DR '+key,np.allclose(q['curve'][key],direct['causal_curve'][key],atol=1e-10,rtol=0))
for key in ('lower','upper','standard_errors'):
    check('exact shared conditional band '+key,np.allclose(q['inference'][key],direct['inference'][key],atol=1e-10,rtol=0))
check('zero reference contrast',q['curve']['contrasts'][2]==0.)
model_path=ROOT/'work/b1_finish_ev_20261030/functional_model_corrected.json'
saved=f.save_continuous_model(m,model_path)
loaded=f.load_continuous_model(model_path)
check('save load byte identity',m==loaded)
check('save load query exact',f.query_continuous_model(loaded,grid)==q)
rejects('exclusive save refuses overwrite',lambda:f.save_continuous_model(m,model_path))
rejects('tamper checksum',lambda:f.query_continuous_model(replace(m,payload_json=m.payload_json+' '),grid))
for bad in ([True],['.8'],[float('nan')],[2.5],[.8,.7],[.8,.8],[]):
    rejects('reject invalid query '+repr(bad),lambda bad=bad:f.query_continuous_model(m,bad))
old=core._crossfit
def forbidden(*a,**k):raise AssertionError('query retrained nuisance')
core._crossfit=forbidden
try:
    check('queries do not retrain',f.query_continuous_model(m,grid)==q)
    t=f.find_incentive_threshold(m,target_contrast=20,search_domain=[.4,2.0],mesh_step=.04)
    check('threshold no retraining',t['status']=='point_reached')
finally:core._crossfit=old
check('threshold correct numeric root',abs(f.query_continuous_model(m,[t['first_point_crossing']])['curve']['contrasts'][0]-20)<1e-6)
check('threshold not continuous CI',t['continuous_threshold_coverage_validated'] is False)
check('unreachable target explicit',f.find_incentive_threshold(m,target_contrast=1e6,search_domain=[.4,2.0],mesh_step=.04)['status']=='point_not_reached_on_mesh')
rejects('invalid mesh size',lambda:f.find_incentive_threshold(m,target_contrast=20,search_domain=[.4,2.],mesh_step=.0001))
rejects('invalid target bool',lambda:f.find_incentive_threshold(m,target_contrast=True,search_domain=[.4,2.],mesh_step=.04))
dw=f.local_linear_derivative_weights(d,grid,.3)
check('derivative constants zero',np.max(abs(dw@np.ones(n)))<1e-10)
check('derivative affine exact',np.max(abs(dw@d-1))<1e-10)
eps=1e-6
numeric=(local_linear_weights(d,grid+eps,.3)-local_linear_weights(d,grid-eps,.3))/(2*eps)
check('derivative finite difference',np.max(abs(dw-numeric))<1e-8)
check('currency scaling',np.max(abs(f.local_linear_derivative_weights(d*100,grid*100,30)*100-dw))<1e-10)
p=json.loads(m.payload_json);p['status']='association';p['declared_assumptions']['conditional_exchangeability']=None;p['declared_assumptions']['randomized_assignment']=False
def synthetic(xi):
    a=p.copy();a['pseudo_outcome']=xi.tolist();a['residual']=[0.]*n
    s=f._json(a);return f.FrozenContinuousModel(s,hashlib.sha256(s.encode()).hexdigest())
qa=f.query_continuous_model(synthetic(d),grid)
check('association has no causal bands',qa['status']=='association' and qa['inference'] is None and qa['sensitivity']['inference'] is None)
# Multiple disjoint up-crossings, no forced monotonicity.
nonmono=synthetic(300*np.sin(7*d))
t2=f.find_incentive_threshold(nonmono,target_contrast=20,search_domain=[.25,2.2],mesh_step=.02)
check('nonmonotonic multiple crossings',len(t2['point_crossings'])>=2)
strict=replace(options['config'],min_local_events=100000)
rejects('unsupported fit cannot become artifact',lambda:f.fit_continuous_model(x,d,y,users,**(options|{'config':strict})))
before=json.loads((ROOT/'work/b1_finish_ev_20261030/before_source.json').read_text(encoding='utf-8'))
check('original continuous core unchanged',hashlib.sha256((ROOT/'B1算法/b1_algorithm/effects/continuous.py').read_bytes()).hexdigest()==before['B1算法/b1_algorithm/effects/continuous.py'])
receipt=dict(passed=len(checks),checks=checks,model_id=m.sha256,numeric_root=t['first_point_crossing'],multiple_crossings=t2['point_crossings'])
(ROOT/'work/b1_finish_ev_20261030/frozen_check_receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(receipt,ensure_ascii=False))
