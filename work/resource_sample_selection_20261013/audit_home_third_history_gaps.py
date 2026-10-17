"""Diagnose fixed-window missing time and observable anchors, never compute capacity or score."""
from pathlib import Path
from datetime import datetime, timezone
import argparse,hashlib,json,sys
import pandas as pd
import numpy as np

ROOT=Path(__file__).resolve().parent
pa=argparse.ArgumentParser(); pa.add_argument('--run-id',required=True); args=pa.parse_args()
if not args.run_id.isidentifier(): raise ValueError('simple unique ID required')
OUT=ROOT/'downloads/rwth_home_third_test_20261014'/'gap_diagnostics'/args.run_id
if OUT.exists(): raise FileExistsError(OUT)
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
pf=ROOT/'home_capacity_crossperiod_protocol_v3.json'
p=json.loads(pf.read_text('utf-8'))
admission_path=ROOT/p['source']['relative_directory']/p['source']['admission_receipt']
admission=json.loads(admission_path.read_text('utf-8'))
start=pd.Timestamp(p['information']['history_start_inclusive']); end=pd.Timestamp(p['information']['history_end_exclusive'])
sources=admission['source_members']; pieces=[]
for src in sources:
    path=ROOT/src['path']
    if sha(path)!=src['sha256']: raise ValueError('source changed')
    for f in pd.read_csv(path,chunksize=100000):
        t=pd.to_datetime(f['Time'],format='%d-%b-%Y %H:%M:%S',errors='raise')
        mask=(t>=start)&(t<end)
        if mask.any(): pieces.append(f.loc[mask].assign(native_time=t[mask]))
frame=pd.concat(pieces,ignore_index=True)
if len(frame)!=admission['history_rows']: raise ValueError('history row count changed')
t=frame['native_time']; sec=t.to_numpy(dtype='datetime64[s]').astype(np.int64)
if (np.diff(sec)<=0).any(): raise ValueError('nonincreasing native time; explicit diagnosis required')
borders=np.r_[0,np.flatnonzero(np.diff(sec)!=1)+1,len(frame)]
expected=int((end-start).total_seconds()); rp=p['rest_proxy']
numeric=frame[['P_in_W','V_in_V','I_in_A','T_Bat_in_C','T_Room_in_C']].to_numpy(dtype=float)
valid=np.isfinite(numeric).all(axis=1)&(frame['Interpolated'].to_numpy()==0)
current=frame['I_in_A'].to_numpy(dtype=float); voltage=frame['V_in_V'].to_numpy(dtype=float)
rest=valid&(np.abs(current)<=rp['absolute_current_max_a'])
blocks=[]; gaps=[]; anchors=[]; rests=[]; pairs=[]; orphans=[]; resets=[]
cursor=start
for block_index,(lo,hi) in enumerate(zip(borders[:-1],borders[1:])):
    block_id=f'block_{block_index:02}'
    first=t.iloc[lo]; after=t.iloc[hi-1]+pd.Timedelta(seconds=1)
    if first>cursor:
        gaps.append({'gap_id':f'gap_{len(gaps):02}','start_inclusive':str(cursor),'end_exclusive':str(first),
                     'missing_seconds':int((first-cursor).total_seconds()),'kind':'leading' if block_index==0 else 'internal'})
    cursor=after
    subset=rest[lo:hi]
    transitions=np.diff(np.r_[False,subset,False].astype(np.int8))
    starts=np.flatnonzero(transitions==1)+lo; ends=np.flatnonzero(transitions==-1)+lo
    ba=[]
    for rlo,rhi in zip(starts,ends):
        rec={'rest_id':f'rest_{len(rests):04}','block_id':block_id,'start_inclusive':str(t.iloc[rlo]),
             'end_exclusive':str(t.iloc[rhi-1]+pd.Timedelta(seconds=1)),'observed_seconds':int(rhi-rlo),
             'left_censored':bool(rlo==lo),'right_censored':bool(rhi==hi),'status':'too_short',
             'anchor_time':None,'voltage_proxy_per_cell_v':None}
        if rhi-rlo>=rp['minimum_consecutive_seconds']:
            at=int(rlo+rp['minimum_consecutive_seconds']-1)
            vc=float(np.median(voltage[at-rp['voltage_tail_seconds']+1:at+1])/p['source']['series_cells'])
            kind='high' if vc>=rp['high_voltage_min_v_per_series_cell'] else 'low' if vc<=rp['low_voltage_max_v_per_series_cell'] else 'middle'
            rec.update(status=kind,anchor_time=str(t.iloc[at]),voltage_proxy_per_cell_v=vc)
            a={'rest_id':rec['rest_id'],'block_id':block_id,'kind':kind,'anchor_time':str(t.iloc[at]),
               'voltage_proxy_per_cell_v':vc,'rest_left_censored':rec['left_censored'],'raw_index':at}
            anchors.append(a); ba.append(a)
        rests.append(rec)
    # Reset at every missing-time boundary; no endpoint may cross a gap.
    pending=None; n_pairs_before=len(pairs); n_orphan_before=len(orphans)
    for a in ba:
        if a['kind']=='high':
            if pending is not None:
                resets.append({'block_id':block_id,'high_anchor':pending['anchor_time'],'reason':'replaced_by_later_high','next_time':a['anchor_time']})
            pending=a
        elif a['kind']=='low':
            if pending is None:
                orphans.append({'block_id':block_id,'low_anchor':a['anchor_time'],'reason':'no_known_high_within_same_observed_block'})
            else:
                x,y=pending['raw_index'],a['raw_index']
                bad=int((~valid[x:y+1]).sum())
                pairs.append({'pair_id':f'pair_{len(pairs):03}','block_id':block_id,'high_anchor':pending['anchor_time'],
                    'low_anchor':a['anchor_time'],'observed_seconds':y-x,'bad_rows_inclusive':bad,
                    'start_rest_left_censored':pending['rest_left_censored'],
                    'status':'quality_failure' if bad else 'observed_endpoint_pair_only_not_capacity_prediction'})
                pending=None
    if pending is not None:
        resets.append({'block_id':block_id,'high_anchor':pending['anchor_time'],'reason':'unclosed_at_observation_boundary','next_time':str(after)})
    blocks.append({'block_id':block_id,'start_inclusive':str(first),'end_exclusive':str(after),'native_rows':int(hi-lo),
        'duration_seconds':int((after-first).total_seconds()),'bad_rows':int((~valid[lo:hi]).sum()),
        'rest_candidates':len(starts),'anchor_count':len(ba),'high_anchors':sum(a['kind']=='high' for a in ba),
        'low_anchors':sum(a['kind']=='low' for a in ba),'middle_anchors':sum(a['kind']=='middle' for a in ba),
        'same_block_endpoint_pairs':len(pairs)-n_pairs_before,'orphan_low_anchors':len(orphans)-n_orphan_before})
