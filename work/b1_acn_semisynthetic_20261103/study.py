"""Continuous EV compensation pilot on measured ACN background trajectories."""
import os
for thread_setting in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[thread_setting] = '1'

import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.special import expit

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = ROOT / 'data/ACN_real_user_benchmark_v1_20261102'
SPLINE = ROOT / 'work/b1_curve_spline_pilot_20261103'
sys.path.insert(0, str(ROOT / 'B1算法'))
sys.path.insert(0, str(SPLINE))
from b1_algorithm.effects.continuous import fit_continuous_effects, ContinuousEffectConfig
from candidate import fit_candidate_from_shared_result, query_candidate

SEEDS = [90371001, 90371002, 90371003, 90371004]
MECHANISMS = ['saturation', 'nonmonotone', 'zero_effect']
DOMAIN = [0., 2.4]
GRID = np.linspace(.3, 2.1, 31)
THRESHOLD = .15
REQUEST = 1.5
REPLICATES = 8


def save(name, value):
    with (HERE / name).open('x', encoding='utf-8') as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def protocol():
    inputs = [SOURCE / (role + '_sessions.json') for role in ('training', 'validation')]
    inputs += [Path(__file__), SPLINE / 'candidate.py', SPLINE / 'smoothers.py']
    inputs += list((ROOT / 'B1算法').rglob('*.py')) + list((ROOT / 'B1算法').rglob('*.json'))
    save('protocol.json', dict(
        archive_roles=['training', 'validation'],
        source_selection='Hash-order sessions per user, at most 3 eligible sessions, first eligible window per session. Development archive roles only.',
        window='15 min history + 30 min task, anchors every 15 min from first source time; require finite nonnegative measured power/pilot, native gaps <=15s, median history power >=0.30 kW.',
        background='Measured Power (kW), original times and row references; piecewise constant from each reading until next, clipped exactly at window boundaries. Scenario baseline, not an identified no-control counterfactual.',
        action='Synthetic continuous U(0,2.4) CNY/kWh offer; Bernoulli response and dose-dependent active interval; reduction min(1.5, observed background power) when active. Duration integrates reduction >=0.15 kW.',
        truth='Average over fixed real context roster, integrating simulated participation analytically. No fitted outcomes used for truth.',
        model='Formal continuous Kennedy DR vs retained lambda=0.0001 spline using identical DR pseudo-outcomes. Fit only ACN training-role users; compare both on expected response curves of disjoint ACN validation-role users.',
        metrics='Uniform-grid level and contrast RMSE (s), reference .30. Report each seed/mechanism, including unsupported curves. Transfer error includes change of context population. No parameters selected from validation.',
        seeds=SEEDS, mechanisms=MECHANISMS, repetitions_per_context_per_seed=REPLICATES,
        hashes={str(path.relative_to(ROOT)): sha(path) for path in inputs}))


def read_context(item):
    path = ROOT / item['local']
    source_hash = sha(path)
    df = pd.read_csv(path, usecols=['Unnamed: 0', 'Power (kW)', 'Actual Pilot (A)'])
    stamps = pd.to_datetime(df['Unnamed: 0'], utc=True, errors='raise', format='mixed')
    times = (stamps - stamps.iloc[0]).dt.total_seconds().to_numpy()
    power = df['Power (kW)'].to_numpy(float)
    pilot = df['Actual Pilot (A)'].to_numpy(float)
    if np.any(np.diff(times) <= 0):
        return None, 'nonincreasing_source_time'
    for anchor in np.arange(900, times[-1] - 1800 + .001, 900):
        first = np.searchsorted(times, anchor - 900, side='right') - 1
        last = np.searchsorted(times, anchor + 1800)
        index = np.arange(first, last)
        if not len(index) or np.max(np.diff(times[first:last+1])) > 15:
            continue
        if not np.all(np.isfinite(power[index]) & np.isfinite(pilot[index]) & (power[index] >= 0) & (pilot[index] >= 0)):
            continue
        prefix = index[times[index] < anchor]
        if np.median(power[prefix]) < .30:
            continue
        task_index = index[times[index+1] > anchor]
        return dict(user=item['user_group'], source=item['local'], source_sha256=source_hash,
                    time_origin=stamps.iloc[0].isoformat(), anchor=float(anchor),
                    X=[float(np.median(power[prefix])), float(np.median(pilot[prefix])), float(anchor/3600)],
                    history_source_indices=prefix.tolist(),
                    source_indices=task_index.tolist(), raw_time_seconds=times[task_index].tolist(),
                    raw_next_time_seconds=times[task_index+1].tolist(),
                    starts=np.maximum(0, times[task_index]-anchor).tolist(),
                    ends=np.minimum(1800, times[task_index+1]-anchor).tolist(),
                    power=power[task_index].tolist(), pilot=pilot[task_index].tolist()), 'eligible'
    return None, 'no_eligible_window'


