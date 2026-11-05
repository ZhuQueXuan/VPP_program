"""Versioned JSON API for discrete effect estimation and legacy binary G1."""
from __future__ import annotations
from dataclasses import asdict
import json
import numpy as np
from .validation import (ContractError, EffectConfig, numeric_array, user_ids, integer,
                         validate_config, validate_task, validate_assumptions, fail)
from .core import (AuxiliaryFitError, group_folds, training_support, crossfit_auxiliary,
                   aipw_scores, support_screen, cluster_band, threshold_set)

SCHEMA_VERSION = 'b1.effects.v1'
DEFAULT_LEVELS = (0., .4, .8, 1.2, 1.6, 2., 2.4)


def _empty(method='standard_multivalued_AIPW'):
    return dict(schema_version=SCHEMA_VERSION, component='effects', method=method,
                status='invalid_input', reasons=[], task=None, levels=None,
                estimand='event_weighted_mean_contrast_relative_to_first_level',
                support_pass=False, causal_assumptions_confirmed=False,
                declared_assumptions=None, unconfirmed_assumptions=[],
                causal_curve=None, standardized_association=None, threshold_set=None,
                comparators=None, diagnostics=None, inference=None,
                uncertainty=dict(scope='conditional_on_supplied_outcome',
                                 reference_process_uncertainty_propagated=False),
                audit=None)


def _levels_and_idx(treatment, levels):
    levels = numeric_array(levels, 'levels', 1)
    if len(levels) < 2 or not np.all(np.diff(levels) > 0):
        fail('invalid_levels', 'levels', 'At least two distinct increasing levels are required.')
    d = numeric_array(treatment, 'treatment', 1)
    match = np.isclose(d[:, None], levels[None, :], rtol=0, atol=1e-10)
    if not np.all(match.sum(1) == 1):
        fail('dose_out_of_domain', 'treatment', 'Every treatment must match exactly one declared level.')
    return levels, match.argmax(1), d


def _point_curve(apo, levels, unit):
    return dict(levels=levels.tolist(), reference_level=float(levels[0]), mean_outcomes=apo.tolist(),
                contrasts=(apo-apo[0]).tolist(), outcome_unit=unit,
                weighting='event_equal_weight', new_causal_estimator=False)


def _json_checked(result):
    try:
        json.dumps(result, allow_nan=False)
    except (ValueError, TypeError, OverflowError):
        result.update(status='unsupported', reasons=[dict(code='nonfinite_numerical_output', field='estimation',
                      detail='Computation produced an unsafe numerical/serialization result; no estimates are reported.')],
                      support_pass=False, causal_curve=None, standardized_association=None,
                      comparators=None, threshold_set=None, inference=None, audit=None, diagnostics=None)
    return result


