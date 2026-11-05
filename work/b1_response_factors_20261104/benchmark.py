"""Evaluate a targeted outcome screen using the existing resource study contract."""
import hashlib
import json
import sys
import zipfile
from collections import Counter
from dataclasses import replace
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'b1_resource_factors_20261104'))
from study import MECHANISMS, RESOURCES, generate, np, score
import pandas as pd
from scipy.special import expit
from scipy.stats import f, rankdata
from b1_api import analyze_resource_factors
from b1_algorithm.resource_factors import _read_events, _stable_skeleton
from causallearn.utils.cit import CIT

SEEDS = (9054101, 9054102, 9054103, 9054104)
NEW_MECHANISMS = ('outcome_quadratic', 'outcome_interaction', 'quote_mediated_only')


def screen(matrix, alpha):
    """One additive quadratic conditional-mean model, joint HC3 test per factor."""
    x = matrix[:, :-1]
    x = (x-x.mean(0))/x.std(0)
    n, k = x.shape
    design = np.column_stack((np.ones(n), x, x*x))
    if np.linalg.matrix_rank(design) < design.shape[1]:
        raise ValueError('Full rank is required for the conditional mean screen')
    inv = np.linalg.pinv(design)
    beta = inv @ matrix[:, -1]
    leverage = np.einsum('ij,ji->i', design, inv)
    residual = (matrix[:, -1]-design@beta)/(1-leverage)
    robust = inv*residual
    cov = robust@robust.T
    pvalues = []
    for j in range(k-1):
        indices = [1+j, 1+k+j]
        block = cov[np.ix_(indices, indices)]
        b = beta[indices]
        statistic = b @ np.linalg.solve(block, b) / 2
        pvalues.append(float(f.sf(statistic, 2, n-design.shape[1])))
    return {j for j, p in enumerate(pvalues) if p <= alpha}, pvalues


def evaluate(study, events):
    result = analyze_resource_factors(study, events)
    names, matrix, ids, _ = _read_events(study, events)
    assert ids == result['selected_events']
    old = result['evidence']['tiered_kci']
    indices, pvalues = screen(matrix, result['alpha'])
    outcome = {names[j] for j in indices}
    quote = set(old['quote_candidates'])
    return dict(quote=sorted(quote), baseline_outcome=old['outcome_candidates'], baseline_common=old['common_candidates'],
                candidate_outcome=sorted(outcome), candidate_common=sorted(quote & outcome),
                conditional_mean_pvalues=dict(zip(names, pvalues)), n=len(ids))


def compare(study, events, quote, outcome):
    row = evaluate(study, events)
    row['truth'] = dict(quote=sorted(quote), outcome=sorted(outcome))
    row['metrics'] = {key: score(set(row[key]), truth) for key, truth in (
        ('baseline_outcome', outcome), ('candidate_outcome', outcome),
        ('baseline_common', quote & outcome), ('candidate_common', quote & outcome))}
    return row


def old_diagnosis():
    path = HERE.parent/'b1_resource_factors_20261104/contract_replay/results.json'
    output = []
    for row in json.loads(path.read_text(encoding='utf8'))['rows']:
        study = RESOURCES[row['resource']]
        events, _, truth = generate(study, row['seed'], row['mechanism'])
        names, matrix, _, _ = _read_events(study, events)
        target = len(names)+1
        ci = CIT(matrix, 'kci')
        removed = {}

        def trace(a, b, conditions):
            p = ci(a, b, conditions)
            if b == target and p > .05:
                removed[a] = (conditions, float(p))
            return p

        edges = _stable_skeleton(trace, [0]*len(names)+[1, 2], .05, True)
        retained = {name for i, name in enumerate(names) if (i, target) in edges}
        assert retained == set(row['analysis']['evidence']['tiered_kci']['outcome_candidates'])
        for factor in sorted(truth-retained):
            conditions, p = removed[names.index(factor)]
            variables = names+['offer', 'outcome']
            output.append(dict(resource=row['resource'], seed=row['seed'], mechanism=row['mechanism'], factor=factor,
                               conditions=[variables[i] for i in conditions], p=p,
                               stage='marginal' if not conditions else 'given_offer' if target-1 in conditions else 'given_other'))
    return output


