"""Independent cross-review probes for frozen.py; no main-study mutation."""
from pathlib import Path
import os
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[name]='1'
import sys
import json
import hashlib
from dataclasses import replace
import numpy as np

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT/'B1算法'))
import b1_algorithm.effects.frozen as f
import b1_algorithm.effects.continuous as c


def main():
    outdir=HERE/'round2';outdir.mkdir(exist_ok=True)
    observations=[];checks=[]
    def check(name,condition,detail=None):
        checks.append(dict(name=name,passed=bool(condition),detail=detail))
    def probe(name,fn):
        try:
            result=fn();entry=dict(name=name,result='accepted',value=result)
        except Exception as exc:
            entry=dict(name=name,result='rejected',exception=type(exc).__name__,message=str(exc))
        observations.append(entry);return entry
    rng=np.random.default_rng(9261030);n=960
    X=rng.normal(size=(n,2));dose=rng.uniform(.01,2.39,n)
    users=np.repeat(np.arange(240),4)
    user_effect=rng.normal(0,10,240)[users]
    Y=40*np.sin(5*dose)+35*dose+X[:,0]*dose+user_effect+rng.normal(0,4+2*dose,n)
    task=dict(task_id='independent-frozen-EV30',outcome_name='raw_duration',outcome_unit='seconds',
        target_population='independent mathematical cohort',window_minutes=[0,30],q_kw=1.5,
        task_pre_treatment=True,reference_status='provided',reference_uncertainty='not_propagated')
    assumptions=dict(pre_treatment_X=True,consistent_treatment=True,no_interference=True,
        same_outcome_definition=True,conditional_exchangeability=None,randomized_assignment=True)
    options=dict(dose_domain=[0,2.4],reference_dose=.9,incentive_unit='CNY',task=task,
        continuous_assignment=True,assumptions=assumptions,known_density=np.full(n,1/2.4),
        config=dict(seed=6013,n_boot=99,bandwidth=.22))
    model=f.fit_continuous_model(X,dose,Y,users,**options)
    source_sha=hashlib.sha256((ROOT/'B1算法/b1_algorithm/effects/frozen.py').read_bytes()).hexdigest()
    grids=[[.25,.7,.9,1.01,1.3,1.8,2.1],[.9],[.52,.89,1.51]]
    for grid in grids:
        q=f.query_continuous_model(model,grid)
        direct=c.fit_continuous_effects(X,dose,Y,users,grid=grid,**options)
        check('independent nonmonotonic means direct identity '+str(grid),np.allclose(q['curve']['mean_outcomes'],direct['causal_curve']['mean_outcomes'],atol=1e-10,rtol=0))
        check('independent nonmonotonic contrast direct identity '+str(grid),np.allclose(q['curve']['contrasts'],direct['causal_curve']['contrasts'],atol=1e-10,rtol=0))
        for field in ('standard_errors','lower','upper'):
            check('same requested grid original band '+field+str(grid),np.allclose(q['inference'][field],direct['inference'][field],atol=1e-10,rtol=0))
    observational=options|dict(known_density=None,assumptions=assumptions|dict(randomized_assignment=False,conditional_exchangeability=True))
    obs_model=f.fit_continuous_model(X,dose,Y,users,**observational)
    obs_grid=[.4,.9,1.35,2.]
    obs_query=f.query_continuous_model(obs_model,obs_grid)
    obs_direct=c.fit_continuous_effects(X,dose,Y,users,grid=obs_grid,**observational)
    check('estimated GPS path same means',np.allclose(obs_query['curve']['mean_outcomes'],obs_direct['causal_curve']['mean_outcomes'],atol=1e-10,rtol=0))
    check('estimated GPS path same conditional upper',np.allclose(obs_query['inference']['upper'],obs_direct['inference']['upper'],atol=1e-10,rtol=0))
    # Derivative tested on the complete non-affine fitted mean, at very
    # unequal spacings and both declared support edges (kernel stays defined).
    p=json.loads(model.payload_json);xi=np.asarray(p['pseudo_outcome']);d=np.asarray(p['dose']);h=p['bandwidth']
    points=np.array([0.,.137,.611,1.083,1.974,2.4]);epsilon=3e-6
    analytic=f.local_linear_derivative_weights(d,points,h)@xi
    def mean(a):return c.local_linear_weights(d,np.asarray(a),h)@xi
    central=(mean(points+epsilon)-mean(points-epsilon))/(2*epsilon)
    check('non-affine whole-curve derivative incl boundaries',np.max(abs(analytic-central))<1e-6,float(np.max(abs(analytic-central))))
    # A local fitted slope differs from the derivative except for affine curves.
    u=(d[None,:]-points[:,None])/h;k=np.exp(-.5*u*u)
    s0=k.sum(1);s1=(k*u).sum(1);s2=(k*u*u).sum(1)
    slope=((s0[:,None]*k*u-s1[:,None]*k)@xi)/(s0*s2-s1*s1)/h
    check('sensitivity is not mislabeled local slope',np.max(abs(analytic-slope))>1.)
    currency=37.
    scaled=f.local_linear_derivative_weights(d*currency,points*currency,h*currency)@xi
    check('nondecimal currency rescaling reciprocal',np.allclose(scaled*currency,analytic,atol=1e-10,rtol=0))
    # Block both the public fit entry and underlying crossfit. Queries should
    # need neither, even for threshold root refinement and sensitivity bands.
    before=model.payload_json;old_f=f.fit_continuous_effects;old_c=c._crossfit
    def forbidden(*a,**kw):raise AssertionError('new fit during query')
    f.fit_continuous_effects=forbidden;c._crossfit=forbidden
    try:
        q=f.query_continuous_model(model,[.7,.9,1.3])
        threshold=f.find_incentive_threshold(model,target_contrast=10,search_domain=[.4,2.0],mesh_step=.07)
        check('threshold and derivative never fit',q['refitted'] is False and model.payload_json==before)
    finally:f.fit_continuous_effects=old_f;c._crossfit=old_c
    check('mesh actual maximum width respects request',threshold['mesh_max_width']<=.07+1e-14)
    check('threshold keeps finite-mesh limitation',threshold['continuous_threshold_coverage_validated'] is False and threshold['optimal_price'] is False)
    # Hand-built mathematical pseudo-outcome fixtures, explicitly association
    # and zero residual, isolate crossing logic without nuisance simulation.
    def fixture(values,association=True,changes=None):
        value=json.loads(model.payload_json);value['pseudo_outcome']=np.asarray(values).tolist();value['residual']=[0.]*n
        if association:
            value['status']='association';value['known_density_used']=False
            value['declared_assumptions']['randomized_assignment']=False
        if changes:changes(value)
        payload=f._json(value)
        return f.FrozenContinuousModel(payload,hashlib.sha256(payload.encode()).hexdigest())
    oscillatory=fixture(100*np.sin(10*d))
    many=f.find_incentive_threshold(oscillatory,target_contrast=15,search_domain=[.3,2.1],mesh_step=.025)
    check('association label survives threshold',many['query_status']=='association' and many['candidate_cells']==[] and many['not_reached_possible'] is None)
    check('multiple isolated crossings represented',len(many['point_crossings'])>=2,len(many['point_crossings']))
    if many['point_crossings']:
        check('first crossing ordered or left censored',many['first_point_crossing']<=min(z['dose'] for z in many['point_crossings']))
        for crossing in many['point_crossings']:
            value=f.query_continuous_model(oscillatory,[crossing['dose']])['curve']['contrasts'][0]
            check('every crossing root solves same curve',abs(value-15)<1e-6)
    absent=f.find_incentive_threshold(fixture(np.zeros(n)),target_contrast=1,search_domain=[.3,2.1],mesh_step=.025)
    check('flat zero no crossing explicit',absent['status']=='point_not_reached_on_mesh' and absent['first_point_crossing'] is None)
    lower=f.find_incentive_threshold(fixture(100*d),target_contrast=10,search_domain=[1.2,2.],mesh_step=.05)
    check('already reached interval left-censor explicit',lower['first_point_crossing']==1.2 and lower['left_censored_at_search_start'] is True)
    # Explicitly fail a support rule instead of assuming support edges fail.
    unsupported_model=fixture(xi,association=False,changes=lambda z:z['configuration'].update(min_local_events=10000))
    unsupported=f.find_incentive_threshold(unsupported_model,target_contrast=10,search_domain=[0.,2.4],mesh_step=.04)
    check('unsupported mesh never returns numeric threshold',unsupported['status']=='unsupported' and unsupported['first_point_crossing'] is None)
    # New contract counterexamples. SHA is recomputed to test validation
    # rather than integrity; this is not a claim about artifact authenticity.
    for value in (1,'false',[],{}):
        def alter(state,value=value):state['known_density_used']=value
        forged=fixture(xi,association=False,changes=alter)
        entry=probe('known_density_used type '+repr(value),lambda forged=forged:f.query_continuous_model(forged,[.9])['status'])
        check('strict known-density flag '+repr(value),entry['result']=='rejected')
    badmodel=f.FrozenContinuousModel(None,'x')
    malformed=probe('model payload None',lambda:f.query_continuous_model(badmodel,[.9]))
    check('malformed payload rejects via ValueError',malformed.get('exception')=='ValueError',malformed)
    badpath=outdir/'invalid_envelope.json'
    badpath.write_text(json.dumps(dict(payload_json=123,sha256='x')),encoding='utf-8')
    malformed=probe('load numeric payload',lambda:f.load_continuous_model(badpath))
    check('malformed envelope rejects via ValueError',malformed.get('exception')=='ValueError',malformed)
    # Corrupt causal status cannot promote an unconfirmed association.
    entry=probe('causal status promotion without assumptions',lambda:f.query_continuous_model(fixture(xi,changes=lambda z:z.update(status='causal')),[.9]))
    check('causal status cannot override missing declarations',entry['result']=='rejected')
    path=outdir/'valid_model.json';f.save_continuous_model(model,path)
    check('independent roundtrip exact',f.load_continuous_model(path)==model)
    receipt=dict(source_sha256=source_sha,checks=checks,passed=sum(c['passed'] for c in checks),
        failed=sum(not c['passed'] for c in checks),observations=observations,
        scientific_results_changed=False,main_study_run=False)
    (outdir/'receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(passed=receipt['passed'],failed=receipt['failed'],observations=observations),ensure_ascii=False))


if __name__=='__main__':main()
