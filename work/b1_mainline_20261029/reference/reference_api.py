"""Limited unknown-reference implementation using declared pre-notice inputs.

Reuses RIDE historical average and feature construction, but excludes historical
endpoint-derived energy/departure. It never imports the real-data adapter.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import sys
import numpy as np
import pandas as pd
import lightgbm as lgb

ORIGINAL = Path(__file__).resolve().parents[2] / 'ride_b1_v02_reproduction_20261029/source/ride_b1'
if str(ORIGINAL) not in sys.path:
    sys.path.insert(0, str(ORIGINAL))
from ride.baseline import masks, cbl_prev, fill_nan_time

def window_average(values, obs):
    """Width-weighted whole task window. Missing task values stay unavailable."""
    _, _, win, _ = masks(obs)
    width = obs.ends - obs.starts
    weights = win * width[None, :]
    expected = obs.meta['W'].to_numpy(float)
    if not np.allclose(weights.sum(1), expected):
        raise ValueError('task boundaries must align with complete metering intervals')
    shape = (obs.n,) + (1,) * (values.ndim-2) + (len(width),)
    w = weights.reshape(shape)
    valid = np.all(np.isfinite(values) | (w == 0), axis=-1)
    ans = np.sum(np.where(w > 0, values, 0) * w, axis=-1) / expected.reshape((obs.n,) + (1,)*(values.ndim-2))
    return np.where(valid, ans, np.nan)

def _mean_pre(series, mask):
    sh = (len(series),) + (1,)*(series.ndim-2) + (series.shape[-1],)
    m = np.broadcast_to(mask.reshape(sh), series.shape)
    count = (m & np.isfinite(series)).sum(-1)
    total = np.where(m & np.isfinite(series), series, 0.).sum(-1)
    return np.divide(total, count, out=np.full(count.shape, np.nan), where=count>0)

def safe_features(obs, kind, cbl, rows=None):
    """Only the first nine, legally available feature concepts from RIDE."""
    pre, adj, _, _ = masks(obs)
    if kind == 'event':
        series = obs.P
        lead = obs.meta['lead'].to_numpy(float)
        hour = obs.meta['hour'].to_numpy(float)
        weekday = obs.meta['weekday'].to_numpy(float)
        temp = obs.meta['temp'].to_numpy(float)
        is_ev = obs.meta['is_ev'].to_numpy(float)
        base = cbl
    else:
        prefix = 'hist' if kind == 'hist' else 'pse'
        data = obs.Hist if kind == 'hist' else obs.Pse
        count = data.shape[1]
        series = data.reshape(-1,data.shape[-1])
        lead = np.repeat(obs.meta['lead'].to_numpy(float), count)
        hour = np.repeat(obs.meta['hour'].to_numpy(float), count)
        weekday = obs.day_meta[prefix+'_weekday'].reshape(-1)
        temp = obs.day_meta[prefix+'_temp'].reshape(-1)
        is_ev = np.repeat(obs.meta['is_ev'].to_numpy(float), count)
        pre, adj = np.repeat(pre,count,0), np.repeat(adj,count,0)
        base = cbl.reshape(series.shape) if kind == 'hist' else np.repeat(cbl,count,0)
    if rows is not None:
        series, pre, adj, base = series[rows], pre[rows], adj[rows], base[rows]
        lead,hour,weekday,temp,is_ev = [x[rows] for x in (lead,hour,weekday,temp,is_ev)]
    prior60 = _mean_pre(series,adj)
    last15 = pre & (obs.starts[None,:] >= -lead[:,None]-15-1e-9)
    prior15 = _mean_pre(series,last15)
    prior15 = np.where(np.isfinite(prior15),prior15,prior60)
    n,k=series.shape
    bcast=lambda a:np.broadcast_to(a[:,None],(n,k))
    mid=np.broadcast_to((obs.starts+obs.ends)[None,:]/2,(n,k))
    return np.stack([mid,bcast(hour),bcast(weekday),bcast(temp),bcast(is_ev),bcast(lead),bcast(prior60),bcast(prior15),base],-1).astype('float32')

class SafeGBDT:
    def __init__(self, seed=0):
        self.seed=seed
    def fit(self,obs,train_users):
        rng=np.random.default_rng(self.seed)
        h=obs.Hist.shape[1]
        hist=fill_nan_time(obs.Hist)
        if h<2:raise ValueError('need at least two historical days')
        loo=(hist.sum(1,keepdims=True)-hist)/(h-1)
        rows=np.flatnonzero(np.repeat(obs.meta['user'].isin(train_users).to_numpy(),h))
        if not len(rows):raise ValueError('no training users')
        features=safe_features(obs,'hist',loo,rows)
        target=obs.Hist.reshape(-1,obs.P.shape[-1])[rows]
        kk=rng.integers(0,obs.P.shape[-1],(len(rows),16))
        xx=np.take_along_axis(features,kk[...,None],1).reshape(-1,9)
        yy=np.take_along_axis(target,kk,1).reshape(-1)
        valid=np.isfinite(yy)
        self.model=lgb.LGBMRegressor(n_estimators=100,num_leaves=15,min_child_samples=35,learning_rate=.05,n_jobs=1,verbosity=-1,random_state=self.seed)
        self.model.fit(xx[valid],yy[valid])
        return self
    def predict(self,obs,kind='event'):
        f=safe_features(obs,kind,cbl_prev(obs))
        y=self.model.predict(f.reshape(-1,9))
        return y.reshape(obs.P.shape if kind=='event' else obs.Pse.shape)

def split_users(users,seed):
    us=np.array(sorted(set(users)))
    if len(us)<40:raise ValueError('need >=40 users for four distinct roles')
    us=np.random.default_rng(seed).permutation(us)
    a,b,c=[int(len(us)*v) for v in (.5,.7,.85)]
    return dict(train=us[:a],selection=us[a:b],calibration=us[b:c],test=us[c:])

@dataclass
class ReferenceResult:
    predictions:dict
    choices:dict
    selection_table:pd.DataFrame
    halfwidth_eta:dict
    calibration_table:pd.DataFrame
    splits:dict

def fit_references(obs,splits,seed=0):
    roles=list(splits)
    for i,a in enumerate(roles):
        for b in roles[i+1:]:
            if set(splits[a]) & set(splits[b]):raise ValueError('user partitions overlap')
    g=SafeGBDT(seed).fit(obs,splits['train'])
    base=cbl_prev(obs)
    predictions={'prev10':(base,np.repeat(base[:,None,:],obs.Pse.shape[1],1)),
                 'gbdt':(g.predict(obs),g.predict(obs,'pseudo'))}
    q=obs.meta['q'].to_numpy(float)
    if not np.all(np.isfinite(q)&(q>0)):raise ValueError('request q must be positive finite')
    typ=obs.meta['is_ev'].to_numpy()
    user=obs.meta['user'].to_numpy()
    selection=[]; choices={}; half={}; calibration=[]
    for t in (0,1):
        pick=(typ==t)&np.isin(user,splits['selection'])
        for name,(_,bp) in predictions.items():
            err=window_average(bp-obs.Pse,obs)/q[:,None]
            risk=float(np.nanmean(np.abs(err[pick]))) if pick.any() else np.inf
            selection.append(dict(resource=int(t),candidate=name,mae_eta=risk,n_users=len(np.unique(user[pick]))))
        scored=[r for r in selection if r['resource']==t and np.isfinite(r['mae_eta'])]
        choices[t]=min(scored,key=lambda x:(x['mae_eta'],x['candidate']))['candidate'] if scored else None
    event=np.full(obs.P.shape,np.nan);pseudo=np.full(obs.Pse.shape,np.nan)
    for t,name in choices.items():
        if name is not None:
            sel=typ==t
            event[sel],pseudo[sel]=predictions[name][0][sel],predictions[name][1][sel]
    predictions['selected']=(event,pseudo)
    for name,(_,bp) in predictions.items():
        err=np.abs(window_average(bp-obs.Pse,obs)/q[:,None])
        hw=np.full(obs.n,np.inf)
        for t in (0,1):
            rows=(typ==t)&np.isin(user,splits['calibration'])
            scores=[]
            for u in np.unique(user[rows]):
                vals=err[rows&(user==u)]
                scores.append(float(np.max(vals)) if np.isfinite(vals).all() else np.inf)
            rank=int(np.ceil((len(scores)+1)*.9))
            quantile=float(np.sort(scores)[rank-1]) if 0<rank<=len(scores) else np.inf
            hw[typ==t]=quantile
            calibration.append(dict(method=name,resource=int(t),n_calibration_users=len(scores),rank=rank,halfwidth_eta=quantile))
        half[name]=hw
    return ReferenceResult(predictions,choices,pd.DataFrame(selection),half,pd.DataFrame(calibration),splits)
