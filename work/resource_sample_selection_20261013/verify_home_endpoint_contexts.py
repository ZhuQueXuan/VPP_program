"""Independent raw CSV verification of all fixed endpoint contexts and maximality guards."""
from pathlib import Path
import argparse
import csv
import datetime as dt
import hashlib
import json
import math
import statistics

ROOT=Path(__file__).resolve().parent
pa=argparse.ArgumentParser();pa.add_argument('--audit-run',required=True);pa.add_argument('--verification-id',required=True);a=pa.parse_args()
if not a.audit_run.isidentifier() or not a.verification_id.isidentifier():raise ValueError('simple IDs required')
base=ROOT/'downloads/rwth_home_endpoint_context_20261015';folder=base/a.audit_run;out=base/(a.verification_id+'.json')
if out.exists():raise FileExistsError(out)
read=lambda p:json.loads(p.read_text('utf-8'));sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def table(p):
    with p.open(newline='',encoding='utf-8') as f:return list(csv.DictReader(f))
p=read(ROOT/'home_endpoint_context_diagnostic_protocol_v1.json');receipt=read(folder/'receipt.json');s=read(folder/'summary.json')
assert sha(ROOT/'home_endpoint_context_diagnostic_protocol_v1.json')==receipt['protocol_sha256']==s['protocol_sha256']
for name,h in receipt['artifacts'].items():assert sha(folder/name)==h,name
sample=ROOT/'downloads/rwth_home_local_span_20261014/samples'/p['sample_run']
for name,h in p['sample_artifacts'].items():assert sha(sample/name)==h,name
features=table(sample/'features.csv');pairs=table(sample/'pairs.csv');rests=table(sample/'rests.csv');blocks=table(sample/'blocks.csv')
contexts=table(folder/'raw_contexts_with_guards.csv');result_rows=table(folder/'endpoint_contexts.csv')
lookup={r['endpoint_id']:r for r in s['endpoints']};assert len(lookup)==len(result_rows)==8
months={name:n for n,name in enumerate(['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'],1)}
def native(text):return dt.datetime(int(text[7:11]),months[text[3:6]],int(text[:2]),int(text[12:14]),int(text[15:17]),int(text[18:20]))
iso=dt.datetime.fromisoformat;second=dt.timedelta(seconds=1);cols=['P_in_W','V_in_V','I_in_A','T_Bat_in_C','T_Room_in_C']
def valid(row):return int(row['Interpolated'])==0 and all(math.isfinite(float(row[c])) for c in cols)
max_difference=0.;raw_context_rows=0;all_rebuilt=[]
def compare(expected,actual):
    global max_difference
    assert set(expected)==set(actual)
    for k,v in expected.items():
        if isinstance(v,(int,float)) and not isinstance(v,bool):
            difference=abs(v-actual[k]);assert difference<=1e-9,(k,v,actual[k]);max_difference=max(max_difference,difference)
        else:assert v==actual[k],(k,v,actual[k])
