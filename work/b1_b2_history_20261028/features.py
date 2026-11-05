"""Only past completed curves enter historical summaries or ordered encoding."""
import numpy as np
from legacy import b1_event

def physical(o):
    qmax=np.minimum(o['b'],(7.2-o['b'])*(o['T']/60-.5)/.5)
    out=dict(o);out['qmax']=qmax;out['physical_feasible']=o['q']<=qmax+1e-10;out['eligible']=out['physical_feasible']&o['permission'].astype(bool)
    out['discomfort']=o['q']/7.2+o['q']*.5/o['E'];out['margin']=(qmax-o['q'])/7.2
    return out

def current(o,probabilities):
    z=np.maximum(probabilities,1e-8);odds=np.log(z[:,1:]/z[:,:1])
    return np.column_stack([odds,o['b']/7.2,o['T']/120,o['q']/3,o['low']/2,o['high']/4,o['prob'],o['reference']/2.4,
        o['green_preference'],o['green_attribute'],o['risk'],o['margin'],o['discomfort']])

def summarize(events):
    a=np.asarray(events,float)
    if a.shape!=(3,4) or not np.isfinite(a).all():raise ValueError('three complete B1 feature rows required')
    return np.array([a[:,0].mean(),a[-1,0],a[:,1].mean(),a[:,2].mean(),a[:,3].mean(),(a[-1,0]-a[0,0])/2])

def extract_one(reference,power,q):
    reference=np.asarray(reference,float);power=np.asarray(power,float);q=np.asarray(q,float)
    if reference.shape!=(3,120) or power.shape!=(3,120) or q.shape!=(3,) or not np.isfinite(np.r_[reference.ravel(),power.ravel(),q]).all() or q.min()<=0:raise ValueError('complete past curves and positive offered amplitudes required')
    event=np.array([b1_event(reference[i],power[i],q[i]) for i in range(3)])
    raw=((reference[:,:30]-power[:,:30])/q[:,None]).reshape(90)
    return dict(summary=summarize(event),raw=raw,b1_features=event)

def assemble(o,power,b1features,users,events):
    rows=[];raw=[];index=[]
    for u in users:
        for j in events:
            if j<3:raise ValueError('insufficient completed history')
            rows.append(summarize(b1features[u,j-3:j]))
            ref=o['b'][u,j-3:j,None]*(np.arange(120)[None,:]<o['T'][u,j-3:j,None])
            raw.append(((ref[:,:30]-power[u,j-3:j,:30])/o['q'][u,j-3:j,None]).ravel())
            index.append((int(u),int(j)))
    return dict(summary=np.array(rows),raw=np.array(raw)),np.array(index,int)
