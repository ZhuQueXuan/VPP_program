"""Run the frozen charging demo evaluation on new simulated cohorts."""
import hashlib
import json
import os
from pathlib import Path
import sys

for variable in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[variable] = '1'

import numpy as np
from scipy.optimize import brentq
from scipy.special import betaincc
from sklearn.linear_model import Ridge
from sklearn.preprocessing import PolynomialFeatures, SplineTransformer, StandardScaler

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OLD = HERE.parent / 'b1_research_point1_20261103'
sys.path[:0] = [str(OLD), str(ROOT / 'B1算法'), str(OLD / 'runtime/site-packages')]

from study import assumptions, cfg, save, TASK
from data import generate, mean_parts, NAMES
from b1_api import (EVFactorStudy, analyze_events, fit_research_point_one,
                    provided_reference, query_research_point_one, save_research_point_one)
from b1_algorithm.effects.continuous import _design, local_linear_weights, _local_support
from b1_algorithm.effects.frozen import (_payload, fit_continuous_model,
                                         local_linear_derivative_weights)
from b1_algorithm.structure import skeleton_metrics

SPEC = json.loads((HERE / 'protocol.json').read_text(encoding='utf-8'))
DOMAIN = SPEC['domain']
REFERENCE = SPEC['reference_dose']
TARGET = SPEC['target_seconds']
GRID = np.linspace(*SPEC['query_domain'], 17)
SEARCH = np.linspace(*SPEC['query_domain'], 81)


def truth_function(x, kind, rounded=False):
    nodes, weights = np.polynomial.legendre.leggauss(15)
    slack, demand = x[:, 0, None], x[:, 1, None]

    def level(amounts):
        values = []
        for amount in np.atleast_1d(amounts):
            participation, fraction, full = mean_parts(amount, slack, demand, 0.6 * nodes, kind)
            if rounded:
                # E[round(180 * Beta)] is the sum of the 180 tail probabilities.
                boundaries = (np.arange(1, 181) - 0.5) / 180
                fraction = betaincc(20 * fraction[..., None], 20 * (1 - fraction[..., None]),
                                    boundaries).sum(axis=-1) / 180
            values.append(1800 * np.mean((participation * (full + (1 - full) * fraction)) @ (weights / 2)))
        return np.asarray(values)

    return level


def pooled_functions(x, dose, seconds, masks, alpha):
    poly = PolynomialFeatures(2, include_bias=False).fit_transform(x)
    states = StandardScaler().fit_transform(poly)
    spline = SplineTransformer(knots=np.linspace(*DOMAIN, 6)[:, None], degree=3,
                               include_bias=False, extrapolation='error').fit(np.array(DOMAIN)[:, None])
    reg = Ridge(alpha=alpha).fit(_design(states, spline.transform(dose[:, None])), seconds)

    def predict(amounts, mask, derivative=False):
        query = np.atleast_1d(amounts)
        mean_state = np.broadcast_to(states[mask].mean(0), (len(query), states.shape[1]))
        if derivative:
            basis = spline.bsplines_[0](query, nu=1)[:, :-1]
            design = _design(mean_state, basis)
            design[:, :states.shape[1]] = 0
            return design @ reg.coef_
        return reg.predict(_design(mean_state, spline.transform(query[:, None])))

    return [(lambda a, m=m: predict(a, m), lambda a, m=m: predict(a, m, True)) for m in masks]


def incumbent(x, dose, seconds, users, mask, kind, seed):
    try:
        model = fit_continuous_model(x[mask], dose[mask], seconds[mask], users[mask],
            dose_domain=DOMAIN, reference_dose=REFERENCE, incentive_unit='元/千瓦时', task=TASK,
            assumptions=assumptions(kind), config=cfg(seed), continuous_assignment=True,
            known_density=np.full(mask.sum(), 1 / 2.4) if kind == 'randomized' else None)
    except ValueError as exc:
        return None, False, str(exc)
    p, states, observed, pseudo, weights, _, groups, config = _payload(model)
    width = p['bandwidth']
    _, failed = _local_support(states, observed, groups, GRID, width, weights, config)
    if failed:
        return None, False, f'grid support failed at {failed}'
    _, threshold_failed = _local_support(states, observed, groups, SEARCH, width, weights, config)
    return (lambda a: local_linear_weights(observed, np.atleast_1d(a), width) @ pseudo,
            lambda a: local_linear_derivative_weights(observed, np.atleast_1d(a), width) @ pseudo), not threshold_failed, None