def collect(role):
    registry = load(SOURCE / (role + '_sessions.json'))
    by_user = defaultdict(list)
    for item in registry:
        by_user[item['user_group']].append(item)
    contexts, audit = [], []
    for user, sessions in sorted(by_user.items()):
        accepted = 0
        for item in sorted(sessions, key=lambda row: hashlib.sha256(row['session_id'].encode()).hexdigest()):
            if accepted == 3:
                break
            try:
                context, reason = read_context(item)
            except (OSError, ValueError, IndexError, EOFError) as exc:
                context, reason = None, type(exc).__name__
            audit.append(dict(source=item['local'], reason=reason))
            if context is not None:
                contexts.append(context)
                accepted += 1
    save(role + '_contexts.json', contexts)
    save(role + '_selection.json', audit)
    print(role, len(contexts), len({c['user'] for c in contexts}), dict(Counter(r['reason'] for r in audit)), flush=True)
    return contexts


def schedule(context, amount, mechanism):
    pre_power, _, elapsed_hours = context['X']
    if mechanism == 'saturation':
        signal = 2.5 * (1 - np.exp(-amount/.8))
    elif mechanism == 'nonmonotone':
        signal = 2.2 * np.sin(np.pi * amount/2.4)
    else:
        signal = 0. * amount
    power_state = np.tanh((pre_power-2.)/2.)
    probability = expit(-1.4 + signal * (1.25 + .25*power_state) + .25*power_state)
    delay = 45. + 80. * expit(-pre_power + 1.)
    active_length = (1800.-delay) * expit(-1.8 + 1.05*signal + .3*power_state - .25*elapsed_hours)
    return probability, delay, delay + active_length


def active_seconds(context, start, end):
    left = np.asarray(context['starts'])
    right = np.asarray(context['ends'])
    support = np.minimum(REQUEST, context['power']) >= THRESHOLD
    return np.maximum(0, np.minimum(np.asarray(end)[..., None], right[support]) -
                      np.maximum(start, left[support])).sum(axis=-1)


def truth(contexts, mechanism):
    means = []
    for context in contexts:
        p, start, end = schedule(context, GRID, mechanism)
        means.append(p * active_seconds(context, start, end))
    return np.mean(means, axis=0)


def events(contexts, seed, mechanism):
    rng = np.random.default_rng(seed)
    rows = []
    for i, context in enumerate(contexts):
        amount = rng.uniform(*DOMAIN, REPLICATES)
        uniform = rng.uniform(size=REPLICATES)
        p, start, end = schedule(context, amount, mechanism)
        seconds = active_seconds(context, start, end)
        for j in range(REPLICATES):
            rows.append(dict(context=i, user=context['user'], X=context['X'], offered_compensation=float(amount[j]),
                             simulated_participation=bool(uniform[j] < p[j]), probability=float(p[j]),
                             simulated_start=float(start), simulated_end=float(end[j]),
                             effective_response_seconds=float(seconds[j] if uniform[j] < p[j] else 0.)))
    return rows


