"""Independent saved native/raw/feature/full-query audit, no native refit."""
from pathlib import Path
from collections import defaultdict
import csv
import hashlib
import json
import sys
import numpy as np

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];P=HERE/'physical'
sys.path.insert(0,str(ROOT/'B1算法'))
from b1_algorithm.api import _prepare_event
from b1_algorithm.factors import EVFactorStudy,_inputs
from b1_algorithm.research import load_research_point_one,save_research_point_one,query_research_point_one

def read(path):return json.loads(path.read_text(encoding='utf-8'))
raw=read(P/'raw_records.json');events=read(P/'events.json');factors=read(P/'factor_records.json');ledger=read(P/'truth_ledger.json')
model=load_research_point_one(P/'model.json');score=read(P/'score.json')
assert len(raw)==len(events)==len(factors)==len(ledger)==240
assert all(e['status']=='ok' for e in events)
assert len({e['task']['user_id'] for e in events})==120
assert model['outcome_source']=='duration_estimates'
study=EVFactorStudy('physical-independent-revalidation',model['incentive_unit'],
    covariates=tuple(model['covariate_names']),outcome_source='duration_estimates')
bound=_inputs(events,factors,study)
durations=np.array([e['process']['duration_estimates']['cumulative_response_seconds'] for e in events])
assert np.allclose(bound['y'],durations,rtol=0,atol=0)
assert np.allclose(model['derivative_model']['outcome'],durations,rtol=0,atol=0)
mae=float(np.mean(abs(durations-np.array([v['true_seconds'] for v in ledger]))))
assert abs(mae-score['first_block_duration_mae'])<1e-12
nativefiles=list((P/'native').glob('*/input.csv'));assert len(nativefiles)==1
native=defaultdict(list)
with nativefiles[0].open(encoding='utf-8',newline='') as f:
    for row in csv.DictReader(f):native[int(row['case_id'])].append(row)
assert len(native)==240
segmentfile=nativefiles[0].with_name('segments.csv');segments=defaultdict(list)
with segmentfile.open(encoding='utf-8',newline='') as f:
    for row in csv.DictReader(f):segments[int(row['case_id'])].append(row)
native_y_error=native_x_error=prediction_error=0.;raw_values=0
for i,(record,event,true) in enumerate(zip(raw,events,ledger)):
    assert record['task']['task_id']==event['task']['task_id']==true['task_id']
    context=_prepare_event(record)
    digest=hashlib.sha256(json.dumps(dict(task=context['task'],starts=context['s'].tolist(),ends=context['e'].tolist(),
        power=context['p'].tolist(),reference=context['b'].tolist()),sort_keys=True).encode()).hexdigest()
    assert digest==event['input_digest']
    start=record['task']['start_min'];mid=(context['s']+context['e'])/2-start
    ny=context['b']-context['p'];rows=native[i*10]
    assert len(rows)==len(mid)==360
    native_y_error=max(native_y_error,float(np.max(abs(np.array([float(r['y']) for r in rows])-ny))))
    native_x_error=max(native_x_error,float(np.max(abs(np.array([float(r['x']) for r in rows])-mid))))
    assert all(float(r['sigma'])==.05 and r['train']=='1' for r in rows)
    # Reconstruct piecewise native fit from saved line coefficients independently.
    valid=[r for r in segments[i*10] if float(r['x1'])>float(r['x0'])]
    pred=np.full(len(mid),np.nan)
    for j,r in enumerate(valid):
        a,b=float(r['x0']),float(r['x1']);mask=(mid>=a-1e-9)&(mid<=b+1e-9)
        if j==0:mask|=mid<a
        if j==len(valid)-1:mask|=mid>b
        pred[mask]=float(r['gradient'])*mid[mask]+float(r['intercept'])
    assert np.isfinite(pred).all()
    prediction_error=max(prediction_error,float(np.max(abs(pred-np.asarray(event['process']['reduction_interval_kw'])))))
    raw_values+=len(mid)*5
assert native_y_error<1e-10 and native_x_error<1e-9 and prediction_error<1e-8
assert len(model['process_feature_table'])==240
grid=np.array([.4,.6,.8,1.,1.2,1.4,1.6,1.8,2.])
q=query_research_point_one(model,grid)
extended=np.sort(np.r_[grid,.73,.85,1.17]);qx=query_research_point_one(model,extended)
ix=[int(np.flatnonzero(extended==a)[0]) for a in grid]
for name in ['mean_outcomes','contrasts']:
    assert np.allclose(q['mean_curve']['curve'][name],np.asarray(qx['mean_curve']['curve'][name])[ix],rtol=0,atol=1e-10)
single=query_research_point_one(model,[.73])
assert single['target_threshold']['status']=='single_query_no_search_interval'
assert len(single['mean_curve']['curve']['mean_outcomes'])==1
save_research_point_one(model,HERE/'audit_physical_model_roundtrip.json')
loaded=load_research_point_one(HERE/'audit_physical_model_roundtrip.json')
assert query_research_point_one(loaded,[.73])['mean_curve']['curve']==single['mean_curve']['curve']
freeze=read(HERE/'source_freeze.json')['files']
changed=[name for name,expected in freeze.items() if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=expected]
assert not changed,changed
result=dict(status='passed',scope='EV known-reference physical simulation prototype only',events=240,users=120,
    raw_events_retained=240,feature_rows=240,first_block_duration_mae_seconds=mae,
    input_digest_checks=240,original_numeric_values_checked=raw_values,native_case_count=240,
    native_points_checked=86400,native_power_difference_max=native_y_error,native_midpoint_difference_max=native_x_error,
    native_segment_prediction_reconstruction_max=prediction_error,
    high_level_direct_duration_binding_exact=True,model_outcome_array_exact=True,
    query_insertion_invariance=True,single_amount_query_passed=True,persistence_query_exact=True,
    source_freeze_files_unchanged=len(freeze),old_test_reuse=False,new_native_or_model_refit=False)
with (HERE/'audit_physical_result.json').open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
print(json.dumps(result,ensure_ascii=False))
