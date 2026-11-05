"""Observed feature outcomes and declared adjustment only; no simulator access."""
import numpy as np

def fit(x,w,d,a,outcomes,columns,minimum):
    observed={'X':np.asarray(x,int),'W':np.asarray(w,int),'A':np.asarray(a,int)}
    code=sum(observed[c]*(2**i) for i,c in enumerate(columns)) if columns else np.zeros(len(d),int)
    tables=np.zeros((2,2**len(columns),2));counts=np.zeros(tables.shape[:2],int)
    for arm in (0,1):
        for k in range(tables.shape[1]):
            mask=(d==arm)&(code==k);counts[arm,k]=mask.sum()
            if mask.any():tables[arm,k]=outcomes[mask].mean(axis=0)
    valid=bool(counts.min()>=minimum)
    return dict(columns=columns,counts=counts.tolist(),available=valid,table=tables.tolist() if valid else None,minimum_required=minimum)

def predict(model,x,w,a=None):
    if not model['available']:return np.full((len(x),2,2),np.nan)
    fields={'X':np.asarray(x,int),'W':np.asarray(w,int)}
    if a is not None:fields['A']=np.asarray(a,int)
    code=sum(fields[c]*(2**i) for i,c in enumerate(model['columns'])) if model['columns'] else np.zeros(len(x),int)
    table=np.asarray(model['table']);return table[:,code,:].transpose(1,0,2)
