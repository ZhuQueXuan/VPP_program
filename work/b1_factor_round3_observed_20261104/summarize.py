"""Recompute the two observation tables from the frozen event ledgers."""
import csv
import gzip
import json
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path
from statistics import mean, median


BASE = Path(__file__).resolve().parent
GATES = ('new_below_6', 'pre_time_unavailable', 'pre_limit_unstable_or_missing',
         'pre_status_not_charging', 'pre_current_low_or_missing', 'pre_current_unstable')
SIDES = ('below', 'above')


def read_rows(name):
    with gzip.open(BASE / name, 'rt', encoding='utf-8') as stream:
        return [json.loads(line) for line in stream]


def csv_output(name, records):
    names = list(dict.fromkeys(k for row in records for k in row))
    with (BASE / name).open('x', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, names)
        writer.writeheader()
        writer.writerows(records)


def key(row):
    return row['charger_id'], row['transaction_id']


def iso_week(text):
    day = date.fromisoformat(text[:10])
    return (day - timedelta(days=day.weekday())).isoformat()


def dimensions(rows, week='week', group='group'):
    return {'n': len(rows), 'transactions': len({key(r) for r in rows}),
            'chargers': len({r['charger_id'] for r in rows}),
            'weeks': len({r[week] for r in rows}),
            'groups': len({r[group] for r in rows if r[group] not in ('NULL', 'None', '')}),
            'rows_unknown_group': sum(r[group] in ('NULL', 'None', '') for r in rows)}


def quantile(values, proportion):
    if not values:
        return None
    ordered = sorted(values)
    rank = (len(ordered) - 1) * proportion
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (rank - lower) * (ordered[upper] - ordered[lower])


def diff_if_known(a, b):
    return None if a is None or b is None else round(a - b, 9)


def event_flows(rows):
    counts = Counter()
    for event in rows:
        later = event['next']
        timing = event['next_timing']
        counts[f'timing_{timing}'] += 1
        counts['y_minute_readable'] += event['y_abs'] is not None
        counts['y_minute_field_unreadable'] += timing == 'minute' and event['y_abs'] is None
        counts['visible_status1_within_30min'] += event['first_visible_status1_within_30min_s'] is not None
        if later is None:
            counts['next_status_unobserved'] += 1
            continue
        status = str(later['status'])
        counts[f'next_status_{status}'] += 1
        read_state = 'readable' if later['current'] is not None else 'unreadable'
        counts[f'next_status_{status}_{read_state}'] += 1
        counts[f'{timing}_status_{status}_{read_state}'] += 1
        for source in ('back', 'charger'):
            new_drop = diff_if_known(event['index'][source], later[source])
            counts[f'next_{source}_re_drop_ge2'] += new_drop is not None and new_drop >= 2
            counts[f'next_{source}_re_drop_unknown'] += new_drop is None
            counts[f'minute_{source}_re_drop_ge2'] += timing == 'minute' and new_drop is not None and new_drop >= 2
    return dict(counts)


def discrepancy(rows, stage, role, source, snapshot):
    sample = rows if snapshot == 'same' else [r for r in rows if r['next'] is not None and
                                             (snapshot != 'next_minute' or r['next_timing'] == 'minute')]
    selected_field = 'index' if snapshot == 'same' else 'next'
    diffs = [diff_if_known(r[selected_field]['back'], r[selected_field]['charger']) for r in sample]
    known = [x for x in diffs if x is not None]
    other = 'charger' if source == 'back' else 'back'
    same_drop = [diff_if_known(r['previous'][other], r['index'][other]) for r in rows]
    return {'trial': stage, 'role': role, 'source': source, 'snapshot': snapshot,
            'selected_index_denominator': len(rows), **dimensions(sample), 'two_limits_readable': len(known),
            'pair_missing_among_snapshot': len(sample) - len(known),
            'equal': sum(x == 0 for x in known), 'within_0_25': sum(abs(x) <= .25 for x in known),
            'abs_ge_1': sum(abs(x) >= 1 for x in known),
            'median_back_minus_charger': median(known) if known else None,
            'q25_back_minus_charger': quantile(known, .25), 'q75_back_minus_charger': quantile(known, .75),
            'median_abs_difference': median([abs(x) for x in known]) if known else None,
            'other_same_drop_ge2': sum(x is not None and x >= 2 for x in same_drop) if snapshot == 'same' else None,
            'other_same_no_drop_ge2': sum(x is not None and x < 2 for x in same_drop) if snapshot == 'same' else None,
            'other_same_drop_unknown': sum(x is None for x in same_drop) if snapshot == 'same' else None,
            **(event_flows(rows) if snapshot == 'same' else {})}


