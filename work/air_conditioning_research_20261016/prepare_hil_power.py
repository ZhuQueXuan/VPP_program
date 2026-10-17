"""Full-row admission/sign/condition split, before any new mapping fit/errors."""
from common import *
from datetime import datetime
import math,re
out=BASE/'runs/PREP_HIL_POWER_01';out.mkdir(parents=True,exist_ok=False)
pp=BASE/'hil_power_protocol_v1.json';p=load(pp);assert sha(pp)==load(BASE/'hil_power_freeze_v1.json')['protocol_sha256']
for s in list(p['sources'].values())+list(p['documents'].values()):assert sha(ROOT/s['path'])==s['sha256']
summary=[];all_rows=[]
for name,s in p['sources'].items():
    data=read(ROOT/s['path']);condition=int(re.search(r'OAT(\d+)F',name)[1]);split='training' if condition in p['split']['training_OAT_F'] else 'test'
    previous=None;counts={'rows':len(data),'admitted':0,'clock_invalid':0,'nonfinite':0,'negative_Q':0,'negative_outdoor_P':0,'negative_total_P':0}
    for i,row in enumerate(data):
        t=datetime.fromisoformat(row['TimeStamp']);clock=previous is None or (t-previous).total_seconds()==1;previous=t
        Q=float(row['Cooling Capacity (kW)']);T=float(row['T_Outdoor (C)']);po=float(row['Outdoor Unit Power (W)']);pi=float(row['Indoor Unit Power (W)'])
        finite=all(math.isfinite(v) for v in (Q,T,po,pi));ok=clock and finite
        counts['admitted']+=ok;counts['clock_invalid']+=not clock;counts['nonfinite']+=not finite
        counts['negative_Q']+=Q<0;counts['negative_outdoor_P']+=po<0;counts['negative_total_P']+=po+pi<0
        all_rows.append({'file':name,'OAT_F':condition,'row':i+1,'timestamp':row['TimeStamp'],'split':split,'Q_kW':Q,'Tout_C':T,
          'outdoor_P_W':po,'indoor_P_W':pi,'target_total_W':po+pi,'admitted':ok,'clock_invalid':not clock,'nonfinite':not finite})
    summary.append({'file':name,'OAT_F':condition,'split':split,**counts})
with (out/'all_rows.csv').open('w',encoding='utf-8',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(all_rows[0]));w.writeheader();w.writerows(all_rows)
result={'date':'2026-10-16','protocol_sha256':sha(pp),'files':summary,'all_rows':len(all_rows),'admitted_rows':sum(r['admitted'] for r in summary),
 'training_rows':sum(r['admitted'] for r in summary if r['split']=='training'),'test_rows':sum(r['admitted'] for r in summary if r['split']=='test'),
 'all_negative_values_preserved':True,'before_model_fit_errors':True}
dump(out/'summary.json',result);dump(out/'admission.json',{'status':'fixed_before_fit','script_sha256':sha(Path(__file__)),'protocol_sha256':sha(pp),
 'outputs':{p.name:sha(p) for p in sorted(out.iterdir()) if p.is_file()}})
print(json.dumps(result,ensure_ascii=False,indent=2))
