"""Functional/mathematical controls; no test-panel truth or tuning."""
from pathlib import Path
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
import sys,json
import numpy as np
from scipy.optimize import lsq_linear
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];sys.path.insert(0,str(ROOT/'B1算法'))
from b1_algorithm.process import _ride_revised as revised
from b1_algorithm.process.api import prepare,complete,resolve_policy
from b1_algorithm.process import _ride_template as original
from b1_api import provided_reference,analyze_event
checks=[]
def check(name,condition):
    assert condition,name
    checks.append(name)
def main(receipt_name='functional_receipt.json'):
    if Path(receipt_name).name!=receipt_name:raise ValueError('local receipt filename required')
    target=HERE/receipt_name
    if target.exists():raise RuntimeError('do not overwrite completed controls')
    s=np.arange(-15.,45.);e=s+1.;W=30.;q=1.5
    rng=np.random.default_rng(7129990)
    for i in range(12):
        positive=rng.uniform(0,1,60);negative=rng.uniform(0,1,60);y=rng.normal(0,2,60)
        a,b=revised.bounded_amplitudes(positive,negative,y,q,1.5,2.)
        A=np.column_stack([q*positive,-q*negative]);expected=lsq_linear(A,y,bounds=([0,0],[1.5,2.]),tol=1e-12)
        check('profiled amplitude matches independent boxLS '+str(i),abs(np.sum((A@np.array([a,b])-y)**2)-np.sum((A@expected.x-y)**2))<1e-7)
    # Direct pointwise definition, independent of the cumulative-integral
    # implementation. All control breakpoints are aligned to the fine grid.
    times=np.array([1.,2.,14.,1.,16.,7.,6.,3.]);fine=s[:,None]+(np.arange(1000)+.5)/1000
    d,ru,hold,dn,wait,rb,gs,gl=times;tx=min(d+ru+hold,W)
    direct=np.where(fine<d,0,np.where(fine<d+ru,(fine-d)/ru,np.where(fine<tx,1,np.where(fine<tx+dn,1-(fine-tx)/dn,0))))
    direct-=((fine>=d+ru+gs)&(fine<min(d+ru+gs+gl,tx))).astype(float)
    pos,neg=revised.interval_components(times,W,s,e,2)
    check('positive interval mean matches independent dense piecewise definition',np.max(abs(pos-direct.mean(axis=1)))<1e-10)
    negative=((fine>=tx+dn+wait)&(fine<tx+dn+wait+rb)).mean(axis=1)
    check('delayed recharge interval mean matches independent rectangle',np.max(abs(neg-negative))<1e-10)
    cases={
        'ordinary_M1':(np.array([1,1,15,1,0,10]),1,.8,.6),
        'release_at_end':(np.array([1,2,27,1,0,10]),1,.8,.6),
        'end_wait':(np.array([1,0,16,0,13,10]),1,.8,.6),
        'internal_gap_and_wait':(np.array([1,1,20,0,8,10,8,3]),2,.8,.6),
        'wait_after_task':(np.array([1,0,16,0,17,8]),1,.8,1.2),
        'none':(np.array([1,0,16,0,13,10]),1,0.,0.),
    }
    rows=[]
    for name,(value,structure,a,b) in cases.items():
        pos,neg=revised.interval_components(value,W,s,e,structure);truth=q*(a*pos-b*neg)
        task=dict(task_id=name,user_id='control-user',meter_id='control-meter',start_min=0.,end_min=30.,notice_min=-15.,request_kw=q)
        data=prepare(s,e,3.5-truth,np.full(60,3.5),task,.05,dict(max_charge_kw=7.2,revised_rebound_bound_policy='declared_headroom'))
        fit=revised.fit_revised_ride(data);check(name+' returns checked local result',fit['status']=='ok' and fit['local_solver_success'])
        pred=fit['prediction'];mask=(s>=0)&(s<30)
        duration_error=float(abs(np.sum(mask&(pred>=.15))-np.sum(mask&(truth>=.15)))*60)
        rmse=float(np.sqrt(np.mean((pred[mask]-truth[mask])**2)))
        rows.append(dict(control=name,task_rmse=rmse,duration_error=duration_error,structure=fit['structure'],solver_starts=len(fit['solver_records'])))
        check(name+' exact task duration',duration_error==0)
        check(name+' small task curve error',rmse<.01)
        check(name+' no global certificate',fit['global_optimum_certified'] is False)
    # Explicitly simulate optimizer exhaustion. A finite but unsuccessful
    # result must not enter the selected family.
    from types import SimpleNamespace
    saved=revised.least_squares
    revised.least_squares=lambda fun,x0,**kw:SimpleNamespace(x=x0,success=False,status=0,nfev=250,optimality=1.)
    failed=revised.fit_revised_ride(data)
    revised.least_squares=saved
    check('exhausted solves do not become successful fits',failed['status']=='unavailable')
    check('old one-minute default unchanged',resolve_policy(60,delta_min=1.)=='ride_template')
    # Public API parity and energy integration use a hand-constructed interval
    # response, independent of model outputs.
    task=dict(task_id='public',user_id='u',meter_id='m',start_min=100.,end_min=130.,notice_min=85.,request_kw=1.5,task_pre_treatment=True)
    reference=provided_reference(task,s+100,e+100,np.full(60,3.5),available_at_min=85.)
    power=np.full(60,3.5);power[(s>=1)&(s<17)]-=1.2;power[(s>=30)&(s<40)]+=1.8
    old=analyze_event(task,s+100,e+100,power,reference,.05,process_method='ride_template',ev_config=dict(max_charge_kw=7.2))
    new=analyze_event(task,s+100,e+100,power,reference,.05,process_method='ride_revised',ev_config=dict(max_charge_kw=7.2))
    check('public repaired method usable',new['status']=='ok' and new['process']['method']=='RIDE_revised_template_average')
    check('raw eta unchanged and correct',new['outcome']==old['outcome'] and abs(new['outcome']['value']-16*1.2/45)<1e-12)
    check('selected diagnostics distinguish repair',new['process']['selection_evidence']['version']==revised.VERSION)
    receipt=dict(passed=True,n_checks=len(checks),checks=checks,controls=rows,performance_claim=False)
    with target.open('x',encoding='utf-8') as stream:json.dump(receipt,stream,ensure_ascii=False,indent=2)
    print(json.dumps(receipt,indent=2))
if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--receipt',default='functional_receipt.json')
    main(parser.parse_args().receipt)
