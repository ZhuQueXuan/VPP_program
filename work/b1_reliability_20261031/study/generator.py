"""Paired EV reliability facts, using the frozen independent old mechanism.

Truth is accessed here only to construct declared simulation interventions.
The estimator harness must read facts files only until all fits are frozen.
No original simulator or data artifact is changed by this wrapper.
"""
from __future__ import annotations
from pathlib import Path
import copy
import hashlib
import importlib.util
import json
import math
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BASE_SOURCE = ROOT / 'work/b1_ev_mainline_20261030/simulation.py'
PROTOCOL = HERE.parent / 'protocol.json'
PROTOCOL_SHA = 'd095a56114f34f6d827e708a8f063b4dd758c5b113abc222f73f259e72cf3749'
FACTS = ROOT / 'data/B1_reliability_v1_20261031'
_spec = importlib.util.spec_from_file_location('frozen_independent_ev_mechanism', BASE_SOURCE)
BASE = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(BASE)

# Duration/slack/relative times must not be shifted. These keys are absolute.
ABSOLUTE_SCALARS = frozenset(('start_min', 'end_min', 'notice_min',
    'task_start_min', 'task_end_min', 'pre_available_min', 'prior_available_min',
    'calendar_available_min', 'temperature_available_min', 'treatment_set_min',
    'current_conditions_at_min', 'offered_incentive_at_min',
    'power_records_available_at_min', 'historical_source_completion_max_min'))
