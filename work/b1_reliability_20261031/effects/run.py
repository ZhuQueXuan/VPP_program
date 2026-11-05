"""Sequential phase-two selection, frozen test fits, then evaluator-only scoring.

Invoke only after root declares phase one complete. Selection reads positive
validation measurements only. Test fits finish and are saved before evaluation
imports the old simulator potential-outcome function or opens evaluator truth.
"""
from pathlib import Path
import os
for _key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[_key] = '1'
import sys
import hashlib
import json
import time
import traceback
import numpy as np
from scipy.stats import t as student_t

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
STUDY = HERE.parent/'study/continuous'
sys.path.insert(0, str(ROOT/'B1算法'))
from b1_algorithm.factors import EVFactorStudy, _inputs
from b1_algorithm.effects.continuous import fit_continuous_effects
from b1_algorithm.effects.tuning import (select_continuous_tuning,
    describe_continuous_tuning, save_continuous_tuning, load_continuous_tuning,
    fit_tuned_continuous_effects, fit_tuned_continuous_model)
from b1_algorithm.effects.frozen import (save_continuous_model,
    query_continuous_model)

PROTOCOL_SHA = 'd095a56114f34f6d827e708a8f063b4dd758c5b113abc222f73f259e72cf3749'
ASSUMPTIONS = dict(pre_treatment_X=True, consistent_treatment=True,
    no_interference=True, same_outcome_definition=True,
    conditional_exchangeability=True, randomized_assignment=False)
COVARIATES = ('deadline_slack', 'demand_urgency')
STUDY_DEFINITION = EVFactorStudy('B1-reliability-continuous-30min-q1.5', '元/千瓦时',
    covariates=COVARIATES, outcome_name='cumulative_response_seconds',
    outcome_source='selected_curve')
SELECTION = HERE/'selection.json'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump_new(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, allow_nan=False, separators=(',', ':'))


def protocol():
    path = HERE.parent/'protocol.json'
    if sha(path) != PROTOCOL_SHA:
        raise RuntimeError('central frozen protocol identity changed')
    return read(path)['continuous_after_reliability']


def source_identity():
    paths = [ROOT/'B1算法/b1_algorithm'/name for name in (
        'effects/tuning.py', 'effects/continuous.py', 'effects/frozen.py',
        'effects/core.py', 'effects/validation.py', 'factors.py', 'contracts.py')]
    paths.extend([HERE/'run.py', HERE/'selection_design.json', HERE.parent/'protocol.json',
                  ROOT/'work/b1_ev_mainline_20261030/simulation.py',
                  HERE.parent/'study/models/reliable_reference.json'])
    return {p.relative_to(ROOT).as_posix(): sha(p) for p in paths}


def assert_identity(identity):
    now = source_identity()
    if identity != now:
        raise RuntimeError('frozen source identity changed: '+str(
            [k for k in sorted(set(identity)|set(now)) if identity.get(k) != now.get(k)]))


def measurements(phase, seed, scenario, expected_users):
    ep = STUDY/phase/'events'/f'{seed}_{scenario}.json'
    fp = STUDY/phase/'factor_inputs'/f'{seed}_{scenario}.json'
    events, factors = read(ep), read(fp)
    # The study interface is a list of original factor records, not selected X.
    if not isinstance(factors, list):
        raise ValueError('factor input artifact must be an unfiltered record list')
    data = _inputs(events, factors, STUDY_DEFINITION)
    if len(events) != expected_users*2 or len(set(data['users'])) != expected_users:
        raise ValueError('protocol event/user counts differ; cannot discard failed events')
    if data['design']['identification']['used_covariates'] != list(COVARIATES):
        raise ValueError('L/U adjustment must remain present and ordered')
    if data['X'].shape != (len(events), 2) or set(data['methods']) != {'CPOP'}:
        raise ValueError('two original confounders and common original CPOP outcomes required')
    if not np.allclose(data['signature'], [30., 1.5, 1., .1, 30., 15., 15.], rtol=0, atol=1e-8):
        raise ValueError('frozen physical task/meter/outcome definition differs')
    reference_id = read(HERE.parent/'study/models/reliable_reference.json')['model_id']
    if any(event['reference']['model_id'] != reference_id for event in events):
        raise ValueError('all outcomes must use the same new frozen reference model')
    if any(t['task_pre_treatment'] is not True for t in data['tasks']):
        raise ValueError('all tasks must be fixed before treatment')
    context = dict(task_id=STUDY_DEFINITION.study_id,
        outcome_name=STUDY_DEFINITION.outcome_name, outcome_unit='seconds',
        target_population=STUDY_DEFINITION.target_population,
        window_minutes=[0., 30.], q_kw=1.5, task_pre_treatment=True,
        reference_status=data['reference_status']+';model_id='+reference_id,
        reference_uncertainty='not_propagated')
    times = dict(first_notice_min=min(t['notice_min'] for t in data['tasks']),
        final_label_available_min=max(t['end_min']+15. for t in data['tasks']))
    artifacts = {p.relative_to(ROOT).as_posix(): sha(p) for p in (ep, fp)}
    return data, context, times, artifacts


