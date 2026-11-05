"""Validation-user tuning of the existing Kennedy DR local-linear estimator.

This selects a nuisance configuration by observed-outcome prediction risk and
then a smoothing multiplier by leave-one-user-out pseudo-outcome prediction
risk. The latter is conditional on the selected cross-fitted pseudo-outcomes;
it is not a new causal estimator or full-pipeline uncertainty procedure.
"""
from collections.abc import Mapping
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import numpy as np

from .continuous import (ContinuousEffectConfig, _config, _crossfit,
                         _local_support, fit_continuous_effects,
                         local_linear_weights)
from .frozen import _freeze
from .validation import (integer, numeric_array, real_scalar, text, user_ids,
                         validate_assumptions, validate_task)


SCHEMA = 'b1.continuous-tuning.v1'
RIDGE_CANDIDATES = (.1, 10.)
KNOT_CANDIDATES = (4, 6)
BANDWIDTH_CANDIDATES = (.75, 1., 1.5, 2.)


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False)


def _sha(value):
    return hashlib.sha256(_json(value).encode('utf-8')).hexdigest()


@dataclass(frozen=True)
class TuningSelection:
    """Immutable serialized selection; checksum establishes integrity only."""
    payload_json: str
    sha256: str


def _checked_inputs(X, treatment, outcome, users, *, dose_domain, grid,
                    reference_dose, incentive_unit, task,
                    continuous_assignment, assumptions, known_density, config):
    """Same strict input policy and validators as the existing core fit."""
    x = numeric_array(X, 'X', 2)
    d = numeric_array(treatment, 'treatment', 1)
    y = numeric_array(outcome, 'outcome', 1)
    groups = user_ids(users)
    if not len(y) or not (len(x) == len(d) == len(y) == len(groups)) or x.shape[1] < 1:
        raise ValueError('nonempty matching event arrays and pre-treatment covariates required')
    if len(y) > 12000 or x.shape[1] > 30:
        raise ValueError('finite domain: at most12000 events and30 covariates')
    cfg = _config(config)
    context = validate_task(task)
    unit = text(incentive_unit, 'incentive_unit')
    if continuous_assignment is not True:
        raise ValueError('explicit continuous assignment declaration required')
    domain = numeric_array(dose_domain, 'dose_domain', 1)
    if domain.shape != (2,) or domain[0] < 0 or domain[1] <= domain[0]:
        raise ValueError('finite nonnegative increasing dose domain required')
    lo, hi = domain
    if np.any((d <= lo) | (d >= hi)):
        raise ValueError('observed doses must be strictly inside the continuous domain')
    if len(np.unique(d)) < cfg.min_unique_doses:
        raise ValueError('too few unique continuous doses')
    if len(np.unique(groups)) < max(cfg.n_folds*2, cfg.min_local_users):
        raise ValueError('insufficient independent users')
    requested = numeric_array(grid, 'grid', 1)
    ref = real_scalar(reference_dose, 'reference_dose')
    if not 1 <= len(requested) <= 301 or np.any(np.diff(requested) <= 0):
        raise ValueError('1..301 increasing query amounts required')
    if not lo <= ref <= hi or np.any((requested < lo) | (requested > hi)):
        raise ValueError('reference and complete grid must lie inside declared domain')
    density = None if known_density is None else numeric_array(known_density, 'known_density', 1)
    if density is not None:
        if density.shape != d.shape or np.any(density <= 0):
            raise ValueError('positive ex-ante density required for every observed dose')
        if (not np.allclose(density, 1/(hi-lo), rtol=1e-8, atol=1e-10)
                or not isinstance(assumptions, Mapping)
                or assumptions.get('randomized_assignment') is not True):
            raise ValueError('known density supports declared randomized Uniform design only')
    declared, _, _ = validate_assumptions(assumptions, context, density is not None)
    points = np.r_[ref, requested[~np.isclose(requested, ref, atol=1e-12, rtol=0)]]
    return x, d, y, groups, cfg, context, unit, domain, requested, ref, density, declared, points


def _rule_bandwidth(d, groups):
    return 1.06*float(np.std(d))*len(np.unique(groups))**(-.2)


def _feature_names(names, count):
    if names is None:
        return ['X_'+str(i) for i in range(count)]
    if not isinstance(names, (list, tuple)) or len(names) != count:
        raise ValueError('one ordered predeclared covariate name per X column required')
    result = [text(name, 'covariate_names') for name in names]
    if len(set(result)) != count:
        raise ValueError('covariate names must be unique')
    return result


