"""Audit CrowdCharge keys and time before opening a bounded development slice."""
import argparse
import hashlib
import json
from array import array
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from zipfile import ZipFile

import openpyxl


BASE = Path(__file__).resolve().parent
ORIGINAL = BASE / 'original'
METER = 'crowdcharge_meter.zip'
TRANSACTIONS = 'crowdcharge_transactions.xlsx'
GROUPS = 'group_definition.xlsx'
EXPECTED_SIZES = {METER: 188915502, TRANSACTIONS: 11141809,
                  GROUPS: 239602, 'meter_dictionary.pdf': 431974}
METER_MEMBER = 'CrowdChargeMeterValues.csv'
FIRST_ROW_EXPOSURE = (b'0035000117', b'100012')
DAY_MS = 86_400_000
WEEK = timedelta(days=7)
ROLE_NAMES = ('train', 'development_validation', 'confirmation')


def write_json(name, obj):
    with (BASE / name).open('x', encoding='utf-8') as stream:
        json.dump(obj, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def file_hash(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def stable_hash(salt, key):
    return hashlib.sha256(salt + key).digest()


def original_files():
    facts = {}
    for name, size in EXPECTED_SIZES.items():
        path = ORIGINAL / name
        assert path.stat().st_size == size, name
        facts[name] = {'bytes': size, 'sha256': file_hash(path)}
    for name in (TRANSACTIONS, GROUPS):
        with ZipFile(ORIGINAL / name) as book:
            assert book.testzip() is None, name
    with (ORIGINAL / 'meter_dictionary.pdf').open('rb') as stream:
        assert stream.read(5) == b'%PDF-'
    return facts


def charger_key(raw):
    # The meter stores a zero-padded string and the workbook stores a number.
    value = str(raw)
    return (value.zfill(10) if value.isdecimal() else value).encode('ascii')


def millis(value):
    return (value.toordinal() * DAY_MS + value.hour * 3_600_000
            + value.minute * 60_000 + value.second * 1000 + value.microsecond // 1000)


def transaction_metadata():
    book = openpyxl.load_workbook(ORIGINAL / TRANSACTIONS, read_only=True, data_only=True)
    rows = book['Transaction Data'].values
    header = next(rows)
    columns = ('ChargerID', 'TransactionID', 'ParticipantID', 'StartTime', 'StopTime', 'GroupID', 'Trial')
    positions = [header.index(name) for name in columns]
    registry = {}
    duplicates = set()
    counts = Counter()
    people_by_charger = defaultdict(set)
    chargers_by_person = defaultdict(set)
    for row in rows:
        counts['workbook_rows'] += 1
        charger, transaction, person, start, stop, group, trial = (row[pos] for pos in positions)
        if None in (charger, transaction, person, start, stop):
            counts['missing_key_or_time'] += 1
            continue
        key = (charger_key(charger), str(int(transaction)).encode('ascii'))
        if key in registry:
            duplicates.add(key)
            counts['repeated_key_rows'] += 1
            continue
        if not isinstance(start, datetime) or not isinstance(stop, datetime) or stop < start:
            counts['invalid_time'] += 1
            continue
        registry[key] = (start, stop, str(person), str(group), str(trial))
        people_by_charger[key[0]].add(str(person))
        chargers_by_person[str(person)].add(key[0])
    book.close()
    for key in duplicates:
        registry.pop(key)
    counts['unique_valid_transactions'] = len(registry)
    counts['duplicate_keys_excluded'] = len(duplicates)
    counts['multi_participant_chargers'] = sum(len(x) > 1 for x in people_by_charger.values())
    counts['multi_charger_participants'] = sum(len(x) > 1 for x in chargers_by_person.values())
    ambiguous = {c for c, people in people_by_charger.items() if len(people) > 1}
    for chargers in chargers_by_person.values():
        if len(chargers) > 1:
            ambiguous.update(chargers)
    counts['charger_identity_excluded'] = len(ambiguous)
    return registry, ambiguous, counts, header


def group_metadata():
    book = openpyxl.load_workbook(ORIGINAL / GROUPS, read_only=True, data_only=True)
    rows = book['CrowdCharge'].values
    header = next(rows)
    assert header[:4] == ('ChargerID', 'GroupID', 'StartDate', 'EndDate')
    periods = defaultdict(list)
    group_ids = set()
    counts = Counter()
    for row in rows:
        counts['workbook_rows'] += 1
        charger, group, start, stop = row[:4]
        if charger is None or group is None or not isinstance(start, datetime) or not isinstance(stop, datetime) or stop < start:
            counts['unusable_rows'] += 1
            continue
        periods[charger_key(charger)].append((start, stop))
        group_ids.add(str(group))
    book.close()
    for times in periods.values():
        high = datetime.min
        for start, stop in sorted(times):
            counts['periods_overlapping_previous_or_earlier'] += start <= high
            high = max(high, stop)
    counts['chargers'] = len(periods)
    counts['groups'] = len(group_ids)
    return counts, header, group_ids


def date_roles(registry):
    start = min(row[0] for row in registry.values()).date()
    stop = max(row[1] for row in registry.values()).date()
    monday = start + timedelta(days=(7 - start.weekday()) % 7)
    # Keep only full calendar weeks contained within the raw date extent.
    weeks = [monday + index * WEEK for index in range((stop - monday).days // 7)]
    train_end = len(weeks) // 2
    confirm_start = train_end + len(weeks) // 4
    return {'train': (weeks[0], weeks[train_end]),
            'development_validation': (weeks[train_end + 1], weeks[confirm_start]),
            'confirmation': (weeks[confirm_start + 1], weeks[-1] + WEEK)}


def assign_roles(registry, ambiguous, periods):
    roles = {}
    reasons = Counter()
    for key, (start, stop, *_rest) in registry.items():
        if key == FIRST_ROW_EXPOSURE:
            reasons['headerless_first_row_exposure'] += 1
            continue
        if key[0] in ambiguous:
            reasons['ambiguous_charger_participant'] += 1
            continue
        bucket = int.from_bytes(stable_hash(b'b1-r1-20261104|', key[0])[:8], 'big') % 5
        role = ROLE_NAMES[2 - bucket] if bucket < 2 else 'train'
        left, right = periods[role]
        if left <= start.date() <= stop.date() < right:
            roles[key] = role
        else:
            reasons['outside_charger_date_intersection'] += 1
    return roles, reasons


def meter_metadata(registry, roles):
    times = {}
    bounds = {key: (millis(registry[key][0]), millis(registry[key][1])) for key in roles}
    groups = defaultdict(Counter)
    counts = Counter()
    by_role = defaultdict(Counter)
    with ZipFile(ORIGINAL / METER) as archive:
        assert archive.namelist() == [METER_MEMBER]
        member = archive.getinfo(METER_MEMBER)
        archive_meta = {'member': member.filename, 'bytes': member.file_size,
                        'compressed_bytes': member.compress_size, 'crc32': f'{member.CRC:08x}'}
        with archive.open(member) as stream:
            for raw in stream:
                counts['rows'] += 1
                cols = raw.rstrip(b'\r\n').split(b',')
                if len(cols) != 9:
                    counts['unexpected_column_count'] += 1
                    continue
                # Whitelist: charger, group, UTC timestamp, transaction. Never inspect other tokens here.
                key = (cols[0], cols[7])
                role = roles.get(key)
                if role is None:
                    counts['outside_roles' if key in registry else 'unmatched_meter_key'] += 1
                    continue
                by_role[role]['matched_meter_rows'] += 1
                try:
                    point = millis(datetime.fromisoformat(cols[2].decode('ascii')))
                except (ValueError, UnicodeError):
                    by_role[role]['invalid_utc'] += 1
                    continue
                start, stop = bounds[key]
                if not start <= point <= stop:
                    by_role[role]['outside_workbook_boundary'] += 1
                    continue
                if key not in times:
                    times[key] = array('Q')
                if times[key] and point < times[key][-1]:
                    by_role[role]['out_of_order_in_transaction'] += 1
                times[key].append(point)
                groups[role][cols[1].decode('ascii')] += 1
    # EOF on ZipExtFile checks the CRC of the complete compressed member.
    return times, counts, by_role, groups, archive_meta


def coverage(registry, roles, times, by_role):
    summary = {}
    eligible = defaultdict(list)
    for role in ROLE_NAMES:
        counts = by_role[role]
        chargers = set()
        people = set()
        weeks = set()
        potential_weeks = set()
        potential_chargers = set()
        trials = defaultdict(Counter)
        intervals = Counter()
        for key, assigned in roles.items():
            if assigned != role:
                continue
            start, stop, person, _group, trial = registry[key]
            week = start.date() - timedelta(days=start.weekday())
            chargers.add(key[0])
            people.add(person)
            weeks.add(week.isoformat())
            trials[trial]['transactions'] += 1
            counts['transactions'] += 1
            raw_points = times.get(key, ())
            if not raw_points:
                counts['transactions_without_in_bounds_meter_row'] += 1
                continue
            counts['transactions_with_in_bounds_meter_row'] += 1
            points = sorted(raw_points)
            duplicate = any(a == b for a, b in zip(points, points[1:]))
            run = 1
            max_run = 1
            for left, right in zip(points, points[1:]):
                gap = right - left
                intervals[str(gap) if gap in (0, 60_000, 1_800_000) else 'other'] += 1
                run = run + 1 if 45_000 <= gap <= 75_000 else 1
                max_run = max(max_run, run)
            if duplicate:
                counts['transactions_with_duplicate_timestamp'] += 1
                continue
            if max_run >= 6:
                counts['transactions_with_six_consecutive_timestamps'] += 1
                trials[trial]['six_consecutive_timestamps'] += 1
                potential_chargers.add(key[0])
                potential_weeks.add(week.isoformat())
                eligible[role, trial].append(key)
        summary[role] = {'counts': dict(counts), 'chargers': len(chargers), 'participants': len(people),
                         'transaction_start_weeks': sorted(weeks), 'gap_ms_counts': dict(intervals),
                         'trial_counts': trials, 'six_point_chargers': len(potential_chargers),
                         'six_point_start_weeks': sorted(potential_weeks)}
    return summary, eligible


def metadata():
    facts = original_files()
    registry, ambiguous, transactions, transaction_header = transaction_metadata()
    group_counts, group_header, group_ids = group_metadata()
    periods = date_roles(registry)
    roles, exclusions = assign_roles(registry, ambiguous, periods)
    for offset, left in enumerate(ROLE_NAMES):
        for right in ROLE_NAMES[offset + 1:]:
            for key_field in (lambda key: key[0], lambda key: registry[key][2]):
                assert {key_field(k) for k in roles if roles[k] == left}.isdisjoint(
                    key_field(k) for k in roles if roles[k] == right)
    times, counts, by_role, groups, archive = meter_metadata(registry, roles)
    summary, eligible = coverage(registry, roles, times, by_role)
    chosen = {}
    for (role, trial), keys in sorted(eligible.items()):
        if role == 'confirmation':
            continue
        ordered = sorted(keys, key=lambda key: stable_hash(b'b1-r1-dev-inspection-v1|', b'|'.join(key)))
        for key in ordered[:3]:
            start, stop, _person, group, stage = registry[key]
            chosen['|'.join(x.decode('ascii') for x in key)] = {
                'role': role, 'start': start.isoformat(), 'stop': stop.isoformat(),
                'workbook_group': group, 'trial': stage}
    write_json('metadata.json', {'original_files': facts, 'archive': archive, 'meter_rows': counts,
              'workbook_header': transaction_header, 'workbook_counts': transactions,
              'group_header': group_header, 'group_workbook_counts': group_counts,
              'role_dates_left_inclusive_right_exclusive': {k: [x.isoformat() for x in v] for k, v in periods.items()},
              'role_exclusions': exclusions, 'roles': summary,
              'groups_in_meter': {k: len(set(v) & group_ids) for k, v in groups.items()},
              'group_ids_shared_by_dev_and_confirmation': sorted(
                  (set(groups['train']) | set(groups['development_validation'])) & set(groups['confirmation']) - {'NULL', ''}),
              'whitelist': ['ChargerID', 'GroupID', 'Timestamp', 'TransactionID'],
              'outcomes_opened_by_metadata_script': False})
    write_json('development_registry.json', {'metadata_sha256': file_hash(BASE / 'metadata.json'),
               'selector': 'At most 3 per development role and workbook trial by fixed salted hash; require six consecutive original in-bounds timestamps and no duplicate timestamps.',
               'transactions': chosen})


def parse_decimal(raw):
    try:
        value = Decimal(raw.decode('ascii'))
    except (InvalidOperation, UnicodeError):
        return None
    return value if value.is_finite() else None


def development():
    metadata_doc = json.loads((BASE / 'metadata.json').read_text(encoding='utf-8'))
    frozen = json.loads((BASE / 'development_registry.json').read_text(encoding='utf-8'))
    assert frozen['metadata_sha256'] == file_hash(BASE / 'metadata.json')
    assert metadata_doc['original_files'][METER]['sha256'] == file_hash(ORIGINAL / METER)
    keys = {tuple(part.encode('ascii') for part in key.split('|')): value for key, value in frozen['transactions'].items()}
    assert all(row['role'] in ROLE_NAMES[:2] for row in keys.values())
    assert FIRST_ROW_EXPOSURE not in keys
    opened = defaultdict(list)
    with ZipFile(ORIGINAL / METER) as archive, archive.open(METER_MEMBER) as stream:
        for number, raw in enumerate(stream, 1):
            cols = raw.rstrip(b'\r\n').split(b',')
            if len(cols) != 9:
                continue
            key = (cols[0], cols[7])
            row = keys.get(key)
            if row is None:
                continue
            when = datetime.fromisoformat(cols[2].decode('ascii'))
            if datetime.fromisoformat(row['start']) <= when <= datetime.fromisoformat(row['stop']):
                opened[key].append((number, cols))
    assert set(opened) == set(keys)
    counters = defaultdict(Counter)
    examples = {}
    for key, rows in opened.items():
        role = keys[key]['role']
        counts = counters[role]
        rows.sort(key=lambda row: row[1][2])
        counts['transactions'] += 1
        counts['rows'] += len(rows)
        for position, (number, row) in enumerate(rows):
            current, charger_limit, back_limit = (parse_decimal(row[i]) for i in (3, 4, 5))
            counts['status_' + row[6].decode('ascii')] += 1
            if current is None:
                counts['current_missing'] += 1
            else:
                counts['current_decimals_' + str(-current.normalize().as_tuple().exponent)] += 1
                counts['current_zero'] += current == 0
            if charger_limit is None or back_limit is None:
                counts['limit_missing'] += 1
            else:
                mismatch = charger_limit != back_limit
                counts['same_record_limit_mismatch'] += mismatch
                counts['same_record_difference_at_least_1A'] += abs(charger_limit - back_limit) >= 1
                counts['current_exceeds_local_limit'] += current is not None and current > charger_limit
                if mismatch and 'mismatch' not in examples:
                    examples['mismatch'] = example(key, rows[max(0, position - 1):position + 2], role)
            if 'three_adjacent_rows' not in examples and position == 2:
                examples['three_adjacent_rows'] = example(key, rows[:3], role)
    write_json('development_fields.json', {'metadata_sha256': frozen['metadata_sha256'],
               'development_registry_sha256': file_hash(BASE / 'development_registry.json'),
               'scope': 'Preselected development-only transactions. Descriptive field QA, no fit, no effect score.',
               'roles': counters, 'examples': examples})


def example(key, rows, role):
    return {'transaction': '|'.join(part.decode('ascii') for part in key), 'role': role,
            'rows': [{'source_line': number, 'utc': row[2].decode('ascii'), 'current_A': row[3].decode('ascii'),
                      'charger_limit_A': row[4].decode('ascii'), 'backend_limit_A': row[5].decode('ascii'),
                      'status': row[6].decode('ascii'), 'local_timestamp': row[8].decode('ascii')}
                     for number, row in rows]}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('metadata', 'development'))
    mode = parser.parse_args().mode
    (metadata if mode == 'metadata' else development)()
