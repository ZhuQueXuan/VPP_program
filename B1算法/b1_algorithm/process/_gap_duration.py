"""Gap-aware duration feature calibration over full known-reference observations.

Keeps adopted event decisions, localization and raw accounting. Standard frozen
HGB models estimate two duration functionals; this does not define a new power
curve or physical transition timing.
"""
from pathlib import Path
from functools import lru_cache
import hashlib,json
import numpy as np
from scipy.ndimage import uniform_filter1d
from . import _known_duration as KD,_local_response as LR

def gap_features(case,cpop,support,baseline):
    s=np.asarray(case['starts_s']);task=(s>=0)&(s<1800);step=case['ends_s'][0]-s[0];y=np.asarray(case['reference_kw'])-np.asarray(case['power_kw']);out=[];n=int(task.sum())
    traces=[y,np.asarray(cpop),np.asarray(support)]
    traces += [uniform_filter1d(y,max(1,int(round(seconds/step))),mode='nearest') for seconds in [30.,60.,120.]]
    for raw in traces:
        z=raw[task]
        for level in [.10,.15,.20]:
            mask=z>=level;edge=np.diff(np.r_[False,mask,False].astype(int));a=np.flatnonzero(edge==1);b=np.flatnonzero(edge==-1);length=b-a;order=np.argsort(-length)
            out.extend([float(mask.sum()/n),len(a)/n])
            for k in range(3):
                if k<len(order):j=order[k];out.extend([length[j]/n,a[j]/n,b[j]/n])
                else:out.extend([0.,0.,0.])
            if len(a)>1:
                gaps=a[1:]-b[:-1];out.extend([float(gaps.sum()/n),float(gaps.max()/n),float(len(gaps)/n)])
            else:out.extend([0.,0.,0.])
    out.extend(np.asarray(baseline)/1800.);out.append(baseline[1]/max(baseline[0],step))
    return np.asarray(out,np.float32)

def features(case,cpop,support,baseline,old_features=None):
    x=KD.input_features(case,cpop,support) if old_features is None else old_features
    return np.r_[x,gap_features(case,cpop,support,baseline)].astype(np.float32)

def refine(case,baseline,prediction,mix,head):
    old=np.asarray(baseline,float);s=np.asarray(case['starts_s']);task=(s>=0)&(s<1800);step=case['ends_s'][0]-s[0];y=np.asarray(case['reference_kw'])-np.asarray(case['power_kw']);median=float(np.median(y[task]))
    if old[0]<=0 or median>.4 or (old[0]<=60.+1e-8 and abs(median)<=.075):return old.copy()
    proposed_c=float(prediction[0])*1800.
    proposed_l=float(prediction[1])*proposed_c if head=='fraction' else float(prediction[1])*1800.
    value=np.rint(((1-mix)*old+mix*np.array([proposed_c,proposed_l]))/step)*step
    value[0]=np.clip(value[0],step,1800.);value[1]=np.clip(value[1],0.,value[0])
    if 0<value[1]<30.:value[1]=0.
    if step>=30. and value[0]>0:value[1]=max(step,value[1])
    count=int(round(value[0]/step));minimum=int(np.ceil(count/(int(task.sum())-count+1)))
    if minimum*step>=30.-1e-8:value[1]=max(value[1],minimum*step)
    return value

@lru_cache(maxsize=1)
def _artifacts():
    folder=Path(__file__).with_name('gap_duration_models')
    meta=json.loads((folder/'manifest.json').read_text(encoding='utf-8'));models={}
    for name,expected in meta['model_files'].items():
        raw=(folder/name).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=expected:raise ValueError('gap duration model hash mismatch')
        model=json.loads(raw)
        if model['features']!=426:raise ValueError('gap duration feature schema mismatch')
        models[name]=model
    return meta,models

def fit_gap_duration(data,baseline_result):
    meta,models=_artifacts();cfg=meta['configuration']
    case=dict(starts_s=data['starts']*60,ends_s=data['ends']*60,power_kw=data['power'],reference_kw=data['reference'],sigma=data['sigma'])
    old=baseline_result['duration_estimates'];baseline=[old['cumulative_response_seconds'],old['longest_continuous_response_seconds']]
    X=features(case,baseline_result['reduction_interval_kw'],baseline_result['retained_duration_support_curve_kw'],baseline)[None,:]
    prediction=[LR.fast_predict(models[name],X)[0] for name in ['cumulative.json','longest.json']]
    value=refine(case,baseline,prediction,cfg['mix'],cfg['head'])
    return dict(cumulative_response_seconds=float(value[0]),longest_continuous_response_seconds=float(value[1]),
        model_sha256=meta['model_files'],duration_values_changed=bool(np.any(abs(value-np.asarray(baseline))>1e-8)),
        task_decision_changed=bool((value[0]>0)!=(baseline[0]>0)),localized_mask_changed=False,raw_points_replaced=False)
