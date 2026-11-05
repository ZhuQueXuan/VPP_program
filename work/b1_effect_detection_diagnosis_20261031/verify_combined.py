"""Root cross-checks of independently produced diagnostic artifacts."""
from pathlib import Path
import hashlib,json
import numpy as np
import pandas as pd
W=Path(__file__).resolve().parent;R=W.parents[1]
def read(p):return json.loads(p.read_text(encoding='utf-8'))
checks=0
def check(value,label):
    global checks
    assert bool(value),label
    checks+=1
join=pd.read_csv(W/'detection/event_join.csv')
check(len(join)==4096,'all target variants')
zero=join[join.no_action==1]
check(len(zero)==1778 and zero.task_id.nunique()==1121,'paired no-action denominator')
for m,want in [('ride_revised',263),('cpop',274),('ride_template',262)]:
    check(int(zero[m+'_detection'].sum())==want,'false detections '+m)
check(int(((zero.ride_revised_detection==1)&(zero.cpop_detection==1)).sum())==246,'same-event overlap')
check(np.allclose(zero.raw_residual_task_mean_kw,zero.reference_task_bias_mean_kw-zero.meter_noise_task_mean_kw,atol=1e-12,rtol=0),'observation identity event means')
point=pd.read_csv(W/'effects/pointwise_decomposition.csv')
check(len(point)==2304,'all decomposition points')
check(np.allclose(point.total_error,point.measurement_chain_component+point.oracle_estimator_component,atol=1e-10,rtol=0),'vector identity')
check(np.allclose(point.total_error**2,point.measurement_chain_component**2+point.oracle_estimator_component**2+point.squared_error_cross_term,atol=2e-8,rtol=0),'square identity incl cross term')
check(point.groupby(['seed','scenario','label','estimator']).size().eq(9).all(),'nine doses each curve')
p=pd.read_csv(W/'process/metrics.csv');check(len(p)==3072,'all process condition rows')
check(p.status.isin(['ok','degraded']).all(),'process availability')
for row in read(W/'process/summary.json')['rows']:
    g=p[(p.scenario==row['scenario'])&(p.condition==row['condition'])&(p.method==row['method'])]
    for col,metric in [('mae','duration_mae'),('error','duration_bias'),('curve_rmse','curve_rmse')]:
        check(abs(g[col].mean()-row[metric])<1e-10,'process summary '+metric)
    check(g.no_action.sum()==row['no_action'] and g.false_detection.sum()==row['false_detection'],'probe confusion counts')
for m in ('ride_revised','cpop'):
    actual=p[(p.method==m)&(p.condition=='saved_predicted_reference')]
    oracle=p[(p.method==m)&(p.condition=='true_reference_observed_power')]
    check(actual.no_action.sum()==244 and actual.false_detection.sum()==33,'saved paired subset '+m)
    check(oracle.no_action.sum()==244 and oracle.false_detection.sum()==0,'oracle paired subset '+m)
frozen=read(W/'source_freeze.json')
check(all(hashlib.sha256((R/path).read_bytes()).hexdigest()==digest for path,digest in frozen.items()),'runtime unchanged')
old=read(R/'work/b1_finish_ev_20261030/final_chain/scientific_files_final_sha256.json')
check(all(hashlib.sha256((R/path).read_bytes()).hexdigest()==digest for path,digest in old.items()),'old science all unchanged')
receipt=dict(passed=checks,original_runtime_files=len(frozen),old_scientific_files=len(old),
    crosschecked_target_variants=4096,process_method_condition_rows=3072,pointwise_decomposition_points=2304,
    source_unchanged=True,old_scientific_outputs_unchanged=True,refitting=False,
    analyst='root, cross-check of two specialist analyses and process oracle')
(W/'combined_verification.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
print(receipt)