def fixed_options(p, task):
    return dict(dose_domain=p['domain'], grid=p['grid'], reference_dose=p['reference_dose'],
        incentive_unit=STUDY_DEFINITION.incentive_unit, task=task,
        continuous_assignment=True, assumptions=ASSUMPTIONS)


def select():
    p = protocol()
    tick = time.perf_counter()
    data, task, times, inputs = measurements('validation', p['validation_seed'], 'positive', p['validation_users'])
    cfg = dict(seed=p['validation_seed'], n_boot=199)
    chosen = select_continuous_tuning(data['X'], data['D'], data['y'], data['users'],
        **fixed_options(p, task), config=cfg, covariate_names=COVARIATES,
        validation_id='positive-validation-'+str(p['validation_seed']),
        validation_completed_at_min=times['final_label_available_min'],
        selection_cutoff_min=times['final_label_available_min'])
    save_continuous_tuning(chosen, SELECTION)
    restored = load_continuous_tuning(SELECTION)
    if restored != chosen:
        raise AssertionError('selection save/load changed payload')
    description = describe_continuous_tuning(chosen)
    dump_new(HERE/'selection_description.json', description)
    receipt = dict(stage='continuous_selection', selection_id=chosen.sha256,
        status=description['status'], selected=description['selected'],
        validation_seed=p['validation_seed'], validation_scenario='positive',
        test_scenarios_share_one_selection=True, validation_truth_read=False,
        test_inputs_opened=False, validation_times=times, inputs=inputs,
        selection_artifact_sha256=sha(SELECTION), sources=source_identity(),
        seconds=time.perf_counter()-tick)
    dump_new(HERE/'selection_receipt.json', receipt)
    print(json.dumps(receipt, ensure_ascii=False), flush=True)


def fit_tests():
    p = protocol()
    selected = load_continuous_tuning(SELECTION)
    receipt = read(HERE/'selection_receipt.json')
    assert_identity(receipt['sources'])
    if sha(SELECTION) != receipt['selection_artifact_sha256']:
        raise RuntimeError('selection artifact changed after freeze')
    rows = []
    start = time.perf_counter()
    for seed in p['test_seeds']:
        positive_design = None
        for scenario in p['scenarios']:
            tick = time.perf_counter()
            identity = dict(seed=seed, scenario=scenario)
            try:
                data, task, times, inputs = measurements('test', seed, scenario, p['test_users'])
                current_design = dict(X=data['X'].tolist(), D=data['D'].tolist(), users=data['users'])
                if positive_design is None:
                    positive_design = current_design
                elif current_design != positive_design:
                    raise ValueError('paired positive/zero facts do not share X/D/users')
                options = fixed_options(p, task)
                baseline = fit_continuous_effects(data['X'], data['D'], data['y'], data['users'],
                    **options, config=dict(seed=seed, n_boot=199))
                dump_new(HERE/'test/results'/f'{seed}_{scenario}_default.json', baseline)
                tuned = fit_tuned_continuous_effects(selected, data['X'], data['D'], data['y'], data['users'],
                    **options, covariate_names=COVARIATES, evaluation_seed=seed,
                    evaluation_notice_min=times['first_notice_min'])
                dump_new(HERE/'test/results'/f'{seed}_{scenario}_selected.json', tuned)
                output_paths = [HERE/'test/results'/f'{seed}_{scenario}_{label}.json'
                                for label in ('default', 'selected')]
                frozen = None
                if tuned['status'] in ('causal', 'association'):
                    model = fit_tuned_continuous_model(selected, data['X'], data['D'], data['y'], data['users'],
                        **options, covariate_names=COVARIATES, evaluation_seed=seed,
                        evaluation_notice_min=times['first_notice_min'])
                    model_path = HERE/'test/models'/f'{seed}_{scenario}.json'
                    model_path.parent.mkdir(parents=True, exist_ok=True)
                    save_continuous_model(model, model_path)
                    query = query_continuous_model(model, p['grid'])
                    dump_new(HERE/'test/queries'/f'{seed}_{scenario}.json', query)
                    output_paths.extend([model_path, HERE/'test/queries'/f'{seed}_{scenario}.json'])
                    expected = tuned['causal_curve'] or tuned['standardized_association']
                    if query['status'] != tuned['status'] or query['curve']['contrasts'] != expected['contrasts']:
                        raise AssertionError('frozen query differs from selected core fit')
                    frozen = dict(model_id=model.sha256, query_exact=True,
                                  artifact_sha256=sha(model_path))
                rows.append(dict(**identity, status='fitted', baseline_status=baseline['status'],
                    selected_status=tuned['status'], events=len(data['y']), users=len(set(data['users'])),
                    input_measurements_sha256=inputs, times=times, frozen=frozen,
                    result_artifacts_sha256={path.relative_to(ROOT).as_posix(): sha(path) for path in output_paths},
                    seconds=time.perf_counter()-tick, evaluation_truth_read=False,
                    evidence_decision_filter_used=False, post_treatment_adjustment_used=False))
            except Exception as exc:
                error = dict(**identity, status='exception', error=str(exc),
                             traceback=traceback.format_exc(), seconds=time.perf_counter()-tick)
                dump_new(HERE/'test/failures'/f'{seed}_{scenario}.json', error)
                rows.append(error)
            print(json.dumps(rows[-1], ensure_ascii=False), flush=True)
    assert_identity(receipt['sources'])
    final = dict(stage='continuous_test_fits', selection_id=selected.sha256,
        all_fits_saved_before_truth_read=True, expected_contexts=16, contexts=rows,
        sources=receipt['sources'], seconds=time.perf_counter()-start)
    dump_new(HERE/'test_fit_receipt.json', final)


