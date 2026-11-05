"""Independently recover C17 candidates directly from Excel XML."""
import argparse
import csv
import json
import runpy
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from zoneinfo import ZoneInfo


HERE = Path(__file__).resolve().parent
R3A = HERE.parent / 'b1_factor_r3a_price_admission_20261104'
STEP = timedelta(minutes=30)
DAY = timedelta(days=1)


def load_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as file:
        return list(csv.DictReader(file))


def main(write):
    raw = runpy.run_path(str(R3A / 'verify_calendar.py'))['raw_rows']()
    spec = json.loads((HERE / 'protocol.json').read_text(encoding='utf-8'))
    result = json.loads((HERE / 'decision.json').read_text(encoding='utf-8'))
    rows = {r['trial_day']: r for r in load_csv(HERE / 'event_dates.csv')}
    assert len(raw) == 17520
    by_day = defaultdict(list)
    for index, (stamp, arm) in raw.items():
        by_day[(stamp - 10 * STEP).date()].append((index, stamp, arm))
    london = ZoneInfo('Europe/London')

    def utc(stamp):
        return stamp.replace(tzinfo=london).astimezone(timezone.utc)

    slot_lookup = {stamp: arm for stamp, arm in raw.values()}
    cm_rows = load_csv(R3A / 'cm_schedule_check.csv')
    matches = Counter()
    conflicts = []
    for cm in cm_rows:
        day = date.fromisoformat(cm['trial_day'])
        start = datetime.fromisoformat(cm['expected_local_start'])
        end = datetime.fromisoformat(cm['expected_local_end'])
        count = (end - start) // STEP
        starts = [start + i * STEP for i in range(count)]
        gmt_starts = [utc(s).replace(tzinfo=None) for s in starts]
        possible = {'local_start': starts, 'gmt_start': gmt_starts,
                    'local_end': [s + STEP for s in starts],
                    'gmt_end': [s + STEP for s in gmt_starts]}
        same_count = sum(arm == 'High' for _, _, arm in by_day[day]) == count
        for name, stamps in possible.items():
            agrees = same_count and all(slot_lookup.get(s) == 'High' for s in stamps)
            matches[name] += agrees
            assert agrees == (cm[name] == 'True')
            if name == 'local_start' and not agrees:
                conflicts.append(cm['trial_day'])
                assert {arm for _, _, arm in by_day[day]} == {'Low'}
    assert dict(matches) == result['cm_exact_matches']
    assert conflicts == result['cm_conflicts']
    dst = {}
    partial = {}
    for day, slots in by_day.items():
        start = slots[0][1]
        if len(slots) != 48:
            partial[str(day)] = len(slots)
            continue
        actual = (utc(start + DAY) - utc(start)) // STEP
        if actual != 48:
            dst[str(day)] = actual
    assert dst == result['dst_excluded'] and partial == result['partial_excluded']
    all_normal = {
        day for day, slots in by_day.items()
        if len(slots) == 48 and str(day) not in dst
        and all(arm == 'Normal' for _, _, arm in slots)
    }

    seen = set()
    raw_counts = Counter()
    ordinary_counts = Counter()
    eligible_counts = defaultdict(Counter)
    for day, slots in by_day.items():
        key = str(day)
        if day.isoweekday() > 5 or key in dst or key in partial:
            continue
        event_slots = slots[24:30]
        event_arms = {arm for _, _, arm in event_slots}
        outer_arms = {arm for _, _, arm in slots[:24] + slots[30:]}
        if len(event_arms) != 1 or outer_arms != {'Normal'}:
            continue
        assert key not in {r['trial_day'] for r in cm_rows}
        seen.add(key)
        arm = event_arms.pop()
        raw_counts[arm] += 1
        row = rows[key]
        assert row['arm'] == arm
        assert row['tariff_first_row'] == str(event_slots[0][0])
        assert row['tariff_last_row'] == str(event_slots[-1][0])
        assert row['gmt_first_end_if_aligned'] == (utc(event_slots[0][1]) + STEP).isoformat()
        assert row['gmt_last_end_if_aligned'] == (utc(event_slots[-1][1]) + STEP).isoformat()
        is_holiday = key in spec['bank_holidays']
        adjacent = {day - DAY, day + DAY} <= all_normal
        season = ('DJF', 'MAM', 'JJA', 'SON')[(day.month % 12) // 3]
        assert row['season'] == season
        assert row['bank_holiday'] == str(is_holiday)
        assert row['neighbors_normal'] == str(adjacent)
        assert row['eligible_shape_only'] == str(not is_holiday and adjacent)
        assert row['assigned_normal'] == 'False'
        if not is_holiday:
            ordinary_counts[arm] += 1
            if adjacent:
                eligible_counts[season][arm] += 1

    assert seen == rows.keys()
    counts = result['date_denominator']
    assert dict(raw_counts) == counts['raw_shape']
    assert dict(ordinary_counts) == counts['ordinary_workday']
    for season, arms in counts['ordinary_and_adjacent_normal_by_season'].items():
        assert eligible_counts[season] == Counter(arms)
    assert all(not (arms['High'] and arms['Low']) for arms in eligible_counts.values())
    assert counts['same_season_triplets_optimistic_bound'] == 0
    assert counts['assigned_normal_dates'] == 0
    assert result['decision'] == 'stop_before_meter_acquisition'
    assert not any(result['gates'].values())

    names = ('protocol.json', 'source_receipt.json', 'event_dates.csv', 'decision.json', 'audit.py')
    receipt = {
        'excel_xml_rows': len(raw), 'candidate_dates_recovered': len(seen),
        'candidate_full_days_and_window_keys_checked': len(seen),
        'cm_plan_dates_replayed': len(cm_rows), 'cm_clock_hypotheses_checked': 4 * len(cm_rows),
        'dst_days_checked': len(dst), 'calendar_edge_days_checked': len(partial),
        'seasonal_support_counts_reproduced': True, 'matching_ceiling_reproduced': 0,
        'meter_files_opened': 0, 'sha256': {
            name: sha256((HERE / name).read_bytes()).hexdigest() for name in names
        },
    }
    path = HERE / 'verification.json'
    if write:
        with path.open('x', encoding='utf-8') as file:
            json.dump(receipt, file, indent=2)
            file.write('\n')
    else:
        assert json.loads(path.read_text(encoding='utf-8')) == receipt
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true', help='create receipt once')
    main(parser.parse_args().write)
