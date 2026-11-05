"""Independently verify public byte ranges and time keys, without reading kWh values."""
import csv
import io
import json
import struct
import zlib
from collections import Counter
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from zoneinfo import ZoneInfo


BASE = Path(__file__).resolve().parent
ORIGINAL = BASE / 'original'
LONDON = ZoneInfo('Europe/London')
GMT = timezone.utc
HALF = timedelta(minutes=30)


def read_csv(name):
    with (BASE / name).open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def digest_bytes(blob):
    return sha256(blob).hexdigest()


def payloads(source):
    logs = source['range_requests']
    assert len(logs) == 5 and all(r['status'] == 206 for r in logs)
    assert len({(r['etag'], r['last_modified'], r['content_range'].split('/')[-1]) for r in logs}) == 1
    tail = (ORIGINAL / 'curl_zip_tail.bin').read_bytes()
    assert digest_bytes(tail) == logs[0]['sha256']
    end = tail.rfind(b'PK\x05\x06')
    count, size, offset = struct.unpack_from('<HII', tail, end + 10)
    assert count == source['zip_total_members'] == 168
    total = int(logs[0]['content_range'].split('/')[-1])
    tail_start = total - len(tail)
    directory = tail[offset-tail_start:offset-tail_start+size]
    assert directory == (ORIGINAL / 'zip_central_directory.bin').read_bytes()
    found = {}
    start = 0
    while start < len(directory):
        assert directory[start:start + 4] == b'PK\x01\x02'
        crc, packed_size, size = struct.unpack_from('<III', directory, start + 16)
        namelen, extralen, commentlen = struct.unpack_from('<HHH', directory, start + 28)
        offset = struct.unpack_from('<I', directory, start + 42)[0]
        name = directory[start+46:start+46+namelen].decode('ascii')
        found[name] = crc, packed_size, size, offset
        start += 46 + namelen + extralen + commentlen
    for i, m in enumerate(source['members']):
        packed = (ORIGINAL / m['file']).read_bytes()
        local = (ORIGINAL / f'member_{i+1:02d}_local_header.bin').read_bytes()
        assert digest_bytes(local) == logs[2*i+1]['sha256']
        assert digest_bytes(packed) == logs[2*i+2]['sha256']
        content = zlib.decompress(packed, -15)
        assert found[m['name']] == (zlib.crc32(content), len(packed), len(content), m['offset'])
        assert digest_bytes(content) == m['expanded_sha256']
        yield m, content


def clock_checks(raw_time_keys, household):
    result = []
    for day, first, last in (('2013-03-30', '2013-03-30T05:00', '2013-03-31T05:00'),
                             ('2013-10-26', '2013-10-26T05:00', '2013-10-27T05:00')):
        start = datetime.fromisoformat(first).replace(tzinfo=LONDON).astimezone(GMT)
        stop = datetime.fromisoformat(last).replace(tzinfo=LONDON).astimezone(GMT)
        hours = int((stop-start)/HALF)
        expected = [start + i*HALF for i in range(1, hours + 1)]
        key_counts = [raw_time_keys[dt.replace(tzinfo=None)] for dt in expected]
        special = [dt for dt in expected if dt.date() > start.date() and dt.hour == 1]
        result.append({'household_clock_only': household, 'trial_day': day,
                       'physical_half_hours': hours, 'unique_raw_gmt_keys_present': sum(n > 0 for n in key_counts),
                       'keys_with_multiple_rows': sum(n > 1 for n in key_counts),
                       'native_01h_keys_seen': sum(raw_time_keys[dt.replace(tzinfo=None)] for dt in special),
                       'native_01h_keys_as_gmt': '|'.join(dt.isoformat() for dt in special),
                       'corresponding_london_wall_times': '|'.join(dt.astimezone(LONDON).isoformat() for dt in special)})
    return result


def main():
    receipt = json.loads((BASE / 'source_access_curl.json').read_text(encoding='utf-8'))
    assert digest_bytes((BASE / 'protocol.json').read_bytes()) == receipt['protocol_sha256']
    groups = set()
    households = set()
    rows = 0
    dynamic = set()
    times = Counter()
    # One clock-only ID, chosen from source key metadata by lexicographic order.
    clock_id = min(h for item in receipt['members'] for h, info in item['household_metadata'].items()
                   if info['labels'] == ['Std'] and info['first'] < '2013-03-30 00:00:00'
                   and info['last'] > '2013-10-27 06:00:00')
    for member, payload in payloads(receipt):
        source = csv.reader(io.TextIOWrapper(io.BytesIO(payload), encoding='utf-8-sig'))
        assert next(source)[:3] == ['LCLid', 'stdorToU', 'DateTime']
        count = 0
        for row in source:
            count += 1
            hid, label, raw_time = row[:3]
            groups.add(label)
            households.add(hid)
            if label.strip().casefold() in ('dtou', 'tou'):
                dynamic.add(hid)
            if hid == clock_id and raw_time[:10] in ('2013-03-30', '2013-03-31', '2013-10-26', '2013-10-27'):
                times[datetime.fromisoformat(raw_time[:19])] += 1
        assert count == member['records']
        rows += count
    clocks = clock_checks(times, clock_id)
    with (BASE / 'clock_key_checks.csv').open('x', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(clocks[0]))
        writer.writeheader()
        writer.writerows(clocks)
    planned = read_csv('planned_windows.csv')
    for row in planned:
        a = datetime.fromisoformat(row['start_gmt'])
        b = datetime.fromisoformat(row['last_gmt_end_key'])
        assert int((b-a)/HALF) == int(row['slots_per_household'])
        assert a + HALF == datetime.fromisoformat(row['first_gmt_end_key'])
    denominators = read_csv('denominators.csv')
    link = json.loads((BASE / 'link_receipt.json').read_text(encoding='utf-8'))
    assert not dynamic and link['selected'] == {} and link['linked_rows'] == 0
    assert all(int(r['selected_dToU_households']) == 0 and not r['raw_zero'] for r in denominators)
    result = {'status': 'passed', 'zip_range_responses_verified': len(receipt['range_requests']),
              'zip_members_independently_decoded': len(receipt['members']), 'csv_metadata_rows_replayed': rows,
              'unique_households': len(households), 'source_group_labels': sorted(groups),
              'dynamic_households': len(dynamic), 'clock_only_household': clock_id,
              'planned_windows_verified': len(planned), 'linked_dynamic_intervals': 0,
              'kwh_value_fields_interpreted': 0, 'old_confirmations_read': 0, 'effects_or_models': 0}
    with (BASE / 'verification.json').open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(result)


if __name__ == '__main__':
    main()
