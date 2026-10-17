"""Read-only diagnosis of frozen failed span and its whole observed block; no correction or scoring."""
from pathlib import Path
import argparse,hashlib,json,sys
import pandas as pd
import numpy as np
ROOT=Path(__file__).resolve().parent
pa=argparse.ArgumentParser();pa.add_argument('--run-id',required=True);args=pa.parse_args()
if not args.run_id.isidentifier():raise ValueError('simple ID required')
OUT=ROOT/'downloads/rwth_home_local_span_20261014'/'failure_diagnostics'/args.run_id
if OUT.exists():raise FileExistsError(OUT)
sha=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
pf=ROOT/'home_capacity_local_span_protocol_v1.json';p=json.loads(pf.read_text('utf-8'))
e=next(e for e in p['events'] if '20190701' in e['sample_id'])
sample=ROOT/'downloads/rwth_home_local_span_20261014/samples/PREP_HOME_LOCAL_20261014_01'
receipt=json.loads((sample/'receipt.json').read_text('utf-8'))
for name,h in receipt['artifacts'].items():
    if sha(sample/name)!=h:raise ValueError('frozen sample changed')
f=pd.read_csv(sample/'features.csv');f=f.loc[f['sample_id']==e['sample_id']].iloc[0]
pairs=pd.read_csv(sample/'pairs.csv');pair=pairs.loc[(pairs['sample_id']==e['sample_id'])&(pairs['pair_id']==f['selected_pair_id'])].iloc[0]
blocks=pd.read_csv(sample/'blocks.csv');block=blocks.loc[(blocks['sample_id']==e['sample_id'])&(blocks['block_id']==pair['block_id'])].iloc[0]
begin=pd.Timestamp(block['start']);end=pd.Timestamp(block['end_exclusive']);high=pd.Timestamp(pair['high_anchor']);low=pd.Timestamp(pair['low_anchor'])
pieces=[]
for src in e['source_members']:
    path=ROOT/src['path']
    if sha(path)!=src['sha256']:raise ValueError('source changed')
    for c in pd.read_csv(path,chunksize=100000):
        t=pd.to_datetime(c['Time'],format='%d-%b-%Y %H:%M:%S');mask=(t>=begin)&(t<end)
        if mask.any():pieces.append(c.loc[mask].assign(native_time=t[mask]))
data=pd.concat(pieces,ignore_index=True);t=data['native_time'];u=data['V_in_V'].to_numpy();i=data['I_in_A'].to_numpy();power=data['P_in_W'].to_numpy();ui=u*i
if len(data)!=int((end-begin).total_seconds()) or not np.all(np.diff(t.to_numpy(dtype='datetime64[s]').astype(np.int64))==1):raise ValueError('block time changed')
if not np.isfinite(data[['P_in_W','V_in_V','I_in_A','T_Bat_in_C','T_Room_in_C']].to_numpy()).all() or (data['Interpolated']!=0).any():raise ValueError('block quality changed')
def stats(mask):
    x=data.loc[mask];a=x['I_in_A'].to_numpy();v=x['V_in_V'].to_numpy();w=x['P_in_W'].to_numpy();d=w-a*v
    return {'rows':len(x),'start':str(x['native_time'].iloc[0]),'last':str(x['native_time'].iloc[-1]),
        'U_min_V':float(v.min()),'U_max_V':float(v.max()),'I_min_A':float(a.min()),'I_max_A':float(a.max()),'P_min_W':float(w.min()),'P_max_W':float(w.max()),
        'net_Ah':float(-a.sum()/3600),'net_UI_kWh':float(-(a*v).sum()/3600000),'net_P_kWh':float(-w.sum()/3600000),
        'P_minus_UI_abs_mean_W':float(np.abs(d).mean()),'P_minus_UI_abs_max_W':float(np.abs(d).max()),
        'seconds_abs_I_le_0p15':int((np.abs(a)<=0.15).sum()),'seconds_charge':int((a>0).sum()),'seconds_discharge':int((a<0).sum())}
