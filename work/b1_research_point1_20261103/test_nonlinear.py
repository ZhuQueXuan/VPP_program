from pathlib import Path
import sys,json,hashlib
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'B1算法'))
from b1_algorithm.effects.nonlinear import (fit_nonlinear_effects,query_nonlinear_effects,
    _query_values,save_nonlinear_model,load_nonlinear_model,bias_corrected_curve_summary)
from b1_algorithm.effects.continuous import _crossfit,_config,local_linear_weights
from b1_algorithm.effects.frozen import fit_continuous_model,FrozenContinuousModel,_json

HERE=Path(__file__).resolve().parent
rng=np.random.default_rng(90323101); users=np.repeat(np.arange(240),2);n=len(users)
x=rng.uniform(-1,1,(n,2));d=rng.uniform(.001,2.399,n)
y=350+85*d+45*d*d+30*x[:,0]+35*d*x[:,1]+rng.normal(0,12,n)
cfg=dict(seed=90323101,n_boot=99,bandwidth=.24)
model=fit_nonlinear_effects(x,d,y,users,dose_domain=[0,2.4],config=cfg)
xi,w,folds,_,mu,pdf=_crossfit(x,d,y,np.asarray(model['users']),_config(cfg),[0,2.4],None)
assert np.array_equal(folds,model['fold_by_event'])
assert np.max(abs(pdf-np.asarray(model['observed_density'])))<1e-12
assert np.max(abs(mu-np.asarray(model['outcome_prediction'])))<1e-10
epsilon=1e-5;derivative_error=0
for a in [.4,.73,1.17,1.65,2.]:
    m,beta=_query_values(model,a)
    numeric=(_query_values(model,a+epsilon)[0]-_query_values(model,a-epsilon)[0])/(2*epsilon)
    derivative_error=max(derivative_error,float(np.max(abs(numeric-beta))))
assert derivative_error<1e-5,derivative_error
query=query_nonlinear_effects(model,[.4,.73,1.17,1.65,2.])
assert query['status']=='ok',query
insert=query_nonlinear_effects(model,[.4,.51,.73,.92,1.17,1.65,2.])
assert query['estimates'][1]==insert['estimates'][2]
path=HERE/'nonlinear_test_model.json';save_nonlinear_model(model,path)
reloaded=query_nonlinear_effects(load_nonlinear_model(path),[.4,.73,1.17,1.65,2.])
assert query==reloaded
sub=query_nonlinear_effects(model,[.4,.73,1.17,1.65,2.],event_mask=x[:,1]>=0)
bad=query_nonlinear_effects(model,[.4],event_mask=np.arange(n)<2)
assert bad['status']=='unsupported'
boundary=query_nonlinear_effects(model,[.05])
assert boundary['status']=='unsupported'

task=dict(task_id='poly-test',outcome_name='seconds',outcome_unit='seconds',target_population='constructed',
    window_minutes=[0,30],q_kw=1.5,task_pre_treatment=True,reference_status='provided')
frozen=fit_continuous_model(x,d,y,users,dose_domain=[0,2.4],reference_dose=.4,
    incentive_unit='amount',task=task,continuous_assignment=True,config=cfg)
p=json.loads(frozen.payload_json)
errors={}
for degree in [0,1,2]:
    exact=300+100*d**degree
    p['pseudo_outcome']=exact.tolist();p['residual']=[0.]*n
    s=_json(p);f=FrozenContinuousModel(s,hashlib.sha256(s.encode()).hexdigest())
    out=bias_corrected_curve_summary(f,np.linspace(.4,2.,9),target_contrast=120.)
    assert out['status']=='ok',out
    expected=300+100*np.linspace(.4,2.,9)**degree
    errors[str(degree)]=float(np.max(abs(np.asarray(out['mean_outcomes'])-expected)))
    assert errors[str(degree)]<1e-8,errors
assert len(out['upward_crossings'])==1
assert abs(out['upward_crossings'][0]-np.sqrt(.4**2+1.2))<1e-7
result=dict(status='passed',events=n,users=240,nuisance_prediction_match=float(np.max(abs(mu-np.asarray(model['outcome_prediction'])))),
    observed_density_match=float(np.max(abs(pdf-np.asarray(model['observed_density'])))),
    analytic_spline_derivative_max_error=derivative_error,query_insertion_exact=True,json_reload_exact=True,
    subgroup_status=sub['status'],unsupported_small_group=bad['status'],unsupported_kernel_boundary=boundary['status'],
    polynomial_reproduction_errors=errors,quadratic_target_crossing=out['upward_crossings'][0],
    derivative_estimates=query['estimates'],full_causal_coverage_claimed=False)
with (HERE/'nonlinear_test_receipt.json').open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2)
print(json.dumps(result))
