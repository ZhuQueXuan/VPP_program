"""Observed-only finite-grid inference; simulator and evaluator never imported."""
import numpy as np

def aggregate(user,dose,x,y,n_users=600):
    user=np.asarray(user);dose=np.asarray(dose);x=np.asarray(x);y=np.asarray(y)
    if y.ndim!=2 or y.shape[1]!=len(user):raise ValueError('expected scenario by observed-event outcomes')
    if not np.isfinite(y).all() or not np.isfinite(x).all():raise ValueError('nonfinite observations')
    masks=(np.ones(len(user),bool),x<0,x>=0)
    counts=np.zeros((3,n_users,7),int);sums=np.zeros((y.shape[0],3,n_users,7))
    for g,mask in enumerate(masks):
        np.add.at(counts[g],(user[mask],dose[mask]),1)
        for s in range(y.shape[0]):np.add.at(sums[s,g],(user[mask],dose[mask]),y[s,mask])
    return counts,sums

def estimate(counts,sums,weights,minimum=50,confidence=.95):
    """All bootstrap draws retained. A failed denominator makes its group unavailable."""
    counts=np.asarray(counts);sums=np.asarray(sums);weights=np.asarray(weights)
    den=weights@counts.reshape(counts.shape[0],counts.shape[1],7).transpose(1,0,2).reshape(counts.shape[1],-1)
    den=den.reshape(len(weights),3,7)
    total=counts.sum(axis=1)
    means=sums.sum(axis=2)/np.where(total>0,total,1)[None,:,:]
    gains=means-means[:,:,:1]
    numerator=weights@sums.transpose(2,0,1,3).reshape(counts.shape[1],-1)
    numerator=numerator.reshape(len(weights),sums.shape[0],3,7)
    bm=numerator/np.where(den>0,den,1)[:,None,:,:]
    bg=bm-bm[:,:,:,:1]
    maxima=np.max(abs(bg-gains[None,:,:,:])[:,:,:,1:],axis=-1)
    q=np.quantile(maxima,confidence,axis=0,method='higher')
    bad_draws=np.any(den==0,axis=2).sum(axis=0)
    available=(total.min(axis=1)>=minimum)&(bad_draws==0)
    q[:,~available]=np.nan
    lower=gains-q[:,:,None];upper=gains+q[:,:,None]
    lower[:,:,0]=0.;upper[:,:,0]=0.
    lower[:,~available,:]=np.nan;upper[:,~available,:]=np.nan
    return dict(mean=means,gain=gains,lower=lower,upper=upper,q=q,
                available=np.broadcast_to(available,(sums.shape[0],3)).copy(),
                bad_draws=bad_draws,counts=total,maxima=maxima)

def old_strict(gain,delta):
    g=np.asarray(gain)
    if not np.isfinite(g).all():return ('unavailable',-1)
    if g.max()<delta:return ('not_reached',-1)
    if np.any(np.diff(g)<-1e-10):return ('ambiguous_nonmonotone',-1)
    return ('bracket',int(np.flatnonzero(g>=delta)[0]))

def naive_first(gain,delta):
    g=np.asarray(gain)
    if not np.isfinite(g).all():return ('unavailable',-1)
    reached=np.flatnonzero(g>=delta)
    return ('bracket',int(reached[0])) if len(reached) else ('not_reached',-1)

def invert(lower,upper,delta):
    lo=np.asarray(lower,float);hi=np.asarray(upper,float)
    if lo.shape!=(7,) or hi.shape!=(7,) or np.any(lo>hi):raise ValueError('invalid seven-node band')
    if not np.isfinite(lo).all() or not np.isfinite(hi).all():
        return dict(status='unavailable',candidates=[],no_cross_possible=None,unique=False,possible_up=[],supported_up=[],supported_decrease=[])
    if delta<=0 or lo[0]!=0 or hi[0]!=0:raise ValueError('positive margin, zero baseline required')
    candidates=[k for k in range(1,7) if hi[k]>=delta and np.all(lo[1:k]<delta)]
    no_cross=bool(np.all(lo[1:]<delta))
    status='supported_not_reached' if not candidates else ('crossing_unresolved' if no_cross else 'bounded_first_crossing')
    return dict(status=status,candidates=candidates,no_cross_possible=no_cross,
        unique=bool(len(candidates)==1 and not no_cross),
        possible_up=[k for k in range(1,7) if lo[k-1]<delta and hi[k]>=delta],
        supported_up=[k for k in range(1,7) if hi[k-1]<delta and lo[k]>=delta],
        supported_decrease=[k for k in range(1,7) if lo[k-1]>hi[k]])
