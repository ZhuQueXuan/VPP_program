"""Simulation-trained denoising of threshold-near segment estimates.

No anomaly labels, point deletion, minimum-duration filter or truth at inference.
Both raw samples and raw energy are preserved. Strong jumps/gaps retain the
unsupervised segmented-regression estimate; learned correction targets the
region whose uncertainty affects duration most. This is an engineering fusion
of standard DP and gradient boosting, not a new universal causal identifier.
"""
import numpy as np
from scipy.ndimage import uniform_filter1d,minimum_filter1d,maximum_filter1d
from candidates import fit_segments

def features(y,pred,sigma,delta_s):
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

def export_model(model):
    trees=[]
    for group in model._predictors:
        for predictor in group:
            nodes=predictor.nodes
            assert not np.any(nodes['is_categorical'])
            trees.append([{name:float(row[name]) if name in ['value','num_threshold'] else int(row[name]) for name in ['value','feature_idx','num_threshold','left','right','is_leaf','missing_go_to_left']} for row in nodes])
    return dict(schema='b1.duration-denoise-hgb.v1',baseline=float(model._baseline_prediction[0,0]),trees=trees,
        features=42,training='Controlled synthetic latent power only; no field-clean-truth performance claim',tree_leaf_values_include_learning_rate=True)

def predict_model(payload,X):
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

def fit_learned(y,sigma,delta_s,payload,weight=1.,band_sigma=1.,beta=3.,zone='below',offset_sigma=0.):
    fit=fit_segments(y,sigma,beta,0.);base=np.asarray(fit['prediction']);X=features(y,base,sigma,delta_s);learned=predict_model(payload,X)*sigma
    use=abs(base-.15)<=band_sigma*sigma if zone=='band' else base<=.15+band_sigma*sigma
    fit['prediction']=np.where(use,(1-weight)*base+weight*(learned+offset_sigma*sigma),base)
    fit['method']='segment_boost_duration';fit['correction_points']=int(use.sum())
    return fit
