"""Prepare history-only phase sidecar; no power-model fitting."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

import numpy as np
import pandas as pd

BASE=Path(__file__).resolve().parent
MODES=['Mode_PQ','Mode_Stop','Mode_Silent','Mode_Wait']


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def partition_phases(frame, native_start):
    """Only supplied mode-prefix rows are inspected. No target or power columns."""
    values=frame[MODES].to_numpy()
    known=np.isfinite(values).all(axis=1)&np.isin(values,[0,1]).all(axis=1)
    known&=(values.sum(axis=1)==1)&frame.interpolated.eq(0).to_numpy()
    pq=known&(values[:,0]==1)
    nonpq=known&~pq
    row=np.arange(len(frame))
    begin=pq&~np.r_[False,pq[:-1]]
    latest=np.maximum.accumulate(np.where(begin,row,-1))
    safe=np.maximum(latest,0)
    exact_begin=begin&np.r_[False,nonpq[:-1]]
    exact=pq&exact_begin[safe]
    age=np.where(pq,row-latest,-1)
    phase=np.full(len(frame),'mode_unknown',dtype=object)
    phase[nonpq]='non_pq'
    phase[pq]='pq_start_unknown'
    phase[exact&(age==0)]='pq_first'
    phase[exact&(age==1)]='pq_second'
    phase[pq&(age>=2)]='pq_sustained_observed'
    lower=pd.array(np.where(pq,age,np.nan),dtype='Int64')
    exact_age=pd.array(np.where(exact,age,np.nan),dtype='Int64')
    prefix=row.copy()
    prefix[pq]=np.maximum(safe[pq]-1,0)
    return pd.DataFrame({'phase_state':phase,'observed_pq_age_lower_bound_s':lower,
                          'exact_pq_age_s':exact_age,'pq_age_left_censored':pq&~exact,
                          'phase_history_start_native_row':prefix+native_start})


def fixture(modes):
    labels={'S':[0,0,1,0],'Q':[1,0,0,0],'?':[0,0,0,0]}
    f=pd.DataFrame([labels[x] for x in modes],columns=MODES)
    f['interpolated']=0
    return f


def boundary_checks():
    a=partition_phases(fixture('SQQQ'),0)
    if a.phase_state.tolist()!=['non_pq','pq_first','pq_second','pq_sustained_observed']:
        raise ValueError('Known entry semantics differ')
    b=partition_phases(fixture('QQQ'),20)
    if b.phase_state.tolist()!=['pq_start_unknown','pq_start_unknown','pq_sustained_observed'] or not b.exact_pq_age_s.isna().all() or not b.pq_age_left_censored.all():
        raise ValueError('Left-censored beginning mislabeled or age zero-filled')
    changed=fixture('SQQQ')
    changed.loc[3,MODES]=[0,0,1,0]
    if not partition_phases(changed,0).iloc[:3].equals(a.iloc[:3]):
        raise ValueError('Future mode changes affected history')
    if not partition_phases(fixture('SQQ'),0).equals(a.iloc[:3].reset_index(drop=True)):
        raise ValueError('Prefix-only and full-source phase differ')
    c=partition_phases(fixture('SQ?QQQ'),0)
    if c.phase_state.iloc[2:].tolist()!=['mode_unknown','pq_start_unknown','pq_start_unknown','pq_sustained_observed']:
        raise ValueError('Unknown observation did not censor following run')
    # A second partition that starts PQ cannot borrow an exact start from the first.
    d=partition_phases(fixture('QQQ'),3)
    if d.phase_history_start_native_row.min()<3 or d.phase_state.iloc[0]!='pq_start_unknown':
        raise ValueError('Partition reset leaked preceding partition history')
    return ['known_start_and_age','unknown_start_not_zero_filled','future_mode_invariance',
            'prefix_invariance','unknown_mode_interrupts_provable_age','partition_prefix_reset']


def prepare(run_id):
    if not re.fullmatch(r'[A-Za-z0-9_-]+',run_id):raise ValueError('Invalid ID')
    output=BASE/'apr2023_response_phase_sample_runs'/run_id
    output.mkdir(parents=True,exist_ok=False)
    protocol=BASE/'apr2023_response_phase_sample_protocol_v2.json'
    p=json.loads(protocol.read_text(encoding='utf-8'))
    parent_path=BASE/p['parent_sample_protocol']
    if sha(parent_path)!=p['parent_sample_protocol_sha256']:raise ValueError('Parent protocol changed')
    parent=json.loads(parent_path.read_text(encoding='utf-8'))
    source=json.loads((BASE/parent['source_field_protocol']).read_text(encoding='utf-8'))
    raw_path=BASE/source['csv_relative_path']
    if sha(raw_path)!=source['csv_sha256']:raise ValueError('Raw source changed')
    previous=BASE/'apr2023_response_sample_runs'/p['parent_sample_run']
    pr=json.loads((previous/'validation_receipt.json').read_text(encoding='utf-8'))
    if any(sha(previous/name)!=value for name,value in pr['output_sha256'].items()):
        raise ValueError('Frozen parent artifact changed')
    contracts=boundary_checks()
    f=pd.read_csv(raw_path,sep=';',usecols=['DateAndTime',*MODES,'interpolated'])
    time=pd.to_datetime(f.DateAndTime)
    if len(f)!=source['rows'] or not time.is_unique or not time.diff().iloc[1:].eq(pd.Timedelta(seconds=1)).all():
        raise ValueError('Raw source clock differs')
    pieces=[]
    for block in parent['partitions']:
        lo=int(time.searchsorted(pd.Timestamp(block['start_inclusive'])))
        hi=int(time.searchsorted(pd.Timestamp(block['end_exclusive'])))
        phase=partition_phases(f.iloc[lo:hi],lo)
        selected=phase.iloc[1:-1].reset_index(drop=True)
        native=np.arange(lo+1,hi-1)
        selected.insert(0,'sample_id','APR2023_LMO1_'+pd.Series(native).astype(str))
        selected.insert(1,'native_origin_row',native)
        selected.insert(2,'partition',block['name'])
        selected.insert(3,'origin_time_utc_declared',f.DateAndTime.iloc[native].to_numpy())
        if (selected.phase_history_start_native_row<lo).any() or (selected.phase_history_start_native_row>native).any():
            raise ValueError('Phase prefix crosses partition or origin')
        pieces.append(selected)
    out=pd.concat(pieces,ignore_index=True)
    offset=0
    for c in pd.read_csv(previous/'inputs.csv.gz',usecols=['sample_id','native_origin_row','partition'],chunksize=100000):
        a=out.iloc[offset:offset+len(c)]
        if not np.array_equal(c.sample_id,a.sample_id) or not np.array_equal(c.native_origin_row,a.native_origin_row) or not np.array_equal(c.partition,a.partition):
            raise ValueError('Sidecar does not exactly preserve parent sample universe')
        offset+=len(c)
    if offset!=len(out) or offset!=pr['eligible_count']:raise ValueError('Sidecar total differs')
    out.to_csv(output/'phase_features.csv.gz',index=False,compression={'method':'gzip','compresslevel':1,'mtime':0})
    groups=out.groupby(['partition','phase_state']).agg(n=('sample_id','size'),
              left_censored=('pq_age_left_censored','sum'),null_exact_age=('exact_pq_age_s',lambda v:v.isna().sum())).reset_index()
    groups.to_csv(output/'phase_support.csv',index=False)
    snapshots=[('phase_sample_protocol_snapshot.json',protocol),
               ('phase_baseline_protocol_snapshot.json',BASE/'apr2023_response_phase_baseline_protocol_v2.json'),
               ('parent_sample_protocol_snapshot.json',parent_path),('preparation_code_snapshot.py',Path(__file__))]
    for name,path in snapshots:(output/name).write_bytes(path.read_bytes())
    receipt={'run_id':run_id,'status':'phase_sidecar_prepared_no_new_model_fit','protocol_id':p['protocol_id'],
             'data_card_version':p['data_card_version'],'source_csv_sha256':source['csv_sha256'],
             'parent_sample_run':p['parent_sample_run'],'samples':len(out),'same_parent_sample_ids_order_split':True,
             'phase_support':groups.to_dict('records'),'historical_information':'partition start through origin only',
             'contract_checks':contracts,'parent_artifact_sha256':pr['output_sha256'],
             'output_sha256':{name:sha(output/name) for name in ['phase_features.csv.gz','phase_support.csv']+[x[0] for x in snapshots]},
             'limits':'posthoc phase design; logged-prefix availability assumed; exact unknown ages null; no physical delay/capacity or independent confirmation'}
    (output/'validation_receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(receipt,ensure_ascii=False,indent=2))


if __name__=='__main__':
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id',required=True)
    prepare(parser.parse_args().run_id)
