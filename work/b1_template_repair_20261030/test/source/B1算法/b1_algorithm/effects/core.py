"""Standard multivalued AIPW arithmetic and grouped nuisance fitting.

No project work-directory imports. The mathematical estimator is established
literature, not a new causal estimator. See SOURCES.json for provenance.
"""
from __future__ import annotations
import warnings
import numpy as np
from sklearn.preprocessing import PolynomialFeatures, StandardScaler
from sklearn.linear_model import Ridge, LogisticRegression
from sklearn.exceptions import ConvergenceWarning


class AuxiliaryFitError(RuntimeError):
    pass


def _ordered_groups(groups):
    # Preserve numeric-ID ordering used by the validated research implementation,
    # while keeping integer 1 and string "1" distinct under the formal contract.
    def order(value):
        if isinstance(value, str) and value.startswith('integer:'):
            return 0, int(value[8:])
        if isinstance(value, str) and value.startswith('string:'):
            return 1, value[7:]
        if isinstance(value, (int, np.integer)):
            return 0, int(value)
        return 1, str(value)
    unique = sorted(set(groups), key=order)
    lookup = {value:i for i,value in enumerate(unique)}
    return unique, np.array([lookup[value] for value in groups], dtype=int)


def group_folds(groups, n_folds, seed):
    unique, inverse = _ordered_groups(groups)
    perm = np.random.default_rng(seed).permutation(len(unique))
    assignment = np.empty(len(unique), int)
    assignment[perm] = np.arange(len(unique)) % n_folds
    return assignment[inverse]


def training_support(d_idx, folds, n_levels, minimum):
    counts = []
    reasons = []
    for fold in np.unique(folds):
        row = [int(np.sum((folds != fold) & (d_idx == j))) for j in range(n_levels)]
        counts.append(dict(fold=int(fold), training_arm_counts=row))
        for arm, count in enumerate(row):
            if count < minimum:
                reasons.append(dict(code='sparse_training_arm', field='treatment',
                                    detail=f'fold={int(fold)}, arm_index={arm}: {count} training events, need {minimum}.'))
    return counts, reasons


def crossfit_auxiliary(X, idx, y, folds, n_levels, config, known_pi=None):
    mu = np.empty((len(y), n_levels))
    pi = np.empty_like(mu)
    for k in np.unique(folds):
        train, test = folds != k, folds == k
        poly = PolynomialFeatures(config.outcome_degree, include_bias=False)
        train_basis = poly.fit_transform(X[train])
        test_basis = poly.transform(X[test])
        scaler_y = StandardScaler().fit(train_basis)
        train_basis, test_basis = scaler_y.transform(train_basis), scaler_y.transform(test_basis)
        for j in range(n_levels):
            arm = idx[train] == j
            model = Ridge(alpha=config.ridge_alpha).fit(train_basis[arm], y[train][arm])
            mu[test, j] = model.predict(test_basis)
        if known_pi is not None:
            pi[test] = known_pi[test]
        else:
            scaler = StandardScaler().fit(X[train])
            model_p = LogisticRegression(C=config.propensity_C, max_iter=2000)
            with warnings.catch_warnings(record=True) as captured:
                warnings.simplefilter('always', ConvergenceWarning)
                model_p.fit(scaler.transform(X[train]), idx[train])
            if any(issubclass(w.category, ConvergenceWarning) for w in captured):
                raise AuxiliaryFitError(f'Propensity model did not converge in fold {int(k)}; no automatic retry/tuning.')
            pi[test] = 0.
            pi[np.ix_(test, model_p.classes_.astype(int))] = model_p.predict_proba(scaler.transform(X[test]))
    if not (np.isfinite(mu).all() and np.isfinite(pi).all()):
        raise AuxiliaryFitError('Nonfinite auxiliary predictions.')
    return mu, pi


def aipw_scores(y, idx, mu, pi, clip=.01):
    return mu + np.eye(mu.shape[1])[idx]*(y[:, None]-mu)/np.maximum(pi, clip)