def contrast(level, values):
    return level(values) - level([REFERENCE])[0]


def first_crossing(level):
    baseline = level([REFERENCE])[0]
    score = level(SEARCH) - baseline - TARGET
    for i in np.flatnonzero((score[:-1] < 0) & (score[1:] >= 0)):
        return float(brentq(lambda a: level([a])[0] - baseline - TARGET, SEARCH[i], SEARCH[i + 1]))
    return None


def rmse(values):
    return float(np.sqrt(np.mean(np.asarray(values)**2)))


def score_case(x, dose, seconds, users, seed, kind, alphas, rounded=False):
    masks = [np.ones(len(x), bool), x[:, 0] < 0, x[:, 0] >= 0]
    support = [incumbent(x, dose, seconds, users, m, kind, seed) for m in masks]
    levels = [truth_function(x[m], kind, rounded) for m in masks]
    truth = [contrast(fn, GRID) for fn in levels]
    derivative_truth = (levels[0](GRID + .0001) - levels[0](GRID - .0001)) / .0002
    true_crossing = first_crossing(levels[0])
    methods = {'incumbent': [s[0] for s in support]}
    methods.update({str(alpha): pooled_functions(x, dose, seconds, masks, alpha) for alpha in alphas})
    scores = {}
    for name, functions in methods.items():
        curves = [contrast(f[0], GRID) if s[0] is not None else None for f, s in zip(functions, support)]
        row = dict(curves=[c.tolist() if c is not None else None for c in curves],
                   curve_rmse=None, derivative_rmse=None, subgroup_rmse=None,
                   threshold_evaluable=support[0][1], crossing=None)
        if curves[0] is not None:
            row['curve_rmse'] = rmse(curves[0] - truth[0])
            row['derivative_rmse'] = rmse(functions[0][1](GRID) - derivative_truth)
        if curves[1] is not None and curves[2] is not None:
            row['subgroup_rmse'] = rmse((curves[2] - curves[1]) - (truth[2] - truth[1]))
        if row['threshold_evaluable']:
            row['crossing'] = first_crossing(functions[0][0])
        scores[name] = row
    return dict(seed=seed, mechanism=kind, events=len(x), users=len(set(users)),
                group_counts=[int(m.sum()) for m in masks], support_reasons=[s[2] for s in support],
                truth=[c.tolist() for c in truth], true_crossing=true_crossing, scores=scores)


def comparisons(rows, candidate):
    result = {}
    for key in ('curve_rmse', 'subgroup_rmse', 'derivative_rmse'):
        paired = [(r['scores']['incumbent'][key], r['scores'][candidate][key]) for r in rows
                  if r['scores']['incumbent'][key] is not None and r['scores'][candidate][key] is not None]
        counts = [sum(r['scores'][name][key] is not None for r in rows) for name in ('incumbent', candidate)]
        result[key] = dict(outputs=counts, paired=len(paired),
                           paired_means=np.mean(paired, axis=0).tolist() if paired else None)
    for label, name in [('baseline_targets', 'incumbent'), ('candidate_targets', candidate)]:
        valid = [r for r in rows if r['scores'][name]['threshold_evaluable']]
        pairs = [(r['true_crossing'], r['scores'][name]['crossing']) for r in valid]
        errors = [abs(a-b) for a,b in pairs if a is not None and b is not None]
        result[label] = dict(evaluable=len(valid), true_reached=sum(a is not None for a,b in pairs),
            false_reach=sum(a is None and b is not None for a,b in pairs),
            missed=sum(a is not None and b is None for a,b in pairs),
            paired_crossings=len(errors), crossing_mae=float(np.mean(errors)) if errors else None)
    wins = []
    for seed in sorted({r['seed'] for r in rows}):
        pairs = [(r['scores']['incumbent']['curve_rmse'], r['scores'][candidate]['curve_rmse'])
                 for r in rows if r['seed'] == seed and r['scores']['incumbent']['curve_rmse'] is not None]
        if pairs and np.mean(pairs, axis=0)[1] < np.mean(pairs, axis=0)[0]:
            wins.append(seed)
    result['winning_blocks'] = wins
    return result