ABSOLUTE_VECTORS = frozenset(('starts_min', 'ends_min', 'pre_starts_min', 'pre_ends_min'))
ABSOLUTE_NESTED = frozenset(('available_at_min', 'state_as_of_min'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump_new(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, allow_nan=False, separators=(',', ':'))


def protocol():
    if sha(PROTOCOL) != PROTOCOL_SHA:
        raise RuntimeError('central frozen protocol SHA changed')
    return json.loads(PROTOCOL.read_text(encoding='utf-8'))


def _shift_all_absolute(value, shift, absolute_values=False):
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if key in ABSOLUTE_SCALARS:
                result[key] = float(item) + shift
            elif key in ABSOLUTE_VECTORS:
                result[key] = [float(v) + shift for v in item]
            elif key in ABSOLUTE_NESTED:
                result[key] = _shift_all_absolute(item, shift, absolute_values=True)
            else:
                result[key] = _shift_all_absolute(item, shift, absolute_values)
        return result
    if isinstance(value, list):
        return [_shift_all_absolute(v, shift, absolute_values) for v in value]
    if absolute_values and isinstance(value, (float, int)) and not isinstance(value, bool):
        return float(value) + shift
    return value


def shift_fact(fact, shift):
    if not math.isfinite(shift) or shift % 10080 != 0:
        raise ValueError('finite whole-week clock shift required')
    result = _shift_all_absolute(fact, float(shift))
    for old_h, new_h in zip(fact['historical_non_event'], result['historical_non_event']):
        assert old_h['reference_context']['clock_hour'] == new_h['reference_context']['clock_hour']
        assert old_h['reference_context']['weekday'] == new_h['reference_context']['weekday']
    start = result['task']['start_min']
    rw = result['reference_window']
    assert rw['clock_hour'] == (start % 1440.) / 60.
    assert rw['weekday'] == int(start // 1440.) % 7
    assert max(rw['pre_ends_min']) <= result['task']['notice_min']
    assert all(h['available_at_min'] < result['task']['notice_min'] for h in result['historical_non_event'])
    return result


def _weak_request(t, user, event):
    fine = np.asarray(t['relative_fine_midpoints_min'], float)
    strong, participates, probability = BASE._request_response(t['assigned_dose'], t['latent'],
        fine, t['W_min'], t['q_kw'], 'positive')
    amplitude_fraction = (.14, .20)[((user // 2) + event) % 2]
    amplitude = t['q_kw'] * amplitude_fraction
    if user % 2 == 0:
        minutes = (3., 6.)[(user // 2) % 2]
        delay = .25 + 1.50 * t['latent']['delay_uniform']
        request = amplitude * ((fine >= delay) & (fine < delay + minutes) & (fine < t['W_min']))
        request = request.astype(float) * int(participates)
        subtype = 'brief' + str(int(minutes))
    else:
        peak = float(np.max(strong))
        request = strong * (amplitude / peak) if peak > 0 else np.zeros_like(strong)
        subtype = 'sustained'
        minutes = None
    return request, dict(weak_subtype=subtype, weak_amplitude_fraction=amplitude_fraction,
        weak_amplitude_kw=amplitude, weak_rectangle_minutes=minutes,
        retained_strong_participation=bool(participates), participation_probability=probability)


def generate_reliability(seed, n_users, events_per_user=2, *, variants=('strong','weak','null'), clock_shift_min=0):
    """Generate exogenous conditions once and intervene only on response.

    non_event is a declared undelivered task observation, never an event selected
    from a responded population. It is used for training/calibration only.
    """
    if any(v not in ('strong', 'weak', 'null', 'non_event') for v in variants) or len(set(variants)) != len(variants):
        raise ValueError('unique declared reliability variants required')
    base_facts, base_truth, base_meta = BASE.generate(seed, n_users=n_users,
        events_per_user=events_per_user, W=30, q=1.5, scenario='positive')
    out = {}
    for variant in variants:
        facts, truth = [], []
        for index, (original, original_truth) in enumerate(zip(base_facts, base_truth)):
            f = copy.deepcopy(original)
            t = copy.deepcopy(original_truth)
            user, event = divmod(index, events_per_user)
            fine = np.asarray(t['relative_fine_midpoints_min'], float)
            weak = dict(weak_subtype=None, weak_amplitude_fraction=None, weak_amplitude_kw=None,
                        weak_rectangle_minutes=None)
            if variant == 'strong':
                request, participation, probability = BASE._request_response(t['assigned_dose'], t['latent'],
                    fine, t['W_min'], t['q_kw'], 'positive')
            elif variant == 'weak':
                request, weak = _weak_request(t, user, event)
                participation = weak['retained_strong_participation']
                probability = weak['participation_probability']
            else:
                request = np.zeros_like(fine)
                participation, probability = False, 0.
            full, debt = BASE._complete_response(request, fine, t['W_min'])
            reduction = BASE._minute_average(full)[60:]
            natural = np.asarray(t['true_reference_kw'], float)
            noise = np.asarray(t['measurement_error_kw'], float)
            noiseless = natural - reduction
            measured = noiseless + noise
            if not (np.isfinite(measured).all() and min(measured) >= 0 and max(measured) <= 7.2):
                raise RuntimeError('declared paired mechanism violated physical bound; no clipping')
            f.update(power_kw=measured.tolist(), observed_participation=bool(participation),
                non_event=variant == 'non_event', task_dispatched=variant != 'non_event',
                simulation_variant=variant,incentive_signal_announced=variant != 'non_event',
                offered_incentive_status=('drawn_for_paired_design_not_announced' if variant == 'non_event' else 'announced_for_dispatched_task'))
            # The fitted reference's legal prefix is unchanged by all responses.
            f = shift_fact(f, clock_shift_min)
            t.update(weak)
            t.update(scenario=variant, source_scenario='positive', true_reduction_kw=reduction.tolist(),
                noiseless_power_kw=noiseless.tolist(), post_window_remaining_debt_kwh=debt,
                participation_probability=float(probability), observed_under_factual_participation=bool(participation),
                physical_action=bool(np.any(request[(fine >= 0) & (fine < t['W_min'])] > 0)),
                clock_shift_min=clock_shift_min)
            t.update(BASE._summaries(reduction, t['relative_starts_min'], t['W_min'], t['q_kw']))
            t['threshold_positive'] = t['cumulative_response_seconds'] > 0
            t['physical_subthreshold'] = t['physical_action'] and not t['threshold_positive']
            facts.append(f)
            truth.append(t)
        meta = dict(base_meta, schema='b1.reliability-simulation.v1', source_scenario='positive',
            scenario=variant, clock_shift_min=clock_shift_min, task_dispatched=variant != 'non_event',
            non_event=variant == 'non_event', original_simulator_sha256=sha(BASE_SOURCE),
            wrapper_sha256=sha(__file__), protocol_sha256=PROTOCOL_SHA,
            paired_variants_share=['natural','measurement_noise','history','dose','L','U','latent','task'],
            weak_design='even users brief3/6; odd users normalized original strong shape; amplitude .14q/.20q alternates by user-pair and event; original strong participation',
            non_event_design='explicit no task dispatched, no response; not selected from observed events',
            non_event_incentive_field='paired exogenous random draw only; signal not actually announced or dispatched',
            truth_allowed_only_in_generator_and_evaluator=True)
        out[variant] = (facts, truth, meta)
    return out


def persist_block(phase, seed, n_users, clock_shift_min, variants):
    target = FACTS / phase
    out = generate_reliability(seed, n_users, variants=variants, clock_shift_min=clock_shift_min)
    paths = {}
    for variant, (facts, truth, meta) in out.items():
        fp = target / f'{seed}_{variant}_facts.json'
        tp = HERE / phase / 'evaluator' / f'{seed}_{variant}_truth.json'
        mp = target / f'{seed}_{variant}_metadata.json'
        dump_new(fp, facts)
        dump_new(tp, truth)
        dump_new(mp, meta)
        paths[variant] = dict(facts=str(fp), truth=str(tp), metadata=str(mp),
            n_events=len(facts), n_users=len({f['task']['user_id'] for f in facts}),
            first_notice_min=min(f['task']['notice_min'] for f in facts),
            final_label_available_min=max(f['availability']['power_records_available_at_min'] for f in facts),
            sha256={str(p.relative_to(ROOT)):sha(p) for p in (fp,tp,mp)})
    return paths


def small_checks():
    checks=[]
    def ck(name, value):
        if not value:raise AssertionError(name)
        checks.append(name)
    a = generate_reliability(7599900, 8, variants=('strong','weak','null','non_event'), clock_shift_min=2016000)
    b = generate_reliability(7599900, 8, variants=('strong','weak','null','non_event'), clock_shift_min=2016000)
    ck('deterministic reproducibility', a == b)
    for index in range(16):
        sf, st, _ = a['strong']; wf, wt, _ = a['weak']; nf, nt, _ = a['null']; ef, et, _ = a['non_event']
        for variant, (facts, truth, meta) in a.items():
            f,t = facts[index],truth[index]
            ck(f'exogenous equality {variant} {index}', f['reference_window'] == sf[index]['reference_window'] and
                f['historical_non_event'] == sf[index]['historical_non_event'] and f['factor_record'] == sf[index]['factor_record'] and f['task'] == sf[index]['task'])
            ck(f'power equation {variant} {index}', np.allclose(np.asarray(f['power_kw']), np.asarray(t['true_reference_kw']) - t['true_reduction_kw'] + np.asarray(t['measurement_error_kw']), atol=1e-14, rtol=0))
            request=(np.asarray(t['relative_starts_min'])>=0)&(np.asarray(t['relative_starts_min'])<30)
            r=np.asarray(t['true_reduction_kw'])[request]
            ck(f'threshold arithmetic {variant} {index}', t['cumulative_response_seconds'] == float(np.count_nonzero(r >= .15)*60))
            ck(f'eta arithmetic {variant} {index}', abs(t['eta'] - float(r.sum()/45)) < 1e-12)
            ck(f'physical bound {variant} {index}', min(f['power_kw']) >= 0 and max(f['power_kw']) <= 7.2)
            ck(f'absolute factor time shift {variant} {index}', f['factor_record']['treatment_set_min'] == f['task']['notice_min'] and f['factor_record']['available_at_min']['offered_incentive'] == f['task']['notice_min'])
        ck(f'non-event and null identical meter {index}', ef[index]['power_kw'] == nf[index]['power_kw'])
        ck(f'non-event undeclared task {index}', ef[index]['non_event'] is True and ef[index]['task_dispatched'] is False and not et[index]['physical_action'])
        ck(f'null dispatched but no physical action {index}', nf[index]['task_dispatched'] is True and not nt[index]['physical_action'])
        ck(f'weak participation preserved {index}', wf[index]['observed_participation'] == sf[index]['observed_participation'])
        ck(f'weak low amplitude {index}', wt[index]['weak_amplitude_fraction'] in (.14,.20) and max(np.asarray(wt[index]['true_reduction_kw'])[request]) <= .3+1e-12)
    ck('all weak subtypes', {t['weak_subtype'] for t in a['weak'][1]} == {'brief3','brief6','sustained'})
    ck('all JSON native', bool(json.dumps(a, allow_nan=False)))
    report=dict(passed=True,n_checks=len(checks),checks=checks, protocol_sha256=PROTOCOL_SHA,
        source_sha256=sha(__file__), original_simulator_sha256=sha(BASE_SOURCE),
        scope='micro generator arithmetic/provenance only; no method fitting or primary test evaluation')
    dump_new(HERE/'micro'/'generator_checks.json',report)
    print(json.dumps({k:v for k,v in report.items() if k!='checks'}),flush=True)
    return report


if __name__ == '__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--check',action='store_true')
    args=p.parse_args()
    protocol()
    if args.check:small_checks()
    else:raise SystemExit('generation is called by reviewed stage harness only')
