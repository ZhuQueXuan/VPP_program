"""Read CrowdCharge development keys only and produce frozen observation ledgers."""
import argparse
import gzip
import importlib.util
import json
import math
import sys
from array import array
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile


BASE = Path(__file__).resolve().parent
PARENT = BASE.parent / 'b1_factor_round2_admission_20261104'
SOURCES = {'back': 2, 'charger': 1}
EPS = 1e-9
GATES = ('new_below_6', 'pre_time_unavailable', 'pre_limit_unstable_or_missing',
         'pre_status_not_charging', 'pre_current_low_or_missing', 'pre_current_unstable')
DEV = ('train', 'development_validation')


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path, obj):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(obj, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


def load_admission():
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location('r1a', PARENT / 'admit.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def frozen_development(admit):
    freeze = read_json(PARENT / 'role_freeze.json')
    meta = read_json(PARENT / 'metadata.json')
    for name, key in (('admit.py', 'audit_code_sha256'), ('metadata.json', 'metadata_sha256'),
                      ('development_registry.json', 'development_registry_sha256')):
        assert admit.file_hash(PARENT / name) == freeze[key], name
    for name, facts in meta['original_files'].items():
        assert admit.file_hash(admit.ORIGINAL / name) == facts['sha256'], name
    registry, ambiguous, _, _ = admit.transaction_metadata()
    all_roles, _ = admit.assign_roles(registry, ambiguous, admit.date_roles(registry))
    for role, facts in freeze['role_keys'].items():
        keys = sorted(key for key, assigned in all_roles.items() if assigned == role)
        assert len(keys) == facts['count']
        assert sha256(b'\n'.join(b'|'.join(key) for key in keys)).hexdigest() == facts['ordered_key_sha256']
    allowed = {key: (role, registry[key]) for key, role in all_roles.items() if role in DEV}
    assert admit.FIRST_ROW_EXPOSURE not in allowed
    assert len(allowed) == 15698
    return allowed, meta


def numeric(raw):
    try:
        value = float(raw)
    except ValueError:
        return math.nan
    return value if math.isfinite(value) and value >= 0 else math.nan


def is_minute(gap_ms):
    return 45000 <= gap_ms <= 75000


class Points:
    def __init__(self):
        self.time = array('q')
        self.line = array('I')
        self.values = tuple(array('d') for _ in range(3))
        self.status = array('B')
        self.group = array('H')

    def append(self, point_time, line, raw, group):
        self.time.append(point_time)
        self.line.append(line)
        for target, column in zip(self.values, (3, 4, 5)):
            target.append(numeric(raw[column]))
        self.status.append(1 if raw[6] == b'1' else 2 if raw[6] == b'2' else 0)
        self.group.append(group)

    def point(self, index, group_labels):
        return {'line': self.line[index], 'utc': utc_text(self.time[index]),
                'current': nullable(self.values[0][index]), 'charger': nullable(self.values[1][index]),
                'back': nullable(self.values[2][index]), 'status': self.status[index],
                'group': group_labels[self.group[index]]}


def utc_text(value):
    day, millis = divmod(value, 86400000)
    return (datetime.fromordinal(day) + timedelta(milliseconds=millis)).isoformat(timespec='milliseconds')


def nullable(value):
    return value if math.isfinite(value) else None


def read_points(admit, allowed, meta):
    bounds = {key: (admit.millis(row[1][0]), admit.millis(row[1][1])) for key, row in allowed.items()}
    points = {}
    group_ids = {'NULL': 0}
    counts = Counter()
    role_counts = Counter()
    with ZipFile(admit.ORIGINAL / admit.METER) as archive, archive.open(admit.METER_MEMBER) as stream:
        for line, record in enumerate(stream, 1):
            counts['source_rows'] += 1
            raw = record.rstrip(b'\r\n').split(b',')
            if len(raw) != 9:
                counts['unexpected_width'] += 1
                continue
            key = raw[0], raw[7]
            if key not in bounds:
                counts['unopened_other_role_or_unmatched'] += 1
                continue
            point = admit.millis(datetime.fromisoformat(raw[2].decode('ascii')))
            start, stop = bounds[key]
            if not start <= point <= stop:
                counts['out_of_boundary'] += 1
                continue
            label = raw[1].decode('ascii').strip() or 'NULL'
            group = group_ids.setdefault(label, len(group_ids))
            if key not in points:
                points[key] = Points()
            points[key].append(point, line, raw, group)
            role_counts[allowed[key][0]] += 1
    assert counts['source_rows'] == meta['meter_rows']['rows']
    for role in DEV:
        expected = meta['roles'][role]['counts']
        assert role_counts[role] == expected['matched_meter_rows'] - expected.get('outside_workbook_boundary', 0)
    counts['parsed_development_rows_by_role'] = dict(role_counts)
    return points, list(group_ids), counts


def preconditions(points, index, field):
    times = points.time
    if index < 4 or any(not is_minute(times[i] - times[i - 1]) for i in range(index - 3, index + 1)):
        return GATES[1], None
    limits = points.values[field][index - 4:index]
    if any(not math.isfinite(v) for v in limits) or max(limits) - min(limits) > .25 + EPS:
        return GATES[2], None
    if any(s != 2 for s in points.status[index - 4:index]):
        return GATES[3], None
    amps = points.values[0][index - 4:index]
    early = (amps[0] + amps[1]) / 2
    ref = (amps[2] + amps[3]) / 2
    if any(not math.isfinite(v) for v in amps) or min(early, ref) < 3 - EPS:
        return GATES[4], None
    if max(abs(amps[0] - amps[1]), abs(amps[2] - amps[3])) > 1 + EPS or abs(ref - early) > .5 + EPS:
        return GATES[5], (early, ref)
    return 'qualified', (early, ref)


def raw_drop(old, new):
    return old - new >= 2 - EPS


def later_stop(points, index):
    for j in range(index + 1, len(points.time)):
        if points.time[j] - points.time[index] > 1_800_000:
            break
        if points.status[j] == 1:
            return (points.time[j] - points.time[index]) / 1000
    return None


def describe_index(points, index, stage, group_labels, state, stop_time):
    now = points.point(index, group_labels)
    previous = points.point(index - 1, group_labels)
    later = points.point(index + 1, group_labels) if index + 1 < len(points.time) else None
    stop_gap = (stop_time - points.time[index]) / 1000
    gap = (points.time[index + 1] - points.time[index]) / 1000 if later else None
    if gap is None:
        timing = 'no_later_trade_ends_by_75s' if stop_gap <= 75 else 'no_later_trade_extends_past_75s'
    elif gap < 45:
        timing = 'earlier_than_45s'
    elif gap > 75:
        timing = 'later_than_75s'
    else:
        timing = 'minute'
    early, ref = state
    observed = later['current'] if timing == 'minute' else None
    utc = datetime.fromisoformat(now['utc']).date()
    return {'trial': stage, 'week': (utc - timedelta(days=utc.weekday())).isoformat(), 'group': now['group'],
            'pre': [points.point(i, group_labels) for i in range(index - 4, index)], 'index': now,
            'previous': previous, 'next': later, 'next_timing': timing, 'next_gap_s': gap,
            'stop_gap_s': stop_gap, 'first_visible_status1_within_30min_s': later_stop(points, index),
            'i_pre': early, 'i_ref': ref, 'y_abs': observed,
            'delta': None if observed is None else round(ref - observed, 9)}


def placebo(points, index, early, stage, group_labels, stop_time):
    reasons = Counter()
    limits = points.values[1]
    eligible_before = False
    for i in range(index - 1, 3, -1):
        if points.time[index] - points.time[i] < 600000:
            continue
        eligible_before = True
        if not is_minute(points.time[i + 1] - points.time[i]):
            reasons['post_time'] += 1
            continue
        reason, state = preconditions(points, i, 1)
        if reason != 'qualified':
            reasons[reason] += 1
            continue
        six = limits[i - 4:i + 2]
        if any(not math.isfinite(v) for v in six) or max(six) - min(six) > .25 + EPS:
            reasons['six_limit_records_change_or_missing'] += 1
            continue
        if abs(state[0] - early) > 1 + EPS:
            reasons['i_pre_difference_over_1A'] += 1
            continue
        return {'status': 'matched', 'point': describe_index(points, i, stage, group_labels, state, stop_time),
                'rejected_nearer_points': dict(reasons)}
    return {'status': 'no_candidate_at_least_600s_earlier' if not eligible_before else 'no_eligible_sham',
            'point': None, 'rejected_nearer_points': dict(reasons)}


def analyze_one(points, key, role, record, group_labels, stop_time, candidate_stream):
    stage = record[4]
    charger, transaction = (x.decode('ascii') for x in key)
    tx = {'charger_id': charger, 'transaction_id': transaction, 'role': role, 'trial': stage,
          'start_utc': record[0].isoformat(), 'stop_utc': record[1].isoformat(), 'book_group': record[3],
          'in_bounds_rows': 0 if points is None else len(points.time), 'entrances': {}}
    selected = []
    if points is not None:
        times = points.time
        has_duplicate = any(a == b for a, b in zip(times, times[1:]))
        assert not any(a > b for a, b in zip(times, times[1:])), 'out of order within frozen transaction'
        tx['duplicate_time_quarantined'] = has_duplicate
    else:
        has_duplicate = False
        tx['duplicate_time_quarantined'] = False
    identity = {k: tx[k] for k in ('charger_id', 'transaction_id', 'role', 'trial')}
    for source, field in SOURCES.items():
        counts = Counter()
        if points is not None and not has_duplicate:
            limit = points.values[field]
            first = True
            for index, (old, new) in enumerate(zip(limit, limit[1:]), 1):
                if not (math.isfinite(old) and math.isfinite(new)):
                    continue
                counts['readable_adjacent_pairs'] += 1
                if not raw_drop(old, new):
                    continue
                counts['raw_drops'] += 1
                reason, state = (GATES[0], None) if new < 6 - EPS else preconditions(points, index, field)
                counts[reason] += 1
                now = points.point(index, group_labels)
                entry = {**identity, 'source': source, 'reason': reason, 'old': old, 'new': new,
                         'line': now['line'], 'utc': now['utc'], 'group': now['group'],
                         'pre_and_index': [points.point(i, group_labels) for i in range(max(0, index - 4), index + 1)],
                         'state': state, 'selected': reason == 'qualified' and first}
                if state is not None:
                    in_minute = index + 1 < len(times) and is_minute(times[index + 1] - times[index])
                    entry['stability_gate_minute_point'] = in_minute
                    entry['stability_gate_y_readable'] = in_minute and math.isfinite(points.values[0][index + 1])
                candidate_stream.write(json.dumps(entry, allow_nan=False) + '\n')
                if not entry['selected']:
                    continue
                first = False
                event = {**identity, 'source': source, 'old': old, 'new': new, 'drop': round(old - new, 9),
                         **describe_index(points, index, stage, group_labels, state, stop_time)}
                if source == 'charger':
                    gap = event['i_pre'] - new
                    event['side'] = 'below' if gap >= 1 - EPS else 'above' if gap <= -1 + EPS else 'boundary'
                    event['cell'] = [int(event['i_pre'] // 5) * 5, int(event['drop'] // 5) * 5]
                    event['sham'] = placebo(points, index, event['i_pre'], stage, group_labels, stop_time)
                selected.append(event)
        tx['entrances'][source] = dict(counts)
    return tx, selected


def freeze_inputs(admit):
    files = [BASE / n for n in ('protocol.json', 'study.py', 'summarize.py', 'meter_scope.md')]
    files += [PARENT / n for n in ('ROOT_REVIEW.md', 'role_freeze.json', 'metadata.json', 'admit.py')]
    write_json(BASE / 'freeze.json', {'before_development_response_access': True,
               'files': {str(p.relative_to(BASE.parent)).replace('\\', '/'): admit.file_hash(p) for p in files}})


def run(admit):
    for path, digest in read_json(BASE / 'freeze.json')['files'].items():
        assert admit.file_hash(BASE.parent / path) == digest, path
    allowed, meta = frozen_development(admit)
    points, group_labels, counts = read_points(admit, allowed, meta)
    outputs = ('transactions.jsonl.gz', 'candidates.jsonl.gz', 'events.jsonl.gz')
    for name in outputs:
        assert not (BASE / name).exists(), name
    with gzip.open(BASE / outputs[0], 'xt', encoding='utf-8') as txs, \
         gzip.open(BASE / outputs[1], 'xt', encoding='utf-8') as candidates, \
         gzip.open(BASE / outputs[2], 'xt', encoding='utf-8') as events:
        for key, (role, record) in sorted(allowed.items()):
            row, selected = analyze_one(points.get(key), key, role, record, group_labels,
                                        admit.millis(record[1]), candidates)
            txs.write(json.dumps(row, allow_nan=False) + '\n')
            for event in selected:
                events.write(json.dumps(event, allow_nan=False) + '\n')
    write_json(BASE / 'scan_receipt.json', {'counts': counts, 'allowed_development_keys': len(allowed),
               'confirmation_values_parsed': 0, 'role_hashes_verified': True,
               'output_hashes': {name: admit.file_hash(BASE / name) for name in outputs}})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('freeze', 'scan'))
    args = parser.parse_args()
    admit = load_admission()
    (freeze_inputs if args.mode == 'freeze' else run)(admit)
