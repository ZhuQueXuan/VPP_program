"""Train only on frozen January-September rows; evaluate all held-out rows."""
from common import *
from curve_kernel import evaluate, baselines
import argparse, collections, math, platform
import numpy as np

ap=argparse.ArgumentParser();ap.add_argument('--run-id',required=True);a=ap.parse_args()
assert Path(a.run_id).name==a.run_id
out=BASE/'runs'/a.run_id;out.mkdir(exist_ok=False)
pp=BASE/'curve_protocol_v1.json';protocol=load(pp);assert sha(pp)==load(BASE/'curve_freeze_v1.json')['protocol_sha256']
prep=BASE/'runs/PREP_CURVE_01';ad=load(prep/'admission.json')
assert ad['protocol_sha256']==sha(pp)
for name,h in ad['outputs'].items():assert sha(prep/name)==h
rows=[r for r in read(prep/'candidates.csv') if r['admitted']=='True']
parameters={'schema':'wind-mixed-curve-v1','protocol_sha256':sha(pp),'bin_width_mps':0.5,'units':{}}
for unit in range(1,7):
    train=[r for r in rows if int(r['unit'])==unit and r['split']=='training']
    x=np.array([float(r['wind_mps']) for r in train]);y=np.array([float(r['power_kW']) for r in train])
    buckets=collections.defaultdict(list)
    for v,w in zip(x,y):buckets[math.floor(v/0.5)].append((float(v),float(w)))
    ids=sorted(buckets)
    parameters['units'][str(unit)]={
      'training_rows':len(train),'training_wind_min_mps':float(x.min()),'training_wind_max_mps':float(x.max()),
      'B_LINEAR':np.linalg.lstsq(np.column_stack([np.ones(len(x)),x]),y,rcond=1e-12)[0].tolist(),
      'B_CUBIC':np.linalg.lstsq(np.column_stack([np.ones(len(x)),x**3]),y,rcond=1e-12)[0].tolist(),
      'bin_ids':ids,'bin_counts':[len(buckets[i]) for i in ids],
      'knot_wind_mps':[math.fsum(v for v,w in buckets[i])/len(buckets[i]) for i in ids],
      'knot_power_kW':[math.fsum(w for v,w in buckets[i])/len(buckets[i]) for i in ids]}
dump(out/'parameters.json',parameters)
predictions=[]
for r in rows:
    if r['split']!='test':continue
    unit=int(r['unit']);v=float(r['wind_mps']);p=float(r['power_kW']);m=evaluate(parameters,unit,v)
    predictions.append({'unit':unit,'row':int(r['row']),'timestamp':r['timestamp'],'wind_mps':v,'power_kW':p,
      **baselines(parameters,unit,v),'M_CURVE':m.pop('power_kW'),**m})
with (out/'predictions.csv').open('w',encoding='utf-8',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(predictions[0]));w.writeheader();w.writerows(predictions)
groups={'overall':predictions}
groups.update({f'unit_{u}':[r for r in predictions if r['unit']==u] for u in range(1,7)})
groups.update({f'month_{m}':[r for r in predictions if r['timestamp'][5:7]==m] for m in ['10','11','12']})
groups.update({'positive_power':[r for r in predictions if r['power_kW']>0],
 'nonpositive_power':[r for r in predictions if r['power_kW']<=0],
 'outside_training_wind':[r for r in predictions if r['outside_training_wind']],
 'inside_training_wind':[r for r in predictions if not r['outside_training_wind']],
 'rare_or_unseen_bin':[r for r in predictions if r['rare_or_unseen_bin']],
 'supported_bin':[r for r in predictions if not r['rare_or_unseen_bin']]})
metrics={}
for group,rr in groups.items():
    metrics[group]={'n':len(rr),'models':{}}
    for model in ['B_LINEAR','B_CUBIC','M_CURVE']:
        err=[r[model]-r['power_kW'] for r in rr]
        metrics[group]['models'][model]={'mae_kW':math.fsum(abs(e) for e in err)/len(err) if err else None,
          'rmse_kW':math.sqrt(math.fsum(e*e for e in err)/len(err)) if err else None,
          'bias_kW':math.fsum(err)/len(err) if err else None,'max_absolute_error_kW':max(map(abs,err)) if err else None}
dump(out/'metrics.json',metrics)
def better(g):
    d=metrics[g]['models']
    return all(d['M_CURVE'][k]<d[b][k] for b in ['B_LINEAR','B_CUBIC'] for k in ['mae_kW','rmse_kW'])
checks={g:better(g) for g in ['overall']+[f'unit_{u}' for u in range(1,7)]+['positive_power']}
months={f'month_{m}':better(f'month_{m}') for m in ['10','11','12']}
checks['at_least_two_months']=sum(months.values())>=2
diagnostics={'checks':checks,'month_comparisons':months,'gate_passed':all(checks.values()),
 'worst_examples':{model:max(predictions,key=lambda r:abs(r[model]-r['power_kW'])) for model in ['B_LINEAR','B_CUBIC','M_CURVE']},
 'negative_source_power':sum(r['power_kW']<0 for r in predictions),
 'above_nominal_source_power':sum(r['power_kW']>2050 for r in predictions),
 'negative_curve_predictions':sum(r['M_CURVE']<0 for r in predictions),
 'above_nominal_curve_predictions':sum(r['M_CURVE']>2050 for r in predictions),
 'training_rows':sum(p['training_rows'] for p in parameters['units'].values()),'test_rows':len(predictions)}
dump(out/'diagnostics.json',diagnostics)
dump(out/'protocol_snapshot.json',protocol)
dump(out/'receipt.json',{'status':'completed','protocol_sha256':sha(pp),'admission_sha256':sha(prep/'admission.json'),
 'code':{n:sha(BASE/n) for n in ['run_curve.py','curve_kernel.py','common.py']},
 'environment':{'python':platform.python_version(),'numpy':np.__version__},
 'artifacts':{n:sha(out/n) for n in ['parameters.json','predictions.csv','metrics.json','diagnostics.json','protocol_snapshot.json']}})
print(json.dumps({'overall':metrics['overall'],'gate':checks,'months':months,'diagnostics':{k:v for k,v in diagnostics.items() if k!='worst_examples'}},indent=2))