def fit_effects(X, treatment, outcome, users, *, levels=DEFAULT_LEVELS, task=None,
                assumptions=None, known_pi=None, config=None):
    """Fit established discrete multivalued AIPW on external event outcomes.

    `task` defines one common predeclared task/outcome. Observational causal
    interpretation requires explicit assumptions, never merely diagnostics.
    Unconfirmed assumptions yield standardized association point estimates only.
    Support failures yield no reportable curve. All returned values are JSON-native.
    """
    result = _empty()
    try:
        x = numeric_array(X, 'X', 2)
        if x.shape[1] < 1:
            fail('empty_covariates', 'X', 'At least one declared pre-treatment covariate is required.')
        lev, idx, d = _levels_and_idx(treatment, levels)
        y = numeric_array(outcome, 'outcome', 1)
        groups = user_ids(users)
        if not (len(x) == len(d) == len(y) == len(groups)) or len(y) == 0:
            fail('event_count_mismatch', 'inputs', 'X, treatment, outcome and users must have the same nonzero event count.')
        context = validate_task(task)
        cfg = validate_config(config, len(lev))
        declared, confirmed, missing = validate_assumptions(assumptions, context, known_pi is not None)
        probabilities = None
        if known_pi is not None:
            probabilities = numeric_array(known_pi, 'known_pi', 2)
            if probabilities.shape != (len(y), len(lev)) or np.any((probabilities < 0)|(probabilities > 1)) or not np.allclose(probabilities.sum(1), 1., atol=1e-8, rtol=0):
                fail('invalid_known_probabilities', 'known_pi', 'Expected event-by-level probability rows in [0,1] summing to one.')
            if np.any(probabilities[np.arange(len(y)), idx] <= 0):
                fail('observed_zero_probability_treatment', 'known_pi', 'An observed treatment cannot have declared assignment probability zero.')
        result.update(task=context, levels=lev.tolist(), declared_assumptions=declared,
                      causal_assumptions_confirmed=confirmed, unconfirmed_assumptions=missing,
                      configuration={k:(bool(v) if isinstance(v,np.bool_) else int(v) if isinstance(v,np.integer) else float(v) if isinstance(v,np.floating) else v) for k,v in asdict(cfg).items()})
        result['uncertainty'].update(reference_status=context['reference_status'],
                                     declared_reference_uncertainty=context['reference_uncertainty'])
        G = len(np.unique(groups))
        if G < cfg.n_folds:
            result.update(status='unsupported', reasons=[dict(code='insufficient_users_for_folds', field='users', detail=f'{G} users for {cfg.n_folds} folds.')])
            return result
        folds = group_folds(groups, cfg.n_folds, cfg.seed)
        train_counts, sparse = training_support(idx, folds, len(lev), cfg.min_train_per_arm)
        if sparse:
            result.update(status='unsupported', reasons=sparse,
                          diagnostics=dict(training_counts=train_counts, passed=False, diagnostic_is_not_identification_proof=True))
            return result
        try:
            mu, pi = crossfit_auxiliary(x, idx, y, folds, len(lev), cfg, probabilities)
        except (AuxiliaryFitError, ValueError, np.linalg.LinAlgError) as exc:
            result.update(status='unsupported', reasons=[dict(code='auxiliary_fit_failed', field='auxiliary_models', detail=str(exc))])
            return result
        diag = support_screen(x, idx, pi, cfg)
        diag['training_counts'] = train_counts
        diag['original_user_fold_integrity'] = True
        diag['events'] = len(y)
        diag['users'] = G
        result['diagnostics'] = diag
        result['support_pass'] = bool(diag['passed'])
        if not diag['passed']:
            result.update(status='unsupported', reasons=diag['reasons'])
            return result
        scores = aipw_scores(y, idx, mu, pi, cfg.propensity_clip)
        apo = scores.mean(0)
        point = _point_curve(apo, lev, context['outcome_unit'])
        plugin = mu.mean(0)
        ipw = (np.eye(len(lev))[idx]*y[:, None]/np.maximum(pi, cfg.propensity_clip)).mean(0)
        result['comparators'] = dict(
            plugin_shared_auxiliary=_point_curve(plugin, lev, context['outcome_unit']),
            ipw_shared_auxiliary=dict(**_point_curve(ipw, lev, context['outcome_unit']), normalization='Horvitz_Thompson_not_Hajek'),
            arm_mean_randomized=None)
        if declared['randomized_assignment'] is True and np.allclose(probabilities, probabilities[[0]], rtol=0, atol=1e-10):
            means = np.array([y[idx==j].mean() for j in range(len(lev))])
            result['comparators']['arm_mean_randomized'] = _point_curve(means, lev, context['outcome_unit'])
        elif declared['randomized_assignment'] is True:
            result['comparators']['arm_mean_randomized_unavailable_reason'] = 'Covariate-dependent randomization probabilities require adjustment; unadjusted arm means are not a valid population-effect baseline.'
        if confirmed:
            band = cluster_band(scores, groups, cfg)
            result.update(status='causal', causal_curve=point, inference=band,
                          threshold_set=threshold_set(band['lower'], band['upper'], lev, cfg.kappa) if cfg.kappa is not None else None)
        else:
            result.update(status='association', standardized_association=point,
                          reasons=[dict(code='causal_assumptions_unconfirmed', field='assumptions', detail=', '.join(missing))])
        if cfg.return_audit:
            result['audit'] = dict(auxiliary_result_predictions=mu.tolist(), propensity_predictions=pi.tolist(),
                                  aipw_scores=scores.tolist(), fold_by_event=folds.tolist(),
                                  dose_index=idx.tolist(), purpose='arithmetic_audit_not_additional_causal_evidence')
        return _json_checked(result)
    except ContractError as exc:
        result['reasons'] = [exc.reason]
        return _json_checked(result)


