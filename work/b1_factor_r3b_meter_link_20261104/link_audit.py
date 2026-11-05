"""Make a slot-by-slot meter linkage ledger from the frozen London windows."""
import csv
import json
import re
import sys
import zlib
from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from pathlib import Path
from zoneinfo import ZoneInfo

from openpyxl import load_workbook

sys.dont_write_bytecode = True
from range_fetch import csv_reader, field_map, is_dynamic


BASE = Path(__file__).resolve().parent
PARENT = BASE.parent / 'b1_factor_r3a_price_admission_20261104'
LONDON = ZoneInfo('Europe/London')
UTC = timezone.utc
STEP = timedelta(minutes=30)
DAY = timedelta(days=1)
STATES = ('numeric_nonzero', 'raw_zero', 'empty_field', 'literal_null', 'invalid_field',
          'duplicate_same', 'duplicate_conflict', 'no_row_in_member_interior', 'outside_acquired_span')


def load_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def write_csv(output, name, rows, names=None):
    with (output / name).open('x', encoding='utf-8-sig', newline='') as stream:
        out = csv.DictWriter(stream, fieldnames=names or list(rows[0]))
        out.writeheader()
        out.writerows(rows)


def windows(protocol):
    spec = protocol['windows']
    wanted = {day: arm for arm in ('High', 'Low', 'Normal') for day in spec[arm]}
    refs = {r['trial_day']: r for r in read_csv(PARENT / 'candidate_windows.csv')
            if r['cell'] == spec['cell'] and r['trial_day'] in wanted}
    result = []
    for day, arm in sorted(wanted.items()):
        record = refs[day]
        assert record['arm_raw'] == arm
        first = datetime.fromisoformat(record['start_local'])
        last = datetime.fromisoformat(record['end_local_exclusive'])
        assert first.time().isoformat(timespec='minutes') == spec['local_start']
        assert last.time().isoformat(timespec='minutes') == spec['local_end_exclusive']
        result.append(describe(day, arm, 'event_window', first, last, int(record['raw_first_row'])))
        result.append(trial(day, arm, 'trial_day'))
    result.extend(trial(day, 'clock_only', 'trial_day') for day in spec['clock_only_trial_days'])
    return result


def trial(day, arm, scope):
    first = datetime.combine(date.fromisoformat(day), time(5))
    return describe(day, arm, scope, first, first + DAY, None)


def describe(day, arm, scope, first, last, first_row):
    start_gmt = first.replace(tzinfo=LONDON).astimezone(UTC)
    end_gmt = last.replace(tzinfo=LONDON).astimezone(UTC)
    n = int((end_gmt - start_gmt) / STEP)
    return {'trial_day': day, 'arm': arm, 'scope': scope, 'start_local': first.isoformat(),
            'end_local_exclusive': last.isoformat(), 'start_gmt': start_gmt.isoformat(),
            'first_gmt_end_key': (start_gmt + STEP).isoformat(), 'last_gmt_end_key': end_gmt.isoformat(),
            'slots_per_household': n, 'first_tariff_source_row': first_row}


def select_source(access):
    if access['status'] != 'acquired':
        return [], {}, {}
    if access['selected_source'] == 'archived_sample':
        sample = access['archived_sample']
        members = [(sample['file'], (BASE / 'original' / sample['file']).read_bytes(), sample['household_metadata'])]
    elif access['selected_source'] == 'official_zip_partial_member':
        source = access['prefix_member']
        probe = (BASE / 'original' / source['probe_file']).read_bytes()
        from targeted_prefix import compressed_part, expanded
        packed = compressed_part(probe)
        if source['extension_file']:
            packed += (BASE / 'original' / source['extension_file']).read_bytes()
        data, tail, eof = expanded(packed)
        assert sha256(data).hexdigest() == source['expanded_complete_sha256']
        assert tail == source['truncated_last_line_bytes'] and eof == source['deflate_eof']
        members = [(source['name'], data, source['household_metadata'])]
    else:
        members = [(m['name'], zlib.decompress((BASE / 'original' / m['file']).read_bytes(), -15), m['household_metadata'])
                   for m in access['members']]
    combined = {}
    for _, _, info in members:
        for hid, row in info.items():
            if hid not in combined:
                combined[hid] = {'labels': set(row['labels']), 'first': row['first'], 'last': row['last']}
            else:
                found = combined[hid]
                found['labels'].update(row['labels'])
                found['first'] = min(found['first'], row['first'])
                found['last'] = max(found['last'], row['last'])
    full = [h for h, row in sorted(combined.items()) if is_dynamic(row['labels']) and
            row['first'] <= '2013-02-11 00:00:00' and row['last'] >= '2013-11-22 06:00:00']
    partial = [h for h, row in sorted(combined.items()) if is_dynamic(row['labels'])]
    picked = (full or partial)[:2]
    return members, {h: combined[h] for h in picked}, {'full_range_dToU_available': len(full), 'dynamic_houses_in_members': len(partial)}


