"""Independent stdlib reconstruction of diagnostic blocks, rests and endpoint pairs."""
from pathlib import Path
from datetime import datetime,timedelta
from itertools import groupby
from statistics import median
import argparse,csv,hashlib,json,math
ROOT=Path(__file__).resolve().parent
pa=argparse.ArgumentParser()
for key in ('first-run','repeat-run','verification-id'): pa.add_argument('--'+key,required=True)
args=pa.parse_args()
if not all(v.isidentifier() for v in vars(args).values()): raise ValueError('simple IDs required')
BASE=ROOT/'downloads/rwth_home_third_test_20261014'/'gap_diagnostics'
first=BASE/args.first_run; second=BASE/args.repeat_run; out=BASE/f'{args.verification_id}.json'
if out.exists(): raise FileExistsError(out)
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
receipt=json.loads((first/'receipt.json').read_text('utf-8'))
for name,h in receipt['artifacts'].items():
    if sha(first/name)!=h or sha(second/name)!=h: raise ValueError(f'artifact changed or repeat differs: {name}')
p=json.loads((ROOT/'home_capacity_crossperiod_protocol_v3.json').read_text('utf-8'))
if sha(ROOT/'home_capacity_crossperiod_protocol_v3.json')!=receipt['fixed_protocol_sha256']: raise ValueError('protocol changed')
start=datetime.fromisoformat(p['information']['history_start_inclusive']); end=datetime.fromisoformat(p['information']['history_end_exclusive']); rp=p['rest_proxy']
groups=[]; current=[]; previous=None; ordinal=0
for src in receipt['source_members']:
    path=ROOT/src['path']
    if sha(path)!=src['sha256']: raise ValueError('source changed')
    with path.open(encoding='utf-8',newline='') as handle:
        for raw in csv.DictReader(handle):
            t=datetime.strptime(raw['Time'],'%d-%b-%Y %H:%M:%S')
            if t<start: continue
            if t>=end: break
            if previous is not None and t<=previous: raise ValueError('nonincreasing raw history')
            if previous is not None and t!=previous+timedelta(seconds=1):
                groups.append(current); current=[]
            vals=[float(raw[k]) for k in ('P_in_W','V_in_V','I_in_A','T_Bat_in_C','T_Room_in_C')]
            valid=all(math.isfinite(x) for x in vals) and raw['Interpolated']=='0'
            current.append({'time':t,'valid':valid,'rest':valid and abs(vals[2])<=rp['absolute_current_max_a'],'voltage':vals[1],'index':ordinal})
            previous=t; ordinal+=1
if current: groups.append(current)
blocks=[]; gaps=[]; rests=[]; anchors=[]; pairs=[]; orphans=[]; resets=[]; cursor=start
for bi,group in enumerate(groups):
    bid=f'block_{bi:02}'; begin=group[0]['time']; after=group[-1]['time']+timedelta(seconds=1)
    if begin>cursor:
        gaps.append({'gap_id':f'gap_{len(gaps):02}','start_inclusive':str(cursor),'end_exclusive':str(begin),'missing_seconds':int((begin-cursor).total_seconds()),'kind':'leading' if bi==0 else 'internal'})
    cursor=after; local_anchors=[]; rest_count=0
    for key,items in groupby(group,key=lambda x:x['rest']):
        run=list(items)
        if not key: continue
        rest_count+=1
        left=run[0]['index']==group[0]['index']; right=run[-1]['index']==group[-1]['index']
        r={'rest_id':f'rest_{len(rests):04}','block_id':bid,'start_inclusive':str(run[0]['time']),
           'end_exclusive':str(run[-1]['time']+timedelta(seconds=1)),'observed_seconds':len(run),'left_censored':left,'right_censored':right,
           'status':'too_short','anchor_time':None,'voltage_proxy_per_cell_v':None}
        if len(run)>=rp['minimum_consecutive_seconds']:
            at=rp['minimum_consecutive_seconds']-1
            vc=median(x['voltage'] for x in run[at-rp['voltage_tail_seconds']+1:at+1])/p['source']['series_cells']
            kind='high' if vc>=rp['high_voltage_min_v_per_series_cell'] else 'low' if vc<=rp['low_voltage_max_v_per_series_cell'] else 'middle'
            r.update(status=kind,anchor_time=str(run[at]['time']),voltage_proxy_per_cell_v=vc)
            a={'rest_id':r['rest_id'],'block_id':bid,'kind':kind,'anchor_time':r['anchor_time'],'voltage_proxy_per_cell_v':vc,'rest_left_censored':left,'raw_index':run[at]['index']}
            anchors.append(a); local_anchors.append(a)
        rests.append(r)
    pending=None; npairs=0; norphans=0
    for a in local_anchors:
        if a['kind']=='high':
            if pending is not None: resets.append({'block_id':bid,'high_anchor':pending['anchor_time'],'reason':'replaced_by_later_high','next_time':a['anchor_time']})
            pending=a
        elif a['kind']=='low':
            if pending is None:
                orphans.append({'block_id':bid,'low_anchor':a['anchor_time'],'reason':'no_known_high_within_same_observed_block'}); norphans+=1
            else:
                section=group[pending['raw_index']-group[0]['index']:a['raw_index']-group[0]['index']+1]
                bad=sum(not row['valid'] for row in section)
                pairs.append({'pair_id':f'pair_{len(pairs):03}','block_id':bid,'high_anchor':pending['anchor_time'],'low_anchor':a['anchor_time'],
                    'observed_seconds':a['raw_index']-pending['raw_index'],'bad_rows_inclusive':bad,'start_rest_left_censored':pending['rest_left_censored'],
                    'status':'quality_failure' if bad else 'observed_endpoint_pair_only_not_capacity_prediction'})
                pending=None; npairs+=1
    if pending is not None: resets.append({'block_id':bid,'high_anchor':pending['anchor_time'],'reason':'unclosed_at_observation_boundary','next_time':str(after)})
    blocks.append({'block_id':bid,'start_inclusive':str(begin),'end_exclusive':str(after),'native_rows':len(group),
        'duration_seconds':int((after-begin).total_seconds()),'bad_rows':sum(not row['valid'] for row in group),
        'rest_candidates':rest_count,'anchor_count':len(local_anchors),'high_anchors':sum(a['kind']=='high' for a in local_anchors),
        'low_anchors':sum(a['kind']=='low' for a in local_anchors),'middle_anchors':sum(a['kind']=='middle' for a in local_anchors),
        'same_block_endpoint_pairs':npairs,'orphan_low_anchors':norphans})
