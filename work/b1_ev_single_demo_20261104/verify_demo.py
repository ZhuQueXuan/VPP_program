"""Recompute the scores used in the single-resource demo."""
from hashlib import sha256
from math import isclose, sqrt
from statistics import mean

import evaluate as ev
from b1_api import load_research_point_one
from b1_algorithm.effects.frozen import FrozenContinuousModel, fit_continuous_model, query_continuous_model


def load(file):
    return ev.json.loads((ev.HERE / file).read_text(encoding='utf-8'))


def main():
    development, selection, final, decision = map(load, ('development.json', 'selection.json',
                                                          'confirmation.json', 'decision.json'))
    for relative, digest in selection['source_sha256'].items():
        assert sha256((ev.ROOT / relative).read_bytes()).hexdigest() == digest
    assert not ({r['seed'] for r in development['cohorts']} & {r['seed'] for r in final['cohorts']})
    candidate = str(decision['selected_alpha'])
    assert candidate == str(selection['alpha'])
    rows = final['cohorts']
    assert len(rows) == 24 and len({r['seed'] for r in rows}) == 6
    for row in rows:
        assert row['events'] == 480 and row['users'] == 240
        truth = row['truth']
        for name in ('incumbent', candidate):
            result = row['scores'][name]
            a, b, c = result['curves']
            assert isclose(result['curve_rmse'], sqrt(mean((x-y)**2 for x,y in zip(a, truth[0]))))
            assert isclose(result['subgroup_rmse'], sqrt(mean(((z-y)-(v-u))**2
                for y,z,u,v in zip(b,c,truth[1],truth[2]))))
    for metric, ratio in decision['ratios'].items():
        old, new = (mean(r['scores'][name][metric] for r in rows) for name in ('incumbent', candidate))
        assert isclose(new / old, ratio)
    wins = sum(mean(r['scores'][candidate]['curve_rmse'] - r['scores']['incumbent']['curve_rmse']
                    for r in rows if r['seed'] == seed) < 0 for seed in {r['seed'] for r in rows})
    assert decision['gates']['blocks'] == (wins >= 4)
    assert decision['use_candidate'] == all(decision['gates'].values())

    target = load('target_check.json')
    for key in ('point', 'guarded'):
        called = [r for r in target['cases'] if r[key] is not None]
        assert len(called) == target[key]['decisions']
        assert sum(r[key] != r['truth_reached'] for r in called) == target[key]['wrong']
    assert target['demo_admission']

    raw, inputs = map(load, ('physical.json', 'physical_inputs.json'))
    assert raw['events'] == len(inputs['records']) == len(inputs['factors']) == len(inputs['labels']) == 240
    for record, factor, label in zip(inputs['records'], inputs['factors'], inputs['labels']):
        task = record['task']
        assert task['task_id'] == factor['task_id'] == label['task_id']
        assert factor['treatment_set_min'] < task['notice_min'] < task['start_min']
        assert max(factor['state_as_of_min'].values()) < factor['treatment_set_min']
        assert 0 <= label['longest'] <= label['cumulative'] <= 1800
    split_results = {}
    for method, features in raw['feature_rows'].items():
        assert len(features) == raw['events']
        for key in ('longest', 'cumulative'):
            usable = [(f[key], t[key]) for f,t in zip(features, inputs['labels']) if f[key] is not None]
            assert len(usable) == raw['errors'][method][key]['n'] == 240
            assert isclose(mean(abs(a-b) for a,b in usable), raw['errors'][method][key]['mae'])
        # Fifty seconds was the simulated gap. A 20 s margin avoids treating a single noisy cell as a split.
        split = [f['cumulative'] - f['longest'] >= 20 - 1e-7 for f in features]
        split_results[method] = dict(
            true_split=sum(t['split'] for t in inputs['labels']),
            missed=sum(t['split'] and not call for call,t in zip(split, inputs['labels'])),
            false=sum(not t['split'] and call for call,t in zip(split, inputs['labels'])))
    model = load_research_point_one(ev.HERE / 'demo_model.json')
    frozen = FrozenContinuousModel(**model['mean_model'])
    q = query_continuous_model(frozen, [ev.REFERENCE, ev.SPEC['demo_dose']])
    assert q['curve'] == raw['example']
    q = query_continuous_model(frozen, ev.SEARCH)
    assert q['inference'] is not None
    lower, upper = max(q['inference']['lower']), max(q['inference']['upper'])
    status = 'reached' if lower >= ev.TARGET else ('below' if upper < ev.TARGET else 'uncertain')
    # Keep the downstream estimator and event rows fixed while swapping the extracted duration.
    x = [[factor[k] for k in model['covariate_names']] for factor in inputs['factors']]
    d = [factor['offered_incentive'] for factor in inputs['factors']]
    users = [factor['user_id'] for factor in inputs['factors']]
    downstream = {}
    for method, rows_for_method in raw['feature_rows'].items():
        replacement = fit_continuous_model(x, d, [row['cumulative'] for row in rows_for_method], users,
            dose_domain=ev.DOMAIN, reference_dose=ev.REFERENCE, incentive_unit=model['incentive_unit'],
            task=model['task'], continuous_assignment=True, assumptions=ev.assumptions('observed_confounding'),
            config=ev.cfg(ev.SPEC['physical_seed']))
        replay = query_continuous_model(replacement, ev.GRID)['curve']['contrasts']
        if method == 'effective_response_refined':
            assert ev.np.allclose(replay, raw['query']['mean_curve']['curve']['contrasts'], rtol=0, atol=1e-8)
        downstream[method] = sqrt(mean((a-b)**2 for a,b in zip(replay, raw['truth'])))

    result = dict(physical_events=raw['events'], score_cohorts=len(rows),
        winning_blocks=wins, observed_vs_simulated_split=split_results, target_decision=status,
        threshold_grid_count=len(ev.SEARCH), band_lower_max=lower, band_upper_max=upper,
        curve_rmse_by_extractor=downstream, queried_example_reloaded=True)
    target_file = ev.HERE / 'demo_checks.json'
    target_file.write_text(ev.json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    print('Verified scoring, task binding, source hashes and saved-model query')


if __name__ == '__main__':
    main()
