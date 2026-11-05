"""Known-reference retrospective duration calibration; observed full curves only.

Standard frozen boosted trees complement CPOP. Original input and structural
curve remain available; calibrated duration functionals do not define a new
pointwise physical curve. Existing duration_fusion is unchanged.
"""
from pathlib import Path
from functools import lru_cache
import hashlib,json
import numpy as np
from scipy.special import expit
from scipy.ndimage import uniform_filter1d
from ._duration_fusion import validate_domain,fit_duration_fusion

def features(case,cpop,duration):
    s=np.array(case['starts_s']);use=(s>=0)&(s<1800);y=np.array(case['reference_kw'])-np.array(case['power_kw']);sigma=case['sigma'];step=case['ends_s'][0]-s[0]
    z=y[use]/sigma;b=np.asarray(cpop)[use]/sigma;d=np.asarray(duration)[use]/sigma;n=len(z)
    out=[step/60,float(case['regime']=='unknown')]
    def runs(mask):
        edges=np.diff(np.r_[False,mask,False].astype(int));lens=np.flatnonzero(edges==-1)-np.flatnonzero(edges==1)
        return [len(lens),max(lens,default=0)/n,float(np.median(lens)/n) if len(lens) else 0.]
    for a in [z,b,d]:
        out.extend(np.quantile(a,[0,.01,.05,.1,.25,.5,.75,.9,.95,.99,1]))
        out.extend([a.mean(),a.std(),np.mean(abs(a)),np.mean(abs(np.diff(a)))])
        for sign in [1.,-1.]:
            v=a*sign
            for t in [2.,3.,6.]:out.extend([np.mean(v>=t),np.mean(np.maximum(v-t,0.))]+runs(v>=t))
    for seconds in [10.,30.,60.,120.,300.]:
        smooth=uniform_filter1d(z,max(1,int(round(seconds/step))),mode='nearest')
        out.extend([smooth.min(),smooth.max(),np.mean(smooth>=3.),np.mean(smooth<=-3.)])
    for part in [y[s<0],y[s>=1800]]:
        out.extend([float(np.mean(part)/sigma),float(np.std(part)/sigma),float(np.min(part)/sigma),float(np.max(part)/sigma)])
    out.extend([np.mean(z[:max(1,n//6)]),np.mean(z[-max(1,n//6):])])
    return np.array(out,dtype=np.float32)

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

def tree_predict(payload,X):
    # HistGradientBoosting thresholds are float64. Explicitly preserve that
    # comparison precision when adjacent float32 feature values form a split.
    X=np.asarray(X,np.float64);out=np.full(len(X),payload['baseline'],float)
    for tree in payload['trees']:
        nodes=np.zeros(len(X),int);active=np.ones(len(X),bool)
        while active.any():
            for index in np.unique(nodes[active]):
                use=active&(nodes==index);node=tree[int(index)]
                if node['is_leaf']:out[use]+=node['value'];active[use]=False
                else:
                    values=X[use,node['feature_idx']];left=(values<=node['num_threshold'])|(np.isnan(values)&bool(node['missing_go_to_left']))
                    nodes[use]=np.where(left,node['left'],node['right'])
    return out

@lru_cache(maxsize=1)
def _artifacts():
    folder=Path(__file__).with_name('known_duration_models')
    meta=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
    if meta['schema']!='b1.known-duration.v1':raise ValueError('known duration model schema mismatch')
    models={}
    for name,expected in meta['model_files'].items():
        if name not in ('cumulative.json','longest.json','event.json'):raise ValueError('unknown duration asset')
        raw=(folder/name).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=expected:raise ValueError('known duration asset hash mismatch')
        payload=json.loads(raw)
        if payload['features']!=171:raise ValueError('known duration feature schema mismatch')
        models[name]=payload
    identity=hashlib.sha256(json.dumps(meta,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return meta,models,identity

def fit_known_duration(data,original_prediction):
    validate_domain(data)
    old=fit_duration_fusion(data,original_prediction)
    case=dict(starts_s=data['starts']*60,ends_s=data['ends']*60,
              power_kw=data['power'],reference_kw=data['reference'],sigma=data['sigma'])
    X=input_features(case,original_prediction,old['prediction'])[None,:]
    meta,models,identity=_artifacts();cfg=meta['configuration']
    score=float(expit(tree_predict(models['event.json'],X))[0]);accepted=score>=cfg['event_threshold']
    delta=np.array([tree_predict(models[name],X)[0] for name in ['cumulative.json','longest.json']])
    value=refine(case,original_prediction,old['prediction'],delta,accepted,cfg['shrink'])
    return dict(cumulative_response_seconds=float(value[0]),longest_continuous_response_seconds=float(value[1]),
        retained_prediction=old['prediction'],model_id=identity,retained_model_id=old['model_id'],
        physical_change_score=score,physical_change_threshold=cfg['event_threshold'],physical_change_accepted=bool(accepted),
        score_is_calibrated_probability=False,field_fault_classification_validated=False,
        duration_estimator='full_observed_trajectory_duration_residual_calibration',
        reference_assumed_known=True,points_deleted_or_replaced_in_input=False)
