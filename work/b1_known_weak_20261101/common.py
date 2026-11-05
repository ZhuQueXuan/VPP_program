"""Isolated first-block experiment; existing adopted method stays immutable."""
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
import sys,json,time,hashlib,importlib.util
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];OLD=ROOT/'work/b1_duration_release_20261101'
PREVIOUS=ROOT/'work/b1_command_feature_selection_20261031';V1=ROOT/'work/b1_cpop_improvement_20261031'
sys.path.insert(0,str(ROOT/'B1算法'))
from b1_algorithm.process import _duration_fusion as DF
from scipy.special import expit

def native(v):
    if isinstance(v,np.ndarray):return v.tolist()
    if isinstance(v,np.generic):return v.item()
    if isinstance(v,dict):return {k:native(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)):return [native(x) for x in v]
    return v
def write(name,value):
    p=HERE/name;p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8') as f:json.dump(native(value),f,ensure_ascii=False,allow_nan=False,separators=(',',':'))
def read(name):return json.loads((HERE/name).read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p,name):
    s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
load_module=load
def lengths(mask):
    edges=np.diff(np.r_[False,mask,False].astype(int));return np.flatnonzero(edges==-1)-np.flatnonzero(edges==1)
def measure(pred,truth,s,step):
    use=(s>=0)&(s<1800);a=np.asarray(pred)[use]>=.15;b=np.asarray(truth)[use]>=.15
    def dur(mask):
        longest=max(lengths(mask),default=0)*step
        return float(mask.sum()*step),float(longest) if longest>=30.-1e-8 else 0.
    ac,al=dur(a);bc,bl=dur(b)
    return dict(primary_seconds=.5*(abs(ac-bc)+abs(al-bl)),cumulative_error_seconds=abs(ac-bc),longest_error_seconds=abs(al-bl),
        positive_truth=bool(b.any()),positive_prediction=bool(a.any()),null_false_positive=bool(not b.any() and a.any()),
        whole_miss=bool(b.any() and not a.any()),localized_miss=bool(b.any() and not np.any(a&b)),
        true_cumulative_seconds=bc,predicted_cumulative_seconds=ac,true_longest_seconds=bl,predicted_longest_seconds=al)

def summary(rows):
    out=[]
    for regime in sorted({r['regime'] for r in rows}):
      for method in sorted({r['method'] for r in rows}):
        rr=[r for r in rows if r['regime']==regime and r['method']==method]
        panels=sorted({r['panel'] for r in rr});d=dict(regime=regime,method=method,n=len(rr))
        for k in ['primary_seconds','cumulative_error_seconds','longest_error_seconds']:
            d[k]=float(np.mean([np.mean([np.mean([r[k] for r in rr if r['panel']==p and r['condition']==c]) for c in sorted({r['condition'] for r in rr if r['panel']==p})]) for p in panels]))
        for k in ['positive_truth','null_false_positive','whole_miss','localized_miss','short_local_miss','short_n']:
            d[k]=int(sum(r[k] for r in rr))
        d['negative_n']=len(rr)-d['positive_truth'];out.append(d)
    return out

def preserved_curves(cases,original):
    X=[];slices=[];offset=0
    for c in cases:
        y=np.array(c['reference_kw'])-np.array(c['power_kw']);step=c['ends_s'][0]-c['starts_s'][0]
        fit=DF._segment_fit(y,c['sigma'],3.,0.);x=DF._model_features(y,fit['prediction'],c['sigma'],step)
        X.append(x);slices.append((offset,offset+len(y)));offset+=len(y)
    meta,models,_=DF._artifacts();X=np.vstack(X);q=DF._tree_predict(models['quantile.json'],X)*.05;p=expit(DF._tree_predict(models['state.json'],X));cfg=meta['configuration']
    out=[]
    for c,o,(a,b) in zip(cases,original,slices):
        pred,info=DF._reconcile(o['prediction'],q[a:b],p[a:b],c['starts_s'],c['sigma'],cfg['threshold'],cfg['band_sigma'],cfg['change_cap'],True)
        out.append(dict(status='ok',prediction=pred,decision=info))
    return out
