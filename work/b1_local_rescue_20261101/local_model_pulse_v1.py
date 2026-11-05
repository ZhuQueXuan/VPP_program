import numpy as np
from b1_algorithm.process import _known_duration as KD

def durations(mask,step):
    edge=np.diff(np.r_[False,mask,False].astype(int));lengths=np.flatnonzero(edge==-1)-np.flatnonzero(edge==1);longest=max(lengths,default=0)*step
    return np.array([mask.sum()*step,longest if longest>=30.-1e-8 else 0.],float)

def adopted(cases,curves):
    X=np.vstack([KD.input_features(c,curves[c['task_id']]['cpop']['prediction'],curves[c['task_id']]['duration_fusion']['prediction']) for c in cases]);meta,models,_=KD._artifacts();cfg=meta['configuration']
    score=KD.expit(KD.tree_predict(models['event.json'],X));delta=np.column_stack([KD.tree_predict(models[name],X) for name in ['cumulative.json','longest.json']]);est=[]
    for i,c in enumerate(cases):
        f=curves[c['task_id']];est.append(KD.refine(c,f['cpop']['prediction'],f['duration_fusion']['prediction'],delta[i],score[i]>=cfg['event_threshold'],cfg['shrink']))
    return np.asarray(est),score

def rescue(case,support,baseline,score,local_probability,threshold,z_threshold=4.):
    s=np.asarray(case['starts_s']);task=(s>=0)&(s<1800);step=case['ends_s'][0]-s[0]
    base=(np.asarray(support)>=.15)&task
    if baseline[0]<=0:base[:]=False
    raw=np.asarray(case['reference_kw'])-np.asarray(case['power_kw'])
    quiet_background=abs(np.median(raw[task]))<=.075
    candidate=np.zeros(len(s),bool)
    if score>=.025 and quiet_background:
        probability=np.asarray(local_probability);sy=np.r_[0.,np.cumsum(raw)];sp=np.r_[0.,np.cumsum(probability)];intervals=[]
        for width in range(1,max(1,int(round(60./step)))+1):
            flank=max(2,width)
            starts=np.flatnonzero(task);starts=starts[starts+width<=np.flatnonzero(task)[-1]+1];ends=starts+width
            inside=(starts>=flank)&(ends+flank<=len(raw));starts=starts[inside];ends=ends[inside]
            center=(sy[ends]-sy[starts])/width;left=(sy[starts]-sy[starts-flank])/flank;right=(sy[ends+flank]-sy[ends])/flank
            z=(center-(left+right)/2)/(case['sigma']*np.sqrt(1/width+1/(2*flank)));p=(sp[ends]-sp[starts])/width
            accept=(abs(left)<=.06)&(abs(right)<=.06)&(center>=.15)&(center<=.35)&(z>=z_threshold)&(p>=threshold)
            intervals += [(float(zz),int(a),int(b)) for zz,a,b in zip(z[accept],starts[accept],ends[accept])]
        # Strongest local two-sided pulse first; no minimum duration and no
        # removal of an existing observation or detected response.
        for _,a,b in sorted(intervals,reverse=True):
            if not candidate[a:b].any():candidate[a:b]=True
    added=candidate&~base
    mask=base|added;value=np.asarray(baseline).copy()
    if value[0]<=0 and added.any():value=durations(mask[task],step)
    return mask,value,added