def measure(rows):
    observed = [r for r in rows if r['y_abs'] is not None]
    matched = [r for r in rows if r['sham']['point'] is not None]
    paired = [r for r in matched if r['delta'] is not None and r['sham']['point']['delta'] is not None]
    return {**dimensions(rows), **event_flows(rows),
            'observed_chargers': len({r['charger_id'] for r in observed}),
            'observed_weeks': len({r['week'] for r in observed}),
            'y_mean': mean(r['y_abs'] for r in observed) if observed else None,
            'delta_mean': mean(r['delta'] for r in observed) if observed else None,
            'delta_median': median(r['delta'] for r in observed) if observed else None,
            'delta_q25': quantile([r['delta'] for r in observed], .25),
            'delta_q75': quantile([r['delta'] for r in observed], .75),
            'i_pre_mean': mean(r['i_pre'] for r in rows) if rows else None,
            'i_ref_mean': mean(r['i_ref'] for r in rows) if rows else None,
            'drop_mean': mean(r['drop'] for r in rows) if rows else None,
            'ref_minus_pre_mean': mean(r['i_ref'] - r['i_pre'] for r in rows) if rows else None,
            'sham_matched': len(matched), 'sham_missing': len(rows) - len(matched),
            'sham_no_candidate_at_least_600s_earlier': sum(r['sham']['status'] == 'no_candidate_at_least_600s_earlier' for r in rows),
            'sham_no_eligible': sum(r['sham']['status'] == 'no_eligible_sham' for r in rows),
            'sham_y_readable': sum(r['sham']['point']['y_abs'] is not None for r in matched),
            'paired_y_readable': len(paired),
            'paired_real_delta_mean': mean(r['delta'] for r in paired) if paired else None,
            'paired_sham_delta_mean': mean(r['sham']['point']['delta'] for r in paired) if paired else None,
            'paired_sham_ref_minus_pre_mean': mean(r['sham']['point']['i_ref'] - r['sham']['point']['i_pre'] for r in paired) if paired else None,
            'paired_delta_difference_mean': mean(r['delta'] - r['sham']['point']['delta'] for r in paired) if paired else None}


def support_status(groups):
    info = {k: dimensions(v) for k, v in groups.items()}
    weeks = all(info[k]['weeks'] >= 3 for k in SIDES)
    return ('primary' if weeks and all(info[k]['chargers'] >= 10 for k in SIDES) else
            'exploratory_only' if weeks and all(info[k]['chargers'] >= 5 for k in SIDES) else 'unsupported')


def bounds(rows, ceiling):
    current = [r['y_abs'] for r in rows if r['y_abs'] is not None]
    return (sum(current) / len(rows), (sum(current) + ceiling * (len(rows) - len(current))) / len(rows))


def combine(cells):
    selected = {k: [r for g in cells for r in g[k]] for k in SIDES}
    measured = [(measure(g['below']), measure(g['above'])) for g in cells]
    observed = [(a, b) for a, b in measured if a['y_mean'] is not None and b['y_mean'] is not None]
    result = {'support_cells': len(cells), 'cells_with_observed_both_sides': len(observed),
              **{f'{k}_{name}': value for k, rows in selected.items() for name, value in measure(rows).items()}}
    for field in ('y_mean', 'delta_mean', 'i_pre_mean', 'i_ref_mean', 'drop_mean', 'ref_minus_pre_mean'):
        source = observed if field in ('y_mean', 'delta_mean') else measured
        result[field + '_below_minus_above'] = mean(a[field] - b[field] for a, b in source) if source else None
    for ceiling in (32, 80):
        if not cells:
            continue
        limits = [(bounds(g['below'], ceiling), bounds(g['above'], ceiling)) for g in cells]
        lower = mean(a[0] - b[1] for a, b in limits)
        upper = mean(a[1] - b[0] for a, b in limits)
        ref = result['i_ref_mean_below_minus_above']
        result.update({f'abs_0_{ceiling}_lower': lower, f'abs_0_{ceiling}_upper': upper,
                       f'delta_0_{ceiling}_lower': ref - upper, f'delta_0_{ceiling}_upper': ref - lower,
                       f'observed_above_{ceiling}': sum(r['y_abs'] is not None and r['y_abs'] > ceiling
                                                        for rows in selected.values() for r in rows)})
    return result


def all_slices(rows):
    split = defaultdict(list)
    for row in rows:
        split[row['trial'], row['role']].append(row)
        split[row['trial'], 'pooled_development'].append(row)
    return split


