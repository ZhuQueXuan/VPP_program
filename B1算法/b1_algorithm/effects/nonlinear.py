"""Continuous marginal effects and finite-grid polynomial bias correction.

Zhang--Chen (arXiv:2501.06969), Eq(8), independently implemented.
The mean-curve estimator remains Kennedy DR. Stored models concern the fixed
cohort; queries evaluate the formula directly and do not refit learners.
"""
from dataclasses import asdict
from pathlib import Path
import hashlib
import json
import numpy as np
from scipy.interpolate import BSpline
from scipy.optimize import brentq
from scipy.special import logit
from scipy.stats import norm
from sklearn.linear_model import Ridge
from sklearn.preprocessing import PolynomialFeatures, StandardScaler, SplineTransformer
from .continuous import _config, _design, _local_support, local_linear_weights
from .core import group_folds
from .validation import numeric_array, user_ids


SCHEMA = 'b1.direct-derivative.v1'


def _native(v):
    if isinstance(v, np.ndarray): return v.tolist()
    if isinstance(v, np.generic): return v.item()
    if isinstance(v, dict): return {k: _native(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)): return [_native(x) for x in v]
    return v


def fit_nonlinear_effects(X, treatment, outcome, users, *, dose_domain,
                          known_density=None, config=None, grid=None):
    """Fit independent user-fold nuisance models and retain fixed-cohort state.

    Does not establish identification. known_density is allowed only for a
    declared uniform design; callers supply identification in their study.
    """
    x = numeric_array(X, 'X', 2)
    d = numeric_array(treatment, 'treatment', 1)
    y = numeric_array(outcome, 'outcome', 1)
    groups = user_ids(users)
    cfg = _config(config)
    domain = numeric_array(dose_domain, 'dose_domain', 1)
    if domain.shape != (2,) or domain[0] < 0 or domain[1] <= domain[0]:
        raise ValueError('increasing nonnegative dose domain required')
    lo, hi = domain
    if not (len(x) == len(d) == len(y) == len(groups)) or len(y) < 60 or x.shape[1] < 1:
        raise ValueError('matching nonempty event arrays required')
    if np.any((d <= lo) | (d >= hi)) or len(np.unique(d)) < cfg.min_unique_doses:
        raise ValueError('pure continuous interior dose observations required')
    if len(set(groups)) < max(2*cfg.n_folds, cfg.min_local_users):
        raise ValueError('insufficient independent users')
    h = float(cfg.bandwidth or 1.06*np.std(d)*len(set(groups))**(-.2))
    if not 0 < h <= (hi-lo)/2: raise ValueError('invalid derivative bandwidth')
    known = None if known_density is None else numeric_array(known_density, 'known_density', 1)
    if known is not None and (known.shape != d.shape or not np.allclose(known, 1/(hi-lo))):
        raise ValueError('known density currently supports uniform assignment only')
    folds = group_folds(groups, cfg.n_folds, cfg.seed)
    density = np.empty(len(y)); mu_observed = np.empty(len(y)); models = []
    for fold in np.unique(folds):
        tr, te = folds != fold, folds == fold
        if tr.sum() < 50: raise ValueError('insufficient fold training events')
        poly = PolynomialFeatures(2, include_bias=False)
        xt = poly.fit_transform(x[tr]); xe = poly.transform(x[te])
        scaler = StandardScaler().fit(xt)
        xt, xe = scaler.transform(xt), scaler.transform(xe)
        spline = SplineTransformer(knots=np.linspace(lo, hi, cfg.spline_knots)[:, None],
            degree=3, include_bias=False, extrapolation='error').fit(domain[:, None])
        reg = Ridge(alpha=cfg.ridge_alpha).fit(_design(xt, spline.transform(d[tr, None])), y[tr])
        mu_observed[te] = reg.predict(_design(xe, spline.transform(d[te, None])))
        if known is not None:
            density[te] = known[te]
        else:
            z = logit((d[tr]-lo)/(hi-lo))
            inner = group_folds(groups[tr], 2, cfg.seed+int(fold)+130)
            residual = np.empty(len(z))
            for k in (0, 1):
                dm = Ridge(alpha=cfg.ridge_alpha).fit(xt[inner != k], z[inner != k])
                residual[inner == k] = z[inner == k]-dm.predict(xt[inner == k])
            sd = float(np.sqrt(np.mean(residual**2)))
            if not np.isfinite(sd) or sd < .05:
                raise ValueError('near deterministic assignment; derivative unsupported')
            dm = Ridge(alpha=cfg.ridge_alpha).fit(xt, z)
            u = (d[te]-lo)/(hi-lo)
            density[te] = norm.pdf(logit(u), dm.predict(xe), sd)/((hi-lo)*u*(1-u))
        bs = spline.bsplines_[0]
        models.append(dict(fold=int(fold), indices=np.flatnonzero(te), X=xe,
            coefficient=reg.coef_, intercept=float(reg.intercept_),
            spline_t=bs.t, spline_c=bs.c, spline_k=bs.k))
    if np.any(density <= 0) or not np.isfinite(density).all():
        raise ValueError('nonpositive observed density')
    model = _native(dict(schema=SCHEMA, status='fitted', dose_domain=domain,
        dose=d, outcome=y, users=groups, X=x, fold_by_event=folds,
        observed_density=density, outcome_prediction=mu_observed, models=models,
        bandwidth=h, configuration=asdict(cfg), known_uniform_density=known is not None,
        estimand='population derivative; causal only under supplied identification',
        kernel='Epanechnikov', kappa2=.2, source_equation='Zhang-Chen Eq8',
        reference_process_uncertainty_propagated=False))
    if grid is not None: model['initial_query'] = query_nonlinear_effects(model, grid)
    return model


