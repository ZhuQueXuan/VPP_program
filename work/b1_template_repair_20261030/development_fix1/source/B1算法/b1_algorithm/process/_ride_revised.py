"""Finite RIDE repair candidate: observed starts, delayed recharge, checked fits.

The old solver and template remain unchanged comparators. This variant adds
one waiting time after positive release, preserves exact interval averages,
and profiles the two bounded linear amplitudes. No CPOP or evaluation truth
is used. A successful local solve is not a global-optimum certificate.
"""
import numpy as np
from scipy.optimize import least_squares
from . import _ride_template as tpl

VERSION='ride-repair-v1'
MAX_NFEV=250


def interval_components(times,W,starts,ends,structure):
    """Unit positive template and unit negative recharge with a free wait."""
    d,ru,hold,dn,wait,rb=times[:6]
    gap=times[6:8] if structure==2 else (0.,0.)
    theta=np.array([d,ru,1.,hold,dn,0.,0.,*gap])
    positive=tpl.interval_average(theta,W,starts,ends)
    end=min(d+ru+hold,W)+dn+wait
    width=ends-starts
    negative=(np.clip(ends-end,0,rb)-np.clip(starts-end,0,rb))/width
    return positive,negative


def bounded_amplitudes(positive,negative,y,q,a_max,b_max):
    """Exact two-variable box LS, including active-bound alternatives."""
    A=q*positive;B=-q*negative
    aa=float(A@A);bb=float(B@B);ab=float(A@B);ay=float(A@y);by=float(B@y)
    candidates=[];det=aa*bb-ab*ab
    if det>1e-12*max(aa*bb,1.):
        a=(ay*bb-by*ab)/det;b=(by*aa-ay*ab)/det
        if 0<=a<=a_max and 0<=b<=b_max:candidates.append((a,b))
    for a in (0.,a_max):candidates.append((a,float(np.clip((by-ab*a)/bb if bb>1e-15 else 0.,0,b_max))))
    for b in (0.,b_max):candidates.append((float(np.clip((ay-ab*b)/aa if aa>1e-15 else 0.,0,a_max)),b))
    return min(candidates,key=lambda x:float(np.sum((A*x[0]+B*x[1]-y)**2)))


def _runs(mask):
    idx=np.flatnonzero(mask)
    if not len(idx):return []
    return np.split(idx,np.flatnonzero(np.diff(idx)>1)+1)


def observed_starts(data,structure):
    """Deterministic initial times derived only from this supplied signal."""
    s,e,y,W,q=data['starts'],data['ends'],data['y'],data['W'],data['q']
    use=(s>=0)&(e<=W+1e-9);x=s[use];r=y[use];sigma=data['sigma']
    peak=max(float(np.quantile(r,.85)),.05*q)
    high=r[r>=.6*peak];level=max(float(np.median(high)) if len(high) else peak,.05*q)
    pos=r>=max(.15*level,2*sigma)
    if pos.any():
        first,last=np.flatnonzero(pos)[[0,-1]]
        begin=float(np.clip(x[first]+1-r[first]/level,0,W))
        finish=float(np.clip(x[last]+r[last]/level,begin,W))
    else:begin,finish=0.,W
    p90=np.flatnonzero(r>=.9*level);p10=np.flatnonzero(r>=.1*level)
    ramp=float(np.clip((x[p90[0]]-x[p10[0]])*1.25,0,min(data['profile'].template_ramp_max_min,W))) if len(p90) and len(p10) else 0.
    ramp=min(ramp,max(0,finish-begin))
    # Recharge can begin immediately after an early task response, before W.
    # Restrict to after the last positive response, rather than assuming the
    # recharge label must lie outside the requested task window.
    neg=(s>=finish-1e-9)&(y<=-max(2*sigma,.1*q))
    if neg.any():
        indices=np.flatnonzero(neg);nlevel=max(float(np.median(-y[indices])),sigma)
        reb_begin=float(s[indices[0]]+np.clip(1+y[indices[0]]/nlevel,0,1))
        reb_end=float(s[indices[-1]]+np.clip(-y[indices[-1]]/nlevel,0,1))
    else:reb_begin,reb_end=W,W
    wait=max(0,reb_begin-finish);duration=max(0,reb_end-reb_begin)
    base=np.array([begin,ramp,max(0,finish-begin-ramp),0.,wait,duration])
    starts=[(base,False)]
    step=base.copy();step[1]=0.;step[2]=max(0,finish-begin);starts.append((step,True))
    release=base.copy();release[3]=min(1.,max(0,finish-begin-ramp));release[2]=max(0,release[2]-release[3]);starts.append((release,False))
    # A task-ending response and a smooth rise are useful alternatives. The
    # budget is fixed; no random search or truth-based retry occurs.
    ending=base.copy();ending[2]=max(0,W-begin-ramp);ending[4]=max(0,reb_begin-W);starts.append((ending,False))
    slow=base.copy();slow[1]=min(max(1.,ramp),max(0,finish-begin));slow[2]=max(0,finish-begin-slow[1]);starts.append((slow,False))
    if structure==2:
        internal=(x>begin+ramp)&(x<finish-1e-8)&(r<.45*level)
        runs=_runs(internal);gap=max(runs,key=len) if runs else None
        gs=max(0,float(x[gap[0]])-(begin+ramp)) if gap is not None else .35*max(0,finish-begin-ramp)
        gl=float(len(gap)) if gap is not None else min(1.,.15*W)
        starts=[(np.r_[v,[gs,gl]],instant) for v,instant in starts]
        # Retain a zero-gap start so a wrong low excursion cannot force M2.
        starts.append((np.r_[base,[0.,0.]],False))
    unique=[]
    for value,instant in starts:
        if not any(instant==flag and np.allclose(value,other,rtol=0,atol=1e-10) for other,flag in unique):unique.append((value,instant))
    return unique


