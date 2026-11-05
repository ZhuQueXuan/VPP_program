import time
import numpy as np
import joblib
from scipy.stats import t
from io_utils import BASE,RAW,ROOT,read,write,sha
from features import current,assemble
from legacy import base_forecast
from models import fit,select,metrics,NAMES

def designs(raw,b1,r):
    keys=['b','T','q','E','low','high','prob','reference','green_preference','green_attribute','risk','permission','qmax','physical_feasible','eligible','discomfort','margin']
    o={k:raw[k][r] for k in keys};flat={k:v.ravel() for k,v in o.items()};bp=base_forecast(flat).reshape(400,12,6);parts=[]
    for sp,events in enumerate([range(3,7),range(7,9),range(9,12)]):
        users=np.flatnonzero(raw['split'][r]==sp)
        for scene in range(3):
            h,idx=assemble(o,raw['power'][r,scene],b1[r,scene],users,events);u,j=idx.T;sub={k:v[u,j] for k,v in o.items()}
            parts.append(dict(X=current(sub,bp[u,j]),S=h['summary'],H=h['raw'],y=raw['label'][r,scene,u,j],q=sub['q'],eligible=sub['eligible'],split=np.full(len(u),sp),scene=np.full(len(u),scene),user=u,event=j,base=bp[u,j]))
    return {k:np.concatenate([v[k] for v in parts]) for k in parts[0]}

def frozen():
    f=read(BASE/'source_freeze.json')
    for group,root in [('source',BASE),('protected',ROOT)]:
        for path,h in f[group].items():assert sha(root/path)==h,str(root/path)

def train():
    frozen();start=time.perf_counter();raw=np.load(RAW/'observations.npz');b1=np.load(BASE/'b1_features.npz')['features'];meta=[];models=[];choices=[]
    for r in range(20):
        d=designs(raw,b1,r);m,p,info=fit(d['X'],d['S'],d['H'],d['y'],d['eligible'],d['split']==0,r);choice,score=select(p,d['y'],d['q'],d['split']==1)
        z=m['scale'].transform(d['H']);info['reconstruction']={str(sp):dict(pca=float(np.mean((m['pca'].inverse_transform(m['pca'].transform(z[d['split']==sp]))-z[d['split']==sp])**2)),ae=float(np.mean((m['ae'].predict(z[d['split']==sp])-z[d['split']==sp])**2))) for sp in range(3)}
        with (BASE/f'replicate_{r:02d}.npz').open('xb') as f:np.savez_compressed(f,**d,probabilities=p)
        models.append(m);choices.append(choice);meta.append(dict(rep=r,selected=NAMES[choice],validation=score,**info));print('fit and validation selection',r+1,NAMES[choice],flush=True)
    with (BASE/'models.joblib').open('xb') as f:joblib.dump(models,f,compress=3)
    write(BASE/'selection.json',dict(selected=choices,records=meta,seconds=time.perf_counter()-start,test_metrics_not_used=True))
    write(BASE/'prediction_freeze.json',{p.name:sha(p) for p in [BASE/'models.joblib',BASE/'selection.json']+list(BASE.glob('replicate_*.npz'))});frozen()

def paired(v):
    a=np.asarray(v);mu=float(a.mean());se=float(a.std(ddof=1)/np.sqrt(len(a)));c=float(t.ppf(.975,len(a)-1))*se
    return dict(mean=mu,ci95=[mu-c,mu+c],improved=int((a<0).sum()),n_blocks=len(a))

def evaluate():
    frozen();pf=read(BASE/'prediction_freeze.json');assert all(sha(BASE/p)==h for p,h in pf.items());choices=read(BASE/'selection.json')['selected'];records=[]
    for r in range(20):
        d=np.load(BASE/f'replicate_{r:02d}.npz');p=d['probabilities'];pp=np.concatenate([p,p[choices[r]][None],d['base'][None]])
        for group in ['all','no_persistence','stable_user_effect','drifting_user_effect','eligible']:
            mask=d['split']==2
            if group=='eligible':mask&=d['eligible']
            elif group!='all':mask&=d['scene']==['no_persistence','stable_user_effect','drifting_user_effect'].index(group)
            for i,name in enumerate(NAMES+['selected','frozen_B2']):records.append(dict(rep=r,group=group,method=name,**metrics(pp[i,mask],d['y'][mask],d['q'][mask])))
    summary={};contrasts={}
    for group in ['all','no_persistence','stable_user_effect','drifting_user_effect','eligible']:
        rows=[v for v in records if v['group']==group];summary[group]={}
        for name in NAMES+['selected','frozen_B2']:
            s=[v for v in rows if v['method']==name];summary[group][name]={k:float(np.mean([v[k] for v in s])) for k in ['mse','rmse','mae','brier']}
        contrasts[group]={}
        for a,b in [('C1','C0'),('C2','C0'),('C3','C0'),('selected','C0'),('C3','C2')]:
            aa=[v for v in rows if v['method']==a];bb=[v for v in rows if v['method']==b];contrasts[group][a+'-'+b]={k:paired([x[k]-y[k] for x,y in zip(aa,bb)]) for k in ['mse','brier']}
    write(BASE/'results.json',dict(summary=summary,contrasts=contrasts,records=records,selected_counts={n:choices.count(i) for i,n in enumerate(NAMES)}));frozen();print(summary['all'],flush=True)

if __name__=='__main__':
    import sys
    if sys.argv[1]=='train':train()
    elif sys.argv[1]=='evaluate':evaluate()
