"""Independently compare prepared samples with native rows and repeated outputs."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def verify(first_id, repeat_id, verification_id):
    if any(not re.fullmatch(r'[A-Za-z0-9_-]+',x) for x in [first_id,repeat_id,verification_id]):
        raise ValueError('Invalid ID')
    runs=BASE/'apr2023_response_sample_runs'
    output=runs/(verification_id+'.json')
    if output.exists():
        raise FileExistsError(output)
    first, repeat=runs/first_id, runs/repeat_id
    a=json.loads((first/'validation_receipt.json').read_text(encoding='utf-8'))
    b=json.loads((repeat/'validation_receipt.json').read_text(encoding='utf-8'))
    file_checks={name:sha(first/name)==sha(repeat/name)==value==b['output_sha256'][name]
                 for name,value in a['output_sha256'].items()}
    if not all(file_checks.values()):
        raise ValueError('Repeated artifacts differ')
    p=json.loads((first/'sample_protocol_snapshot.json').read_text(encoding='utf-8'))
    src=json.loads((first/'source_field_protocol_snapshot.json').read_text(encoding='utf-8'))
    raw_path=BASE/src['csv_relative_path']
    if sha(raw_path)!=src['csv_sha256']:
        raise ValueError('Native source fingerprint changed')
    f=pd.read_csv(raw_path,sep=';')
    times=pd.to_datetime(f.DateAndTime)
    arrays={name:f[name].to_numpy() for name in f.columns}
    expected_rows=[]
    part_name=np.full(len(f),'outside',dtype=object)
    raw_support=[]
    for block in p['partitions']:
        start=int(times.searchsorted(pd.Timestamp(block['start_inclusive'])))
        end=int(times.searchsorted(pd.Timestamp(block['end_exclusive'])))
        raw_support.append((start,end))
        part_name[start:end]=block['name']
        # Independent interval construction. No prepared selection function imported.
        expected_rows.append(np.arange(start+1,end-1))
    expected=np.concatenate(expected_rows)
    if any(max(raw_support[i][0],raw_support[j][0])<min(raw_support[i][1],raw_support[j][1])
           for i in range(len(raw_support)) for j in range(i)):
        raise ValueError('Partition raw supports overlap')
    modes=['Mode_PQ','Mode_Stop','Mode_Silent','Mode_Wait']
    if not np.isfinite(f[['P_AC','P_AC_Set']].to_numpy()).all() or not f.interpolated.eq(0).all():
        raise ValueError('Independent interval count requires complete unflagged source; revise verifier otherwise')
    if not f[modes].isin([0,1]).all().all():
        raise ValueError('Invalid mode encoding')
    mapping={'ac_t_kw':('P_AC',0),'set_t_kw':('P_AC_Set',0),
             'ac_tm1_kw':('P_AC',-1),'set_tm1_kw':('P_AC_Set',-1),
             'mode_pq_t':('Mode_PQ',0),'mode_stop_t':('Mode_Stop',0),
             'mode_silent_t':('Mode_Silent',0),'mode_wait_t':('Mode_Wait',0)}
    offset=0
    unknown_modes=0
    inputs_iter=pd.read_csv(first/'inputs.csv.gz',chunksize=100000)
    labels_iter=pd.read_csv(first/'labels.csv.gz',chunksize=100000)
    for x,y in zip(inputs_iter,labels_iter,strict=True):
        i=x.native_origin_row.to_numpy()
        if not np.array_equal(i,expected[offset:offset+len(x)]):
            raise ValueError('Eligibility/order differs from native interval calculation')
        expected_ids=np.array(['APR2023_LMO1_'+str(v) for v in i],dtype=object)
        if not np.array_equal(x.sample_id.to_numpy(),expected_ids) or not x.sample_id.equals(y.sample_id):
            raise ValueError('Sample/target keys differ')
        if not np.array_equal(x.origin_time_utc_declared,arrays['DateAndTime'][i]):
            raise ValueError('Origin timestamp differs')
        if not np.array_equal(y.target_time_utc_declared,arrays['DateAndTime'][i+1]):
            raise ValueError('Next-second timestamp differs')
        if not np.array_equal(x.partition,part_name[i]):
            raise ValueError('Partition differs')
        for col,(native,shift) in mapping.items():
            if not np.array_equal(x[col],arrays[native][i+shift]):
                raise ValueError('Input/history differs: '+col)
        if not np.array_equal(y.ac_tp1_kw,arrays['P_AC'][i+1]):
            raise ValueError('Target is not next native AC')
        set_changed=arrays['P_AC_Set'][i+1]!=arrays['P_AC_Set'][i]
        mode_changed=np.column_stack([arrays[name][i+1]!=arrays[name][i] for name in modes]).any(axis=1)
        if not np.array_equal(y.set_changed_next_second,set_changed) or not np.array_equal(y.mode_changed_next_second,mode_changed):
            raise ValueError('Post-origin diagnostics differ')
        if any(col in x.columns for col in ['ac_tp1_kw','set_changed_next_second','mode_changed_next_second']):
            raise ValueError('Future columns present in input file')
        unknown_modes+=int(x[['mode_pq_t','mode_stop_t','mode_silent_t','mode_wait_t']].sum(axis=1).eq(0).sum())
        offset+=len(x)
    if offset!=len(expected) or offset!=a['eligible_count']:
        raise ValueError('Sample total differs')
    # Manifest streamed separately: every native row appears once, excluded set matches intervals.
    offset_manifest=0
    excluded=[]
    for c in pd.read_csv(first/'candidate_manifest.csv.gz',chunksize=100000):
        i=c.native_origin_row.to_numpy()
        if not np.array_equal(i,np.arange(offset_manifest,offset_manifest+len(c))):
            raise ValueError('Native candidate coverage differs')
        expected_eligible=np.zeros(len(c),dtype=bool)
        for start,end in raw_support:
            expected_eligible|=(i>=start+1)&(i<end-1)
        if not np.array_equal(c.paired_eligible,expected_eligible):
            raise ValueError('Candidate qualification differs')
        excluded.extend(i[~expected_eligible].tolist())
        offset_manifest+=len(c)
    if offset_manifest!=len(f):
        raise ValueError('Manifest misses native rows')
    receipt={'verification_id':verification_id,'status':'all_samples_independently_verified_not_model_validation',
             'first_run':first_id,'repeat_run':repeat_id,'sample_count':offset,
             'excluded_native_origins':excluded,'unknown_mode_samples_retained':unknown_modes,
             'partition_raw_supports_nonoverlapping':True,'all_input_history_target_rows_match_native':True,
             'future_diagnostics_separate_from_inputs':True,'repeat_artifact_checks':file_checks,
             'source_csv_sha256':src['csv_sha256'],'verification_code_sha256':sha(Path(__file__)),
             'limits':'record-time availability assumed; correlated within-partition seconds; no real receipt timing or capacity claim'}
    output.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(receipt,ensure_ascii=False,indent=2))


if __name__=='__main__':
    if hasattr(sys.stdout,'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--first-run',required=True)
    parser.add_argument('--repeat-run',required=True)
    parser.add_argument('--verification-id',required=True)
    args=parser.parse_args()
    verify(args.first_run,args.repeat_run,args.verification_id)
