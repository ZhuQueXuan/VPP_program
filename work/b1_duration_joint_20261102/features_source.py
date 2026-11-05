"""Known-reference weak-state inference; original short CPOP support is fixed."""
import numpy as np
from scipy.ndimage import median_filter
from b1_algorithm.process import _duration_fusion as DF

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

def state_features(case,cpop):
    y=np.array(case['reference_kw'])-np.array(case['power_kw']);sigma=case['sigma'];step=case['ends_s'][0]-case['starts_s'][0]
    segmented=DF._segment_fit(y,sigma,3.,0.)['prediction'];X=DF._model_features(y,segmented,sigma,step);base=np.asarray(cpop)
    cols=[base/sigma,(base-.15)/sigma]
    for width in [3,5,9,17,31,61]:cols.append(median_filter(y,size=width,mode='nearest')/sigma)
    task=y[(np.array(case['starts_s'])>=0)&(np.array(case['starts_s'])<1800)]
    for q in [.05,.25,.5,.75,.95]:cols.append(np.full(len(y),np.quantile(task,q)/sigma))
    return np.column_stack([X]+cols).astype(np.float32)

def decode(case,cpop,probability,median_prediction,threshold,switch_penalty):
    base=np.asarray(cpop,float);s=np.array(case['starts_s']);step=case['ends_s'][0]-s[0];task=(s>=0)&(s<1800);positive=base>=.15
    if not positive[task].any():return base.copy()
    # Fixed support keeps genuine short positive runs and clear negative gaps.
    flexible=(base>.10)&(base<=.25)&task
    edges=np.diff(np.r_[False,positive&task,False].astype(int))
    for a,b in zip(np.flatnonzero(edges==1),np.flatnonzero(edges==-1)):
        if (b-a)*step<=60.+1e-8:flexible[a:b]=False
    probability=np.clip(np.asarray(probability),1e-7,1-1e-7)
    odds=np.log(probability/(1-probability))-np.log(threshold/(1-threshold))
    loss=np.column_stack([np.zeros(len(base)),-odds]);loss[~flexible,1-positive[~flexible].astype(int)]=np.inf
    back=np.zeros((len(base),2),np.int8);v0,v1=loss[0]
    for i in range(1,len(base)):
        a,b=v0,v1
        back[i,0]=int(a>b+switch_penalty);back[i,1]=int(b<=a+switch_penalty)
        v0=loss[i,0]+min(a,b+switch_penalty);v1=loss[i,1]+min(b,a+switch_penalty)
    mask=np.zeros(len(base),bool);j=int(v1<v0)
    for i in range(len(base)-1,-1,-1):mask[i]=j;j=int(back[i,j])
    pred=np.where(flexible,np.where(mask,np.maximum(median_prediction,.150001),np.minimum(median_prediction,.149999)),base)
    # No change of entire task evidence at the duration stage. The separate
    # event classifier is evaluated explicitly, including every additional miss.
    if not np.any(pred[task]>=.15):return base.copy()
    if np.sum(((pred>=.15)!=(base>=.15))&task)>.2*task.sum():return base.copy()
    return pred

def export(model):
    trees=[]
    for group in model._predictors:
      for predictor in group:
        assert not np.any(predictor.nodes['is_categorical'])
        trees.append([{k:float(v[k]) if k in ['value','num_threshold'] else int(v[k]) for k in ['value','feature_idx','num_threshold','left','right','is_leaf','missing_go_to_left']} for v in predictor.nodes])
    return dict(schema='b1.known-weak-hgb.v1',baseline=float(model._baseline_prediction[0,0]),features=int(model.n_features_in_),trees=trees)
