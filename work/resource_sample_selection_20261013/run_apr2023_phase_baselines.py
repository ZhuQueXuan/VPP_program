"""Run frozen three-coefficient phase baseline; reuse immutable original controls."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import re
import sys
import time

import numpy as np
import pandas as pd

BASE=Path(__file__).resolve().parent
GROUPS=['pq_first','pq_second','pq_sustained_observed']


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def coefficients(ac,setting,phase,target,partition):
    parameters={}
    for name in GROUPS:
        mask=(partition=='fit')&(phase==name)
        gap=setting[mask]-ac[mask]
        delta=target[mask]-ac[mask]
        denominator=float(np.dot(gap,gap))
        numerator=float(np.dot(gap,delta))
        identifiable=bool(mask.any() and denominator>0 and np.isfinite(denominator) and np.isfinite(numerator))
        raw=numerator/denominator if identifiable else None
        beta=float(np.clip(raw,0,1)) if identifiable else None
        parameters[name]={'fit_n':int(mask.sum()),'denominator_kw_squared':denominator,
                          'beta_raw':raw,'beta':beta,'identifiable':identifiable,
                          'boundary_hit':bool(identifiable and raw!=beta),
                          'fallback_reason':None if identifiable else 'unidentifiable_fit_group'}
    return parameters


def predict(ac,setting,phase,original_set_prediction,params):
    # CSV controls can parse as integer even though fitted forecasts are fractional.
    value=np.asarray(original_set_prediction,dtype=float).copy()
    reason=np.select([phase=='non_pq',phase=='mode_unknown',phase=='pq_start_unknown'],
                     ['non_pq_design','mode_unknown','pq_start_unknown'],default='unidentifiable_fit_group').astype(object)
    for name in GROUPS:
        mask=phase==name
        if params[name]['identifiable']:
            value[mask]=ac[mask]+params[name]['beta']*(setting[mask]-ac[mask])
            reason[mask]=''
    return value,reason


def scientific_checks():
    ac=np.zeros(6);setting=np.array([10.,20.,30.,40.,50.,60.])
    phase=np.array(['pq_first','pq_second','pq_sustained_observed','pq_first','pq_second','pq_sustained_observed'])
    target=np.array([5.,10.,45.,0.,0.,0.]);partition=np.array(['fit']*3+['evaluation']*3)
    a=coefficients(ac,setting,phase,target,partition)
    future=target.copy();future[partition!='fit']=100000
    if a!=coefficients(ac,setting,phase,future,partition):raise ValueError('Non-fit targets affect parameters')
    if not a['pq_sustained_observed']['boundary_hit'] or a['pq_sustained_observed']['beta']!=1:
        raise ValueError('Declared boundary handling differs')
    zero=coefficients(ac,np.zeros(6),phase,target,partition)
    if any(x['identifiable'] or x['beta'] is not None for x in zero.values()):raise ValueError('Invented unidentified coefficient')
    absent=coefficients(ac,setting,phase,target,np.array(['evaluation']*6))
    if any(x['identifiable'] for x in absent.values()):raise ValueError('Missing fit phase assigned parameter')
    values,reason=predict(ac[:3],setting[:3],np.array(['pq_start_unknown','mode_unknown','non_pq']),np.array([10.,0.,0.]),a)
    if not np.array_equal(values,[10.,0.,0.]) or not np.all(reason!=''):
        raise ValueError('Unknown/non-PQ fallback differs')
    values,reason=predict(ac,setting,phase,setting,zero)
    if not np.array_equal(values,setting) or not np.all(reason=='unidentifiable_fit_group'):
        raise ValueError('Unidentifiable groups not retained with B_SET fallback')
    fractional={name:dict(beta=0.375,identifiable=True) for name in GROUPS}
    values,_=predict(np.array([0.]),np.array([100.]),np.array(['pq_first']),np.array([100],dtype=np.int64),fractional)
    if values[0]!=37.5 or not np.issubdtype(values.dtype,np.floating):
        raise ValueError('Integer control parsing truncated fractional forecasts')
    return ['nonfit_targets_do_not_change_parameters','declared_boundary_reported',
            'zero_or_absent_fit_groups_not_imputed','unknown_nonpq_and_unidentifiable_fallback_keeps_samples',
            'integer_control_input_preserves_fractional_phase_forecast']


def main(run_id,feature_run):
    started=time.perf_counter()
    if any(not re.fullmatch(r'[A-Za-z0-9_-]+',x) for x in [run_id,feature_run]):raise ValueError('Invalid ID')
    output=BASE/'apr2023_response_phase_baseline_runs'/run_id
    output.mkdir(parents=True,exist_ok=False)
    fr=BASE/'apr2023_response_phase_sample_runs'/feature_run
    freceipt=json.loads((fr/'validation_receipt.json').read_text(encoding='utf-8'))
    bp=BASE/'apr2023_response_phase_baseline_protocol_v2.json'
    sp=BASE/'apr2023_response_phase_sample_protocol_v2.json'
    if sha(bp)!=freceipt['output_sha256']['phase_baseline_protocol_snapshot.json'] or sha(sp)!=freceipt['output_sha256']['phase_sample_protocol_snapshot.json']:
        raise ValueError('Phase protocols differ from feature preparation freeze')
    if sha(fr/'phase_features.csv.gz')!=freceipt['output_sha256']['phase_features.csv.gz']:raise ValueError('Phase features changed')
    p=json.loads(bp.read_text(encoding='utf-8'));s=json.loads(sp.read_text(encoding='utf-8'))
    original=BASE/'apr2023_response_baseline_runs'/p['parent_baseline_run']
    br=json.loads((original/'run_receipt.json').read_text(encoding='utf-8'))
    if any(sha(original/name)!=value for name,value in br['output_sha256'].items()):raise ValueError('Original controls changed')
    samples=BASE/'apr2023_response_sample_runs'/s['parent_sample_run']
    if any(sha(samples/name)!=value for name,value in freceipt['parent_artifact_sha256'].items()):raise ValueError('Parent samples changed')
    contracts=scientific_checks()
    x=pd.read_csv(samples/'inputs.csv.gz',usecols=['sample_id','partition','origin_time_utc_declared',*s['input_columns'][:-1]])
    y=pd.read_csv(samples/'labels.csv.gz',usecols=['sample_id','ac_tp1_kw','set_changed_next_second','mode_changed_next_second'])
    phases=pd.read_csv(fr/'phase_features.csv.gz',usecols=['sample_id','phase_state','pq_age_left_censored'])
    old=pd.read_csv(original/'predictions.csv.gz',usecols=['sample_id','ac_tp1_reference_kw','B0_predicted_kw','B_SET_predicted_kw','B1_predicted_kw'],float_precision='round_trip')
    if not (x.sample_id.equals(y.sample_id) and x.sample_id.equals(phases.sample_id) and x.sample_id.equals(old.sample_id)):
        raise ValueError('Sample/phase/control alignment differs')
    if not np.array_equal(y.ac_tp1_kw,old.ac_tp1_reference_kw):raise ValueError('Reference target differs')
    legal=x[s['input_columns'][:-1]].copy();legal['phase_state']=phases.phase_state
    ac=legal.ac_t_kw.to_numpy(dtype=float);setting=legal.set_t_kw.to_numpy(dtype=float)
    phase=legal.phase_state.to_numpy();partition=x.partition.to_numpy();pq=legal.mode_pq_t.eq(1).to_numpy()
    if not np.isin(phase,['non_pq','mode_unknown','pq_start_unknown',*GROUPS]).all():raise ValueError('Unregistered phase')
    if np.any(np.isin(phase,GROUPS)&~pq):raise ValueError('Known PQ phase disagrees with current mode')
    target=y.ac_tp1_kw.to_numpy(dtype=float)
    fit_started=time.perf_counter();params=coefficients(ac,setting,phase,target,partition)
    fit_elapsed=time.perf_counter()-fit_started
    phase_values,reasons=predict(ac,setting,phase,old.B_SET_predicted_kw.to_numpy(),params)
    values={name:old[name+'_predicted_kw'].to_numpy() for name in ['B0','B_SET','B1']}
    values['B_PHASE']=phase_values
    pred=x[['sample_id','partition','origin_time_utc_declared']].copy()
    pred['phase_state']=phase;pred['ac_tp1_reference_kw']=target;pred['phase_fallback_reason']=reasons
    for name,v in values.items():
        if not np.isfinite(v).all():raise ValueError('Nonfinite predictions, no silent exclusion')
        pred[name+'_predicted_kw']=v
    dates=x.origin_time_utc_declared.str[:10]
    summaries=[];daily_rows=[];group_rows=[]
    mode=np.select([legal.mode_pq_t.eq(1),legal.mode_stop_t.eq(1),legal.mode_silent_t.eq(1),legal.mode_wait_t.eq(1)],['PQ','Stop','Silent','Wait'],default='unknown')
    for name,v in values.items():
        errors=pd.DataFrame({'partition':partition,'date':dates,'pq':pq,'phase_state':phase,'mode':mode,
                   'origin_direction':np.select([ac>0,ac<0],['discharge','charge'],default='zero'),
                   'future_set_changed':y.set_changed_next_second,'future_mode_changed':y.mode_changed_next_second,
                   'censored':phases.pq_age_left_censored,'absolute':np.abs(v-target),'signed':v-target})
        for subset,frame in [('all',errors),('current_PQ',errors[errors.pq])]:
            d=frame.groupby(['partition','date']).agg(n=('absolute','size'),mae_kw=('absolute','mean'),bias_kw=('signed','mean')).reset_index()
            d['model'],d['subset']=name,subset;daily_rows.append(d)
        for part in ['fit','validation','evaluation']:
            all_part=errors[errors.partition.eq(part)];active=all_part[all_part.pq]
            summaries.append({'model':name,'partition':part,'n_all':len(all_part),'n_current_pq':len(active),
                  'all_pooled_mae_kw':float(all_part.absolute.mean()),'pq_pooled_mae_kw':float(active.absolute.mean()),
                  'pq_daily_equal_mae_kw':float(active.groupby('date').absolute.mean().mean()),
                  'pq_bias_kw':float(active.signed.mean()),'coverage':1.})
        for key,frame in [('phase_state',errors),('mode',errors),('censored',errors[errors.pq]),
                          ('origin_direction',errors[errors.pq]),('future_set_changed',errors[errors.pq]),('future_mode_changed',errors[errors.pq])]:
            g=frame.groupby(['partition',key]).agg(n=('absolute','size'),mae_kw=('absolute','mean'),bias_kw=('signed','mean')).reset_index().rename(columns={key:'group'})
            g['model'],g['stratum']=name,key;group_rows.append(g)
    summary=pd.DataFrame(summaries);daily=pd.concat(daily_rows,ignore_index=True);grouped=pd.concat(group_rows,ignore_index=True)
    paired=daily[daily.subset.eq('current_PQ')].pivot(index=['partition','date'],columns='model',values='mae_kw').reset_index()
    paired['B_PHASE_minus_B_SET_kw']=paired.B_PHASE-paired.B_SET
    fallback=pd.DataFrame({'partition':partition,'reason':reasons,'pq':pq}).groupby(['partition','reason']).agg(n=('pq','size'),current_pq_n=('pq','sum')).reset_index()
    worst=[];idx=np.flatnonzero((partition=='evaluation')&pq)
    for name,v in values.items():
        inds=idx[np.lexsort((idx,-np.abs(v[idx]-target[idx])))[:10]]
        table=pred.iloc[inds].copy();table['model']=name;table['absolute_residual_kw']=np.abs(v[inds]-target[inds]);worst.append(table)
    pred.to_csv(output/'predictions.csv.gz',index=False,float_format='%.17g',compression={'method':'gzip','compresslevel':1,'mtime':0})
    for filename,frame in [('summary_metrics.csv',summary),('daily_metrics.csv',daily),('group_metrics.csv',grouped),
                            ('daily_paired_mae.csv',paired),('fallback_counts.csv',fallback),('worst_evaluation_pq.csv',pd.concat(worst,ignore_index=True))]:
        frame.to_csv(output/filename,index=False,float_format='%.17g')
    pd.DataFrame(columns=['sample_id','model','reason']).to_csv(output/'failed_predictions.csv',index=False)
    (output/'parameters.json').write_text(json.dumps(params,indent=2)+'\n',encoding='utf-8')
    for filename,path in [('phase_baseline_protocol_snapshot.json',bp),('phase_sample_protocol_snapshot.json',sp),('runner_code_snapshot.py',Path(__file__))]:
        (output/filename).write_bytes(path.read_bytes())
    if any(sha(original/name)!=value for name,value in br['output_sha256'].items()):raise ValueError('Original controls altered')
    names=['predictions.csv.gz','summary_metrics.csv','daily_metrics.csv','group_metrics.csv','daily_paired_mae.csv',
           'fallback_counts.csv','worst_evaluation_pq.csv','failed_predictions.csv','parameters.json',
           'phase_baseline_protocol_snapshot.json','phase_sample_protocol_snapshot.json','runner_code_snapshot.py']
    receipt={'run_id':run_id,'status':'exploratory_phase_baseline_run_pending_independent_verification',
       'protocol_id':p['protocol_id'],'input_card':s['data_card_version'],'feature_run':feature_run,
       'parent_sample_run':s['parent_sample_run'],'parent_baseline_run':p['parent_baseline_run'],
       'samples':len(x),'input_whitelist':s['input_columns'],'parameters':params,'coefficient_fit_partition':'fit_only',
       'parent_control_artifact_sha256':br['output_sha256'],'source_csv_sha256':freceipt['source_csv_sha256'],
       'scientific_checks':contracts,'failures':0,'feature_sha256':freceipt['output_sha256']['phase_features.csv.gz'],
       'primary_evaluation':summary[summary.partition.eq('evaluation')].to_dict('records'),
       'fallback_counts':fallback.to_dict('records'),'output_sha256':{name:sha(output/name) for name in names},
       'runtime':{'device':'local_CPU','coefficient_fit_seconds':fit_elapsed,'total_seconds':time.perf_counter()-started,
                  'python':platform.python_version(),'numpy':np.__version__,'pandas':pd.__version__},
       'limits':'April phase-design-informed retrospective exploration; no independent confirmation or actual delay/capacity/project accuracy'}
    (output/'run_receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({key:receipt[key] for key in ['run_id','parameters','primary_evaluation','fallback_counts','runtime']},indent=2))


if __name__=='__main__':
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id',required=True);parser.add_argument('--feature-run',required=True)
    args=parser.parse_args();main(args.run_id,args.feature_run)
