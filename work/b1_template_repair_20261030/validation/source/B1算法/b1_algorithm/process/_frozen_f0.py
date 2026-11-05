"""Frozen F0 interval feature extractor for declared synthetic EV panels.

Powers are left-constant on [t[i], t[i+1]). A dwell covers complete
intervals; confirmation is the end of the final required interval.
The onset bracket uses preceding and first qualifying sample times.
"""
from __future__ import annotations
import math


def _run(mask, indexes, dwell):
    count = 0
    start = None
    previous = None
    for i in indexes:
        if mask[i] and (previous is None or i == previous + 1):
            count += 1
        elif mask[i]:
            count = 1
        else:
            count = 0
        if count == 1:
            start = i
        if count >= dwell:
            return start, i
        previous = i
    return None


def extract(t, reference, measured, t0=600.0, t1=1800.0, q=1.5,
            onset_kw=0.15, target_fraction=0.9, dwell_samples=3,
            recovery_band_kw=0.15):
    """Return observed features, availability and distinct recovery states.

    Missing means None or a nonfinite measured/reference value. No missing
    interval is bridged. Threshold detection does not infer participation.
    Units: seconds, kW, kWh, dimensionless Y. This is retrospective analysis.
    """
    t = [float(v) for v in t]
    n = len(reference)
    if len(measured) != n or len(t) != n + 1 or n == 0:
        raise ValueError('Require n powers and n+1 time boundaries')
    if not all(math.isfinite(v) for v in t) or any(t[i+1] <= t[i] for i in range(n)):
        raise ValueError('Time boundaries must be finite and strictly increasing')
    if not (math.isfinite(q) and q > 0 and t0 < t1):
        raise ValueError('Request must have positive q and duration')
    if not (isinstance(dwell_samples, int) and dwell_samples >= 1):
        raise ValueError('dwell_samples must be a positive integer')
    r = []
    for a, b in zip(reference, measured):
        if a is None or b is None:
            r.append(None)
        else:
            value = float(a) - float(b)
            r.append(value if math.isfinite(value) else None)
    overlaps = [max(0.0, min(t[i+1], t1) - max(t[i], t0)) for i in range(n)]
    request_indexes = [i for i, overlap in enumerate(overlaps) if overlap > 0]
    covered_s = sum(overlaps[i] for i in request_indexes if r[i] is not None)
    request_s = t1 - t0
    full_request = abs(covered_s - request_s) <= 1e-8
    net_kws = sum(r[i] * overlaps[i] for i in request_indexes if r[i] is not None)
    result = {
        'Y': net_kws/(q*request_s) if full_request else None,
        'request_net_kwh': net_kws/3600 if full_request else None,
        'request_positive_kwh': sum(max(0, r[i])*overlaps[i] for i in request_indexes if r[i] is not None)/3600 if full_request else None,
        'request_negative_kwh': sum(min(0, r[i])*overlaps[i] for i in request_indexes if r[i] is not None)/3600 if full_request else None,
        'request_coverage': covered_s/request_s,
        'onset_interval_s': None, 'onset_confirmation_s': None,
        'onset_delay_interval_s': None, 'target_interval_s': None,
        'target_confirmation_s': None,
        'power_recovery_time_s': None, 'power_recovery_confirmation_s': None,
        'power_recovery_interval_s': None, 'energy_recovery_time_s': None,
        'power_recovery_status': 'not_applicable',
        'energy_recovery_status': 'not_applicable',
        'post_rebound_kwh': None, 'remaining_debt_kwh': None,
        'stage': 'unavailable' if not full_request else 'no_response',
        'observation_end_s': t[-1],
        'criterion': 'observed_threshold_dwell; not participation inference',
    }
    mask = [v is not None and v >= onset_kw for v in r]
    onset = _run(mask, request_indexes, dwell_samples)
    target = _run([v is not None and v >= target_fraction*q for v in r], request_indexes, dwell_samples)
    if onset:
        first, last = onset
        lo = max(t0, t[max(first-1, 0)])
        hi = max(t0, t[first])
        result['onset_interval_s'] = [lo, hi]
        result['onset_delay_interval_s'] = [lo-t0, hi-t0]
        result['onset_confirmation_s'] = min(t[last+1], t1)
        if full_request:
            result['stage'] = 'response' if target else 'partial'
    if target:
        first, last = target
        result['target_interval_s'] = [max(t0, t[max(first-1, 0)]), max(t0, t[first])]
        result['target_confirmation_s'] = min(t[last+1], t1)
    post = [i for i in range(n) if t[i+1] > t1]
    post_complete = t[-1] >= t1 and all(r[i] is not None for i in post)
    result['post_rebound_kwh'] = sum(max(0.0, -r[i])*(t[i+1]-max(t[i], t1)) for i in post)/3600 if post_complete else None
    if not full_request:
        result['power_recovery_status'] = 'unavailable'
        result['energy_recovery_status'] = 'unavailable'
        return result
    if not onset:
        return result
    result['remaining_debt_kwh'] = net_kws/3600
    if net_kws <= 1e-9:
        result['energy_recovery_status'] = 'recovered'
        result['energy_recovery_time_s'] = t1
    if not post or not post_complete:
        status = 'unavailable' if any(r[i] is None for i in post) else 'right_censored'
        result['power_recovery_status'] = status
        if result['energy_recovery_time_s'] is None:
            result['energy_recovery_status'] = status
        return result
    recovered = _run([v is not None and abs(v) <= recovery_band_kw for v in r], post, dwell_samples)
    result['power_recovery_status'] = 'recovered' if recovered else 'right_censored'
    if recovered:
        first, last = recovered
        result['power_recovery_time_s'] = max(t[first], t1)
        result['power_recovery_interval_s'] = [max(t1, t[max(first-1, 0)]), max(t[first], t1)]
        result['power_recovery_confirmation_s'] = t[last+1]
    debt = net_kws
    result['energy_recovery_status'] = 'right_censored'
    if debt <= 1e-9:
        result['energy_recovery_status'] = 'recovered'
        result['energy_recovery_time_s'] = t1
    for i in post:
        start = max(t[i], t1)
        next_debt = debt + r[i]*(t[i+1]-start)
        if result['energy_recovery_time_s'] is None and debt > 1e-9 and next_debt <= 1e-9:
            result['energy_recovery_time_s'] = start + debt/(-r[i])
            result['energy_recovery_status'] = 'recovered'
        debt = next_debt
    result['remaining_debt_kwh'] = debt/3600
    return result
