"""Unchanged fixed B0/OR10/S contracts, with serializable query states.

Fit hooks only retain the parameters of original _crossfit fits; no extra fit.
"""
from contextlib import contextmanager
import importlib.util
from pathlib import Path
import numpy as np
from scipy.special import logit
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler, SplineTransformer
from b1_algorithm.effects.continuous import (
    ContinuousEffectConfig, _crossfit, _design, _local_support, local_linear_weights)
from b1_algorithm.effects.core import group_folds
from continuous_r import state

ROOT=Path(__file__).resolve().parents[2]


def spline_state(spline):
    b=spline.bsplines_[0]
    return dict(t=b.t.tolist(),c=b.c.tolist(),k=b.k,drop_last=True)


@contextmanager
def capture_parameters():
    fits,scales=[],[]
    ridge_fit,scaler_fit=Ridge.fit,StandardScaler.fit
    def capture_ridge(obj,x,y,*args,**kw):
        result=ridge_fit(obj,x,y,*args,**kw)
        fits.append(dict(alpha=float(obj.alpha),coef=np.asarray(obj.coef_).tolist(),
                         intercept=np.asarray(obj.intercept_).tolist(),
                         rows=len(x),features=np.shape(x)[1]))
        return result
    def capture_scale(obj,x,*args,**kw):
        result=scaler_fit(obj,x,*args,**kw)
        scales.append(dict(mean=obj.mean_.tolist(),scale=obj.scale_.tolist(),rows=len(x)))
        return result
    Ridge.fit,StandardScaler.fit=capture_ridge,capture_scale
    try:
        yield fits,scales
    finally:
        Ridge.fit,StandardScaler.fit=ridge_fit,scaler_fit


def finish(x,a,u,xi,w,cfg,grid):
    h=1.06*float(np.std(a))*len(set(u))**(-.2)
    diagnostic,failed=_local_support(x,a,u,grid,h,w,cfg)
    out=dict(status="unsupported" if failed else "ok",bandwidth=h,xi=xi,weights=w,
             support=diagnostic,failed_doses=failed)
    if not failed:
        level=local_linear_weights(a,grid,h)@xi
        out.update(level=level,contrast=level-level[0])
    return out


def fit_b0(d,seed,grid):
    x,a,y,u=[d[k] for k in ("X","dose","outcome","users")]
    masks=[np.ones(len(a),bool),x[:,0]<0,x[:,0]>=0]
    cfg=ContinuousEffectConfig(seed=seed,n_boot=99)
    populations=[]
    for mask in masks:
        idx=np.flatnonzero(mask)
        xu,au,yu,uu=x[mask],a[mask],y[mask],u[mask]
        known=None if d["known_density"] is None else d["known_density"][mask]
        try:
            with capture_parameters() as (fits,scales):
                xi,w,folds,models,mu,pdf=_crossfit(xu,au,yu,uu,cfg,[0.,2.4],known)
            out=finish(xu,au,uu,xi,w,cfg,grid)
            nuisance=[]
            stride=1 if known is not None else 4
            assert len(fits)==3*stride and len(scales)==3
            for pos,k in enumerate(np.unique(folds)):
                train,test=folds!=k,folds==k
                pack=fits[pos*stride:(pos+1)*stride]
                inner=group_folds(uu[train],2,seed+int(k)+130)
                scale=scales[pos]
                sd=None
                if known is None:
                    xt=(state(xu[train])[:,1:]-np.array(scale["mean"]))/np.array(scale["scale"])
                    z=logit(au[train]/2.4)
                    residual=np.empty(len(z))
                    for q in (0,1):
                        reg=pack[1+q]
                        residual[inner==q]=z[inner==q]-(
                            xt[inner==q]@np.array(reg["coef"])+reg["intercept"])
                    sd=float(np.sqrt(np.mean(residual**2)))
                nuisance.append(dict(fold=int(k),train_event_index=idx[train],
                    test_event_index=idx[test],scaler=scale,outcome_model=pack[0],
                    spline=spline_state(models[pos][3]),mean_state=models[pos][2],
                    density_inner_models=None if known is not None else pack[1:3],
                    density_final_model=None if known is not None else pack[3],
                    density_inner_fold=inner,density_sd=sd,known_uniform=known is not None))
            out.update(event_index=idx,folds=folds,mu_observed=mu,conditional_density=pdf,
                       marginal_mu=xi-(yu-mu)*w,marginal_density=w*pdf,
                       auxiliary_models=nuisance,actual_ridge_fits=len(fits))
        except (ValueError,np.linalg.LinAlgError) as exc:
            out=dict(status="unsupported",reason=str(exc),event_index=idx)
        populations.append(out)
    return populations


def fit_or(d,support):
    x,a,y=[d[k] for k in ("X","dose","outcome")]
    raw=state(x)[:,1:]
    scaler=StandardScaler().fit(raw)
    xs=scaler.transform(raw)
    spline=SplineTransformer(knots=np.linspace(0,2.4,6)[:,None],degree=3,
        include_bias=False,extrapolation="error").fit(np.array([[0.],[2.4]]))
    reg=Ridge(alpha=10.).fit(_design(xs,spline.transform(a[:,None])),y)
    return dict(coef=reg.coef_,intercept=float(reg.intercept_),alpha=10.,
                scaler_mean=scaler.mean_,scaler_scale=scaler.scale_,
                spline=spline_state(spline),group_supported=support)


def query_or(model,x,amounts):
    from scipy.interpolate import BSpline
    sp=model["spline"]
    spline=BSpline(sp["t"],sp["c"],sp["k"],extrapolate=False)
    basis=spline(np.asarray(amounts))[:,:-1]
    xs=(state(x)[:,1:]-np.asarray(model["scaler_mean"]))/np.asarray(model["scaler_scale"])
    averages=np.broadcast_to(xs.mean(0),(len(basis),xs.shape[1]))
    return _design(averages,basis)@np.asarray(model["coef"])+model["intercept"]


def retained_smoothers():
    path=ROOT/"work/b1_curve_spline_pilot_20261103/smoothers.py"
    spec=importlib.util.spec_from_file_location("r_pilot_retained_smoothing",path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
