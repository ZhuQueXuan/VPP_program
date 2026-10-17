"""Post-hoc native B_SET residual contexts and observed-mode run age. No refit."""
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


def audit(run_id):
    if not re.fullmatch(r'[A-Za-z0-9_-]+',run_id):
        raise ValueError('Invalid ID')
    output=BASE/'apr2023_response_residual_runs'/run_id
    output.mkdir(parents=True,exist_ok=False)
    protocol=BASE/'apr2023_response_residual_protocol_v1.json'
    p=json.loads(protocol.read_text(encoding='utf-8'))
    sp=json.loads((BASE/p['sample_protocol']).read_text(encoding='utf-8'))
    source=json.loads((BASE/p['source_field_protocol']).read_text(encoding='utf-8'))
    csv_path=BASE/source['csv_relative_path']
    baseline=BASE/'apr2023_response_baseline_runs'/p['baseline_run']
    br=json.loads((baseline/'run_receipt.json').read_text(encoding='utf-8'))
    frozen_before={name:sha(baseline/name) for name in br['output_sha256']}
    if frozen_before!=br['output_sha256'] or sha(csv_path)!=source['csv_sha256']:
        raise ValueError('Frozen source or baseline changed')
    f=pd.read_csv(csv_path,sep=';')
    clock=pd.to_datetime(f.DateAndTime)
    pq=f.Mode_PQ.eq(1).to_numpy()
    row=np.arange(len(f))
    starts=pq&~np.r_[False,pq[:-1]]
    latest_start=np.maximum.accumulate(np.where(starts,row,-1))
    ages=np.where(pq,row-latest_start,-1)
    left_censored=pq&(latest_start==0)&bool(pq[0])
    origins=[]; partitions=[]
    for block in sp['partitions']:
        lo=int(clock.searchsorted(pd.Timestamp(block['start_inclusive'])))
        hi=int(clock.searchsorted(pd.Timestamp(block['end_exclusive'])))
        idx=np.arange(lo+1,hi-1)
        origins.append(idx);partitions.extend([block['name']]*len(idx))
    all_origins=np.concatenate(origins)
    all_partitions=np.asarray(partitions)
    sel=pq[all_origins]
    i=all_origins[sel]
    part=all_partitions[sel]
    ac=f.P_AC.to_numpy();setting=f.P_AC_Set.to_numpy()
    residual=setting[i].astype(float)-ac[i+1]
    absolute=np.abs(residual)
    age=ages[i]
    phase=np.select([age==0,age==1],p['age_groups'][:2],default=p['age_groups'][2])
    mode_changed=(f[MODE].iloc[i].to_numpy()!=f[MODE].iloc[i+1].to_numpy()).any(axis=1)
    s=pd.DataFrame({'native_origin_row':i,'partition':part,'logged_pq_age_s':age,'age_group':phase,
                    'left_censored_age':left_censored[i],'signed_residual_kw':residual,'abs_residual_kw':absolute,
                    'large_residual':absolute>p['large_residual_strict_gt_kw'],
                    'future_set_changed':setting[i]!=setting[i+1],'future_mode_changed':mode_changed,
                    'target_ac_zero':ac[i+1]==0,'target_current_zero':f.I_DC_Batt.to_numpy()[i+1]==0})
    groups=s.groupby(['partition','age_group']).agg(n=('abs_residual_kw','size'),
               mae_kw=('abs_residual_kw','mean'),absolute_residual_sum_kw=('abs_residual_kw','sum'),
               large_residual_n=('large_residual','sum'),future_set_changed_n=('future_set_changed','sum'),
               future_mode_changed_n=('future_mode_changed','sum'),target_ac_zero_n=('target_ac_zero','sum'),
               left_censored_n=('left_censored_age','sum')).reset_index()
    totals=s.groupby('partition').abs_residual_kw.sum()
    groups['absolute_residual_sum_share']=groups.absolute_residual_sum_kw/groups.partition.map(totals)
    groups['large_residual_rate']=groups.large_residual_n/groups.n
    exact_age=s.assign(age_bin=np.minimum(s.logged_pq_age_s,10)).groupby(['partition','age_bin']).agg(
                n=('abs_residual_kw','size'),mae_kw=('abs_residual_kw','mean'),large_n=('large_residual','sum')).reset_index()
    # All original predictions independently streamed to verify this diagnostic population/arithmetic.
    streamed={'fit':[0,0.],'validation':[0,0.],'evaluation':[0,0.]}
    for c in pd.read_csv(baseline/'predictions.csv.gz',chunksize=100000,float_precision='round_trip'):
        idx=c.sample_id.str.rsplit('_',n=1).str[-1].astype(int).to_numpy()
        current=pq[idx]
        expected=np.where(current,setting[idx],ac[idx])
        if not np.array_equal(c.B_SET_predicted_kw.to_numpy(),expected) or not np.array_equal(c.ac_tp1_reference_kw.to_numpy(),ac[idx+1]):
            raise ValueError('Original B_SET predictions/reference differ from raw')
        for name in streamed:
            mask=c.partition.eq(name).to_numpy()&current
            streamed[name][0]+=int(mask.sum())
            streamed[name][1]+=float(np.abs(c.B_SET_predicted_kw.to_numpy()[mask]-c.ac_tp1_reference_kw.to_numpy()[mask]).sum())
    for name,(count,total) in streamed.items():
        raw=s[s.partition.eq(name)]
        if count!=len(raw) or abs(total-float(raw.abs_residual_kw.sum()))>1e-8:
            raise ValueError('Frozen-prediction and native population counts/sums differ')
    evaluation=s[s.partition.eq('evaluation')].copy()
    top=evaluation.iloc[np.lexsort((evaluation.native_origin_row.to_numpy(),-evaluation.abs_residual_kw.to_numpy()))[:p['top_rows']]].copy()
    contexts=[]
    first_nonzero=[]
    for rank,origin in enumerate(top.native_origin_row,1):
        radius=p['context_seconds_before_and_after']
        native=f.iloc[max(0,origin-radius):min(len(f),origin+radius+1)].copy()
        native['selected_origin_row']=origin;native['case_rank']=rank
        native['relative_to_origin_s']=native.index-origin
        native['logged_pq_age_s']=ages[native.index]
        native['soc_pct']=native.SOC/10
        native['dc_current_a']=native.I_DC_Batt/10
        native['dc_voltage_v']=native.U_DC_Batt/10
        native['reconstructed_dc_kw']=native.dc_current_a*native.dc_voltage_v/1000
        contexts.append(native)
        forward=np.arange(origin+1,min(len(f),origin+11))
        nonzero=forward[np.abs(ac[forward])>50]
        first_nonzero.append(int(nonzero[0]-origin) if len(nonzero) else None)
    j=top.native_origin_row.to_numpy()
    top['set_t_kw']=setting[j];top['set_tp1_kw']=setting[j+1];top['ac_t_kw']=ac[j];top['ac_tp1_kw']=ac[j+1]
    top['command_difference_term_kw']=setting[j].astype(float)-setting[j+1]
    top['contemporaneous_difference_term_kw']=setting[j+1].astype(float)-ac[j+1]
    top['first_abs_ac_gt50_logged_offset_s_within10']=first_nonzero
    if not np.array_equal(top.signed_residual_kw,top.command_difference_term_kw+top.contemporaneous_difference_term_kw):
        raise ValueError('Signed difference identity fails')
    groups.to_csv(output/'age_group_metrics.csv',index=False,float_format='%.17g')
    exact_age.to_csv(output/'exact_age_metrics.csv',index=False,float_format='%.17g')
    top.to_csv(output/'top20_native_cases.csv',index=False,float_format='%.17g')
    pd.concat(contexts,ignore_index=True).to_csv(output/'top20_native_contexts.csv',index=False,float_format='%.17g')
    large=evaluation[evaluation.large_residual].copy()
    large.to_csv(output/'large_evaluation_residual_origins.csv',index=False,float_format='%.17g')
    pos=large.native_origin_row.to_numpy()
    episode_count=int(np.sum(np.r_[True,np.diff(pos)>1])) if len(pos) else 0
    frozen_after={name:sha(baseline/name) for name in br['output_sha256']}
    if frozen_after!=frozen_before or sha(csv_path)!=source['csv_sha256']:
        raise ValueError('Diagnostic changed original baseline/source')
    (output/'protocol_snapshot.json').write_bytes(protocol.read_bytes())
    (output/'diagnostic_code_snapshot.py').write_bytes(Path(__file__).read_bytes())
    names=['age_group_metrics.csv','exact_age_metrics.csv','top20_native_cases.csv','top20_native_contexts.csv',
           'large_evaluation_residual_origins.csv','protocol_snapshot.json','diagnostic_code_snapshot.py']
    receipt={'run_id':run_id,'protocol_id':p['protocol_id'],'status':'posthoc_descriptive_residual_audit_complete',
             'source_csv_sha256':source['csv_sha256'],'baseline_run':p['baseline_run'],
             'original_baseline_artifacts_unchanged':True,'native_and_saved_prediction_counts_sums_match':True,
             'current_pq_counts':{name:value[0] for name,value in streamed.items()},
             'evaluation_abs_residual_quantiles_kw':{str(q):float(evaluation.abs_residual_kw.quantile(q)) for q in [.5,.9,.95,.99,1.]},
             'evaluation_large_residual_count':len(large),'evaluation_large_residual_adjacent_origin_clusters':episode_count,
             'top20_age_groups':top.age_group.value_counts().to_dict(),
             'top20_future_set_changed':int(top.future_set_changed.sum()),'top20_future_mode_changed':int(top.future_mode_changed.sum()),
             'top20_target_ac_zero':int(top.target_ac_zero.sum()),'signed_identity_pass':True,
             'group_metrics':groups.to_dict('records'),'output_sha256':{name:sha(output/name) for name in names},
             'limitations':'posthoc observed phase association; no causal fault/delay inference, no future features, no refit or excluded residuals; clusters not independent tasks'}
    (output/'audit_receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(receipt,ensure_ascii=False,indent=2))


if __name__=='__main__':
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id',required=True)
    audit(parser.parse_args().run_id)
