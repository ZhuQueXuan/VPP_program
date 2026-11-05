"""Observed-only dose-mean estimators. No simulator or truth imports."""
import numpy as np

DOSES=np.array([0.,.4,.8,1.2,1.6,2.,2.4])
METHODS=('M0_dose_means','M1_linear','M2_linear_spline')

def design(d,method):
    d=np.asarray(d,float)
    if not np.isfinite(d).all() or np.any(d<0) or np.any(d>2.4):
        raise ValueError('dose outside frozen support')
    if method=='M1_linear':return np.column_stack((np.ones(len(d)),d))
    if method=='M2_linear_spline':return np.column_stack((np.ones(len(d)),d,np.maximum(0,d-.8),np.maximum(0,d-1.6)))
    raise ValueError('unknown regression model')

def group_masks(x):return (np.ones(len(x),bool),x[:,0]<0,x[:,0]>=0)

def fit(dose_index,y):
    dose_index=np.asarray(dose_index,int);y=np.asarray(y,float)
    if y.ndim==1:y=y[:,None]
    if len(dose_index)!=len(y) or not np.isfinite(y).all():raise ValueError('invalid observed rows')
    counts=np.bincount(dose_index,minlength=7)
    if len(counts)!=7 or min(counts)<50:raise ValueError('insufficient group-dose support, no imputation')
    models=[]
    models.append({'method':METHODS[0],'parameter':np.array([y[dose_index==k].mean(axis=0) for k in range(7)])})
    for method in METHODS[1:]:
        b=design(DOSES[dose_index],method)
        coef,res,rank,sv=np.linalg.lstsq(b,y,rcond=None)
        if rank!=b.shape[1]:raise ValueError('rank deficient training design')
        models.append({'method':method,'parameter':coef})
    return models,counts

def predict(model,d):
    d=np.asarray(d,float)
    if model['method']==METHODS[0]:
        if not np.all(np.isin(d,DOSES)):raise ValueError('dose means only available at supported nodes')
        return model['parameter'][np.argmin(abs(d[:,None]-DOSES),axis=1)]
    return design(d,model['method'])@model['parameter']

def crossing(mu,delta):
    mu=np.asarray(mu,float);gain=mu-mu[0]
    if not np.isfinite(mu).all():return {'status':'unavailable','lower':None,'upper':None}
    if np.max(gain)<delta:return {'status':'not_reached','lower':None,'upper':None}
    if np.any(np.diff(mu)<-1e-10):return {'status':'ambiguous_nonmonotone','lower':None,'upper':None}
    k=int(np.flatnonzero(gain>=delta)[0])
    return {'status':'bracket','lower':float(DOSES[k-1]),'upper':float(DOSES[k])}
