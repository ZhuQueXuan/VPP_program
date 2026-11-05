import numpy as np
from b1_algorithm.process import _gap_duration as GD,_local_response as LR
from baseline_parts import adopted,features as previous_features,refine as previous_refine

def scope(case,baseline):
    s=np.asarray(case['starts_s']);inside=(s>=0)&(s<1800);y=np.asarray(case['reference_kw'])-np.asarray(case['power_kw']);median=float(np.median(y[inside]))
    return baseline[0]>0 and .075<median<.20

def current_baseline(cases,curves):
    local,oldX,masks=adopted(cases,curves,True);X=[]
    for i,c in enumerate(cases):
        f=curves[c['task_id']];X.append(previous_features(c,f['cpop']['prediction'],f['duration_fusion']['prediction'],local[i],oldX[i]))
    X=np.vstack(X);meta,models=GD._artifacts();cfg=meta['configuration'];pred=np.column_stack([LR.fast_predict(models[n],X) for n in ['cumulative.json','longest.json']]);current=[]
    for i,c in enumerate(cases):current.append(previous_refine(c,local[i],pred[i],cfg['mix'],cfg['head']))
    current=np.asarray(current)
    # Only the final three baseline-duration fields differ from the frozen
    #426-feature raw/structural descriptor; update them for effective checking.
    X[:,-3:-1]=current/1800.
    for i,c in enumerate(cases):X[i,-1]=current[i,1]/max(current[i,0],c['ends_s'][0]-c['starts_s'][0])
    return current,masks,X

def infer(case,baseline,mask,probability,threshold,duration_cap):
    reject=scope(case,baseline) and baseline[0]<=duration_cap and probability<threshold
    if reject:return np.zeros(2),np.zeros(len(mask),bool),True
    return np.asarray(baseline).copy(),np.asarray(mask).copy(),False
