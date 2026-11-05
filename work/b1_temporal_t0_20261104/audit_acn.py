"""Select one control sequence per ACN development session and export native points."""
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = ROOT / 'data/ACN_real_user_benchmark_v1_20261102'
META = ROOT / 'work/b1_real_training_data_20261102/source_documents/acn_official_Caltech_2020.json'
COLUMNS = ['Unnamed: 0', 'Actual Pilot (A)', 'Charging Current (A)', 'Power (kW)']
ROLES = ('training', 'validation')
STRATA = ('complete_return_window', 'complete_multistep', 'complete_single', 'incomplete')


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path, data):
    with path.open('x', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, allow_nan=False, indent=2)
        f.write('\n')


def hash_bytes(raw):
    return hashlib.sha256(raw).hexdigest()


def load_trace(entry):
    path = ROOT / entry['local']
    frame = pd.read_csv(path, usecols=COLUMNS)
    utc = pd.to_datetime(frame[COLUMNS[0]], format='mixed', utc=True, errors='coerce')
    x = frame[COLUMNS[1:]].apply(pd.to_numeric, errors='coerce').to_numpy()
    return utc, utc.astype('int64').to_numpy() / 1e9, x


def coverage(t, x, left, right, disconnect):
    inside = (t >= left) & (t <= right)
    sample = t[inside]
    gaps = np.diff(sample)
    edges = [float(sample[0] - left), float(right - sample[-1])] if len(sample) else []
    max_gap = float(max([*edges, *gaps], default=0)) if len(sample) else None
    issues = []
    if t[0] > left or t[-1] < right or disconnect < right:
        issues.append('time_or_session_boundary')
    if len(sample) < 2:
        issues.append('too_few_points')
    if max_gap is not None and max_gap > 12:
        issues.append('gap_over_12s')
    if (gaps == 0).any():
        issues.append('duplicate_timestamp')
    if not np.isfinite(x[inside]).all():
        issues.append('missing_core_channel')
    return {'points': int(inside.sum()), 'max_gap_s': max_gap, 'issues': issues}


def scan(entry, disconnect):
    utc, t, x = load_trace(entry)
    if not len(t) or utc.isna().any() or (np.diff(t) < 0).any():
        return {'status': 'unusable_time'}
    pilot = x[:, 0]
    gap = np.diff(t)
    step = np.diff(pilot)
    bracketed = (gap > 0) & (gap <= 12) & np.isfinite(step)
    drops = np.flatnonzero(bracketed & (step <= -2)) + 1
    eligible = drops[(t[drops] - t[0] >= 60) & (t[drops] < disconnect)]
    if not len(eligible):
        return {'status': 'no_eligible_anchor', 'bracketed_drop_count': len(drops)}
    i = int(eligible[0]); start = t[i]; end = start + 1800
    subsequent = np.flatnonzero(bracketed & (np.abs(step) > .25)) + 1
    subsequent = subsequent[(t[subsequent] > start) & (t[subsequent] <= min(end, disconnect))]
    returns = [int(j) for j in subsequent if step[j - 1] >= 2 and abs(pilot[j] - pilot[i - 1]) <= .25]
    core = coverage(t, x, start - 60, end, disconnect)
    release = None
    if returns:
        j = returns[0]; release_end = min(t[j] + 300, start + 2100)
        post = coverage(t, x, t[j], release_end, disconnect)
        after = pilot[(t >= t[j]) & (t <= release_end)]
        changed = bool((np.abs(after - pilot[j]) > .25).any())
        release = {'raw_row': j + 2, 'relative_s': float(t[j] - start),
                   'end_relative_s': float(release_end - start), 'post': post, 'new_limit_change': changed,
                   'usable': not post['issues'] and not changed}
    stratum = ('incomplete' if core['issues'] else 'complete_return_window' if release and release['usable']
               else 'complete_multistep' if len(subsequent) else 'complete_single')
    return {'status': 'anchor_selected', 'stratum': stratum, 'bracketed_drop_count': len(drops),
            'raw_row': i + 2, 'anchor_utc': utc.iloc[i].isoformat(), 'start_seconds': float(start),
            'disconnect_seconds': float(disconnect),
            'old_limit_A': float(pilot[i - 1]), 'new_limit_A': float(pilot[i]),
            'subsequent_change_count': len(subsequent),
            'subsequent_changes': [{'raw_row': int(j) + 2, 'relative_s': float(t[j] - start),
                                    'old_A': float(pilot[j-1]), 'new_A': float(pilot[j])}
                                   for j in subsequent],
            'core': core, 'release': release}


