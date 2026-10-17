"""Execute frozen eight-endpoint context diagnosis without changing predictions."""
from pathlib import Path
import argparse
import hashlib
import json
import sys
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parent
pa=argparse.ArgumentParser();pa.add_argument('--run-id',required=True);a=pa.parse_args()
if not a.run_id.isidentifier():raise ValueError('simple unique ID required')
OUT=ROOT/'downloads/rwth_home_endpoint_context_20261015'/a.run_id
if OUT.exists():raise FileExistsError(OUT)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
pf=ROOT/'home_endpoint_context_diagnostic_protocol_v1.json'
if sha(pf)!='d94ee1ba95b0d7b06a5f8c0095cb406ffc4a0bf174acf4f1358b8fdb61d4c034':raise ValueError('frozen protocol changed')
p=json.loads(pf.read_text('utf-8'))
sample=ROOT/'downloads/rwth_home_local_span_20261014/samples'/p['sample_run']
for name,h in p['sample_artifacts'].items():
    if sha(sample/name)!=h:raise ValueError('sample changed')
features=pd.read_csv(sample/'features.csv');pairs=pd.read_csv(sample/'pairs.csv');rests=pd.read_csv(sample/'rests.csv');blocks=pd.read_csv(sample/'blocks.csv')
all_records=[];contexts=[];events=[]
for e in p['events']:
    sid=e['sample_id'];begin=pd.Timestamp(e['information']['history_start_inclusive']);cutoff=pd.Timestamp(e['information']['history_end_exclusive'])
    parts=[]
    for src in e['source_members']:
        path=ROOT/src['path']
        if sha(path)!=src['sha256']:raise ValueError('raw source changed')
        for chunk in pd.read_csv(path,chunksize=250000):
            t=pd.to_datetime(chunk['Time'],format='%d-%b-%Y %H:%M:%S');m=(t>=begin)&(t<cutoff)
            if m.any():parts.append(chunk.loc[m].assign(native_time=t[m]))
    f=pd.concat(parts,ignore_index=True);t=f['native_time'];u=f['V_in_V'].to_numpy();current=f['I_in_A'].to_numpy()
    seconds=t.to_numpy(dtype='datetime64[s]').astype(np.int64)
    if (np.diff(seconds)<=0).any():raise ValueError('nonunique or backward timestamps')
    valid=np.isfinite(f[['P_in_W','V_in_V','I_in_A','T_Bat_in_C','T_Room_in_C']].to_numpy()).all(axis=1)&f['Interpolated'].eq(0).to_numpy()
    feature=features.loc[features['sample_id'].eq(sid)].iloc[0]
    selected=pairs.loc[pairs['sample_id'].eq(sid)&pairs['pair_id'].eq(feature['selected_pair_id'])]
    if len(selected)!=1:raise ValueError('fixed pair not unique')
    pair=selected.iloc[0];block=blocks.loc[blocks['sample_id'].eq(sid)&blocks['block_id'].eq(pair['block_id'])].iloc[0]
    lo=int(t.searchsorted(pd.Timestamp(block['start'])));hi=int(t.searchsorted(pd.Timestamp(block['end_exclusive'])))
    for kind,key in [('high','high_anchor'),('low','low_anchor')]:
        endpoint_id=sid+'_'+kind;at=pd.Timestamp(pair[key])
        r=rests.loc[rests['sample_id'].eq(sid)&rests['anchor_time'].eq(str(at))]
        if len(r)!=1:raise ValueError('fixed rest not unique')
        rest=r.iloc[0];left=int(t.searchsorted(pd.Timestamp(rest['start'])));right=int(t.searchsorted(pd.Timestamp(rest['end_exclusive'])));anchor=int(t.searchsorted(at))
        if not (lo<=left<=anchor<right<=hi):raise ValueError('rest outside original block')
        if not valid[left:right].all() or not (np.abs(current[left:right])<=.15).all():raise ValueError('stored rest quality differs')
        if right-left!=int(rest['observed_seconds']) or anchor-left!=299:raise ValueError('rest/anchor length differs')
        j=left
        while j>lo and valid[j-1] and abs(current[j-1])>.15:j-=1
        # Observed threshold transition is not evidence of a physical command/SOC boundary.
        onset_seen=j<left and j>lo and bool(valid[j-1]) and abs(current[j-1])<=.15
        reason='observed_rest_to_activity' if onset_seen else 'no_immediate_activity' if j==left else 'block_or_history_boundary' if j==lo else 'previous_quality_boundary'
        prior=current[j:left];positive=np.maximum(prior,0);negative=np.maximum(-prior,0)
        charge_s=int((prior>.15).sum());discharge_s=int((prior<-.15).sum())
        record={'sample_id':sid,'endpoint_id':endpoint_id,'kind':kind,'pair_id':pair['pair_id'],'block_id':pair['block_id'],
            'anchor':str(at),'rest_start':str(t.iloc[left]),'rest_end_exclusive':str(t.iloc[right-1]+pd.Timedelta(seconds=1)),
            'rest_seconds':right-left,'rest_left_censored':bool(rest['left_censored']),'rest_right_censored':bool(rest['right_censored']),
            'rest_U_first_V':float(u[left]),'rest_U_anchor_V':float(u[anchor]),'rest_U_last_V':float(u[right-1]),
            'rest_U_change_V':float(u[right-1]-u[left]),'rest_U_min_V':float(u[left:right].min()),'rest_U_max_V':float(u[left:right].max()),
            'rest_max_abs_I_A':float(np.abs(current[left:right]).max()),'anchor_tail60_U_range_V':float(np.ptp(u[anchor-59:anchor+1])),
            'anchor_tail60_U_median_V':float(np.median(u[anchor-59:anchor+1])),
            'preceding_activity_start':str(t.iloc[j]) if j<left else None,'preceding_activity_end_exclusive':str(t.iloc[left]),
            'preceding_activity_seconds':left-j,'preceding_activity_onset_observed':bool(onset_seen),'preceding_activity_boundary':reason,
            'preceding_activity_status':'observed_segment' if j<left else 'no_immediate_valid_activity',
            'preceding_charge_seconds':charge_s,'preceding_discharge_seconds':discharge_s,
            'preceding_direction':'mixed' if charge_s and discharge_s else 'charge' if charge_s else 'discharge' if discharge_s else 'unavailable',
            'preceding_gross_charge_Ah':float(positive.sum()/3600) if j<left else None,
            'preceding_gross_discharge_Ah':float(negative.sum()/3600) if j<left else None,
            'preceding_signed_Ah_charge_positive':float(prior.sum()/3600) if j<left else None,
            'preceding_U_first_V':float(u[j]) if j<left else None,'preceding_U_last_V':float(u[left-1]) if j<left else None,
            'history_cutoff':str(cutoff),'capacity_prediction_or_SOC_label':False}
        all_records.append(record)
        x=f.iloc[max(lo,j-1):min(hi,right+1)].copy();x.insert(0,'endpoint_id',endpoint_id)
        x['context_role']=np.where(x.index<j,'guard_before',np.where(x.index<left,'preceding_activity',np.where(x.index<right,'rest','guard_after')))
        contexts.append(x)
    events.append({'sample_id':sid,'history_rows':len(f),'endpoints':2,'source_members':e['source_members']})
    print(json.dumps({'event':sid,'endpoints_processed':2,'history_rows':len(f)},ensure_ascii=False),flush=True)
