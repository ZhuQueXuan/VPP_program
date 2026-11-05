"""Relative-reference debt uncertainty; no truth/simulator imports."""
import numpy as np
from scipy.stats import norm


def profile(edges_s, sigma_kw, rho=0., bias_bound_kw=0., start_s=600., release_s=1800., alpha=.05):
    t=np.asarray(edges_s,float)
    if t.ndim!=1 or len(t)<2 or not np.isfinite(t).all() or np.any(np.diff(t)<=0):
        raise ValueError('finite increasing time boundaries required')
    if sigma_kw is None:
        return None
    if not(np.isfinite(sigma_kw) and sigma_kw>=0 and np.isfinite(rho) and abs(rho)<1
           and np.isfinite(bias_bound_kw) and bias_bound_kw>=0 and 0<alpha<1):
        raise ValueError('invalid declared uncertainty parameters')
    w=np.maximum(0.,t[1:]-np.maximum(t[:-1],start_s))/3600
    # AR correlation is by observation-interval index, also for irregular intervals.
    variance=np.zeros(len(w));v=0.;cross=0.
    for i,wi in enumerate(w):
        v+=wi*wi+2*wi*cross
        variance[i]=max(0.,v)*sigma_kw**2
        cross=rho*(cross+wi)
    sd=np.sqrt(variance)
    bias=bias_bound_kw*np.cumsum(abs(w))
    post=t[1:]>release_s
    k=int(post.sum())
    path_z=norm.ppf(1-alpha/(2*k)) if k else np.nan
    return dict(weights_h=w,sd_kwh=sd,bias_kwh=bias,post=post,
                fixed_width_kwh=norm.ppf(1-alpha/2)*sd+bias,
                simultaneous_width_kwh=path_z*sd+bias,
                K=k,path_z=float(path_z))


def classify(lower,upper,margin):
    if not np.isfinite(margin) or margin<0:
        raise ValueError('margin must be declared nonnegative')
    lo,hi=np.asarray(lower),np.asarray(upper)
    return np.where(~np.isfinite(lo)|~np.isfinite(hi),'unavailable',
                    np.where(hi<=margin,'within_margin',np.where(lo>margin,'above_margin','unresolved')))


def assess(edges_s,reference_kw,power_obs_kw,deadline_s,*,sigma_kw=None,rho=0.,bias_bound_kw=0.,
           start_s=600.,release_s=1800.,alpha=.05,margins=(0.,.005,.01,.02)):
    t=np.asarray(edges_s,float)
    ref,p=np.asarray(reference_kw,float),np.asarray(power_obs_kw,float)
    # Always validate times even when uncertainty parameters are unavailable.
    if t.ndim!=1 or len(t)<2 or not np.isfinite(t).all() or np.any(np.diff(t)<=0):
        raise ValueError('finite increasing boundaries required')
    if ref.shape!=p.shape or p.shape[-1]!=len(t)-1:
        raise ValueError('n interval powers and n+1 boundaries required')
    if not(np.isfinite(deadline_s) and start_s<release_s<deadline_s):
        raise ValueError('declare start < release < deadline')
    if t[-1]>deadline_s+1e-10:
        raise ValueError('truncate to declared endpoint explicitly before assessment')
    w=np.maximum(0.,t[1:]-np.maximum(t[:-1],start_s))/3600
    finite=np.isfinite(ref)&np.isfinite(p)
    bad=(~finite)&(w>0)
    accum_missing=np.cumsum(bad,axis=-1)>0
    increment=np.where(finite,(ref-p)*w,0.)
    debt=np.cumsum(increment,axis=-1)
    debt=np.where(accum_missing,np.nan,debt)
    if t[0]>start_s:
        debt[...]=np.nan
    pr=profile(t,sigma_kw,rho,bias_bound_kw,start_s,release_s,alpha)
    endpoint_available=abs(t[-1]-deadline_s)<=1e-8
    result=dict(observed_end_s=float(t[-1]),deadline_available=endpoint_available,
                deadline_status='observed' if endpoint_available else 'right_censored',
                observed_end_debt_kwh=debt[...,-1],debt_path_kwh=debt,
                uncertainty_status='available' if pr is not None else 'unavailable',
                conditions='conditional on declared effective Gaussian covariance and bounded bias; no service guarantee')
    if pr is None:
        result.update(observed_end_lower_kwh=None,observed_end_upper_kwh=None,decisions=None)
        return result
    fixed_lo=debt-pr['fixed_width_kwh'];fixed_hi=debt+pr['fixed_width_kwh']
    post=pr['post'];path=debt[...,post];width=pr['simultaneous_width_kwh'][post]
    result.update(observed_end_lower_kwh=fixed_lo[...,-1],observed_end_upper_kwh=fixed_hi[...,-1],
        post_times_s=t[1:][post],post_debt_kwh=path,post_width_kwh=width,
        endpoint_width_kwh=float(pr['fixed_width_kwh'][-1]),sd_path_kwh=pr['sd_kwh'],K=pr['K'])
    result['decisions']={str(e):classify(fixed_lo[...,-1],fixed_hi[...,-1],e)
                         if endpoint_available else np.full(debt.shape[:-1],'right_censored') for e in margins}
    result['grid_bounds']={}
    for e in margins:
        possible=path-width<=e;supported=path+width<=e
        times=t[1:][post]
        def first(mask):
            if not len(times):return np.full(debt.shape[:-1],np.nan)
            return np.where(mask.any(axis=-1),times[np.argmax(mask,axis=-1)],np.nan)
        result['grid_bounds'][str(e)]={'first_possible_s':first(possible),'first_supported_s':first(supported)}
    return result
