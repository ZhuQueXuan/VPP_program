"""Literal-clock minute anchors and complete-file split. No fitting."""
from common import *
import argparse,datetime,math,collections
ap=argparse.ArgumentParser();ap.add_argument('--run-id',required=True);a=ap.parse_args()
out=BASE/'runs'/a.run_id;out.mkdir(exist_ok=False)
p=load(BASE/'temperature_protocol_v1.json');assert sha(BASE/'temperature_protocol_v1.json')==load(BASE/'temperature_freeze_v1.json')['protocol_sha256']
def dt(s):
    for fmt in ['%Y-%m-%dT%H:%M:%S','%d/%m/%Y %H:%M','%Y/%m/%d %H:%M','%I:%M:%S %p','%H:%M:%S']:
        try:return datetime.datetime.strptime(s,fmt)
        except ValueError:pass
    return None
def valid(v):return isinstance(v,(int,float)) and math.isfinite(v) and 0<=v<=100
counts=collections.Counter();manifest=[];samples=[];allanchors=[]
for j,item in enumerate(p['files']):
    f=ROOT/item['path'];assert sha(f)==item['sha256'];d=load(f);tr=d.get('Trace',d.get('TraceCollection'));tk='TimeStamp' if 'TimeStamp' in tr else 'Timestamp'
    block=0;previous=None;anchors={};badclock=0
    for i,s in enumerate(tr[tk]):
        t=dt(s)
        if t is None:badclock+=1;block+=1;previous=None;continue
        if previous is not None and t<previous:block+=1
        minute=int((t-datetime.datetime(1900,1,1)).total_seconds()//60)
        anchors[(block,minute)]=i;previous=t
    split='test' if item['name'].startswith(('Exp2_6','Exp2_9')) else 'training';fid=f'E{j+1:02d}'
    summary=collections.Counter()
    for (block,minute),i in anchors.items():
        summary['candidate_minutes']+=1
        complete=all((block,minute+k) in anchors for k in range(-5,6))
        flags={'clock_window_incomplete':not complete,'temperature_invalid':False,'heating_flag_invalid':False}
        if complete:
            before=anchors[(block,minute-5)];after=anchors[(block,minute+5)]
            needed=[tr['GeyserWaterThermostatTemp'][k] for k in [before,i,after]]+[tr[k][i] for k in ['ChamberTemp1','ChamberTemp2','B0-T0','B0-T8']]
            flags['temperature_invalid']=not all(valid(v) for v in needed)
            flags['heating_flag_invalid']=tr['GeyserHeatingFlag'][i] not in [0,1]
        admitted=not any(flags.values())
        allanchors.append({'file_id':fid,'split':split,'block':block,'minute':minute,'row':i+1,'source_timestamp':tr[tk][i],**flags,'admitted':admitted})
        for key,v in flags.items():summary[key]+=int(v)
        summary['admitted']+=int(admitted)
        if admitted:
            samples.append({'file_id':fid,'split':split,'block':block,'minute':minute,'row':i+1,'previous_row':before+1,'target_row':after+1,
              'source_timestamp':tr[tk][i],'target_source_timestamp':tr[tk][after],
              'temperature_C':tr['GeyserWaterThermostatTemp'][i],'previous_temperature_C':tr['GeyserWaterThermostatTemp'][before],
              'heating_flag':tr['GeyserHeatingFlag'][i],'ambient_C':(tr['ChamberTemp1'][i]+tr['ChamberTemp2'][i])/2,
              'top_C':tr['B0-T0'][i],'bottom_C':tr['B0-T8'][i],'target_C':tr['GeyserWaterThermostatTemp'][after]})
    manifest.append({'file_id':fid,**item,'split':split,'original_rows':len(tr[tk]),'unparseable_time_rows':badclock,'clock_blocks':block+1,'counts':dict(summary)})
    counts.update(summary)
for name,rows in [('candidates.csv',allanchors),('samples.csv',samples)]:
    with (out/name).open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
dump(out/'summary.json',{'counts':dict(counts),'files':manifest,'split_counts':dict(collections.Counter(r['split'] for r in samples))})
dump(out/'admission.json',{'status':'prepared_before_fit_or_errors','protocol_sha256':sha(BASE/'temperature_protocol_v1.json'),'script_sha256':sha(Path(__file__)),
 'outputs':{f.name:sha(f) for f in out.iterdir() if f.is_file()}})
print(json.dumps(load(out/'summary.json')['counts']));print(json.dumps(load(out/'summary.json')['split_counts']))
