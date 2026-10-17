"""Prepare frozen log-time response samples, separating inputs from future labels."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent
MODE = ['Mode_PQ', 'Mode_Stop', 'Mode_Silent', 'Mode_Wait']


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def construct(f, p):
    time = pd.to_datetime(f.DateAndTime, errors='raise')
    if not time.is_unique or not time.diff().iloc[1:].eq(pd.Timedelta(seconds=1)).all():
        raise ValueError('Clock must be unique and continuous, no gap filling')
    n = len(f)
    part = np.full(n, 'outside', dtype=object)
    for block in p['partitions']:
        part[(time >= block['start_inclusive']) & (time < block['end_exclusive'])] = block['name']
    previous = np.maximum(np.arange(n)-1, 0)
    following = np.minimum(np.arange(n)+1, n-1)
    finite_input = np.isfinite(f[['P_AC', 'P_AC_Set']].to_numpy()).all(axis=1)
    finite_target = np.isfinite(f.P_AC.to_numpy())
    known_flags = f[MODE].isin([0, 1]).all(axis=1).to_numpy()
    valid_input_row = finite_input & known_flags & f.interpolated.eq(0).to_numpy()
    origin_valid = valid_input_row & valid_input_row[previous]
    origin_valid[0] = False
    target_valid = finite_target[following] & f.interpolated.to_numpy()[following].__eq__(0)
    target_valid[-1] = False
    same_partition = (part == part[previous]) & (part == part[following]) & (part != 'outside')
    good = origin_valid & target_valid & same_partition
    reason = np.select([np.arange(n)==0, np.arange(n)==n-1, ~same_partition, ~origin_valid, ~target_valid],
                       ['no_history', 'no_target', 'partition_boundary', 'invalid_input', 'invalid_target'], default='')
    manifest = pd.DataFrame({'native_origin_row': np.arange(n), 'origin_time_utc_declared': f.DateAndTime,
                             'partition': part, 'origin_input_valid': origin_valid,
                             'paired_eligible': good, 'exclusion_reason': reason})
    i = np.flatnonzero(good)
    ids = 'APR2023_LMO1_' + pd.Series(i).astype(str)
    inputs = pd.DataFrame({'sample_id': ids, 'native_origin_row': i,
                           'origin_time_utc_declared': f.DateAndTime.iloc[i].to_numpy(),
                           'partition': part[i], 'ac_t_kw': f.P_AC.iloc[i].to_numpy(),
                           'set_t_kw': f.P_AC_Set.iloc[i].to_numpy(),
                           'ac_tm1_kw': f.P_AC.iloc[i-1].to_numpy(),
                           'set_tm1_kw': f.P_AC_Set.iloc[i-1].to_numpy()})
    for col, source in zip(p['input_columns'][2:], MODE):
        inputs[col] = f[source].iloc[i].to_numpy()
    labels = pd.DataFrame({'sample_id': ids,
                           'target_time_utc_declared': f.DateAndTime.iloc[i+1].to_numpy(),
                           'ac_tp1_kw': f.P_AC.iloc[i+1].to_numpy(),
                           'set_changed_next_second': f.P_AC_Set.iloc[i+1].to_numpy() != f.P_AC_Set.iloc[i].to_numpy(),
                           'mode_changed_next_second': (f[MODE].iloc[i+1].to_numpy() != f[MODE].iloc[i].to_numpy()).any(axis=1)})
    return inputs, labels, manifest


def scientific_checks(p):
    f = pd.DataFrame({'DateAndTime': pd.date_range('2023-04-01', periods=8, freq='s').strftime('%Y-%m-%d %H:%M:%S'),
                      'P_AC': [0, 10, 20, 30, 40, 50, 60, 70], 'P_AC_Set': 20,
                      'Mode_PQ': 1, 'Mode_Stop': 0, 'Mode_Silent': 0, 'Mode_Wait': 0, 'interpolated': 0})
    a, y, m = construct(f, p)
    changed = f.copy()
    changed.loc[3, ['P_AC', 'P_AC_Set', 'Mode_PQ', 'Mode_Stop']] = [-600, 600, 0, 1]
    b, z, k = construct(changed, p)
    # Native row 2 uses rows 1/2, never the mutated future row 3.
    left = a[a.native_origin_row == 2].reset_index(drop=True)
    right = b[b.native_origin_row == 2].reset_index(drop=True)
    if not left.equals(right) or not np.array_equal(m.paired_eligible, k.paired_eligible):
        raise ValueError('Future values changed input/eligibility')
    if y.ac_tp1_kw.iloc[1] == z.ac_tp1_kw.iloc[1]:
        raise ValueError('Target must refer to next native row')
    silent = f.copy()
    silent.loc[2, ['Mode_PQ', 'Mode_Silent']] = [0, 1]
    _, _, ms = construct(silent, p)
    if not bool(ms.paired_eligible.iloc[2]):
        raise ValueError('Silent origins must be retained')
    future_invalid = f.copy()
    future_invalid.loc[3, 'interpolated'] = 1
    _, _, mf = construct(future_invalid, p)
    if not bool(mf.origin_input_valid.iloc[2]) or bool(mf.paired_eligible.iloc[2]):
        raise ValueError('Target quality must not be presented as origin eligibility')
    return ['future_set_ac_mode_not_used_in_inputs_or_selection', 'next_row_target',
            'silent_origins_retained', 'origin_vs_future_label_quality_separate']


def main(run_id):
    if not re.fullmatch(r'[A-Za-z0-9_-]+', run_id):
        raise ValueError('Invalid run ID')
    output = BASE / 'apr2023_response_sample_runs' / run_id
    output.mkdir(parents=True, exist_ok=False)
    protocol_path = BASE / 'apr2023_response_sample_protocol_v1.json'
    p = json.loads(protocol_path.read_text(encoding='utf-8'))
    if (p['horizon_seconds'], p['history_seconds'], p['origin_stride_seconds']) != (1, 1, 1):
        raise ValueError('This implementation supports the frozen 1s protocol only')
    source_path = BASE / p['source_field_protocol']
    source = json.loads(source_path.read_text(encoding='utf-8'))
    csv_path = BASE / source['csv_relative_path']
    if sha(csv_path) != source['csv_sha256']:
        raise ValueError('Source fingerprint changed')
    f = pd.read_csv(csv_path, sep=';')
    if len(f) != source['rows']:
        raise ValueError('Source row count changed')
    checks = scientific_checks(p)
    inputs, labels, manifest = construct(f, p)
    counts = {}
    for block in p['partitions']:
        name = block['name']
        part = inputs.partition.eq(name)
        pq = part & inputs.mode_pq_t.eq(1)
        counts[name] = {'sample_count': int(part.sum()), 'origin_pq_count': int(pq.sum()),
                        'origin_dates': int(inputs.loc[part, 'origin_time_utc_declared'].str[:10].nunique()),
                        'pq_origin_dates': int(inputs.loc[pq, 'origin_time_utc_declared'].str[:10].nunique()),
                        'future_set_changes_retained': int(labels.loc[part, 'set_changed_next_second'].sum()),
                        'future_mode_changes_retained': int(labels.loc[part, 'mode_changed_next_second'].sum())}
    daily = inputs.groupby([inputs.origin_time_utc_declared.str[:10], 'partition']).agg(
        samples=('sample_id','size'), pq_samples=('mode_pq_t','sum'),
        stop_samples=('mode_stop_t','sum'), silent_samples=('mode_silent_t','sum'), wait_samples=('mode_wait_t','sum'))
    for filename, frame in [('inputs.csv.gz', inputs), ('labels.csv.gz', labels), ('candidate_manifest.csv.gz', manifest)]:
        frame.to_csv(output / filename, index=False, compression={'method':'gzip', 'compresslevel':1, 'mtime':0})
    daily.to_csv(output / 'daily_support.csv')
    snapshots = [('sample_protocol_snapshot.json', protocol_path), ('source_field_protocol_snapshot.json', source_path),
                 ('baseline_protocol_snapshot.json', BASE/'apr2023_response_baseline_protocol_v1.json')]
    for filename, path in snapshots:
        (output/filename).write_bytes(path.read_bytes())
    receipt = {'run_id': run_id, 'status':'samples_prepared_no_forecast_fit', 'protocol_id':p['protocol_id'],
               'split_id':p['split_id'], 'data_card_version':p['data_card_version'],
               'source_csv_sha256':source['csv_sha256'], 'code_sha256':sha(Path(__file__)),
               'sample_protocol_sha256':sha(protocol_path), 'source_field_protocol_sha256':sha(source_path),
               'baseline_protocol_sha256':sha(BASE/'apr2023_response_baseline_protocol_v1.json'),
               'candidate_count':len(manifest), 'eligible_count':len(inputs),
               'exclusions':{str(k):int(v) for k,v in manifest.loc[~manifest.paired_eligible,'exclusion_reason'].value_counts().items()},
               'partitions':counts, 'scientific_boundary_checks':checks,
               'output_sha256':{name:sha(output/name) for name in ['inputs.csv.gz','labels.csv.gz','candidate_manifest.csv.gz','daily_support.csv']+[x[0] for x in snapshots]},
               'environment':{'pandas':pd.__version__,'numpy':np.__version__},
               'limits':'one site/unit; correlated seconds; entire month quality-seen; live timing/energy/capacity not validated'}
    (output/'validation_receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(receipt,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    if hasattr(sys.stdout,'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id',required=True)
    main(parser.parse_args().run_id)
