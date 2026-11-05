import numpy as np
from scipy.ndimage import median_filter
from b1_algorithm.process import _duration_fusion as DF

RAW_INDICES=[0,4,5]+list(range(6,42))+list(range(44,55))

def raw_features(case):
    y=np.asarray(case['reference_kw'])-np.asarray(case['power_kw']);s=np.asarray(case['starts_s']);sigma=case['sigma'];step=case['ends_s'][0]-s[0]
    base=DF._model_features(y,np.zeros(len(y)),sigma,step);out=[base[:,[0,4,5]+list(range(6,42))]]
    for width in [3,5,9,17,31,61]:out.append((median_filter(y,size=width,mode='nearest')/sigma)[:,None])
    task=y[(s>=0)&(s<1800)]
    for q in [.05,.25,.5,.75,.95]:out.append(np.full((len(y),1),np.quantile(task,q)/sigma))
    return np.column_stack(out).astype(np.float32)
