"""Independently verify raw U/I/P diagnosis; descriptive refresh statistics do not shift data."""
from pathlib import Path
from datetime import datetime
import argparse,csv,hashlib,json,math,statistics
ROOT=Path(__file__).resolve().parent
pa=argparse.ArgumentParser();pa.add_argument('--audit-run',required=True);pa.add_argument('--verification-id',required=True);args=pa.parse_args()
if not all(x.isidentifier() for x in vars(args).values()):raise ValueError('simple IDs required')
BASE=ROOT/'downloads/rwth_home_local_span_20261014/failure_diagnostics';folder=BASE/args.audit_run;out=BASE/f'{args.verification_id}.json'
if out.exists():raise FileExistsError(out)
sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
r=json.loads((folder/'receipt.json').read_text('utf-8'));s=json.loads((folder/'summary.json').read_text('utf-8'))
for n,h in r['artifacts'].items():
    if sha(folder/n)!=h:raise ValueError('audit artifact changed')
begin=datetime.fromisoformat(s['block']['start']);end=datetime.fromisoformat(s['block']['end_exclusive'])
high=datetime.fromisoformat(s['pair']['high_anchor']);low=datetime.fromisoformat(s['pair']['low_anchor'])
raws=[]
for src in r['source_members']:
    path=ROOT/src['path']
    if sha(path)!=src['sha256']:raise ValueError('source changed')
    with path.open(encoding='utf-8',newline='') as h:
        for row in csv.DictReader(h):
            t=datetime.strptime(row['Time'],'%d-%b-%Y %H:%M:%S')
            if t<begin:continue
            if t>=end:break
            raws.append((t,row))
with (folder/'observed_block_raw_and_derived.csv').open(encoding='utf-8',newline='') as h:saved=list(csv.DictReader(h))
if len(raws)!=len(saved) or len(raws)!=int((end-begin).total_seconds()):raise ValueError('count differs')
for k,((t,raw),savedrow) in enumerate(zip(raws,saved)):
    if t!=begin+__import__('datetime').timedelta(seconds=k) or str(t)!=savedrow['native_time']:raise ValueError('native time differs')
    for name in ('P_in_W','V_in_V','I_in_A','T_Bat_in_C','T_Room_in_C','Interpolated'):
        if not math.isfinite(float(raw[name])) or float(raw[name])!=float(savedrow[name]):raise ValueError('original field differs')
    u=float(raw['V_in_V']);i=float(raw['I_in_A']);p=float(raw['P_in_W'])
    if abs(float(savedrow['UI_reconstructed_W'])-u*i)>1e-9 or abs(float(savedrow['P_minus_UI_W'])-(p-u*i))>1e-9:raise ValueError('derived power differs')
def metrics(records):
    vs=[float(row['V_in_V']) for _,row in records];cs=[float(row['I_in_A']) for _,row in records];ps=[float(row['P_in_W']) for _,row in records];diff=[power-v*i for power,v,i in zip(ps,vs,cs)]
    return {'rows':len(records),'start':str(records[0][0]),'last':str(records[-1][0]),'U_min_V':min(vs),'U_max_V':max(vs),'I_min_A':min(cs),'I_max_A':max(cs),'P_min_W':min(ps),'P_max_W':max(ps),
        'net_Ah':-math.fsum(cs)/3600,'net_UI_kWh':-math.fsum(v*i for v,i in zip(vs,cs))/3600000,'net_P_kWh':-math.fsum(ps)/3600000,
        'P_minus_UI_abs_mean_W':math.fsum(abs(x) for x in diff)/len(diff),'P_minus_UI_abs_max_W':max(abs(x) for x in diff),
        'seconds_abs_I_le_0p15':sum(abs(x)<=.15 for x in cs),'seconds_charge':sum(x>0 for x in cs),'seconds_discharge':sum(x<0 for x in cs)}
