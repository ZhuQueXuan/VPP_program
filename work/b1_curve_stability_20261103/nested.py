"""One nested, user-held-out convex combination of two fixed smoothers.

Validation uses observed-dose pseudo-outcome level risk, not the primary
contrast-curve error. No simulated truth or old confirmation result is read.
"""

from dataclasses import asdict
from pathlib import Path
import hashlib
import importlib.util
import json

import numpy as np
from scipy.special import logit
from scipy.stats import norm
from sklearn.linear_model import Ridge
from sklearn.preprocessing import PolynomialFeatures, StandardScaler, SplineTransformer

from b1_algorithm.effects import continuous as C
from b1_algorithm.effects.core import group_folds
from b1_algorithm.effects.validation import numeric_array, user_ids


_path = Path(__file__).resolve().parent.parent / 'b1_curve_spline_pilot_20261103' / 'smoothers.py'
_spec = importlib.util.spec_from_file_location('_retained_spline_smoothers', _path)
_smoothers = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_smoothers)
spline_state = _smoothers.spline_state
spline_query = _smoothers.spline_query


def _user_hash(values):
    raw = json.dumps(sorted(set(map(str, values))), ensure_ascii=False, separators=(',', ':'))
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def _finite_list(values):
    return [float(v) if np.isfinite(v) else None for v in values]