def _loo_user_risk(x, d, xi, groups, weights, points, bandwidth, cfg):
    """Predict every held-out event after excluding its entire original user."""
    diagnostics, failed = _local_support(x, d, groups, points, bandwidth, weights, cfg)
    if failed:
        return dict(status='unsupported', risk=None,
                    reasons=['full_validation_grid_lacks_support'],
                    unsupported_doses=failed, support=diagnostics,
                    held_out_events=0, held_out_users=0)
    prediction = np.empty(len(d))
    held_out_support_failures = []
    for group in np.unique(groups):
        held = groups == group
        train = ~held
        _, unsupported = _local_support(x[train], d[train], groups[train],
                                        points, bandwidth, weights[train], cfg)
        if unsupported:
            held_out_support_failures.append(dict(user=str(group), doses=unsupported))
        # No rows or query points are discarded to improve this risk.
        prediction[held] = local_linear_weights(d[train], d[held], bandwidth) @ xi[train]
    if held_out_support_failures:
        return dict(status='unsupported', risk=None,
                    reasons=['leave_user_out_training_grid_lacks_support'],
                    support=diagnostics,
                    held_out_support_failures=held_out_support_failures,
                    held_out_events=len(d), held_out_users=len(np.unique(groups)))
    risk = float(np.mean((xi-prediction)**2))
    if not np.isfinite(prediction).all() or not np.isfinite(risk):
        raise ValueError('nonfinite held-user-out prediction or risk')
    return dict(status='supported', risk=risk,
                reasons=[], support=diagnostics, held_out_events=len(d),
                held_out_users=len(np.unique(groups)),
                target='same_selected_crossfitted_pseudo_outcome',
                event_weighting='event_equal_weight', all_user_events_excluded=True)


