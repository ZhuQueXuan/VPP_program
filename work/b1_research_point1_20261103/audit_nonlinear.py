"""Independent fitted-state and mathematical-query audit on new inputs."""
from pathlib import Path
import hashlib
import json
import sys
import numpy as np

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'B1算法'))
from b1_algorithm.effects import nonlinear as N
from b1_algorithm.effects.frozen import fit_continuous_model,FrozenContinuousModel,_json

rng=np.random.default_rng(90335991)
X=rng.uniform(-1,1,(480,2)); d=rng.uniform(.005,2.395,len(X))
users=np.repeat([f'audit-new-user{i}' for i in range(240)],2)
y=350+85*d+45*d*d+30*X[:,0]+35*d*X[:,1]+rng.normal(0,2,len(d))
cfg=dict(seed=90335992,bandwidth=.24,n_boot=99,min_local_users=8,min_local_events=10,min_local_ess=8,max_weighted_smd=1.)
grid=np.array([.4,.73,1.17,1.65,2.])
model=N.fit_nonlinear_effects(X,d,y,users,dose_domain=[0,2.4],known_density=np.full(len(d),1/2.4),config=cfg)
largest=0.
for a in grid:
    m,b=N._query_values(model,a)
    plus,_=N._query_values(model,a+1e-5);minus,_=N._query_values(model,a-1e-5)
    largest=max(largest,float(np.max(abs(b-(plus-minus)/(2e-5)))))
assert largest<1e-5,largest
q=N.query_nonlinear_effects(model,grid,include_scores=True)
assert q['status']=='ok',q
reference=[]
for a in grid:
    m,b=N._query_values(model,a);acc=0.
    for i in range(len(d)):
        z=(d[i]-a)/.24;k=.75*(1-z*z) if abs(z)<=1 else 0.
        acc+=b[i]+z*k/(.24**2*.2*(1/2.4))*(y[i]-m[i]-(d[i]-a)*b[i])
    reference.append(acc/len(d))
scalar_error=float(np.max(abs(np.asarray(q['estimates'])-reference)))
assert scalar_error<1e-8
extended=np.sort(np.r_[grid,.61,.92,1.91]);q2=N.query_nonlinear_effects(model,extended)
ix=[int(np.flatnonzero(extended==a)[0]) for a in grid]
assert np.allclose(np.asarray(q2['estimates'])[ix],q['estimates'],rtol=0,atol=1e-12)
N.save_nonlinear_model(model,HERE/'audit_new_nonlinear_model.json')
loaded=N.load_nonlinear_model(HERE/'audit_new_nonlinear_model.json')
assert N.query_nonlinear_effects(loaded,grid)['estimates']==q['estimates']

task=dict(task_id='audit-new-math-input',outcome_name='seconds',outcome_unit='seconds',
          target_population='new audit constructed cohort',window_minutes=[0,30],q_kw=1.5,
          task_pre_treatment=True,reference_status='provided',reference_uncertainty='known_reference')
assumptions=dict(pre_treatment_X=True,consistent_treatment=True,no_interference=True,same_outcome_definition=True,
                 conditional_exchangeability=True,randomized_assignment=True)
frozen=fit_continuous_model(X,d,y,users,dose_domain=[0,2.4],reference_dose=.4,incentive_unit='yuan/kWh',
             task=task,continuous_assignment=True,assumptions=assumptions,known_density=np.full(len(d),1/2.4),config=cfg)

# Controlled frozen pseudo-outcome fixture tests the linear operator itself.
# This is not a fitted causal curve or performance result.
def mathematical_state(xi,h=.08):
    p=json.loads(frozen.payload_json);p['pseudo_outcome']=xi.tolist();p['bandwidth']=h
    p['residual']=np.zeros(len(xi)).tolist();p['metadata']={'audit_role':'constructed pseudo-outcome mathematical fixture'}
    raw=_json(p)
    return FrozenContinuousModel(raw,hashlib.sha256(raw.encode()).hexdigest())

dense=np.linspace(.4,2.,161)
poly=500+80*d+40*d*d
r=N.bias_corrected_curve_summary(mathematical_state(poly),dense,target_contrast=120.)
expected=500+80*dense+40*dense*dense
quadratic_error=float(np.max(abs(np.asarray(r['mean_outcomes'])-expected)))
assert quadratic_error<1e-6,quadratic_error
osc=600+200*np.sin(2*np.pi*d/.8)
r2=N.bias_corrected_curve_summary(mathematical_state(osc),dense,target_contrast=60.)
assert len(r2['upward_crossings'])>=2,r2['upward_crossings']
unreached=N.bias_corrected_curve_summary(mathematical_state(osc),dense,target_contrast=2000.)
assert unreached['first_crossing'] is None and unreached['not_reached_possible']

result=dict(status='passed',new_users=240,new_events=480,
    fitted_spline_derivative_vs_independent_central_difference_max=largest,
    direct_derivative_vs_independent_scalar_max=scalar_error,
    saved_loaded_estimates_exact=True,query_insertion_invariant=True,
    finite_design_quadratic_correction_error=quadratic_error,
    constructed_oscillatory_upcrossings=r2['upward_crossings'],not_reached_correct=True,
    sources='new constructed fit data and separately labelled mathematical pseudo-outcome fixtures; no old test',
    performance_or_coverage_claim=False)
with (HERE/'audit_nonlinear_result.json').open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
print(json.dumps(result,ensure_ascii=False))
