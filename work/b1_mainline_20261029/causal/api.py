"""Discrete multivalued AIPW with user folds and cluster inference.

The estimator accepts external event outcomes; it never accesses simulation truth.
This adapts standard methods, absorbing RIDE's useful structural separation.
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
from sklearn.preprocessing import PolynomialFeatures, StandardScaler
from sklearn.linear_model import Ridge, LogisticRegression


LEVELS = np.array([0., .4, .8, 1.2, 1.6, 2., 2.4])


def group_folds(groups, n_folds=3, seed=0):
    groups = np.asarray(groups)
    unique, inverse = np.unique(groups, return_inverse=True)
    if len(unique) < n_folds or n_folds < 2:
        raise ValueError('Need at least n_folds independent users and n_folds >= 2')
    rng = np.random.default_rng(seed)
    perm = rng.permutation(len(unique))
    assignment = np.empty(len(unique), int)
    assignment[perm] = np.arange(len(unique)) % n_folds
    return assignment[inverse]


def validate_inputs(X, d, y, groups, levels):
    X, d, y, groups = np.asarray(X, float), np.asarray(d, float), np.asarray(y, float), np.asarray(groups)
    levels = np.asarray(levels, float)
    if X.ndim != 2 or len(X) < 20 or d.ndim != 1 or y.ndim != 1 or groups.ndim != 1:
        raise ValueError('Expected X matrix and event-wise dose, outcome, user vectors')
    if not (len(X) == len(d) == len(y) == len(groups)):
        raise ValueError('Inconsistent event counts')
    if not (np.isfinite(X).all() and np.isfinite(d).all() and np.isfinite(y).all()):
        raise ValueError('Missing/nonfinite values need a separately defined missingness policy')
    if levels.ndim != 1 or len(levels) < 2 or not np.isfinite(levels).all() or not np.all(np.diff(levels) > 0):
        raise ValueError('Levels must be finite, unique and increasing')
    matches = np.isclose(d[:, None], levels[None, :], rtol=0, atol=1e-10)
    if not np.all(matches.sum(1) == 1):
        raise ValueError('Dose outside declared levels')
    return X, matches.argmax(1), y, groups, levels


def aipw_scores(y, d_idx, mu, pi, clip=.01):
    y, mu, pi = np.asarray(y, float), np.asarray(mu, float), np.asarray(pi, float)
    if mu.shape != pi.shape or mu.shape[0] != len(y) or not np.isfinite(mu).all() or not np.isfinite(pi).all():
        raise ValueError('Invalid auxiliary predictions')
    if np.any(pi < 0) or not np.allclose(pi.sum(1), 1, atol=1e-7):
        raise ValueError('Propensities must be probability rows')
    return mu + np.eye(mu.shape[1])[d_idx] * (y[:, None]-mu) / np.maximum(pi, clip)


def crossfit_auxiliary(X, d_idx, y, groups, n_levels, seed=0, known_pi=None, n_folds=3):
    folds = group_folds(groups, n_folds, seed)
    mu = np.full((len(y), n_levels), np.nan)
    pi = np.full_like(mu, np.nan)
    for k in range(n_folds):
        train, test = folds != k, folds == k
        for user in np.unique(groups[test]):
            assert not np.any(groups[train] == user)
        poly = PolynomialFeatures(2, include_bias=False)
        basis_train = poly.fit_transform(X[train])
        basis_test = poly.transform(X[test])
        scaler_y = StandardScaler().fit(basis_train)
        basis_train, basis_test = scaler_y.transform(basis_train), scaler_y.transform(basis_test)
        for j in range(n_levels):
            arm = d_idx[train] == j
            if arm.sum() < 10:
                raise ValueError(f'Insufficient training events in arm {j}')
            model = Ridge(alpha=1.).fit(basis_train[arm], y[train][arm])
            mu[test, j] = model.predict(basis_test)
        if known_pi is None:
            scaler_p = StandardScaler().fit(X[train])
            model_p = LogisticRegression(C=1., max_iter=2000).fit(scaler_p.transform(X[train]), d_idx[train])
            pi[test] = 0.
            pi[np.ix_(test, model_p.classes_.astype(int))] = model_p.predict_proba(scaler_p.transform(X[test]))
        else:
            pi[test] = np.asarray(known_pi)[test]
    return mu, pi, folds


def overlap_diagnostics(X, d_idx, pi, clip=.01, smd_limit=.2):
    n, J = pi.shape
    means, sd = X.mean(0), np.maximum(X.std(0), 1e-9)
    counts, ess_fractions, smds = [], [], []
    for j in range(J):
        arm = d_idx == j
        counts.append(int(arm.sum()))
        if arm.sum() < 10:
            ess_fractions.append(0.)
            smds.append(float('inf'))
            continue
        weights = 1 / np.maximum(pi[arm, j], clip)
        ess_fractions.append(float(weights.sum()**2 / np.sum(weights**2) / arm.sum()))
        smds.append(float(np.max(np.abs(np.average(X[arm], axis=0, weights=weights)-means)/sd)))
    frac = float(np.mean(pi < clip))
    reasons = []
    if frac > .01: reasons.append('insufficient_common_support')
    if min(ess_fractions) < .1: reasons.append('small_effective_sample')
    if max(smds) > smd_limit: reasons.append('weighted_imbalance')
    if min(counts) < 10: reasons.append('small_arm')
    return dict(passed=not reasons, reasons=reasons, counts=counts, min_pi=float(pi.min()),
                fraction_below_clip=frac, min_ess_fraction=min(ess_fractions), max_smd=max(smds),
                smd_limit=smd_limit)


def cluster_inference(scores, groups, n_boot=999, alpha=.05, seed=0):
    """Simultaneous band for contrasts with first arm, not APO-level bands."""
    scores = np.asarray(scores, float)
    contrasts = scores[:, 1:] - scores[:, [0]]
    tau = contrasts.mean(0)
    unique, inverse = np.unique(groups, return_inverse=True)
    G, n = len(unique), len(groups)
    if G < 2: raise ValueError('Need two independent clusters')
    sums = np.zeros((G, contrasts.shape[1]))
    np.add.at(sums, inverse, contrasts-tau)
    sums *= np.sqrt(G/(G-1))
    se = np.sqrt(np.sum(sums**2, axis=0))/n
    rng = np.random.default_rng(seed)
    z = rng.standard_normal((n_boot, G)) @ sums/n
    active = se > 1e-14
    crit = float(np.quantile(np.max(np.abs(z[:, active])/se[active], axis=1), 1-alpha)) if active.any() else 0.
    return dict(tau=np.r_[0., tau], se=np.r_[0., se], critical=crit,
                lower=np.r_[0., tau-crit*se], upper=np.r_[0., tau+crit*se],
                n_clusters=G, n_events=n, n_boot=n_boot, alpha=alpha)


def threshold_candidates(lower, upper, levels=LEVELS, kappa=.1):
    """Invert unrestricted simultaneous rectangular band at observed levels only."""
    lo, hi, levels = np.asarray(lower, float), np.asarray(upper, float), np.asarray(levels, float)
    if len(lo) != len(hi) or len(lo) != len(levels) or np.any(lo > hi):
        raise ValueError('Invalid band')
    positions = [j for j in range(1, len(levels)) if hi[j] >= kappa and np.all(lo[:j] < kappa)]
    return dict(indices=positions, brackets=[[float(levels[j-1]), float(levels[j])] for j in positions],
                not_reached=bool(np.all(lo < kappa)), kappa=kappa, shape_constraint='none')


def fit_discrete(X, d, y, groups, levels=LEVELS, known_pi=None, seed=0, n_boot=999,
                 alpha=.05, kappa=.1, n_folds=3, smd_limit=.2):
    """Public API. X must contain only declared pre-treatment information.

    If identification diagnostics fail, causal output is withheld. The audit field
    is retained for software verification and must not be reported as a conclusion.
    Assumptions such as no hidden confounding cannot be established by this API.
    """
    X, idx, y, groups, levels = validate_inputs(X, d, y, groups, levels)
    if known_pi is not None:
        known_pi = np.asarray(known_pi, float)
        if known_pi.shape != (len(y), len(levels)) or np.any(known_pi <= 0) or not np.allclose(known_pi.sum(1), 1):
            raise ValueError('Invalid known randomization probabilities')
    try:
        mu, pi, folds = crossfit_auxiliary(X, idx, y, groups, len(levels), seed, known_pi, n_folds)
    except ValueError as exc:
        return dict(identified=False, diagnostics=dict(passed=False, reasons=['auxiliary_fit_unavailable'], detail=str(exc)),
                    curve=None, threshold=None, audit=None)
    scores = aipw_scores(y, idx, mu, pi)
    diag = overlap_diagnostics(X, idx, pi, smd_limit=smd_limit)
    band = cluster_inference(scores, groups, n_boot, alpha, seed+73)
    curve = {k: (v.tolist() if isinstance(v, np.ndarray) else v) for k,v in band.items()}
    return dict(identified=diag['passed'], diagnostics=diag, curve=curve if diag['passed'] else None,
                threshold=threshold_candidates(band['lower'], band['upper'], levels, kappa) if diag['passed'] else None,
                audit=dict(mu=mu, pi=pi, folds=folds, scores=scores, raw_band=band, d_idx=idx))
