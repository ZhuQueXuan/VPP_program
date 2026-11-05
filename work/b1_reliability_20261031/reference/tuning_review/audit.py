"""Limited independent LOOU WLS and frozen-application checks; no main fitting."""
import os
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[name]='1'
from pathlib import Path
import sys,json,hashlib
from dataclasses import asdict
import numpy as np

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[3]
sys.path.insert(0,str(ROOT/'B1算法'))
from b1_algorithm.effects import tuning as t
from b1_algorithm.effects.continuous import ContinuousEffectConfig


def main():
    checks=[]
    rng=np.random.default_rng(378100)
    d=(np.arange(240)+.5)/100.
    rng.shuffle(d)
    users=np.repeat(['independent-'+str(i) for i in range(120)],2)
    x=np.zeros((240,2));groups=t.user_ids(users)
    xi=120+30*np.sin(2*d)+np.repeat(rng.normal(0,15,120),2)
    h=.35;points=np.array([.4,.8,1.2,1.6,2.])
    cfg=ContinuousEffectConfig(n_boot=99)
    result=t._loo_user_risk(x,d,xi,groups,np.ones(240),points,h,cfg)
    assert result['status']=='supported'
    prediction=np.empty(240)
    for i in range(240):
        train=groups!=groups[i]
        z=np.column_stack((np.ones(train.sum()),d[train]-d[i]))
        w=np.exp(-.5*((d[train]-d[i])/h)**2)
        # Solve weighted normal equations independently of the core kernel formula.
        prediction[i]=np.linalg.solve(z.T@(w[:,None]*z),z.T@(w*xi[train]))[0]
    expected=float(np.mean((xi-prediction)**2))
    assert abs(result['risk']-expected)<1e-10
    checks.append('LOOU risk equals independent local weighted least-squares intercepts')
    assert result['held_out_events']==240 and result['held_out_users']==120 and result['all_user_events_excluded'] is True
    checks.append('every repeated event belongs to held-out original-user block')

    # Use the existing clearly labelled control artifact, never science data.
    artifact=ROOT/'work/b1_reliability_20261031/effects/control4/selection.json'
    selection=t.load_continuous_tuning(artifact)
    payload=t.describe_continuous_tuning(selection)
    fixed=payload['fixed_context']
    kwargs=dict(evaluation_notice_min=102.,dose_domain=fixed['dose_domain'],grid=fixed['grid'],
        reference_dose=fixed['reference_dose'],incentive_unit=fixed['incentive_unit'],task=fixed['task'],
        continuous_assignment=True,assumptions=fixed['declared_assumptions'],known_density=np.full(240,1/2.4),
        covariate_names=fixed['covariate_names'])
    p,a=t._application(selection,x,d,xi,users,**kwargs)
    _,b=t._application(selection,x,d,xi+1e6,users,**kwargs)
    assert asdict(a)==asdict(b)
    checks.append('evaluation outcome level cannot retune frozen configuration')
    assert a.ridge_alpha==p['selected']['ridge_alpha'] and a.spline_knots==p['selected']['spline_knots']
    assert a.bandwidth==p['selected']['bandwidth_scale']*(1.06*np.std(d)*120**(-.2))
    checks.append('frozen alpha knots and scale applied to evaluation cohort rule')
    assert selection==t.load_continuous_tuning(artifact)
    checks.append('application does not mutate frozen selection artifact')

    receipt=dict(status='passed',checks=checks,n_checks=len(checks),manual_WLS_risk=expected,
        module_LOOU_risk=result['risk'],source_sha256=hashlib.sha256((ROOT/'B1算法/b1_algorithm/effects/tuning.py').read_bytes()).hexdigest(),
        scope='limited synthetic LOOU/frozen-application checks; no main validation/test or truth')
    with (OUT/'receipt.json').open('x',encoding='utf-8') as f:json.dump(receipt,f,ensure_ascii=False,indent=2,allow_nan=False)
    print(json.dumps(receipt,ensure_ascii=False))


if __name__=='__main__':main()
