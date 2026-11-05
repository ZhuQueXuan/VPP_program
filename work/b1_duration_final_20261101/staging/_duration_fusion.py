"""Retrospective duration fusion; frozen synthetic model, explicit bounded domain.

Original measurements/accounting and default policy are preserved. This is a
domain-specific composition of standard models, not a new universal detector.
"""
from pathlib import Path
from functools import lru_cache
import hashlib,json
import numpy as np
from scipy.ndimage import uniform_filter1d,minimum_filter1d,maximum_filter1d
from scipy.special import expit

def _segment_fit(y,sigma,beta_scale=2.,slope_scale=1.,allow_linear=True):
    y=np.asarray(y,float);n=len(y)
    if y.ndim!=1 or n<3 or not np.isfinite(y).all() or not np.isfinite(sigma) or sigma<=0:raise ValueError('finite complete vector and positive sigma required')
    x=np.arange(n,dtype=float)
    sy=np.r_[0.,np.cumsum(y)];sy2=np.r_[0.,np.cumsum(y*y)];sx=np.r_[0.,np.cumsum(x)];sx2=np.r_[0.,np.cumsum(x*x)];sxy=np.r_[0.,np.cumsum(x*y)]
    a=np.arange(n)[:,None];b=np.arange(1,n+1)[None,:];length=b-a;valid=length>0;m=np.maximum(length,1)
    S=sy[b]-sy[a];S2=sy2[b]-sy2[a];X=sx[b]-sx[a];X2=sx2[b]-sx2[a];XY=sxy[b]-sxy[a]
    rss0=np.maximum(0.,S2-S*S/m);den=np.maximum(0.,X2-X*X/m);cross=XY-X*S/m
    gain=np.divide(cross*cross,den,out=np.zeros_like(den),where=den>1e-12)
    rss1=np.maximum(0.,rss0-gain)
    beta=beta_scale*np.log(n);slope_penalty=slope_scale*np.log(n)
    linear=valid&(length>=3)&((rss0-rss1)/sigma**2>slope_penalty)&allow_linear
    cost=np.where(linear,rss1/sigma**2+slope_penalty,rss0/sigma**2)
    cost=np.where(valid,cost+beta,np.inf)
    best=np.full(n+1,np.inf);best[0]=-beta;previous=np.zeros(n+1,int)
    for j in range(1,n+1):
        v=best[:j]+cost[:j,j-1];k=int(np.argmin(v));best[j]=v[k];previous[j]=k
    segments=[];j=n;pred=np.empty(n)
    while j:
        k=int(previous[j]);count=j-k;mean=(sy[j]-sy[k])/count
        if linear[k,j-1]:
            slope=cross[k,j-1]/den[k,j-1];pred[k:j]=mean+slope*(x[k:j]-(sx[j]-sx[k])/count);degree=1
        else:pred[k:j]=mean;degree=0
        segments.append(dict(start=k,end=j,degree=degree));j=k
    return dict(status='ok',prediction=pred,segments=list(reversed(segments)),objective=float(best[n]),
        beta_scale=beta_scale,slope_scale=slope_scale,allow_linear=allow_linear,points_replaced=False,method='adaptive_polynomial_segments')

def _model_features(y,pred,sigma,delta_s):
    y=np.asarray(y,float);p=np.asarray(pred,float);n=len(y);tau=.15
    cols=[y/sigma,p/sigma,(y-p)/sigma,(p-tau)/sigma,np.full(n,tau/sigma),np.full(n,delta_s/60)]
    for width in [3,5,9,17,31,61]:
        mean=uniform_filter1d(y,width,mode='nearest');var=np.maximum(0.,uniform_filter1d(y*y,width,mode='nearest')-mean*mean)
        cols += [mean/sigma,np.sqrt(var)/sigma,minimum_filter1d(y,width,mode='nearest')/sigma,maximum_filter1d(y,width,mode='nearest')/sigma]
    for offset in [1,2,3]:
        left=y[np.maximum(np.arange(n)-offset,0)];right=y[np.minimum(np.arange(n)+offset,n-1)]
        cols += [left/sigma,right/sigma,(right-left)/sigma]
    # Retrospective same-task summaries; no kind/seed/true amplitude/time labels.
    pre=n//4;task=y[pre:3*pre]
    for q in [.1,.5,.9]:cols.append(np.full(n,np.quantile(task,q)/sigma))
    return np.column_stack(cols).astype(np.float32)

