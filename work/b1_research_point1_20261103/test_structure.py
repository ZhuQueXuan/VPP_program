"""Actual PC/FCI nonlinear-CI smoke and small-SCM checks, new data only."""
from pathlib import Path
import sys
import json
import hashlib
import time
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE/'runtime/site-packages'))
sys.path.insert(0, str(ROOT/'B1算法'))
from b1_algorithm.structure import discover_factor_structure, skeleton_metrics


def generate(kind, seed, n=120):
    rng = np.random.default_rng(seed)
    l = rng.uniform(-1, 1, n)
    u = rng.uniform(-1, 1, n)
    negative = rng.normal(size=n)
    hidden = rng.normal(size=n)
    if kind == 'randomized':
        a = rng.uniform(0, 2.4, n)
    else:
        a = 2.4/(1+np.exp(-(.9*l-.8*u+.6*rng.normal(size=n) +
                             (.8*hidden if kind == 'hidden' else 0))))
    response = .55*l-.4*u+(.9*np.sin(a) if kind != 'zero' else 0)
    response += (.7*hidden if kind == 'hidden' else 0)
    probability = 1/(1+np.exp(-response))
    positive = rng.random(n) < probability
    amount = rng.beta(3+probability*5, 4, n)
    y = np.where(positive, np.rint(180*amount)*10, 0.)
    # Retain zero/full mass without jitter; N has no outgoing edge.
    y[(rng.random(n)<.03) & positive] = 1800.
    return np.column_stack([l, u, a, y, negative])


def main():
    start = time.perf_counter()
    names = ['deadline_slack', 'demand_urgency', 'incentive', 'response', 'negative_control']
    entries = []
    for k, kind in enumerate(['randomized', 'observed', 'zero', 'hidden']):
        values = generate(kind, 90331000+k)
        # Deliberately append repeated events. The backend must select exactly
        # the first event/user, never silently double independent CI sample N.
        users = [f'{kind}|u{i}' for i in range(len(values))]
        data = np.repeat(values, 2, axis=0)
        ids = np.repeat(users, 2)
        for method in ['pc_kci', 'fci_kci']:
            before = time.perf_counter()
            result = discover_factor_structure(data, ids, names, method=method,
                time_tiers={'deadline_slack': 0, 'demand_urgency': 0, 'incentive': 1,
                            'response': 2, 'negative_control': 0})
            assert result['selected_users'] == 120
            assert result['selected_event_indices'] == list(range(0, 240, 2))
            assert result['temporal_constraints_applied'] is False
            assert result['status'] == 'ok'
            assert set(e['endpoint1'] for e in result['edges']) <= {'tail', 'arrow', 'circle'}
            assert set(e['endpoint2'] for e in result['edges']) <= {'tail', 'arrow', 'circle'}
            edges = [('deadline_slack', 'response'), ('demand_urgency', 'response')]
            if kind != 'randomized':
                edges += [('deadline_slack', 'incentive'), ('demand_urgency', 'incentive')]
            if kind != 'zero':
                edges += [('incentive', 'response')]
            # Hidden H affects A and Y: their latent-projection adjacency is
            # present, even when a direct observed effect is not distinguished.
            metrics = skeleton_metrics(result, edges)
            entries.append(dict(kind=kind, method=method, result=result,
                                metrics=metrics, elapsed_seconds=time.perf_counter()-before))
            print(kind, method, metrics, flush=True)
    output = dict(status='actual_backend_checks_passed', data='new declared synthetic SCM only',
        users_per_mechanism=120, repeated_input_events_per_mechanism=240,
        entries=entries, elapsed_seconds=time.perf_counter()-start,
        graph_accuracy_universal_claim=False, real_mechanism_validation=False,
        source_sha256=hashlib.sha256((ROOT/'B1算法/b1_algorithm/structure.py').read_bytes()).hexdigest())
    with (HERE/'structure_checks.json').open('x', encoding='utf-8') as stream:
        json.dump(output, stream, ensure_ascii=False, indent=2)


if __name__ == '__main__':
    main()
