"""Independent mathematical/leakage fixture; no research dev/final is read."""
from pathlib import Path
import hashlib
import json
import sys

import numpy as np
from scipy.special import expit

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'B1算法'))
sys.path.insert(0, str(HERE))
import nested as N
from b1_algorithm.effects import continuous as C
from b1_algorithm.effects.core import group_folds
from b1_algorithm.effects.validation import user_ids


def main():
    seed = 90345991
    rng = np.random.default_rng(seed)
    users = np.repeat([f'nested-audit-{seed}-user{j:04d}' for j in range(240)], 2)
    x = rng.uniform(-1.0, 1.0, (480, 2))
    d = 2.4 * expit(0.35 * x[:, 0] - 0.3 * x[:, 1] + 1.3 * rng.normal(size=480))
    y = 250.0 + 130.0 * d + 40.0 * x[:, 0] - 30.0 * x[:, 1] + rng.normal(0.0, 15.0, 480)
    cfg = C.ContinuousEffectConfig(seed=seed, n_boot=99)
    domain = np.array([0.0, 2.4])
    ids = user_ids(users)
    fold = group_folds(ids, 3, seed)
    v = fold == 0
    t = ~v
    assert not set(ids[t]) & set(ids[v])

    def external(yv):
        return N.external_pseudo(x[t], d[t], y[t], users[t],
                                 x[v], d[v], yv, users[v], config=cfg, outer_fold=0)

    before = external(y[v])
    shift = 37.0
    after = external(y[v] + shift)
    unchanged_keys = ['outcome_prediction', 'marginal_outcome_prediction', 'stabilized_weight',
                      'observed_dose_density', 'marginal_dose_density', 'gps_residual_sd']
    assert all(before[k] == after[k] for k in unchanged_keys)
    delta_error = float(np.max(np.abs(
        np.asarray(after['pseudo_outcome']) - before['pseudo_outcome']
        - shift * np.asarray(before['stabilized_weight']))))
    assert delta_error < 1e-10
    train_before = C._crossfit(x[t], d[t], y[t], ids[t], cfg, domain, None)
    train_after = C._crossfit(x[t], d[t], y[t], ids[t], cfg, domain, None)
    assert np.array_equal(train_before[0], train_after[0])
    dt = d[t]
    comparable = (d[v] >= dt.min()) & (d[v] <= dt.max())
    h = 1.06 * np.std(dt) * len(set(ids[t])) ** (-0.2)
    sb = N.spline_state(dt, train_before[0], 1e-4)
    sa = N.spline_state(dt, train_after[0], 1e-4)
    pred_s_before = N.spline_query(sb, d[v][comparable])
    pred_s_after = N.spline_query(sa, d[v][comparable])
    pred_l_before = C.local_linear_weights(dt, d[v][comparable], 2.0 * h) @ train_before[0]
    pred_l_after = C.local_linear_weights(dt, d[v][comparable], 2.0 * h) @ train_after[0]
    assert np.array_equal(pred_s_before, pred_s_after)
    assert np.array_equal(pred_l_before, pred_l_after)

    # Make one public implementation fold have exactly T as its training set.
    # The other fold is not part of the asserted equality. Inner GPS splits
    # remain the official grouped implementation with seed+fold+130.
    xx = np.r_[x[t], x[v]]
    dd = np.r_[d[t], d[v]]
    yy = np.r_[y[t], y[v]]
    uu = np.r_[ids[t], ids[v]]
    nt = int(t.sum())
    original_group_folds = C.group_folds

    def fixed_outer(groups, n_folds, split_seed):
        if n_folds == 3 and split_seed == cfg.seed and np.array_equal(groups, uu):
            return np.r_[np.ones(nt, dtype=int), np.zeros(int(v.sum()), dtype=int)]
        return original_group_folds(groups, n_folds, split_seed)

    try:
        C.group_folds = fixed_outer
        official = C._crossfit(xx, dd, yy, uu, cfg, domain, None)
        yy_shifted = yy.copy()
        yy_shifted[nt:] += shift
        official_shifted = C._crossfit(xx, dd, yy_shifted, uu, cfg, domain, None)
    finally:
        C.group_folds = original_group_folds
    equivalence = {}
    for key, index in [('pseudo_outcome', 0), ('stabilized_weight', 1),
                       ('outcome_prediction', 4), ('observed_dose_density', 5)]:
        equivalence[key] = float(np.max(np.abs(np.asarray(before[key]) - official[index][nt:])))
        assert equivalence[key] < 1e-10
    assert np.array_equal(official[4][nt:], official_shifted[4][nt:])
    assert np.array_equal(official[1][nt:], official_shifted[1][nt:])

    # Count the complete nested pipeline's T-only cross-fits and external fits.
    original_crossfit = C._crossfit
    original_external = N.external_pseudo
    calls = dict(training_crossfit=0, external_pseudo=0)

    def counted_crossfit(*args, **kwargs):
        calls['training_crossfit'] += 1
        return original_crossfit(*args, **kwargs)

    def counted_external(*args, **kwargs):
        calls['external_pseudo'] += 1
        return original_external(*args, **kwargs)

    try:
        C._crossfit = counted_crossfit
        N.external_pseudo = counted_external
        result = N.select_nested_alpha(x, d, y, users, config=cfg)
    finally:
        C._crossfit = original_crossfit
        N.external_pseudo = original_external
    assert calls == dict(training_crossfit=3, external_pseudo=3)
    assert result['status'] == 'selected', result['failures']
    assert sorted(i for f in result['folds'] for i in f['validation_indices']) == list(range(len(y)))
    for row in result['folds']:
        assert not set(row['training_users']) & set(row['validation_users'])
        assert row['training_users'] == row['external']['training_users']
        assert row['validation_users'] == row['external']['validation_users']
        assert row['external']['gps_inner_seed'] == seed + row['fold'] + 130
    held = result['heldout']
    valid = np.array(held['common_valid_mask'], dtype=bool)
    ps = np.array(held['pred_spline'], dtype=float)[valid]
    pl = np.array(held['pred_LL2'], dtype=float)[valid]
    target = np.array(held['pseudo_outcome'], dtype=float)[valid]
    difference = ps - pl
    independent_alpha = float(np.clip((difference @ (target - pl)) / (difference @ difference), 0.0, 1.0))
    assert independent_alpha == result['alpha'] == result['raw_alpha_S']
    grid = np.linspace(0.0, 1.0, 1001)
    grid_losses = np.mean((target[None, :] - (grid[:, None] * ps + (1 - grid[:, None]) * pl)) ** 2, axis=1)
    selected_loss = np.mean((target - (result['alpha'] * ps + (1 - result['alpha']) * pl)) ** 2)
    assert selected_loss <= float(grid_losses.min()) + 1e-9

    # A failed validation nuisance fit must keep S, even when other folds fit.
    def fail_one_external(*args, **kwargs):
        if kwargs['outer_fold'] == 1:
            raise ValueError('microaudit deliberately failed external density support')
        return original_external(*args, **kwargs)

    try:
        N.external_pseudo = fail_one_external
        fallback = N.select_nested_alpha(x, d, y, users, config=cfg)
    finally:
        N.external_pseudo = original_external
    assert fallback['status'] == 'fallback_retained_spline'
    assert fallback['alpha'] == fallback['raw_alpha_S'] == 1.0
    assert len(fallback['folds']) == 3 and len(fallback['failures']) == 1
    assert fallback['failures'][0]['fold'] == 1
    json.dumps(result, allow_nan=False)
    json.dumps(fallback, allow_nan=False)

    summary = dict(
        status='passed', fixture_seed=seed, simulated_fixture_users=240,
        simulated_fixture_events=480, research_dev_or_final_generated=False,
        old_confirmation_read=False, validation_outcome_shift=shift,
        unchanged_training_pseudo_outcomes=True,
        unchanged_training_only_external_mu_weights_and_densities=True,
        unchanged_validation_component_predictions=True,
        validation_pseudo_outcome_shift_equals_weight_times_shift_max_error=delta_error,
        external_vs_official_custom_fold_max_errors=equivalence,
        gps_inner_seed_rule='cfg.seed + outer_fold + 130',
        complete_pipeline_call_counts=calls,
        complete_users_disjoint_in_every_outer_fold=True,
        every_event_held_out_once=True,
        observed_dose_level_risk_not_contrast_risk=True,
        fixture_selected_alpha=result['alpha'],
        fixture_valid_events=int(valid.sum()),
        analytic_quadratic_alpha_exact=True,
        analytic_loss_no_greater_than_1001_point_grid=True,
        forced_failed_fold_keeps_all_spline=True,
        forced_failed_fold_recorded=True,
        json_contains_no_nan=True,
        nested_source_sha256=hashlib.sha256((HERE / 'nested.py').read_bytes()).hexdigest(),
    )
    with (HERE / 'audit_nested.json').open('x', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2, allow_nan=False)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
