"""Resource-neutral input and factor evidence for a single incentive study."""
from dataclasses import asdict, dataclass
from itertools import combinations

import numpy as np
from scipy.special import logit

from .contracts import identifier, number


@dataclass(frozen=True)
class ResourceFactorStudy:
    resource_type: str
    factors: tuple[tuple[str, str], ...]
    offer_unit: str
    outcome_name: str
    outcome_unit: str
    measurement_definition: str
    window_minutes: float
    continuous_offer_domain: tuple[float, float] | None = None


def _read_events(study, records):
    for field in ('resource_type', 'offer_unit', 'outcome_name', 'outcome_unit', 'measurement_definition'):
        identifier(getattr(study, field), field)
    window = number(study.window_minutes, 'window_minutes')
    names = [identifier(name, 'factor name') for name, _ in study.factors]
    for _, unit in study.factors:
        identifier(unit, 'factor unit')
    if window <= 0 or not 1 <= len(names) <= 8 or len(set(names + ['offer', 'outcome'])) != len(names) + 2:
        raise ValueError('Use a positive study window and 1..8 unique factor names')
    if study.continuous_offer_domain is not None:
        low, high = [number(x, 'offer domain') for x in study.continuous_offer_domain]
        if not 0 <= low < high:
            raise ValueError('Expected an increasing nonnegative offer domain')
    events, seen = {}, set()
    for row in records:
        event = identifier(row['event_id'], 'event_id')
        cluster = identifier(row['cluster_id'], 'cluster_id')
        if any(row[key] != getattr(study, key) for key in ('resource_type', 'offer_unit', 'outcome_name', 'outcome_unit')):
            raise ValueError('Event resource, unit or outcome disagrees with the study: ' + event)
        if event in seen:
            raise ValueError('Duplicate event ID: ' + event)
        seen.add(event)
        formed, notified, start, end, measured = [number(row[key], key) for key in (
            'offer_formed_min', 'notice_min', 'start_min', 'end_min', 'outcome_available_min')]
        if not formed <= notified <= start < end <= measured or not np.isclose(end-start, window, rtol=0, atol=1e-8):
            raise ValueError('Invalid event timeline or study window: ' + event)
        values = []
        for name in names:
            factor = row['pre_factors'][name]
            as_of = number(factor['measured_min'], name + ' measured time')
            available = number(factor['available_min'], name + ' availability')
            if not as_of <= available <= formed:
                raise ValueError('Factor unavailable at offer formation: ' + event + '/' + name)
            values.append(number(factor['value'], name))
        amount = number(row['offered_incentive'], 'offered_incentive')
        if amount < 0 or (study.continuous_offer_domain is not None and not low < amount < high):
            raise ValueError('Offer outside its declared domain: ' + event)
        value = number(row['outcome_value'], 'outcome_value')
        if cluster not in events or (start, event) < events[cluster][:2]:
            events[cluster] = (start, event, values + [amount, value])
    selected = [events[cluster] for cluster in sorted(events)]
    if len(selected) < 30:
        raise ValueError('At least 30 independent clusters are required')
    matrix = np.asarray([row[2] for row in selected], dtype=float)
    if np.any(np.ptp(matrix, axis=0) <= 1e-12):
        raise ValueError('Each analyzed variable needs nonconstant observations')
    return names, matrix, [row[1] for row in selected], len(seen)


def _stable_skeleton(ci_test, tiers, alpha, restricted):
    """Stable skeleton search with an optional upper bound on separator time."""
    count = len(tiers)
    edges = set(combinations(range(count), 2))
    for depth in range(count-1):
        neighbors = [set() for _ in tiers]
        for a, b in edges:
            neighbors[a].add(b)
            neighbors[b].add(a)
        remove = set()
        tested = False
        for a, b in sorted(edges):
            subsets = set()
            for side, other in ((a, b), (b, a)):
                pool = neighbors[side] - {other}
                if restricted:
                    pool = {node for node in pool if tiers[node] <= max(tiers[a], tiers[b])}
                subsets.update(combinations(sorted(pool), depth))
            for condition in sorted(subsets):
                tested = True
                if ci_test(a, b, condition) > alpha:
                    remove.add((a, b))
                    break
        edges.difference_update(remove)
        if not tested:
            break
    return edges


def _quote_screen(matrix, domain):
    """Grouped additive quadratic Gaussian BIC on a declared logit quote scale."""
    factors = matrix[:, :-2]
    n, k = factors.shape
    scaled = (factors - factors.mean(axis=0)) / factors.std(axis=0)
    y = logit((matrix[:, -2] - domain[0]) / (domain[1] - domain[0]))
    candidates = []
    for size in range(k+1):
        for indices in combinations(range(k), size):
            x = scaled[:, indices]
            design = np.column_stack([np.ones(n), x, x*x])
            coef, _, rank, _ = np.linalg.lstsq(design, y, rcond=None)
            if rank == design.shape[1]:
                residual = y-design@coef
                bic = n*np.log(max(float(residual@residual)/n, 1e-15)) + (rank+1)*np.log(n)
                candidates.append((bic, size, indices))
    return list(min(candidates)[2])


def analyze_resource_factors(study, records, *, alpha=.05):
    """Compare chronological skeleton evidence and an optional bounded quote screen.

    One earliest event per independent cluster supplies the structure sample.
    Associations serve as candidates for scientific review and downstream adjustment.
    """
    if not 0 < alpha < 1:
        raise ValueError('Expected 0 < alpha < 1')
    names, matrix, event_ids, n_events = _read_events(study, records)
    from causallearn.utils.cit import CIT

    ci = CIT(matrix, 'kci')
    tiers = [0]*len(names) + [1, 2]
    variables = names + ['offer', 'outcome']
    offer, outcome = len(names), len(names)+1
    unrestricted = _stable_skeleton(ci, tiers, alpha, False)
    tiered = _stable_skeleton(ci, tiers, alpha, True)

    def describe(edges, quote_indices=None):
        by_quote = set(quote_indices) if quote_indices is not None else {i for i in range(offer) if (i, offer) in edges}
        by_outcome = {i for i in range(offer) if (i, outcome) in edges}
        return dict(adjacencies=[[variables[a], variables[b]] for a, b in sorted(edges)],
                    quote_method='skeleton' if quote_indices is None else 'grouped_quadratic_logit_BIC',
                    quote_candidates=[names[i] for i in sorted(by_quote)],
                    outcome_candidates=[names[i] for i in sorted(by_outcome)],
                    common_candidates=[names[i] for i in sorted(by_quote & by_outcome)])

    evidence = {'kci': describe(unrestricted), 'tiered_kci': describe(tiered)}
    if study.continuous_offer_domain is not None:
        evidence['quote_bic_plus_tiered'] = describe(tiered, _quote_screen(matrix, study.continuous_offer_domain))
    return dict(schema_version='b1.resource-factor-study.v1', study=asdict(study), input_events=n_events,
                selected_events=event_ids, independent_clusters=len(event_ids), alpha=alpha,
                temporal_tiers=dict(zip(variables, tiers)), evidence=evidence,
                interpretation='candidate associations for review; temporal order is supplied by the caller',
                automatic_adjustment_selection=False)