def fit(rows, seed):
    x = [r['X'] for r in rows]
    users = [r['user'] for r in rows]
    baseline = fit_continuous_effects(x, [r['offered_compensation'] for r in rows],
        [r['effective_response_seconds'] for r in rows], users,
        dose_domain=DOMAIN, grid=GRID, reference_dose=.3, incentive_unit='yuan/kWh',
        task=dict(task_id='acn_semisynthetic_30min', outcome_name='cumulative_response_seconds',
                  outcome_unit='seconds', target_population='eligible ACN background scenarios',
                  window_minutes=[0,30], q_kw=REQUEST, task_pre_treatment=True, reference_status='provided'),
        continuous_assignment=True, known_density=np.full(len(rows), 1/2.4),
        assumptions=dict(pre_treatment_X=True, consistent_treatment=True, no_interference=True,
                         same_outcome_definition=True, randomized_assignment=True),
        config=ContinuousEffectConfig(seed=seed, n_boot=99, return_audit=True))
    if baseline['status'] != 'causal':
        return baseline, None, None
    spline = fit_candidate_from_shared_result(baseline, x, users)
    return baseline, spline, query_candidate(spline, GRID)


def scores(curve, actual):
    mean = np.asarray(curve['mean_outcomes'])
    return dict(level_rmse_seconds=float(np.sqrt(np.mean((mean-actual)**2))),
                contrast_rmse_seconds=float(np.sqrt(np.mean(((mean-mean[0])-(actual-actual[0]))**2))))


def verify_waveforms(rows, contexts):
    examples = []
    for i in np.linspace(0, len(rows)-1, 32, dtype=int):
        event = rows[i]
        context = contexts[event['context']]
        reconstructed, pieces = 0., []
        for left, right, power in zip(context['starts'], context['ends'], context['power']):
            boundaries = [left, right]
            if event['simulated_participation']:
                boundaries += [t for t in (event['simulated_start'], event['simulated_end']) if left < t < right]
            boundaries.sort()
            for a, b in zip(boundaries, boundaries[1:]):
                active = event['simulated_participation'] and event['simulated_start'] <= (a+b)/2 < event['simulated_end']
                actual = max(0., power-REQUEST) if active else power
                if power-actual >= THRESHOLD - 1e-12:
                    reconstructed += b-a
                pieces.append([a, b, power, actual])
        assert abs(reconstructed-event['effective_response_seconds']) < 1e-8
        examples.append(dict(event_index=int(i), expected_seconds=event['effective_response_seconds'],
                             reconstructed_seconds=reconstructed, waveform=pieces))
    return examples


def main():
    protocol()
    training = collect('training')
    validation = collect('validation')
    assert training and validation and not ({c['user'] for c in training} & {c['user'] for c in validation})
    for context in training + validation:
        assert np.isclose(sum(np.asarray(context['ends'])-context['starts']), 1800.)
    result = []
    for mechanism in MECHANISMS:
        expected = truth(validation, mechanism)
        save(mechanism+'_truth.json', dict(amounts=GRID.tolist(), validation_mean_seconds=expected.tolist(),
                                         training_mean_seconds=truth(training, mechanism).tolist()))
        for seed in SEEDS:
            name = f'{mechanism}_{seed}'
            rows = events(training, seed, mechanism)
            save(name+'_training_events.json', rows)
            baseline, model, query = fit(rows, seed)
            entry = dict(seed=seed, mechanism=mechanism, training_events=len(rows), status=baseline['status'])
            save(name+'_baseline.json', baseline)
            if query is not None:
                save(name+'_spline_model.json', model)
                save(name+'_spline_query.json', query)
                entry['baseline'] = scores(baseline['causal_curve'], expected)
                if query['curve'] is not None:
                    entry['spline'] = scores(query['curve'], expected)
            result.append(entry)
            if seed == SEEDS[0]:
                save(mechanism+'_waveform_checks.json', verify_waveforms(rows, training))
            print(entry, flush=True)
    for filename, digest in load(HERE/'protocol.json')['hashes'].items():
        assert sha(ROOT/filename) == digest, filename
    for context in training + validation:
        assert sha(ROOT/context['source']) == context['source_sha256']
    save('results.json', dict(rows=result, training_contexts=len(training), validation_contexts=len(validation),
        training_users=len({c['user'] for c in training}), validation_users=len({c['user'] for c in validation}),
        source_and_code_hash_checks_passed=True, waveform_checks=96,
        total_training_variants=sum(r['training_events'] for r in result)))


if __name__ == '__main__':
    main()
