"""Independent tiny algebra audit; no fitting and no test facts/truth access."""
from pathlib import Path
import sys,json,hashlib
import numpy as np
from scipy.optimize import lsq_linear
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT/'B1算法'))
from b1_algorithm.process import _ride_revised as revised
from b1_algorithm.process.api import prepare,complete,resolve_policy
from b1_algorithm.resources.ev import EVAnalysisConfig

checks=[]
def check(name,condition):
    if not bool(condition):raise AssertionError(name)
    checks.append(name)

def direct_unit(t,times,W,structure):
    d,ru,hold,dn,wait,rb=times[:6]
    tx=min(d+ru+hold,W)
    peak=min(1.,(tx-d)/max(ru,1e-9))
    rise_end=min(d+ru,tx)
    v=np.zeros_like(t)
    if rise_end>d:
        use=(t>=d)&(t<rise_end)
        v[use]=peak*(t[use]-d)/(rise_end-d)
    use=(t>=rise_end)&(t<tx);v[use]=peak
    if dn>0:
        use=(t>=tx)&(t<tx+dn);v[use]=peak*(1-(t[use]-tx)/dn)
    if structure==2:
        gs,gl=times[6:8]
        gap0=min(rise_end+gs,tx);gap1=max(gap0,min(rise_end+gs+gl,tx))
        v[(t>=gap0)&(t<gap1)]-=peak
    neg=((t>=tx+dn+wait)&(t<tx+dn+wait+rb)).astype(float)
    return v,neg

def main():
    target=HERE/'core_review.json'
    if target.exists():raise RuntimeError('preserve previous review receipt')
    s=np.arange(-15.,45.);e=s+1.;fine=s[:,None]+(np.arange(2000)+.5)/2000
    cases=[([1.2,0.,15.35,0.,13.45,8.25],1),
           ([28.5,6.,5.,2.25,.45,5.75],1),
           ([1.1,2.3,20.2,1.4,9.2,5.3,6.6,3.3],2),
           ([5.,0.,0.,0.,0.,10.],1),
           ([30.,7.,2.,5.,1.,8.,0.,2.],2)]
    worst=0.
    for i,(times,structure) in enumerate(cases):
        a,b=revised.interval_components(np.asarray(times,float),30.,s,e,structure)
        da,db=direct_unit(fine,np.asarray(times,float),30.,structure)
        error=max(float(np.max(abs(a-da.mean(axis=1)))),float(np.max(abs(b-db.mean(axis=1)))))
        worst=max(worst,error)
        check('independent point definition versus interval averages '+str(i),error<.0006)
        check('components nonnegative bounded '+str(i),min(a.min(),b.min())>=-1e-12 and max(a.max(),b.max())<=1+1e-12)
    rng=np.random.default_rng(8123000)
    worst_ls=0.
    for i in range(30):
        pos=rng.uniform(size=60);neg=rng.uniform(size=60);y=rng.normal(size=60)
        if i==28:pos=np.zeros(60)
        if i==29:neg=pos.copy()
        q=.1 if i%2 else 22.;amax=.05 if i%3 else 20.;bmax=.02 if i%3 else 20.
        a,b=revised.bounded_amplitudes(pos,neg,y,q,amax,bmax)
        A=np.c_[q*pos,-q*neg]
        answer=lsq_linear(A,y,bounds=([0,0],[amax,bmax]),tol=1e-12,max_iter=1000)
        excess=float(np.sum((A@np.array([a,b])-y)**2)-np.sum((A@answer.x-y)**2))
        worst_ls=max(worst_ls,excess)
        check('box amplitude LS including zero and collinear columns '+str(i),excess<1e-7 and 0<=a<=amax and 0<=b<=bmax)
    task=dict(task_id='independent-algebra',user_id='u',meter_id='m',start_min=0.,end_min=30.,notice_min=-15.,request_kw=1.5)
    data=prepare(s,e,np.full(60,3.5),np.full(60,3.5),task,.05,dict(max_charge_kw=7.2,template_rebound_max_ratio=.02))
    actual,source=revised.rebound_bound(data)
    check('document explicit ratio override example',abs(actual-(7.2-3.5)/1.5)<1e-12 and actual>.02)
    check('default policy unchanged',resolve_policy(60,delta_min=1.)=='ride_template')
    no_max=dict(data,profile=EVAnalysisConfig(template_rebound_max_ratio=.02))
    check('configured ratio retained without max',revised.rebound_bound(no_max)==(.02,'configured_ratio_no_declared_max'))
    two_grid=np.arange(-15.,45.,.25)
    # Public unsupported resolution route uses only prepare on supported10s.
    s10=np.arange(360)/6.-15.;e10=s10+1/6
    unsupported=prepare(s10,e10,np.full(360,3.5),np.full(360,3.5),task,.05)
    fallback=complete(unsupported,{},policy='ride_revised')
    check('10s repaired method explicitly raw degraded fallback',fallback['status']=='degraded' and fallback['method']=='raw_F0' and fallback['selection_evidence']['failure_reason']=='revised_RIDE_currently_validated_for_one_minute_only')
    files=['B1算法/b1_algorithm/process/_ride_revised.py','B1算法/b1_algorithm/process/api.py','work/b1_template_repair_20261030/protocol.json','work/b1_template_repair_20261030/run.py','work/b1_template_repair_20261030/assess.py']
    source_sha={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in files}
    result=dict(passed=True,checks=checks,n_checks=len(checks),worst_dense_interval_error=worst,worst_boxLS_objective_excess=worst_ls,
      no_performance_fitting_run=True,no_test_fact_or_truth_read=True,source_sha256=source_sha,
      core_judgment='No mathematical or information-leakage blocker for the frozen finite comparison. Local termination success is not global optimality, and null detection remains uncalibrated.',
      findings=[dict(priority='important_public_interface_limitation',file='B1算法/b1_algorithm/process/_ride_revised.py',function='rebound_bound',
        detail='Supplying max_charge_kw replaces even an explicitly supplied template_rebound_max_ratio. Independent example requested0.02, selected'+str(actual)+'. The frozen protocol describes headroom override, so retain this candidate hypothesis; do not claim general preservation of user-declared template bounds.'),
        dict(priority='minor_diagnostic_limitation',file='B1算法/b1_algorithm/process/api.py',function='complete',detail='When every revised solve fails, raw degraded fallback retains failure_reason but drops solver_records from the fitted failure dictionary. This does not select unsuccessful curves but loses public diagnostics.')],
      source_change_requested_during_frozen_test=False)
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('passed','n_checks','worst_dense_interval_error','worst_boxLS_objective_excess','no_test_fact_or_truth_read')},indent=2))
if __name__=='__main__':main()
