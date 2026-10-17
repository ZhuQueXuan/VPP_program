"""Independent observed-run reconstruction for a frozen phase feature sidecar."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

import numpy as np
import pandas as pd

BASE=Path(__file__).resolve().parent
MODE=['Mode_PQ','Mode_Stop','Mode_Silent','Mode_Wait']


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def verify(run_id,verification_id):
    if any(not re.fullmatch(r'[A-Za-z0-9_-]+',v) for v in [run_id,verification_id]):raise ValueError('Invalid ID')
    run=BASE/'apr2023_response_phase_sample_runs'/run_id
    output=run/(verification_id+'.json')
    if output.exists():raise FileExistsError(output)
    receipt=json.loads((run/'validation_receipt.json').read_text(encoding='utf-8'))
    if any(sha(run/name)!=value for name,value in receipt['output_sha256'].items()):raise ValueError('Feature artifact changed')
    p=json.loads((run/'phase_sample_protocol_snapshot.json').read_text(encoding='utf-8'))
    parent=json.loads((run/'parent_sample_protocol_snapshot.json').read_text(encoding='utf-8'))
    source=json.loads((BASE/parent['source_field_protocol']).read_text(encoding='utf-8'))
    raw_path=BASE/source['csv_relative_path']
    if sha(raw_path)!=source['csv_sha256']:raise ValueError('Source changed')
    f=pd.read_csv(raw_path,sep=';',usecols=['DateAndTime',*MODE,'interpolated'])
    clock=pd.to_datetime(f.DateAndTime)
    arrays=[]
    for block in parent['partitions']:
        lo=clock.searchsorted(pd.Timestamp(block['start_inclusive']))
        hi=clock.searchsorted(pd.Timestamp(block['end_exclusive']))
        flags=f[MODE].iloc[lo:hi].to_numpy()
        known=np.isin(flags,[0,1]).all(axis=1)&(flags.sum(axis=1)==1)&f.interpolated.iloc[lo:hi].eq(0).to_numpy()
        q=known&(flags[:,0]==1)
        nonq=known&~q
        n=hi-lo
        phase=np.where(nonq,'non_pq','mode_unknown').astype(object)
        lower=np.full(n,np.nan);exact=np.full(n,np.nan);censored=np.zeros(n,dtype=bool)
        prefix=np.arange(lo,hi)
        # Reconstruct each contiguous observed run, without importing preparation code.
        indices=np.flatnonzero(q)
        segments=np.split(indices,np.flatnonzero(np.diff(indices)>1)+1) if len(indices) else []
        for seq in segments:
            start=int(seq[0]);confirmed=start>0 and bool(nonq[start-1])
            age=np.arange(len(seq));lower[seq]=age
            censored[seq]=not confirmed
            prefix[seq]=lo+max(0,start-1)
            phase[seq]='pq_sustained_observed'
            if confirmed:
                exact[seq]=age
                phase[seq[0]]='pq_first'
                if len(seq)>1:phase[seq[1]]='pq_second'
            else:
                phase[seq[:2]]='pq_start_unknown'
        native=np.arange(lo+1,hi-1)
        expected=pd.DataFrame({'sample_id':['APR2023_LMO1_'+str(v) for v in native],
                               'native_origin_row':native,'partition':block['name'],
                               'phase_state':phase[1:-1],'observed_pq_age_lower_bound_s':lower[1:-1],
                               'exact_pq_age_s':exact[1:-1],'pq_age_left_censored':censored[1:-1],
                               'phase_history_start_native_row':prefix[1:-1]})
        if (prefix[1:-1]<lo).any() or (prefix[1:-1]>native).any():raise ValueError('Prefix boundary violation')
        arrays.append(expected)
    expected=pd.concat(arrays,ignore_index=True)
    offset=0
    for chunk in pd.read_csv(run/'phase_features.csv.gz',chunksize=100000):
        e=expected.iloc[offset:offset+len(chunk)]
        for name in expected.columns:
            actual=chunk[name].to_numpy();wanted=e[name].to_numpy()
            same=np.array_equal(actual,wanted,equal_nan=True) if name in ['exact_pq_age_s','observed_pq_age_lower_bound_s'] else np.array_equal(actual,wanted)
            if not same:raise ValueError('Independent feature differs: '+name)
        if any(name in chunk.columns for name in ['ac_tp1_kw','future_setpoint','set_changed_next_second','mode_changed_next_second']):
            raise ValueError('Future column in feature table')
        offset+=len(chunk)
    if offset!=len(expected) or offset!=receipt['samples']:raise ValueError('Feature count differs')
    parent_run=BASE/'apr2023_response_sample_runs'/p['parent_sample_run']
    if any(sha(parent_run/name)!=value for name,value in receipt['parent_artifact_sha256'].items()):
        raise ValueError('Immutable parent artifact changed')
    first=BASE/'apr2023_response_phase_sample_runs/PREP_PHASE_APR_20261013_01/phase_features.csv.gz'
    feature_values_same=sha(first)==sha(run/'phase_features.csv.gz') if first.exists() else None
    result={'verification_id':verification_id,'feature_run':run_id,'status':'all_phase_features_independently_reconstructed',
            'features_verified':offset,'same_parent_samples_split_and_order':True,'within_partition_prefixes':True,
            'phase_age_censoring_provenance_match_native':True,'parent_artifacts_unchanged':True,
            'initial_metadata_revision_feature_bytes_identical':feature_values_same,
            'source_csv_sha256':source['csv_sha256'],'verification_code_sha256':sha(Path(__file__)),
            'limits':'observed April data had no PQ-start censoring; censoring/future invariance tested with synthetic boundary fixtures, not proven as device timing; no model fitted'}
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (run/(verification_id+'_code_snapshot.py')).write_bytes(Path(__file__).read_bytes())
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--feature-run',required=True)
    parser.add_argument('--verification-id',required=True)
    args=parser.parse_args()
    verify(args.feature_run,args.verification_id)
