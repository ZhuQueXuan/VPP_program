"""Observable history-only features, no current outcome or mechanism inputs."""
import numpy as np

def make(current_conditions,history_conditions,history_power):
    current=np.asarray(current_conditions,float);conditions=np.asarray(history_conditions,float);power=np.asarray(history_power,float)
    if current.shape!=(3,) or conditions.shape!=(3,3) or power.shape!=(3,120) or not np.isfinite(np.r_[current,conditions.ravel(),power.ravel()]).all():raise ValueError('complete three-event histories required')
    reduction=3-power;req=reduction[:,20:60];post=reduction[:,60:]
    y=req.sum(axis=1)/60
    onset=[];dur=[];detected=[]
    for r in req:
        mask=r>=.15;ids=np.flatnonzero(mask);detected.append(len(ids)>0);onset.append(float(ids[0]*30) if len(ids) else 1200.)
        best=run=0
        for good in mask:
            run=run+1 if good else 0;best=max(best,run)
        dur.append(best*30/1200)
    onset=np.array(onset);detected=np.array(detected)
    meanon=float(onset[detected].mean()/1200) if detected.any() else 1.
    rebound=np.maximum(0,-post).sum(axis=1)*30/1800
    summary=np.r_[current,conditions.mean(axis=0),y.mean(),y[-1],detected.mean(),meanon,np.mean(dur),rebound.mean()]
    tt=np.arange(20)*30;center=tt-tt.mean();den=np.sum(center**2)
    slope1=(req[:,:20]@center/den).mean()*1200/1.5
    slope2=(req[:,20:]@center/den).mean()*1200/1.5
    shape=np.r_[summary,req[:,:20].mean()/1.5,req[:,20:].mean()/1.5,slope1,slope2,(y[-1]-y[0])/2,(onset[-1]-onset[0])/2400]
    return dict(current=current.copy(),summary=summary,shape=shape,encoder_input=(reduction/1.5).ravel())

def assemble(conditions,power,target_users,target_events):
    """Only index the permitted previous3 curves; current curves never read."""
    rows=[];maps=[]
    for u in target_users:
        for j in target_events:
            if j<3:raise ValueError('insufficient past events')
            rows.append(make(conditions[u,j],conditions[u,j-3:j],power[u,j-3:j]));maps.append((int(u),int(j)))
    return {k:np.array([r[k] for r in rows]) for k in rows[0]},np.array(maps,int)