def select_continuous_tuning(X, treatment, outcome, users, *, dose_domain,
                             grid, reference_dose, incentive_unit, task,
                             validation_id, validation_completed_at_min,
                             selection_cutoff_min, continuous_assignment=None,
                             assumptions=None, known_density=None, config=None,
                             covariate_names=None):
    """Select once on completed validation users without latent/simulator truth.

    Only measured outcome is accepted. ``selection_cutoff_min`` uses the same
    absolute minute clock as the supplied completed events and later notices.
    It is a declaration; array-only APIs cannot audit the event provenance.
    """
    (x, d, y, groups, cfg, context, unit, domain, requested, ref, density,
     declared, points) = _checked_inputs(X, treatment, outcome, users,
        dose_domain=dose_domain, grid=grid, reference_dose=reference_dose,
        incentive_unit=incentive_unit, task=task,
        continuous_assignment=continuous_assignment, assumptions=assumptions,
        known_density=known_density, config=config)
    identifier = text(validation_id, 'validation_id')
    completed = real_scalar(validation_completed_at_min, 'validation_completed_at_min')
    cutoff = real_scalar(selection_cutoff_min, 'selection_cutoff_min')
    if completed > cutoff:
        raise ValueError('validation outcomes must be complete by the declared selection cutoff')
    if cfg.bandwidth is not None:
        raise ValueError('selection requires the existing cohort bandwidth rule, not an absolute bandwidth')
    nuisance = []
    usable = []
    # The Ridge alpha is shared with the original assignment-density model.
    # Therefore this is joint nuisance tuning, not only outcome-head tuning.
    for alpha in RIDGE_CANDIDATES:
        for knots in KNOT_CANDIDATES:
            row = dict(ridge_alpha=alpha, spline_knots=knots, risk=None,
                       risk_target='OOF_observed_outcome_prediction_MSE', reasons=[])
            candidate = replace(cfg, ridge_alpha=alpha, spline_knots=knots)
            try:
                crossfit = _crossfit(x, d, y, groups, candidate, domain, density)
                xi, weights, folds, _, mu, _ = crossfit
                risk = float(np.mean((y-mu)**2))
                if not all(np.isfinite(value).all() for value in (xi, weights, mu)) or not np.isfinite(risk):
                    raise ValueError('nonfinite crossfitted nuisance output or prediction risk')
                row.update(status='supported', risk=risk,
                           fold_by_event=folds.tolist(),
                           max_stabilized_weight=float(weights.max()))
                usable.append((row['risk'], knots, -alpha, candidate, xi, weights))
            except (ValueError, TypeError, OverflowError, np.linalg.LinAlgError) as exc:
                row.update(status='unsupported', reasons=[str(exc)])
            nuisance.append(row)
    selected = None
    bandwidth_rows = []
    base_h = _rule_bandwidth(d, groups)
    if usable:
        # Exact ties prefer fewer spline knots, then stronger regularization.
        _, _, _, chosen_cfg, xi, weights = min(usable, key=lambda value: value[:3])
        supported = []
        for scale in BANDWIDTH_CANDIDATES:
            h = base_h*scale
            row = dict(bandwidth_scale=scale, validation_bandwidth=h, risk=None)
            try:
                if not 0 < h <= (domain[1]-domain[0])/2:
                    row.update(status='unsupported', reasons=['bandwidth_exceeds_half_domain_span'])
                else:
                    row.update(_loo_user_risk(x, d, xi, groups, weights,
                                             points, h, chosen_cfg))
                    if row['status'] == 'supported':
                        supported.append((row['risk'], -scale, scale))
            except (ValueError, TypeError, OverflowError, np.linalg.LinAlgError) as exc:
                row.update(status='unsupported', reasons=[str(exc)])
            bandwidth_rows.append(row)
        if supported:
            _, _, scale = min(supported)
            selected = dict(ridge_alpha=chosen_cfg.ridge_alpha,
                            spline_knots=chosen_cfg.spline_knots,
                            bandwidth_scale=scale)
    payload = dict(schema=SCHEMA, status='selected' if selected else 'unsupported',
        method='validation_tuning_existing_Kennedy_DR_local_linear',
        new_causal_estimator=False, selected=selected,
        fixed_context=dict(task=context, incentive_unit=unit,
            dose_domain=domain.tolist(), grid=requested.tolist(), reference_dose=ref,
            covariate_names=_feature_names(covariate_names, x.shape[1]),
            declared_assumptions=declared, known_density_used=density is not None,
            continuous_assignment_declared=True),
        base_configuration=asdict(replace(cfg, return_audit=False)),
        validation=dict(id=identifier, events=len(y), users=sorted(set(groups)),
            completed_at_min=completed, selection_cutoff_min=cutoff,
            data_sha256=_sha(dict(X=x.tolist(), dose=d.tolist(), outcome=y.tolist(),
                                 users=groups.tolist(), known_density=None if density is None else density.tolist())),
            timestamp_provenance='caller_declared_absolute_minute_clock'),
        created_at_utc=datetime.now(timezone.utc).isoformat(),
        nuisance_candidates=nuisance, bandwidth_candidates=bandwidth_rows,
        selection_protocol=dict(nuisance_risk='OOF_observed_outcome_prediction_MSE',
            nuisance_crossfit='original_core_same_user_folds',
            ridge_alpha_also_changes_assignment_model=True,
            pseudo_outcome_risks_compared_only_within_selected_nuisance=True,
            smoothing_risk='leave_one_original_user_out_pseudo_outcome_prediction_MSE',
            smoothing_risk_conditional_on_fixed_crossfitted_pseudo_outcomes=True,
            required_support='complete_fixed_grid_and_reference_in_full_and_each_leave_user_out_training_cohort',
            unsupported_points_deleted=0, latent_truth_used=False,
            nuisance_tie='fewer_knots_then_stronger_ridge', bandwidth_tie='larger_bandwidth',
            bandwidth_rule='selected_scale *1.06*std(cohort_dose)*cohort_users**(-.2)',
            validation_rule_bandwidth=base_h),
        limitations=['validation selection does not establish a new causal estimator',
            'smoothing risk is conditional on fixed cross-fitted pseudo-outcomes, not an independent full-pipeline risk',
            'time and pre-treatment covariate provenance remain caller declarations for array APIs',
            'original conditional sampling bands do not propagate tuning, nuisance, reference or process uncertainty'])
    serialized = _json(payload)
    selection = TuningSelection(serialized, hashlib.sha256(serialized.encode('utf-8')).hexdigest())
    _payload(selection)
    return selection