def _query_values(model, a):
    n = len(model['dose']); m = np.empty(n); beta = np.empty(n)
    for fm in model['models']:
        bs = BSpline(np.asarray(fm['spline_t']), np.asarray(fm['spline_c']), fm['spline_k'])
        b = np.asarray(bs(a))[:-1]
        db = np.asarray(bs.derivative()(a))[:-1]
        x = np.asarray(fm['X']); ids = np.asarray(fm['indices'], int)
        reg = np.asarray(fm['coefficient']); px = x.shape[1]; pb = len(b)
        interaction = reg[px+pb:].reshape(px, pb)
        m[ids] = fm['intercept']+x@reg[:px]+b@reg[px:px+pb]+(x@interaction)@b
        beta[ids] = db@reg[px:px+pb]+(x@interaction)@db
    return m, beta


def direct_derivative_scores(dose, outcome, mean, derivative, density, amount, bandwidth):
    """Eq(8), no density clipping or self-normalization."""
    z = (np.asarray(dose)-amount)/bandwidth
    kernel = .75*(1-z*z)*(np.abs(z) <= 1)
    return np.asarray(derivative)+z*kernel/(bandwidth**2*.2*np.asarray(density))*(
        np.asarray(outcome)-mean-(np.asarray(dose)-amount)*derivative)


def query_nonlinear_effects(model, grid, *, event_mask=None, include_scores=False):
    if model.get('schema') != SCHEMA: raise ValueError('direct derivative model required')
    a = numeric_array(grid, 'grid', 1); lo, hi = model['dose_domain']
    h = model['bandwidth']; d = np.asarray(model['dose']); y = np.asarray(model['outcome'])
    pdf = np.asarray(model['observed_density']); users = np.asarray(model['users'])
    mask = np.ones(len(d), bool) if event_mask is None else np.asarray(event_mask)
    if mask.shape != d.shape or mask.dtype != bool or not mask.any():
        raise ValueError('nonempty Boolean event mask required')
    if not len(a) or len(a) > 301 or np.any(np.diff(a) <= 0) or np.any((a < lo) | (a > hi)):
        raise ValueError('increasing in-domain amounts required')
    cfg = _config(model['configuration']); rows=[]; scores=[]; failed=[]
    for amount in a:
        local = mask & (abs(d-amount) <= h)
        z = (d[mask]-amount)/h; k = .75*(1-z*z)*(abs(z) <= 1)
        weight = k/pdf[mask]; mass = weight.sum()
        ess = float(mass*mass/(weight@weight)) if weight@weight > 0 else 0.
        reason = []
        if amount-h < lo or amount+h > hi: reason.append('compact_kernel_boundary')
        if local.sum() < cfg.min_local_events: reason.append('local_events')
        if len(set(users[local])) < cfg.min_local_users: reason.append('local_users')
        if ess < cfg.min_local_ess: reason.append('local_ess')
        rows.append(dict(amount=float(amount), local_events=int(local.sum()),
            local_users=len(set(users[local])), ess=ess, supported=not reason, reasons=reason))
        if reason: failed.append(float(amount))
        m, beta = _query_values(model, amount)
        scores.append(direct_derivative_scores(d, y, m, beta, pdf, amount, h)[mask])
    result = dict(schema='b1.direct-derivative-query.v1', status='unsupported' if failed else 'ok',
        incentive_values=a.tolist(), bandwidth=h, diagnostics=rows,
        unsupported_amounts=failed, estimates=None, refitted=False,
        events=int(mask.sum()), users=len(set(users[mask])),
        estimand='fixed-cohort mean derivative; subgroup mask fixed across amounts',
        uncertainty_scope='conditional_user_score_variation; smoothing and nuisance uncertainty not propagated')
    if failed: return result
    q = np.asarray(scores); estimate=q.mean(1)
    unique, inverse=np.unique(users[mask], return_inverse=True); g=len(unique)
    sums=np.zeros((g,len(a)))
    np.add.at(sums,inverse,(q-estimate[:,None]).T/len(inverse))
    if g > 1: sums *= np.sqrt(g/(g-1))
    se=np.sqrt((sums*sums).sum(0))
    result.update(estimates=estimate.tolist(), standard_errors=se.tolist(),
                  inference_unit='original_user', signs=np.sign(estimate).astype(int).tolist())
    if include_scores: result['scores_by_query']=q.tolist()
    return result