if cursor<end: gaps.append({'gap_id':f'gap_{len(gaps):02}','start_inclusive':str(cursor),'end_exclusive':str(end),'missing_seconds':int((end-cursor).total_seconds()),'kind':'trailing'})
maximum=0.0
for name,reconstructed in [('blocks.csv',blocks),('gaps.csv',gaps),('rests.csv',rests),('anchors.csv',anchors),('endpoint_pairs.csv',pairs),('orphan_lows.csv',orphans),('high_resets.csv',resets)]:
    with (first/name).open(encoding='utf-8',newline='') as handle: saved=list(csv.DictReader(handle))
    if len(saved)!=len(reconstructed): raise ValueError(f'count differs: {name}')
    for row,wanted in zip(saved,reconstructed):
        for k,v in wanted.items():
            if isinstance(v,float):
                error=abs(float(row[k])-v); maximum=max(maximum,error)
                if error>1e-12: raise ValueError(f'float differs: {name} {k}')
            elif row[k]!=('' if v is None else str(v)): raise ValueError(f'value differs: {name} {k}')
expected=int((end-start).total_seconds()); missing=sum(g['missing_seconds'] for g in gaps)
if ordinal+missing!=expected: raise ValueError('missing-time partition does not close')
summary=json.loads((first/'summary.json').read_text('utf-8'))
wanted={'history_expected_seconds':expected,'observed_rows':ordinal,'missing_seconds':missing,'observed_fraction':ordinal/expected,
    'continuous_blocks':len(blocks),'internal_gaps':max(0,len(blocks)-1),'all_gap_intervals':len(gaps),
    'longest_continuous_seconds':max(b['native_rows'] for b in blocks),'longest_gap_seconds':max(g['missing_seconds'] for g in gaps),
    'rest_candidates':len(rests),'anchors':len(anchors),'anchor_counts':{k:sum(a['kind']==k for a in anchors) for k in ('high','low','middle')},
    'same_block_endpoint_pairs':len(pairs),'orphan_low_anchors':len(orphans),'high_reset_records':len(resets),
    'quality_failed_endpoint_pairs':sum(x['status']=='quality_failure' for x in pairs),'left_censored_anchors':sum(a['rest_left_censored'] for a in anchors)}
for k,v in wanted.items():
    if summary[k]!=v: raise ValueError(f'summary differs: {k}')
result={'status':'passed','verification_id':args.verification_id,'first_run':args.first_run,'repeat_run':args.repeat_run,
    'scope':'stdlib raw native-time partition and groupby rest reconstruction; all seven tables and summary checked; no integration or reference reading',
    'repeat_equal_artifacts':len(receipt['artifacts']),'observed_rows':ordinal,'missing_seconds':missing,'continuous_blocks':len(blocks),
    'same_block_endpoint_pairs':len(pairs),'max_voltage_difference':maximum,'voltage_tolerance':1e-12,
    'source_members':receipt['source_members'],'fixed_protocol_sha256':receipt['fixed_protocol_sha256'],'code_sha256':sha(Path(__file__))}
out.open('x',encoding='utf-8').write(json.dumps(result,ensure_ascii=False,indent=2))
print(json.dumps(result,ensure_ascii=False))
