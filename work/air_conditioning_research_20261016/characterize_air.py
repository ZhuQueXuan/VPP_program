"""No fitted models: full source-order reported-value and adjacent-pair summary."""
from common import *
import argparse,datetime,math,statistics,collections
ap=argparse.ArgumentParser();ap.add_argument('--run-id',required=True);a=ap.parse_args();assert Path(a.run_id).name==a.run_id
out=BASE/'runs'/a.run_id;out.mkdir(exist_ok=False)
pp=BASE/'air_characteristic_protocol_v1.json';p=load(pp);assert sha(pp)==load(BASE/'air_characteristic_freeze_v1.json')['protocol_sha256']
def quantile(values,q):
    ordered=sorted(values);z=(len(ordered)-1)*q;lo=int(math.floor(z));hi=int(math.ceil(z));return ordered[lo]+(ordered[hi]-ordered[lo])*(z-lo)
rows=[];pairlabels=[]
for name,source in sorted(p['sources'].items()):
    fp=ROOT/source['path'];assert sha(fp)==source['sha256'];d=read(fp)
    ts=[datetime.datetime.strptime(r['Timestamp'],'%Y-%m-%d %H:%M') for r in d];assert all((b-a).total_seconds()==300 for a,b in zip(ts,ts[1:]))
    for room in (1,2):
        t=[float(r[f"Room{room}'s Indoor air temperature (°C)"]) for r in d];power=[float(r[f"Room{room}'s power consumption (W)"]) for r in d]
        delta=[b-a for a,b in zip(t,t[1:])];patterns=collections.Counter()
        for i in range(len(delta)):
            pattern=('positive' if power[i]>0 else 'zero')+'->'+('positive' if power[i+1]>0 else 'zero');assert power[i]>=0 and power[i+1]>=0;patterns[pattern]+=1
            pairlabels.append({'file':name,'room':room,'start_row':i+1,'end_row':i+2,'start_timestamp':ts[i].isoformat(),'end_timestamp':ts[i+1].isoformat(),'temperature_increment_C':delta[i],'reported_power_pattern':pattern})
        rows.append({'file':name,'room':room,'split':'training' if int(name.split('Day')[1].split('(')[0])<=4 else 'test','labels':len(t),'adjacent_pairs':len(delta),
          'temperature_C':{'min':min(t),'max':max(t),'mean':statistics.fmean(t)},'reported_power_W':{'min':min(power),'max':max(power),'mean':statistics.fmean(power)},
          'positive_power_labels':sum(x>0 for x in power),'zero_power_labels':sum(x==0 for x in power),'temperature_increments':{'warming':sum(x>0 for x in delta),'cooling':sum(x<0 for x in delta),'unchanged':sum(x==0 for x in delta),'min_C_per_min':min(delta)/5.,'max_C_per_min':max(delta)/5.,'signed_quantiles_C_per_min':{str(q):quantile(delta,q)/5. for q in [.05,.5,.95]},'absolute_quantiles_C_per_min':{str(q):quantile([abs(x) for x in delta],q)/5. for q in [.05,.5,.95]}},
          'reported_power_pair_patterns':{k:patterns[k] for k in ['zero->zero','zero->positive','positive->zero','positive->positive']}})
with (out/'adjacent_pairs.csv').open('w',encoding='utf-8',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(pairlabels[0]));w.writeheader();w.writerows(pairlabels)
dump(out/'characteristics.json',{'protocol_sha256':sha(pp),'scope':'All published source labels and within-file neighbouring pairs, retrospective description only; no command/state/physical capacity inference.','room_day_summaries':rows,'total_room_labels':sum(r['labels'] for r in rows),'total_adjacent_room_pairs':sum(r['adjacent_pairs'] for r in rows),'total_positive_power_labels':sum(r['positive_power_labels'] for r in rows),'total_zero_power_labels':sum(r['zero_power_labels'] for r in rows),'reported_power_pair_patterns':{k:sum(r['reported_power_pair_patterns'][k] for r in rows) for k in rows[0]['reported_power_pair_patterns']}})
dump(out/'receipt.json',{'status':'completed','script_sha256':sha(Path(__file__)),'protocol_sha256':sha(pp),'outputs':{f.name:sha(f) for f in sorted(out.iterdir()) if f.is_file()}})
print(json.dumps({k:v for k,v in load(out/'characteristics.json').items() if k!='room_day_summaries'},ensure_ascii=False,indent=2))