def _payload(selection):
    if not isinstance(selection, TuningSelection):
        raise ValueError('TuningSelection required')
    if not isinstance(selection.payload_json, str) or not isinstance(selection.sha256, str):
        raise ValueError('selection payload and checksum must be strings')
    if hashlib.sha256(selection.payload_json.encode('utf-8')).hexdigest() != selection.sha256:
        raise ValueError('tuning selection checksum mismatch')
    p = json.loads(selection.payload_json)
    if not isinstance(p, dict) or p.get('schema') != SCHEMA:
        raise ValueError('unsupported tuning selection schema')
    _json(p)
    if p.get('status') not in ('selected', 'unsupported') or p.get('new_causal_estimator') is not False:
        raise ValueError('invalid tuning status or estimator declaration')
    cfg = _config(p['base_configuration'])
    if cfg.bandwidth is not None:
        raise ValueError('selection must freeze a bandwidth multiplier, not an absolute bandwidth')
    context = p['fixed_context']
    names = context['covariate_names']
    if not isinstance(names, list) or not 1 <= len(names) <= 30:
        raise ValueError('invalid frozen covariate columns')
    _feature_names(names, len(names))
    validate_task(context['task'])
    text(context['incentive_unit'], 'incentive_unit')
    domain = numeric_array(context['dose_domain'], 'dose_domain', 1)
    a = numeric_array(context['grid'], 'grid', 1)
    ref = real_scalar(context['reference_dose'], 'reference_dose')
    if (domain.shape != (2,) or domain[0] < 0 or domain[1] <= domain[0]
            or not 1 <= len(a) <= 301 or np.any(np.diff(a) <= 0)
            or np.any((a < domain[0]) | (a > domain[1]))
            or not domain[0] <= ref <= domain[1]):
        raise ValueError('invalid frozen dose domain, grid or reference')
    if type(context['known_density_used']) is not bool or context['continuous_assignment_declared'] is not True:
        raise ValueError('invalid frozen design declaration')
    validate_assumptions(context['declared_assumptions'], context['task'], context['known_density_used'])
    validation = p['validation']
    text(validation['id'], 'validation.id')
    completed = real_scalar(validation['completed_at_min'], 'completed_at_min')
    cutoff = real_scalar(validation['selection_cutoff_min'], 'selection_cutoff_min')
    if completed > cutoff:
        raise ValueError('validation completion exceeds selection cutoff')
    identifiers = validation['users']
    if (not isinstance(identifiers, list) or not identifiers
            or any(not isinstance(v, str) or not v.startswith(('string:', 'integer:')) for v in identifiers)
            or identifiers != sorted(set(identifiers))):
        raise ValueError('unique sorted canonical validation user IDs required')
    integer(validation['events'], 'validation.events', len(identifiers), 12000)
    digest = text(validation['data_sha256'], 'data_sha256')
    if len(digest) != 64 or any(v not in '0123456789abcdef' for v in digest):
        raise ValueError('invalid validation data SHA256')
    created = datetime.fromisoformat(p['created_at_utc'])
    if created.tzinfo is None:
        raise ValueError('selection creation time requires explicit timezone')
    if p['status'] == 'selected':
        chosen = p['selected']
        if (set(chosen) != {'ridge_alpha', 'spline_knots', 'bandwidth_scale'}
                or real_scalar(chosen['ridge_alpha'], 'ridge_alpha') not in RIDGE_CANDIDATES
                or integer(chosen['spline_knots'], 'spline_knots') not in KNOT_CANDIDATES
                or real_scalar(chosen['bandwidth_scale'], 'bandwidth_scale') not in BANDWIDTH_CANDIDATES):
            raise ValueError('invalid selected candidate configuration')
    elif p['selected'] is not None:
        raise ValueError('unsupported selection cannot contain selected configuration')
    if len(p['nuisance_candidates']) != 4 or len(p['bandwidth_candidates']) not in (0, 4):
        raise ValueError('complete fixed candidate records required')
    nuisance_supported = []
    nuisance_seen = set()
    for row in p['nuisance_candidates']:
        alpha = real_scalar(row['ridge_alpha'], 'candidate.ridge_alpha')
        knots = integer(row['spline_knots'], 'candidate.spline_knots')
        if (alpha not in RIDGE_CANDIDATES or knots not in KNOT_CANDIDATES
                or (alpha, knots) in nuisance_seen
                or row['risk_target'] != 'OOF_observed_outcome_prediction_MSE'):
            raise ValueError('invalid or duplicate nuisance candidate')
        nuisance_seen.add((alpha, knots))
        if row['status'] == 'supported':
            risk = real_scalar(row['risk'], 'candidate.risk')
            if risk < 0 or len(row['fold_by_event']) != validation['events']:
                raise ValueError('invalid OOF risk or incomplete fold record')
            nuisance_supported.append((risk, knots, -alpha))
        elif row['status'] != 'unsupported' or row['risk'] is not None or not row['reasons']:
            raise ValueError('invalid unsupported nuisance candidate')
    smoothing_supported = []
    bandwidth_seen = set()
    for row in p['bandwidth_candidates']:
        scale = real_scalar(row['bandwidth_scale'], 'candidate.bandwidth_scale')
        if scale not in BANDWIDTH_CANDIDATES or scale in bandwidth_seen:
            raise ValueError('invalid or duplicate bandwidth candidate')
        bandwidth_seen.add(scale)
        h = real_scalar(row['validation_bandwidth'], 'candidate.validation_bandwidth', positive=True)
        if row['status'] == 'supported':
            risk = real_scalar(row['risk'], 'candidate.risk')
            if (risk < 0 or h > (domain[1]-domain[0])/2
                    or row['held_out_events'] != validation['events']
                    or row['held_out_users'] != len(identifiers)
                    or row['all_user_events_excluded'] is not True):
                raise ValueError('invalid supported smoothing candidate')
            smoothing_supported.append((risk, -scale, scale))
        elif row['status'] != 'unsupported' or row['risk'] is not None or not row['reasons']:
            raise ValueError('invalid unsupported bandwidth candidate')
    if bool(nuisance_supported) != bool(p['bandwidth_candidates']):
        raise ValueError('smoothing stage must follow an eligible nuisance selection')
    if p['status'] == 'selected':
        if not nuisance_supported or not smoothing_supported:
            raise ValueError('selected configuration lacks supported candidate evidence')
        _, best_knots, negative_best_alpha = min(nuisance_supported)
        best_scale = min(smoothing_supported)[2]
        if p['selected'] != dict(ridge_alpha=-negative_best_alpha,
                                 spline_knots=best_knots, bandwidth_scale=best_scale):
            raise ValueError('selected configuration disagrees with recorded validation risks')
    elif smoothing_supported:
        raise ValueError('supported candidates require a selected configuration')
    return p


