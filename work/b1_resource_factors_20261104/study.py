"""Paired second-part benchmark and common-interface replay for two resources."""
import os
for setting in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[setting] = '1'

from collections import defaultdict
from dataclasses import replace
from pathlib import Path
import hashlib
import json
import sys

import numpy as np
from scipy.special import expit

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[1]
HERE = Path(sys.argv[1]).resolve() if __name__ == '__main__' and len(sys.argv) > 1 else SCRIPT_DIR
sys.path.insert(0, str(ROOT/'B1算法'))
sys.path.append(str(ROOT/'work/b1_research_point1_20261103/runtime/site-packages'))
from b1_api import ResourceFactorStudy, analyze_resource_factors, discover_factor_structure

SEEDS = (9042001, 9042002, 9042003, 9042004)
MECHANISMS = ('linear', 'nonlinear', 'correlated', 'randomized', 'zero_effect', 'one_side')
METHODS = ('kci', 'tiered_kci', 'quote_bic_plus_tiered')
RESOURCES = {
    'EV': ResourceFactorStudy('EV', (('deadline_slack', 'h'), ('demand_urgency', 'kWh'), ('negative_control', '1')),
                              'CNY/kWh', 'cumulative_response_seconds', 's', 'effective reduction duration in task', 30, (0, 2.4)),
    'heat_pump': ResourceFactorStudy('heat_pump', (('thermal_margin', 'degC'), ('outdoor_temperature', 'degC'), ('negative_control', '1')),
                                     'CNY/event', 'net_reduction_energy', 'kWh', 'metered reduction energy over task', 45, (0, 3.0)),
}


def save(name, value):
    with (HERE/name).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)


def generate(study, seed, mechanism):
    rng = np.random.default_rng(seed)
    independent = 120
    n = independent*2
    a, b, control = rng.uniform(-1., 1., (3, n))
    if mechanism == 'correlated':
        b = .6*a+.4*b
    x = np.column_stack((a, b, control))
    if study.resource_type == 'EV':
        values = np.column_stack((2.+1.7*a, 12.+9.*b, control))
        quote_term = .56*a-.48*b
        outcome_term = .65*a-.60*b
        noise = 1.15
    else:
        values = np.column_stack((1.5+1.1*a, 1.+9.*b, control))
        quote_term = .45*a+.60*b
        outcome_term = .76*a+.42*b
        noise = 1.05
    quote_truth = {0, 1}
    outcome_truth = {0, 1}
    if mechanism == 'nonlinear':
        quote_term = 1.7*(a*a-1/3) + .5*b
    if mechanism == 'one_side':
        quote_term = .85*a
        outcome_term = .90*b
        quote_truth, outcome_truth = {0}, {1}
    z = quote_term + noise*rng.normal(size=n)
    fraction = expit(z)
    if mechanism == 'randomized':
        fraction = rng.uniform(0, 1, n)
        quote_truth = set()
    effect = np.zeros(n) if mechanism == 'zero_effect' else fraction
    if study.resource_type == 'EV':
        outcome = (rng.random(n) < expit(-.65+2.2*effect+outcome_term)) * rng.beta(
            8*expit(-.15+effect+.55*outcome_term), 8*expit(.15-effect-.55*outcome_term))*1800
    else:
        outcome = (rng.random(n) < expit(.2+1.4*effect+.65*outcome_term)) * (
            .65+.7*effect+.32*outcome_term+.25*rng.normal(size=n))
    names = [name for name, unit in study.factors]
    rows = []
    for i in range(n):
        start = float(i*90)
        rows.append(dict(event_id=f'{study.resource_type}-{seed}-{i}', cluster_id=f'cluster-{i//2:03d}',
                         resource_type=study.resource_type, offer_unit=study.offer_unit,
                         outcome_name=study.outcome_name, outcome_unit=study.outcome_unit,
                         offer_formed_min=start-20, notice_min=start-15, start_min=start,
                         end_min=start+study.window_minutes, outcome_available_min=start+study.window_minutes+1,
                         offered_incentive=float(fraction[i]*study.continuous_offer_domain[1]),
                         outcome_value=float(outcome[i]),
                         pre_factors={name: dict(value=float(value), measured_min=start-35, available_min=start-34)
                                      for name, value in zip(names, values[i])}))
    return rows, set(names[i] for i in quote_truth), set(names[i] for i in outcome_truth)


