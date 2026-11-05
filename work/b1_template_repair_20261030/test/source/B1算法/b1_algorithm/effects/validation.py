"""Input contract for discrete effects. No implicit imputation or coercion."""
from __future__ import annotations
from dataclasses import asdict, dataclass, fields
from numbers import Integral, Real
from collections.abc import Mapping
import numpy as np


class ContractError(ValueError):
    def __init__(self, code, field, detail):
        super().__init__(detail)
        self.reason = dict(code=code, field=field, detail=detail)


def fail(code, field, detail):
    raise ContractError(code, field, detail)


def real_scalar(value, field, *, positive=False):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real):
        fail('invalid_numeric_type', field, 'Expected a finite real number; booleans and numeric strings are rejected.')
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        fail('numeric_domain', field, 'Value is outside the finite float64 domain.')
    if not np.isfinite(result) or (positive and result <= 0):
        fail('numeric_domain', field, 'Expected a finite strictly positive value.' if positive else 'Value is not finite after conversion.')
    return result


def integer(value, field, minimum=0, maximum=None):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral):
        fail('invalid_integer_type', field, 'Expected an integer, excluding booleans.')
    result = int(value)
    if result < minimum or (maximum is not None and result > maximum):
        fail('integer_domain', field, f'Expected integer in [{minimum}, {maximum if maximum is not None else "infinity"}].')
    return result


def numeric_array(value, field, ndim):
    try:
        objects = np.asarray(value, dtype=object)
    except (TypeError, ValueError) as exc:
        fail('invalid_array', field, str(exc))
    if objects.ndim != ndim:
        fail('array_dimension', field, f'Expected {ndim} dimensions.')
    for item in objects.flat:
        if isinstance(item, (bool, np.bool_)) or not isinstance(item, Real):
            fail('invalid_numeric_type', field, 'Every entry must be real numeric; booleans, strings and missing entries are rejected.')
    try:
        result = objects.astype(float)
    except (ValueError, TypeError, OverflowError) as exc:
        fail('invalid_numeric_conversion', field, str(exc))
    if not np.isfinite(result).all():
        fail('nonfinite_input', field, 'Missing/NaN/infinite values require a separately specified missingness policy.')
    return result


def user_ids(value, field='users'):
    objects = np.asarray(value, dtype=object)
    if objects.ndim != 1:
        fail('array_dimension', field, 'Expected one user identifier per event.')
    result = []
    for item in objects:
        if isinstance(item, (bool, np.bool_)):
            fail('invalid_user_id', field, 'Boolean identifiers are rejected.')
        if isinstance(item, Integral):
            result.append('integer:' + str(int(item)))
        elif isinstance(item, str) and item.strip():
            result.append('string:' + item)
        else:
            fail('invalid_user_id', field, 'Use nonempty strings or integers; missing/nonfinite/fractional identifiers are rejected.')
    return np.asarray(result, dtype=str)


def text(value, field):
    if not isinstance(value, str) or not value.strip():
        fail('missing_text', field, 'Expected a nonempty string.')
    return value


@dataclass(frozen=True)
class EffectConfig:
    n_folds: int = 3
    n_boot: int = 999
    alpha: float = .05
    kappa: float | None = .1
    propensity_clip: float = .01
    max_fraction_below_clip: float = .01
    min_ess_fraction: float = .1
    smd_limit: float = .2
    min_train_per_arm: int = 10
    min_events_per_arm: int = 10
    outcome_degree: int = 2
    ridge_alpha: float = 1.
    propensity_C: float = 1.
    seed: int = 0
    return_audit: bool = False


