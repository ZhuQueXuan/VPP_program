"""New autonomous feature-method selection; old experiments are development only."""
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
import json,time,csv,hashlib,sys,importlib.util,subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
PREVIOUS=ROOT/'work/b1_command_feature_selection_20261031'
V1=ROOT/'work/b1_cpop_improvement_20261031'
sys.path.insert(0,str(ROOT/'B1算法'))
from b1_algorithm.process._cpop import fit_cases
from b1_algorithm.api import _default_runtime_config

def native(v):
    if isinstance(v,np.generic):return v.item()
    if isinstance(v,np.ndarray):return v.tolist()
    if isinstance(v,dict):return {k:native(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)):return [native(x) for x in v]
    return v
def write(name,v):
    p=HERE/name;p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8') as f:json.dump(native(v),f,ensure_ascii=False,allow_nan=False,separators=(',',':'))
def read(name):return json.loads((HERE/name).read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load_module(p,name):
    s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def runtime(d):
    c=_default_runtime_config();c['artifact_dir']=str(HERE/d);c['timeout_seconds']=180;return c
def summary(rows):
    out=[]
    for method in sorted({r['method'] for r in rows}):
      for panel in ['all']+sorted({r['panel'] for r in rows}):
        rr=[r for r in rows if r['method']==method and (panel=='all' or r['panel']==panel)]
        if not rr:continue
        d=dict(method=method,panel=panel,n=len(rr))
        for k in ['primary_seconds','cumulative_error_seconds','longest_error_seconds','seconds']:d[k]=float(np.mean([r[k] for r in rr]))
        for k in ['whole_miss','null_false_positive','short_local_miss','true_gap_filled']:d[k]=int(sum(r[k] for r in rr))
        out.append(d)
    return out
def measure(pred,truth,s,step):
    use=(s>=0)&(s<1800);a=np.asarray(pred)[use];b=np.asarray(truth)[use];pm=a>=.15;tm=b>=.15
    def duration(m):
        edges=np.diff(np.r_[False,m,False].astype(int));lens=np.flatnonzero(edges==-1)-np.flatnonzero(edges==1);longest=float(max(lens,default=0)*step)
        return float(np.sum(m)*step),longest if longest>=30.-1e-8 else 0.
    pc,pl=duration(pm);tc,tl=duration(tm);ce=abs(pc-tc);le=abs(pl-tl)
    edges=np.diff(np.r_[False,~tm,False].astype(int));gaps=list(zip(np.flatnonzero(edges==1),np.flatnonzero(edges==-1)))
    gap_filled=any(a>0 and b<len(tm) and np.all(pm[a:b]) for a,b in gaps)
    return dict(primary_seconds=.5*(ce+le),cumulative_error_seconds=ce,longest_error_seconds=le,
        whole_miss=bool(tm.any() and not pm.any()),null_false_positive=bool(not tm.any() and pm.any()),
        short_local_miss=bool(tm.any() and not np.any(pm&tm)),true_gap_filled=bool(gap_filled))
