"""Independent persisted-artifact verification; no scientific implementation imports.

Recomputes observation integrals, dense Gaussian covariance propagation, fixed
and simultaneous intervals, decisions, first grid endpoints, and all metrics.
This verifies the declared synthetic model, not real-world service recovery.
"""
from pathlib import Path
import ast
import csv
import hashlib
import json
import math

import numpy as np
from scipy.stats import norm, beta

BASE = Path(__file__).resolve().parent
PROJECT = BASE.parent.parent
CHECKS = []


def check(name, ok, detail=None):
    CHECKS.append(dict(name=name, passed=bool(ok), detail=detail))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def maximum_error(a, b):
    return float(np.max(np.abs(np.asarray(a)-np.asarray(b))))


def same_with_nan(a,b):
    return np.array_equal(a,b,equal_nan=True)


def first_time(mask, times):
    ans=[]
    for row in mask:
        hits=np.flatnonzero(row)
        ans.append(times[hits[0]] if len(hits) else np.nan)
    return np.array(ans)


def clopper_pearson(k,n):
    lo=0. if k==0 else float(beta.ppf(.025,k,n-k+1))
    hi=1. if k==n else float(beta.ppf(.975,k+1,n-k))
    return lo,hi


def main():
    p=json.loads((BASE/'protocol.json').read_text(encoding='utf-8'))
    raw_path=PROJECT/p['raw_root']/'observations.npz'
    raw=np.load(raw_path,allow_pickle=False)
    fitted=np.load(BASE/'intervals.npz',allow_pickle=False)
    truth=np.load(BASE/'evaluator_truth.npz',allow_pickle=False)
    receipt=json.loads((BASE/'run_receipt.json').read_text(encoding='utf-8'))
    frozen=json.loads((BASE/'source_freeze.json').read_text(encoding='utf-8'))
    models=p['observation_models'];mechs=list(p['mechanisms']);reps=p['repetitions_per_cell']
    check('factual artifact contains only public observed fields',
          set(raw.files)=={'time_edges_s','reference_kw','power_obs_kw'},raw.files)
    check('public observation shape',(raw['power_obs_kw'].shape==(5,4,1000,360)))
    check('interval shape',(fitted['debt_path'].shape==(5,4,1000,180)))
    check('first grid endpoint shape',fitted['first_possible'].shape==(5,4,4,1000)
          and fitted['first_supported'].shape==(5,4,4,1000))
    check('protocol prior to generating retained observations',receipt['protocol_sha256']==sha(BASE/'protocol.json'))
    check('raw and intervals identity',receipt['raw_sha256']==sha(raw_path)
          and receipt['intervals_sha256']==sha(BASE/'intervals.npz'))
    check('evaluator truth not available during estimation',receipt['truth_existed_before_estimation'] is False)
    for name,digest in frozen.items():
        check('frozen source identity '+name,sha(BASE/name)==digest)
    t=raw['time_edges_s']
    check('predeclared grid',np.array_equal(t,np.arange(0,3601,10)))
    # Independent overlap weights. The dot/covariance implementation deliberately
    # differs from recovery.profile's online AR covariance recursion.
    dt=np.diff(t)
    weights=np.array([max(0.,min(right,3600.)-max(left,600.))/3600.
                      for left,right in zip(t[:-1],t[1:])])
    post_indices=np.flatnonzero(t[1:]>1800.)
    times=t[1:][post_indices]
    check('finite simultaneous family fixed in advance',len(times)==180
          and np.array_equal(times,np.arange(1810.,3601.,10.))
          and np.array_equal(times,fitted['post_times_s']))
    check('bias integration includes request through deadline',abs(float(weights.sum())-5/6)<1e-14)
    prefix=np.array([weights*(np.arange(len(weights))<=j) for j in post_indices])
    sigma=p['measurement']['marginal_sigma_kw']
    distance=np.abs(np.subtract.outer(np.arange(360),np.arange(360)))
    z_fixed=norm.ppf(1-p['alpha']/2)
    z_path=norm.ppf(1-p['alpha']/(2*len(times)))
    independent_truth=[]
    # An independently formed power rectangle, integrated on the persisted grid,
    # checks evaluation.py's direct post-release debt formula.
    for name,target in p['mechanisms'].items():
        power=np.full(360,3.)
        if name!='no_action':
            power[(t[:-1]>=600)&(t[:-1]<1800)]=1.5
            gain=(.5-target)*3600/(2520-1800)
            power[(t[:-1]>=1800)&(t[:-1]<2520)]=3+gain
        check(name+' declared power bounds',power.min()>=0 and power.max()<=6)
        cumulative=np.cumsum((3-power)*dt/3600)
        independent_truth.append(cumulative[post_indices])
    independent_truth=np.array(independent_truth)
    truth_err=maximum_error(independent_truth,truth['debt_path'])
    check('true path independently integrated from rectangles',truth_err<1e-12,truth_err)
    check('true endpoint independently integrated',maximum_error(independent_truth[:,-1],truth['endpoint'])<1e-12)
    # Main declaration creates repeated observation-model versions, not independent
    # physical/noise samples; verify those identities explicitly.
    check('iid variants share factual power draws',np.array_equal(raw['power_obs_kw'][0],raw['power_obs_kw'][3])
          and np.array_equal(raw['power_obs_kw'][0],raw['power_obs_kw'][4]))
    check('AR variants share factual power draws',np.array_equal(raw['power_obs_kw'][1],raw['power_obs_kw'][2]))
    metrics=[];decisions=[];worst_integral=0.;worst_width=0.
    for s,model in enumerate(models):
        rho=.8 if model=='ar1_correct' else 0.
        bias_bound=.02 if model=='reference_bias_bounded' else 0.
        covariance=sigma*sigma*np.power(rho,distance)
        # Each row is an independently constructed prefix integral vector.
        variance=np.einsum('ij,jk,ik->i',prefix,covariance,prefix)
        sd=np.sqrt(np.maximum(variance,0.))
        bounded_bias=bias_bound*np.abs(prefix).sum(axis=1)
        path_width=z_path*sd+bounded_bias
        end_width=z_fixed*sd[-1]+bounded_bias[-1]
        check(model+' declared reference bias',np.allclose(raw['reference_kw'][s],3.+(.02 if model.startswith('reference_bias') else 0.),atol=0,rtol=0))
        observed=np.cumsum((raw['reference_kw'][s][None,None,:]-raw['power_obs_kw'][s])*weights,axis=-1)
        path=observed[...,post_indices]
        endpoint=observed[...,-1]
        lo,hi=endpoint-end_width,endpoint+end_width
        err=max(maximum_error(path,fitted['debt_path'][s]),maximum_error(endpoint,fitted['endpoint_debt'][s]),
                maximum_error(lo,fitted['endpoint_lower'][s]),maximum_error(hi,fitted['endpoint_upper'][s]))
        worst_integral=max(worst_integral,err)
        width_err=max(maximum_error(path_width,fitted['path_width'][s]),abs(end_width-fitted['endpoint_width'][s]))
        worst_width=max(worst_width,width_err)
        check(model+' public integral and fixed bounds',err<1e-12,err)
        check(model+' independent dense covariance widths',width_err<1e-12,width_err)
        for m,name in enumerate(mechs):
            true=truth['endpoint'][m]
            covers=(lo[m]<=true+1e-14)&(hi[m]>=true-1e-14)
            path_covers=np.all((path[m]-path_width<=truth['debt_path'][m]+1e-14)
                               &(path[m]+path_width>=truth['debt_path'][m]-1e-14),axis=1)
            ci=clopper_pearson(int(covers.sum()),reps)
            metrics.append(dict(model=model,mechanism=name,n=reps,true_debt_kwh=true,
                endpoint_coverage=float(covers.mean()),coverage_mc_low=ci[0],coverage_mc_high=ci[1],
                simultaneous_path_coverage=float(path_covers.mean()),endpoint_bias=float(np.mean(endpoint[m]-true)),
                endpoint_rmse=float(np.sqrt(np.mean((endpoint[m]-true)**2))),endpoint_width=end_width,
                naive_endpoint_sign_unpaid_rate=float(np.mean(endpoint[m]>0))))
            for ei,margin in enumerate(p['margins_kwh']):
                within=hi[m]<=margin;above=lo[m]>margin;unresolved=~(within|above)
                incorrect=(within&(true>margin+1e-12))|(above&(true<=margin+1e-12))
                decisions.append(dict(model=model,mechanism=name,margin_kwh=margin,
                    within_margin=float(within.mean()),above_margin=float(above.mean()),
                    unresolved=float(unresolved.mean()),incorrect_decisive=float(incorrect.mean())))
                possible=first_time(path[m]-path_width<=margin,times)
                supported=first_time(path[m]+path_width<=margin,times)
                check(f'{model}/{name}/{margin}: first grid endpoints independently selected',
                      same_with_nan(possible,fitted['first_possible'][s,ei,m])
                      and same_with_nan(supported,fitted['first_supported'][s,ei,m]))
                check(f'{model}/{name}/{margin}: states partition all observations',
                      np.all(within.astype(int)+above.astype(int)+unresolved.astype(int)==1))
    csv_metric_err=compare_csv(BASE/'metrics.csv',metrics,('model','mechanism'))
    csv_state_err=compare_csv(BASE/'decisions.csv',decisions,('model','mechanism','margin_kwh'))
    summary=json.loads((BASE/'evaluation.json').read_text(encoding='utf-8'))
    check('summary has fixed 20 and 80 rows',len(summary['metrics'])==20 and len(summary['decisions'])==80)
    check('evaluation retains declared-model limitation','known declared Gaussian' in summary['limitations'])
    scientific_source_check()
    results=dict(identity='independent_declared_simulation_verification_only',
        protocol_sha256=sha(BASE/'protocol.json'),verifier_sha256=sha(Path(__file__)),
        checks=CHECKS,passed=all(c['passed'] for c in CHECKS),check_count=len(CHECKS),
        failures=sum(not c['passed'] for c in CHECKS),
        maximum_integral_or_bound_error=worst_integral,maximum_width_error=worst_width,
        maximum_truth_error=truth_err,maximum_metric_csv_error=csv_metric_err,
        maximum_decision_csv_error=csv_state_err,
        limitations='Coverage is conditional on declared effective Gaussian covariance/bias, not estimated real noise; numerical epsilon is not a service threshold.')
    (BASE/'independent_verification.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    with (BASE/'verification_recomputed_metrics.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(metrics[0]));writer.writeheader();writer.writerows(metrics)
    print(json.dumps({k:v for k,v in results.items() if k not in ('checks','limitations')}))
    if not results['passed']:raise SystemExit(1)


