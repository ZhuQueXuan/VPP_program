"""Exact independent-segment polynomial DP using sufficient statistics.

Standard penalised segmented regression, not a novel change-point estimator.
Every point is retained. Segments may be one sample; degree0/1 model choice
avoids forcing a noisy slope on a stable plateau. Curve fits are meter-bin means.
"""
import numpy as np

def fit_segments(y,sigma,beta_scale=2.,slope_scale=1.,allow_linear=True):
    y=np.asarray(y,float);n=len(y)
    if y.ndim!=1 or n<3 or not np.isfinite(y).all() or not np.isfinite(sigma) or sigma<=0:raise ValueError('finite complete vector and positive sigma required')
    x=np.arange(n,dtype=float)
    sy=np.r_[0.,np.cumsum(y)];sy2=np.r_[0.,np.cumsum(y*y)];sx=np.r_[0.,np.cumsum(x)];sx2=np.r_[0.,np.cumsum(x*x)];sxy=np.r_[0.,np.cumsum(x*y)]
    a=np.arange(n)[:,None];b=np.arange(1,n+1)[None,:];length=b-a;valid=length>0;m=np.maximum(length,1)
    S=sy[b]-sy[a];S2=sy2[b]-sy2[a];X=sx[b]-sx[a];X2=sx2[b]-sx2[a];XY=sxy[b]-sxy[a]
    rss0=np.maximum(0.,S2-S*S/m);den=np.maximum(0.,X2-X*X/m);cross=XY-X*S/m
    gain=np.divide(cross*cross,den,out=np.zeros_like(den),where=den>1e-12)
    rss1=np.maximum(0.,rss0-gain)
    beta=beta_scale*np.log(n);slope_penalty=slope_scale*np.log(n)
    linear=valid&(length>=3)&((rss0-rss1)/sigma**2>slope_penalty)&allow_linear
    cost=np.where(linear,rss1/sigma**2+slope_penalty,rss0/sigma**2)
    cost=np.where(valid,cost+beta,np.inf)
    best=np.full(n+1,np.inf);best[0]=-beta;previous=np.zeros(n+1,int)
    for j in range(1,n+1):
        v=best[:j]+cost[:j,j-1];k=int(np.argmin(v));best[j]=v[k];previous[j]=k
    segments=[];j=n;pred=np.empty(n)
    while j:
        k=int(previous[j]);count=j-k;mean=(sy[j]-sy[k])/count
        if linear[k,j-1]:
            slope=cross[k,j-1]/den[k,j-1];pred[k:j]=mean+slope*(x[k:j]-(sx[j]-sx[k])/count);degree=1
        else:pred[k:j]=mean;degree=0
        segments.append(dict(start=k,end=j,degree=degree));j=k
    return dict(status='ok',prediction=pred,segments=list(reversed(segments)),objective=float(best[n]),
        beta_scale=beta_scale,slope_scale=slope_scale,allow_linear=allow_linear,points_replaced=False,method='adaptive_polynomial_segments')

def shrink_segments(y,fit,sigma,strength):
    y=np.asarray(y,float);out=np.empty(len(y))
    for segment in fit['segments']:
        a,b=segment['start'],segment['end'];z=y[a:b];x=np.arange(b-a,dtype=float);x-=x.mean();den=float(x@x)
        if den==0:out[a:b]=z.mean();continue
        slope=float(x@z/den);t2=slope*slope*den/(sigma*sigma)
        factor=max(0.,1.-strength/max(t2,1e-30))
        out[a:b]=z.mean()+factor*slope*x
    return out
