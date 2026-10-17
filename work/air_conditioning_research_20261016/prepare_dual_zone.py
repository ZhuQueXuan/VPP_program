"""Raw stdlib minute clock, original row windows, admission before modelling."""
from common import *
import argparse,datetime,math,collections
ap=argparse.ArgumentParser();ap.add_argument('--run-id',required=True);a=ap.parse_args();assert Path(a.run_id).name==a.run_id
out=BASE/'runs'/a.run_id;out.mkdir(exist_ok=False)
pp=BASE/'dual_zone_protocol_v1.json';assert sha(pp)==load(BASE/'dual_zone_freeze_v1.json')['protocol_sha256'];p=load(pp)
records=[];counts=collections.Counter();by=collections.Counter()
def val(row,key):
    if row is None:return None
    try:
        x=float(row[key]);return x if math.isfinite(x) else None
    except Exception:return None
for name,source in sorted(p['sources'].items()):
    fp=ROOT/source['path'];assert sha(fp)==source['sha256'];rows=read(fp);times=[datetime.datetime.strptime(r['Timestamp'],'%Y-%m-%d %H:%M') for r in rows]
    day=int(name.split('Day')[1].split('(')[0]);split='training' if day<=4 else 'test'
    for i,row in enumerate(rows):
        for zone in (1,2):
            temp=f"Room{zone}'s Indoor air temperature (°C)";other=f"Room{3-zone}'s Indoor air temperature (°C)"
            prev=rows[i-1] if i>0 else None;nxt=rows[i+1] if i+1<len(rows) else None
            x={'T_prev_C':val(prev,temp),'T_now_C':val(row,temp),'Tout_C':val(row,'Outdoor temperature (°C)'),'P_now_W':val(row,f"Room{zone}'s power consumption (W)"),'T_other_C':val(row,other),'target_T_C':val(nxt,temp)}
            missing_window=prev is None or nxt is None
            bad_clock=not missing_window and ((times[i]-times[i-1]).total_seconds()!=300 or (times[i+1]-times[i]).total_seconds()!=300)
            nonfinite=any(v is None for v in x.values());temperature_QC=any(x[k] is not None and not 0<=x[k]<=60 for k in ('T_prev_C','T_now_C','Tout_C','T_other_C','target_T_C'))
            flags={'missing_window':missing_window,'clock_invalid':bool(bad_clock),'nonfinite':nonfinite,'temperature_QC':temperature_QC};admitted=not any(flags.values())
            counts['candidates']+=1;counts['admitted']+=admitted
            for k,v in flags.items():counts[k]+=int(v)
            if admitted:by[f'{split}_room{zone}']+=1
            records.append({'file':name,'day':day,'zone':zone,'row':i+1,'timestamp':times[i].isoformat(),'target_timestamp':times[i+1].isoformat() if nxt else '', 'split':split,**x,**flags,'admitted':admitted})
with (out/'candidates.csv').open('w',encoding='utf-8',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(records[0]));w.writeheader();w.writerows(records)
dump(out/'summary.json',{'counts':dict(counts),'by_split_zone':dict(by),'assumption':p['information_time'],'admission_only_not_model_acceptance':True})
dump(out/'admission.json',{'status':'prepared_before_fitting','protocol_sha256':sha(pp),'preparer_sha256':sha(Path(__file__)),'outputs':{n:sha(out/n) for n in ['candidates.csv','summary.json']}})
print(json.dumps({'counts':dict(counts),'by_split_zone':dict(by)},indent=2))
