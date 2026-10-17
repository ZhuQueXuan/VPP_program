"""Score all four events; old predictions are immutable controls, new features already exist."""
from pathlib import Path
import argparse,csv,hashlib,json,math,time,zipfile,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parent
pa=argparse.ArgumentParser();pa.add_argument('--run-id',required=True);pa.add_argument('--sample-run',required=True);args=pa.parse_args()
if not all(x.isidentifier() for x in vars(args).values()):raise ValueError('simple IDs required')
BASE=ROOT/'downloads/rwth_home_local_span_20261014';OUT=BASE/'baselines'/args.run_id
if OUT.exists():raise FileExistsError(OUT)
begin=time.perf_counter();sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def rows(path):
    with path.open(encoding='utf-8',newline='') as h:return list(csv.DictReader(h))
pf=ROOT/'home_capacity_local_span_protocol_v1.json';p=json.loads(pf.read_text('utf-8'));sample=BASE/'samples'/args.sample_run
sr=json.loads((sample/'receipt.json').read_text('utf-8'))
if sr['protocol_sha256']!=sha(pf) or json.loads((sample/'protocol_snapshot.json').read_text('utf-8'))!=p:raise ValueError('protocol differs')
for name,h in sr['artifacts'].items():
    if sha(sample/name)!=h:raise ValueError('sample artifact changed')
features={f['sample_id']:f for f in rows(sample/'features.csv')}
ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
labels={};predictions=[];metrics=[];failures=[]
for e in p['events']:
    sid=e['sample_id'];f=features[sid];rp=e['reference'];path=ROOT/rp['relative_path']
    if sha(path)!=rp['sha256']:raise ValueError('reference changed')
    with zipfile.ZipFile(path) as z:
        ss=[''.join(n.itertext()) for n in ET.fromstring(z.read('xl/sharedStrings.xml'))] if 'xl/sharedStrings.xml' in z.namelist() else []
        matches=[]
        for row in ET.fromstring(z.read(rp['worksheet'])).findall('.//s:row',ns):
            cellmap={}
            for c in row.findall('s:c',ns):
                v=c.find('s:v',ns);val=None if v is None else v.text
                if c.attrib.get('t')=='s' and val is not None:val=ss[int(val)]
                cellmap[''.join(k for k in c.attrib['r'] if k.isalpha())]=val
            if cellmap.get('A')==rp['excel_time_value'] and cellmap.get('B')==rp['system_id_value']:matches.append(cellmap)
        if len(matches)!=1:raise ValueError('reference key not unique')
        label={'capacity':float(matches[0]['D']),'energy':float(matches[0]['E'])}
    labels[sid]=label
    old=ROOT/'home_capacity_baseline_runs'/e['old_baseline_run']
    if sha(old/'predictions.csv')!=e['old_prediction_sha256'] or sha(old/'metrics.csv')!=e['old_metric_sha256']:raise ValueError('old control changed')
    previous=rows(old/'predictions.csv')
    if len(previous)!=6 or {r['sample_id'] for r in previous}!={sid}:raise ValueError('old event mismatch')
    for r in previous:
        if abs(float(r['reference'])-label[r['quantity']])>1e-12:raise ValueError('old reference differs')
    for model in p['comparison']['models']:
        for quantity,unit,key in [('capacity','Ah','capacity_ah'),('energy','kWh','energy_kwh')]:
            if model=='B_LOCAL_SPAN':
                value=float(f[key]) if f['proxy_available']=='True' else None
                status='ok' if value is not None else f['unavailable_reason']
            else:
                row=next(r for r in previous if r['model']==model and r['quantity']==quantity)
                value=None if row['prediction']=='' else float(row['prediction']);status=row['status']
            ref=label[quantity]
            if not math.isfinite(ref) or ref<=0 or value is not None and (not math.isfinite(value) or value<=0):raise ValueError('invalid quantity')
            pred={'sample_id':sid,'model':model,'quantity':quantity,'unit':unit,'status':status,'prediction':value,'reference':ref}
            predictions.append(pred);error=None if value is None else value-ref
            metrics.append({'sample_id':sid,'model':model,'quantity':quantity,'unit':unit,'status':status,'n_target_events':1,'n_predictions':int(value is not None),
                'signed_error':error,'absolute_error':None if error is None else abs(error),'absolute_error_percent_of_reference':None if error is None else abs(error)/ref*100})
            if value is None:failures.append({'sample_id':sid,'model':model,'quantity':quantity,'status':status,'runtime_failure':False})
OUT.mkdir(parents=True)
for name,data in [('predictions.csv',predictions),('metrics.csv',metrics),('unavailable.csv',failures)]:
    with (OUT/name).open('w',encoding='utf-8',newline='') as h:
        w=csv.DictWriter(h,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
(OUT/'labels.json').write_text(json.dumps(labels,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'protocol_snapshot.json').write_text(json.dumps(p,ensure_ascii=False,indent=2),encoding='utf-8')
receipt={'run_id':args.run_id,'sample_run':args.sample_run,'protocol_sha256':sha(pf),'sample_artifacts':sr['artifacts'],'code_sha256':sha(Path(__file__)),
    'events':4,'prediction_rows':len(predictions),'unavailable_rows':len(failures),'runtime_failures':0,'fit':'none','elapsed_seconds':time.perf_counter()-begin,
    'artifacts':{x.name:sha(x) for x in OUT.iterdir() if x.is_file()}}
(OUT/'receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'run_id':args.run_id,'new_metrics':[r for r in metrics if r['model']=='B_LOCAL_SPAN'],'unavailable_rows':len(failures),'elapsed_seconds':receipt['elapsed_seconds']},ensure_ascii=False))