def fit_binary_saturated(X_train, treatment, outcome, users_train, X_target, users_target,
                         *, levels=(0., 1.), task=None, assumptions=None, min_cell=20):
    """Legacy G1: exactly two binary covariates, separate target-user weights.

    No continuous median binning, no dropping/renormalizing unsupported cells,
    and no causal interval claim. This preserves the legitimate old binary domain.
    """
    result = _empty('legacy_binary_saturated_standardization')
    try:
        x = numeric_array(X_train, 'X_train', 2)
        target = numeric_array(X_target, 'X_target', 2)
        if x.shape[1:] != (2,) or target.shape[1:] != (2,) or not np.isin(x,[0.,1.]).all() or not np.isin(target,[0.,1.]).all():
            fail('legacy_binary_domain', 'X', 'Exactly two genuinely binary 0/1 covariates are supported; continuous binning is not performed.')
        lev, idx, d = _levels_and_idx(treatment, levels)
        if len(lev) != 2:
            fail('legacy_binary_domain', 'levels', 'Exactly two treatment levels are required.')
        y = numeric_array(outcome, 'outcome', 1)
        source_users, target_users = user_ids(users_train, 'users_train'), user_ids(users_target, 'users_target')
        if len(y) == 0 or len(target) == 0 or not (len(x)==len(y)==len(idx)==len(source_users)) or len(target)!=len(target_users):
            fail('event_count_mismatch', 'inputs', 'Training and target arrays must match their respective users and be nonempty.')
        if set(source_users)&set(target_users):
            fail('overlapping_target_users', 'users', 'Training and target users must be disjoint.')
        minimum = integer(min_cell, 'min_cell', 2)
        context = validate_task(task)
        declared, confirmed, missing = validate_assumptions(assumptions, context, False)
        result.update(task=context, levels=lev.tolist(), declared_assumptions=declared,
                      causal_assumptions_confirmed=confirmed, unconfirmed_assumptions=missing,
                      estimand='target_event_weighted_mean_contrast_relative_to_first_level')
        means = np.empty((4,2));counts=[];weights=[];reasons=[]
        for cell,(a,b) in enumerate([(0,0),(0,1),(1,0),(1,1)]):
            mask=(x[:,0]==a)&(x[:,1]==b)
            weights.append(float(np.mean((target[:,0]==a)&(target[:,1]==b))))
            row=[]
            for j in range(2):
                select=mask&(idx==j);count=int(select.sum());row.append(count)
                if count < minimum:
                    reasons.append(dict(code='sparse_binary_cell',field='X_train/treatment',detail=f'cell=({a},{b}), arm={j}: {count} events, need {minimum}; no cell is silently dropped.'))
                means[cell,j]=float(y[select].mean()) if count else 0.
            counts.append(row)
        result['diagnostics']=dict(passed=not reasons, cell_training_counts=counts, target_cell_weights=weights,
                                   diagnostic_is_not_identification_proof=True)
        if reasons:
            result.update(status='unsupported',reasons=reasons);return result
        apo=np.asarray(weights)@means
        point=_point_curve(apo,lev,context['outcome_unit'])
        result['support_pass']=True
        result['uncertainty']['scope']='point_estimate_only_no_legacy_interval_claim'
        if confirmed:
            result.update(status='causal',causal_curve=point)
        else:
            result.update(status='association',standardized_association=point,
                          reasons=[dict(code='causal_assumptions_unconfirmed',field='assumptions',detail=', '.join(missing))])
        return _json_checked(result)
    except ContractError as exc:
        result['reasons']=[exc.reason];return _json_checked(result)
