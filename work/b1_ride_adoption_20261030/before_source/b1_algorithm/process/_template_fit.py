"""Task-template candidate adapted from RIDE; finite success-aware fitting."""
import numpy as np
from scipy.optimize import least_squares
from . import _ride_template as tpl

def fit_template(starts,ends,y,sigma,q=1.5,train=None,seed=711):
    s,e,y=(np.asarray(v,float) for v in (starts,ends,y))
    mask=np.ones(len(y),bool) if train is None else np.asarray(train,bool)
    st,et,r=s[mask],e[mask],y[mask];n=len(r)
    if n<10:return dict(status='unavailable',reason='template_information_insufficient')
    W=30.;rng=np.random.default_rng(seed);mid=(st+et)/2
    inside=(st>=0)&(et<=W)
    level=float(np.clip(np.quantile(r[inside],.8)/q if inside.any() else .5,.05,1.5))
    positive=np.flatnonzero(inside&(r>=max(.15,.2*level*q)))
    delay=max(0,float(mid[positive[0]])-1) if len(positive) else 1.
    initials=[np.array([1.,2.,level,27.,2.,0.,0.]),
              np.array([delay,5.,level,max(1,W-delay-5),3.,0.,0.]),
              np.array([rng.uniform(0,5),rng.uniform(1,10),level,rng.uniform(12,30),rng.uniform(1,5),.05,10.])]
    bounds7=(np.zeros(7),np.array([30.,30.,1.5,30.,30.,1.,180.]))
    fits=[]
    for struct,p in [(1,7),(2,9)]:
        if n<=p:continue
        lb,ub=bounds7
        if p==9:lb=np.r_[lb,0,0];ub=np.r_[ub,30,30]
        def predict(theta,ss=st,ee=et):return q*tpl.interval_average(theta,W,ss,ee)
        def fun(theta):return (predict(theta)-r)/sigma
        def jac(theta):
            h=1e-6*np.maximum(1,np.abs(theta));h=np.where(theta+h>ub,-h,h)
            th=np.vstack([theta,theta+np.diag(h)])
            values=q*tpl.interval_average(th,W,st,et)
            return ((values[1:]-values[0])/h[:,None]).T/sigma
        best=None
        for initial in initials:
            initial=np.r_[initial,7.5,3.] if p==9 else initial
            try:
                result=least_squares(fun,np.clip(initial,lb,ub),jac=jac,bounds=(lb,ub),
                    method='trf',max_nfev=180,x_scale=np.maximum(ub-lb,1e-3)/10,
                    ftol=1e-6,xtol=1e-6,gtol=1e-6)
            except (ValueError,FloatingPointError):continue
            if not result.success or not np.isfinite(result.fun).all():continue
            cost=float(np.sum(result.fun**2))
            if best is None or cost<best[0]:best=(cost,result.x)
        if best is not None:fits.append((best[0]+p*np.log(n),struct,best[1],best[0]))
    if not fits:return dict(status='unavailable',reason='template_optimizer_failed')
    bic,struct,theta,rss=min(fits,key=lambda row:row[0])
    detected=bic<float(np.sum((r/sigma)**2)) and float(tpl.timing(theta,W)['level'])>=.1
    curve=q*tpl.interval_average(theta,W,s,e) if detected else np.zeros(len(y))
    if not np.isfinite(curve).all():return dict(status='unavailable',reason='template_nonfinite_prediction')
    return dict(status='ok',prediction=curve,structure=struct if detected else 0,
                bic=float(bic),theta=theta.tolist() if detected else None,optimizer_success=True)
