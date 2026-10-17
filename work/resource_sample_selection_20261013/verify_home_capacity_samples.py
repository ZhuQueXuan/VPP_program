"""Independently stream native CSV history; verify anchors, integrals and repeated artifacts."""
from pathlib import Path
from datetime import datetime, timedelta
from collections import deque, Counter
import argparse, csv, json, hashlib, math, statistics

ROOT=Path(__file__).resolve().parent
pa=argparse.ArgumentParser()
pa.add_argument('--first-run',required=True); pa.add_argument('--repeat-run',required=True); pa.add_argument('--verification-id',required=True)
args=pa.parse_args()
if not all(v.isidentifier() for v in vars(args).values()): raise ValueError('simple IDs required')
first=ROOT/'home_capacity_sample_runs'/args.first_run
repeat=ROOT/'home_capacity_sample_runs'/args.repeat_run
out=ROOT/'home_capacity_sample_runs'/f'{args.verification_id}.json'
if out.exists(): raise FileExistsError(out)
p=json.loads((first/'protocol_snapshot.json').read_text('utf-8'))
def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as handle:
        for b in iter(lambda:handle.read(1048576),b''): h.update(b)
    return h.hexdigest()
artifact_names=json.loads((first/'validation_receipt.json').read_text('utf-8'))['artifacts']
for name,expected in artifact_names.items():
    if sha(first/name)!=expected or sha(repeat/name)!=expected: raise ValueError(f'repeat differs: {name}')
source=ROOT/p['source']['relative_path']
if sha(source)!=p['source']['sha256']: raise ValueError('source hash differs')
start=datetime.fromisoformat(p['information']['history_start_inclusive']); cutoff=datetime.fromisoformat(p['information']['history_end_exclusive'])
rests=[]; anchors=[]; pairs=[]; orphan=[]; replaced=[]
length=0; rest_start=None; tail=deque(maxlen=p['rest_proxy']['voltage_tail_seconds'])
pending=None; rows=0; old_time=None
def close_rest(end_time):
    global length, rest_start
    if length:
        rests.append({'start':str(rest_start),'end_exclusive':str(end_time),'observed_duration_seconds':length})
    length=0; rest_start=None; tail.clear()
with source.open(encoding='utf-8',newline='') as handle:
    for row in csv.DictReader(handle):
        time=datetime.strptime(row['Time'],'%d-%b-%Y %H:%M:%S')
        if time>=cutoff: break
        if time!=start+timedelta(seconds=rows): raise ValueError('native prefix discontinuity')
        values=[float(row[k]) for k in ('P_in_W','V_in_V','I_in_A','T_Bat_in_C','T_Room_in_C')]
        power,voltage,current=values[:3]
        valid=all(math.isfinite(v) for v in values) and row['Interpolated']=='0'
        is_rest=valid and abs(current)<=p['rest_proxy']['absolute_current_max_a']
        if is_rest:
            if not length: rest_start=time
            length+=1; tail.append(voltage)
            if length==p['rest_proxy']['minimum_consecutive_seconds']:
                vc=statistics.median(tail)/p['source']['series_cells']
                kind='high' if vc>=p['rest_proxy']['high_voltage_min_v_per_series_cell'] else 'low' if vc<=p['rest_proxy']['low_voltage_max_v_per_series_cell'] else 'middle'
                a={'kind':kind,'time':str(time),'voltage':vc}
                anchors.append(a)
                if kind=='high':
                    if pending: replaced.append({'previous_high':pending['time'],'replacement_high':str(time)})
                    pending={'time':str(time),'voltage':vc,'i':0.0,'ui':0.0,'power':0.0,'gross_charge':0.0,'gross_discharge':0.0,'bad':0,'duration':0}
                elif kind=='low':
                    if pending:
                        cap=-pending['i']/3600; energy=-pending['ui']/3600000
                        status='quality_failure' if pending['bad'] else 'nonpositive_net' if cap<=0 or energy<=0 else 'eligible_proxy'
                        pairs.append({'high_anchor':pending['time'],'low_anchor':str(time),'duration_seconds':pending['duration'],
                                      'quality_bad_rows_inclusive':pending['bad'],'status':status,'net_capacity_ah':None if pending['bad'] else cap,
                                      'net_UI_energy_kwh':None if pending['bad'] else energy,'P_column_energy_kwh_diagnostic':None if pending['bad'] else -pending['power']/3600000,
                                      'gross_charge_ah_diagnostic':None if pending['bad'] else pending['gross_charge']/3600,
                                      'gross_discharge_ah_diagnostic':None if pending['bad'] else pending['gross_discharge']/3600})
                        pending=None
                    else: orphan.append({'low_anchor':str(time),'reason':'no_known_high'})
        else: close_rest(time)
        if pending:
            pending['bad']+=int(not valid); pending['duration']+=1
            if all(math.isfinite(v) for v in (current,voltage,power)):
                pending['i']+=current; pending['ui']+=current*voltage; pending['power']+=power
                pending['gross_charge']+=max(current,0); pending['gross_discharge']+=max(-current,0)
        rows+=1; old_time=time