def _truth_path(seed, scenario):
    # The study agent stores sealed truth alongside the matching phase.
    alternatives = [STUDY/'test/evaluator'/f'{seed}_{scenario}_truth.json',
                    STUDY/'evaluator'/f'{seed}_{scenario}_truth.json']
    matches = [path for path in alternatives if path.is_file()]
    if len(matches) != 1:
        raise ValueError('exactly one sealed evaluator truth artifact required: '+str(alternatives))
    return matches[0]


def _curve_row(result, truth, seed, scenario, label):
    row = dict(seed=seed, scenario=scenario, method=label, status=result['status'],
        curve_rmse_seconds=None, maximum_absolute_error_seconds=None,
        comparators={}, reasons=result.get('reasons'))
    if result['status'] == 'causal':
        error = np.asarray(result['causal_curve']['contrasts'])-truth
        row.update(curve_rmse_seconds=float(np.sqrt(np.mean(error**2))),
                   maximum_absolute_error_seconds=float(np.max(abs(error))))
        for name, curve in result['comparators'].items():
            row['comparators'][name] = float(np.sqrt(np.mean((np.asarray(curve['contrasts'])-truth)**2)))
        band = result['inference']
        row['all_grid_truth_in_conditional_band'] = bool(np.all((truth >= band['lower']) & (truth <= band['upper'])))
    return row


def _difference_summary(rows):
    out = {}
    for scenario in ('positive', 'zero', 'equal_scenario_pooled'):
        differences = []
        base, selected = [], []
        for seed in protocol()['test_seeds']:
            cases = [r for r in rows if r['seed'] == seed and
                     (scenario == 'equal_scenario_pooled' or r['scenario'] == scenario)]
            expected = 4 if scenario == 'equal_scenario_pooled' else 2
            if len(cases) != expected or any(r['curve_rmse_seconds'] is None for r in cases):
                continue
            b = float(np.sqrt(np.mean([r['curve_rmse_seconds']**2 for r in cases if r['method'] == 'default'])))
            s = float(np.sqrt(np.mean([r['curve_rmse_seconds']**2 for r in cases if r['method'] == 'selected'])))
            base.append(b)
            selected.append(s)
            differences.append(s-b)
        if differences:
            n = len(differences)
            mean = float(np.mean(differences))
            half = float(student_t.ppf(.975, n-1)*np.std(differences, ddof=1)/np.sqrt(n)) if n > 1 else None
            out[scenario] = dict(complete_paired_seed_blocks=n, expected_seed_blocks=8,
                default_mean_RMSE_seconds=float(np.mean(base)),
                selected_mean_RMSE_seconds=float(np.mean(selected)),
                paired_difference_mean_seconds=mean,
                paired_difference_MC95=None if half is None else [mean-half, mean+half],
                blocks_selected_lower=int(np.count_nonzero(np.asarray(differences) < 0)),
                block_differences_seconds=differences,
                inference_unit='independent_simulation_seed_block',
                pooled_rule='within seed, equal scenario mean squared errors then square root; report mean across seed blocks',
                interval_is_real_world_causal_CI=False)
        else:
            out[scenario] = dict(complete_paired_seed_blocks=0, expected_seed_blocks=8,
                                 reason='no complete supported paired blocks')
    return out


