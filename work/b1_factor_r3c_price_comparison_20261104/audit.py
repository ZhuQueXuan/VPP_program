"""Replay the frozen C17 calendar admission screen. No meter inputs."""
import argparse
import csv
import json
from collections import Counter
from datetime import date, datetime, time, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from zoneinfo import ZoneInfo

from openpyxl import load_workbook
from scipy.stats import t


HERE = Path(__file__).resolve().parent
ROOTS = {
    'r3a': HERE.parent / 'b1_factor_r3a_price_admission_20261104',
    'r3b': HERE.parent / 'b1_factor_r3b_meter_link_20261104',
}
HALF = timedelta(minutes=30)
DAY = timedelta(days=1)
SEASONS = ('DJF', 'MAM', 'JJA', 'SON')
ARMS = ('High', 'Low', 'Normal')


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def csv_rows(path):
    with path.open(encoding='utf-8-sig', newline='') as file:
        return list(csv.DictReader(file))


def summarize(rows):
    counts = Counter(row['arm'] for row in rows)
    return {arm: counts[arm] for arm in ARMS}


def main(write):
    protocol_path = HERE / 'protocol.json'
    spec = json.loads(protocol_path.read_text(encoding='utf-8'))
    source = json.loads((HERE / 'source_receipt.json').read_text(encoding='utf-8'))
    assert digest(protocol_path) == source['protocol_sha256']
    for name, expected in spec['inputs'].items():
        part, path = name.split('/', 1)
        assert digest(ROOTS[part] / path) == expected, name

    old = ROOTS['r3a']
    days = {date.fromisoformat(r['trial_day']): r for r in csv_rows(old / 'trial_days.csv')}
    cm = csv_rows(old / 'cm_schedule_check.csv')
    cm_dates = {r['trial_day'] for r in cm}
    assert len(cm_dates) == len(cm) == 21
    book = load_workbook(old / 'original' / 'Tariffs.xlsx', read_only=True, data_only=True)
    values = iter(book['Sheet1'].values)
    assert next(values) == ('TariffDateTime', 'Tariff')
    tariffs = {stamp: (arm, i) for i, (stamp, arm) in enumerate(values, 2)}
    book.close()
    assert len(tariffs) == 17520
    assert all(b - a == HALF for a, b in zip(tariffs, list(tariffs)[1:]))

    spec_window = spec['window']
    holidays = set(spec['bank_holidays'])
    tz = ZoneInfo(spec_window['time_zone'])
    previous = {
        (r['trial_day'], r['arm_raw']): r for r in csv_rows(old / 'candidate_windows.csv')
        if r['cell'] == spec_window['cell']
    }
    rows = []
    for d, day in sorted(days.items()):
        if d.weekday() >= 5 or day['classification'] not in {'SF_shape_candidate', 'normal_full_day'}:
            continue
        assert day['raw_slots'] == day['expected_utc_slots_full_trial_day'] == '48'
        assert d.isoformat() not in cm_dates
        begin = datetime.combine(d, time(spec_window['trial_day_local_start_hour']))
        start = datetime.combine(d, time(spec_window['local_start_hour']))
        span = [start + i * HALF for i in range(spec_window['slots'])]
        all_slots = [begin + i * HALF for i in range(48)]
        arm = tariffs[start][0]
        if any(tariffs[s][0] != (arm if s in span else 'Normal') for s in all_slots):
            continue
        to_gmt = lambda stamp: stamp.replace(tzinfo=tz).astimezone(timezone.utc)
        prev = days.get(d - DAY, {}).get('classification', 'outside_calendar')
        following = days.get(d + DAY, {}).get('classification', 'outside_calendar')
        neighbors = prev == following == 'normal_full_day'
        earlier = previous.pop((d.isoformat(), arm))
        assert (neighbors == (earlier['adjacent_trial_days_both_normal'] == 'True'))
        assert int(earlier['raw_first_row']) == tariffs[start][1]
        assert int(earlier['raw_last_row']) == tariffs[span[-1]][1]
        first_end = (to_gmt(start) + HALF).isoformat()
        assert first_end == earlier['first_ukds_end_key_if_aligned']
        assert (to_gmt(begin + DAY) - to_gmt(begin)) / HALF == 48
        ordinary = d.isoformat() not in holidays
        rows.append({
            'trial_day': d.isoformat(), 'arm': arm, 'season': SEASONS[(d.month % 12) // 3],
            'iso_week': d.strftime('%G-W%V'), 'weekday_0_is_mon': d.weekday(),
            'bank_holiday': not ordinary, 'local_start': start.isoformat(),
            'local_end': (span[-1] + HALF).isoformat(), 'gmt_first_end_if_aligned': first_end,
            'gmt_last_end_if_aligned': to_gmt(span[-1] + HALF).isoformat(),
            'trial_day_gmt_first_end_if_aligned': (to_gmt(begin) + HALF).isoformat(),
            'trial_day_gmt_last_end_if_aligned': to_gmt(begin + DAY).isoformat(),
            'tariff_first_row': tariffs[start][1], 'tariff_last_row': tariffs[span[-1]][1],
            'previous_trial_day': prev, 'next_trial_day': following,
            'neighbors_normal': neighbors, 'eligible_shape_only': ordinary and neighbors,
            'event_identity': 'published_all_normal' if arm == 'Normal' else 'SF_shape_unverified',
            'assigned_normal': False,
        })
    assert not previous, 'C17 source window missing from replay'

    eligible = [r for r in rows if r['eligible_shape_only']]
    by_season = {s: summarize([r for r in eligible if r['season'] == s]) for s in SEASONS}
    bound = sum(min(counts.values()) for counts in by_season.values())
    assert bound == 0, 'An eligible stratum requires the frozen block assignment before proceeding'
    precision = spec['precision']
    quantile = 1 - precision['family_alpha'] / (2 * precision['primary_comparisons'])
    half_width = {
        n: float(t.ppf(quantile, n - 1) * precision['planning_block_sd_kwh'] / n**0.5)
        for n in range(2, precision['minimum_disjoint_triplets'] + 1)
    }
    minimum = min(n for n, width in half_width.items() if width <= precision['event_min_useful_kwh'])
    assert minimum == precision['minimum_disjoint_triplets']
    results = {
        'protocol_sha256': digest(protocol_path), 'input_hashes_verified': len(spec['inputs']),
        'tariff_rows': len(tariffs), 'cm_dates': len(cm),
        'cm_exact_matches': {k: sum(r[k] == 'True' for r in cm)
                             for k in ('local_start', 'gmt_start', 'local_end', 'gmt_end')},
        'cm_conflicts': [r['trial_day'] for r in cm if r['local_start'] == 'False'],
        'unlisted_cm_shapes': [d.isoformat() for d, r in days.items() if r['classification'] == 'CM_shape_unlisted'],
        'dst_excluded': {d.isoformat(): int(r['expected_utc_slots_full_trial_day'])
                         for d, r in days.items() if r['classification'] == 'clock_transition_excluded'},
        'partial_excluded': {d.isoformat(): int(r['raw_slots']) for d, r in days.items()
                             if r['classification'] == 'partial_calendar_edge'},
        'date_denominator': {
            'raw_shape': summarize(rows),
            'ordinary_workday': summarize([r for r in rows if not r['bank_holiday']]),
            'ordinary_and_adjacent_normal': summarize(eligible),
            'ordinary_and_adjacent_normal_by_season': by_season,
            'verified_SF_dates': 0, 'same_season_triplets_optimistic_bound': bound,
            'assigned_triplets': 0, 'assigned_normal_dates': 0, 'assigned_normal': [],
        },
        'precision': {'minimum_triplets': minimum, 'half_width_kwh_at_11': half_width[11],
                      'half_width_kwh_at_12': half_width[12]},
        'household_denominator': {
            'status': 'not_opened_after_calendar_gate', 'eligible': None, 'complete_event': None,
            'complete_trial_day': None, 'complete_common_panel': None,
        },
        'gates': {'same_release_clock': False, 'verified_SF_labels': False,
                  'shape_only_date_support': False, 'meter_acquisition_authorized_by_gate': False},
        'meter_download_bytes': 0, 'meter_rows_read': 0, 'outcome_comparisons': 0,
        'decision': 'stop_before_meter_acquisition',
    }
    if write:
        with (HERE / 'event_dates.csv').open('x', encoding='utf-8-sig', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        with (HERE / 'decision.json').open('x', encoding='utf-8') as file:
            json.dump(results, file, indent=2, ensure_ascii=False)
            file.write('\n')
    else:
        assert json.loads((HERE / 'decision.json').read_text(encoding='utf-8')) == results
        saved = csv_rows(HERE / 'event_dates.csv')
        assert saved == [{k: str(v) for k, v in row.items()} for row in rows]
    print(json.dumps(results, ensure_ascii=True, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true', help='create receipts once')
    main(parser.parse_args().write)