if cursor<end:
    gaps.append({'gap_id':f'gap_{len(gaps):02}','start_inclusive':str(cursor),'end_exclusive':str(end),
                 'missing_seconds':int((end-cursor).total_seconds()),'kind':'trailing'})
assert sum(g['missing_seconds'] for g in gaps)+len(frame)==expected
summary={'purpose':'quality diagnosis only; no history feature replacement, net I/UI integration, reference reading, prediction or scoring',
    'fixed_protocol_sha256':sha(pf),'source_members':sources,'history_expected_seconds':expected,'observed_rows':len(frame),
    'missing_seconds':sum(g['missing_seconds'] for g in gaps),'observed_fraction':len(frame)/expected,
    'continuous_blocks':len(blocks),'internal_gaps':sum(g['kind']=='internal' for g in gaps),'all_gap_intervals':len(gaps),
    'longest_continuous_seconds':max(b['native_rows'] for b in blocks),'longest_gap_seconds':max(g['missing_seconds'] for g in gaps),
    'rest_candidates':len(rests),'anchors':len(anchors),'anchor_counts':{kind:sum(a['kind']==kind for a in anchors) for kind in ('high','low','middle')},
    'same_block_endpoint_pairs':len(pairs),'orphan_low_anchors':len(orphans),'high_reset_records':len(resets),
    'quality_failed_endpoint_pairs':sum(q['status']=='quality_failure' for q in pairs),
    'left_censored_anchors':sum(a['rest_left_censored'] for a in anchors),
    'limitations':'observed run first confirmation within each block, actual rest onset can be unknown at block left; no cross-gap bridge, no integral or label; diagnostic endpoints do not prove SOC full/empty'}
OUT.mkdir(parents=True)
def table(name,records,columns): pd.DataFrame(records,columns=columns).to_csv(OUT/name,index=False)
for name,records,cols in [
    ('blocks.csv',blocks,['block_id','start_inclusive','end_exclusive','native_rows','duration_seconds','bad_rows','rest_candidates','anchor_count','high_anchors','low_anchors','middle_anchors','same_block_endpoint_pairs','orphan_low_anchors']),
    ('gaps.csv',gaps,['gap_id','start_inclusive','end_exclusive','missing_seconds','kind']),
    ('rests.csv',rests,['rest_id','block_id','start_inclusive','end_exclusive','observed_seconds','left_censored','right_censored','status','anchor_time','voltage_proxy_per_cell_v']),
    ('anchors.csv',anchors,['rest_id','block_id','kind','anchor_time','voltage_proxy_per_cell_v','rest_left_censored','raw_index']),
    ('endpoint_pairs.csv',pairs,['pair_id','block_id','high_anchor','low_anchor','observed_seconds','bad_rows_inclusive','start_rest_left_censored','status']),
    ('orphan_lows.csv',orphans,['block_id','low_anchor','reason']),
    ('high_resets.csv',resets,['block_id','high_anchor','reason','next_time'])]: table(name,records,cols)
(OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'rules_snapshot.json').write_text(json.dumps({'fixed_window':p['information'],'rest_proxy':rp,'diagnostic_pairing':'v1 within each observed block; reset on each time gap; no integrals or target file reading'},ensure_ascii=False,indent=2),encoding='utf-8')
receipt={'run_id':args.run_id,'created_at_utc':datetime.now(timezone.utc).isoformat(),'code_sha256':sha(Path(__file__)),
    'python':sys.version,'pandas':pd.__version__,'numpy':np.__version__,'source_members':sources,'fixed_protocol_sha256':sha(pf),
    'admission_sha256':sha(admission_path),'artifacts':{f.name:sha(f) for f in OUT.iterdir() if f.is_file()}}
(OUT/'receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False))
