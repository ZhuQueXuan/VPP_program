"""Whole-trajectory evidence, not an isolated-point suppression rule."""
import numpy as np
from scipy.ndimage import uniform_filter1d

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

def export(model):
    trees=[]
    for group in model._predictors:
      for predictor in group:
        assert not np.any(predictor.nodes['is_categorical'])
        trees.append([{k:float(row[k]) if k in ('value','num_threshold') else int(row[k]) for k in ['value','feature_idx','num_threshold','left','right','is_leaf','missing_go_to_left']} for row in predictor.nodes])
    return dict(schema='b1.task-response-hgb.v1',baseline=float(model._baseline_prediction[0,0]),trees=trees,features=int(model.n_features_in_))
