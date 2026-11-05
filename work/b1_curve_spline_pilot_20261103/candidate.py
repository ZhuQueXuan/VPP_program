"""Reusable part-three research candidate from an existing Kennedy DR fit.

No nuisance model is refitted. The public baseline result must contain its
``return_audit=True`` output, with X and users in the identical event order.
The confirmed default penalty applies to this 0..2.4, 30-minute study scope.
Only the point curve is exposed; parts four through six are not modified.
"""

import json
import numpy as np

from b1_algorithm.effects.continuous import _config, _local_support
from b1_algorithm.effects.validation import numeric_array, user_ids
from smoothers import spline_state, spline_query


SCHEMA = 'b1.research-smoothing-spline.v1'


def fit_candidate_from_shared_result(baseline_result, X, users, lambda_mean=1e-4):
    """Replace only final smoothing of the public baseline's cached pseudo-Y.

    The same rows of X/users used for the baseline must be supplied; its audit
    does not contain event identities with which to independently recover them.
    """
    if (baseline_result.get('schema_version') != 'b1.continuous-effects.v1'
            or baseline_result.get('method') != 'Kennedy_DR_local_linear'
            or baseline_result.get('status') not in ('causal', 'association')):
        raise ValueError('A completed public Kennedy DR baseline result is required')
    task = baseline_result['task']
    if (baseline_result['dose_domain'] != [0.0, 2.4]
            or task['outcome_name'] != 'cumulative_response_seconds'
            or task['outcome_unit'] != 'seconds'
            or not np.isclose(np.diff(task['window_minutes'])[0], 30.0)):
        raise ValueError('Candidate scope is 0..2.4 compensation and 30-minute cumulative response seconds')
    audit = baseline_result.get('audit')
    if audit is None:
        raise ValueError('The shared public result must be fitted with return_audit=True')
    x = numeric_array(X, 'X', 2)
    groups = user_ids(users)
    d = numeric_array(audit['dose'], 'dose', 1)
    xi = numeric_array(audit['pseudo_outcome'], 'pseudo_outcome', 1)
    weights = numeric_array(audit['stabilized_weight'], 'stabilized_weight', 1)
    if not (len(x) == len(groups) == len(d) == len(xi) == len(weights)) or not 1 <= x.shape[1] <= 30:
        raise ValueError('X and users must match the original baseline event rows')
    penalty = float(lambda_mean)
    if not np.isfinite(penalty) or penalty < 0:
        raise ValueError('A finite nonnegative lambda_mean is required')
    _config(baseline_result['configuration'])
    model = dict(
        schema=SCHEMA, method='Kennedy_DR_shared_pseudo_outcome_cubic_smoothing_spline',
        status=baseline_result['status'], state=spline_state(d, xi, penalty),
        X=x.tolist(), users=groups.tolist(), dose=d.tolist(),
        stabilized_weight=weights.tolist(),
        baseline_bandwidth=float(baseline_result['diagnostics']['bandwidth']),
        configuration=baseline_result['configuration'], task=task,
        dose_domain=baseline_result['dose_domain'],
        reference_dose=float(baseline_result['reference_dose']),
        incentive_unit=baseline_result['incentive_unit'],
        declared_assumptions=baseline_result['declared_assumptions'],
        new_nuisance_fits=0, shared_pseudo_outcome=True,
        population_scope='fixed fitted cohort, event equal weight',
        output_scope='part-three point curve only',
    )
    # Standard JSON is the complete persisted state, independent of live objects.
    return json.loads(json.dumps(model, ensure_ascii=False, allow_nan=False))


def query_candidate(model, amounts):
    """Evaluate the continuous spline directly at arbitrary supported amounts."""
    if model.get('schema') != SCHEMA:
        raise ValueError('Unsupported candidate model schema')
    a = numeric_array(amounts, 'amounts', 1)
    if not 1 <= len(a) <= 301:
        raise ValueError('Supply 1..301 continuous query amounts')
    ref = model['reference_dose']
    points = np.r_[ref, a]
    lo, hi = model['dose_domain']
    observed_lo, observed_hi = model['state']['observed_domain']
    out = dict(schema='b1.research-smoothing-spline-query.v1',
               method=model['method'], status=model['status'], refitted=False,
               task=model['task'], population_scope=model['population_scope'],
               output_scope=model['output_scope'], curve=None, diagnostics=None)
    if np.any((points < lo) | (points > hi) | (points < observed_lo) | (points > observed_hi)):
        out.update(status='unsupported', reason='query_or_reference_beyond_observed_compensation_support')
        return out
    diagnostics, failed = _local_support(
        np.asarray(model['X']), np.asarray(model['dose']),
        np.asarray(model['users'], dtype=object), points,
        model['baseline_bandwidth'], np.asarray(model['stabilized_weight']),
        _config(model['configuration']))
    out['diagnostics'] = dict(by_dose=diagnostics, unsupported_doses=failed,
                              support_bandwidth=model['baseline_bandwidth'])
    if failed:
        out.update(status='unsupported', reason='insufficient_local_support')
        return out
    mean = spline_query(model['state'], a)
    reference_mean = float(spline_query(model['state'], np.array([ref]))[0])
    out['curve'] = dict(
        incentive_values=a.tolist(), reference_incentive=ref,
        mean_outcomes=mean.tolist(), contrasts=(mean - reference_mean).tolist(),
        outcome_unit=model['task']['outcome_unit'], incentive_unit=model['incentive_unit'],
        continuous_query_evaluated_directly=True, shape_constraint='none',
        interpretation=('causal conditional on declarations' if model['status'] == 'causal'
                        else 'standardized association'),
    )
    return out
