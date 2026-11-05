"""Exact constant-mean segmentation on a separately frozen development panel.

This implements unpruned O(n^2) dynamic programming, not PELT. It does not
assign business phases, read the main study, or compare superiority to F0.
"""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
import time
import numpy as np


def penalized_segment(values, penalty, min_size=3):
    """Minimize sum segment SSE + penalty * number of internal cuts.

    Each segment is [start, end); changepoints are sample indexes. Prefix
    sums give each SSE in O(1), hence O(n^2) time, O(n) auxiliary storage.
    The input is a bounded-scale finite synthetic series; prefix subtraction
    is not intended for arbitrary extremely large offsets.
    """
    y = np.asarray(values, dtype=float)
    if y.ndim != 1 or not np.all(np.isfinite(y)):
        raise ValueError('Require a finite one-dimensional series')
    n = len(y)
    if not isinstance(min_size, int) or min_size < 1 or n < min_size:
        raise ValueError('Require at least min_size observations')
    if not math.isfinite(penalty) or penalty < 0:
        raise ValueError('Penalty must be nonnegative and finite')
    prefix = np.concatenate(([0.0], np.cumsum(y)))
    square = np.concatenate(([0.0], np.cumsum(y*y)))
    costs = np.full(n+1, np.inf)
    previous = np.full(n+1, -1, dtype=int)
    costs[0] = -penalty
    for end in range(min_size, n+1):
        for start in range(0, end-min_size+1):
            if not math.isfinite(costs[start]):
                continue
            count = end-start
            total = prefix[end]-prefix[start]
            sse = max(0.0, square[end]-square[start]-total*total/count)
            candidate = costs[start]+sse+penalty
            if candidate < costs[end]:
                costs[end] = candidate
                previous[end] = start
    if previous[n] < 0:
        raise RuntimeError('No legal segmentation')
    segments = []
    end = n
    while end:
        start = int(previous[end])
        segments.append({'start':start, 'end':end,
                         'mean_kw':float((prefix[end]-prefix[start])/(end-start))})
        end = start
    segments.reverse()
    return {'objective':float(costs[n]), 'segments':segments,
            'changepoints':[segment['end'] for segment in segments[:-1]]}


def exhaustive_objective(values, penalty, min_size=3):
    """Independent tiny-series oracle: enumerate every cut subset.

    Uses direct two-pass residual arithmetic, not the DP cost recurrence or
    prefix-SSE computation. Limited to n<=12 intentionally.
    """
    y = [float(v) for v in values]
    n = len(y)
    if n > 12:
        raise ValueError('Oracle limited to n<=12')
    best = math.inf
    best_cuts = None
    legal = 0
    for mask in range(1 << (n-1)):
        cuts = [0] + [i for i in range(1,n) if mask & (1 << (i-1))] + [n]
        if any(right-left < min_size for left,right in zip(cuts[:-1],cuts[1:])):
            continue
        legal += 1
        residual_sse = 0.0
        for left,right in zip(cuts[:-1],cuts[1:]):
            segment = y[left:right]
            mean = math.fsum(segment)/len(segment)
            residual_sse += math.fsum((v-mean)**2 for v in segment)
        objective = residual_sse + penalty*(len(cuts)-2)
        if objective < best:
            best, best_cuts = objective, cuts[1:-1]
    return {'objective':best, 'changepoints':best_cuts,
            'legal_segmentations':legal}


def _signals(n):
    return {'constant':np.ones(n),
            'rectangle':np.asarray([float(n//3<=i<2*n//3) for i in range(n)]),
            'slow_ramp':np.arange(n)/(n-1)}


def run_development():
    started = time.perf_counter()
    folder = Path(__file__).resolve().parent
    protocol_path = folder/'development_protocol.json'
    protocol_bytes = protocol_path.read_bytes()
    protocol = json.loads(protocol_bytes.decode('utf-8-sig'))
    sigma = protocol['sigma_kw']
    min_size = protocol['minimum_segment_points']
    checks = []
    for n in protocol['independent_check']['lengths']:
        penalty = sigma*sigma*3*math.log(n)
        for seed in protocol['seeds']:
            rng = np.random.default_rng(seed)
            for kind,signal in _signals(n).items():
                y = signal+rng.normal(0,sigma,n)
                result = penalized_segment(y,penalty,min_size)
                oracle = exhaustive_objective(y,penalty,min_size)
                error = abs(result['objective']-oracle['objective'])
                passed = error <= protocol['independent_check']['objective_absolute_tolerance']
                checks.append({'n':n, 'seed':seed, 'kind':kind, 'objective_error':error,
                               'dp_objective':result['objective'], 'exhaustive_objective':oracle['objective'],
                               'dp_cuts':result['changepoints'], 'exhaustive_cuts':oracle['changepoints'],
                               'legal_segmentations':oracle['legal_segmentations'], 'passed':passed})
                if not passed:
                    raise AssertionError(checks[-1])
    n = protocol['n']
    penalty = sigma*sigma*3*math.log(n)
    panels = []
    for seed in protocol['seeds']:
        rng = np.random.default_rng(seed)
        for kind,signal in _signals(n).items():
            y = signal+rng.normal(0,sigma,n)
            result = penalized_segment(y,penalty,min_size)
            diagnostics = {'number_of_segments':len(result['segments'])}
            if kind == 'rectangle':
                truth = [40,80]
                diagnostics.update({'declared_step_indexes':truth,
                    'nearest_boundary_errors_s':[min(abs(c-cut) for c in result['changepoints'])*protocol['dt_s']
                                                 if result['changepoints'] else None for cut in truth],
                    'number_of_fitted_internal_cuts':len(result['changepoints'])})
            elif kind == 'constant':
                diagnostics['false_internal_cuts'] = len(result['changepoints'])
            else:
                diagnostics['interpretation'] = 'Continuous ramp has no finite mean-jump truth; fitted steps approximate slope and cannot be labeled physical stages.'
            panels.append({'seed':seed, 'kind':kind, 'penalty':penalty,
                           'signal_kw':signal.tolist(), 'observed_kw':y.tolist(),
                           'fit':result, 'development_description':diagnostics})
    out = {'id':protocol['id'], 'identity':protocol['identity'],
           'protocol_sha256':hashlib.sha256(protocol_bytes).hexdigest(),
           'main_study_data_read':False, 'main_test_tuned':False,
           'algorithm':'exact unpruned penalized constant-mean DP, not PELT',
           'complexity':'O(n^2) time, O(n) auxiliary storage',
           'independent_optimum_checks':len(checks), 'all_checks_passed':all(v['passed'] for v in checks),
           'maximum_objective_error':max(v['objective_error'] for v in checks),
           'checks':checks, 'development_panels':panels,
           'elapsed_s':time.perf_counter()-started,
           'scope':'Constructed development correctness and approximation behavior only; no F0 superiority or real EV phase identification claim.'}
    (folder/'segmentation_development.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:out[k] for k in ['id','independent_optimum_checks','all_checks_passed','maximum_objective_error','elapsed_s']},ensure_ascii=False))
    print(json.dumps([{'seed':v['seed'],'kind':v['kind'],**v['development_description']} for v in panels],ensure_ascii=False))
    return out

if __name__=='__main__':
    run_development()
