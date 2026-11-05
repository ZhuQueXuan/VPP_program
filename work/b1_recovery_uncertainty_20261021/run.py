"""micro -> observations -> intervals; evaluator truth is absent until separate evaluation."""
from pathlib import Path
import json,hashlib,sys,time
import numpy as np
from recovery import assess,profile,classify
BASE=Path(__file__).resolve().parent
PROJECT=BASE.parent.parent
P=json.loads((BASE/'protocol.json').read_text(encoding='utf-8'))
RAW=PROJECT/P['raw_root']

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def micro():
    checks=[]
    def check(name,cond):
        checks.append(dict(name=name,passed=bool(cond)))
        assert cond,name
    t=np.array([0.,600.,1800.,2520.,3600.]);r=np.full(4,3.);p=np.array([3.,1.5,5.5,3.])
    a=assess(t,r,p,3600,sigma_kw=0.)
    check('irregular widths exact debt zero',abs(float(a['observed_end_debt_kwh']))<1e-12)
    check('zero noise epsilon0 within at exact known zero',str(a['decisions']['0.0'])=='within_margin')
    pbad=p.copy();pbad[1]=np.nan
    b=assess(t,r,pbad,3600,sigma_kw=.05)
    check('request missing makes endpoint unavailable',str(b['decisions']['0.0'])=='unavailable')
    c=assess(t[:-1],r[:-1],p[:-1],3600,sigma_kw=.05)
    check('truncated deadline keeps censor',not c['deadline_available'] and str(c['decisions']['0.0'])=='right_censored')
    d=assess(t,r,p,3600)
    check('unknown covariance no interval',d['uncertainty_status']=='unavailable' and d['decisions'] is None)
    weights=np.diff(t)/3600;weights[0]=0
    for rho in (0.,.8,-.3):
        pr=profile(t,.05,rho)
        cov=.05**2*rho**np.abs(np.subtract.outer(np.arange(4),np.arange(4)))
        direct=weights@cov@weights
        check('independent covariance form rho='+str(rho),abs(pr['sd_kwh'][-1]**2-direct)<1e-15)
    shifted=assess(t,r+.02,p,3600,sigma_kw=0,bias_bound_kw=.02)
    check('reference bias bound contains zero',float(shifted['observed_end_lower_kwh'])<=1e-12 and float(shifted['observed_end_upper_kwh'])>=-1e-12)
    for lo,hi,e,expected in [(-.01,.01,0,'unresolved'),(.02,.03,.01,'above_margin'),(-.04,-.02,0,'within_margin')]:
        check('state '+expected,str(classify(lo,hi,e))==expected)
    out=dict(checks=checks,passed=True,protocol_sha256=sha(BASE/'protocol.json'))
    (BASE/'micro_checks.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
    print(json.dumps(out))

def main():
    assert json.loads((BASE/'micro_checks.json').read_text())['passed']
    if (BASE/'evaluator_truth.npz').exists():raise RuntimeError('truth already revealed; freeze a new study')
    from observe import generate
    start=time.time()
    frozen={p:sha(BASE/p) for p in ('protocol.json','recovery.py','observe.py','run.py','evaluate.py')}
    (BASE/'source_freeze.json').write_text(json.dumps(frozen,indent=2),encoding='utf-8')
    raw=generate(P);RAW.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(RAW/'observations.npz',**raw)
    estimates=[];low=[];high=[];widths=[];debt_end=[];endpoint_width=[]
    first_supported=[];first_possible=[]
    for s,name in enumerate(P['observation_models']):
        declared_rho=.8 if name=='ar1_correct' else 0.
        bias=.02 if name=='reference_bias_bounded' else 0.
        p=raw['power_obs_kw'][s]
        ref=np.broadcast_to(raw['reference_kw'][s],p.shape)
        a=assess(raw['time_edges_s'],ref,p,3600,sigma_kw=.05,rho=declared_rho,bias_bound_kw=bias)
        estimates.append(a['post_debt_kwh']);widths.append(a['post_width_kwh'])
        low.append(a['observed_end_lower_kwh']);high.append(a['observed_end_upper_kwh'])
        debt_end.append(a['observed_end_debt_kwh']);endpoint_width.append(a['endpoint_width_kwh'])
        first_supported.append([a['grid_bounds'][str(e)]['first_supported_s'] for e in P['margins_kwh']])
        first_possible.append([a['grid_bounds'][str(e)]['first_possible_s'] for e in P['margins_kwh']])
    np.savez_compressed(BASE/'intervals.npz',debt_path=np.array(estimates),path_width=np.array(widths),
        endpoint_debt=np.array(debt_end),endpoint_lower=np.array(low),endpoint_upper=np.array(high),
        endpoint_width=np.array(endpoint_width),post_times_s=a['post_times_s'],
        first_supported=np.array(first_supported),first_possible=np.array(first_possible))
    receipt=dict(protocol_sha256=sha(BASE/'protocol.json'),raw_sha256=sha(RAW/'observations.npz'),
        intervals_sha256=sha(BASE/'intervals.npz'),truth_existed_before_estimation=False,seconds=time.time()-start,
        factual_observation_variants=20000,base_mechanism_noise_draws=4000)
    (BASE/'run_receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print(json.dumps(receipt))

if __name__=='__main__':{'micro':micro,'main':main}[sys.argv[1]]()