max_difference=0.
for key,records in [('whole_observed_block',raws),('frozen_pair_integral',[(t,row) for t,row in raws if high<=t<low])]:
    wanted=metrics(records)
    for name,v in wanted.items():
        if isinstance(v,float):
            error=abs(v-s[key][name]);max_difference=max(max_difference,error)
            if error>1e-9:raise ValueError('summary metric differs')
        elif v!=s[key][name]:raise ValueError('summary count/time differs')
for ep in s['rest_endpoint_diagnostics']:
    a=datetime.fromisoformat(ep['rest_start']);b=datetime.fromisoformat(ep['rest_end_exclusive']);at=datetime.fromisoformat(ep['anchor'])
    rr=[(t,row) for t,row in raws if a<=t<b];vs=[float(row['V_in_V']) for _,row in rr];tail=[float(row['V_in_V']) for t,row in rr if at.timestamp()-59<=t.timestamp()<=at.timestamp()]
    expected={'observed_seconds':len(rr),'voltage_first_V':vs[0],'voltage_at_anchor_V':next(float(row['V_in_V']) for t,row in rr if t==at),'voltage_last_V':vs[-1],
        'voltage_min_V':min(vs),'voltage_max_V':max(vs),'max_abs_I_A':max(abs(float(row['I_in_A'])) for _,row in rr),'tail60_voltage_range_V':max(tail)-min(tail)}
    for name,v in expected.items():
        if abs(v-ep[name])>1e-9:raise ValueError('rest endpoint differs')
steps=[]
for k in range(1,len(raws)):
    before=raws[k-1][1];t,row=raws[k];du=float(row['V_in_V'])-float(before['V_in_V'])
    steps.append({'rank':0,'time':str(t),'dU_V':du,'previous_U_V':float(before['V_in_V']),'U_V':float(row['V_in_V']),
        'previous_I_A':float(before['I_in_A']),'I_A':float(row['I_in_A']),'previous_P_W':float(before['P_in_W']),'P_W':float(row['P_in_W']),'inside_frozen_pair':high<=t<low})
steps=sorted(steps,key=lambda q:abs(q['dU_V']),reverse=True)[:10]
for n,step in enumerate(steps,1):
    step['rank']=n
    for key,v in step.items():
        got=s['largest_voltage_steps'][n-1][key]
        if isinstance(v,float):
            if abs(v-got)>1e-9:raise ValueError('jump differs')
        elif v!=got:raise ValueError('jump key/time differs')
refresh={}
for column in ('V_in_V','I_in_A','P_in_W'):
    values=[float(row[column]) for _,row in raws];indices=[k for k in range(1,len(values)) if values[k]!=values[k-1]]
    intervals=[(raws[b][0]-raws[a][0]).total_seconds() for a,b in zip(indices,indices[1:])]
    refresh[column]={'changed_rows':len(indices),'unchanged_adjacent_rows':len(values)-1-len(indices),
        'median_seconds_between_changes':None if not intervals else statistics.median(intervals),'most_common_intervals_seconds':__import__('collections').Counter(intervals).most_common(5)}
span=[row for t,row in raws if high<=t<low]
zero_nonzero=[(t,row) for t,row in raws if float(row['I_in_A'])==0 and float(row['P_in_W'])!=0]
result={'status':'passed','verification_id':args.verification_id,'audit_run':args.audit_run,'raw_block_rows_checked':len(raws),
    'scope':'all raw block fields/UI residual, full-block/frozen-pair metrics, all rest endpoint ranges and 10 largest raw voltage steps; no lag correction or new prediction',
    'max_summary_numeric_difference':max_difference,'numeric_tolerance':1e-9,
    'zero_I_but_nonzero_P_rows_in_block':len(zero_nonzero),'maximum_abs_P_when_I_zero_W':max(abs(float(row['P_in_W'])) for _,row in zero_nonzero),
    'channel_value_change_descriptions':refresh,'warning':'observed value-hold pattern is descriptive; not proof of sensor rate, channel lag, clock scaling or failure cause',
    'protocol_sha256':r['protocol_sha256'],'source_members':r['source_members'],'code_sha256':sha(Path(__file__))}
out.open('x',encoding='utf-8').write(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False))
