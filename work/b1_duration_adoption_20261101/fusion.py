"""Duration-focused curve reconciliation with observable CPOP safeguards.

The event-positive flag stays identical to original CPOP; no claim of improved
fault classification. Quantile/state models refine within-task duration only.
"""
import numpy as np

def reconcile(cpop,quantile,probability,starts_s,sigma,threshold=.4,band_sigma=2.,change_cap=.1,preserve_gaps=True):
    base=np.asarray(cpop,float);q=np.asarray(quantile,float);p=np.asarray(probability,float);s=np.asarray(starts_s,float)
    task=(s>=0)&(s<1800);positive=base>=.15
    if not np.any(positive[task]):return base.copy(),dict(reason='original_no_threshold_positive',changed_bins=0)
    use=(base<=.15+band_sigma*sigma)&task
    step=float(s[1]-s[0])
    edges=np.diff(np.r_[False,positive&task,False].astype(int))
    for a,b in zip(np.flatnonzero(edges==1),np.flatnonzero(edges==-1)):
        if (b-a)*step<=60.+1e-8:use[a:b]=False
    if preserve_gaps:
        # Retain observed near-zero returns between positive neighbours. This
        # protects genuine gaps rather than labelling/deleting isolated points.
        for i in range(1,len(base)-1):
            if abs(base[i])<=2*sigma and min(base[i-1],base[i+1])>=.15:use[i]=False
        edges=np.diff(np.r_[False,(~positive)&task,False].astype(int))
        for a,b in zip(np.flatnonzero(edges==1),np.flatnonzero(edges==-1)):
            if a>0 and b<len(base) and positive[a-1] and positive[b] and (b-a)*step<=60.+1e-8 and np.all(abs(base[a:b])<=2*sigma):use[a:b]=False
    corrected=np.where(p>=threshold,np.maximum(q,.150001),np.minimum(q,.149999))
    pred=np.where(use,corrected,base);flipped=(pred>=.15)!=(base>=.15);count=int(np.sum(flipped&task))
    if not np.any(pred[task]>=.15):return base.copy(),dict(reason='retained_original_task_evidence',changed_bins=0)
    if count>change_cap*int(task.sum())+1e-8:return base.copy(),dict(reason='large_change_retained_original',changed_bins=0)
    return pred,dict(reason='duration_reconciled',changed_bins=count)
