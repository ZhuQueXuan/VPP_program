"""Audit actual APR2023 LMO1 fields/semantics. No model fitting or time correction."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import zipfile
import zlib

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent


def fingerprint(path):
    checksum = 0
    sha = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            checksum = zlib.crc32(chunk, checksum)
            sha.update(chunk)
    return sha.hexdigest(), checksum & 0xffffffff


def audit(run_id):
    if not re.fullmatch(r'[A-Za-z0-9_-]+', run_id):
        raise ValueError('Invalid run ID')
    output = BASE / 'apr2023_audit_runs' / run_id
    output.mkdir(parents=True, exist_ok=False)
    protocol_path = BASE / 'apr2023_lmo1_field_protocol_v1.json'
    p = json.loads(protocol_path.read_text(encoding='utf-8'))
    archive_path, csv_path = BASE / p['archive_relative_path'], BASE / p['csv_relative_path']
    archive_hash, _ = fingerprint(archive_path)
    csv_hash, csv_crc = fingerprint(csv_path)
    with zipfile.ZipFile(archive_path) as archive:
        member = archive.getinfo(p['member'])
    if archive_hash != p['archive_sha256'] or csv_hash != p['csv_sha256'] or csv_crc != member.CRC:
        raise ValueError('Archive/member fingerprint or CRC differs')
    f = pd.read_csv(csv_path, sep=p['separator'])
    time = pd.to_datetime(f.DateAndTime, errors='raise')
    if len(f) != p['rows'] or not time.is_unique or not time.diff().iloc[1:].eq(pd.Timedelta(seconds=1)).all():
        raise ValueError('Row count or one-second clock invalid')
    if f.isna().any().any() or not np.isfinite(f.select_dtypes('number')).all().all():
        raise ValueError('Missing/nonfinite native fields')
    normalized = f[list(p['field_multipliers'])].astype(float).mul(p['field_multipliers'])
    ac, request = normalized.P_AC, normalized.P_AC_Set
    dc = normalized.I_DC_Batt * normalized.U_DC_Batt / 1000
    soc = normalized.SOC
    flags = p['mode_flags'] + [p['quality_flag'].split('=')[0]]
    if any(not f[name].isin([0, 1]).all() for name in flags):
        raise ValueError('Unknown flag encoding')
    mode_sum = f[p['mode_flags']].sum(axis=1)
    active = (ac.abs() > 50) & (dc.abs() > 50)
    mismatch = (ac * dc < 0) & (ac.abs() > 50)
    # Retrospective AC-stable windows; DC values never select the windows.
    grouping = np.arange(len(f)) // 60
    windows = pd.DataFrame({'ac': ac, 'dc': dc, 'interpolated': f.interpolated}).groupby(grouping).agg(
        ac_min=('ac', 'min'), ac_max=('ac', 'max'), ac_mean=('ac', 'mean'), dc_mean=('dc', 'mean'),
        n=('ac', 'size'), any_interpolated=('interpolated', 'max'))
    eligible = (windows.n == 60) & ((windows.ac_min > 50) | (windows.ac_max < -50))
    eligible &= (windows.ac_max - windows.ac_min < 10) & windows.any_interpolated.eq(0)
    stable = windows[eligible]
    summaries = {}
    for direction in ['charge', 'discharge']:
        segment = stable[stable.ac_mean.lt(0) if direction == 'charge' else stable.ac_mean.gt(0)]
        efficiency = segment.dc_mean / segment.ac_mean if direction == 'charge' else segment.ac_mean / segment.dc_mean
        summaries[direction] = {'window_count': len(segment), 'median_ratio': float(efficiency.median()),
                                'fraction_ratio_in_0_to_1': float(((efficiency > 0) & (efficiency <= 1)).mean()),
                                'negative_loss_windows_retained': int((segment.dc_mean - segment.ac_mean < 0).sum()),
                                'ac_mean_abs_min_kw': float(segment.ac_mean.abs().min()), 'ac_mean_abs_max_kw': float(segment.ac_mean.abs().max())}
    jump_indices = np.flatnonzero(soc.diff().abs().to_numpy() > 1 + 1e-8)
    examples = f.loc[np.flatnonzero(mismatch.to_numpy())[:10]].copy()
    examples['dc_reconstructed_kw'] = dc.loc[examples.index]
    examples.to_csv(output / 'native_sign_mismatch_examples.csv', index=False)
    zero_soc = soc.eq(0)
    zero_current_active = normalized.I_DC_Batt.eq(0) & ac.abs().gt(50)
    receipt = {
        'run_id': run_id, 'status': 'field_and_semantic_audit_complete_not_model_experiment',
        'protocol_id': p['protocol_id'], 'source_sha256': archive_hash, 'csv_sha256': csv_hash,
        'selected_member_crc32_pass': True, 'other_members_crc_status': 'not tested; only LMO1 extracted',
        'rows': len(f), 'columns': list(f.columns), 'start': str(time.iloc[0]), 'end': str(time.iloc[-1]),
        'timezone_basis': 'publisher UTC declaration; no inferred shifts', 'missing_or_duplicate_times': 0,
        'missing_cells': 0, 'interpolated_flag_counts': {str(k): int(v) for k, v in f.interpolated.value_counts().items()},
        'normalized_ranges': {col: {'min': float(v.min()), 'max': float(v.max())} for col, v in normalized.items()},
        'mode_flag_counts': {col: {str(k): int(v) for k, v in f[col].value_counts().items()} for col in p['mode_flags']},
        'mode_sum_counts': {str(k): int(v) for k, v in mode_sum.value_counts().items()},
        'active_ac_dc_rows': int(active.sum()), 'raw_active_ac_dc_sign_mismatch_rows': int(mismatch.sum()),
        'active_ac_but_zero_native_current_rows': int(zero_current_active.sum()),
        'raw_soc_zero_rows': int(zero_soc.sum()), 'soc_zero_and_abs_ac_gt_50_rows': int((zero_soc & ac.abs().gt(50)).sum()),
        'soc_jumps_gt_1pp': len(jump_indices), 'max_soc_jump_pp': float(soc.diff().abs().max()),
        'setpoint_change_nonzero_rows': int(request.diff().fillna(0).ne(0).sum()),
        'setpoint_change_abs_ge_50kw_rows': int(request.diff().abs().ge(50).sum()),
        'same_time_request_ac_mae_kw_diagnostic': float((ac - request).abs().mean()),
        'ac_stable_60s_windows': len(stable), 'candidate_60s_windows': len(windows),
        'stable_window_diagnostic': summaries,
        'interpretation': 'ratios are descriptive reconstructed port checks, not fitted efficiency or model accuracy',
        'no_target_based_exclusion': True, 'source_or_SOC_modified': False, 'no_model_fit_or_lag_alignment': True,
        'code_sha256': fingerprint(Path(__file__))[0], 'protocol_sha256': fingerprint(protocol_path)[0],
        'environment': {'pandas': pd.__version__, 'numpy': np.__version__},
    }
    (output / 'audit_receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (output / 'field_protocol_snapshot.json').write_text(json.dumps(p, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(receipt, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', required=True)
    audit(parser.parse_args().run_id)
