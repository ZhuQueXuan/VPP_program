"""Independent chunk counts and native mode/SOC context; no models or shifts."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent
p = json.loads((BASE / 'apr2023_lmo1_field_protocol_v1.json').read_text(encoding='utf-8'))
csv_path = BASE / p['csv_relative_path']
output = BASE / 'apr2023_audit_runs' / 'QA_APR_LMO1_20261013_02'
output.mkdir(parents=True, exist_ok=False)
counts = dict(rows=0, zero_soc=0, zero_soc_stop=0, zero_soc_other_mode=0,
              stop_nonzero_soc=0, no_mode=0, active_ac_zero_current=0, sign_mismatch=0)
for c in pd.read_csv(csv_path, sep=';', chunksize=100000):
    zero, stop = c.SOC.eq(0), c.Mode_Stop.eq(1)
    mode = c[['Mode_PQ', 'Mode_Stop', 'Mode_Silent', 'Mode_Wait']].sum(axis=1)
    counts['rows'] += len(c)
    counts['zero_soc'] += int(zero.sum())
    counts['zero_soc_stop'] += int((zero & stop).sum())
    counts['zero_soc_other_mode'] += int((zero & ~stop).sum())
    counts['stop_nonzero_soc'] += int((stop & ~zero).sum())
    counts['no_mode'] += int(mode.eq(0).sum())
    counts['active_ac_zero_current'] += int((c.P_AC.abs().gt(50) & c.I_DC_Batt.eq(0)).sum())
    # Voltage is positive throughout, so current sign independently checks P_DC sign.
    counts['sign_mismatch'] += int(((c.P_AC * c.I_DC_Batt < 0) & c.P_AC.abs().gt(50)).sum())
f = pd.read_csv(csv_path, sep=';')
soc = f.SOC.astype(float) / 10
jump = soc.diff().abs() > 1 + 1e-8
zero_boundary = soc.eq(0) | soc.shift().eq(0)
indices = np.flatnonzero(jump.to_numpy())
largest = int(soc.diff().abs().idxmax())
context = f.iloc[max(0, largest - 2):largest + 3].copy()
context['soc_pct'] = soc.loc[context.index]
context.to_csv(output / 'largest_soc_jump_native_context.csv', index=False)
nomode = f[['Mode_PQ', 'Mode_Stop', 'Mode_Silent', 'Mode_Wait']].sum(axis=1).eq(0)
f[nomode].to_csv(output / 'no_mode_native_rows.csv', index=False)
zero = soc.eq(0).to_numpy()
edges = np.diff(np.r_[False, zero, False].astype(int))
starts, ends = np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)
episodes = [{'start': str(f.DateAndTime.iloc[a]), 'end': str(f.DateAndTime.iloc[b-1]),
             'duration_seconds': int(b-a)} for a, b in zip(starts, ends)]
first = json.loads((BASE / 'apr2023_audit_runs/QA_APR_LMO1_20261013_01/audit_receipt.json').read_text(encoding='utf-8'))
checks = {
    'rows': counts['rows'] == first['rows'],
    'zero_soc': counts['zero_soc'] == first['raw_soc_zero_rows'],
    'active_ac_zero_current': counts['active_ac_zero_current'] == first['active_ac_but_zero_native_current_rows'],
    'sign_mismatch': counts['sign_mismatch'] == first['raw_active_ac_dc_sign_mismatch_rows'],
    'soc_jumps': len(indices) == first['soc_jumps_gt_1pp'],
}
if not all(checks.values()):
    raise ValueError('Independent counts differ')
receipt = {
    'run_id': output.name, 'purpose': 'native contextual diagnostics and independent counts, not model validation',
    'counts': counts, 'independent_count_checks': checks,
    'soc_jumps_gt_1pp': len(indices),
    'soc_jumps_touching_zero': int((jump & zero_boundary).sum()),
    'soc_jumps_not_touching_zero': int((jump & ~zero_boundary).sum()),
    'largest_jump_pp': float(soc.diff().abs().max()),
    'largest_jump_time': str(f.DateAndTime.iloc[largest]),
    'largest_jump_from_pct': float(soc.iloc[largest-1]),
    'largest_jump_to_pct': float(soc.iloc[largest]),
    'zero_soc_episodes': episodes,
    'source_csv_sha256': hashlib.sha256(csv_path.read_bytes()).hexdigest(),
    'code_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'limits': 'Mode_Stop coincidence does not establish a fault mechanism; counts are rows, not independent events. No deletion, fitting, lag correction or source edits.'
}
(output / 'audit_receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(receipt, ensure_ascii=False, indent=2))