def fingerprint():
    paths = [HERE / 'protocol.json', Path(__file__), OLD / 'data.py', OLD / 'study.py']
    paths += sorted((ROOT / 'B1算法' / 'b1_algorithm').rglob('*.py'))
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def study(stage):
    freeze = HERE / 'selection.json'
    if stage == 'development':
        alphas = SPEC['candidate_ridge_alpha']
    else:
        selection = json.loads(freeze.read_text(encoding='utf-8'))
        assert selection['source_sha256'] == fingerprint()
        alphas = [selection['alpha']]
    rows = []
    for seed in SPEC[f'{stage}_seeds']:
        for kind in SPEC['mechanisms']:
            d = generate(seed, kind, SPEC['users_per_cohort'], SPEC['events_per_user'])
            rows.append(score_case(*[np.asarray(d[k]) for k in ('X', 'treatment', 'outcome', 'users')],
                                   seed, kind, alphas))
        print(stage, seed, 'complete', flush=True)
    summaries = {str(a): comparisons(rows, str(a)) for a in alphas}
    save(HERE / f'{stage}.json', dict(grid=GRID.tolist(), cohorts=rows, comparisons=summaries))
    if stage == 'development':
        def rank(alpha):
            stat = summaries[str(alpha)]
            return sum(stat[key]['paired_means'][1] / stat[key]['paired_means'][0]
                       for key in ('curve_rmse', 'subgroup_rmse'))
        save(freeze, dict(alpha=min(alphas, key=rank), source_sha256=fingerprint()))
        return
    stat = summaries[str(alphas[0])]
    ratios = {k: stat[k]['paired_means'][1] / stat[k]['paired_means'][0]
              for k in ('curve_rmse', 'subgroup_rmse', 'derivative_rmse')}
    base, cand = stat['baseline_targets'], stat['candidate_targets']
    gates = dict(overall=ratios['curve_rmse'] <= .95, subgroup=ratios['subgroup_rmse'] <= .95,
                 derivative=ratios['derivative_rmse'] <= 1,
                 coverage=all(stat[k]['outputs'][1] >= stat[k]['outputs'][0] for k in ratios),
                 targets=all(cand[k] <= base[k] for k in ('false_reach', 'missed')),
                 blocks=len(stat['winning_blocks']) >= 4)
    save(HERE / 'decision.json', dict(selected_alpha=alphas[0], use_candidate=all(gates.values()),
                                    ratios=ratios, gates=gates))


