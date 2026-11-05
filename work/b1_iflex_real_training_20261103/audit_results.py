"""Independent score and load-only model replay audit of the frozen iFlex study."""
import os
for variable in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[variable] = '1'

import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import joblib
import numpy as np
from models import Design  # needed to deserialize the already fitted objects

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = HERE.parent / 'b1_real_response_data_20261103'
KEY = ('ID', 'Group', 'Date')
TARGET = 'actual_peak_2h_kwh'
checks, issues, errors = Counter(), [], {}

def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))

def table(path):
    with path.open(encoding='utf-8-sig', newline='') as file:
        return list(csv.DictReader(file))

def digest(path, algorithm='sha256'):
    return hashlib.new(algorithm, path.read_bytes()).hexdigest()

def claim(name, ok, detail=None):
    checks[name] += 1
    if not bool(ok):
        issues.append(dict(check=name, detail=detail))

def close(name, actual, expected, tolerance=1e-9):
    a, b = np.asarray(actual, float), np.asarray(expected, float)
    if a.shape != b.shape:
        claim(name, False, [list(a.shape), list(b.shape)])
        return
    error = float(np.max(np.abs(a-b))) if a.size else 0.
    errors[name] = max(errors.get(name, 0.), error)
    claim(name, np.isfinite(error) and error <= tolerance, error)

def compare(name, actual, expected):
    if isinstance(expected, dict):
        claim(name+'_keys', set(actual) == set(expected))
        for k, v in expected.items():
            compare(name, actual[k], v)
    elif isinstance(expected, (int, float)):
        close(name, actual, expected, 1e-9)
    else:
        claim(name, actual == expected)

def key(row):
    return tuple(row[name] for name in KEY)

def average(values):
    return math.fsum(values) / len(values)

def independent_score(rows, prediction):
    observed = [float(row[TARGET]) for row in rows]
    residual = [p-y for p, y in zip(prediction, observed)]

    def summarize(indices):
        return dict(rows=len(indices),
                    rmse=math.sqrt(average([residual[i]**2 for i in indices])),
                    mae=average([abs(residual[i]) for i in indices]),
                    observed_mean=average([observed[i] for i in indices]),
                    prediction_mean=average([prediction[i] for i in indices]),
                    signed_bias=average([residual[i] for i in indices]),
                    dates=len({rows[i]['Date'] for i in indices}))

    def by(fields):
        indices = defaultdict(list)
        for i, row in enumerate(rows):
            indices['|'.join(row[field] for field in fields)].append(i)
        return {group: summarize(ids) for group, ids in sorted(indices.items())}

    dates, groups = by(('Date',)), by(('Date', 'Group'))
    pooled = summarize(range(len(rows)))
    return dict(events=len(rows), dates=len(dates), group_days=len(groups),
                date_equal_rmse=average([record['rmse'] for record in dates.values()]),
                pooled_rmse=pooled['rmse'], mae=pooled['mae'],
                group_day_mean_rmse=math.sqrt(average([record['signed_bias']**2 for record in groups.values()])),
                per_date=dates, per_group_day=groups, per_price=by(('nominal_price_level',)), per_group=by(('Group',)))

protocol = read(HERE/'protocol.json')
freeze = read(HERE/'selection_freeze.json')
decision = read(HERE/'decision.json')
prepared_path = DATA/'prepared_P_events.csv'
prepared = table(prepared_path)
source = {key(row): row for row in prepared}
claim('prepared_exact_roster', len(source) == len(prepared) == 14213)
claim('prepared_outcome_link_hash', digest(prepared_path) == protocol['prepared_data_sha256'])
claim('prepared_protocol_hash', digest(DATA/'real_data_protocol.json') == protocol['data_protocol_sha256'])

def check_predictions(file, split, names):
    rows = table(file)
    roster = [key(row) for row in rows]
    expected = {key(row) for row in prepared if row['split'] == split}
    claim(split+'_prediction_exact_roster', len(roster) == len(set(roster)) == len(expected) and set(roster) == expected)
    claim(split+'_prediction_exact_columns', set(rows[0]) == set(names) | set(KEY) | {'Region','split','nominal_price_level',TARGET})
    for row in rows:
        original = source[key(row)]
        claim(split+'_metadata_link', all(row[k] == original[k] for k in ('Region', 'nominal_price_level', 'split')))
        close(split+'_real_label_link', float(row[TARGET]), float(original[TARGET]), 0.)
    return rows