def evaluate():
    p = protocol()
    fits = read(HERE/'test_fit_receipt.json')
    if fits['all_fits_saved_before_truth_read'] is not True or len(fits['contexts']) != 16:
        raise RuntimeError('all sixteen planned test contexts must finish before evaluator truth opens')
    assert_identity(fits['sources'])
    for context in fits['contexts']:
        for path, expected in context.get('result_artifacts_sha256', {}).items():
            if sha(ROOT/path) != expected:
                raise RuntimeError('saved test fit changed before evaluation: '+path)
    # This import and every evaluator truth read occur only after frozen fits.
    sys.path.insert(0, str(ROOT/'work/b1_ev_mainline_20261030'))
    from simulation import potential_outcome
    rows, evaluator_ids = [], {}
    for seed in p['test_seeds']:
        for scenario in p['scenarios']:
            truth_path = _truth_path(seed, scenario)
            truth = read(truth_path)
            events = read(STUDY/'test/events'/f'{seed}_{scenario}.json')
            if len(truth) != p['test_users']*2 or len(truth) != len(events):
                raise ValueError('truth/event count mismatch; cannot score selected rows')
            if any(event['task']['task_id'] != t['task_id'] or event['task']['user_id'] != t['user_id']
                   for event, t in zip(events, truth)):
                raise ValueError('truth/event identity/order mismatch')
            evaluator_ids[truth_path.relative_to(ROOT).as_posix()] = sha(truth_path)
            values = np.array([np.mean([potential_outcome(float(a), event)['cumulative_response_seconds']
                                        for event in truth]) for a in p['grid']])
            reference = float(np.mean([potential_outcome(p['reference_dose'], event)['cumulative_response_seconds']
                                       for event in truth]))
            contrast = values-reference
            dump_new(HERE/'evaluation/truth_curves'/f'{seed}_{scenario}.json',
                dict(mean=values.tolist(), contrasts=contrast.tolist(), reference_dose=p['reference_dose'],
                     evaluator_only=True, passed_to_selector_or_fitter=False))
            for method in ('default', 'selected'):
                path = HERE/'test/results'/f'{seed}_{scenario}_{method}.json'
                if path.is_file():
                    result = read(path)
                else:
                    result = dict(status='exception', reasons=['test context failed; all cases retained'])
                rows.append(_curve_row(result, contrast, seed, scenario, method))
    result = dict(stage='continuous_evaluation', selection_id=fits['selection_id'],
        scores=rows, paired_summary=_difference_summary(rows), evaluator_artifacts=evaluator_ids,
        source_identity=fits['sources'], default_status_counts={s:sum(r['method'] == 'default' and r['status'] == s for r in rows) for s in sorted({r['status'] for r in rows})},
        selected_status_counts={s:sum(r['method'] == 'selected' and r['status'] == s for r in rows) for s in sorted({r['status'] for r in rows})},
        measurement_estimand='effect on common reference/CPOP measured outcome, all invited events',
        truth_evaluation_target='latent simulated duration effect; reference/process and estimator error jointly contribute',
        selection_changed_after_test=False, new_causal_estimator=False,
        limitations=['validation positive only; zero is held-out transfer evaluation',
            'only eight independent seed blocks; paired positive/zero facts are not independent blocks',
            'conditional bands omit tuning, nuisance, reference/process errors; not coverage certification'])
    dump_new(HERE/'assessment.json', result)
    print(json.dumps({k: v for k, v in result.items() if k not in ('scores', 'source_identity', 'evaluator_artifacts')}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=('select', 'test', 'evaluate'), required=True)
    parser.add_argument('--start', action='store_true')
    args = parser.parse_args()
    if not args.start:
        raise SystemExit('main continuous stages require root start after phase one is complete')
    {'select': select, 'test': fit_tests, 'evaluate': evaluate}[args.stage]()
