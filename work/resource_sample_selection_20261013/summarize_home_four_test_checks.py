"""Summarize every indexed ID01 event, including missing predictions; no new metric choice."""
from pathlib import Path
import csv,hashlib,json
ROOT=Path(__file__).resolve().parent
DEST=ROOT/'downloads/rwth_home_fourth_test_20261014'
OUT=DEST/'four_event_summary_01.json'
if OUT.exists(): raise FileExistsError(OUT)
cases=[('2017-06-14 14:23:39','PREP_HOME_CAP_20261014_01','BL_HOME_CAP_20261014_01'),
       ('2018-03-06 16:24:35','PREP_HOME_CROSS_20261014_01','BL_HOME_CROSS_20261014_01'),
       ('2019-07-01 13:55:06','PREP_HOME_THIRD_20261014_01','BL_HOME_THIRD_20261014_01'),
       ('2022-10-30 15:02:27','PREP_HOME_FOURTH_20261014_01','BL_HOME_FOURTH_20261014_01')]
def rows(p):
    with p.open(encoding='utf-8',newline='') as h: return list(csv.DictReader(h))
records=[]
for test,sample_run,bl_run in cases:
    s=ROOT/'home_capacity_sample_runs'/sample_run
    b=ROOT/'home_capacity_baseline_runs'/bl_run
    f=rows(s/'features.csv')[0]
    predictions=rows(b/'predictions.csv'); metrics=rows(b/'metrics.csv')
    if len(predictions)!=6 or len(metrics)!=6: raise ValueError('missing model/quantity row')
    rec={'test_start_native':test,'sample_id':f['sample_id'],'sample_run':sample_run,'baseline_run':bl_run,'history_proxy_available':f['history_proxy_available']=='True','metrics':metrics}
    rec['predictions_sha256']=hashlib.sha256((b/'predictions.csv').read_bytes()).hexdigest()
    rec['metrics_sha256']=hashlib.sha256((b/'metrics.csv').read_bytes()).hexdigest()
    records.append(rec)
index=json.loads((DEST/'freeze_receipt_01.json').read_text('utf-8'))['system01_tests']
if len(index)!=len(records): raise ValueError('not all published ID01 index events retained')
out={'scope':'four events in currently published ID01 index; no new average, accuracy or independence claim',
     'indexed_events':len(index),'evaluated_target_events':len(records),
     'events_with_history_proxy':sum(r['history_proxy_available'] for r in records),'events':records,
     'code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
OUT.open('x',encoding='utf-8').write(json.dumps(out,ensure_ascii=False,indent=2))
print(json.dumps(out,ensure_ascii=False))