history = table(HERE/'features_peak_history.csv')
history_by_key = {key(row): row for row in history}
receipt = read(HERE/'peak_history_verification.json')
claim('history_exact_roster', len(history_by_key) == len(history) == 14213 and set(history_by_key) == set(source))
claim('history_receipt_matches_prepared', receipt['prepared_metadata_csv_md5'] == digest(prepared_path, 'md5'))
claim('history_receipt_matches_features', receipt['features_csv_md5'] == digest(HERE/'features_peak_history.csv', 'md5'))
archive = ROOT/'data/public_datasets/挪威_iFlex_动态电价试验/iFlex_dataset.RData'
claim('history_receipt_matches_original_archive', receipt['input_archive_md5'] == digest(archive, 'md5'))
claim('history_source_receipt_counts', receipt['status'] == 'passed' and receipt['source_pairs_total'] == 85278 and receipt['pair_count_distribution'] == {'6': 14213})
claim('history_receipt_cutoffs', receipt['min_notice_minus_pair_end_seconds'] == receipt['min_pair_start_minus_lookback_start_seconds'] == 82800 and not receipt['current_event_outcomes_used'])
for row in history:
    original = source[key(row)]
    pairs = [tuple(map(int, value.split(':'))) for value in row['history_peak_source_pairs'].split(';')]
    current = {int(v) for v in original['event_source_rows'].split(';') if v}
    last = datetime.fromisoformat(row['latest_available_utc'].replace('Z', '+00:00'))
    notice = datetime.fromisoformat(row['notice_utc'].replace('Z', '+00:00'))
    expected_last = datetime.combine(date.fromisoformat(row['Date'])-timedelta(days=2), datetime.min.time(), timezone.utc)+timedelta(hours=18)
    claim('history_join_and_asof', row['split'] == original['split'] and row['notice_utc'] == original['notice_utc'] and last == expected_last and (notice-last).total_seconds() == 82800)
    claim('history_six_source_pairs', int(row['pairs_count']) == len(pairs) == len(set(pairs)) == 6 and all(0 < a < b for a,b in pairs) and pairs == sorted(pairs))
    claim('history_latest_source_and_no_current_overlap', pairs[-1] == (int(row['latest_source_row17']), int(row['latest_source_row18'])) and not current.intersection(i for pair in pairs for i in pair))
    claim('history_feature_finite', math.isfinite(float(row['mean_peak_history_kwh'])))
fixed = receipt['fixed_raw_source_checks']
claim('history_fixed5_source_receipts', Counter(r['split'] for r in fixed) == {'train': 3, 'validation': 2} and all(
    r['source_pairs'] == history_by_key[key(r)]['history_peak_source_pairs'] and
    r['latest_available_utc'] == history_by_key[key(r)]['latest_available_utc'] and
    r['mean_absolute_difference_kwh'] < 1e-12 and r['recent_absolute_difference_kwh'] < 1e-12 for r in fixed))

methods = list(protocol['methods'])
validation = {}
selected_configs = {}
for feature_set in ('base','peak'):
    summary = read(HERE/f'{feature_set}_validation.json')
    columns = [f'{method}__cfg{i}' for method in methods for i in range(4)]
    rows = check_predictions(HERE/f'{feature_set}_validation_predictions.csv', 'validation', columns)
    claim('validation_budget_and_access', len(rows)==2213 and summary['train_events']==9581 and not summary['test_numeric_outcomes_used'])
    validation[feature_set] = {}
    for method in methods:
        trials = []
        configurations = [{'alpha': a} for a in protocol['ridge_alpha_grid']] if method.endswith('ridge') else protocol['hgb_grid']
        for i, parameters in enumerate(configurations):
            name = f'{method}__cfg{i}'
            trial = summary['results'][method]['trials'][i]
            claim('validation_trial_identity', trial['id'] == name and trial['params'] == parameters)
            prediction = [float(row[name]) for row in rows]
            claim('validation_prediction_finite', all(map(math.isfinite, prediction)))
            score = independent_score(rows, prediction)
            compare('validation_score_recomputed', score, trial['score'])
            tie = (-parameters['alpha'],) if 'alpha' in parameters else (parameters['leaves'], -parameters['l2'])
            trials.append(((score['date_equal_rmse'], *tie), name, parameters))
        ranking, name, parameters = min(trials)
        saved = summary['results'][method]['best']
        claim('validation_best_recomputed', saved['id'] == name and saved['params'] == parameters)
        validation[feature_set][method] = ranking[0]
        selected_configs[feature_set+'__'+method] = parameters

