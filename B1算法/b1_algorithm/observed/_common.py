"""Current observed-curve numerical helpers, without experiment I/O."""
import numpy as np

def arrays(r):
    d=r['model_input'];t=np.array(d['relative_seconds'],float);p=np.array(d['power_kw'],float);i=np.array(d['current_a'],float);pilot=np.array(d['pilot_a'],float)
    if not all(np.isfinite(v).all() for v in [t,p,i,pilot]) or len(t)<3 or np.any(np.diff(t)<=0):return None
    zeros=np.flatnonzero(t==0)
    if len(zeros)!=1 or zeros[0]<1:return None
    return dict(t=t,p=p,i=i,pilot=pilot,j0=int(zeros[0]))

def scale(t,y,floor):
    use=(t>=-60)&(t<=-12);dt=np.diff(t);z=np.diff(y);mask=use[:-1]&use[1:]&(dt>0)&(dt<=15)
    vals=z[mask]
    return float(max(floor,1.4826*np.median(abs(vals-np.median(vals)))/np.sqrt(2))) if len(vals) else float(floor)

def context(a):
    t=a['t'];j=a['j0'];pilot=a['pilot'];old=pilot[j-1];direction=float(np.sign(pilot[j]-old))
    start=j-1
    while start>0 and t[start-1]>=-24 and abs(pilot[start-1]-old)<.25:start-=1
    return dict(direction=direction,pre=np.arange(start,j),sigma_p=scale(t,a['p'],.005),sigma_i=scale(t,a['i'],.05),search=np.flatnonzero((np.arange(len(t))>=j-1)&(t<=24)),prior_pilot=float(old))

def estimate(a,curve,k=3,current=False):
    if a is None:return dict(status='unavailable',detected=False,onset_seconds=None,recovery_seconds=None,reason='nonfinite_or_nonincreasing_native_observations')
    c=context(a);t=a['t'];direction=c['direction']
    if direction==0:return dict(status='not_applicable',detected=False,onset_seconds=None,recovery_seconds=None,reason='no_limit_edge')
    curve=np.asarray(curve,float)
    if curve.shape!=t.shape or not np.isfinite(curve).all():return dict(status='unavailable',detected=False,onset_seconds=None,recovery_seconds=None,reason='native_fit_unavailable')
    base=float(np.median(curve[c['pre']]));base_i=float(np.median(a['i'][c['pre']]))
    threshold=max(.03,k*c['sigma_p']);departure=direction*(curve-base)
    condition=departure>=threshold
    if current:condition &= direction*(a['i']-base_i)>=max(.15,k*c['sigma_i'])
    hits=[j for j in c['search'] if condition[j]]
    if not hits:return dict(status='ok',detected=False,onset_seconds=None,recovery_seconds=None,reference_recorded_power_kw=base,threshold_kw=threshold,reason='no_resolved_local_departure')
    first=hits[0];back=abs(curve-base)<=max(.03,2*c['sigma_p'])
    if current:back &= abs(a['i']-base_i)<=max(.2,2*c['sigma_i'])
    returns=np.flatnonzero(back&(np.arange(len(t))>first))
    return dict(status='ok',detected=True,onset_seconds=float(t[first]),recovery_seconds=float(t[returns[0]]) if len(returns) else None,reference_recorded_power_kw=base,threshold_kw=threshold,reason='native_point_evidence',onset_raw_row_position=int(first))
