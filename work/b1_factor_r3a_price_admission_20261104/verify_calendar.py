"""Verify source cells and derived windows through the workbook XML."""
import csv
import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from xml.etree import ElementTree
from zipfile import ZipFile
from zoneinfo import ZoneInfo


BASE = Path(__file__).resolve().parent
NS = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
STEP = timedelta(minutes=30)


def read_csv(name):
    with (BASE / name).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def raw_rows():
    with ZipFile(BASE / 'original' / 'Tariffs.xlsx') as z:
        labels = [part.find('m:t', NS).text for part in ElementTree.fromstring(z.read('xl/sharedStrings.xml'))]
        elements = ElementTree.fromstring(z.read('xl/worksheets/sheet1.xml')).findall('.//m:row', NS)
        assert tuple(labels[int(c.find('m:v', NS).text)] for c in elements[0]) == ('TariffDateTime', 'Tariff')
        result = {}
        for row in elements[1:]:
            serial, label = (c.find('m:v', NS).text for c in row)
            slots = Decimal(serial) * 48
            integer = int(slots.to_integral_value())
            assert abs(slots - integer) < Decimal('0.000001')
            result[int(row.attrib['r'])] = (datetime(1899, 12, 30) + integer * STEP, labels[int(label)])
    return result


def main():
    source = raw_rows()
    audit = json.loads((BASE / 'calendar_audit.json').read_text(encoding='utf-8'))
    assert len(source) == audit['raw_rows']
    assert Counter(tariff for _, tariff in source.values()) == audit['raw_categories']
    for file, info in audit['original_hashes'].items():
        raw = (BASE / 'original' / file).read_bytes()
        assert len(raw) == info['bytes'] and sha256(raw).hexdigest() == info['sha256']
    seen = set()
    for row in read_csv('trial_days.csv'):
        block = list(range(int(row['raw_first_row']), int(row['raw_last_row']) + 1))
        assert seen.isdisjoint(block)
        seen.update(block)
        labels = Counter(source[n][1] for n in block)
        assert len(block) == int(row['raw_slots'])
        assert all((source[n][0] - 10 * STEP).date().isoformat() == row['trial_day'] for n in block)
        assert all(labels[k] == int(row[k.lower() + '_slots']) for k in ('Normal', 'High', 'Low'))
    assert seen == set(source)
    cm = read_csv('cm_schedule_check.csv')
    assert len(cm) == 21
    expected_matches = {k: sum(r[k] == 'True' for r in cm) for k in ('local_start', 'local_end', 'gmt_start', 'gmt_end')}
    assert expected_matches == audit['cm_plan_match_counts_by_timestamp_hypothesis']
    windows = read_csv('candidate_windows.csv')
    counts = Counter()
    for r in windows:
        first, last = int(r['raw_first_row']), int(r['raw_last_row'])
        assert last - first + 1 == int(r['slots'])
        assert all(source[n][1] == r['arm_raw'] for n in range(first, last + 1))
        assert source[first][0].isoformat() == r['start_local']
        assert source[last][0].isoformat() == r['raw_last_stamp']
        end = source[last][0] + STEP
        assert end.isoformat() == r['end_local_exclusive']
        london = ZoneInfo('Europe/London')
        utc_end = end.replace(tzinfo=london).astimezone(timezone.utc)
        utc_first_end = (source[first][0] + STEP).replace(tzinfo=london).astimezone(timezone.utc)
        assert utc_end.isoformat() == r['end_gmt_exclusive']
        assert utc_first_end.isoformat() == r['first_ukds_end_key_if_aligned']
        counts[(r['cell'], r['arm_raw'])] += 1
    assert Counter(r['arm_raw'] for r in windows) == audit['window_rows']
    cells = read_csv('comparison_cells.csv')
    for row in cells:
        for arm in ('Normal', 'High', 'Low'):
            assert counts[(row['cell'], arm)] == int(row[arm])
    dst = read_csv('clock_transition_conflicts.csv')
    assert Counter(r['status'] for r in dst) == {'ambiguous': 2, 'nonexistent': 2}
    receipt = {'source_xml_rows_checked': len(source), 'windows_replayed': len(windows),
               'cell_counts_checked': len(cells), 'clock_label_conflicts_checked': len(dst),
               'original_files_hash_checked': len(audit['original_hashes']),
               'meter_outcome_files_opened': 0, 'fits_or_effect_estimates': 0}
    with (BASE / 'verification.json').open('x', encoding='utf-8') as f:
        json.dump(receipt, f, indent=2)
        f.write('\n')
    print(receipt)


if __name__ == '__main__':
    main()