def export_pack(entries, ledger):
    output = HERE / 'blind_source_points'
    output.mkdir(exist_ok=False)
    selected = []
    seen = set()
    for role in ROLES:
        for stratum in STRATA:
            group = [row for row in ledger if row['role'] == role and row.get('stratum') == stratum]
            group.sort(key=lambda row: hash_bytes(('b1-t0-20261104|' + row['session']).encode()))
            count = 0
            for row in group:
                if row['user'] in seen:
                    continue
                case = f'ACN{len(selected) + 1:02d}'
                utc, t, x = load_trace(entries[row['session']])
                elapsed = t - row['start_seconds']
                stop = max(1800, row['release']['end_relative_s']) if row['release'] else 1800
                in_range = np.flatnonzero((elapsed >= -60) & (elapsed <= stop) & (t <= row['disconnect_seconds']))
                with (output / (case + '.csv')).open('x', encoding='utf-8', newline='') as stream:
                    writer = csv.writer(stream)
                    writer.writerow(['source_row', 'time_utc', 'relative_s', 'limit_A', 'current_A', 'power_kW'])
                    for i in in_range:
                        writer.writerow([i + 2, utc.iloc[i].isoformat(), elapsed[i],
                                         *[v if np.isfinite(v) else '' for v in x[i]]])
                selected.append({'case': case, 'session': row['session'], 'user': row['user'],
                                 'role': role, 'stratum': stratum, 'native_points': len(in_range)})
                seen.add(row['user'])
                count += 1
                if count == 3:
                    break
    return selected


def main():
    disconnects = {row['sessionID']: pd.Timestamp(row['disconnectTime']).timestamp()
                   for row in read_json(META)['_items']}
    entries, ledger, hashes = {}, [], {}
    for role in ROLES:
        manifest = DATA / f'{role}_sessions.json'
        hashes[role] = hash_bytes(manifest.read_bytes())
        for entry in read_json(manifest):
            session = entry['session_id']
            assert entry['split'] == role and entry['site'] == 'caltech' and session not in entries
            entries[session] = entry
            try:
                result = scan(entry, disconnects[session])
            except (OSError, EOFError, ValueError) as exc:
                result = {'status': 'unreadable_source', 'error_type': type(exc).__name__}
            ledger.append({'session': session, 'user': entry['user_group'], 'role': role,
                           'source': entry['local'], **result})
    assert len(ledger) == 1423
    write_json(HERE / 'acn_control_ledger.json', ledger)
    selected = export_pack(entries, ledger)
    write_json(HERE / 'acn_review_registry.json', selected)
    write_json(HERE / 'receipt.json', {'protocol_sha256': hash_bytes((HERE / 'protocol.md').read_bytes()),
                                      'audit_code_sha256': hash_bytes(Path(__file__).read_bytes()),
                                      'development_manifest_sha256': hashes, 'sessions': len(ledger),
                                      'users': len({r['user'] for r in ledger}),
                                      'statuses': Counter(r['status'] for r in ledger),
                                      'strata': Counter(r['stratum'] for r in ledger if 'stratum' in r),
                                      'return_candidates': sum(bool(r.get('release')) for r in ledger),
                                      'return_windows_usable': sum(bool((r.get('release') or {}).get('usable')) for r in ledger),
                                      'blind_records': len(selected), 'models': 0})


if __name__ == '__main__':
    main()
