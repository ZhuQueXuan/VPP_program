"""Diagnose frozen test-near records without predicting or reconstructing capacity."""
from pathlib import Path
import argparse
import collections
import hashlib
import json
import statistics
import sys
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
pa = argparse.ArgumentParser()
pa.add_argument('--run-id', required=True)
args = pa.parse_args()
if not args.run_id.isidentifier():
    raise ValueError('simple unique ID required')
OUT = ROOT / 'downloads/rwth_home_test_record_diagnostic_20261014' / args.run_id
if OUT.exists():
    raise FileExistsError(OUT)
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
protocol_path = ROOT / 'home_test_record_diagnostic_protocol_v1.json'
p = json.loads(protocol_path.read_text('utf-8'))
source = ROOT / p['source']['path']
if sha(source) != p['source']['sha256']:
    raise ValueError('source fingerprint mismatch')
start, end, test = map(pd.Timestamp, [p['window_start_inclusive'], p['window_end_exclusive'], p['test_start_native']])
pieces = []
for chunk in pd.read_csv(source, chunksize=100000):
    t = pd.to_datetime(chunk['Time'], format='%d-%b-%Y %H:%M:%S')
    mask = (t >= start) & (t < end)
    if mask.any():
        pieces.append(chunk.loc[mask].assign(native_time=t[mask]))
f = pd.concat(pieces, ignore_index=True)
if not f['native_time'].is_monotonic_increasing or f['native_time'].duplicated().any():
    raise ValueError('duplicate or out-of-order timestamps; not safe to infer blocks')
columns = ['P_in_W', 'V_in_V', 'I_in_A', 'T_Bat_in_C', 'T_Room_in_C']
finite = np.isfinite(f[columns].to_numpy()).all(axis=1)
legal = f['Interpolated'].isin([0, 1]).to_numpy()
f['record_valid'] = finite & legal
f['UI_reconstructed_W'] = f['V_in_V'] * f['I_in_A']
f['P_minus_UI_W'] = f['P_in_W'] - f['UI_reconstructed_W']
f['block_id'] = (f['native_time'].diff().dt.total_seconds().ne(1).cumsum() - 1).astype(int)
f['state'] = np.select([~f['record_valid'], f['I_in_A'].abs() <= .15, f['I_in_A'] > .15], ['invalid', 'rest', 'charge'], default='discharge')

def changes(x, column, measured_only):
    intervals = []
    changed = held = 0
    previous_time = previous_value = previous_change = None
    for row in x.itertuples(index=False):
        at = row.native_time
        ok = row.record_valid and (not measured_only or row.Interpolated == 0)
        value = getattr(row, column)
        if not ok:
            previous_time = previous_value = previous_change = None
            continue
        if previous_time is not None and (at - previous_time).total_seconds() == 1:
            if value != previous_value:
                changed += 1
                if previous_change is not None:
                    intervals.append((at - previous_change).total_seconds())
                previous_change = at
            else:
                held += 1
        else:
            previous_change = None
        previous_time, previous_value = at, value
    return {'changed_adjacent_rows': changed, 'held_adjacent_rows': held,
            'median_seconds_between_changes': statistics.median(intervals) if intervals else None,
            'change_interval_counts_seconds': dict(sorted(collections.Counter(intervals).items()))}

def scope_stats(x):
    def quality_stats(measured_only):
        mask = x['record_valid'] & (x['Interpolated'].eq(0) if measured_only else True)
        q = x.loc[mask]
        z = q.loc[q['I_in_A'].eq(0) & q['P_in_W'].ne(0)]
        return {'rows': len(q), 'zero_I_nonzero_P_rows': len(z),
                'max_abs_P_when_I_zero_W': float(z['P_in_W'].abs().max()) if len(z) else None,
                'P_minus_UI_mean_abs_W': float(q['P_minus_UI_W'].abs().mean()) if len(q) else None,
                'P_minus_UI_max_abs_W': float(q['P_minus_UI_W'].abs().max()) if len(q) else None,
                'ranges': {c: [float(q[c].min()), float(q[c].max())] for c in columns} if len(q) else {},
                'channel_changes': {c: changes(x, c, measured_only) for c in ['V_in_V', 'I_in_A', 'P_in_W']}}
    return {'rows': len(x), 'first': str(x['native_time'].iloc[0]) if len(x) else None,
            'last': str(x['native_time'].iloc[-1]) if len(x) else None,
            'interpolated_rows': int(x['Interpolated'].eq(1).sum()), 'invalid_rows': int((~x['record_valid']).sum()),
            'all_valid_records': quality_stats(False), 'noninterpolated_valid_records': quality_stats(True)}

