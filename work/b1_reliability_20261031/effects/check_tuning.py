"""Small numerical/contract checks; never consumes the phase-two main seeds."""
import os
for name in ('OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'OMP_NUM_THREADS'):
    os.environ[name] = '1'
import sys
from pathlib import Path
import dataclasses
import hashlib
import json
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'B1算法'))
from b1_algorithm.effects import tuning as t
from b1_algorithm.effects.continuous import (ContinuousEffectConfig,
    fit_continuous_effects, _crossfit, local_linear_weights)
from b1_algorithm.effects.frozen import query_continuous_model


def run(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    checks = []
    def check(name, flag):
        if not flag:
            raise AssertionError(name)
        checks.append(name)
    def rejects(name, action):
        try:
            action()
        except (ValueError, TypeError, KeyError, OverflowError, OSError, dataclasses.FrozenInstanceError):
            checks.append(name)
        else:
            raise AssertionError('not rejected: '+name)
    def sample(seed, nusers, label):
        rng = np.random.default_rng(seed)
        users = np.repeat([label+str(i) for i in range(nusers)], 2)
        x = rng.normal(0, .3, (2*nusers, 2))
        d = rng.uniform(.001, 2.399, 2*nusers)
        y = 200+40*np.sin(d*1.7)+12*x[:, 0]-8*x[:, 1]+rng.normal(0, 5, len(d))
        return x, d, y, users
    X, D, Y, users = sample(291002, 120, 'validation-')
    task = dict(task_id='numerical_control', outcome_name='cumulative_response_seconds',
        outcome_unit='seconds', target_population='all_invited_events', window_minutes=[0., 30.],
        q_kw=1.5, task_pre_treatment=True, reference_status='control_measured_reference',
        reference_uncertainty='not_propagated')
    assumptions = dict(pre_treatment_X=True, consistent_treatment=True,
        no_interference=True, same_outcome_definition=True,
        randomized_assignment=True, conditional_exchangeability=None)
    context = dict(dose_domain=[0., 2.4], grid=[.4, .8, 1.2, 1.6, 2.],
        reference_dose=.8, incentive_unit='declared_currency_per_event', task=task,
        continuous_assignment=True, assumptions=assumptions,
        known_density=np.repeat(1/2.4, len(Y)))
    selection = t.select_continuous_tuning(X, D, Y, users,
        **context, validation_id='control-only', validation_completed_at_min=100.,
        selection_cutoff_min=101., config=ContinuousEffectConfig(n_boot=99, seed=23))
    p = t.describe_continuous_tuning(selection)
    check('selection_supported', p['status'] == 'selected')
    check('all_nuisance_candidates_kept', len(p['nuisance_candidates']) == 4)
    check('all_bandwidth_candidates_kept', len(p['bandwidth_candidates']) == 4)
    check('no_new_estimator_claim', p['new_causal_estimator'] is False)
    canonical = t.user_ids(users)
    cfg = t._config(p['base_configuration'])
    for row in p['nuisance_candidates']:
        candidate = dataclasses.replace(cfg, ridge_alpha=row['ridge_alpha'], spline_knots=row['spline_knots'])
        cf = _crossfit(X, D, Y, canonical, candidate, np.array([0., 2.4]), context['known_density'])
        check('original_OOF_risk_'+str(row['ridge_alpha'])+'_'+str(row['spline_knots']),
              row['risk'] == float(np.mean((Y-cf[4])**2)))
    selected = p['selected']
    candidate = dataclasses.replace(cfg, ridge_alpha=selected['ridge_alpha'], spline_knots=selected['spline_knots'])
    xi, weights, _, _, _, _ = _crossfit(X, D, Y, canonical, candidate,
                                      np.array([0., 2.4]), context['known_density'])
    row = next(r for r in p['bandwidth_candidates'] if r['bandwidth_scale'] == selected['bandwidth_scale'])
    h = row['validation_bandwidth']
    predicted = np.empty(len(Y))
    for group in np.unique(canonical):
        held = canonical == group
        predicted[held] = local_linear_weights(D[~held], D[held], h)@xi[~held]
    check('manual_whole_user_heldout_risk', row['risk'] == float(np.mean((xi-predicted)**2)))
    fit_path = output/'selection.json'
    t.save_continuous_tuning(selection, fit_path)
    loaded = t.load_continuous_tuning(fit_path)
    check('selection_save_load_exact', loaded == selection)
    rejects('no_overwrite_saved_selection', lambda: t.save_continuous_tuning(selection, fit_path))
    detached = t.describe_continuous_tuning(selection)
    detached['selected']['bandwidth_scale'] = 999
    check('detached_payload_cannot_mutate', t.describe_continuous_tuning(selection)['selected'] == selected)
    rejects('frozen_dataclass', lambda: setattr(selection, 'sha256', 'changed'))
    rejects('checksum_rejects_modified_payload', lambda: t.describe_continuous_tuning(
        t.TuningSelection(selection.payload_json+' ', selection.sha256)))
    def forged(edit):
        z = json.loads(selection.payload_json)
        edit(z)
        serialized = t._json(z)
        return t.TuningSelection(serialized, hashlib.sha256(serialized.encode()).hexdigest())
    rejects('finite_payload', lambda: t.describe_continuous_tuning(forged(
        lambda z: z.update(late_metadata=float('nan')))))
    rejects('bool_selected_alpha', lambda: t.describe_continuous_tuning(forged(
        lambda z: z['selected'].update(ridge_alpha=True))))
    rejects('float_selected_knots', lambda: t.describe_continuous_tuning(forged(
        lambda z: z['selected'].update(spline_knots=4.0))))
    rejects('selection_must_match_risk', lambda: t.describe_continuous_tuning(forged(
        lambda z: z['selected'].update(bandwidth_scale=.75 if selected['bandwidth_scale'] != .75 else 2.))))
    rejects('candidate_table_cannot_drop', lambda: t.describe_continuous_tuning(forged(
        lambda z: z['nuisance_candidates'].pop())))
    rejects('completed_before_cutoff', lambda: t.select_continuous_tuning(X, D, Y, users,
        **context, validation_id='bad-time', validation_completed_at_min=102.,
        selection_cutoff_min=101., config=cfg))
    rejects('strict_bool_X', lambda: t.select_continuous_tuning(np.ones(X.shape, bool), D, Y, users,
        **context, validation_id='bad-X', validation_completed_at_min=100.,
        selection_cutoff_min=101., config=cfg))
    rejects('mixed_zero_atom', lambda: t.select_continuous_tuning(X, np.zeros_like(D), Y, users,
        **context, validation_id='bad-dose', validation_completed_at_min=100.,
        selection_cutoff_min=101., config=cfg))
    rejects('absolute_bandwidth_cannot_replace_rule', lambda: t.select_continuous_tuning(X, D, Y, users,
        **context, validation_id='bad-h', validation_completed_at_min=100.,
        selection_cutoff_min=101., config=dataclasses.replace(cfg, bandwidth=.2)))
    tx, td, ty, tu = sample(291003, 100, 'test-')
    tc = dict(context, known_density=np.repeat(1/2.4, len(ty)))
    application = dict(evaluation_notice_min=102., **tc)
    tuned = t.fit_tuned_continuous_effects(selection, tx, td, ty, tu, **application)
    check('new_user_fit_supported', tuned['status'] == 'causal')
    cohort_h = selected['bandwidth_scale']*t._rule_bandwidth(td, t.user_ids(tu))
    check('cohort_rule_not_validation_h', cohort_h != h and tuned['diagnostics']['bandwidth'] == cohort_h)
    direct = fit_continuous_effects(tx, td, ty, tu, **tc,
        config=dataclasses.replace(candidate, bandwidth=cohort_h))
    check('same_original_estimator_exact_result', tuned['causal_curve'] == direct['causal_curve']
          and tuned['inference'] == direct['inference'] and tuned['comparators'] == direct['comparators'])
    seeded = t.fit_tuned_continuous_effects(selection, tx, td, ty, tu,
        **application, evaluation_seed=291003)
    seeded_direct = fit_continuous_effects(tx, td, ty, tu, **tc,
        config=dataclasses.replace(candidate, bandwidth=cohort_h, seed=291003))
    check('predeclared_evaluation_seed_matches_core', seeded['causal_curve'] == seeded_direct['causal_curve']
          and seeded['inference'] == seeded_direct['inference'])
    rejects('evaluation_seed_strict_integer', lambda: t.fit_tuned_continuous_effects(
        selection, tx, td, ty, tu, **application, evaluation_seed=True))
    model = t.fit_tuned_continuous_model(selection, tx, td, ty, tu, **application)
    frozen = query_continuous_model(model, tc['grid'])
    check('frozen_means_exact', frozen['curve']['mean_outcomes'] == tuned['causal_curve']['mean_outcomes'])
    check('frozen_contrasts_exact', frozen['curve']['contrasts'] == tuned['causal_curve']['contrasts'])
    rejects('whole_original_user_overlap', lambda: t.fit_tuned_continuous_effects(selection, X, D, Y, users,
        evaluation_notice_min=102., **context))
    rejects('notices_must_follow_selection', lambda: t.fit_tuned_continuous_effects(selection, tx, td, ty, tu,
        evaluation_notice_min=101., **tc))
    for field, value in [('dose_domain', [0., 2.5]), ('grid', [.4, .8, 1.2]),
                         ('reference_dose', 1.), ('incentive_unit', 'other_unit')]:
        changed = dict(application, **{field: value})
        rejects('fixed_'+field, lambda changed=changed: t.fit_tuned_continuous_effects(selection, tx, td, ty, tu, **changed))
    altered_task = dict(task, q_kw=2.)
    rejects('fixed_physical_task', lambda: t.fit_tuned_continuous_effects(selection, tx, td, ty, tu,
        **dict(application, task=altered_task)))
    altered_assumptions = dict(assumptions, pre_treatment_X=False)
    rejects('fixed_assumptions', lambda: t.fit_tuned_continuous_effects(selection, tx, td, ty, tu,
        **dict(application, assumptions=altered_assumptions)))
    rejects('cannot_drop_legal_covariate_column', lambda: t.fit_tuned_continuous_effects(selection,
        tx[:, :1], td, ty, tu, **application))
    rejects('cannot_rename_or_reorder_covariate_schema', lambda: t.fit_tuned_continuous_effects(selection,
        tx, td, ty, tu, **dict(application, covariate_names=['U', 'L'])))
    # Canonical normalization is one pass, preserving integer-vs-string identity.
    check('typed_user_identity', t.user_ids([1, '1']).tolist() == ['integer:1', 'string:1'])
    # A smaller task grid is never silently substituted even if supported.
    check('all_grid_points_retained', tuned['causal_curve']['incentive_values'] == context['grid'])
    # A deliberately unsupported dose design keeps all failed candidates.
    rng = np.random.default_rng(291004)
    gap_d = np.r_[rng.uniform(.002, .02, 60), rng.uniform(2.38, 2.398, 60)]
    gap_users = np.repeat(['gap-'+str(i) for i in range(30)], 4)
    gap_context = dict(context, known_density=None,
        assumptions=dict(assumptions, randomized_assignment=False, conditional_exchangeability=True))
    unsupported = t.select_continuous_tuning(np.zeros((120, 2)), gap_d,
        20*gap_d, gap_users, **gap_context, validation_id='gap-control-only',
        validation_completed_at_min=100., selection_cutoff_min=101., config=cfg)
    gap = t.describe_continuous_tuning(unsupported)
    check('unsupported_selection_preserved', gap['status'] == 'unsupported')
    check('unsupported_grid_candidates_all_retained', len(gap['bandwidth_candidates']) == 4
          and all(r['status'] == 'unsupported' for r in gap['bandwidth_candidates']))
    check('oversized_bandwidth_not_clipped', 'bandwidth_exceeds_half_domain_span'
          in gap['bandwidth_candidates'][-1]['reasons'])
    rejects('cannot_apply_unsupported_selection', lambda: t.fit_tuned_continuous_effects(
        unsupported, tx, td, ty, tu, **application))
    receipt = dict(status='passed', checks=len(checks), names=checks,
        selection=selected, nuisance_risk=[r['risk'] for r in p['nuisance_candidates']],
        smoothing_risk=[r['risk'] for r in p['bandwidth_candidates']],
        small_control_only=True, main_validation_or_test_consumed=False)
    (output/'receipt.json').write_text(json.dumps(receipt, indent=2, ensure_ascii=False, allow_nan=False), encoding='utf-8')
    print(json.dumps(receipt, ensure_ascii=False, allow_nan=False))


if __name__ == '__main__':
    run(sys.argv[1])
