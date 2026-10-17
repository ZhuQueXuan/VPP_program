"""Frozen equal-file OLS versus persistence and trend; no searching."""
from common import *
import argparse,math,platform,collections
import numpy as np
ap=argparse.ArgumentParser();ap.add_argument('--run-id',required=True);a=ap.parse_args();out=BASE/'runs'/a.run_id;out.mkdir(exist_ok=False)
pp=BASE/'temperature_protocol_v1.json';p=load(pp);assert sha(pp)==load(BASE/'temperature_freeze_v1.json')['protocol_sha256']
prep=BASE/'runs/PREP_TEMPERATURE_01';ad=load(prep/'admission.json');assert ad['protocol_sha256']==sha(pp)
for name,h in ad['outputs'].items():assert sha(prep/name)==h
rows=read(prep/'samples.csv');train=[r for r in rows if r['split']=='training'];test=[r for r in rows if r['split']=='test']
def features(r):
    t=float(r['temperature_C']);return [1.,t-float(r['previous_temperature_C']),float(r['heating_flag']),float(r['ambient_C'])-t,float(r['top_C'])-t,float(r['bottom_C'])-t]
x=np.array([features(r) for r in train]);y=np.array([float(r['target_C'])-float(r['temperature_C']) for r in train]);cnt=collections.Counter(r['file_id'] for r in train)
w=np.array([1/math.sqrt(cnt[r['file_id']]) for r in train]);beta,residual,rank,sv=np.linalg.lstsq(x*w[:,None],y*w,rcond=1e-12)
assert rank==6
params={'beta':beta.tolist(),'rank':int(rank),'singular_values':sv.tolist(),'feature_min':x.min(axis=0).tolist(),'feature_max':x.max(axis=0).tolist(),'train_files':dict(cnt),'protocol_sha256':sha(pp),'not_physical_parameters':True}
dump(out/'parameters.json',params)
pred=[]
for r in test:
    t=float(r['temperature_C']);v=np.array(features(r));target=float(r['target_C'])
    pred.append({**r,'B_P':t,'B_TREND':t+(t-float(r['previous_temperature_C'])),'M_LAYER6':t+float(v@beta),'outside_training_range':bool(np.any((v<x.min(axis=0))|(v>x.max(axis=0))))})
with (out/'predictions.csv').open('w',encoding='utf-8',newline='') as f:
    wri=csv.DictWriter(f,fieldnames=list(pred[0]));wri.writeheader();wri.writerows(pred)
groups={'overall':pred,**{fid:[r for r in pred if r['file_id']==fid] for fid in sorted(set(r['file_id'] for r in pred))},
 'heating_flag1':[r for r in pred if float(r['heating_flag'])==1],'heating_flag0':[r for r in pred if float(r['heating_flag'])==0],
 'outside_training_range':[r for r in pred if r['outside_training_range']], 'inside_training_range':[r for r in pred if not r['outside_training_range']]}
metrics={}
for g,rr in groups.items():
    mm={}
    for model in ['B_P','B_TREND','M_LAYER6']:
        errors=[r[model]-float(r['target_C']) for r in rr];n=len(errors)
        mm[model]={'mae_C':math.fsum(abs(e) for e in errors)/n if n else None,'rmse_C':math.sqrt(math.fsum(e*e for e in errors)/n) if n else None,'bias_C':math.fsum(errors)/n if n else None,'max_abs_C':max(map(abs,errors)) if n else None}
    metrics[g]={'n':len(rr),'models':mm}
dump(out/'metrics.json',metrics)
gates={}
for g in ['overall']+sorted(set(r['file_id'] for r in pred))+['heating_flag1']:
    mm=metrics[g]['models'];gates[g]=all(mm['M_LAYER6'][k]<mm[b][k] for b in ['B_P','B_TREND'] for k in ['mae_C','rmse_C'])
diag={'gate_checks':gates,'gate_passed':all(gates.values()),'training_rows':len(train),'test_rows':len(pred),
 'worst_examples':{m:max(pred,key=lambda r:abs(r[m]-float(r['target_C']))) for m in ['B_P','B_TREND','M_LAYER6']}}
dump(out/'diagnostics.json',diag);dump(out/'protocol_snapshot.json',p)
dump(out/'receipt.json',{'status':'completed','protocol_sha256':sha(pp),'admission_sha256':sha(prep/'admission.json'),
 'code':{n:sha(BASE/n) for n in ['run_temperature.py','common.py']},'environment':{'python':platform.python_version(),'numpy':np.__version__},
 'artifacts':{n:sha(out/n) for n in ['parameters.json','predictions.csv','metrics.json','diagnostics.json','protocol_snapshot.json']}})
print(json.dumps({'overall':metrics['overall'],'gate':gates,'gate_passed':all(gates.values()),'rank':int(rank),'outside':metrics['outside_training_range']['n']},indent=2))
