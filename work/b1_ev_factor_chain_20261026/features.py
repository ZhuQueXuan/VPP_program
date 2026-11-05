"""Only public time/reference/meter curves -> retrospective event features."""
import numpy as np

def extract(reference,power):
    ref=np.asarray(reference,float);p=np.asarray(power,float)
    if ref.shape!=p.shape or p.ndim!=2 or p.shape[1]!=360:raise ValueError('expected n x360 on fixed10s grid')
    if not np.isfinite(ref).all() or not np.isfinite(p).all():raise ValueError('complete finite curves required')
    reduction=ref-p;req=reduction[:,60:180];mask=req>=.15
    cumulative=mask.sum(axis=1)*10
    run=np.zeros(len(p),int);longest=np.zeros_like(run)
    for j in range(120):run=np.where(mask[:,j],run+1,0);longest=np.maximum(longest,run)
    longest=np.where(longest>=3,longest*10,0)
    return dict(cumulative_s=cumulative.astype(float),S=(cumulative>=600).astype(np.uint8),longest_s=longest,
        net_kwh=req.sum(axis=1)*10/3600,Y=req.sum(axis=1)/180,
        debt_end_kwh=reduction[:,60:].sum(axis=1)*10/3600)