if len(all_records)!=8:raise ValueError('all fixed endpoints must be retained')
OUT.mkdir(parents=True)
pd.DataFrame(all_records).to_csv(OUT/'endpoint_contexts.csv',index=False)
pd.concat(contexts,ignore_index=True).to_csv(OUT/'raw_contexts_with_guards.csv',index=False)
summary={'run_id':a.run_id,'protocol_sha256':sha(pf),'endpoints':all_records,'events':events,
         'new_capacity_predictions_or_metrics':False,'label_values_read':False,'onset_observed_count':sum(r['preceding_activity_onset_observed'] for r in all_records),
         'right_censored_rest_count':sum(r['rest_right_censored'] for r in all_records),'interpretation':'diagnostic throughput only; no SOC conversion, threshold filtering, endpoint reselection or physical full-cycle confirmation'}
(OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'protocol_snapshot.json').write_text(pf.read_text('utf-8'),encoding='utf-8')
(OUT/'receipt.json').write_text(json.dumps({'run_id':a.run_id,'code_sha256':sha(Path(__file__)),'protocol_sha256':sha(pf),
    'python':sys.version,'numpy':np.__version__,'pandas':pd.__version__,'artifacts':{q.name:sha(q) for q in OUT.iterdir() if q.is_file()}},ensure_ascii=False,indent=2),encoding='utf-8')
print(pd.DataFrame(all_records)[['sample_id','kind','rest_seconds','rest_U_change_V','preceding_activity_seconds','preceding_direction','preceding_gross_charge_Ah','preceding_gross_discharge_Ah','preceding_activity_onset_observed']].to_string(index=False))