close_rest(cutoff)
def read_csv(name):
    return list(csv.DictReader((first/name).open(encoding='utf-8',newline='')))
saved_rests=read_csv('historical_rest_candidates.csv')
if len(saved_rests)!=len(rests): raise ValueError('rest count differs')
for a,b in zip(rests,saved_rests):
    for k,v in a.items():
        if str(v)!=b[k]: raise ValueError(f'rest mismatch {k}')
saved_anchors=[r for r in saved_rests if r['status'] in ('high','middle','low')]
if len(saved_anchors)!=len(anchors): raise ValueError('anchor count differs')
for a,b in zip(anchors,saved_anchors):
    if a['kind']!=b['status'] or a['time']!=b['anchor_time'] or abs(a['voltage']-float(b['voltage_proxy_per_cell_v']))>1e-12: raise ValueError('anchor mismatch')
saved_pairs=read_csv('historical_span_candidates.csv')
if len(saved_pairs)!=len(pairs): raise ValueError('pair count differs')
max_error=0.0
for a,b in zip(pairs,saved_pairs):
    for key,v in a.items():
        if v is None:
            if b[key]!='': raise ValueError(f'missing pair value filled {key}')
        elif isinstance(v,float):
            error=abs(v-float(b[key])); max_error=max(max_error,error)
            if error>1e-9: raise ValueError(f'integral mismatch {key}: {error}')
        elif str(v)!=b[key]: raise ValueError(f'pair mismatch {key}')
if read_csv('missing_high_anchors.csv')!=orphan or read_csv('replaced_high_anchors.csv')!=replaced: raise ValueError('orphan/replacement records differ')
eligible=[r for r in pairs if r['status']=='eligible_proxy']
selected=max(eligible,key=lambda r:(r['low_anchor'],r['high_anchor'])) if eligible else None
f=read_csv('features.csv')
if len(f)!=1: raise ValueError('sample count differs')
f=f[0]
if (f['history_proxy_available']=='True')!=(selected is not None): raise ValueError('availability differs')
if selected:
    for k,pk in (('history_net_capacity_ah','net_capacity_ah'),('history_net_UI_energy_kwh','net_UI_energy_kwh')):
        if abs(float(f[k])-selected[pk])>1e-9: raise ValueError('selected feature differs')
    pair_id=f'pair_{pairs.index(selected):04}'
    if f['selected_pair_id']!=pair_id: raise ValueError('not latest eligible pair')
    age=(cutoff-datetime.fromisoformat(selected['low_anchor'])).total_seconds()
    if float(f['history_anchor_age_seconds'])!=age: raise ValueError('age differs')
if rows!=int((cutoff-start).total_seconds()): raise ValueError('history count mismatch')
result={'verification_id':args.verification_id,'status':'passed','independent_method':'stdlib native-row streaming state machine with local sums, no preparation functions or numeric targets',
        'history_rows':rows,'latest_history_time':str(old_time),'rest_runs':len(rests),'rest_anchors':len(anchors),'span_candidates':len(pairs),'eligible_proxy_spans':len(eligible),
        'max_integral_absolute_difference':max_error,'tolerance_ah_or_kwh':1e-9,'repeat_equal_artifacts':len(artifact_names),
        'source_sha256':sha(source),'protocol_sha256':sha(first/'protocol_snapshot.json'),'code_sha256':sha(Path(__file__))}
out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False))