blocks, gaps = [], []
cursor = start
for bid, x in f.groupby('block_id', sort=False):
    a, b = x['native_time'].iloc[0], x['native_time'].iloc[-1] + pd.Timedelta(seconds=1)
    if a > cursor:
        gaps.append({'start': str(cursor), 'end_exclusive': str(a), 'missing_seconds': int((a - cursor).total_seconds())})
    blocks.append({'block_id': int(bid), 'start': str(a), 'end_exclusive': str(b), 'rows': len(x),
                   'interpolated_rows': int(x['Interpolated'].eq(1).sum()), 'contains_test_start': bool(a <= test < b)})
    cursor = b
if cursor < end:
    gaps.append({'start': str(cursor), 'end_exclusive': str(end), 'missing_seconds': int((end - cursor).total_seconds())})

boundary = f['block_id'].ne(f['block_id'].shift()) | f['state'].ne(f['state'].shift()) | f['Interpolated'].ne(f['Interpolated'].shift())
runs = []
for rid, x in f.groupby(boundary.cumsum(), sort=False):
    j = int(x.index[0])
    onset_seen = j > 0 and f.loc[j-1, 'block_id'] == x['block_id'].iloc[0] and f.loc[j-1, 'Interpolated'] == x['Interpolated'].iloc[0] and f.loc[j-1, 'record_valid'] and x['record_valid'].iloc[0]
    runs.append({'run_id': int(rid), 'block_id': int(x['block_id'].iloc[0]), 'state': x['state'].iloc[0],
                 'interpolated': int(x['Interpolated'].iloc[0]), 'start': str(x['native_time'].iloc[0]),
                 'end_exclusive': str(x['native_time'].iloc[-1] + pd.Timedelta(seconds=1)), 'rows': len(x),
                 'state_onset_observed': bool(onset_seen), 'U_first_V': float(x['V_in_V'].iloc[0]), 'U_last_V': float(x['V_in_V'].iloc[-1]),
                 'I_min_A': float(x['I_in_A'].min()), 'I_max_A': float(x['I_in_A'].max())})

context = f.loc[(f['native_time'] >= test-pd.Timedelta(seconds=5)) & (f['native_time'] <= test+pd.Timedelta(seconds=5))]
summary = {'protocol_id': p['protocol_id'], 'protocol_sha256': sha(protocol_path),
           'window': [str(start), str(end)], 'expected_seconds': int((end-start).total_seconds()),
           'observed_rows': len(f), 'missing_seconds': sum(g['missing_seconds'] for g in gaps),
           'blocks': blocks, 'gaps': gaps, 'test_start_row_count': int(f['native_time'].eq(test).sum()),
           'test_start_rows': f.loc[f['native_time'].eq(test), p['fields']].to_dict('records'),
           'scopes': {'whole_window': scope_stats(f), 'before_test_index': scope_stats(f.loc[f['native_time'] < test]),
                      'at_or_after_test_index': scope_stats(f.loc[f['native_time'] >= test])},
           'current_state_runs': len(runs), 'no_capacity_integral_or_prediction': True,
           'interpretation': 'observed value holds and channel disagreement only; no inferred sampling rate, channel lag, clock multiplier, test end or physical SOC endpoints'}
OUT.mkdir()
f.to_csv(OUT/'raw_window_and_derived.csv', index=False)
pd.DataFrame(blocks).to_csv(OUT/'continuous_blocks.csv', index=False)
pd.DataFrame(gaps, columns=['start','end_exclusive','missing_seconds']).to_csv(OUT/'gaps.csv', index=False)
pd.DataFrame(runs).to_csv(OUT/'current_state_runs.csv', index=False)
context.to_csv(OUT/'test_start_context.csv', index=False)
(OUT/'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
(OUT/'receipt.json').write_text(json.dumps({'run_id': args.run_id, 'protocol_sha256': sha(protocol_path),
    'source': p['source'], 'code_sha256': sha(Path(__file__)), 'python': sys.version, 'pandas': pd.__version__,
    'artifacts': {q.name: sha(q) for q in OUT.iterdir() if q.is_file()}}, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'run_id':args.run_id,'rows':len(f),'missing_seconds':summary['missing_seconds'],
                  'blocks':len(blocks),'interpolated_rows':summary['scopes']['whole_window']['interpolated_rows'],
                  'test_start_rows':summary['test_start_rows'],
                  'measured_only':{k:{a:b for a,b in v['noninterpolated_valid_records'].items() if a!='ranges'} for k,v in summary['scopes'].items()}}, ensure_ascii=False))
