"""Verify only the selected dynamic meter keys and price rows, without effect calculations."""
import csv
import io
import json
import struct
import zlib
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile


BASE = Path(__file__).resolve().parent
TARGET = BASE / 'targeted_link'
NS = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}


def from_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def from_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(blob):
    return sha256(blob).hexdigest()


def checked_prefix(initial, target, spec):
    ranges = initial['range_requests'] + target['range_requests']
    assert all(row['status'] == 206 for row in ranges)
    assert {row['etag'] for row in ranges} == {spec['exact_version']['etag']}
    assert {row['last_modified'] for row in ranges} == {spec['exact_version']['last_modified']}
    assert {int(row['content_range'].split('/')[-1]) for row in ranges} == {spec['exact_version']['archive_bytes']}
    received = sum(int(row['content_length']) for row in ranges)
    assert received <= spec['maximum_network_bytes_including_previous_ranges']
    assert len(target['probes']) == 1 and len(target['range_requests']) == 2
    member = target['prefix_member']
    probe = (BASE / 'original' / member['probe_file']).read_bytes()
    continuation = (BASE / 'original' / member['extension_file']).read_bytes()
    assert sha(probe) == target['range_requests'][0]['sha256']
    assert sha(continuation) == target['range_requests'][1]['sha256']
    assert target['range_requests'][0]['request_range'] == f'bytes={member["offset"]}-{member["offset"]+len(probe)-1}'
    assert target['range_requests'][1]['request_range'] == f'bytes={member["offset"]+len(probe)}-{member["offset"]+len(probe)+len(continuation)-1}'
    lengths = struct.unpack_from('<HH', probe, 26)
    inflater = zlib.decompressobj(wbits=-15)
    partial = inflater.decompress(probe[30+sum(lengths):] + continuation)
    final_line_end = partial.rindex(b'\n') + 1
    data = partial[:final_line_end]
    assert sha(data) == member['expanded_complete_sha256']
    assert len(partial) - len(data) == member['truncated_last_line_bytes']
    assert inflater.eof is False and member['full_crc_verified'] is False
    return received, data


def tariff_xml():
    file = BASE.parent / 'b1_factor_r3a_price_admission_20261104/original/Tariffs.xlsx'
    with ZipFile(file) as archive:
        labels = [x.find('m:t', NS).text for x in ET.fromstring(archive.read('xl/sharedStrings.xml'))]
        rows = ET.fromstring(archive.read('xl/worksheets/sheet1.xml')).findall('.//m:row', NS)
    parsed = {}
    for r in rows[1:]:
        serial, label = (c.find('m:v', NS).text for c in r)
        slots = int((Decimal(serial)*48).to_integral_value())
        parsed[int(r.attrib['r'])] = (datetime(1899, 12, 30) + timedelta(minutes=30*slots), labels[int(label)])
    return parsed


def main():
    initial = from_json(BASE / 'source_access_curl.json')
    target = from_json(BASE / 'targeted_access.json')
    spec = from_json(BASE / 'targeted_amendment.json')
    assert sha((BASE / 'targeted_amendment.json').read_bytes()) == target['amendment_sha256']
    received, data = checked_prefix(initial, target, spec)
    linked = from_csv(TARGET / 'linked_intervals.csv')
    denominator = from_csv(TARGET / 'denominators.csv')
    desired = {(r['household'], r['expected_gmt_end'][:19].replace('T', ' ')) for r in linked}
    source_rows = defaultdict(list)
    labels = defaultdict(set)
    observed_bounds = {}
    count = 0
    reader = csv.reader(io.TextIOWrapper(io.BytesIO(data), encoding='utf-8-sig'))
    assert next(reader)[:3] == ['LCLid', 'stdorToU', 'DateTime']
    for r in reader:
        count += 1
        id_, label, stamp = r[:3]
        key = id_, stamp[:19]
        labels[id_].add(label)
        if id_ not in observed_bounds:
            observed_bounds[id_] = key[1], key[1]
        else:
            begin, end = observed_bounds[id_]
            observed_bounds[id_] = min(begin, key[1]), max(end, key[1])
        if key in desired:
            source_rows[key].append((reader.line_num, label, stamp, r[3]))
    allowed = sorted(h for h, (first, last) in observed_bounds.items() if labels[h] == {'ToU'} and
                     first <= '2013-02-11 00:00:00' and last >= '2013-11-22 06:00:00')
    assert sorted({h for h, _ in desired}) == allowed[:2]
    assert count == target['prefix_member']['records']
    price = tariff_xml()
    totals = defaultdict(Counter)
    price_checks = 0
    for r in linked:
        key = r['household'], r['expected_gmt_end'][:19].replace('T', ' ')
        records = [(x['row'], x['label'], x['timestamp'], x['token']) for x in json.loads(r['raw_source_records'])]
        assert records == source_rows[key] and len(records) == int(r['raw_rows_found'])
        if len(records) == 1:
            assert r['status'] == ('raw_zero' if Decimal(records[0][-1]) == 0 else 'numeric_nonzero')
        else:
            assert len(records) == 2 and records[0][1:] == records[1][1:] and r['status'] == 'duplicate_same'
        totals[r['scope'], r['arm']][r['status']] += 1
        if r['arm'] == 'clock_only':
            assert not r['tariff_workbook_row'] and not r['tariff_raw_label']
        else:
            tariff_start, category = price[int(r['tariff_workbook_row'])]
            assert tariff_start == datetime.fromisoformat(r['derived_local_start']).replace(tzinfo=None)
            assert r['tariff_raw_label'] == category
            if r['scope'] == 'event_window':
                assert category == r['arm']
            price_checks += 1
    for r in denominator:
        counts = totals[r['scope'], r['arm']]
        assert sum(counts.values()) == int(r['selected_household_slots'])
        assert counts['numeric_nonzero'] == int(r['numeric_nonzero'])
        assert counts['duplicate_same'] == int(r['duplicate_same'])
    result = {'status': 'passed', 'total_verified_http_range_bytes': received, 'complete_prefix_rows': count,
              'full_range_dynamic_households_in_prefix': len(allowed), 'selected_dynamic_households': allowed[:2],
              'link_rows_verified': len(linked), 'unique_household_meter_keys_verified': len(desired),
              'unique_raw_source_rows_verified': sum(map(len, source_rows.values())),
              'tariff_raw_row_joins_verified': price_checks, 'full_member_crc_possible': False,
              'confirmations_opened': 0, 'effect_estimates': 0, 'model_fits': 0}
    with (TARGET / 'verification.json').open('x', encoding='utf-8') as f:
        json.dump(result, f, indent=2)
        f.write('\n')
    print(result)


if __name__ == '__main__':
    main()
