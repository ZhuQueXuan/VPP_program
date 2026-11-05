"""Independently reconcile observation ledgers and replay a development-only raw sample."""
import csv
import gzip
import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from zipfile import ZipFile


BASE = Path(__file__).resolve().parent
ADMISSION = BASE.parent / 'b1_factor_round2_admission_20261104'
ROLES = {'train', 'development_validation'}


def read_jsonl(name):
    with gzip.open(BASE / name, 'rt', encoding='utf-8') as stream:
        return [json.loads(line) for line in stream]


def read_table(name):
    with (BASE / name).open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def hash_file(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for data in iter(lambda: stream.read(2**20), b''):
            h.update(data)
    return h.hexdigest()


def transaction(row):
    return row['charger_id'], row['transaction_id'], row['role']


def identity(row):
    return (*transaction(row), row['source'])


def time_between(a, b):
    return (datetime.fromisoformat(b['utc']) - datetime.fromisoformat(a['utc'])).total_seconds()


def decimal_or_none(value):
    return None if value is None else Decimal(str(value))


def candidate_reason(candidate):
    points = candidate['pre_and_index']
    source = candidate['source']
    old, new = (decimal_or_none(candidate[n]) for n in ('old', 'new'))
    assert old - new >= 2
    assert points[-1]['line'] == candidate['line']
    assert decimal_or_none(points[-2][source]) == old
    assert decimal_or_none(points[-1][source]) == new
    if new < 6:
        return 'new_below_6'
    if len(points) < 5 or not all(45 <= time_between(a, b) <= 75 for a, b in zip(points, points[1:])):
        return 'pre_time_unavailable'
    pre = points[:4]
    limits = [decimal_or_none(p[source]) for p in pre]
    if None in limits or max(limits) - min(limits) > Decimal('.25'):
        return 'pre_limit_unstable_or_missing'
    if any(p['status'] != 2 for p in pre):
        return 'pre_status_not_charging'
    current = [decimal_or_none(p['current']) for p in pre]
    if None in current:
        return 'pre_current_low_or_missing'
    early, near = sum(current[:2]) / 2, sum(current[2:]) / 2
    if min(early, near) < 3:
        return 'pre_current_low_or_missing'
    assert math.isclose(early, candidate['state'][0], abs_tol=1e-9)
    assert math.isclose(near, candidate['state'][1], abs_tol=1e-9)
    if max(abs(current[0] - current[1]), abs(current[2] - current[3])) > 1 or abs(early - near) > Decimal('.5'):
        return 'pre_current_unstable'
    return 'qualified'


def verify_index(row):
    post = row['next']
    gap = time_between(row['index'], post) if post else None
    stop = row['stop_gap_s']
    if not post:
        timing = 'no_later_trade_ends_by_75s' if stop <= 75 else 'no_later_trade_extends_past_75s'
    else:
        timing = 'earlier_than_45s' if gap < 45 else 'later_than_75s' if gap > 75 else 'minute'
    assert row['next_gap_s'] == gap and row['next_timing'] == timing
    assert row['y_abs'] == (post['current'] if timing == 'minute' else None)
    if row['y_abs'] is None:
        assert row['delta'] is None
    else:
        assert math.isclose(row['delta'], row['i_ref'] - row['y_abs'], abs_tol=1e-9)


def verify_ledgers(txs, candidates, events):
    ledger = {transaction(row): row for row in txs}
    assert len(ledger) == len(txs) == 15698
    assert {row['role'] for row in txs} == ROLES
    assert ('0035000117', '100012') not in {key[:2] for key in ledger}
    collected = defaultdict(Counter)
    earliest = {}
    chosen = set()
    for row in candidates:
        assert transaction(row) in ledger
        reason = candidate_reason(row)
        assert row['reason'] == reason
        key = identity(row)
        collected[key][reason] += 1
        collected[key]['raw_drops'] += 1
        if reason == 'qualified':
            earliest[key] = min(earliest.get(key, row['line']), row['line'])
        if row['selected']:
            assert reason == 'qualified'
            chosen.add((*key, row['line']))
    assert chosen == {(*key, line) for key, line in earliest.items()}
    for row in txs:
        for source, counts in row['entrances'].items():
            observed = {k: v for k, v in counts.items() if k != 'readable_adjacent_pairs'}
            assert observed == collected[(*transaction(row), source)]
    assert len({identity(r) for r in events}) == len(events)
    assert chosen == {(*identity(r), r['index']['line']) for r in events}
    sham_count = 0
    for row in events:
        verify_index(row)
        if row['source'] != 'charger':
            continue
        margin = Decimal(str(row['i_pre'])).quantize(Decimal('.0000001')) - Decimal(str(row['new']))
        expected = 'below' if margin >= 1 else 'above' if margin <= -1 else 'boundary'
        assert row['side'] == expected
        assert row['cell'] == [int(row['i_pre'] // 5) * 5, int(row['drop'] // 5) * 5]
        sham = row['sham']['point']
        if sham is None:
            continue
        sham_count += 1
        verify_index(sham)
        points = [*sham['pre'], sham['index'], sham['next']]
        limits = [Decimal(str(p['charger'])) for p in points]
        assert max(limits) - min(limits) <= Decimal('.25')
        assert all(45 <= time_between(a, b) <= 75 for a, b in zip(points, points[1:]))
        assert time_between(sham['index'], row['index']) >= 600
        assert abs(sham['i_pre'] - row['i_pre']) <= 1 + 1e-9
    return sham_count


def verify_tables(events):
    checks = 0
    for row in read_table('table1_record_limits.csv'):
        matches = [r for r in events if r['source'] == row['source'] and r['trial'] == row['trial'] and
                   row['role'] in ('pooled_development', r['role'])]
        assert len(matches) == int(row['selected_index_denominator'])
        tag = row['snapshot']
        points = [r['index'] if tag == 'same' else r['next'] for r in matches
                  if tag != 'next_minute' or r['next_timing'] == 'minute']
        points = [p for p in points if p is not None]
        differences = [Decimal(str(p['back'])) - Decimal(str(p['charger'])) for p in points
                       if p['back'] is not None and p['charger'] is not None]
        assert len(points) == int(row['n']) and len(differences) == int(row['two_limits_readable'])
        assert sum(d == 0 for d in differences) == int(row['equal'])
        assert sum(abs(d) >= 1 for d in differences) == int(row['abs_ge_1'])
        checks += 1
    by_cell = defaultdict(lambda: defaultdict(list))
    for r in events:
        if r['source'] == 'charger' and r['side'] in ('below', 'above'):
            by_cell[(r['trial'], *r['cell'])][r['side']].append(r)
    for row in read_table('support_cells.csv'):
        cell = row['trial'], int(row['cell_i_pre_left']), int(row['cell_drop_left'])
        sides = by_cell[cell]
        n = min(len({r['charger_id'] for r in sides[k]}) for k in ('below', 'above'))
        w = min(len({r['week'] for r in sides[k]}) for k in ('below', 'above'))
        status = 'primary' if n >= 10 and w >= 3 else 'exploratory_only' if n >= 5 and w >= 3 else 'unsupported'
        assert row['status'] == status and len(sides[row['side']]) == int(row['n'])
        checks += 1
    for row in read_table('table2_observed_current.csv'):
        if row['side'] != 'below_minus_above':
            continue
        threshold = 10 if row['scope'] == 'primary' else 5
        diffs = []
        support = 0
        for cell, sides in by_cell.items():
            if cell[0] != row['trial'] or not all(len({r['charger_id'] for r in sides[k]}) >= threshold and
                                                 len({r['week'] for r in sides[k]}) >= 3 for k in ('below', 'above')):
                continue
            support += 1
            groups = [[Decimal(str(r['delta'])) for r in sides[k] if r['delta'] is not None]
                      for k in ('below', 'above')]
            if all(groups):
                diffs.append(sum(groups[0]) / len(groups[0]) - sum(groups[1]) / len(groups[1]))
        assert support == int(row['support_cells']) and len(diffs) == int(row['cells_with_observed_both_sides'])
        if diffs:
            assert math.isclose(float(row['delta_mean_below_minus_above']), sum(diffs) / len(diffs), abs_tol=1e-9)
        else:
            assert not row['delta_mean_below_minus_above']
        checks += 1
    return checks


def verify_original_sample(events):
    wanted = {}
    for stage in ('1', '2', 'NULL'):
        for role in sorted(ROLES):
            for source in ('back', 'charger'):
                matches = [r for r in events if r['trial'] == stage and r['role'] == role and r['source'] == source]
                subset = sorted(matches, key=lambda r: hashlib.sha256(repr(identity(r)).encode()).digest())[:2]
                for event in subset:
                    for window in (event, event.get('sham', {}).get('point')):
                        if window is not None:
                            for point in [*window['pre'], window['index'], window['next']]:
                                if point is not None:
                                    wanted[point['line']] = (transaction(event), point)
    seen = 0
    with ZipFile(ADMISSION / 'original/crowdcharge_meter.zip') as archive, archive.open('CrowdChargeMeterValues.csv') as raw:
        for line, data in enumerate(raw, 1):
            if line in wanted:
                (charger, tx, role), point = wanted[line]
                cols = data.decode('ascii').rstrip('\r\n').split(',')
                assert role in ROLES and (charger, tx) == (cols[0], cols[7])
                assert point['utc'] == cols[2].replace(' ', 'T')
                for field, index in (('current', 3), ('charger', 4), ('back', 5)):
                    if point[field] is not None:
                        assert Decimal(cols[index]) == Decimal(str(point[field]))
                seen += 1
            if line == max(wanted):
                break
    assert seen == len(wanted)
    return seen


if __name__ == '__main__':
    receipt = json.loads((BASE / 'scan_receipt.json').read_text(encoding='utf-8'))
    freeze = json.loads((BASE / 'freeze.json').read_text(encoding='utf-8'))
    for name, digest in freeze['files'].items():
        assert hash_file(BASE.parent / name) == digest
    for name, digest in receipt['output_hashes'].items():
        assert hash_file(BASE / name) == digest
    assert receipt['confirmation_values_parsed'] == 0
    txs, candidates, events = (read_jsonl(name) for name in ('transactions.jsonl.gz', 'candidates.jsonl.gz', 'events.jsonl.gz'))
    result = {'status': 'passed', 'development_transactions': len(txs), 'all_candidate_gates_replayed': len(candidates),
              'selected_indices_and_post_axes_reconciled': len(events), 'sham_windows_recomputed': verify_ledgers(txs, candidates, events),
              'table_rows_independently_checked': verify_tables(events), 'raw_development_points_replayed': verify_original_sample(events),
              'confirmation_response_values_parsed': 0, 'model_fits': 0, 'confirmation_scores': 0}
    with (BASE / 'verification.json').open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(result)