def extra_events(study, seed, mechanism, anchors=None):
    events, _, _ = generate(study, seed, 'linear')
    rng = np.random.default_rng(seed+1500)
    n = len(events)
    names = [name for name, _ in study.factors]
    a, b = rng.uniform(-1, 1, (2, n)) if anchors is None else anchors[rng.integers(len(anchors), size=n)].T
    z = .8*a + .6*b + rng.normal(size=n)
    offer = expit(z)
    if mechanism == 'outcome_quadratic':
        signal = 1.4*(a*a-1/3) + .65*b
    elif mechanism == 'outcome_interaction':
        signal = 1.7*a*b
    elif mechanism == 'quote_mediated_only':
        signal = np.zeros(n)
    else:
        signal = .8*a + .65*b
    expected = set(names[:2]) if mechanism != 'quote_mediated_only' else set()
    if study.resource_type == 'EV':
        y = (rng.random(n) < expit(-.3+1.3*offer+signal))*1800*expit(-.5+offer+.6*signal+rng.normal(size=n))
    else:
        y = (rng.random(n) < expit(.2+offer+signal))*(.6+.4*offer+.32*signal+.35*rng.normal(size=n))
    for i, row in enumerate(events):
        row['offered_incentive'] = float(offer[i]*study.continuous_offer_domain[1])
        row['outcome_value'] = float(y[i])
        for name, value in zip(names[:2], (a[i], b[i])):
            row['pre_factors'][name]['value'] = float(value)
    return events, set(names[:2]), expected


def field_inputs():
    ev = pd.read_csv(HERE/'raw/ev.csv', index_col=0, parse_dates=True).sort_index()
    ev['previous_energy'] = ev['consumption_total'].shift(48, freq='h')
    ev['weekday'] = ev.index.dayofweek
    ev['day'] = (ev.index.normalize()-ev.index[0].normalize()).days
    keep = (ev.hour == 13) & (ev.availability_service == 1) & (ev.availability_discounts == 1) & (ev.holiday == 0)
    ev = ev.loc[keep].dropna(subset=['previous_energy', 'market_price', 'discount', 'consumption_total'])
    with zipfile.ZipFile(HERE/'raw/heat.zip') as archive, archive.open('experiment_data.dta') as stream:
        heat = pd.read_stata(stream, columns=['time', 'hh_id', 't_in', 't_set', 't_out', 'intervention_dummy'])
    time = pd.to_datetime(heat.time)
    heat = heat.loc[(time.dt.hour == 6) & (time.dt.minute == 0) & (time.dt.second == 0) & (heat.intervention_dummy == 0)].dropna()
    heat['margin'] = heat.t_in-heat.t_set
    anchors = {'EV': ev[['market_price', 'previous_energy']].to_numpy(), 'heat_pump': heat[['margin', 't_out']].to_numpy()}
    anchors = {resource: (2*rankdata(values, axis=0)-1)/len(values)-1 for resource, values in anchors.items()}
    return ev, anchors, int(heat.hh_id.nunique())