def build_funnel(txs, candidates):
    table = []
    tx_split = all_slices(txs)
    candidate_split = all_slices(candidates)
    for (trial, role), transactions in sorted(tx_split.items()):
        for source in ('back', 'charger'):
            for stage, subset in (
                ('transactions', transactions), ('in_bounds_rows', [r for r in transactions if r['in_bounds_rows']]),
                ('readable_adjacent_pairs', [r for r in transactions if r['entrances'][source].get('readable_adjacent_pairs')]),
            ):
                named = [{**r, 'week': iso_week(r['start_utc']), 'group': r['book_group']} for r in subset]
                table.append({'trial': trial, 'role': role, 'source': source, 'gate': stage,
                              'count_basis': 'transaction_start_week_and_book_group', **dimensions(named)})
            subset = [r for r in candidate_split[trial, role] if r['source'] == source]
            gates = ('raw_drop_ge2', *GATES, 'earliest_qualified')
            for i, gate in enumerate(gates):
                if gate == 'earliest_qualified':
                    subset = [r for r in subset if r['selected']]
                elif i:
                    subset = [r for r in subset if r['reason'] != gate]
                named = [{**r, 'week': iso_week(r['utc'])} for r in subset]
                table.append({'trial': trial, 'role': role, 'source': source, 'gate': 'passed_' + gate,
                              'count_basis': 'event_utc_week_and_meter_group', **dimensions(named)})
    return table


def stability_report(candidates):
    rows = []
    for (trial, role), sample in sorted(all_slices(candidates).items()):
        for source in ('back', 'charger'):
            for reason in ('pre_current_unstable', 'qualified'):
                records = [r for r in sample if r['source'] == source and r['reason'] == reason]
                shifts = [r['state'][1] - r['state'][0] for r in records]
                spreads = [max(abs(r['pre_and_index'][0]['current'] - r['pre_and_index'][1]['current']),
                               abs(r['pre_and_index'][2]['current'] - r['pre_and_index'][3]['current']))
                           for r in records]
                rows.append({'trial': trial, 'role': role, 'source': source, 'reason': reason,
                             **dimensions([{**r, 'week': iso_week(r['utc'])} for r in records]),
                             'next_minute': sum(r['stability_gate_minute_point'] for r in records),
                             'y_readable': sum(r['stability_gate_y_readable'] for r in records),
                             'median_i_pre': median([r['state'][0] for r in records]) if records else None,
                             'median_signed_i_ref_minus_i_pre': median(shifts) if shifts else None,
                             'median_abs_i_ref_minus_i_pre': median([abs(s) for s in shifts]) if shifts else None,
                             'median_largest_within_window_spread': median(spreads) if spreads else None})
    return rows


def build_tables(txs, candidates, events):
    table1 = []
    table2 = []
    support = []
    split = all_slices(events)
    for trial, role in sorted(all_slices(txs)):
        for source in ('back', 'charger'):
            subset = [r for r in split[trial, role] if r['source'] == source]
            for snapshot in ('same', 'next', 'next_minute'):
                table1.append(discrepancy(subset, trial, role, source, snapshot))
        current_events = [r for r in split[trial, role] if r['source'] == 'charger']
        for side in (*SIDES, 'boundary'):
            rows = [r for r in current_events if r['side'] == side]
            table2.append({'trial': trial, 'role': role, 'scope': 'all_eligible_descriptive', 'side': side, **measure(rows)})
        if role != 'pooled_development':
            continue
        cells = defaultdict(lambda: {k: [] for k in SIDES})
        for row in current_events:
            if row['side'] in SIDES:
                cells[tuple(row['cell'])][row['side']].append(row)
        tiers = defaultdict(list)
        for (i_pre, drop), sides in sorted(cells.items()):
            status = support_status(sides)
            tiers[status].append(sides)
            for side, rows in sides.items():
                info = measure(rows)
                for dev_role in ('train', 'development_validation'):
                    info[f'{dev_role}_n'] = sum(r['role'] == dev_role for r in rows)
                    info[f'{dev_role}_observed'] = sum(r['role'] == dev_role and r['y_abs'] is not None for r in rows)
                support.append({'trial': trial, 'cell_i_pre_left': i_pre, 'cell_drop_left': drop,
                                'status': status, 'side': side, **info})
        for name, sets in (('primary', tiers['primary']),
                           ('exploratory_includes_primary', tiers['primary'] + tiers['exploratory_only'])):
            table2.append({'trial': trial, 'role': role, 'scope': name, 'side': 'below_minus_above', **combine(sets)})
    return table1, table2, support


if __name__ == '__main__':
    txs, candidates, events = (read_rows(n) for n in ('transactions.jsonl.gz', 'candidates.jsonl.gz', 'events.jsonl.gz'))
    table1, table2, support = build_tables(txs, candidates, events)
    csv_output('table1_record_limits.csv', table1)
    csv_output('table2_observed_current.csv', table2)
    csv_output('support_cells.csv', support)
    csv_output('funnel.csv', build_funnel(txs, candidates))
    csv_output('stability_selection.csv', stability_report(candidates))