def compare_csv(path,expected,keys):
    with path.open(encoding='utf-8-sig',newline='') as f:actual=list(csv.DictReader(f))
    check(path.name+' frozen row count',len(actual)==len(expected))
    worst=0.
    for i,(got,want) in enumerate(zip(actual,expected)):
        for k,v in want.items():
            if isinstance(v,str):check(f'{path.name}/{i}/{k}',got[k]==v)
            else:
                err=abs(float(got[k])-float(v));worst=max(worst,err)
                check(f'{path.name}/{i}/{k}',err<1e-11,err)
    return worst


def scientific_source_check():
    source=(BASE/'recovery.py').read_text(encoding='utf-8')
    tree=ast.parse(source)
    imports=[ast.unparse(n) for n in ast.walk(tree) if isinstance(n,(ast.Import,ast.ImportFrom))]
    check('estimator imports no simulator/evaluator',not any('observe' in x or 'evaluate' in x for x in imports))
    check('estimator opens no artifacts',not any(isinstance(n,ast.Call) and isinstance(n.func,ast.Name)
          and n.func.id in {'open','load'} for n in ast.walk(tree)))
    run=(BASE/'run.py').read_text(encoding='utf-8')
    rt=ast.parse(run)
    main_fn=next(n for n in rt.body if isinstance(n,ast.FunctionDef) and n.name=='main')
    main_text=ast.unparse(main_fn)
    check('truth existence gate before generating observations',
          "evaluator_truth.npz" in main_text and 'RuntimeError' in main_text
          and 'truth already revealed' in main_text)
    check('main intervals do not import/read truth before persistence',
          'physical_power' not in main_text and 'debt_path' in main_text
          and 'np.load' not in main_text and 'conditional_truth' not in main_text)


if __name__=='__main__':main()