def describe_continuous_tuning(selection):
    """Return a detached copy; edits cannot mutate the frozen selection."""
    return _payload(selection)


def save_continuous_tuning(selection, path):
    _payload(selection)
    with Path(path).open('x', encoding='utf-8') as handle:
        handle.write(_json(dict(payload_json=selection.payload_json, sha256=selection.sha256)))


def load_continuous_tuning(path):
    path = Path(path)
    if path.stat().st_size > 20_000_000:
        raise ValueError('selection exceeds finite size limit')
    value = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(value, dict) or set(value) != {'payload_json', 'sha256'}:
        raise ValueError('invalid selection envelope')
    selection = TuningSelection(**value)
    _payload(selection)
    return selection


def _application(selection, X, treatment, outcome, users, *, evaluation_notice_min,
                 dose_domain, grid, reference_dose, incentive_unit, task,
                 continuous_assignment, assumptions, known_density, covariate_names):
    p = _payload(selection)
    if p['status'] != 'selected':
        raise ValueError('cannot apply an unsupported tuning selection')
    notice = real_scalar(evaluation_notice_min, 'evaluation_notice_min')
    if notice <= p['validation']['selection_cutoff_min']:
        raise ValueError('evaluation notices must follow the frozen validation selection cutoff')
    data = _checked_inputs(X, treatment, outcome, users, dose_domain=dose_domain,
        grid=grid, reference_dose=reference_dose, incentive_unit=incentive_unit,
        task=task, continuous_assignment=continuous_assignment,
        assumptions=assumptions, known_density=known_density,
        config=p['base_configuration'])
    x, d, y, groups, cfg, context, unit, domain, requested, ref, density, declared, _ = data
    overlaps = set(groups) & set(p['validation']['users'])
    if overlaps:
        raise ValueError('evaluation users overlap frozen validation users')
    supplied_context = dict(task=context, incentive_unit=unit, dose_domain=domain.tolist(),
        grid=requested.tolist(), reference_dose=ref, declared_assumptions=declared,
        covariate_names=_feature_names(covariate_names, x.shape[1]),
        known_density_used=density is not None, continuous_assignment_declared=True)
    if _json(supplied_context) != _json(p['fixed_context']):
        raise ValueError('task, units, population, domain, reference, grid or assumptions differ from frozen selection')
    chosen = p['selected']
    h = chosen['bandwidth_scale']*_rule_bandwidth(d, groups)
    # The original core rejects h beyond span/2 transparently; never clip it.
    return p, replace(cfg, ridge_alpha=chosen['ridge_alpha'],
                      spline_knots=chosen['spline_knots'], bandwidth=h)


