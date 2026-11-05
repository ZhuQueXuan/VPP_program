"""Observed-only retrospective extraction. No generator/evaluator imports."""
from pathlib import Path
import importlib.util
import math
import numpy as np
from scipy.stats import norm

OLD=Path(__file__).resolve().parents[1]/'b1_research_20261021/features.py'
spec=importlib.util.spec_from_file_location('frozen_b1_f0',OLD)
f0=importlib.util.module_from_spec(spec);spec.loader.exec_module(f0)

def segment(y,penalty,min_size):
    """Exact unpruned O(n^2) DP; vectorize candidate starts, same SSE objective."""
    y=np.asarray(y,float);n=len(y)
    if y.ndim!=1 or not np.isfinite(y).all() or n<min_size or min_size<1 or penalty<0 or not np.isfinite(penalty):raise ValueError('invalid segmentation input')
    prefix=np.r_[0.,np.cumsum(y)];square=np.r_[0.,np.cumsum(y*y)]
    cost=np.full(n+1,np.inf);last=np.full(n+1,-1,int);cost[0]=-penalty
    for end in range(min_size,n+1):
        starts=np.arange(end-min_size+1)
        sse=np.maximum(0,square[end]-square[starts]-(prefix[end]-prefix[starts])**2/(end-starts))
        candidates=cost[starts]+sse+penalty;j=int(np.argmin(candidates))
        cost[end]=candidates[j];last[end]=starts[j]
    segments=[];end=n
    while end:
        start=int(last[end]);segments.append((start,end,float((prefix[end]-prefix[start])/(end-start))));end=start
    segments.reverse();fit=np.empty(n)
    for a,b,m in segments:fit[a:b]=m
    return fit,segments,float(cost[n])

def smooth(t,reduction,sigma,dwell):
    t=np.asarray(t);y=np.asarray(reduction,float);fit=y.copy();cuts=[];blocks=0
    phases=np.where(t[:-1]<600,0,np.where(t[:-1]<1800,1,2))
    for phase in (0,1,2):
        i=0
        while i<len(y):
            if phases[i]!=phase or not np.isfinite(y[i]):i+=1;continue
            end=i+1
            while end<len(y) and phases[end]==phase and np.isfinite(y[end]):end+=1
            if end-i>=dwell:
                val,segs,obj=segment(y[i:end],3*sigma*sigma*math.log(end-i),dwell)
                fit[i:end]=val;blocks+=1
                cuts.extend(int(t[i+b]) for a,b,m in segs[:-1])
            i=end
    return fit,cuts,blocks

def longest_run(t,y,dwell):
    run=0;best=0
    for i,v in enumerate(y):
        if 600<=t[i]<1800 and np.isfinite(v) and v>=.15:run+=1;best=max(best,run)
        else:run=0
    return float(best*(t[1]-t[0])) if best>=dwell else 0.

def raw_balance(t,reduction,sigma):
    t=np.asarray(t,float);y=np.asarray(reduction,float);use=t[:-1]>=600
    if not np.isfinite(y[use]).all():return dict(status='unavailable',debt_kwh=None,lower_kwh=None,upper_kwh=None)
    widths=np.diff(t)[use];debt=float(np.sum(y[use]*widths)/3600)
    half=float(norm.ppf(.975)*sigma*np.sqrt(np.sum(widths**2))/3600)
    lo,hi=debt-half,debt+half
    status='right_censored' if t[-1]<3600 else ('within_margin' if hi<=.01 else 'above_margin' if lo>.01 else 'unresolved')
    return dict(status=status,debt_kwh=debt,lower_kwh=lo,upper_kwh=hi)

def extract(t,reference,power,sigma,method):
    t=np.asarray(t,float);ref=np.asarray(reference,float);power=np.asarray(power,float)
    if len(t)!=len(power)+1 or ref.shape!=power.shape or len(power)==0 or not np.all(np.diff(t)>0):raise ValueError('bad curve shape or time')
    dt=float(t[1]-t[0])
    if not np.allclose(np.diff(t),dt) or sigma<0 or not np.isfinite(sigma):raise ValueError('require regular grid and declared finite sigma')
    dwell=max(1,math.ceil(30/dt));raw=ref-power
    if method=='F0_raw_rule':fit=raw.copy();cuts=[];blocks=0
    elif method=='F1_segment_rule':fit,cuts,blocks=smooth(t,raw,sigma,dwell)
    else:raise ValueError('unknown method')
    old=f0.extract(t,ref,ref-fit,dwell_samples=dwell)
    rawold=f0.extract(t,ref,power,dwell_samples=dwell) if method!='F0_raw_rule' else old
    request=(t[:-1]>=600)&(t[:-1]<1800);full=bool(np.all(np.isfinite(raw[request])) and t[-1]>=1800)
    onset=old['onset_interval_s'];target=old['target_interval_s']
    result=dict(method=method,stage=old['stage'] if full else 'unavailable',
        onset_s=float(onset[1]) if full and onset is not None else None,
        onset_confirmation_s=old['onset_confirmation_s'] if full else None,
        target_s=float(target[1]) if full and target is not None else None,
        duration_s=longest_run(t,fit,dwell) if full else None,
        request_coverage=rawold['request_coverage'],request_net_kwh=rawold['request_net_kwh'],Y=rawold['Y'],
        power_recovery_status=old['power_recovery_status'] if full else 'unavailable',
        power_recovery_s=old['power_recovery_time_s'] if full else None,
        balance=raw_balance(t,raw,sigma),internal_cut_count=len(cuts),internal_cuts_s=cuts,finite_fit_blocks=blocks,
        criterion='retrospective threshold+dwell on interval-average curve, not physical action/willingness')
    if not np.isfinite(raw[t[:-1]>=1800]).all():
        result['power_recovery_status']='unavailable';result['power_recovery_s']=None
    return result,fit
