"""Independently apply frozen T0 definitions to anonymous points before reading first judgments."""
import csv
import json
import math
from pathlib import Path
from statistics import median


BASE = Path(__file__).resolve().parent


def value(row, key):
    try:
        number = float(row[key])
    except ValueError:
        return None
    return number if math.isfinite(number) else None


def window(points, left, right, include_end=False):
    return [p for p in points if left <= p[0] and (p[0] < right or (include_end and p[0] == right))]


def complete(points, left, right, gap):
    return (bool(points) and points[0][0] - left <= gap and right - points[-1][0] <= gap
            and all(p[1] is not None for p in points)
            and all(0 < b[0] - a[0] <= gap for a, b in zip(points, points[1:])))


def supported(points, min_count, min_span):
    return len(points) >= min_count and points[-1][0] - points[0][0] >= min_span


def interruptions(points, gap, min_count, min_span, low, running):
    last_run = []
    state = 'break'
    sequence = []
    events = []

    def finish():
        if not supported(last_run, min_count, min_span):
            return
        sequence.append((state, last_run[0][0], last_run[-1][0]))
        if len(sequence) >= 3 and [r[0] for r in sequence[-3:]] == ['on', 'low', 'on']:
            events.append(list(sequence[-2][1:]))
            sequence[:] = sequence[-1:]

    for p in points:
        new_state = 'break' if p[1] is None else 'low' if p[1] <= low else 'on' if p[1] >= running else 'between'
        discontinuity = bool(last_run) and not 0 < p[0] - last_run[-1][0] <= gap
        if discontinuity or new_state != state or new_state == 'break':
            finish()
            if discontinuity or new_state == 'break':
                sequence.clear()
            last_run = []
        state = new_state
        last_run.append(p)
    finish()
    return events


def analyze(case, mark):
    ev = case.startswith('EV')
    gap, n, span, lo, run, change, pre, after, early = (
        (12, 3, 6, .15, .50, .30, 30, 300, 30) if ev else
        (450, 2, 240, 50, 300, 200, 1800, 21600, 1800))
    power, control = ('power_kW', 'limit_A') if ev else ('hp_p', 'intervention_dummy')
    with (BASE / 'blind_pack/points' / (case + '.csv')).open(newline='', encoding='utf-8-sig') as f:
        points = [(float(r['relative_s']), value(r, power), value(r, control)) for r in csv.DictReader(f)]
    end = mark['end_s']
    active_end = (1800 if end is None else end) if ev else end
    end_session = mark.get('session_end_s_if_in_window')
    active = window(points, 0, active_end)
    valid = (active_end > 0 and (end_session is None or end_session >= active_end)
             and complete(active, 0, active_end, gap) and supported(active, n, span))
    stops = interruptions(active, gap, n, span, lo, run)
    stop_label = ('multi' if len(stops) >= 2 else 'one' if len(stops) == 1 else 'none') if valid else ('at_least_two' if len(stops) >= 2 else 'unknown')
    thirds = [window(points, active_end * k / 3, active_end * (k + 1) / 3) for k in range(3)]
    order = 'unknown'
    mids = None
    if valid and all(complete(s, active_end * k / 3, active_end * (k + 1) / 3, gap) and supported(s, n, span)
                     for k, s in enumerate(thirds)):
        a, b, c = mids = [median(p[1] for p in third) for third in thirds]
        order = ('middle_high' if b - max(a, c) >= change else 'middle_low' if min(a, c) - b >= change else
                 'early_high' if a - c >= change else 'early_low' if c - a >= change else 'similar')

    recovery, recovery_time = 'not_applicable', None
    if end is not None and end > 0:
        recovery = 'unknown'
        pre_points = window(points, end - pre, end)
        post_points = [p for p in points if end < p[0] <= end + after]
        at_end = [p for p in points if p[0] == end]
        if ev:
            changed = (len(at_end) != 1 or at_end[0][2] is None or
                       any(p[2] is None or abs(p[2] - at_end[0][2]) > .25 for p in post_points))
        else:
            changed = (any(p[2] != 0 for p in post_points) or
                       any(end < t <= end + after for t in mark['other_intervention_start_s']))
        if (not changed and (end_session is None or end_session >= end + after)
                and complete(pre_points, end - pre, end, gap) and supported(pre_points, n, span)
                and complete(post_points, end, end + after, gap) and supported(post_points, n, span)):
            reference = median(p[1] for p in pre_points)
            recovery = 'none'
            segment = []
            for p in post_points:
                if p[1] < reference + change:
                    segment = []
                    continue
                segment.append(p)
                if supported(segment, n, span):
                    recovery_time = segment[0][0] - end
                    recovery = 'early' if recovery_time <= early else 'late'
                    break
    return {'case': case, 'resource': 'EV' if ev else 'HP', 'interruption': stop_label,
            'interruption_segments_s': stops, 'order': order, 'third_medians': mids,
            'recovery': recovery, 'recovery_time_s': recovery_time}


def main():
    marks = json.loads((BASE / 'blind_pack/control_marks.json').read_text(encoding='utf-8'))
    results = [analyze(case, marks[case]) for case in sorted(marks)]
    with (BASE / 'root_point_replay.json').open('x', encoding='utf-8') as f:
        json.dump(results, f, indent=2, allow_nan=False)
        f.write('\n')


if __name__ == '__main__':
    main()