summary={'purpose':'diagnose already-frozen failed interval, no threshold/lag/unit calibration or revised capacity prediction',
    'protocol_sha256':sha(pf),'pair':pair.to_dict(),'block':block.to_dict(),
    'whole_observed_block':stats(np.ones(len(data),dtype=bool)),'frozen_pair_integral':stats((t>=high)&(t<low)),
    'context_rules':'entire original observed block, all one-second U jumps, top 10 by abs jump as descriptive extremes; fixed ±5-second raw contexts, not exclusion/selection',
    'native_time_zone':'unchanged source strings, absolute timezone unknown'}
data['UI_reconstructed_W']=ui;data['P_minus_UI_W']=power-ui
data['dU_V']=data['V_in_V'].diff();data['dI_A']=data['I_in_A'].diff();data['dP_W']=data['P_in_W'].diff()
top=data['dU_V'].abs().nlargest(10).index
events=[];contexts=[]
for rank,j in enumerate(top,1):
    r=data.iloc[j];before=data.iloc[j-1]
    events.append({'rank':rank,'time':str(r['native_time']),'dU_V':float(r['dU_V']),'previous_U_V':float(before['V_in_V']),'U_V':float(r['V_in_V']),
        'previous_I_A':float(before['I_in_A']),'I_A':float(r['I_in_A']),'previous_P_W':float(before['P_in_W']),'P_W':float(r['P_in_W']),
        'inside_frozen_pair':bool(high<=r['native_time']<low)})
    x=data.iloc[max(0,j-5):min(len(data),j+6)].copy();x.insert(0,'jump_rank',rank);contexts.append(x)
rests=pd.read_csv(sample/'rests.csv');anchors=rests.loc[(rests['sample_id']==e['sample_id'])&(rests['block_id']==pair['block_id'])&(rests['kind'].isin(['high','low']))]
endpoints=[]
for _,r in anchors.iterrows():
    at=pd.Timestamp(r['anchor_time']);a=pd.Timestamp(r['start']);b=pd.Timestamp(r['end_exclusive']);mask=(t>=a)&(t<b)
    x=data.loc[mask];tail=x.loc[x['native_time']<=at].tail(60)
    endpoints.append({'kind':r['kind'],'rest_start':str(a),'anchor':str(at),'rest_end_exclusive':str(b),'observed_seconds':len(x),
        'voltage_first_V':float(x['V_in_V'].iloc[0]),'voltage_at_anchor_V':float(x.loc[x['native_time']==at,'V_in_V'].iloc[0]),
        'voltage_last_V':float(x['V_in_V'].iloc[-1]),'voltage_min_V':float(x['V_in_V'].min()),'voltage_max_V':float(x['V_in_V'].max()),
        'max_abs_I_A':float(x['I_in_A'].abs().max()),'tail60_voltage_range_V':float(tail['V_in_V'].max()-tail['V_in_V'].min()),
        'left_censored':bool(r['left_censored']),'selected_endpoint':bool(at in [high,low])})
summary['largest_voltage_steps']=events;summary['rest_endpoint_diagnostics']=endpoints
OUT.mkdir(parents=True)
data.to_csv(OUT/'observed_block_raw_and_derived.csv',index=False)
pd.DataFrame(events).to_csv(OUT/'largest_voltage_steps.csv',index=False)
pd.concat(contexts,ignore_index=True).to_csv(OUT/'step_raw_contexts.csv',index=False)
pd.DataFrame(endpoints).to_csv(OUT/'rest_endpoint_diagnostics.csv',index=False)
minute=data.set_index('native_time')[['P_in_W','V_in_V','I_in_A','UI_reconstructed_W','P_minus_UI_W']].resample('1min').mean();minute.to_csv(OUT/'minute_view_diagnostic_only.csv')
(OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'receipt.json').write_text(json.dumps({'run_id':args.run_id,'code_sha256':sha(Path(__file__)),'protocol_sha256':sha(pf),
    'source_members':e['source_members'],'sample_artifacts':receipt['artifacts'],'python':sys.version,'pandas':pd.__version__,'numpy':np.__version__,
    'artifacts':{x.name:sha(x) for x in OUT.iterdir() if x.is_file()}},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False))
