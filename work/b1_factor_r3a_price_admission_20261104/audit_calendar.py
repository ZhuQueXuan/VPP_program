"""Reconcile the official London tariff calendar without reading household outcomes."""
import csv
import json
from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile
from zoneinfo import ZoneInfo

from openpyxl import load_workbook


BASE = Path(__file__).resolve().parent
LONDON = ZoneInfo('Europe/London')
UTC = timezone.utc
DAY = timedelta(days=1)
HALF_HOUR = timedelta(minutes=30)

# Author's 2015 thesis Table 4.5. From/To are the first and last half-hour end stamps.
CM = {
    '01-19': ('P9_2D', '17:30', '23:00'), '01-20': ('P9_2D', '17:30', '23:00'),
    '01-29': ('P3_1D', '07:30', '10:00'), '02-09': ('P8_1D', '10:30', '14:00'),
    '02-20': ('P4_2D', '17:30', '23:00'), '02-21': ('P4_2D', '17:30', '23:00'),
    '03-16': ('P9_2D', '17:30', '23:00'), '03-17': ('P9_2D', '17:30', '23:00'),
    '03-21': ('P3_1D', '07:30', '10:00'), '03-27': ('P4_3D', '17:30', '23:00'),
    '03-28': ('P4_3D', '17:30', '23:00'), '03-29': ('P4_3D', '17:30', '23:00'),
    '04-23': ('P1_1D', '17:30', '23:00'), '05-01': ('P1_3D', '17:30', '23:00'),
    '05-02': ('P1_3D', '17:30', '23:00'), '05-03': ('P1_3D', '17:30', '23:00'),
    '10-13': ('P6_1D', '17:30', '23:00'), '10-20': ('P6_1D', '17:30', '23:00'),
    '11-26': ('P1_2D', '17:30', '23:00'), '11-27': ('P1_2D', '17:30', '23:00'),
    '12-15': ('P9_1D', '17:30', '23:00'),
}
SF_TIMES = {6: (5, 8, 11, 14, 17, 20, 23, 2), 12: (5, 11, 17, 23),
            24: (5, 11, 17), 48: (5,)}


