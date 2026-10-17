"""Verify all phase forecasts and main/daily/phase metrics from raw logged prefixes."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

import numpy as np
import pandas as pd

BASE=Path(__file__).resolve().parent
GROUPS=['pq_first','pq_second','pq_sustained_observed']


def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def verify(first_id,repeat_id,verification_id):
    if any(not re.fullmatch(r'[A-Za-z0-9_-]+',x) for x in [first_id,repeat_id,verification_id]):raise ValueError('Invalid ID')
    runs=BASE/'apr2023_response_phase_baseline_runs';first=runs/first_id;repeat=runs/repeat_id
    output=runs/(verification_id+'.json')
    if output.exists():raise FileExistsError(output)
    a=json.loads((first/'run_receipt.json').read_text(encoding='utf-8'));b=json.loads((repeat/'run_receipt.json').read_text(encoding='utf-8'))
    byte_checks={name:sha(first/name)==sha(repeat/name)==value==b['output_sha256'][name] for name,value in a['output_sha256'].items()}
    if not all(byte_checks.values()):raise ValueError('Fixed-result artifacts differ on rerun')
    src=json.loads((BASE/'apr2023_lmo1_field_protocol_v1.json').read_text(encoding='utf-8'))
    raw_path=BASE/src['csv_relative_path']
    if sha(raw_path)!=src['csv_sha256']:raise ValueError('Raw source changed')
    f=pd.read_csv(raw_path,sep=';');clock=pd.to_datetime(f.DateAndTime)
    sp=json.loads((first/'phase_sample_protocol_snapshot.json').read_text(encoding='utf-8'))
    parent=json.loads((BASE/sp['parent_sample_protocol']).read_text(encoding='utf-8'))
    native=[];names=[];states=[]
    modes=['Mode_PQ','Mode_Stop','Mode_Silent','Mode_Wait']
    for block in parent['partitions']:
        lo=int(clock.searchsorted(pd.Timestamp(block['start_inclusive'])));hi=int(clock.searchsorted(pd.Timestamp(block['end_exclusive'])))
        flags=f[modes].iloc[lo:hi].to_numpy()
        known=np.isin(flags,[0,1]).all(axis=1)&(flags.sum(axis=1)==1)&f.interpolated.iloc[lo:hi].eq(0).to_numpy()
        q=known&(flags[:,0]==1);nonq=known&~q
        # Independent phase classification using only up to three historical observations.
        prevq=np.r_[False,q[:-1]];prevprevq=np.r_[False,False,q[:-2]]
        prevnonq=np.r_[False,nonq[:-1]];prevprevnonq=np.r_[False,False,nonq[:-2]]
        phase=np.where(nonq,'non_pq','mode_unknown').astype(object);phase[q]='pq_start_unknown'
        phase[q&prevq&prevprevq]='pq_sustained_observed'
        phase[q&prevnonq]='pq_first';phase[q&prevq&prevprevnonq]='pq_second'
        native.append(np.arange(lo+1,hi-1));names.append(np.full(hi-lo-2,block['name'],dtype=object));states.append(phase[1:-1])
    origins=np.concatenate(native);part=np.concatenate(names);phase=np.concatenate(states)
    ac=f.P_AC.to_numpy(dtype=float)[origins];setting=f.P_AC_Set.to_numpy(dtype=float)[origins]
    target=f.P_AC.to_numpy(dtype=float)[origins+1];pq=f.Mode_PQ.to_numpy()[origins]==1
    saved=json.loads((first/'parameters.json').read_text(encoding='utf-8'));parameters={}
    for name in GROUPS:
        mask=(part=='fit')&(phase==name);gap=setting[mask]-ac[mask]
        denominator=float(np.sum(gap**2));numerator=float(np.sum(gap*(target[mask]-ac[mask])))
        identified=bool(mask.any() and denominator>0 and np.isfinite(denominator) and np.isfinite(numerator))
        raw=numerator/denominator if identified else None;beta=min(1.,max(0.,raw)) if identified else None
        parameters[name]=beta
        if identified!=saved[name]['identifiable'] or int(mask.sum())!=saved[name]['fit_n']:
            raise ValueError('Training cohort/identifiability differs')
        if identified and (abs(beta-saved[name]['beta'])>1e-12 or abs(raw-saved[name]['beta_raw'])>1e-12):
            raise ValueError('Raw-only coefficients differ')
    original=BASE/'apr2023_response_baseline_runs'/a['parent_baseline_run']
    old=json.loads((original/'parameters.json').read_text(encoding='utf-8'))
    expected={'B0':ac,'B_SET':np.where(pq,setting,ac),'B1':np.where(pq,(1-old['beta'])*ac+old['beta']*setting,ac)}
    expected['B_PHASE']=expected['B_SET'].copy()
    reason=np.select([phase=='non_pq',phase=='mode_unknown',phase=='pq_start_unknown'],
                     ['non_pq_design','mode_unknown','pq_start_unknown'],default='unidentifiable_fit_group').astype(object)
    for name,beta in parameters.items():
        if beta is not None:
            mask=phase==name;expected['B_PHASE'][mask]=(1-beta)*ac[mask]+beta*setting[mask];reason[mask]=''
    count=0;maxdiff={name:0. for name in expected}
    for c in pd.read_csv(first/'predictions.csv.gz',chunksize=100000,float_precision='round_trip'):
        sl=slice(count,count+len(c));idx=origins[sl]
        if not np.array_equal(c.sample_id,['APR2023_LMO1_'+str(i) for i in idx]) or not np.array_equal(c.partition,part[sl]):raise ValueError('Keys/partitions differ')
        if not np.array_equal(c.phase_state,phase[sl]) or not np.array_equal(c.ac_tp1_reference_kw,target[sl]):raise ValueError('Phase/target differs')
        if not np.array_equal(c.phase_fallback_reason.fillna(''),reason[sl]):raise ValueError('Fallback retention differs')
        for name,v in expected.items():
            diff=float(np.max(np.abs(c[name+'_predicted_kw'].to_numpy()-v[sl])))
            maxdiff[name]=max(maxdiff[name],diff)
            if diff>1e-10:raise ValueError('Prediction exceeds frozen tolerance: '+name)
        count+=len(c)
    if count!=len(origins):raise ValueError('Prediction coverage differs')
    dates=f.DateAndTime.iloc[origins].str[:10].to_numpy()
    daily=pd.read_csv(first/'daily_metrics.csv');summary=pd.read_csv(first/'summary_metrics.csv');grouped=pd.read_csv(first/'group_metrics.csv')
    metricdiff=0.
    for name,v in expected.items():
        error=v-target
        for split in ['fit','validation','evaluation']:
            whole=part==split;active=whole&pq;daily_pq=[]
            for subset,mask in [('all',whole),('current_PQ',active)]:
                for date in np.unique(dates[mask]):
                    m=mask&(dates==date);mae=float(np.abs(error[m]).mean());bias=float(error[m].mean())
                    row=daily[(daily.model==name)&(daily.partition==split)&(daily.subset==subset)&(daily.date==date)]
                    if len(row)!=1 or int(row.iloc[0]['n'])!=int(m.sum()):raise ValueError('Daily coverage differs')
                    metricdiff=max(metricdiff,abs(mae-float(row.iloc[0].mae_kw)),abs(bias-float(row.iloc[0].bias_kw)))
                    if subset=='current_PQ':daily_pq.append(mae)
            row=summary[(summary.model==name)&(summary.partition==split)].iloc[0]
            calculations={'all_pooled_mae_kw':float(np.abs(error[whole]).mean()),'pq_pooled_mae_kw':float(np.abs(error[active]).mean()),
                          'pq_daily_equal_mae_kw':float(np.mean(daily_pq)),'pq_bias_kw':float(error[active].mean())}
            for key,value in calculations.items():metricdiff=max(metricdiff,abs(value-float(row[key])))
            for state in np.unique(phase[whole]):
                m=whole&(phase==state);row=grouped[(grouped.model==name)&(grouped.partition==split)&(grouped.stratum=='phase_state')&(grouped['group']==state)]
                if len(row)!=1 or int(row.iloc[0]['n'])!=int(m.sum()):raise ValueError('Phase coverage differs')
                metricdiff=max(metricdiff,abs(float(np.abs(error[m]).mean())-float(row.iloc[0].mae_kw)),abs(float(error[m].mean())-float(row.iloc[0].bias_kw)))
    if metricdiff>1e-9:raise ValueError('Metrics exceed frozen tolerance')
    if any(sha(original/name)!=value for name,value in a['parent_control_artifact_sha256'].items()):raise ValueError('Original controls changed')
    result={'verification_id':verification_id,'status':'exploratory_phase_arithmetic_and_reproducibility_verified_not_independent_confirmation',
            'first_run':first_id,'repeat_run':repeat_id,'samples_verified':count,'raw_only_fit_coefficients':parameters,
            'max_prediction_difference_kw':maxdiff,'max_daily_main_phase_metric_difference_kw':metricdiff,
            'repeat_artifact_checks':byte_checks,'original_control_artifacts_unchanged':True,
            'all_phases_and_fallback_flags_match_raw_prefix':True,'source_csv_sha256':src['csv_sha256'],
            'verification_code_sha256':sha(Path(__file__)),
            'limits':'raw numeric verification includes parameters, all forecasts, all daily/main/phase metrics; other strata byte-reproduced only. April was phase-design-informed; no independent method confirmation or physical delay/capacity claim.'}
    output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    (runs/(verification_id+'_code_snapshot.py')).write_bytes(Path(__file__).read_bytes())
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--first-run',required=True);parser.add_argument('--repeat-run',required=True);parser.add_argument('--verification-id',required=True)
    args=parser.parse_args();verify(args.first_run,args.repeat_run,args.verification_id)
