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

def rescue(case,support,baseline,score,local_probability,threshold):
    s=np.asarray(case['starts_s']);task=(s>=0)&(s<1800);step=case['ends_s'][0]-s[0]
    base=(np.asarray(support)>=.15)&task
    if baseline[0]<=0:base[:]=False
    raw=np.asarray(case['reference_kw'])-np.asarray(case['power_kw'])
    quiet_background=abs(np.median(raw[task]))<=.075
    added=(np.asarray(local_probability)>=threshold)&task&(score>=.025)&~base&(raw<=.35)&quiet_background
    mask=base|added;value=np.asarray(baseline).copy()
    if value[0]<=0 and added.any():value=durations(mask[task],step)
    return mask,value,added