def actual_ev(ev):
    study = replace(RESOURCES['EV'], factors=(('previous_energy', 'kWh'), ('weekday', 'day')),
                    offer_unit='published_discount_fraction', outcome_name='site_hourly_charging_energy',
                    outcome_unit='kWh', measurement_definition='published station aggregate in a single hour',
                    window_minutes=60, continuous_offer_domain=None)
    rows = []
    for date, r in ev.loc[ev.day%4 == 0].iterrows():
        start = date.timestamp()/60
        rows.append(dict(event_id=date.isoformat(), cluster_id=date.date().isoformat(), resource_type='EV',
                         offer_unit=study.offer_unit, outcome_name=study.outcome_name, outcome_unit=study.outcome_unit,
                         offer_formed_min=start-1441, notice_min=start-1440, start_min=start, end_min=start+60,
                         outcome_available_min=start+60, offered_incentive=r.discount, outcome_value=r.consumption_total,
                         pre_factors={key: dict(value=r[key], measured_min=start-2880, available_min=start-2820)
                                      for key, _ in study.factors}))
    return dict(result=evaluate(study, rows), discounts=sorted({r['offered_incentive'] for r in rows}),
                first=rows[0]['event_id'], last=rows[-1]['event_id'],
                inference='exploratory single-site time series; offer timing approximated, no ground truth')


def summarize(rows):
    return {method: {key: sum(row['metrics'][method][key] for row in rows) for key in ('tp', 'fp', 'fn')}
            for method in rows[0]['metrics']}


def main():
    path = HERE/'protocol_replay.json'
    provenance = [Path(__file__), HERE.parent/'b1_resource_factors_20261104/study.py',
                  HERE.parents[1]/'B1算法/b1_algorithm/resource_factors.py', HERE/'raw/ev.csv', HERE/'raw/heat.zip']
    with path.open('x', encoding='utf8') as out:
        json.dump(dict(seeds=SEEDS, mechanisms=MECHANISMS+NEW_MECHANISMS, anchors=['linear', 'outcome_quadratic', 'quote_mediated_only'],
                       primary='new fully synthetic cohorts; same quote evidence and input, change response screen only',
                       gate='>=10 percentage points gain in common recall, no additional false common selections overall, no loss of common TP for either resource',
                       alpha=.05, hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in provenance}), out, indent=2)
    diagnosis = old_diagnosis()
    ev, anchors, heat_households = field_inputs()
    synthetic, anchored = [], []
    for resource, study in RESOURCES.items():
        for seed in SEEDS:
            for mechanism in MECHANISMS+NEW_MECHANISMS:
                events, quote, outcome = (generate if mechanism in MECHANISMS else extra_events)(study, seed, mechanism)
                synthetic.append(dict(resource=resource, seed=seed, mechanism=mechanism, **compare(study, events, quote, outcome)))
            for mechanism in ('linear', 'outcome_quadratic', 'quote_mediated_only'):
                events, quote, outcome = extra_events(study, seed, mechanism, anchors[resource])
                anchored.append(dict(resource=resource, seed=seed, mechanism=mechanism, **compare(study, events, quote, outcome)))
    def group(rows):
        return dict(total=summarize(rows), by_resource={r:summarize([row for row in rows if row['resource']==r]) for r in RESOURCES},
                    by_mechanism={m:summarize([row for row in rows if row['mechanism']==m]) for m in sorted({row['mechanism'] for row in rows})})
    main_scores, anchor_scores = group(synthetic), group(anchored)
    old, new = [main_scores['total'][key] for key in ('baseline_common','candidate_common')]
    gate = (new['tp']-old['tp'])/(old['tp']+old['fn']) >= .1 and new['fp'] <= old['fp'] and all(
        metrics['candidate_common']['tp']>=metrics['baseline_common']['tp'] for metrics in main_scores['by_resource'].values())
    summary = dict(diagnosis=dict(Counter(row['stage'] for row in diagnosis)), primary=main_scores, real_covariates=anchor_scores,
                   source_counts={**{k:len(v) for k,v in anchors.items()}, 'heat_households':heat_households},
                   actual_EV=actual_ev(ev), gate_passed=gate)
    with (HERE/'results.json').open('x', encoding='utf8') as out:
        json.dump(dict(summary, diagnostics=diagnosis, synthetic_rows=synthetic, anchored_rows=anchored), out, indent=2, allow_nan=False)
    print(json.dumps({k:v for k,v in summary.items() if k not in ('primary','real_covariates')}))
    print(json.dumps([main_scores['total'],anchor_scores['total']]))


if __name__ == '__main__':
    main()
