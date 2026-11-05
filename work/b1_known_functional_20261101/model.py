"""Duration functionals calibrated from full observed curves, no future forecast."""
import numpy as np
from task_model import features

def durations(pred,starts,step):
    s=np.asarray(starts);mask=np.asarray(pred)[(s>=0)&(s<1800)]>=.15;edges=np.diff(np.r_[False,mask,False].astype(int));runs=np.flatnonzero(edges==-1)-np.flatnonzero(edges==1)
    longest=max(runs,default=0)*step
    return np.array([mask.sum()*step,longest if longest>=30.-1e-8 else 0.],float)

def input_features(case,cpop,retained):
    step=case['ends_s'][0]-case['starts_s'][0]
    return np.r_[features(dict(case,regime='known'),cpop,retained),durations(cpop,case['starts_s'],step)/1800.,durations(retained,case['starts_s'],step)/1800.].astype(np.float32)

def refine(case,cpop,retained,delta,accepted,shrink):
    s=np.array(case['starts_s']);use=(s>=0)&(s<1800);step=case['ends_s'][0]-s[0];old=durations(retained,s,step)
    if not accepted:return np.array([0.,0.])
    if old[0]==0:return old
    # Preserve existing short positive support. Strong plateaus remain on the
    # previously adopted extractor; calibration targets weak/low-duty traces.
    y=np.asarray(case['reference_kw'])-np.asarray(case['power_kw'])
    if old[0]<=60.+1e-8 or np.median(y[use])>.4:return old
    positive=(np.asarray(cpop)>=.15)&use;edge=np.diff(np.r_[False,positive,False].astype(int));count=0;long=0.
    for a,b in zip(np.flatnonzero(edge==1),np.flatnonzero(edge==-1)):
        seconds=(b-a)*step
        if seconds<=60.+1e-8:count+=b-a;long=max(long,seconds if seconds>=30 else 0.)
    # The whole short task is already protected above. Summing every short
    # CPOP fragment in a long weak/noisy trace wrongly anchors false positives.
    # Calibrate long-task durations without replacing or deleting any samples.
    lower=step;value=np.rint((old+shrink*np.asarray(delta))/step)*step
    value[0]=np.clip(value[0],lower,1800.);value[1]=np.clip(value[1],0.,value[0])
    if 0<value[1]<30.:value[1]=0.
    if step>=30. and value[0]>0:value[1]=max(step,value[1])
    n=int(use.sum());positive_count=int(round(value[0]/step));minimum_run=int(np.ceil(positive_count/(n-positive_count+1)))
    if minimum_run*step>=30.-1e-8:value[1]=max(value[1],minimum_run*step)
    return value
