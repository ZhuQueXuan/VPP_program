"""Run only the frozen persistence/setpoint/one-parameter log forecast baselines."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

import numpy as np
import pandas as pd

BASE=Path(__file__).resolve().parent
MODELS=['B0','B_SET','B1']


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def main(run_id,sample_run):
    if any(not re.fullmatch(r'[A-Za-z0-9_-]+',x) for x in [run_id,sample_run]):
        raise ValueError('Invalid ID')
    output=BASE/'apr2023_response_baseline_runs'/run_id
    output.mkdir(parents=True,exist_ok=False)
    samples=BASE/'apr2023_response_sample_runs'/sample_run
    sr=json.loads((samples/'validation_receipt.json').read_text(encoding='utf-8'))
    protocol=BASE/'apr2023_response_baseline_protocol_v1.json'
    if sha(protocol)!=sr['baseline_protocol_sha256']:
        raise ValueError('Frozen comparison protocol changed')
    p=json.loads(protocol.read_text(encoding='utf-8'))
    sp=json.loads((samples/'sample_protocol_snapshot.json').read_text(encoding='utf-8'))
    for name in ['inputs.csv.gz','labels.csv.gz','sample_protocol_snapshot.json']:
        if sha(samples/name)!=sr['output_sha256'][name]:
            raise ValueError('Frozen sample artifact changed: '+name)
    x=pd.read_csv(samples/'inputs.csv.gz')
    y=pd.read_csv(samples/'labels.csv.gz')
    if not x.sample_id.equals(y.sample_id) or len(x)!=sr['eligible_count']:
        raise ValueError('Sample/label alignment differs')
    # Predictors come only from the frozen whitelist, never target or diagnostic columns.
    features=x[sp['input_columns']].copy()
    ac=features.ac_t_kw.to_numpy(dtype=float)
    setting=features.set_t_kw.to_numpy(dtype=float)
    pq=features.mode_pq_t.eq(1).to_numpy()
    target=y.ac_tp1_kw.to_numpy(dtype=float)
    fit=x.partition.eq('fit').to_numpy()&pq
    gap=setting[fit]-ac[fit]
    delta=target[fit]-ac[fit]
    denominator=float(np.dot(gap,gap))
    if denominator<=0 or not np.isfinite(denominator):
        raise ValueError('B1 unidentifiable: invalid training denominator')
    beta_unconstrained=float(np.dot(gap,delta)/denominator)
    beta=float(np.clip(beta_unconstrained,0,1))
    parameters={'beta_unconstrained':beta_unconstrained,'beta':beta,
                'boundary_hit':bool(beta!=beta_unconstrained),'fit_current_pq_samples':int(fit.sum()),
                'denominator_kw_squared':denominator,'fit_partition_only':True,
                'interpretation':'declared blending coefficient; no physical time-constant/causality claim'}
    values={'B0':ac,'B_SET':np.where(pq,setting,ac),'B1':np.where(pq,ac+beta*(setting-ac),ac)}
    pred=x[['sample_id','partition','origin_time_utc_declared']].copy()
    pred['ac_tp1_reference_kw']=target
    for model,v in values.items():
        pred[model+'_predicted_kw']=v
        if not np.isfinite(v).all():
            raise ValueError('Nonfinite prediction; do not silently exclude samples')
    dates=x.origin_time_utc_declared.str[:10]
    mode=np.select([features.mode_pq_t.eq(1),features.mode_stop_t.eq(1),features.mode_silent_t.eq(1),
                    features.mode_wait_t.eq(1)],['PQ','Stop','Silent','Wait'],default='unknown')
    direction=np.select([ac>0,ac<0],['discharge','charge'],default='zero')
    daily_rows=[]
    group_rows=[]
    summaries=[]
    for model,v in values.items():
        error=v-target
        scores=pd.DataFrame({'partition':x.partition,'date':dates,'pq':pq,'mode':mode,'direction':direction,
                             'future_set_changed':y.set_changed_next_second,
                             'future_mode_changed':y.mode_changed_next_second,
                             'abs_error_kw':np.abs(error),'signed_error_kw':error})
        for subset,frame in [('all',scores),('current_PQ',scores[scores.pq])]:
            table=frame.groupby(['partition','date']).agg(n=('abs_error_kw','size'),
                      mae_kw=('abs_error_kw','mean'),bias_kw=('signed_error_kw','mean')).reset_index()
            table['model'],table['subset']=model,subset
            daily_rows.append(table)
        for part in ['fit','validation','evaluation']:
            all_part=scores[scores.partition.eq(part)]
            active=all_part[all_part.pq]
            summaries.append({'model':model,'partition':part,'n_all':len(all_part),'n_current_pq':len(active),
                              'all_pooled_mae_kw':float(all_part.abs_error_kw.mean()),
                              'pq_pooled_mae_kw':float(active.abs_error_kw.mean()),
                              'pq_daily_equal_mae_kw':float(active.groupby('date').abs_error_kw.mean().mean()),
                              'pq_bias_kw':float(active.signed_error_kw.mean()),'prediction_coverage':1.0})
        for strata,frame in [('current_mode',scores),('origin_direction_current_PQ',scores[scores.pq]),
                             ('future_set_change_current_PQ',scores[scores.pq]),('future_mode_change_current_PQ',scores[scores.pq])]:
            key={'current_mode':'mode','origin_direction_current_PQ':'direction',
                 'future_set_change_current_PQ':'future_set_changed','future_mode_change_current_PQ':'future_mode_changed'}[strata]
            table=frame.groupby(['partition',key]).agg(n=('abs_error_kw','size'),
                      mae_kw=('abs_error_kw','mean'),bias_kw=('signed_error_kw','mean')).reset_index().rename(columns={key:'group'})
            table['model'],table['stratum']=model,strata
            group_rows.append(table)
    daily=pd.concat(daily_rows,ignore_index=True)
    grouped=pd.concat(group_rows,ignore_index=True)
    summary=pd.DataFrame(summaries)
    worst=[]
    evaluation=x.partition.eq('evaluation').to_numpy()&pq
    for model,v in values.items():
        inds=np.flatnonzero(evaluation)
        order=inds[np.argsort(np.abs(v[inds]-target[inds]),kind='stable')[-10:][::-1]]
        rows=pred.iloc[order].copy()
        rows['model'],rows['absolute_residual_kw']=model,np.abs(v[order]-target[order])
        rows['set_changed_next_second']=y.set_changed_next_second.iloc[order].to_numpy()
        rows['mode_changed_next_second']=y.mode_changed_next_second.iloc[order].to_numpy()
        worst.append(rows)
    pred.to_csv(output/'predictions.csv.gz',index=False,float_format='%.17g',
                compression={'method':'gzip','compresslevel':1,'mtime':0})
    daily.to_csv(output/'daily_metrics.csv',index=False,float_format='%.17g')
    grouped.to_csv(output/'group_metrics.csv',index=False,float_format='%.17g')
    summary.to_csv(output/'summary_metrics.csv',index=False,float_format='%.17g')
    pd.concat(worst,ignore_index=True).to_csv(output/'worst_evaluation_pq.csv',index=False,float_format='%.17g')
    pd.DataFrame(columns=['sample_id','model','failure_reason']).to_csv(output/'failed_predictions.csv',index=False)
    (output/'parameters.json').write_text(json.dumps(parameters,indent=2)+'\n',encoding='utf-8')
    (output/'baseline_protocol_snapshot.json').write_bytes(protocol.read_bytes())
    (output/'sample_protocol_snapshot.json').write_bytes((samples/'sample_protocol_snapshot.json').read_bytes())
    (output/'runner_code_snapshot.py').write_bytes(Path(__file__).read_bytes())
    names=['predictions.csv.gz','daily_metrics.csv','group_metrics.csv','summary_metrics.csv',
           'worst_evaluation_pq.csv','failed_predictions.csv','parameters.json','baseline_protocol_snapshot.json',
           'sample_protocol_snapshot.json','runner_code_snapshot.py']
    receipt={'run_id':run_id,'status':'frozen_baselines_run_not_yet_independently_verified','sample_run':sample_run,
             'data_card_version':sp['data_card_version'],'protocol_id':p['protocol_id'],'sample_count':len(x),
             'input_whitelist':sp['input_columns'],'parameter_fit_source':'fit_current_PQ_only',
             'parameters':parameters,'primary_evaluation':summary[summary.partition.eq('evaluation')].to_dict('records'),
             'failures':0,'sample_artifact_sha256':sr['output_sha256'],
             'output_sha256':{name:sha(output/name) for name in names},
             'environment':{'pandas':pd.__version__,'numpy':np.__version__},
             'limits':'log-time one-step forecast only; future commands unknown; no actual latency, energy, capacity, causality or project accuracy'}
    (output/'run_receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'run_id':run_id,'parameters':parameters,'primary_evaluation':receipt['primary_evaluation']},indent=2))


if __name__=='__main__':
    if hasattr(sys.stdout,'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id',required=True)
    parser.add_argument('--sample-run',required=True)
    args=parser.parse_args()
    main(args.run_id,args.sample_run)