def _tree_predict(payload,X):
    X=np.asarray(X,np.float32);out=np.full(len(X),payload['baseline'],float)
    for tree in payload['trees']:
        nodes=np.zeros(len(X),int);active=np.ones(len(X),bool)
        while active.any():
            for index in np.unique(nodes[active]):
                use=active&(nodes==index);node=tree[int(index)]
                if node['is_leaf']:out[use]+=node['value'];active[use]=False
                else:
                    vals=X[use,node['feature_idx']];left=(vals<=node['num_threshold'])|(np.isnan(vals)&bool(node['missing_go_to_left']))
                    nodes[use]=np.where(left,node['left'],node['right'])
    return out

def _reconcile(cpop,quantile,probability,starts_s,sigma,threshold=.4,band_sigma=2.,change_cap=.1,preserve_gaps=True):
    base=np.asarray(cpop,float);q=np.asarray(quantile,float);p=np.asarray(probability,float);s=np.asarray(starts_s,float)
    task=(s>=0)&(s<1800);positive=base>=.15
    if not np.any(positive[task]):return base.copy(),dict(reason='original_no_threshold_positive',changed_bins=0)
    use=(base<=.15+band_sigma*sigma)&task&positive
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

@lru_cache(maxsize=1)
def _artifacts():
    folder=Path(__file__).with_name('duration_models')
    meta=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
    if meta.get('schema')!='b1.duration-fusion.v1':raise ValueError('duration model schema mismatch')
    models={}
    for name,expected in meta['model_files'].items():
        if name not in ('quantile.json','state.json'):raise ValueError('unknown duration model file')
        raw=(folder/name).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=expected:raise ValueError('duration model hash mismatch')
        value=json.loads(raw)
        if value.get('features')!=42:raise ValueError('duration model feature schema mismatch')
        models[name]=value
    identity=hashlib.sha256(json.dumps(meta,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return meta,models,identity

def validate_domain(data):
    checks={'W':30.,'q':1.5,'sigma':.05}
    for key,expected in checks.items():
        if not np.isclose(data[key],expected,atol=1e-9,rtol=0):raise ValueError('duration_fusion domain requires '+key+'='+str(expected))
    if not any(np.isclose(data['delta'],v,atol=1e-9,rtol=0) for v in (1.,1/6)):
        raise ValueError('duration_fusion requires1min or10s observed intervals')
    profile=data['profile']
    for key,expected in [('observation_pre_min',15.),('observation_post_min',15.),('onset_fraction',.1),('target_fraction',.9),('recovery_fraction',.1),('dwell_seconds',30.)]:
        if not np.isclose(getattr(profile,key),expected,atol=1e-9,rtol=0):raise ValueError('duration_fusion domain requires '+key+'='+str(expected))

def fit_duration_fusion(data,original_prediction):
    validate_domain(data)
    meta,models,identity=_artifacts();cfg=meta['configuration']
    original=np.asarray(original_prediction,float)
    if original.shape!=data['y'].shape or not np.isfinite(original).all():raise ValueError('complete original CPOP curve required')
    base=_segment_fit(data['y'],data['sigma'],cfg['beta'],0.)
    X=_model_features(data['y'],base['prediction'],data['sigma'],data['delta']*60)
    quantile=_tree_predict(models['quantile.json'],X)*data['sigma']
    probability=expit(_tree_predict(models['state.json'],X))
    pred,decision=_reconcile(original,quantile,probability,data['starts']*60,data['sigma'],cfg['threshold'],cfg['band_sigma'],cfg['change_cap'],cfg['preserve_gaps'])
    use=(data['starts']>=0)&(data['starts']<30)
    if not np.isfinite(pred).all() or bool(np.any(pred[use]>=.15))!=bool(np.any(original[use]>=.15)):
        raise ValueError('duration fusion violated original task-evidence contract')
    return dict(prediction=pred,model_id=identity,decision=decision,
        curve_role='threshold_state_reconciled_curve; original CPOP structural curve retained separately',
        training_domain=meta['validation_scope'],probability_calibrated=False,
        task_detection='original_CPOP_threshold_positive_unchanged',points_deleted_or_replaced_in_input=False)
