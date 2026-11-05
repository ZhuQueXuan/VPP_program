"""Local raw-trajectory short-response rescue for known-reference historical tasks.

Add localized evidence to the adopted duration method. Original meter values,
raw energy and original structural curve remain unchanged. Standard frozen HGB,
two-sided pulse scan and fusion; no new CPOP solver or fault-truth guarantee.
"""
from pathlib import Path
from functools import lru_cache
import hashlib,json
import numpy as np
from scipy.special import expit
from scipy.ndimage import median_filter
from . import _duration_fusion as DF

def raw_features(case):
    y=np.asarray(case['reference_kw'])-np.asarray(case['power_kw']);s=np.asarray(case['starts_s']);sigma=case['sigma'];step=case['ends_s'][0]-s[0]
    base=DF._model_features(y,np.zeros(len(y)),sigma,step);out=[base[:,[0,4,5]+list(range(6,42))]]
    for width in [3,5,9,17,31,61]:out.append((median_filter(y,size=width,mode='nearest')/sigma)[:,None])
    task=y[(s>=0)&(s<1800)]
    for q in [.05,.25,.5,.75,.95]:out.append(np.full((len(y),1),np.quantile(task,q)/sigma))
    return np.column_stack(out).astype(np.float32)

def fast_predict(payload,X):
    X=np.asarray(X,np.float64);out=np.full(len(X),payload['baseline'],float)
    for tree in payload['trees']:
        node=np.zeros(len(X),int);active=np.arange(len(X))
        leaf=np.array([v['is_leaf'] for v in tree],bool);value=np.array([v['value'] for v in tree]);feature=np.array([v['feature_idx'] for v in tree]);threshold=np.array([v['num_threshold'] for v in tree]);left=np.array([v['left'] for v in tree]);right=np.array([v['right'] for v in tree]);missing=np.array([v['missing_go_to_left'] for v in tree],bool)
        while len(active):
            n=node[active];done=leaf[n];out[active[done]]+=value[n[done]];active=active[~done];n=n[~done]
            v=X[active,feature[n]];go=(v<=threshold[n])|(np.isnan(v)&missing[n]);node[active]=np.where(go,left[n],right[n])
    return out

def durations(mask,step):
    edge=np.diff(np.r_[False,mask,False].astype(int));lengths=np.flatnonzero(edge==-1)-np.flatnonzero(edge==1);longest=max(lengths,default=0)*step
    return np.array([mask.sum()*step,longest if longest>=30.-1e-8 else 0.],float)

def rescue(case,support,baseline,score,local_probability,threshold,z_threshold=4.,amplitude_margin_sigma=0.):
    s=np.asarray(case['starts_s']);task=(s>=0)&(s<1800);step=case['ends_s'][0]-s[0]
    base=(np.asarray(support)>=.15)&task
    if baseline[0]>0:
        return base,np.asarray(baseline).copy(),np.zeros(len(s),bool)
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
            supported_amplitude=center-amplitude_margin_sigma*case['sigma']/np.sqrt(width)
            accept=(abs(left)<=.06)&(abs(right)<=.06)&(supported_amplitude>=.15)&(center<=.35)&(z>=z_threshold)&(p>=threshold)
            intervals += [(float(zz),int(a),int(b)) for zz,a,b in zip(z[accept],starts[accept],ends[accept])]
        # Strongest local two-sided pulse first; no minimum duration and no
        # removal of an existing observation or detected response.
        for _,a,b in sorted(intervals,reverse=True):
            if not candidate[a:b].any():candidate[a:b]=True
    added=candidate&~base
    mask=base|added;value=np.asarray(baseline).copy()
    if value[0]<=0 and added.any():value=durations(mask[task],step)
    return mask,value,added

@lru_cache(maxsize=1)
def _artifacts():
    folder=Path(__file__).with_name('local_response_models')
    meta=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
    raw=(folder/'local.json').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=meta['model_sha256']:raise ValueError('local response model hash mismatch')
    payload=json.loads(raw)
    if payload['features']!=50:raise ValueError('local response feature schema mismatch')
    return meta,payload

def intervals(mask,starts,step):
    edge=np.diff(np.r_[False,mask,False].astype(int))
    return [[float(starts[a]),float(starts[b-1]+step)] for a,b in zip(np.flatnonzero(edge==1),np.flatnonzero(edge==-1))]

def fit_local_response(data,baseline_result):
    meta,model=_artifacts();cfg=meta['configuration']
    case=dict(starts_s=data['starts']*60,ends_s=data['ends']*60,power_kw=data['power'],reference_kw=data['reference'],sigma=data['sigma'])
    probability=expit(fast_predict(model,raw_features(case)))
    features=baseline_result['features']['selected_curve']
    baseline=[features['cumulative_response_seconds'],features['longest_continuous_response_seconds']]
    support=baseline_result['retained_duration_support_curve_kw'];physical=baseline_result['selection_evidence']['physical_change_score']
    mask,value,added=rescue(case,support,baseline,physical,probability,cfg['threshold'],cfg['z_threshold'],cfg['amplitude_margin_sigma'])
    return dict(cumulative_response_seconds=float(value[0]),longest_continuous_response_seconds=float(value[1]),
        localized_threshold_state=mask.tolist(),localized_response_intervals_seconds=intervals(mask,case['starts_s'],data['delta']*60),
        rescued_response_intervals_seconds=intervals(added,case['starts_s'],data['delta']*60),
        rescued_bins=int(sum(added)),duration_source='local_rescue_mask' if baseline[0]<=0 and added.any() else 'adopted_direct_duration_calibration',
        model_sha256=meta['model_sha256'],raw_input_points_replaced=False)