def source_records(members, selected, expected_keys):
    index = defaultdict(list)
    if not selected:
        return index
    for name, data, _ in members:
        rows = csv_reader(data)
        fields = field_map(rows.fieldnames)
        for r in rows:
            hid = r[fields['id']]
            if hid not in selected:
                continue
            native = r[fields['time']]
            short = native[:19]
            if short not in expected_keys:
                continue
            if not re.fullmatch(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:\.0+)?', native):
                raise ValueError(f'Unexpected sub-second clock in selected window: {name} row {rows.line_num}')
            index[hid, short].append({'member': name, 'row': rows.line_num,
                                      'label': r[fields['group']], 'timestamp': native,
                                      'token': r[fields['kwh']]})
    return index


def state(records, short, meta):
    if not records:
        return 'no_row_in_member_interior' if meta['first'] <= short <= meta['last'] else 'outside_acquired_span'
    if len(records) > 1:
        values = {(x['label'], x['token']) for x in records}
        return 'duplicate_same' if len(values) == 1 else 'duplicate_conflict'
    token = records[0]['token'].strip()
    if not token:
        return 'empty_field'
    if token.casefold() == 'null':
        return 'literal_null'
    try:
        value = Decimal(token)
    except InvalidOperation:
        return 'invalid_field'
    if not value.is_finite():
        return 'invalid_field'
    return 'raw_zero' if value == 0 else 'numeric_nonzero'


def stamp(gmt):
    return gmt.replace(tzinfo=None).isoformat(sep=' ')


def keys(window):
    first = datetime.fromisoformat(window['first_gmt_end_key'])
    return [first + STEP * i for i in range(window['slots_per_household'])]


def tariff_rows():
    book = load_workbook(PARENT / 'original/Tariffs.xlsx', read_only=True, data_only=True)
    data = {key: (number, tariff) for number, (key, tariff) in enumerate(book['Sheet1'].values, 1) if number > 1}
    book.close()
    return data


def ledger(plan, selected, index, tariffs):
    for window in plan:
        for hid, meta in selected.items():
            for end in keys(window):
                short = stamp(end)
                records = index[hid, short]
                local_start = (end - STEP).astimezone(LONDON)
                tariff = (None, '') if window['arm'] == 'clock_only' else tariffs[local_start.replace(tzinfo=None)]
                if window['scope'] == 'event_window':
                    assert tariff[1] == window['arm']
                yield {'trial_day': window['trial_day'], 'arm': window['arm'], 'scope': window['scope'],
                       'household': hid, 'meter_group': next(iter(meta['labels'])), 'expected_gmt_end': end.isoformat(),
                       'derived_local_start': local_start.isoformat(),
                       'derived_local_end': end.astimezone(LONDON).isoformat(), 'status': state(records, short, meta),
                       'tariff_workbook_row': tariff[0], 'tariff_raw_label': tariff[1],
                       'raw_rows_found': len(records), 'raw_source_records': json.dumps(records, ensure_ascii=False)}


def aggregate(plan, lines, selected, source_acquired):
    for scope, arm in sorted({(w['scope'], w['arm']) for w in plan}):
        targets = [w for w in plan if (w['scope'], w['arm']) == (scope, arm)]
        have = [r for r in lines if (r['scope'], r['arm']) == (scope, arm)]
        count = Counter(row['status'] for row in have)
        yield {'scope': scope, 'arm': arm, 'planned_distinct_dates': len(targets),
               'planned_slots_per_household': sum(w['slots_per_household'] for w in targets),
               'selected_dToU_households': len(selected), 'selected_household_slots': len(have),
               'slots_with_raw_meter_row': sum(r['raw_rows_found'] > 0 for r in have),
               'raw_meter_rows': sum(r['raw_rows_found'] for r in have),
               **{k: count[k] if selected else '' for k in STATES},
               'admission_status': ('selected_sample_only' if selected else 'acquired_members_no_dynamic_denominator'
                                    if source_acquired else 'source_unavailable_no_meter_denominator')}


if __name__ == '__main__':
    protocol = load_json(BASE / 'protocol.json')
    for n, digest in protocol['upstream_sha256'].items():
        assert sha256((PARENT / n).read_bytes()).hexdigest() == digest
    access_file = sys.argv[1] if len(sys.argv) > 1 else 'source_access.json'
    output = BASE / sys.argv[2] if len(sys.argv) > 2 else BASE
    output.mkdir(exist_ok=True)
    access = load_json(BASE / access_file)
    assert access['protocol_sha256'] == sha256((BASE / 'protocol.json').read_bytes()).hexdigest()
    plan = windows(protocol)
    members, selected, scope = select_source(access)
    index = source_records(members, selected, {stamp(t) for w in plan for t in keys(w)})
    linked = list(ledger(plan, selected, index, tariff_rows() if selected else {}))
    write_csv(output, 'planned_windows.csv', plan)
    if linked:
        write_csv(output, 'linked_intervals.csv', linked)
    write_csv(output, 'denominators.csv', list(aggregate(plan, linked, selected, bool(members))))
    with (output / 'link_receipt.json').open('x', encoding='utf-8') as stream:
        json.dump({'access_receipt': access_file, 'selected': {k: {**v, 'labels': sorted(v['labels'])} for k, v in selected.items()},
                   'acquired_source_scope': scope, 'windows': len(plan), 'linked_rows': len(linked),
                   'confirmations_read': 0, 'models_fitted': 0, 'effect_estimates': 0}, stream, indent=2)
        stream.write('\n')