def support_screen(X, idx, pi, config):
    counts = []
    fractions = []
    smds = []
    mean, sd = X.mean(0), np.maximum(X.std(0), 1e-9)
    for j in range(pi.shape[1]):
        arm = idx == j
        counts.append(int(arm.sum()))
        if arm.sum() == 0:
            fractions.append(0.)
            smds.append(None)
            continue
        w = 1/np.maximum(pi[arm, j], config.propensity_clip)
        fractions.append(float(w.sum()**2/(w@w)/arm.sum()))
        smds.append(float(np.max(abs(np.average(X[arm], axis=0, weights=w)-mean)/sd)))
    below = float(np.mean(pi < config.propensity_clip))
    reasons = []
    if min(counts) < config.min_events_per_arm:
        reasons.append(dict(code='small_observed_arm', field='treatment', detail=f'Arm counts {counts}; need >= {config.min_events_per_arm}.'))
    if below > config.max_fraction_below_clip:
        reasons.append(dict(code='insufficient_common_support', field='propensity', detail=f'Fraction below clip is {below:.6g}.'))
    if min(fractions) < config.min_ess_fraction:
        reasons.append(dict(code='small_effective_sample', field='propensity', detail=f'Minimum observed-arm ESS fraction is {min(fractions):.6g}.'))
    finite_smds = [v for v in smds if v is not None]
    maximum = max(finite_smds) if finite_smds else None
    if maximum is None or maximum > config.smd_limit:
        reasons.append(dict(code='weighted_imbalance', field='pre_treatment_X', detail=f'Maximum weighted SMD is {maximum}; limit={config.smd_limit}.'))
    return dict(passed=not reasons, reasons=reasons, arm_counts=counts, min_pi=float(pi.min()),
                fraction_below_clip=below, observed_arm_ess_fractions=fractions,
                weighted_smd_by_arm=smds, max_weighted_smd=maximum,
                smd_limit=config.smd_limit, propensity_clip=config.propensity_clip,
                diagnostic_is_not_identification_proof=True)


def cluster_band(scores, groups, config):
    contrasts = scores[:, 1:]-scores[:, [0]]
    tau = contrasts.mean(0)
    users, inverse = _ordered_groups(groups)
    G, n = len(users), len(groups)
    sums = np.zeros((G, contrasts.shape[1]))
    np.add.at(sums, inverse, contrasts-tau)
    sums *= np.sqrt(G/(G-1))
    se = np.sqrt(np.sum(sums*sums, axis=0))/n
    rng = np.random.default_rng(config.seed+73)
    # Draw in chunks so a larger user count does not allocate n_boot*users at once.
    t_max = []
    active = se > 1e-14
    for start in range(0, config.n_boot, 128):
        xi = rng.standard_normal((min(128, config.n_boot-start), G))
        z = xi@sums/n
        t_max.extend(np.max(abs(z[:, active])/se[active], axis=1).tolist() if active.any() else [0.]*len(xi))
    critical = float(np.quantile(t_max, 1-config.alpha))
    return dict(contrasts=np.r_[0., tau].tolist(), standard_errors=np.r_[0., se].tolist(),
                lower=np.r_[0., tau-critical*se].tolist(), upper=np.r_[0., tau+critical*se].tolist(),
                critical=critical, nominal_level=1-config.alpha, bootstrap_draws=config.n_boot,
                cluster_count=G, inference_unit='original_user',
                uncertainty_scope='sampling_conditional_on_supplied_outcome_and_nuisance_method',
                reference_process_uncertainty_propagated=False)


def threshold_set(lower, upper, levels, kappa):
    lo, hi = np.asarray(lower), np.asarray(upper)
    indices = [j for j in range(1, len(levels)) if hi[j] >= kappa and np.all(lo[:j] < kappa)]
    return dict(first_grid_crossing_indices=indices,
                adjacent_level_brackets=[[float(levels[j-1]), float(levels[j])] for j in indices],
                not_reached_possible=bool(np.all(lo < kappa)), target_increment=float(kappa),
                shape_constraint='none', continuous_between_level_threshold_identified=False)