def external_pseudo(X_train, d_train, y_train, users_train,
                    X_valid, d_valid, y_valid, users_valid, *, config,
                    dose_domain=(0.0, 2.4), known_density_train=None,
                    known_density_valid=None, outer_fold=0):
    """Fit exactly the official nuisance equations on T, then construct xi_V.

    The validation outcomes occur only in ``(y_valid - mu_valid) * weight``.
    The marginal mean/density always average over training covariates.
    ``outer_fold`` determines the official GPS residual-fold seed.
    """
    cfg = C._config(config)
    xt0 = numeric_array(X_train, 'X_train', 2)
    xv0 = numeric_array(X_valid, 'X_valid', 2)
    dt = numeric_array(d_train, 'd_train', 1)
    dv = numeric_array(d_valid, 'd_valid', 1)
    yt = numeric_array(y_train, 'y_train', 1)
    yv = numeric_array(y_valid, 'y_valid', 1)
    ut = user_ids(users_train)
    uv = user_ids(users_valid)
    if len(xt0) != len(dt) or len(dt) != len(yt) or len(yt) != len(ut):
        raise ValueError('Training arrays must contain matching event rows')
    if len(xv0) != len(dv) or len(dv) != len(yv) or len(yv) != len(uv) or xt0.shape[1] != xv0.shape[1]:
        raise ValueError('Validation arrays must match and use the training features')
    if set(ut) & set(uv):
        raise ValueError('Training and validation must contain disjoint complete users')
    if len(yt) < 50 or len(np.unique(dt)) < cfg.min_unique_doses:
        raise ValueError('Insufficient training events or unique compensation amounts')
    lo, hi = map(float, dose_domain)
    if np.any((dt <= lo) | (dt >= hi)) or np.any((dv <= lo) | (dv >= hi)):
        raise ValueError('Observed amounts must be inside the declared continuous domain')

    poly = PolynomialFeatures(2, include_bias=False)
    xt = poly.fit_transform(xt0)
    xv = poly.transform(xv0)
    scaler = StandardScaler().fit(xt)
    xt = scaler.transform(xt)
    xv = scaler.transform(xv)
    knots = np.linspace(lo, hi, cfg.spline_knots)[:, None]
    spline = SplineTransformer(knots=knots, degree=3, include_bias=False,
                               extrapolation='error').fit(np.array([[lo], [hi]]))
    bt = spline.transform(dt[:, None])
    bv = spline.transform(dv[:, None])
    reg = Ridge(alpha=cfg.ridge_alpha).fit(C._design(xt, bt), yt)
    mu = reg.predict(C._design(xv, bv))
    marginal_mu = C._marginal_prediction(reg, xt.mean(0), spline, dv)
    sd = None
    inner = None
    if known_density_train is not None or known_density_valid is not None:
        if known_density_train is None or known_density_valid is None:
            raise ValueError('Known randomized density must be supplied for both T and V')
        kt = numeric_array(known_density_train, 'known_density_train', 1)
        kv = numeric_array(known_density_valid, 'known_density_valid', 1)
        if (kt.shape != dt.shape or kv.shape != dv.shape
                or not np.allclose(kt, 1.0 / (hi - lo), rtol=1e-8, atol=1e-10)
                or not np.allclose(kv, 1.0 / (hi - lo), rtol=1e-8, atol=1e-10)):
            raise ValueError('Only the declared known uniform randomized design is supported')
        conditional = kv.copy()
        marginal_density = kv.copy()
    else:
        z = logit((dt - lo) / (hi - lo))
        inner = group_folds(ut, 2, cfg.seed + int(outer_fold) + 130)
        residual = np.empty(len(z))
        for k in (0, 1):
            dm_inner = Ridge(alpha=cfg.ridge_alpha).fit(xt[inner != k], z[inner != k])
            residual[inner == k] = z[inner == k] - dm_inner.predict(xt[inner == k])
        sd = float(np.sqrt(np.mean(residual ** 2)))
        if not np.isfinite(sd) or sd < 0.05:
            raise ValueError('Assignment nearly deterministic; conditional density unsupported')
        dm = Ridge(alpha=cfg.ridge_alpha).fit(xt, z)
        u = (dv - lo) / (hi - lo)
        conditional = norm.pdf(logit(u), dm.predict(xv), sd) / ((hi - lo) * u * (1.0 - u))
        marginal_density = C._marginal_logit_density(dv, dm.predict(xt), sd, lo, hi)
    if not np.isfinite(conditional).all() or np.any(conditional <= 0):
        raise ValueError('Nonpositive or nonfinite external assignment density')
    weights = marginal_density / conditional
    if not np.isfinite(weights).all() or np.max(weights) > cfg.max_stabilized_weight:
        raise ValueError('Extreme external stabilized density weights; no capping or trimming')
    xi = C._dr_pseudo_outcome(yv, mu, marginal_mu, conditional, marginal_density)
    if not np.isfinite(xi).all():
        raise ValueError('Nonfinite external pseudo-outcome')
    return dict(
        pseudo_outcome=xi.tolist(), dose=dv.tolist(), stabilized_weight=weights.tolist(),
        outcome_prediction=mu.tolist(), marginal_outcome_prediction=marginal_mu.tolist(),
        observed_dose_density=conditional.tolist(), marginal_dose_density=marginal_density.tolist(),
        gps_residual_sd=sd,
        gps_inner_user_fold=None if inner is None else inner.tolist(),
        gps_inner_seed=cfg.seed + int(outer_fold) + 130,
        outer_fold=int(outer_fold), training_users=sorted(set(ut)), validation_users=sorted(set(uv)),
        training_users_sha256=_user_hash(ut), validation_users_sha256=_user_hash(uv),
        training_events=len(yt), validation_events=len(yv), validation_outcomes_used_for_fit=False,
    )