for event in p['events']:
    sid=event['sample_id'];feature=next(r for r in features if r['sample_id']==sid)
    pair=next(r for r in pairs if r['sample_id']==sid and r['pair_id']==feature['selected_pair_id'])
    block=next(r for r in blocks if r['sample_id']==sid and r['block_id']==pair['block_id']);lo=iso(block['start']);hi=iso(block['end_exclusive'])
    targets={}
    for kind in ['high','low']:
        endpoint=sid+'_'+kind;reported=lookup[endpoint];r=next(x for x in rests if x['sample_id']==sid and x['anchor_time']==pair[kind+'_anchor'])
        # Candidate fetch bounds include an actual source guard on both sides. Maximality is verified below.
        left=iso(reported['preceding_activity_start']) if reported['preceding_activity_start'] else iso(r['start'])
        targets[endpoint]={'kind':kind,'rest':r,'fetch_start':max(lo,left-second),'fetch_end':min(hi,iso(r['end_exclusive'])+second),'raw':[]}
    begin=iso(event['information']['history_start_inclusive']);cutoff=iso(event['information']['history_end_exclusive'])
    for src in event['source_members']:
        path=ROOT/src['path'];assert sha(path)==src['sha256']
        with path.open(newline='',encoding='utf-8') as h:
            for raw in csv.DictReader(h):
                at=native(raw['Time'])
                if not begin<=at<cutoff:continue
                for target in targets.values():
                    if target['fetch_start']<=at<target['fetch_end']:target['raw'].append((at,raw))
    for endpoint,target in targets.items():
        rows=target['raw'];kind=target['kind'];r=target['rest'];at=iso(r['anchor_time']);rs=iso(r['start']);re=iso(r['end_exclusive'])
        assert len(rows)==int((target['fetch_end']-target['fetch_start']).total_seconds())
        assert all(b[0]-a1[0]==second for a1,b in zip(rows,rows[1:]))
        indices={t:j for j,(t,_) in enumerate(rows)};left=indices[rs];right=indices[re] if re in indices else len(rows);anchor=indices[at]
        rest_rows=rows[left:right];assert len(rest_rows)==int(r['observed_seconds']) and anchor-left==299
        assert all(valid(row) and abs(float(row['I_in_A']))<=.15 for _,row in rest_rows)
        if right<len(rows):assert not(valid(rows[right][1]) and abs(float(rows[right][1]['I_in_A']))<=.15),'rest not maximal'
        j=left
        while j>0 and valid(rows[j-1][1]) and abs(float(rows[j-1][1]['I_in_A']))>.15:j-=1
        if j==0 and rows[j][0]>lo:raise AssertionError('raw guard does not prove activity maximality')
        onset=j<left and j>0 and valid(rows[j-1][1]) and abs(float(rows[j-1][1]['I_in_A']))<=.15
        reason='observed_rest_to_activity' if onset else 'no_immediate_activity' if j==left else 'block_or_history_boundary' if rows[j][0]==lo else 'previous_quality_boundary'
        prior=[float(row['I_in_A']) for _,row in rows[j:left]];voltages=[float(row['V_in_V']) for _,row in rest_rows];tail=[float(row['V_in_V']) for _,row in rows[anchor-59:anchor+1]]
        charge_s=sum(x>.15 for x in prior);discharge_s=sum(x<-.15 for x in prior)
        rebuilt={'sample_id':sid,'endpoint_id':endpoint,'kind':kind,'pair_id':pair['pair_id'],'block_id':pair['block_id'],
            'anchor':str(at),'rest_start':str(rs),'rest_end_exclusive':str(re),'rest_seconds':len(rest_rows),'rest_left_censored':rs==lo,'rest_right_censored':re==hi,
            'rest_U_first_V':voltages[0],'rest_U_anchor_V':float(rows[anchor][1]['V_in_V']),'rest_U_last_V':voltages[-1],
            'rest_U_change_V':voltages[-1]-voltages[0],'rest_U_min_V':min(voltages),'rest_U_max_V':max(voltages),
            'rest_max_abs_I_A':max(abs(float(row['I_in_A'])) for _,row in rest_rows),'anchor_tail60_U_range_V':max(tail)-min(tail),'anchor_tail60_U_median_V':statistics.median(tail),
            'preceding_activity_start':str(rows[j][0]) if j<left else None,'preceding_activity_end_exclusive':str(rs),
            'preceding_activity_seconds':left-j,'preceding_activity_onset_observed':bool(onset),'preceding_activity_boundary':reason,
            'preceding_activity_status':'observed_segment' if j<left else 'no_immediate_valid_activity',
            'preceding_charge_seconds':charge_s,'preceding_discharge_seconds':discharge_s,
            'preceding_direction':'mixed' if charge_s and discharge_s else 'charge' if charge_s else 'discharge' if discharge_s else 'unavailable',
            'preceding_gross_charge_Ah':math.fsum(max(x,0) for x in prior)/3600 if prior else None,
            'preceding_gross_discharge_Ah':math.fsum(max(-x,0) for x in prior)/3600 if prior else None,
            'preceding_signed_Ah_charge_positive':math.fsum(prior)/3600 if prior else None,
            'preceding_U_first_V':float(rows[j][1]['V_in_V']) if prior else None,'preceding_U_last_V':float(rows[left-1][1]['V_in_V']) if prior else None,
            'history_cutoff':str(cutoff),'capacity_prediction_or_SOC_label':False}
        compare(rebuilt,lookup[endpoint]);all_rebuilt.append(rebuilt)
        got=[x for x in contexts if x['endpoint_id']==endpoint];assert len(got)==len(rows)
        for idx,((time,raw),given) in enumerate(zip(rows,got)):
            assert given['native_time']==str(time)
            for col in raw:
                if col=='Time':assert given[col]==raw[col]
                else:
                    difference=abs(float(given[col])-float(raw[col]));assert difference<=1e-9;max_difference=max(max_difference,difference)
            role='guard_before' if idx<j else 'preceding_activity' if idx<left else 'rest' if idx<right else 'guard_after'
            assert given['context_role']==role
        raw_context_rows+=len(rows)
assert raw_context_rows==len(contexts)
assert sum(r['rest_right_censored'] for r in all_rebuilt)==s['right_censored_rest_count']
assert sum(r['preceding_activity_onset_observed'] for r in all_rebuilt)==s['onset_observed_count']
result={'status':'passed','audit_run':a.audit_run,'verification_id':a.verification_id,'endpoints_checked':8,'raw_context_rows_checked':raw_context_rows,
        'source_members_hashed':sum(len(e['source_members']) for e in p['events']),'max_numeric_difference':max_difference,'numeric_tolerance':1e-9,
        'fixed_anchor_rest_selection_checked':True,'preceding_and_rest_maximality_guards_checked':True,'label_values_read':False,'new_capacity_predictions_or_metrics':False,
        'protocol_sha256':receipt['protocol_sha256'],'audit_code_sha256':receipt['code_sha256'],'verification_code_sha256':sha(Path(__file__)),
        'scope':'all eight endpoints rebuilt with stdlib from original CSV, original fixed sample lookup; every context field, native continuity, quality, maximality guards and all diagnostic values; no physical SOC inference'}
out.open('x',encoding='utf-8').write(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False))