def save_nonlinear_model(model, path):
    payload=json.dumps(model,sort_keys=True,separators=(',',':'),allow_nan=False)
    envelope=dict(payload=model,sha256=hashlib.sha256(payload.encode()).hexdigest())
    with Path(path).open('x',encoding='utf-8') as stream: json.dump(envelope,stream,ensure_ascii=False)


def load_nonlinear_model(path):
    envelope=json.loads(Path(path).read_text(encoding='utf-8'))
    payload=json.dumps(envelope['payload'],sort_keys=True,separators=(',',':'),allow_nan=False)
    if hashlib.sha256(payload.encode()).hexdigest()!=envelope['sha256']:
        raise ValueError('model checksum mismatch')
    if envelope['payload'].get('schema')!=SCHEMA: raise ValueError('model schema mismatch')
    return envelope['payload']


def bias_corrected_curve_summary(frozen_model, grid, *, target_contrast=120., pilot_bandwidth=None):
    """Finite-design local-linear curvature correction and conditional grid band.

    Polynomial bias correction is inspired by debiased local-polynomial methods;
    this is not a claim to reproduce the full Takatsu--Westling inference theory.
    """
    from .frozen import _payload, _band
    p,x,d,xi,stabilized,residual,users,cfg = _payload(frozen_model)
    grid=numeric_array(grid,'grid',1); lo,hi=p['dose_domain']; ref=p['reference_dose']
    if not len(grid) or np.any(np.diff(grid)<=0) or np.any((grid<lo)|(grid>hi)):
        raise ValueError('increasing in-domain grid required')
    h=p['bandwidth']; b=h if pilot_bandwidth is None else float(pilot_bandwidth)
    if not b>0 or target_contrast<=0: raise ValueError('positive bandwidth and target required')
    points=np.r_[ref,grid[~np.isclose(grid,ref,atol=1e-12,rtol=0)]]
    mapping=np.array([np.argmin(abs(points-a)) for a in grid])
    diagnostics,failed=_local_support(x,d,users,points,h,stabilized,cfg)
    if failed: return dict(status='unsupported',unsupported_amounts=failed,diagnostics=diagnostics)

    def weights(amounts):
        ll=local_linear_weights(d,np.asarray(amounts),h); corrected=[]
        for amount,line in zip(amounts,ll):
            z=(d-amount)/b; k=np.exp(-z*z/2); design=np.column_stack([z**j for j in range(4)])
            gram=design.T@(k[:,None]*design)
            second=np.linalg.solve(gram,(design.T*k))[2]
            # LL quadratic moment cancels exactly on this finite design.
            corrected.append(line-(line@((d-amount)**2))/b**2*second)
        return np.asarray(corrected)

    W=weights(points); means=W@xi; contrast=W-W[[0]]
    band=_band(contrast,xi,residual,users,cfg)
    for key in ['estimate','standard_errors','lower','upper']:
        band[key]=np.asarray(band[key])[mapping].tolist()
    c=(means-means[0])[mapping]; lower=np.asarray(band['lower']); upper=np.asarray(band['upper'])
    crossings=[]
    def f(a): return float(weights([a])[0]@xi-means[0]-target_contrast)
    for left,right,yl,yr in zip(grid[:-1],grid[1:],c[:-1],c[1:]):
        if yl < target_contrast <= yr:
            crossings.append(float(brentq(f,left,right,xtol=1e-9)))
    candidate=[]
    for j in range(len(grid)-1):
        if min(lower[j],lower[j+1])<=target_contrast<=max(upper[j],upper[j+1]):
            candidate.append([float(grid[j]),float(grid[j+1])])
    return dict(status='ok',method='finite_design_local_cubic_curvature_correction',
        incentive_values=grid.tolist(),mean_outcomes=means[mapping].tolist(),contrasts=c.tolist(),
        reference_incentive=ref,bandwidth=h,pilot_bandwidth=b,band=band,
        target_contrast=float(target_contrast),upward_crossings=crossings,
        first_crossing=float(grid[0]) if c[0]>=target_contrast else (crossings[0] if crossings else None),
        target_candidate_cells=candidate,not_reached_possible=bool(np.all(lower<target_contrast)),
        finite_grid_only=True,smoothing_curvature_bias_corrected=True,
        full_nuisance_and_process_uncertainty_propagated=False,
        full_causal_coverage_validated=False,exact_Takatsu_Westling_reproduction=False,
        diagnostics=diagnostics)


debiased_curve_summary = bias_corrected_curve_summary