def select_nested_alpha(X, dose, outcome, users, *, config, known_density=None,
                        dose_domain=(0.0, 2.4), lambda_mean=1e-4,
                        ll_multiplier=2.0, validation_domain=(0.3, 2.1),
                        min_valid_events=20, min_valid_users=15):
    """Select one convex weight with three complete-user validation folds.

    An unsuccessful fold triggers the predeclared all-S fallback (alpha=1).
    Every fold is attempted and retained in the audit. This function returns
    only the weight/audit; it does not refit the full-cohort pseudo-outcomes.
    """
    cfg = C._config(config)
    if cfg.n_folds != 3:
        raise ValueError('This single candidate fixes both outer and inner cross-fitting at three user folds')
    if tuple(map(float, dose_domain)) != (0.0, 2.4):
        raise ValueError('This candidate retains the previous 0..2.4 compensation scope')
    if float(lambda_mean) != 1e-4 or float(ll_multiplier) != 2.0:
        raise ValueError('Both component policies are fixed before this nested comparison')
    x = numeric_array(X, 'X', 2)
    d = numeric_array(dose, 'dose', 1)
    y = numeric_array(outcome, 'outcome', 1)
    u = user_ids(users)
    original_users = np.asarray(users, dtype=object)
    if not (len(x) == len(d) == len(y) == len(u)):
        raise ValueError('Matching event rows are required')
    kd = None if known_density is None else numeric_array(known_density, 'known_density', 1)
    if kd is not None and kd.shape != d.shape:
        raise ValueError('Known density must match the event rows')
    folds = group_folds(u, 3, cfg.seed)
    n = len(d)
    pred_s = np.full(n, np.nan)
    pred_l = np.full(n, np.nan)
    xi_v = np.full(n, np.nan)
    weights_v = np.full(n, np.nan)
    mu_v = np.full(n, np.nan)
    density_v = np.full(n, np.nan)
    valid_all = np.zeros(n, dtype=bool)
    audit_folds = []
    failures = []
    for fold in range(3):
        v = folds == fold
        t = ~v
        t_index = np.flatnonzero(t)
        v_index = np.flatnonzero(v)
        row = dict(fold=fold, train_indices=t_index.tolist(), validation_indices=v_index.tolist(),
                   training_users=sorted(set(u[t])), validation_users=sorted(set(u[v])),
                   training_users_sha256=_user_hash(u[t]), validation_users_sha256=_user_hash(u[v]),
                   failures=[])
        train_result = None
        external = None
        try:
            train_result = C._crossfit(x[t], d[t], y[t], u[t], cfg,
                                      np.asarray(dose_domain), None if kd is None else kd[t])
            xi_t, w_t, inner_fold, _, mu_t, density_t = train_result
            row['training_crossfit'] = dict(
                pseudo_outcome=xi_t.tolist(), stabilized_weight=w_t.tolist(),
                fold_by_training_event=inner_fold.tolist(),
                outcome_prediction=mu_t.tolist(), observed_dose_density=density_t.tolist(),
                excluded_validation_users=True)
        except (ValueError, TypeError, np.linalg.LinAlgError) as exc:
            row['failures'].append('training_crossfit: ' + str(exc))
        try:
            external = external_pseudo(
                x[t], d[t], y[t], original_users[t], x[v], d[v], y[v], original_users[v], config=cfg,
                dose_domain=dose_domain, known_density_train=None if kd is None else kd[t],
                known_density_valid=None if kd is None else kd[v], outer_fold=fold)
            row['external'] = external
            xi_v[v] = external['pseudo_outcome']
            weights_v[v] = external['stabilized_weight']
            mu_v[v] = external['outcome_prediction']
            density_v[v] = external['observed_dose_density']
        except (ValueError, TypeError, np.linalg.LinAlgError) as exc:
            row['failures'].append('external_pseudo: ' + str(exc))
        if train_result is not None and external is not None:
            try:
                h = 1.06 * float(np.std(d[t])) * len(set(u[t])) ** (-0.2)
                if not 0 < h * ll_multiplier <= (dose_domain[1] - dose_domain[0]) / 2.0:
                    raise ValueError('Invalid retained component bandwidth')
                state = spline_state(d[t], xi_t, lambda_mean)
                within_observed = (d[v] >= np.min(d[t])) & (d[v] <= np.max(d[t]))
                pred_s[v_index[within_observed]] = spline_query(state, d[v][within_observed])
                pred_l[v] = C.local_linear_weights(d[t], d[v], h * ll_multiplier) @ xi_t
                candidate = (within_observed & (d[v] >= validation_domain[0])
                             & (d[v] <= validation_domain[1]))
                candidate_index = np.flatnonzero(candidate)
                points = d[v][candidate]
                diag_s, fail_s = C._local_support(x[t], d[t], u[t], points, h, w_t, cfg)
                diag_l, fail_l = C._local_support(x[t], d[t], u[t], points, h * ll_multiplier, w_t, cfg)
                valid = np.zeros(len(v_index), dtype=bool)
                passed = np.array([a not in fail_s and a not in fail_l for a in points], dtype=bool)
                valid[candidate_index[passed]] = True
                valid_all[v_index] = valid
                row.update(training_bandwidth=h, ll_bandwidth=h * ll_multiplier,
                           valid_validation_events=int(valid.sum()),
                           valid_validation_users=len(set(u[v][valid])),
                           validation_valid_mask=valid.tolist(),
                           component_support=dict(spline=diag_s, LL2=diag_l),
                           validation_pred_spline=_finite_list(pred_s[v]),
                           validation_pred_LL2=_finite_list(pred_l[v]))
                if valid.sum() < min_valid_events or len(set(u[v][valid])) < min_valid_users:
                    row['failures'].append('insufficient_common_validation_support')
            except (ValueError, TypeError, np.linalg.LinAlgError) as exc:
                row['failures'].append('training_smoothers_or_support: ' + str(exc))
        if row['failures']:
            failures.extend([dict(fold=fold, reason=reason) for reason in row['failures']])
        audit_folds.append(row)

    alpha = 1.0
    alpha_unconstrained = None
    losses = None
    denominator = None
    if not failures:
        delta = pred_s[valid_all] - pred_l[valid_all]
        residual = xi_v[valid_all] - pred_l[valid_all]
        denominator = float(delta @ delta)
        if denominator > 1e-20:
            alpha_unconstrained = float((delta @ residual) / denominator)
            alpha = float(np.clip(alpha_unconstrained, 0.0, 1.0))
        else:
            failures.append(dict(fold=None, reason='identical_component_predictions_keep_retained_spline'))
        mixture = alpha * pred_s[valid_all] + (1.0 - alpha) * pred_l[valid_all]
        losses = dict(spline=float(np.mean((xi_v[valid_all] - pred_s[valid_all]) ** 2)),
                      LL2=float(np.mean((xi_v[valid_all] - pred_l[valid_all]) ** 2)),
                      selected=float(np.mean((xi_v[valid_all] - mixture) ** 2)))
    return dict(
        schema='b1.nested-smoother-weight.v1',
        status='fallback_retained_spline' if failures else 'selected', alpha=alpha,
        raw_alpha_S=alpha,
        alpha_unconstrained=alpha_unconstrained, quadratic_denominator=denominator,
        objective='equal-event observed-dose external-pseudo-outcome level squared risk on common validation support',
        objective_is_primary_contrast_risk=False, fallback_policy='alpha=1 retained spline if any fold fails',
        failures=failures, configuration=asdict(cfg), lambda_mean=lambda_mean,
        ll_multiplier=ll_multiplier, validation_domain=list(validation_domain),
        min_valid_events=min_valid_events, min_valid_users=min_valid_users,
        outer_fold_by_event=folds.tolist(), folds=audit_folds,
        heldout=dict(dose=d.tolist(), users=u.tolist(), pseudo_outcome=_finite_list(xi_v),
                     stabilized_weight=_finite_list(weights_v),
                     outcome_prediction=_finite_list(mu_v), observed_dose_density=_finite_list(density_v),
                     pred_spline=_finite_list(pred_s), pred_LL2=_finite_list(pred_l),
                     common_valid_mask=valid_all.tolist()),
        validation_losses=losses, full_cohort_nuisance_refit=False,
        training_crossfit_calls=3, external_nuisance_fit_calls=3,
    )