def physical():
    seed = SPEC['physical_seed']
    kind = 'observed_confounding'
    d = generate(seed, kind, SPEC['physical_users'], SPEC['events_per_user'])
    rng = np.random.default_rng(seed + 333)
    rel = np.arange(-900, 2700, 10)
    records, factors, labels = [], [], []
    for i, (seconds, user, state, dose) in enumerate(zip(d['outcome'], d['users'], d['X'], d['treatment'])):
        count = int(np.rint(seconds / 10))
        split = i % 2 == 1 and 4 <= count <= 175
        gap = 5 if split else 0
        start_bin = rng.integers(0, 181 - count - gap) if count else 0
        first = count // 2 if split else count
        active = np.zeros(180, dtype=bool)
        active[start_bin:start_bin + first] = True
        second = start_bin + first + gap
        active[second:second + count - first] = True
        change = np.zeros(len(rel))
        change[90:270] = 1.5 * active
        change[270:] = -.35 * (count / 180) * np.exp(-(rel[270:] - 1800) / 180)
        power = 3 - change + rng.normal(0, .05, len(rel))
        start = float(100 + 90 * i)
        task = dict(task_id=f'ev-demo-{i:04d}', user_id=user, meter_id=user + '-meter',
                    start_min=start, end_min=start + 30, request_kw=1.5, notice_min=start - 15,
                    task_pre_treatment=True)
        starts, ends = (start + rel / 60).tolist(), (start + (rel + 10) / 60).tolist()
        ref = provided_reference(task, starts, ends, np.full(len(rel), 3.), available_at_min=start - 16)
        records.append(dict(task=task, starts_min=starts, ends_min=ends, power_kw=power.tolist(),
                            reference=ref, noise_sigma_kw=.05))
        factors.append(dict(task_id=task['task_id'], user_id=user, meter_id=task['meter_id'],
                            offered_incentive=dose, treatment_set_min=start - 20,
                            available_at_min=dict(offered_incentive=start - 20, **dict.fromkeys(NAMES, start - 30)),
                            state_as_of_min=dict.fromkeys(NAMES, start - 30), **dict(zip(NAMES, state))))
        labels.append(dict(task_id=task['task_id'], cumulative=10 * count,
                           longest=10 * max(first, count - first), split=split))
    inputs = HERE / 'physical_inputs.json'
    if inputs.exists():
        assert json.loads(inputs.read_text(encoding='utf-8')) == dict(records=records, factors=factors, labels=labels)
    else:
        save(inputs, dict(records=records, factors=factors, labels=labels))
    runtime = HERE.parent / 'b1_mainline_20261029' / 'runtime'
    features = {}
    errors = {}
    for method in ('effective_response_refined', 'cpop'):
        events = analyze_events(records, process_method=method,
            process_config=dict(rscript_path=str(runtime / 'R-4.6.1/app/bin/Rscript.exe'),
                r_library=str(runtime / 'r_library'), artifact_dir=str(HERE / 'native' / method), timeout_seconds=240))
        outputs = []
        for row in events:
            process = row.get('process') or {}
            selected = (process.get('features') or {}).get('selected_curve') or {}
            durations = process.get('duration_estimates') or selected
            outputs.append(dict(status=row['status'], task_id=row['task']['task_id'],
                cumulative=durations.get('cumulative_response_seconds'),
                longest=durations.get('longest_continuous_response_seconds'),
                observed_features=selected))
        assert all(a['task_id'] == b['task_id'] for a,b in zip(outputs, labels))
        features[method] = outputs
        errors[method] = {k: dict(n=sum(a[k] is not None for a in outputs),
            mae=float(np.mean([abs(a[k]-b[k]) for a,b in zip(outputs, labels) if a[k] is not None])))
            for k in ('cumulative', 'longest')}
        print('physical', method, errors[method], flush=True)
        if method == 'effective_response_refined':
            incumbent_events = events
    study_design = EVFactorStudy('charging-demo', '元/千瓦时', covariates=tuple(NAMES), outcome_source='duration_estimates')
    group = {side: dict(covariate=NAMES[0], threshold=0., side=side) for side in ('below','above')}
    model = fit_research_point_one(incumbent_events, factors, study_design, dose_domain=DOMAIN,
                                  reference_dose=REFERENCE, assumptions=assumptions(kind), config=cfg(seed), groups=group)
    save_research_point_one(model, HERE / 'demo_model.json')
    from b1_api import load_research_point_one
    model_loaded = load_research_point_one(HERE / 'demo_model.json')
    query = query_research_point_one(model_loaded, GRID, target_contrast=TARGET)
    pair_query = query_research_point_one(model_loaded, [REFERENCE, SPEC['demo_dose']], target_contrast=TARGET)
    assert pair_query['mean_curve']['curve'] is not None
    assert abs(pair_query['mean_curve']['curve']['contrasts'][1] - query['mean_curve']['curve']['contrasts'][8]) < 1e-9
    nodes = NAMES + ['offered_incentive', 'cumulative_response_seconds']
    graph_edges = [(nodes[i], nodes[j]) for i,j in [(0,3),(1,3),(0,4),(1,4),(3,4)]]
    graph_scores = {name: skeleton_metrics(value, graph_edges) for name,value in model['structure'].items()}
    # The raw chain passes a larger predeclared state list, including the diagnostic negative control.
    truth = truth_function(np.asarray(d['X']), kind, rounded=True)
    save(HERE / 'physical.json', dict(grid=GRID.tolist(), query=query, example=pair_query['mean_curve']['curve'],
        truth=contrast(truth, GRID).tolist(), feature_rows=features, errors=errors,
        graph_scores=graph_scores, events=len(records), users=SPEC['physical_users']))


if __name__ == '__main__':
    stage = sys.argv[1]
    if stage == 'physical':
        physical()
    elif stage in ('development', 'confirmation'):
        study(stage)
    else:
        raise ValueError(stage)
