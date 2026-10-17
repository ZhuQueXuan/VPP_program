"""Recompute forecasts/metrics directly from native CSV; verify unchanged rerun."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

import numpy as np
import pandas as pd

BASE=Path(__file__).resolve().parent


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def verify(first_id,repeat_id,verification_id):
    if any(not re.fullmatch(r'[A-Za-z0-9_-]+',x) for x in [first_id,repeat_id,verification_id]):
        raise ValueError('Invalid ID')
    runs=BASE/'apr2023_response_baseline_runs'
    first,repeat=runs/first_id,runs/repeat_id
    output=runs/(verification_id+'.json')
    if output.exists():
        raise FileExistsError(output)
    a=json.loads((first/'run_receipt.json').read_text(encoding='utf-8'))
    b=json.loads((repeat/'run_receipt.json').read_text(encoding='utf-8'))
    repeat_checks={name:sha(first/name)==sha(repeat/name)==value==b['output_sha256'][name]
                   for name,value in a['output_sha256'].items()}
    if not all(repeat_checks.values()):
        raise ValueError('Repeated baseline artifacts differ')
    source=json.loads((BASE/'apr2023_lmo1_field_protocol_v1.json').read_text(encoding='utf-8'))
    raw_path=BASE/source['csv_relative_path']
    if sha(raw_path)!=source['csv_sha256']:
        raise ValueError('Raw source changed')
    f=pd.read_csv(raw_path,sep=';')
    sp=json.loads((first/'sample_protocol_snapshot.json').read_text(encoding='utf-8'))
    clock=pd.to_datetime(f.DateAndTime)
    intervals=[]
    parts=[]
    for block in sp['partitions']:
        lo=int(clock.searchsorted(pd.Timestamp(block['start_inclusive'])))
        hi=int(clock.searchsorted(pd.Timestamp(block['end_exclusive'])))
        intervals.append(np.arange(lo+1,hi-1))
        parts.extend([block['name']]*(hi-lo-2))
    origins=np.concatenate(intervals)
    parts=np.asarray(parts)
    ac=f.P_AC.to_numpy(dtype=float)[origins]
    setting=f.P_AC_Set.to_numpy(dtype=float)[origins]
    target=f.P_AC.to_numpy(dtype=float)[origins+1]
    pq=f.Mode_PQ.to_numpy()[origins]==1
    fit=(parts=='fit')&pq
    # Raw-only recomputation, no prepared targets, fitted implementation or evaluation targets.
    gap=setting[fit]-ac[fit]
    beta_raw=float(np.sum(gap*(target[fit]-ac[fit]))/np.sum(gap**2))
    beta=max(0.,min(1.,beta_raw))
    params=json.loads((first/'parameters.json').read_text(encoding='utf-8'))
    if abs(beta-params['beta'])>1e-12 or abs(beta_raw-params['beta_unconstrained'])>1e-12:
        raise ValueError('Training-only coefficient differs')
    expected={'B0':ac,'B_SET':ac.copy(),'B1':ac.copy()}
    expected['B_SET'][pq]=setting[pq]
    expected['B1'][pq]=(1-beta)*ac[pq]+beta*setting[pq]
    n=0
    maxdiff={name:0. for name in expected}
    for c in pd.read_csv(first/'predictions.csv.gz',chunksize=100000,float_precision='round_trip'):
        rows=slice(n,n+len(c))
        ids=np.array(['APR2023_LMO1_'+str(i) for i in origins[rows]])
        if not np.array_equal(c.sample_id,ids) or not np.array_equal(c.ac_tp1_reference_kw,target[rows]):
            raise ValueError('Prediction keys/reference differ from raw')
        if not np.array_equal(c.partition,parts[rows]):
            raise ValueError('Prediction partition differs')
        for name,v in expected.items():
            diff=float(np.max(np.abs(c[name+'_predicted_kw'].to_numpy()-v[rows])))
            maxdiff[name]=max(maxdiff[name],diff)
            if diff>1e-10:
                raise ValueError('Prediction differs: '+name)
        n+=len(c)
    if n!=len(origins):
        raise ValueError('Prediction coverage differs')
    dates=f.DateAndTime.iloc[origins].str[:10].to_numpy()
    summary=pd.read_csv(first/'summary_metrics.csv')
    saved_daily=pd.read_csv(first/'daily_metrics.csv')
    max_metric_diff=0.
    for name,v in expected.items():
        error=v-target
        for part in ['fit','validation','evaluation']:
            block=parts==part
            current_pq=block&pq
            date_mae=[]
            for subset,mask in [('all',block),('current_PQ',current_pq)]:
                for date in np.unique(dates[mask]):
                    group=mask&(dates==date)
                    mae=float(np.mean(np.abs(error[group])))
                    bias=float(np.mean(error[group]))
                    row=saved_daily[(saved_daily.model==name)&(saved_daily.partition==part)&
                                    (saved_daily.subset==subset)&(saved_daily.date==date)]
                    if len(row)!=1 or int(row.iloc[0]['n'])!=int(group.sum()):
                        raise ValueError('Daily coverage differs')
                    max_metric_diff=max(max_metric_diff,abs(float(row.iloc[0].mae_kw)-mae),
                                         abs(float(row.iloc[0].bias_kw)-bias))
                    if subset=='current_PQ':
                        date_mae.append(mae)
            row=summary[(summary.model==name)&(summary.partition==part)].iloc[0]
            values={'all_pooled_mae_kw':float(np.abs(error[block]).mean()),
                    'pq_pooled_mae_kw':float(np.abs(error[current_pq]).mean()),
                    'pq_daily_equal_mae_kw':float(np.mean(date_mae)),
                    'pq_bias_kw':float(error[current_pq].mean())}
            for key,value in values.items():
                max_metric_diff=max(max_metric_diff,abs(float(row[key])-value))
    if max_metric_diff>1e-9:
        raise ValueError('Independent daily/main metrics differ')
    receipt={'verification_id':verification_id,'status':'raw_predictions_parameters_and_primary_daily_metrics_verified',
             'first_run':first_id,'repeat_run':repeat_id,'samples_verified':n,'raw_training_beta':beta,
             'max_prediction_difference_kw':maxdiff,'max_metric_difference_kw':max_metric_diff,
             'repeat_artifact_checks':repeat_checks,'source_csv_sha256':source['csv_sha256'],
             'verification_code_sha256':sha(Path(__file__)),
             'limits':'group tables byte-reproduced; independent numeric checks cover all predictions, coefficient, daily and main metrics. No actual-delay/capacity validation.'}
    output.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    (runs/(verification_id+'_code_snapshot.py')).write_bytes(Path(__file__).read_bytes())
    print(json.dumps(receipt,indent=2))


if __name__=='__main__':
    if hasattr(sys.stdout,'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--first-run',required=True)
    parser.add_argument('--repeat-run',required=True)
    parser.add_argument('--verification-id',required=True)
    args=parser.parse_args()
    verify(args.first_run,args.repeat_run,args.verification_id)
