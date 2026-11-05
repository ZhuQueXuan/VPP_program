"""Finite-grid L0 continuous-linear fit; matches the observation operator only.

This enumeration is NOT the CPOP dynamic programming algorithm. Its optimum is
over the explicitly enumerated, full-column-rank, at-most-four-knot family.
"""
from functools import lru_cache
from itertools import combinations
from pathlib import Path
import importlib.util
import numpy as np

GRID = np.array([-8.3,-4.3,-.3,3.7,7.7,11.7,15.7,19.7,23.7,27.7,31.7,35.7,39.7,43.7])

def design(starts, ends, knots, averaging):
    s,e=np.asarray(starts,float),np.asarray(ends,float)
    if s.shape != e.shape or np.any(e<=s) or not np.isfinite(s).all() or not np.isfinite(e).all():
        raise ValueError('require finite increasing interval boundaries')
    mid=(s+e)/2
    cols=[np.ones(len(s)), (mid+15)/60]
    for k in knots:
        if averaging:
            value=(np.maximum(e-k,0)**2-np.maximum(s-k,0)**2)/(2*(e-s)*60)
        else: value=np.maximum(mid-k,0)/60
        cols.append(value)
    return np.column_stack(cols)

@lru_cache(maxsize=8)
def cache(delta, averaging):
    starts=np.arange(-15,45-1e-8,delta); ends=starts+delta
    entries=[]
    for count in range(5):
        for ks in combinations(GRID,count):
            X=design(starts,ends,ks,averaging)
            if X.shape[1]>len(starts): continue
            # Compare precisely the common full-rank family at coarse grids.
            other=design(starts,ends,ks,not averaging)
            _,ro=np.linalg.qr(other,mode='reduced')
            do=np.abs(np.diag(ro))
            if do.min()<=1e-10*max(do.max(),1): continue
            Q,R=np.linalg.qr(X,mode='reduced')
            diag=np.abs(np.diag(R))
            if diag.min()<=1e-10*max(diag.max(),1): continue
            entries.append((ks,Q,R))
    padded=np.zeros((len(entries),6,len(starts)))
    for j,(_,Q,_) in enumerate(entries): padded[j,:Q.shape[1]]=Q.T
    return starts,ends,entries,padded,np.array([len(a[0]) for a in entries])

def fit(y,delta,sigma,averaging=True):
    y=np.asarray(y,float)
    s,e,entries,Q,counts=cache(float(delta),bool(averaging))
    if y.shape!=s.shape or not np.isfinite(y).all() or not np.isfinite(sigma) or sigma<=0:
        raise ValueError('finite complete observations and positive noise required')
    qy=np.einsum('mpn,n->mp',Q,y,optimize=True)
    rss=np.maximum(0,np.dot(y,y)-np.sum(qy*qy,axis=1))
    costs=rss/(sigma*sigma)+2*np.log(len(y))*counts
    j=int(np.argmin(costs))
    ks,q,r=entries[j]
    coeff=np.linalg.solve(r,qy[j,:r.shape[0]])
    # Evaluate through average operator for every method's common target.
    prediction=design(s,e,ks,True)@coeff
    return prediction,dict(knots=list(ks),coefficients=coeff.tolist(),cost=float(costs[j]),
                           rss=float(rss[j]),enumerated_models=len(entries),averaging=bool(averaging))

def original_f1(y,delta,sigma):
    """Original exact constant DP, explicit phase adapter for W=30 minutes."""
    path=Path(__file__).resolve().parents[2]/'b1_fullcycle_features_20261026/methods.py'
    spec=importlib.util.spec_from_file_location('frozen_b1_segment',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    y=np.asarray(y,float);s=np.arange(-15,45-1e-8,delta);result=y.copy()
    dwell=max(1,int(np.ceil(.5/delta-1e-9)))
    phases=np.where(s<0,0,np.where(s<30,1,2))
    count=0
    for phase in range(3):
        ix=np.flatnonzero(phases==phase)
        if len(ix)>=dwell:
            value,segs,_=module.segment(y[ix],3*sigma*sigma*np.log(len(ix)),dwell)
            result[ix]=value;count+=len(segs)-1
    return result,dict(knots_count=count)
