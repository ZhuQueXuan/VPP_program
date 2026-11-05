"""Independent fine-grid EV mechanism for a finite B1 mainline study.

No B1/RIDE implementation, estimator, fitted reference, or old test is read.
generate() returns (factual_records, evaluator_truth, provenance_metadata).
All returned values are JSON-native. potential_outcome() reads evaluator truth
only, and must never be called while fitting or selecting an estimator.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np

SIGMA_KW = .05
MAX_CHARGE_KW = 7.2
FINE_PER_MINUTE = 6
DOSE_DOMAIN = (0., 2.4)
SHAPES = ('near_step', 'slow_wavy_rise', 'early_exit', 'interrupted')


def _sigmoid(x):
    return float(1. / (1. + math.exp(-float(x))))


def _validate(seed, n_users, events_per_user, W, q, scenario, assignment):
    for value, label in ((seed, 'seed'), (n_users, 'n_users'), (events_per_user, 'events_per_user')):
        if isinstance(value, bool) or not isinstance(value, (int, np.integer)) or value < 0:
            raise ValueError(label + ' must be a nonnegative integer')
    if n_users < 1 or events_per_user < 1:
        raise ValueError('positive user/event counts required')
    if isinstance(W, bool) or not isinstance(W, (float, int)) or not math.isfinite(W) or W < 1 or W > 60 or W != int(W):
        raise ValueError('one-minute aligned task duration in [1,60] required')
    if isinstance(q, bool) or not isinstance(q, (float, int)) or not math.isfinite(q) or not .1 <= q <= 2.4:
        raise ValueError('this finite physical mechanism supports q in [0.1,2.4] kW')
    if scenario not in ('positive', 'zero') or assignment not in ('observational', 'randomized'):
        raise ValueError('unknown scenario or assignment')


def _minute_average(values):
    values = np.asarray(values, float)
    return values.reshape(-1, FINE_PER_MINUTE).mean(axis=1)


def _natural_power(t, user_offset, day_offset, trend, phase, temperature):
    """Bounded ordinary charging load, unrelated to the offered incentive."""
    return (3.65 + .30 * math.tanh(user_offset) + .30 * math.tanh(day_offset)
            + .12 * math.tanh(trend) * np.tanh(np.asarray(t) / 60.)
            + .06 * np.sin(np.asarray(t) / 13. + phase)
            + .04 * math.tanh((temperature - 25.) / 5.))


def _request_response(dose, latent, relative_fine, W, q, scenario):
    """Construct actions directly; never use an inference template to generate."""
    d = float(dose)
    if not math.isfinite(d) or not DOSE_DOMAIN[0] <= d <= DOSE_DOMAIN[1]:
        raise ValueError('potential incentive outside declared support')
    L, U = latent['L'], latent['U']
    dose_effect = 1. - math.exp(-d / .9) if scenario == 'positive' else 0.
    probability = _sigmoid(-.20 + .50 * L - .45 * U + .45 * latent['participation_user'] + 1.6 * dose_effect)
    participates = latent['participation_uniform'] < probability
    fraction = np.clip(.42 + .12 * L - .10 * U + .06 * math.tanh(latent['duration_user'])
                       + .40 * dose_effect, .12, .93)
    delay = .25 + 1.50 * latent['delay_uniform']
    end = min(float(W), delay + float(W) * float(fraction))
    t = np.asarray(relative_fine, float)
    active = (t >= delay) & (t < end) & (t < W)
    amplitude = float(q) * (.75 + .22 * _sigmoid(latent['amplitude_user']))
    shape = latent['shape']
    profile = active.astype(float)
    if shape == 'slow_wavy_rise':
        ramp = min(6., .25 * W)
        progress = np.clip((t - delay) / ramp, 0., 1.)
        # Half-cosine ramp and a mild oscillation deliberately violate an exact
        # piecewise-linear four-stage template.
        profile *= (.5 - .5 * np.cos(np.pi * progress)) * (.94 + .06 * np.sin((t - delay) * .8))
    elif shape == 'early_exit':
        # Smooth exponential fatigue during the interval, with a hard early end.
        profile *= .78 + .22 * np.exp(-np.maximum(t - delay, 0.) / 7.)
    elif shape == 'interrupted':
        gap_start = .38 * W
        gap_end = .52 * W
        profile[(t >= gap_start) & (t < gap_end)] = 0.
        profile *= .88 + .12 * np.cos((t - delay) * .45) ** 2
    elif shape != 'near_step':
        raise ValueError('unknown independent shape')
    return amplitude * profile * int(participates), bool(participates), probability


def _complete_response(request_reduction, relative_fine, W):
    """A specified recharge action, not an optimized or guaranteed feasible plan."""
    response = np.asarray(request_reduction, float).copy()
    debt_kw_minutes = float(response.sum() / FINE_PER_MINUTE)
    # A fixed extra charging rate of 1.8kW has ample power headroom under the
    # bounded natural-load mechanism. Only the actually observed post-window is
    # accounted; unobserved remaining energy is retained as debt.
    for index in np.flatnonzero(np.asarray(relative_fine) >= W):
        amount = min(1.8, max(0., debt_kw_minutes) * FINE_PER_MINUTE)
        response[index] = -amount
        debt_kw_minutes -= amount / FINE_PER_MINUTE
    return response, max(0., debt_kw_minutes / 60.)


def _summaries(interval_reduction, relative_starts, W, q):
    r = np.asarray(interval_reduction, float)
    s = np.asarray(relative_starts, float)
    request = (s >= 0.) & (s < W)
    mask = r[request] >= .1 * q
    longest = run = 0
    for yes in mask:
        run = run + 1 if yes else 0
        longest = max(longest, run)
    return dict(eta=float(r[request].sum() / (q * W)),
                request_net_kwh=float(r[request].sum() / 60.),
                cumulative_response_seconds=int(mask.sum()) * 60.,
                longest_continuous_response_seconds=float(longest * 60.) if longest * 60 >= 30 else 0.)


def potential_outcome(incentive, truth_record):
    """Evaluator-only intervention, preserving all user/event random variables."""
    W = float(truth_record['W_min']); q = float(truth_record['q_kw'])
    fine = np.asarray(truth_record['relative_fine_midpoints_min'], float)
    r, participation, probability = _request_response(incentive, truth_record['latent'], fine, W, q,
                                                      truth_record['scenario'])
    full, debt = _complete_response(r, fine, W)
    interval = _minute_average(full)[60:]
    result = _summaries(interval, truth_record['relative_starts_min'], W, q)
    result.update(observed_under_intervention_participation=participation,
                  participation_probability=probability, reduction_interval_kw=interval.tolist(),
                  post_window_remaining_debt_kwh=debt)
    return result


def generate(seed, n_users=200, events_per_user=2, W=30, q=1.5,
             scenario='positive', assignment='observational', noise_sigma_kw=.05):
    """Return JSON-native factual data and separately sealed evaluation truth.

    Scenario pairs share all sampled conditions, dose, history and meter noise.
    D depends only on L/U and independent assignment noise; stable hidden user
    behavior affects outcomes but not D conditional on L/U. Calendar, natural
    power and historical features are observed helpers, not extra confounders.
    """
    _validate(seed, n_users, events_per_user, W, q, scenario, assignment)
    if isinstance(noise_sigma_kw, bool) or not isinstance(noise_sigma_kw, (float, int)) or not math.isfinite(noise_sigma_kw) or noise_sigma_kw <= 0:
        raise ValueError('positive finite declared meter standard deviation required')
    sigma = float(noise_sigma_kw)
    W, q = float(W), float(q)
    rng = np.random.default_rng(seed)
    minute = np.arange(-75., W + 15.)
    fine = np.arange(int((W + 90.) * FINE_PER_MINUTE)) / FINE_PER_MINUTE - 75. + 1. / (2 * FINE_PER_MINUTE)
    query = minute >= -15.
    factual, truth = [], []
    for user in range(n_users):
        user_offset, participation_user, duration_user, amplitude_user = rng.normal(size=4)
        for event in range(events_per_user):
            L, U = rng.uniform(-1., 1., size=2)
            assignment_noise = float(rng.normal()); assignment_uniform = float(rng.uniform())
            d = (2.4 * _sigmoid(.6 * L + .8 * U + 1.4 * assignment_noise)
                 if assignment == 'observational' else 2.4 * assignment_uniform)
            latent = dict(L=float(L), U=float(U), participation_user=float(participation_user),
                          duration_user=float(duration_user), amplitude_user=float(amplitude_user),
                          participation_uniform=float(rng.uniform()), delay_uniform=float(rng.uniform()),
                          shape=SHAPES[int(rng.integers(0, len(SHAPES)))])
            start = 200000. + 180. * user + 20160. * event
            notice = start - 15.
            uid = f'ev-mainline-{seed}-user-{user}'
            tid = f'{uid}-event-{event}'
            meter = f'{uid}-ac-meter'
            temp = float(25. + 6. * math.tanh(float(rng.normal()) + .3 * L))
            day_offset, trend, phase = rng.normal(size=3)
            natural_fine = _natural_power(fine, user_offset, day_offset, trend, phase, temp)
            natural = _minute_average(natural_fine)
            noise = rng.uniform(-math.sqrt(3.) * sigma, math.sqrt(3.) * sigma, len(minute))
            histories = []
            for history in range(10):
                history_start = start - (history + 1) * 1440.
                hday, htrend, hphase = rng.normal(size=3)
                htemp = float(25. + 6. * math.tanh(float(rng.normal())))
                hp = _minute_average(_natural_power(fine, user_offset, hday, htrend, hphase, htemp))
                hp += rng.uniform(-math.sqrt(3.) * sigma, math.sqrt(3.) * sigma, len(minute))
                histories.append(dict(source_id=f'{tid}-non-event-history-{history}', non_event=True,
                    user_id=uid,meter_id=meter,
                    reference_context=dict(clock_hour=float((history_start%1440.)/60.),weekday=int(history_start//1440.)%7,
                        calendar_available_min=float(history_start-16.),temperature_available_min=float(history_start-16.)),
                    starts_min=(history_start + minute).tolist(), ends_min=(history_start + minute + 1.).tolist(),
                    power_kw=hp.tolist(), available_at_min=float(history_start + W + 15.),
                    temperature_c=htemp))
            prior = np.mean([np.asarray(h['power_kw'])[query] for h in histories], axis=0)
            r, participated, probability = _request_response(d, latent, fine, W, q, scenario)
            full_response, debt = _complete_response(r, fine, W)
            response = _minute_average(full_response)
            noiseless = natural - response
            measured = noiseless + noise
            if not (np.all(natural_fine >= 2.7) and np.all(measured >= 0.) and np.all(measured <= MAX_CHARGE_KW)):
                raise RuntimeError('independent physical mechanism exceeded its fixed design bounds; no clipping performed')
            task = dict(task_id=tid, user_id=uid, meter_id=meter, resource_type='EV',
                        start_min=start, end_min=start + W, notice_min=notice,
                        request_kw=q, task_pre_treatment=True)
            availability = dict(current_conditions_at_min=notice - 1., offered_incentive_at_min=notice,
                                power_records_available_at_min=start + W + 15.,
                                historical_source_completion_max_min=max(h['available_at_min'] for h in histories))
            factor_record = dict(task_id=tid, user_id=uid, meter_id=meter,
                offered_incentive=float(d), deadline_slack=float(L), demand_urgency=float(U),
                treatment_set_min=notice,
                available_at_min=dict(offered_incentive=notice, deadline_slack=notice-1., demand_urgency=notice-1.),
                state_as_of_min=dict(offered_incentive=notice, deadline_slack=notice-1., demand_urgency=notice-1.))
            ref_window = dict(task_id=tid, user_id=uid, meter_id=meter, resource_type='EV',
                task_start_min=start, task_end_min=start + W, request_kw=q, notice_min=notice,
                starts_min=(start + minute[query]).tolist(), ends_min=(start + minute[query] + 1.).tolist(),
                pre_starts_min=(start + minute[:60]).tolist(), pre_ends_min=(start + minute[:60] + 1.).tolist(),
                pre_power_kw=measured[:60].tolist(), pre_available_min=notice,
                prior_mean_kw=prior.tolist(), prior_available_min=availability['historical_source_completion_max_min'],
                prior_source_count=10, prior_source_ids=[h['source_id'] for h in histories],
                prior_sources_non_event=True, clock_hour=float((start % 1440.) / 60.),
                weekday=int(start // 1440.) % 7, calendar_available_min=notice - 1.,
                temperature_c=temp, temperature_available_min=notice - 1.)
            factual.append(dict(task=task, starts_min=ref_window['starts_min'], ends_min=ref_window['ends_min'],
                power_kw=measured[query].tolist(), noise_sigma_kw=sigma,
                reference_window=ref_window, X=[float(L), float(U)],
                deadline_slack=float(L), demand_urgency=float(U),
                declared_deadline_slack_min=float(45. + 15. * L),
                offered_incentive=float(d), incentive_unit='元/千瓦时',
                observed_participation=bool(participated), historical_non_event=histories,
                availability=availability, factor_record=factor_record, max_charge_kw=MAX_CHARGE_KW))
            evaluation = dict(task_id=tid, user_id=uid, W_min=W, q_kw=q, scenario=scenario,
                relative_starts_min=minute[query].tolist(), relative_fine_midpoints_min=fine.tolist(),
                latent=latent, assigned_dose=float(d), true_reference_kw=natural[query].tolist(),
                true_reduction_kw=response[query].tolist(), noiseless_power_kw=noiseless[query].tolist(),
                measurement_error_kw=noise[query].tolist(), participation_probability=probability,
                post_window_remaining_debt_kwh=debt,
                interpretation='declared synthetic AC trajectories; no actual SOC/capacity/user evidence')
            evaluation.update(_summaries(response[query], minute[query], W, q))
            truth.append(evaluation)
    metadata = dict(schema='b1.ev-mainline-simulation.v1', seed=int(seed), n_users=int(n_users),
        events_per_user=int(events_per_user), n_events=len(factual), W_min=W, q_kw=q,
        scenario=scenario, assignment=assignment, dose_domain=list(DOSE_DOMAIN),
        assignment_equation='logit(D/2.4)=0.6*L+0.8*U+1.4*independent_standard_normal' if assignment == 'observational' else 'D~Uniform(0,2.4)',
        covariate_order=['deadline_slack', 'demand_urgency'], target_weighting='event_equal',
        fine_grid_seconds=10, metering_minutes=1, measurement_noise=dict(kind='independent bounded uniform', standard_deviation_kw=sigma),
        query_relative_minutes=[-15., W + 15.], prefix_relative_minutes=[-75., -15.],
        history_sources_per_event=10, generator_uses_rides_template=False,
        baseline_used_as_prior=False, prior_from_observed_non_event_histories_only=True,
        stable_user_effects_affect_assignment=False, shape_classes=list(SHAPES),
        standardized_conditions='L/U and reported slack minutes are declared synthetic conditions, not measured energy/deadline/SOC or capacity truth',
        calendar_epoch='explicit synthetic day0 origin; historical constant temperature and calendar declared known before pseudo-notice',
        recovery='specified 1.8kW extra action until energy debt exhausted or observation ends; no planner',
        protected_scope='simulation mechanism and input provenance only; no real physical or causal findings')
    return factual, truth, metadata


def run_small_checks():
    """Independent arithmetic/provenance checks; does not fit any method."""
    checks = []
    def check(name, condition):
        if not condition:
            raise AssertionError(name)
        checks.append(name)
    f, t, m = generate(530001, n_users=8, events_per_user=2)
    f2, t2, m2 = generate(530001, n_users=8, events_per_user=2)
    check('seed reproducibility', (f, t, m) == (f2, t2, m2))
    zf, zt, _ = generate(530001, n_users=8, events_per_user=2, scenario='zero')
    check('paired scenarios preserve assignment and all exogenous observations', all(
        a['offered_incentive'] == b['offered_incentive'] and a['X'] == b['X'] and
        a['historical_non_event'] == b['historical_non_event'] and
        a['reference_window'] == b['reference_window'] for a, b in zip(f, zf)))
    check('user/event IDs distinguish repeated events', len({r['task']['task_id'] for r in f}) == 16 and len({r['task']['user_id'] for r in f}) == 8)
    for index, (a, b, zero) in enumerate(zip(f, t, zt)):
        w = a['reference_window']; s = np.asarray(a['starts_min']); e = np.asarray(a['ends_min'])
        check('finite bounded factual power ' + str(index), np.isfinite(a['power_kw']).all() and min(a['power_kw']) >= 0. and max(a['power_kw']) <= 7.2)
        check('true baseline at least2.7 ' + str(index), min(b['true_reference_kw']) >= 2.7)
        check('prefix information available no later than notice ' + str(index), max(w['pre_ends_min']) <= a['task']['notice_min'] and w['pre_available_min'] <= a['task']['notice_min'])
        factors = a['factor_record']; cutoff = factors['treatment_set_min']
        check('factor states and availability precede treatment assignment ' + str(index), all(factors['available_at_min'][k] <= cutoff and factors['state_as_of_min'][k] <= cutoff for k in ('deadline_slack','demand_urgency')) and factors['available_at_min']['offered_incentive'] == cutoff == a['task']['notice_min'])
        check('all historical sources completed before notice ' + str(index), all(h['available_at_min'] < a['task']['notice_min'] and max(h['ends_min']) == h['available_at_min'] for h in a['historical_non_event']))
        recomputed_prior = np.array([h['power_kw'][60:] for h in a['historical_non_event']]).mean(0)
        check('prior equals separate observed history average ' + str(index), np.array_equal(recomputed_prior, w['prior_mean_kw']))
        check('current truth not used as history ' + str(index), all(h['source_id'] != a['task']['task_id'] for h in a['historical_non_event']) and not np.array_equal(recomputed_prior, b['true_reference_kw']))
        request = (s >= a['task']['start_min']) & (e <= a['task']['end_min'])
        expected = sum(float(r) * float(dt) for r, dt in zip(np.asarray(b['true_reduction_kw'])[request], (e-s)[request])) / (1.5 * 30.)
        check('independent raw request integral ' + str(index), abs(expected - b['eta']) < 1e-12)
        check('separate noiseless truth and factual noise ' + str(index), np.allclose(np.asarray(a['power_kw']) - b['noiseless_power_kw'], b['measurement_error_kw'], atol=1e-14, rtol=0))
        check('zero-dose intervention leaves zero mechanism unchanged ' + str(index), potential_outcome(.2, zero) == potential_outcome(2.2, zero))
        check('positive intervention preserves monotone potential eta ' + str(index), potential_outcome(.2, b)['eta'] <= potential_outcome(2.2, b)['eta'])
        check('potential at factual dose recovers stored truth ' + str(index), abs(potential_outcome(a['offered_incentive'], b)['eta'] - b['eta']) < 1e-12)
    for duration in (20, 37, 45):
        ff, tt, _ = generate(530002 + duration, n_users=2, events_per_user=1, W=duration)
        check('variable task aligned ' + str(duration), all(len(r['power_kw']) == duration + 30 and r['task']['end_min'] - r['task']['start_min'] == duration for r in ff))
        check('variable task truth finite ' + str(duration), all(math.isfinite(r['eta']) for r in tt))
    rf, _, rm = generate(530010, n_users=2, events_per_user=1, assignment='randomized')
    check('random assignment interface', rm['assignment'] == 'randomized' and all(0. < r['offered_incentive'] < 2.4 for r in rf))
    stress, _, sm = generate(530011, n_users=2, events_per_user=1, noise_sigma_kw=.15)
    check('explicit higher non-Gaussian meter noise', sm['measurement_noise']['standard_deviation_kw'] == .15 and all(r['noise_sigma_kw'] == .15 for r in stress))
    check('strictly interior continuous assignment', all(0. < r['offered_incentive'] < 2.4 for r in f))
    check('JSON-native payload', isinstance(json.dumps((f, t, m), allow_nan=False), str))
    receipt = dict(passed=True, checks=checks, n_checks=len(checks), scope='small simulator arithmetic/provenance only; no fitting or main research',
                   mechanism_truth_shared_with_estimators=False, source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                   initial_check_failure='Evaluator potential_outcome initially retained prefix bins when matching query mask; fixed by the same explicit60-bin prefix removal as factual query. No model or main research was run before this fix.')
    target = Path(__file__).with_name('simulator_checks.json')
    with target.open('x', encoding='utf-8') as stream:
        json.dump(receipt, stream, ensure_ascii=False, indent=2)
    print(json.dumps({k: v for k, v in receipt.items() if k != 'checks'}, ensure_ascii=False))


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='only run independent small simulator checks')
    if parser.parse_args().check:
        run_small_checks()