def score(estimated, actual):
    return dict(tp=len(estimated & actual), fp=len(estimated-actual), fn=len(actual-estimated))


def summarize(entries):
    result = {}
    for method in METHODS:
        result[method] = {}
        for target in ('quote', 'outcome', 'common'):
            total = {key: sum(row['metrics'][method][target][key] for row in entries) for key in ('tp','fp','fn')}
            tp, fp, fn = [total[key] for key in ('tp','fp','fn')]
            result[method][target] = dict(total, precision=tp/(tp+fp) if tp+fp else None,
                                          recall=tp/(tp+fn) if tp+fn else None)
    return result


def check_contract(study, rows, analysis):
    reverse = analyze_resource_factors(study, list(reversed(rows)))
    assert reverse == analysis
    for key in ('outcome_unit', 'resource_type', 'offer_unit', 'outcome_name'):
        try:
            analyze_resource_factors(study, [dict(rows[0], **{key: 'mismatch'})]+rows[1:])
        except ValueError:
            pass
        else:
            raise AssertionError(key)
    factor = study.factors[0][0]
    bad = dict(rows[0], pre_factors={**rows[0]['pre_factors'], factor: dict(value=1., measured_min=-35., available_min=-19.)})
    try:
        analyze_resource_factors(study, [bad]+rows[1:])
    except ValueError as exc:
        assert 'unavailable' in str(exc)
    else:
        raise AssertionError('post-offer field accepted')
    names = [name for name, unit in study.factors]
    matrix = [[r['pre_factors'][name]['value'] for name in names]+[r['offered_incentive'],r['outcome_value']] for r in rows]
    old = discover_factor_structure(matrix, [r['cluster_id'] for r in rows], names+['offer','outcome'], method='pc_kci')
    expected = {frozenset((e['node1'],e['node2'])) for e in old['edges']}
    assert {frozenset(e) for e in analysis['evidence']['kci']['adjacencies']} == expected
    generic = analyze_resource_factors(replace(study, continuous_offer_domain=None), rows)
    assert set(generic['evidence']) == {'kci','tiered_kci'}
    assert generic['study']['outcome_unit'] == study.outcome_unit


def main():
    HERE.mkdir(parents=True, exist_ok=True)
    files = [Path(__file__), ROOT/'B1算法/b1_api.py', ROOT/'B1算法/b1_algorithm/resource_factors.py']
    save('protocol.json', dict(seeds=SEEDS, mechanisms=MECHANISMS, resources=list(RESOURCES), independent_clusters=120,
        alpha=.05, one_predeclared_comparison=True, prior_graph_results_used_for_tuning=False,
        hypotheses=['Time restriction limits possible separators', 'Bounded additive quote model recovers quote-side candidates'],
        screening_gate='Common-factor recall +10 percentage points and no more than two extra false common candidates versus unrestricted KCI, overall.',
        files={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}))
    results = []
    for resource, study in RESOURCES.items():
        for mechanism in MECHANISMS:
            for seed in SEEDS:
                rows, quote, outcome = generate(study, seed, mechanism)
                analysis = analyze_resource_factors(study, rows)
                metrics = {}
                for name, evidence in analysis['evidence'].items():
                    metrics[name] = {target: score(set(evidence[target+'_candidates']), truth) for target, truth in
                                     [('quote', quote), ('outcome', outcome), ('common', quote & outcome)]}
                results.append(dict(resource=resource, mechanism=mechanism, seed=seed, metrics=metrics, analysis=analysis))
                if mechanism == 'linear' and seed == SEEDS[0]:
                    check_contract(study, rows, analysis)
                    save(resource+'_example.json', dict(study=analysis['study'], records=rows, result=analysis))
                print(resource, mechanism, seed, flush=True)
    aggregate = summarize(results)
    baseline = aggregate['kci']['common']
    candidate = aggregate['quote_bic_plus_tiered']['common']
    save('results.json', dict(aggregate=aggregate, by_resource={k:summarize([r for r in results if r['resource']==k]) for k in RESOURCES},
        by_mechanism={k:summarize([r for r in results if r['mechanism']==k]) for k in MECHANISMS},
        rows=results, interface_replay_checks_passed=True,
        screening_gate_passed=candidate['recall']-baseline['recall']>=.10 and candidate['fp']<=baseline['fp']+2))
    print(json.dumps(aggregate))


if __name__ == '__main__':
    main()
