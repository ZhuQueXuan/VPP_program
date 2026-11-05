"""Read-only numerical replay and independent weighted-line scoring audit."""
import os
for name in ('OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'OMP_NUM_THREADS'):
    os.environ[name] = '1'
from pathlib import Path
import sys
import json
import hashlib
import numpy as np
from scipy.stats import t as student_t

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run
from b1_algorithm.effects.continuous import _crossfit, _config
from b1_algorithm.effects.tuning import load_continuous_tuning, describe_continuous_tuning
from b1_algorithm.effects.validation import user_ids
from b1_algorithm.effects.frozen import load_continuous_model


def intercept(dose, xi, point, bandwidth):
    centered = dose-point
    design = np.column_stack([np.ones(len(dose)), centered])
    weights = np.exp(-.5*(centered/bandwidth)**2)
    return float(np.linalg.solve(design.T@(weights[:, None]*design),
                                design.T@(weights*xi))[0])


def audit(output):
    out = Path(output)
    out.mkdir(parents=True, exist_ok=False)
    checks = []
    maxima = {}
    def ck(name, flag):
        if not flag:
            raise AssertionError(name)
        checks.append(name)
    def near(name, actual, expected, tolerance=1e-8):
        a, e = np.asarray(actual), np.asarray(expected)
        ck(name+'_shape', a.shape == e.shape)
        difference = float(np.max(abs(a-e))) if a.size else 0.
        maxima[name] = difference
        ck(name, difference <= tolerance)
    p = run.protocol()
    selection = load_continuous_tuning(run.SELECTION)
    choice = describe_continuous_tuning(selection)
    receipt = run.read(HERE/'selection_receipt.json')
    fits = run.read(HERE/'test_fit_receipt.json')
    assessment = run.read(HERE/'assessment.json')
    run.assert_identity(receipt['sources'])
    ck('selection_artifact_identity', run.sha(run.SELECTION) == receipt['selection_artifact_sha256'])
    ck('selection_identity_every_stage', selection.sha256 == fits['selection_id'] == assessment['selection_id'])
    ck('one_positive_only_validation', receipt['validation_scenario'] == 'positive' and
       receipt['validation_truth_read'] is False and receipt['test_inputs_opened'] is False)
    ck('all_16_contexts_saved_before_truth', fits['all_fits_saved_before_truth_read'] is True and len(fits['contexts']) == 16)
    for context in fits['contexts']:
        for path, expected in context['result_artifacts_sha256'].items():
            ck('frozen_file_'+path, run.sha(run.ROOT/path) == expected)
    seen_test_users = set()
    rows = []
    comparison_summaries = {}
    for seed in p['test_seeds']:
        block_users = None
        for scenario in p['scenarios']:
            data, task, times, inputs = run.measurements('test', seed, scenario, p['test_users'])
            users = user_ids(data['users'])
            user_set = set(users)
            ck(f'{seed}_{scenario}_all_events', len(data['y']) == 256 and len(user_set) == 128)
            ck(f'{seed}_{scenario}_validation_disjoint', not user_set & set(choice['validation']['users']))
            ck(f'{seed}_{scenario}_post_selection_notice', times['first_notice_min'] > choice['validation']['selection_cutoff_min'])
            if block_users is None:
                ck(f'{seed}_blocks_user_disjoint', not seen_test_users & user_set)
                seen_test_users |= user_set
                block_users = user_set
            else:
                ck(f'{seed}_paired_users_identical', block_users == user_set)
            truth_curve = run.read(HERE/'evaluation/truth_curves'/f'{seed}_{scenario}.json')
            truth = np.asarray(truth_curve['contrasts'])
            for label in ('default', 'selected'):
                result = run.read(HERE/'test/results'/f'{seed}_{scenario}_{label}.json')
                cfg = _config(result['configuration'])
                ck(f'{seed}_{scenario}_{label}_block_seed', cfg.seed == seed and cfg.n_boot == 199)
                ck(f'{seed}_{scenario}_{label}_causal', result['status'] == 'causal')
                ck(f'{seed}_{scenario}_{label}_grid', result['causal_curve']['incentive_values'] == p['grid'])
                ck(f'{seed}_{scenario}_{label}_same_task', result['task'] == task)
                if label == 'selected':
                    chosen = choice['selected']
                    ck(f'{seed}_{scenario}_fixed_choice', cfg.ridge_alpha == chosen['ridge_alpha'] and cfg.spline_knots == chosen['spline_knots'])
                    rule = 1.06*float(np.std(data['D']))*128**(-.2)
                    near(f'{seed}_{scenario}_cohort_bandwidth', cfg.bandwidth, chosen['bandwidth_scale']*rule, 1e-14)
                    ck(f'{seed}_{scenario}_no_test_selection', result['tuning']['selected_on_evaluation_outcomes'] is False)
                cf = _crossfit(data['X'], data['D'], data['y'], users, cfg, np.array(p['domain']), None)
                xi, weight, folds = cf[:3]
                for group in user_set:
                    ck(f'{seed}_{scenario}_{label}_fold_{group}', len(set(folds[users == group])) == 1)
                h = result['diagnostics']['bandwidth']
                reference = intercept(data['D'], xi, p['reference_dose'], h)
                means = [intercept(data['D'], xi, point, h) for point in p['grid']]
                near(f'{seed}_{scenario}_{label}_independent_WLS_mean', result['causal_curve']['mean_outcomes'], means)
                near(f'{seed}_{scenario}_{label}_independent_WLS_contrast', result['causal_curve']['contrasts'], np.asarray(means)-reference)
                score = float(np.sqrt(np.mean((np.asarray(means)-reference-truth)**2)))
                scored = next(row for row in assessment['scores'] if row['seed'] == seed and row['scenario'] == scenario and row['method'] == label)
                near(f'{seed}_{scenario}_{label}_RMSE', scored['curve_rmse_seconds'], score)
                rows.append(dict(seed=seed, scenario=scenario, method=label, rmse=score))
                for name, curve in result['comparators'].items():
                    risk = float(np.sqrt(np.mean((np.asarray(curve['contrasts'])-truth)**2)))
                    near(f'{seed}_{scenario}_{label}_{name}', scored['comparators'][name], risk)
                    comparison_summaries.setdefault((scenario, label, name), []).append(risk)
                if label == 'selected':
                    model = load_continuous_model(HERE/'test/models'/f'{seed}_{scenario}.json')
                    frozen = json.loads(model.payload_json)
                    near(f'{seed}_{scenario}_frozen_xi', frozen['pseudo_outcome'], xi)
                    near(f'{seed}_{scenario}_frozen_weights', frozen['stabilized_weight'], weight)
                    query = run.read(HERE/'test/queries'/f'{seed}_{scenario}.json')
                    near(f'{seed}_{scenario}_frozen_contrasts', query['curve']['contrasts'], result['causal_curve']['contrasts'], 0.)
                    derivative = []
                    epsilon = 1e-5
                    for point in p['grid']:
                        derivative.append((intercept(data['D'], xi, point+epsilon, h)-intercept(data['D'], xi, point-epsilon, h))/(2*epsilon))
                    near(f'{seed}_{scenario}_true_smooth_derivative', query['sensitivity']['values'], derivative, 1e-4)
    for scenario in ('positive', 'zero', 'equal_scenario_pooled'):
        baseline, tuned = [], []
        for seed in p['test_seeds']:
            cases = [row for row in rows if row['seed'] == seed and (scenario == 'equal_scenario_pooled' or row['scenario'] == scenario)]
            baseline.append(float(np.sqrt(np.mean([row['rmse']**2 for row in cases if row['method'] == 'default']))))
            tuned.append(float(np.sqrt(np.mean([row['rmse']**2 for row in cases if row['method'] == 'selected']))))
        delta = np.asarray(tuned)-baseline
        summary = assessment['paired_summary'][scenario]
        near(scenario+'_baseline_mean', summary['default_mean_RMSE_seconds'], np.mean(baseline))
        near(scenario+'_selected_mean', summary['selected_mean_RMSE_seconds'], np.mean(tuned))
        near(scenario+'_paired_difference', summary['paired_difference_mean_seconds'], np.mean(delta))
        half = student_t.ppf(.975, 7)*np.std(delta, ddof=1)/np.sqrt(8)
        near(scenario+'_MC95', summary['paired_difference_MC95'], [np.mean(delta)-half, np.mean(delta)+half])
        ck(scenario+'_eight_independent_blocks', summary['complete_paired_seed_blocks'] == 8)
    sources = run.source_identity()
    ck('source_unchanged_after_audit', sources == receipt['sources'])
    result = dict(passed=True, checks=len(checks), names=checks,
        maximum_numerical_discrepancy=max(maxima.values()), discrepancies=maxima,
        comparator_mean_RMSE=[dict(scenario=k[0], estimator_configuration=k[1], comparator=k[2],
                                  mean_RMSE_seconds=float(np.mean(values))) for k, values in comparison_summaries.items()],
        seed_blocks=8, paired_contexts=16, estimator_outputs=32,
        no_selection_or_fit_result_changed=True, readonly_replay_not_new_independent_performance_data=True,
        source_identity=sources, selection_id=selection.sha256,
        audit_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    run.dump_new(out/'receipt.json', result)
    print(json.dumps({k: v for k, v in result.items() if k not in ('names', 'discrepancies', 'source_identity')}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    audit(sys.argv[1])