def fit_tuned_continuous_effects(selection, X, treatment, outcome, users, *,
                                evaluation_notice_min, dose_domain, grid,
                                reference_dose, incentive_unit, task,
                                continuous_assignment=None, assumptions=None,
                                known_density=None, covariate_names=None,
                                evaluation_seed=None):
    """Fit the original estimator on new users with the frozen configuration.

    Test Y participates in the usual cohort cross-fit, never in configuration
    selection. All measured outcomes/users are retained, including no response.
    """
    p, cfg = _application(selection, X, treatment, outcome, users,
        evaluation_notice_min=evaluation_notice_min, dose_domain=dose_domain,
        grid=grid, reference_dose=reference_dose, incentive_unit=incentive_unit,
        task=task, continuous_assignment=continuous_assignment,
        assumptions=assumptions, known_density=known_density, covariate_names=covariate_names)
    if evaluation_seed is not None:
        cfg = replace(cfg, seed=integer(evaluation_seed, 'evaluation_seed', 0, 2**32-1))
    result = fit_continuous_effects(X, treatment, outcome, users,
        dose_domain=dose_domain, grid=grid, reference_dose=reference_dose,
        incentive_unit=incentive_unit, task=task,
        continuous_assignment=continuous_assignment, assumptions=assumptions,
        known_density=known_density, config=cfg)
    result['tuning'] = dict(selection_id=selection.sha256,
        validation_id=p['validation']['id'], selected=p['selected'],
        selected_on_evaluation_outcomes=False, evaluation_validation_users_disjoint=True,
        bandwidth_uses_evaluation_cohort_rule=True, new_causal_estimator=False,
        evaluation_seed=cfg.seed, evaluation_seed_role='predeclared_cohort_fold_and_bootstrap_seed_not_tuned',
        outcome_definition_or_legal_adjustment_changed=False,
        uncertainty_from_tuning_propagated=False)
    return result


def fit_tuned_continuous_model(selection, X, treatment, outcome, users, *,
                              evaluation_notice_min, dose_domain, grid,
                              reference_dose, incentive_unit, task,
                              continuous_assignment=None, assumptions=None,
                              known_density=None, covariate_names=None,
                              evaluation_seed=None):
    """Freeze an ordinary selected fit after checking the entire fixed grid."""
    p, cfg = _application(selection, X, treatment, outcome, users,
        evaluation_notice_min=evaluation_notice_min, dose_domain=dose_domain,
        grid=grid, reference_dose=reference_dose, incentive_unit=incentive_unit,
        task=task, continuous_assignment=continuous_assignment,
        assumptions=assumptions, known_density=known_density, covariate_names=covariate_names)
    if evaluation_seed is not None:
        cfg = replace(cfg, seed=integer(evaluation_seed, 'evaluation_seed', 0, 2**32-1))
    result = fit_continuous_effects(X, treatment, outcome, users,
        dose_domain=dose_domain, grid=grid, reference_dose=reference_dose,
        incentive_unit=incentive_unit, task=task,
        continuous_assignment=continuous_assignment, assumptions=assumptions,
        known_density=known_density, config=replace(cfg, return_audit=True))
    return _freeze(result, X, users, dict(_known_density_used=known_density is not None,
        tuning_selection_id=selection.sha256, validation_id=p['validation']['id'],
        evaluation_seed=cfg.seed, evaluation_seed_role='predeclared_cohort_fold_and_bootstrap_seed_not_tuned',
        tuned_configuration=p['selected'], new_causal_estimator=False,
        selected_on_evaluation_outcomes=False, fixed_selection_grid=p['fixed_context']['grid'],
        validation_evaluation_users_disjoint=True))