def write_csv(name, rows):
    with (BASE / name).open('x', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def start_day(d):
    return datetime.combine(d, time(5))


def trial_day(stamp):
    return (stamp - timedelta(hours=5)).date()


def to_gmt(wall):
    return wall.replace(tzinfo=LONDON).astimezone(UTC)


def nominal_status(wall):
    valid = set()
    for fold in (0, 1):
        gmt = wall.replace(tzinfo=LONDON, fold=fold).astimezone(UTC)
        if gmt.astimezone(LONDON).replace(tzinfo=None) == wall:
            valid.add(gmt)
    return {0: 'nonexistent', 1: 'unique', 2: 'ambiguous'}[len(valid)]


def weekday(d):
    return 'weekday' if d.weekday() < 5 else 'weekend'


def join(values):
    return '|'.join(str(v) for v in values)


def get_tariffs():
    path = BASE / 'original' / 'Tariffs.xlsx'
    with ZipFile(path) as archive:
        assert archive.testzip() is None
    book = load_workbook(path, read_only=True, data_only=True)
    rows = iter(book['Sheet1'].values)
    assert next(rows) == ('TariffDateTime', 'Tariff')
    calendar = {stamp: (i, tariff) for i, (stamp, tariff) in enumerate(rows, 2)}
    assert len(calendar) == book['Sheet1'].max_row - 1
    assert all(not any(any(v is not None for v in r) for r in book[s].values) for s in ('Sheet2', 'Sheet3'))
    book.close()
    assert set(x[1] for x in calendar.values()) == {'Normal', 'High', 'Low'}
    assert len(calendar) == 17520
    assert all(b - a == HALF_HOUR for a, b in zip(calendar, list(calendar)[1:]))
    return calendar


def cm_evidence(calendar, groups):
    rows = []
    for fragment, (code, first_end, last_end) in CM.items():
        d = date.fromisoformat('2013-' + fragment)
        expected_start = datetime.combine(d, time.fromisoformat(first_end)) - HALF_HOUR
        expected_end = datetime.combine(d, time.fromisoformat(last_end))
        native = [stamp for stamp in groups[d] if calendar[stamp][1] == 'High']
        expected = []
        while expected_start + len(expected) * HALF_HOUR < expected_end:
            expected.append(expected_start + len(expected) * HALF_HOUR)
        actual = {
            'local_start': expected,
            'local_end': [s + HALF_HOUR for s in expected],
            'gmt_start': [to_gmt(s).replace(tzinfo=None) for s in expected],
            'gmt_end': [(to_gmt(s) + HALF_HOUR).replace(tzinfo=None) for s in expected],
        }
        check = {label: all(calendar.get(s, (0, ''))[1] == 'High' for s in labels) and len(native) == len(labels)
                 for label, labels in actual.items()}
        rows.append({'trial_day': d.isoformat(), 'plan_code': code, 'plan_first_local_end': first_end,
                     'plan_last_local_end': last_end, 'expected_local_start': expected_start.isoformat(),
                     'expected_local_end': expected_end.isoformat(), 'workbook_high_first': native[0].isoformat() if native else '',
                     'workbook_high_last': native[-1].isoformat() if native else '', 'workbook_high_slots': len(native),
                     'workbook_low_slots': sum(calendar[s][1] == 'Low' for s in groups[d]), **check})
    return rows


def classify(calendar, groups, cm_rows):
    days = {}
    patterns = defaultdict(list)
    plan = {date.fromisoformat(row['trial_day']): row for row in cm_rows}
    for d, points in sorted(groups.items()):
        counts = Counter(calendar[s][1] for s in points)
        elapsed = int((to_gmt(start_day(d + DAY)) - to_gmt(start_day(d))) / HALF_HOUR)
        event = [s for s in points if calendar[s][1] != 'Normal']
        state = 'partial_calendar_edge'
        if len(points) == 48:
            if elapsed != 48:
                state = 'clock_transition_excluded'
            elif d in plan:
                state = 'CM_plan_matches' if plan[d]['local_start'] else 'CM_plan_conflict'
            elif counts['Low'] and counts['High']:
                state = 'CM_shape_unlisted'
            elif not event:
                state = 'normal_full_day'
            else:
                kind = calendar[event[0]][1]
                valid = (len(event) in SF_TIMES and event[0].minute == 0 and
                         event[0].hour in SF_TIMES[len(event)] and
                         event[-1] - event[0] == HALF_HOUR * (len(event) - 1) and
                         not (kind == 'High' and len(event) == 48))
                state = 'SF_shape_candidate' if valid else 'unresolved_tariff_path'
                if valid:
                    patterns[(kind, len(event), event[0].hour)].append((d, event[0]))
        days[d] = {'trial_day': d.isoformat(), 'day_type': weekday(d), 'classification': state,
                   'raw_slots': len(points), 'expected_utc_slots_full_trial_day': elapsed,
                   'normal_slots': counts['Normal'], 'high_slots': counts['High'], 'low_slots': counts['Low'],
                   'raw_first_row': calendar[points[0]][0], 'raw_last_row': calendar[points[-1]][0],
                   'first_non_normal': event[0].isoformat() if event else '',
                   'last_non_normal': event[-1].isoformat() if event else ''}
    return days, patterns


def signature(d, start, length):
    return (start.strftime('%H:%M'), length, weekday(d), weekday(start.date()),
            weekday((start + (length - 1) * HALF_HOUR).date()))


def describe_window(d, start, length, kind, calendar, days):
    end = start + length * HALF_HOUR
    source_last = end - HALF_HOUR
    adjacent = all(days.get(neighbor, {}).get('classification') == 'normal_full_day'
                   for neighbor in (d - DAY, d + DAY))
    gmt_start, gmt_end = to_gmt(start), to_gmt(end)
    assert (gmt_end - gmt_start) / HALF_HOUR == length
    assert all(calendar[start + n * HALF_HOUR][1] == kind for n in range(length))
    return {'trial_day': d.isoformat(), 'arm_raw': kind, 'start_local': start.isoformat(),
            'end_local_exclusive': end.isoformat(), 'start_gmt': gmt_start.isoformat(),
            'end_gmt_exclusive': gmt_end.isoformat(), 'first_ukds_end_key_if_aligned': (gmt_start + HALF_HOUR).isoformat(),
            'trial_day_type': weekday(d), 'trial_weekday_0_is_mon': d.weekday(),
            'start_day_type': weekday(start.date()), 'last_half_hour_day_type': weekday(source_last.date()),
            'slots': length, 'raw_first_row': calendar[start][0], 'raw_last_row': calendar[source_last][0],
            'raw_last_stamp': source_last.isoformat(), 'adjacent_trial_days_both_normal': adjacent}


def comparison(calendar, days, patterns):
    cells = defaultdict(lambda: {'High': [], 'Low': [], 'Normal': []})
    for (kind, length, _hour), placements in sorted(patterns.items()):
        for d, start in placements:
            cells[signature(d, start, length)][kind].append(describe_window(d, start, length, kind, calendar, days))
    for sig in cells:
        start_text, length, daytype, *_ = sig
        clock = time.fromisoformat(start_text)
        for d, record in days.items():
            if record['classification'] != 'normal_full_day' or record['day_type'] != daytype:
                continue
            start = datetime.combine(d + (DAY if clock.hour < 5 else timedelta()), clock)
            if signature(d, start, length) == sig:
                cells[sig]['Normal'].append(describe_window(d, start, length, 'Normal', calendar, days))
    windows, counts = [], []
    for i, (sig, arms) in enumerate(sorted(cells.items()), 1):
        cell = f'C{i:02d}'
        windows.extend({'cell': cell, **row} for side in arms.values() for row in side)
        counts.append({'cell': cell, 'wall_start': sig[0], 'slots': sig[1], 'trial_day_type': sig[2],
                       'start_day_type': sig[3], 'last_half_hour_day_type': sig[4],
                       **{k: len(v) for k, v in arms.items()},
                       **{k + '_adjacent_normal': sum(r['adjacent_trial_days_both_normal'] for r in v) for k, v in arms.items()},
                       **{k + '_dates': join(r['trial_day'] for r in v) for k, v in arms.items()}})
    return windows, counts


def main():
    calendar = get_tariffs()
    groups = defaultdict(list)
    for stamp in calendar:
        groups[trial_day(stamp)].append(stamp)
    cm_rows = cm_evidence(calendar, groups)
    days, patterns = classify(calendar, groups, cm_rows)
    windows, cells = comparison(calendar, days, patterns)
    write_csv('trial_days.csv', list(days.values()))
    write_csv('cm_schedule_check.csv', cm_rows)
    write_csv('candidate_windows.csv', windows)
    write_csv('comparison_cells.csv', cells)
    clock_labels = [{'raw_stamp': s.isoformat(), 'status': nominal_status(s), 'raw_tariff': calendar[s][1]}
                    for s in calendar if s.date().isoformat() in ('2013-03-31', '2013-10-27') and nominal_status(s) != 'unique']
    write_csv('clock_transition_conflicts.csv', clock_labels)
    summary = {'raw_rows': len(calendar), 'raw_categories': Counter(x[1] for x in calendar.values()),
               'trial_days': Counter(row['classification'] for row in days.values()),
               'cm_plan_match_counts_by_timestamp_hypothesis': {k: sum(row[k] for row in cm_rows)
                                                               for k in ('local_start', 'local_end', 'gmt_start', 'gmt_end')},
               'sf_design_type_counts': {f'{kind}_{length // 2}h_{hour:02d}': len(entries)
                                         for (kind, length, hour), entries in sorted(patterns.items())},
               'window_rows': Counter(row['arm_raw'] for row in windows),
               'unique_normal_trial_days': len({r['trial_day'] for r in windows if r['arm_raw'] == 'Normal'}),
               'candidate_cells': len(cells), 'three_arm_cells': sum(all(row[k] for k in ('High', 'Low', 'Normal')) for row in cells),
               'three_arm_cells_with_adjacent_normal': sum(all(row[k + '_adjacent_normal'] for k in ('High', 'Low', 'Normal')) for row in cells),
               'candidate_normal_window_reuse': 'A normal trial day may supply multiple distinct windows. Counts are not independent events.',
               'original_hashes': {p.name: {'bytes': p.stat().st_size, 'sha256': sha256(p.read_bytes()).hexdigest()}
                                   for p in sorted((BASE / 'original').iterdir()) if p.is_file()},
               'meter_outcome_files_opened': 0, 'models_or_effect_scores': 0}
    with (BASE / 'calendar_audit.json').open('x', encoding='utf-8') as out:
        json.dump(summary, out, indent=2)
        out.write('\n')


if __name__ == '__main__':
    main()
