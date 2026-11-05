import numpy as np
from scipy.special import expit
from b1_algorithm.process import _local_response as LR,_effective_response as ER
from prior_parts import current_baseline as gap_baseline

def extra_features(case):
    s=np.asarray(case['starts_s']);dt=case['ends_s'][0]-s[0];use=(s>=0)&(s<1800)
    raw=np.asarray(case['reference_kw'])-np.asarray(case['power_kw']);z=raw[use];out=[]
    # Full raw observations retained. Window summaries supply repeated support;
    # none of these summaries replaces a sample or imposes minimum duration.
    for seconds in [dt,60.,120.,300.,600.]:
        width=max(1,int(round(seconds/dt)));width=min(width,len(z))
        mean=np.convolve(z,np.ones(width)/width,mode='valid')
        for q in [.05,.25,.5,.75,.9,.95,1.]:out.append(float(np.quantile(mean,q)/.05))
        for threshold in [.10,.125,.14,.15,.16,.175,.20]:out.append(float(np.mean(mean>=threshold)))
        out.extend([float(np.max(mean)-np.median(mean)),float(np.std(mean))])
    for threshold in [.10,.125,.14,.15,.16,.175,.20]:
        mask=z>=threshold;e=np.diff(np.r_[False,mask,False].astype(int));a=np.flatnonzero(e==1);b=np.flatnonzero(e==-1);length=(b-a)*dt
        out.extend([len(a)/len(z),float(np.max(length,initial=0)/1800),float(np.sum(np.maximum(z-threshold,0))*dt/1800)])
    #101 new features, all observation-only.
    return np.asarray(out,np.float32)

def current_baseline(cases,curves):
    base,masks,X=gap_baseline(cases,curves);meta,model=ER._artifacts();cfg=meta['configuration'];score=expit(LR.fast_predict(model,X))
    current=[];state=[]
    for i,c in enumerate(cases):
        value,mask,_=ER.infer(c,base[i],masks[i],score[i],cfg['threshold'],cfg['duration_cap']);current.append(value);state.append(mask)
    # Preserve exact426 inference descriptor used by previous verifier; baseline
    # fields correspond to gap proposals, even if previous qualification is0.
    return np.asarray(current),state,np.column_stack([X,np.vstack([extra_features(c) for c in cases])])

def scope(case,baseline):
    s=np.asarray(case['starts_s']);y=np.asarray(case['reference_kw'])-np.asarray(case['power_kw']);med=float(np.median(y[(s>=0)&(s<1800)]))
    return baseline[0]>0 and med<.20

def infer(case,baseline,mask,probability,quiet_threshold,weak_threshold):
    s=np.asarray(case['starts_s']);y=np.asarray(case['reference_kw'])-np.asarray(case['power_kw']);med=float(np.median(y[(s>=0)&(s<1800)]));cut=quiet_threshold if med<=.075 else weak_threshold
    reject=scope(case,baseline) and probability<cut
    return (np.zeros(2),np.zeros(len(mask),bool),True) if reject else (np.asarray(baseline).copy(),np.asarray(mask).copy(),False)