def rebound_bound(data):
    profile=data['profile'];configured=profile.template_rebound_max_ratio
    if profile.max_charge_kw is None:return configured,'configured_ratio_no_declared_max'
    # Conservative headroom across the supplied reference window. The raw
    # meter is never clipped. This changes a fitted-model bound, not evidence.
    headroom=max(0.,profile.max_charge_kw-float(np.max(data['reference'])))
    return max(headroom/data['q'],1e-6),'declared_max_minus_max_supplied_reference'


def fit_revised_ride(data):
    if not np.isclose(data['delta'],1.,rtol=0,atol=1e-9):
        return dict(status='unavailable',reason='revised_RIDE_currently_validated_for_one_minute_only')
    s,e,y,W,q=data['starts'],data['ends'],data['y'],data['W'],data['q'];profile=data['profile']
    sigma=max(data['sigma'],1e-3);b_max,b_source=rebound_bound(data)
    n=len(y);records=[];fits=[]
    for structure in (1,2):
        bound=np.array([W,min(profile.template_ramp_max_min,max(W,1.)),W,profile.template_release_max_min,
                        max(float(e[-1]),1.),profile.template_rebound_max_min]+([W,W] if structure==2 else []))
        for start_index,(initial,instant) in enumerate(observed_starts(data,structure)):
            active=np.arange(len(bound))
            if instant:active=active[~np.isin(active,[1,3])]
            initial=np.clip(initial,0,bound)
            def expand(z):
                full=initial.copy();full[active]=z
                if instant:full[[1,3]]=0.
                return full
            def evaluate(z):
                times=expand(z);pos,neg=interval_components(times,W,s,e,structure)
                a,b=bounded_amplitudes(pos,neg,y,q,profile.template_level_max_ratio,b_max)
                return q*(a*pos-b*neg),a,b,times
            def fun(z):return (evaluate(z)[0]-y)/sigma
            try:
                result=least_squares(fun,initial[active],bounds=(np.zeros(len(active)),bound[active]),
                    jac='2-point',method='trf',max_nfev=MAX_NFEV,x_scale=np.maximum(bound[active]/10,.1),
                    ftol=1e-7,xtol=1e-7,gtol=1e-7)
                curve,a,b,times=evaluate(result.x);rss=float(np.sum((curve-y)**2))
                accepted=bool(result.success and np.isfinite(curve).all() and np.isfinite(rss))
                record=dict(structure=structure,start_index=start_index,instant_edges=instant,success=bool(result.success),
                    termination_status=int(result.status),nfev=int(result.nfev),optimality=float(result.optimality),rss=rss,accepted=accepted)
                records.append(record)
                if accepted:
                    # Count the whole declared family, including zero-edge
                    # branch parameters, rather than discounting its search.
                    k=8 if structure==1 else 10
                    fits.append(dict(curve=curve,rss=rss,bic=rss/sigma**2+k*np.log(n),a=a,b=b,times=times,
                        structure=structure,solver_record=len(records)-1))
            except (ValueError,RuntimeError,FloatingPointError,np.linalg.LinAlgError) as exc:
                records.append(dict(structure=structure,start_index=start_index,instant_edges=instant,accepted=False,
                    success=False,error=type(exc).__name__+': '+str(exc)))
    if not fits:return dict(status='unavailable',reason='no_successful_revised_template_solve',solver_records=records)
    best=min(fits,key=lambda r:(r['bic'],r['structure']));null=float(y@y)/sigma**2
    # Preserve the prior amplitude/BIC detection semantics; no new false alarm
    # calibration or baseline-shift correction is claimed by this repair.
    detected=best['bic']<null and best['a']>=.1
    chosen=best['curve'] if detected else np.zeros(n)
    return dict(status='ok',prediction=chosen,structure=best['structure'] if detected else 0,detected=bool(detected),
        version=VERSION,selection='checked_local_fits_BIC_with_profiled_amplitudes',
        solver_records=records,selected_solver=best['solver_record'],local_solver_success=True,global_optimum_certified=False,
        parameters=dict(times=best['times'].tolist(),positive_ratio=best['a'],rebound_ratio=best['b']),
        rebound_max_ratio=float(b_max),rebound_bound_source=b_source,independent_post_release_wait=True,
        reference_bias_corrected=False,detection_error_calibrated=False)
