"""Prepare fixed four-event gap-safe spans without reading numeric references or scoring."""
from pathlib import Path
import argparse,hashlib,json,sys
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parent
pa=argparse.ArgumentParser();pa.add_argument('--run-id',required=True);args=pa.parse_args()
if not args.run_id.isidentifier(): raise ValueError('simple ID required')
OUT=ROOT/'downloads/rwth_home_local_span_20261014'/'samples'/args.run_id
if OUT.exists(): raise FileExistsError(OUT)
sha=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
pf=ROOT/'home_capacity_local_span_protocol_v1.json';p=json.loads(pf.read_text('utf-8'))
if sha(pf)!=json.loads((ROOT/'downloads/rwth_home_local_span_20261014/freeze_receipt_01.json').read_text('utf-8'))['protocol_sha256']:raise ValueError('protocol changed')
all_rests=[];all_pairs=[];all_orphans=[];all_resets=[];all_blocks=[];features=[];summary=[]
for e in p['events']:
    sid=e['sample_id']; start=pd.Timestamp(e['information']['history_start_inclusive']);cutoff=pd.Timestamp(e['information']['history_end_exclusive']);parts=[]
    for src in e['source_members']:
        if sha(ROOT/src['path'])!=src['sha256']:raise ValueError('source changed')
        for chunk in pd.read_csv(ROOT/src['path'],chunksize=250000):
            ct=pd.to_datetime(chunk['Time'],format='%d-%b-%Y %H:%M:%S')
            mask=(ct>=start)&(ct<cutoff)
            if mask.any():parts.append(chunk.loc[mask].assign(native_time=ct[mask]))
    if not parts:raise ValueError('empty native history requires explicit no-observation handling')
    f=pd.concat(parts,ignore_index=True);t=f['native_time'];seconds=t.to_numpy(dtype='datetime64[s]').astype(np.int64)
    if (np.diff(seconds)<=0).any():raise ValueError('duplicate/backward time, do not repair')
    bounds=np.r_[0,np.flatnonzero(np.diff(seconds)!=1)+1,len(f)]
    cols=['P_in_W','V_in_V','I_in_A','T_Bat_in_C','T_Room_in_C'];finite=np.isfinite(f[cols].to_numpy(dtype=float)).all(axis=1)
    flags=f['Interpolated'].to_numpy();valid=finite&(flags==0)
    if not np.isin(flags,[0,1]).all():raise ValueError('invalid flag')
    current=f['I_in_A'].to_numpy(dtype=float);voltage=f['V_in_V'].to_numpy(dtype=float)
    rp=p['rest_proxy'];rest=valid&(np.abs(current)<=rp['absolute_current_max_a']);pairs=[];rests=[];orphans=[];resets=[]
    for bi,(lo,hi) in enumerate(zip(bounds[:-1],bounds[1:])):
        bid=f'block_{bi:02}';changes=np.diff(np.r_[False,rest[lo:hi],False].astype(np.int8));aa=np.flatnonzero(changes==1)+lo;bb=np.flatnonzero(changes==-1)+lo
        anchors=[]
        for a,b in zip(aa,bb):
            r={'sample_id':sid,'block_id':bid,'rest_id':f'rest_{len(rests):05}','start':str(t.iloc[a]),'end_exclusive':str(t.iloc[b-1]+pd.Timedelta(seconds=1)),
                'observed_seconds':int(b-a),'left_censored':bool(a==lo),'right_censored':bool(b==hi),'kind':'too_short','anchor_time':None,'voltage_proxy_cell_v':None,'used_for_pairing':False}
            if b-a>=rp['minimum_consecutive_seconds']:
                at=int(a+rp['minimum_consecutive_seconds']-1);vc=float(np.median(voltage[at-rp['voltage_tail_seconds']+1:at+1])/p['source_metadata']['series_cells'])
                kind='high' if vc>=rp['high_voltage_min_v_per_series_cell'] else 'low' if vc<=rp['low_voltage_max_v_per_series_cell'] else 'middle'
                r.update(kind=kind,anchor_time=str(t.iloc[at]),voltage_proxy_cell_v=vc,used_for_pairing=not r['left_censored'])
                if not r['left_censored']:anchors.append({'index':at,'time':str(t.iloc[at]),'kind':kind})
            rests.append(r)
        pending=None
        for a in anchors:
            if a['kind']=='high':
                if pending:resets.append({'sample_id':sid,'block_id':bid,'high_anchor':pending['time'],'reason':'replaced_by_high','boundary':a['time']})
                pending=a
            elif a['kind']=='low':
                if pending is None:orphans.append({'sample_id':sid,'block_id':bid,'low_anchor':a['time'],'reason':'no_high_in_same_block'})
                else:
                    x,y=pending['index'],a['index'];bad=int((~valid[x:y+1]).sum());cap=None if bad else float(-np.sum(current[x:y])/3600);energy=None if bad else float(-np.sum(current[x:y]*voltage[x:y])/3600000)
                    status='quality_failure' if bad else 'nonpositive_net' if cap<=0 or energy<=0 else 'eligible'
                    pairs.append({'sample_id':sid,'pair_id':f'pair_{len(pairs):04}','block_id':bid,'high_anchor':pending['time'],'low_anchor':a['time'],
                        'duration_seconds':y-x,'bad_rows_inclusive':bad,'status':status,'net_capacity_ah':cap,'net_UI_energy_kwh':energy,
                        'gross_charge_ah':None if bad else float(np.maximum(current[x:y],0).sum()/3600),'gross_discharge_ah':None if bad else float(np.maximum(-current[x:y],0).sum()/3600)})
                    pending=None
        if pending:resets.append({'sample_id':sid,'block_id':bid,'high_anchor':pending['time'],'reason':'block_end_reset','boundary':str(t.iloc[hi-1]+pd.Timedelta(seconds=1))})
        all_blocks.append({'sample_id':sid,'block_id':bid,'start':str(t.iloc[lo]),'end_exclusive':str(t.iloc[hi-1]+pd.Timedelta(seconds=1)),'native_rows':int(hi-lo),'bad_rows':int((~valid[lo:hi]).sum())})
    eligible=[q for q in pairs if q['status']=='eligible'];selected=max(eligible,key=lambda q:(q['low_anchor'],q['high_anchor'])) if eligible else None
    low=None if selected is None else pd.Timestamp(selected['low_anchor']);test=pd.Timestamp(e['reference']['test_start_native'])
    feature={'sample_id':sid,'test_start_native':str(test),'history_start':str(start),'history_cutoff':str(cutoff),'history_rows_observed':len(f),
        'history_seconds_expected':int((cutoff-start).total_seconds()),'continuous_blocks':len(bounds)-1,'proxy_available':selected is not None,
        'unavailable_reason':'' if selected else 'no_eligible_complete_local_span','selected_pair_id':None if selected is None else selected['pair_id'],
        'selected_low_anchor':None if low is None else str(low),'capacity_ah':None if selected is None else selected['net_capacity_ah'],'energy_kwh':None if selected is None else selected['net_UI_energy_kwh'],
        'age_at_cutoff_seconds':None if low is None else int((cutoff-low).total_seconds()),'age_at_test_seconds':None if low is None else int((test-low).total_seconds())}
    features.append(feature);summary.append({'sample_id':sid,'rests':len(rests),'anchors':sum(r['kind']!='too_short' for r in rests),'left_censored_anchors':sum(r['kind']!='too_short' and r['left_censored'] for r in rests),
        'pairs':len(pairs),'eligible_pairs':len(eligible),'orphan_lows':len(orphans),'high_resets':len(resets),'selected':selected})
    all_rests+=rests;all_pairs+=pairs;all_orphans+=orphans;all_resets+=resets
    print(json.dumps({'sample_id':sid,'observed_rows':len(f),'selected':selected},ensure_ascii=False),flush=True)
OUT.mkdir(parents=True)
for name,records,empty_cols in [('features.csv',features,[]),('blocks.csv',all_blocks,[]),('rests.csv',all_rests,[]),('pairs.csv',all_pairs,[]),
    ('orphan_lows.csv',all_orphans,['sample_id','block_id','low_anchor','reason']),('high_resets.csv',all_resets,['sample_id','block_id','high_anchor','reason','boundary'])]:
    pd.DataFrame(records,columns=list(records[0]) if records else empty_cols).to_csv(OUT/name,index=False)
(OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'protocol_snapshot.json').write_text(json.dumps(p,ensure_ascii=False,indent=2),encoding='utf-8')
receipt={'run_id':args.run_id,'protocol_sha256':sha(pf),'code_sha256':sha(Path(__file__)),'data_card_version':p['data_card_version'],
    'python':sys.version,'pandas':pd.__version__,'numpy':np.__version__,'events':4,'numeric_reference_not_read':True,
    'artifacts':{x.name:sha(x) for x in OUT.iterdir() if x.is_file()}}
(OUT/'receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
