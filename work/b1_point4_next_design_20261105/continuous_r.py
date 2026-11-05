"""Independent implementation of Zhang--Kong--Yang (2025 v3), eqs 17/S3.

No author source copied. Conditional increments only; no absolute-level claim.
Importing this module performs no model fitting.
"""
import numpy as np
from scipy.interpolate import BSpline
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

DOMAIN=(0.,2.4)
REFERENCE=.4
RHO=.05
EIG_REL_TOL=1e-10
NULL_QUERY_TOL=1e-8
KNOTS=np.r_[np.repeat(0.,4),np.linspace(0.,2.4,6)[1:-1],np.repeat(2.4,4)]


def state(x):
    x=np.asarray(x,float)
    if x.ndim!=2 or x.shape[1]!=3 or not np.isfinite(x).all() or np.any(abs(x)>1):
        raise ValueError("Three finite declared pre-offer factors in [-1,1] required.")
    a,b,c=x.T
    return np.column_stack([np.ones(len(x)),a,b,c,a*a,a*b,a*c,b*b,b*c,c*c])


def dose_basis(a):
    a=np.atleast_1d(np.asarray(a,float))
    if np.any((a<0)|(a>2.4)):
        raise ValueError("No dose extrapolation.")
    return BSpline.design_matrix(a,KNOTS,3,extrapolate=False).toarray()


def design(x,a):
    p=state(x)
    b=dose_basis(a)
    if len(p)!=len(b):
        raise ValueError("Matched X/dose rows required.")
    return (p[:,:,None]*b[:,None,:]).reshape(len(p),-1)


def operator_solution(r,q,rhs,rho=RHO):
    """Q-whitened solve. Identity penalty here is exactly rho*Q, never rho*I in phi."""
    if rho<=0:
        raise ValueError("Strictly positive fixed rho required.")
    q=(np.asarray(q)+np.asarray(q).T)/2
    r=(np.asarray(r)+np.asarray(r).T)/2
    eig,vec=np.linalg.eigh(q)
    largest=float(eig[-1])
    if largest<=0 or eig[0]<-1e-10*largest:
        raise ValueError("Invalid function Gram matrix.")
    keep=eig>EIG_REL_TOL*largest
    if not keep.any():
        raise ValueError("Empty identifiable basis subspace.")
    whitening=vec[:,keep]/np.sqrt(eig[keep])[None,:]
    reduced=whitening.T@r@whitening
    reduced=(reduced+reduced.T)/2
    if np.linalg.eigvalsh(reduced)[0]<-1e-8:
        raise ValueError("Residual Gram matrix not positive semidefinite.")
    phi=whitening@np.linalg.solve(reduced+rho*np.eye(keep.sum()),whitening.T@rhs)
    return dict(phi=phi.tolist(),rho=float(rho),q_eigenvalues=eig.tolist(),
                q_kept_basis=vec[:,keep].tolist(),q_rank=int(keep.sum()),
                q_dimension=len(eig),q_relative_cutoff=EIG_REL_TOL,
                null_query_tolerance=NULL_QUERY_TOL,
                numerical_rule="fixed identifiable-Q-subspace; no data-dependent jitter/retuning")


def query_conditional(model,x,amounts):
    x=np.asarray(x,float)
    p=state(x)
    base=dose_basis([model["reference"]])[0]
    b=dose_basis(amounts)
    coef=np.asarray(model["phi"]).reshape(10,8)
    v=(p[:,None,:,None]*(b[None,:,None,:]-base[None,None,None,:])).reshape(len(x),len(b),80)
    kept=np.asarray(model["q_kept_basis"])
    projection=(v@kept)@kept.T
    lost=np.linalg.norm(v-projection,axis=2)/(1+np.linalg.norm(v,axis=2))
    if np.max(lost)>model["null_query_tolerance"]:
        raise ValueError("Requested conditional contrasts leave identifiable Q-subspace.")
    return (1+model["rho"])*np.einsum("nsab,ab->ns",v.reshape(len(x),len(b),10,8),coef)*model["outcome_scale"]


def query_group(model,x,amounts):
    return query_conditional(model,x,amounts).mean(axis=0)


def fit_increment_surface(x,a,y,users,folds,known_uniform=False):
    """Future research call; NOT called during this design round."""
    x,a,y,users,folds=map(np.asarray,(x,a,y,users,folds))
    if len(x)!=len(a) or len(a)!=len(y) or len(y)!=len(users) or len(users)!=len(folds):
        raise ValueError("Input row mismatch.")
    if np.any((a<=0)|(a>=2.4)) or np.any((y<0)|(y>1800)):
        raise ValueError("Declared continuous doses and 30-minute duration required.")
    sx=state(x)
    ba=dose_basis(a)
    psi=design(x,a)
    m=np.empty(len(y))
    moment=np.empty((len(y),8))
    nuisance=[]
    for k in np.unique(folds):
        train,test=folds!=k,folds==k
        if set(users[train]).intersection(users[test]):
            raise ValueError("Whole-user fold leakage.")
        if train.sum()<80 or not test.any():
            raise ValueError("Insufficient training fold.")
        scaler=StandardScaler().fit(sx[train,1:])
        xt,xe=scaler.transform(sx[train,1:]),scaler.transform(sx[test,1:])
        reg_m=Ridge(alpha=.1).fit(xt,y[train]/1800)
        m[test]=reg_m.predict(xe)
        gamma_model=None
        if known_uniform:
            # Exact design integral; used only for declared randomized Uniform(0,2.4).
            moments=BSpline(KNOTS,np.eye(8),3).integrate(0.,2.4)/2.4
            moment[test]=moments
        else:
            gamma_model=Ridge(alpha=.1).fit(xt,ba[train,:7])
            predicted=gamma_model.predict(xe)
            moment[test,:7]=predicted
            moment[test,7]=1-predicted.sum(axis=1)
        nuisance.append(dict(fold=int(k),train_event_index=np.flatnonzero(train).tolist(),
            test_event_index=np.flatnonzero(test).tolist(),
            scaler_mean=scaler.mean_.tolist(),scaler_scale=scaler.scale_.tolist(),
            m_coef=reg_m.coef_.tolist(),m_intercept=float(reg_m.intercept_),
            gamma_coef=None if gamma_model is None else gamma_model.coef_.tolist(),
            gamma_intercept=None if gamma_model is None else gamma_model.intercept_.tolist(),
            gamma_mode="known_uniform_integral" if known_uniform else "train-only basis conditional regression"))
    gamma=(sx[:,:,None]*moment[:,None,:]).reshape(len(x),80)
    z=psi-gamma
    r=z.T@z/len(y)
    q=psi.T@psi/len(y)
    rhs=z.T@(y/1800-m)/len(y)
    result=operator_solution(r,q,rhs)
    result.update(reference=REFERENCE,outcome_scale=1800.,output_kind="conditional_increment_only",
                  absolute_level_available=False,basis_state="poly2_three_covariates_with_intercept",
                  dose_knots=KNOTS.tolist(),dose_degree=3,
                  auxiliary_models=nuisance,fold_by_event=folds.tolist(),
                  m_oof=m.tolist(),dose_moments_oof=moment.tolist(),Gamma_oof=gamma.tolist(),
                  function_Gram=q.tolist(),residual_Gram=r.tolist(),right_hand_side=rhs.tolist(),
                  maximum_partition_error=float(abs(moment.sum(axis=1)-1).max()),
                  negative_moment_entries=int((moment<0).sum()),moments_clipped=False)
    return result