def choose(feature_set, allowed):
    return min(allowed, key=lambda method: (validation[feature_set][method], method))

reference = choose('base', ('linear_ridge','spline_ridge'))
base_price = choose('base', protocol['price_aware'])
peak_price = choose('peak', protocol['price_aware'])
feature_set = 'peak' if validation['peak'][peak_price] <= .99*validation['base'][base_price] else 'base'
candidate_method = peak_price if feature_set == 'peak' else base_price
selected = dict(reference='base__'+reference,best_base_price='base__'+base_price,best_peak_price='peak__'+peak_price,
                candidate=feature_set+'__'+candidate_method,
                candidate_no_price_control=feature_set+'__'+('history_hgb' if candidate_method=='price_hgb' else 'history_ridge'))
claim('selection_keys_recomputed', selected == freeze['keys'] == decision['selected'])
claim('selection_parameters_recomputed', selected_configs == freeze['validation_selected_configurations'])
close('selection_base_price_score', freeze['validation_best_price_base'], validation['base'][base_price])
close('selection_peak_price_score', freeze['validation_best_price_peak'], validation['peak'][peak_price])
claim('selection_freeze_test_access_flag', not freeze['test_numeric_outcomes_used'])

formal = read(HERE/'formal_before.json')
actual_formal = {str(p.relative_to(ROOT)):digest(p) for suffix in ('*.py','*.json') for p in (ROOT/'B1算法').rglob(suffix)}
claim('formal61_unchanged', len(formal) == 61 and formal == actual_formal)
old = read(HERE.parent/'b1_curve_stability_20261103'/'retained_before.json')
claim('old_spline376_unchanged', len(old) == 376 and all(digest(HERE.parent/'b1_curve_spline_pilot_20261103'/p) == h for p,h in old.items()))
manifest = read(DATA/'artifact_manifest.json')
claim('all_prepared_artifacts_unchanged', all(digest(DATA/p) == h for p,h in manifest.items()))
originals = read(DATA/'source_before.json')
claim('original_iflex_sources_unchanged', all(digest(ROOT/p) == h for p,h in originals.items()))
for path, value in freeze['hashes'].items():
    claim('selection_frozen_source_or_model_hash', digest(ROOT/path) == value, path)
for name, value in read(HERE/'development_source_freeze.json').items():
    claim('development_source_hash', digest(HERE/name) == value, name)

# Test exists and was scored once before this verifier was authorized to read it.
rows = check_predictions(HERE/'test_predictions.csv', 'test', list(selected_configs))
test_rows = [source[key(row)] for row in rows]
scores = {}
matrices = {}
for name, configuration in selected_configs.items():
    kind, method = name.split('__')
    state = joblib.load(HERE/'frozen_models'/(name+'.joblib'))
    design, model = state['design'], state['model']
    claim('model_frozen_fit_metadata', state['method'] == method and state['params'] == configuration and state['events'] == 11794 and design.augmented == (kind=='peak'))
    claim('preprocessing_fitted_sample_count', int(design.scale.n_samples_seen_) == 11794)
    query_rows = [dict(row, mean_peak_history_kwh=history_by_key[key(row)]['mean_peak_history_kwh']) for row in test_rows] if kind=='peak' else test_rows
    matrix = design.transform(query_rows, method)
    matrices[name] = matrix
    if method.endswith('hgb'):
        parameters = model.get_params()
        claim('HGB_early_stop_disabled', parameters['early_stopping'] is False and model.do_early_stopping_ is False and model.n_iter_ == protocol['hgb_fixed']['max_iter'])
        claim('HGB_fixed_settings', all(parameters[k] == v for k,v in protocol['hgb_fixed'].items()) and parameters['max_leaf_nodes'] == configuration['leaves'] and parameters['l2_regularization'] == configuration['l2'])
    else:
        claim('Ridge_fixed_alpha', model.alpha == configuration['alpha'])
    if method.startswith('history_'):
        perturbed = [dict(row, nominal_price_level='15' if row['nominal_price_level']!='15' else '2') for row in query_rows]
        close('no_price_design_invariant_to_A', matrix, design.transform(perturbed, method), 0.)
    predicted = model.predict(matrix)
    close('load_only_frozen_model_test_prediction', predicted, [float(row[name]) for row in rows], 1e-9)
    scores[name] = independent_score(rows, predicted.tolist())
    compare('test_scores_independently_recomputed', scores[name], decision['all_scores'][name])