def validate_config(config, n_levels):
    if config is None:
        cfg = EffectConfig()
    elif isinstance(config, EffectConfig):
        cfg = config
    elif isinstance(config, Mapping):
        unknown = set(config) - {f.name for f in fields(EffectConfig)}
        if unknown:
            fail('unknown_config', 'config', f'Unknown options: {sorted(map(str,unknown))}')
        cfg = EffectConfig(**config)
    else:
        fail('invalid_config', 'config', 'Expected EffectConfig or a mapping.')
    integer(cfg.n_folds, 'config.n_folds', 2, 20)
    integer(cfg.n_boot, 'config.n_boot', 99)
    integer(cfg.seed, 'config.seed', 0, 2**32-1)
    integer(cfg.min_train_per_arm, 'config.min_train_per_arm', 2)
    integer(cfg.min_events_per_arm, 'config.min_events_per_arm', 2)
    if integer(cfg.outcome_degree, 'config.outcome_degree', 1, 2) not in (1, 2):
        fail('numeric_domain', 'config.outcome_degree', 'Use degree 1 or 2.')
    for name in ['alpha', 'propensity_clip', 'min_ess_fraction', 'smd_limit', 'ridge_alpha', 'propensity_C']:
        real_scalar(getattr(cfg, name), 'config.'+name, positive=True)
    real_scalar(cfg.max_fraction_below_clip, 'config.max_fraction_below_clip')
    if not (0 < cfg.alpha < 1 and 0 < cfg.propensity_clip < 1/n_levels):
        fail('numeric_domain', 'config', 'alpha must be in (0,1); propensity_clip must be in (0,1/number_of_levels).')
    if not (0 <= cfg.max_fraction_below_clip < 1 and 0 < cfg.min_ess_fraction <= 1 and 0 < cfg.smd_limit <= 1):
        fail('numeric_domain', 'config', 'Invalid support-screen limits.')
    if cfg.kappa is not None:
        real_scalar(cfg.kappa, 'config.kappa', positive=True)
    if not isinstance(cfg.return_audit, (bool, np.bool_)):
        fail('invalid_boolean', 'config.return_audit', 'Expected an actual boolean.')
    return cfg


def validate_task(task):
    if not isinstance(task, Mapping):
        fail('invalid_task', 'task', 'A common predeclared task/outcome context is required.')
    result = {}
    for name in ['task_id', 'outcome_name', 'outcome_unit', 'target_population']:
        result[name] = text(task.get(name), 'task.'+name)
    interval = numeric_array(task.get('window_minutes'), 'task.window_minutes', 1)
    if interval.shape != (2,) or interval[1] <= interval[0]:
        fail('task_window', 'task.window_minutes', 'Expected [start,end] with end > start, in minutes.')
    result['window_minutes'] = interval.tolist()
    result['q_kw'] = real_scalar(task.get('q_kw'), 'task.q_kw', positive=True)
    flag = task.get('task_pre_treatment')
    if flag is not None and not isinstance(flag, (bool, np.bool_)):
        fail('invalid_boolean', 'task.task_pre_treatment', 'Use true/false/null, not 0/1 or strings.')
    result['task_pre_treatment'] = None if flag is None else bool(flag)
    result['reference_status'] = text(task.get('reference_status', 'not_declared'), 'task.reference_status')
    uncertainty = task.get('reference_uncertainty', 'not_propagated')
    if uncertainty not in ('not_propagated', 'known_reference', 'not_applicable'):
        fail('uncertainty_not_implemented', 'task.reference_uncertainty', 'This module cannot certify full reference/process uncertainty propagation.')
    result['reference_uncertainty'] = uncertainty
    return result


ASSUMPTIONS = ('pre_treatment_X', 'consistent_treatment', 'no_interference',
               'same_outcome_definition', 'conditional_exchangeability', 'randomized_assignment')


def validate_assumptions(assumptions, task, has_known_pi):
    if assumptions is None:
        assumptions = {}
    if not isinstance(assumptions, Mapping):
        fail('invalid_assumptions', 'assumptions', 'Expected explicit boolean/null declarations.')
    unknown = set(assumptions)-set(ASSUMPTIONS)
    if unknown:
        fail('unknown_assumption', 'assumptions', f'Unknown declarations: {sorted(map(str,unknown))}')
    result = {}
    for name in ASSUMPTIONS:
        value = assumptions.get(name)
        if value is not None and not isinstance(value, (bool, np.bool_)):
            fail('invalid_boolean', 'assumptions.'+name, 'Use true/false/null declarations.')
        result[name] = None if value is None else bool(value)
    if result['randomized_assignment'] is True and not has_known_pi:
        fail('randomization_probabilities_required', 'known_pi', 'Declared randomization requires its ex ante assignment probabilities.')
    missing = [name for name in ASSUMPTIONS[:4] if result[name] is not True]
    if task['task_pre_treatment'] is not True:
        missing.append('task_pre_treatment')
    assignment_ok = result['conditional_exchangeability'] is True or (result['randomized_assignment'] is True and has_known_pi)
    if not assignment_ok:
        missing.append('conditional_exchangeability_or_declared_randomization')
    return result, not missing, missing