for kind in ('base','peak'):
    close('same_matrix_price_HGB_vs_spline_Ridge', matrices[kind+'__price_hgb'], matrices[kind+'__spline_ridge'], 0.)
    close('same_matrix_no_price_HGB_vs_history_Ridge', matrices[kind+'__history_hgb'], matrices[kind+'__history_ridge'], 0.)

candidate, ref = selected['candidate'], selected['reference']
def improvement(before, after):
    old_score, new_score = (scores[name]['date_equal_rmse'] for name in (before, after))
    return dict(before=before,after=after,before_rmse=old_score,after_rmse=new_score,
                absolute_reduction_kwh=old_score-new_score,relative_gain=1-new_score/old_score)

total = improvement(ref, candidate)
wins = sum(scores[candidate]['per_date'][d]['rmse'] < scores[ref]['per_date'][d]['rmse'] for d in scores[ref]['per_date'])
gates = dict(five_date_coverage=scores[candidate]['dates']==5 and scores[candidate]['events']==2419,
             gain_at_least_5pct=total['relative_gain']>=.05,date_wins_at_least4=wins>=4)
claim('test_gates_and_decision', decision['gates']==gates and decision['status']==('real_auxiliary_candidate_confirmed' if all(gates.values()) else 'real_auxiliary_gain_not_confirmed'))
close('test_gain_and_date_wins', [decision['date_equal_rmse_gain'],decision['dates_won']],[total['relative_gain'],wins])
ablation = improvement(selected['candidate_no_price_control'], candidate)
close('same_learner_price_ablation', ablation['relative_gain'], decision['no_price_comparison']['relative_gain'])
switch_learner = improvement('base__spline_ridge','base__price_hgb')
add_history = improvement('base__price_hgb','peak__price_hgb')
close('two_stage_absolute_rmse_decomposition', switch_learner['absolute_reduction_kwh']+add_history['absolute_reduction_kwh'],total['absolute_reduction_kwh'])
coverage = {level: dict(events=len(group),dates=len({r['Date'] for r in group}),group_days=len({(r['Date'],r['Group']) for r in group}))
            for level in sorted({r['nominal_price_level'] for r in rows},key=int)
            for group in [[r for r in rows if r['nominal_price_level']==level]]}
claim('real_test_price_support', list(map(int,coverage))==decision['observed_test_prices']==[2,10,15] and coverage['15']['dates']==1)

result = dict(passed=not issues,issues=issues,checks=dict(checks),total_checks=sum(checks.values()),maximum_errors=errors,
              validation_candidates=40,load_only_frozen_models=10,new_model_fits=0,validation=validation,selected=selected,
              test_scores=scores,test_coverage=coverage,gates=gates,total_candidate_gain=total,dates_won=wins,
              same_base_features_change_learner=switch_learner,same_learner_add_aligned_history=add_history,
              same_aligned_history_HGB_add_price=ablation,original_prepared_artifacts_checked=len(manifest),
              formal_artifacts_checked=61,retained_spline_artifacts_checked=376,original_iflex_sources_checked=len(originals),
              history_events=14213,history_pairs=85278,history_raw_numeric_source_recheck_scope='Five fixed train/validation source-event receipts from native R; all event keys, cutoff timestamps and source pair structure audited.',
              interpretation='Factual forecast of measured peak2h kWh at assigned prices for known households on five later dates. Independently tuned feature/learner comparisons; gains describe predictive pipelines.',
              protocol_secondary_note='Saved scores include per-group signed bias and price calibration. A separate signed-bias stratification by historical peak was not included in the study output.')
encoded = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)
with (HERE/'verification.json').open('x',encoding='utf-8') as file:
    file.write(encoded)
print(json.dumps(dict(passed=result['passed'],checks=result['total_checks'],issues=issues,gain=total['relative_gain'],dates_won=wins),ensure_ascii=True))
if issues:
    raise SystemExit(1)
