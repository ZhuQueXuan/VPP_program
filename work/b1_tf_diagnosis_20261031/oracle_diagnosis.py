"""Fixed evaluator-only reference/noise interventions on an already-seen subset.

No prediction model, covariance, penalty or detection threshold is trained or
selected. Oracle inputs are explicitly non-deployable diagnosis conditions.
"""
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
import sys,json,hashlib,time
from pathlib import Path
from collections import defaultdict
import numpy as np

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
PILOT=ROOT/'work/b1_unknown_reference_pilot_20261031'
sys.path.insert(0,str(PILOT));sys.path.insert(0,str(ROOT/'B1算法'))
from trend_filter import fit_curve
from b1_algorithm.process._cpop import fit_cases
from b1_algorithm.api import _default_runtime_config
from run import assert_freeze

inputs={}
def read(path):
    path=Path(path);raw=path.read_bytes();inputs[path.relative_to(ROOT).as_posix()]=hashlib.sha256(raw).hexdigest()
    return json.loads(raw.decode('utf-8'))
def native(value):
    if isinstance(value,np.ndarray):return value.tolist()
    if isinstance(value,np.generic):return value.item()
    if isinstance(value,dict):return {k:native(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [native(v) for v in value]
    return value
def write(name,value):
    with (HERE/name).open('x',encoding='utf-8') as h:json.dump(native(value),h,ensure_ascii=False,allow_nan=False,separators=(',',':'))

assert_freeze();design=read(HERE/'diagnostic_design.json')
error=read(PILOT/'development_error_model.json');selection=read(PILOT/'process_selection.json')
sample=[]
for seed in [7610500,7610501,7610502,7610503]:
    refs=read(PILOT/'references'/f'test_{seed}.json')['prediction']
    for variant in ['strong','weak','null']:
        facts=read(ROOT/'data/B1_unknown_reference_pilot_v1_20261031/test'/f'{seed}_{variant}_facts.json')
        truths=read(PILOT/'evaluator/test'/f'{seed}_{variant}_truth.json')
        saved={m:read(PILOT/'outputs/test'/f'{seed}_{variant}_{m}.json') for m in ['tf_standard','tf_gls']}
        saved['cpop_meter']=read(PILOT/'sensitivity_outputs/test'/f'{seed}_{variant}.json')
        for i in range(16):
            f,t=facts[i],truths[i]
            assert f['task']['task_id']==t['task_id']
            sample.append(dict(seed=seed,variant=variant,fact=f,truth=t,reference=np.asarray(refs[i]),
                saved={m:out[i] for m,out in saved.items()}))
assert len(sample)==192
curves=[];metrics=[];timings=[]

def record(item,condition,method,pred,solver=None):
    t=item['truth'];truth=np.asarray(t['true_reduction_kw']);req=slice(15,45)
    assert pred is not None,'No diagnostic failed output can be omitted'
    pred=np.asarray(pred);actual=truth[req]>=.15;fitted=pred[req]>=.15
    fp=int(np.sum(fitted&~actual));fn=int(np.sum(actual&~fitted))
    bias=float(60*(fitted.sum()-actual.sum()))
    assert bias==60*(fp-fn)
    metrics.append(dict(seed=item['seed'],task_id=t['task_id'],variant=item['variant'],condition=condition,method=method,
        physical_action=t['physical_action'],threshold_positive=t['threshold_positive'],weak_subtype=t.get('weak_subtype'),
        true_duration_seconds=float(actual.sum()*60),pred_duration_seconds=float(fitted.sum()*60),
        duration_bias_seconds=bias,duration_error_seconds=abs(bias),false_positive_bins=fp,false_negative_bins=fn,
        task_curve_mse=float(np.mean((pred[req]-truth[req])**2)),
        mean_error_kw=float(np.mean(pred[req]-truth[req])),
        rebound_error_kwh=float(abs(np.maximum(-pred[45:],0).sum()-np.maximum(-truth[45:],0).sum())/60),
        solver_gap=solver.get('gap') if solver else None))
    curves.append(dict(seed=item['seed'],task_id=t['task_id'],variant=item['variant'],condition=condition,method=method,
        prediction=pred,solver=solver))

for item in sample:
    for method,out in item['saved'].items():record(item,'saved_reference_with_noise',method,out['prediction'])

for condition in ['true_reference_with_noise','true_reference_no_noise']:
    tick=time.perf_counter();cases=[];signals=[]
    for idx,item in enumerate(sample):
        f,t=item['fact'],item['truth'];truth=np.asarray(t['true_reduction_kw'])
        if condition=='true_reference_with_noise':
            y=np.asarray(t['true_reference_kw'])-np.asarray(f['power_kw'])
            assert np.max(np.abs(y-(truth-np.asarray(t['measurement_error_kw']))))<1e-12
        else:y=truth.copy()
        signals.append(y)
        for method,cov in [('tf_standard',error['scalar_variance']),('tf_gls',error['covariance'])]:
            penalty=selection['chosen'][method]['penalty']
            fit=fit_curve(y,cov,penalty)
            if fit['status']!='ok':raise RuntimeError('oracle diagnosis solver unavailable:'+str(fit))
            record(item,condition,method,fit['prediction'],{k:v for k,v in fit.items() if k!='prediction'})
        starts=np.asarray(f['starts_min'])-f['task']['start_min'];ends=np.asarray(f['ends_min'])-f['task']['start_min']
        cases.append(dict(case_id=idx,starts=starts,ends=ends,y=y,sigma=.05,train=np.ones(60,bool)))
    config=_default_runtime_config();config['artifact_dir']=str(HERE/'native_oracle'/condition)
    result,backend=fit_cases(cases,config)
    for idx,item in enumerate(sample):
        out=result[idx]
        if out.get('status')!='ok':raise RuntimeError('native oracle unavailable')
        record(item,condition,'cpop_meter',out['prediction'],dict(native_cost=out['native_cost'],native_knots=out['native_knots']))
    timings.append(dict(condition=condition,seconds=time.perf_counter()-tick,backend=backend))

grouped=defaultdict(list)
for row in metrics:grouped[(row['variant'],row['condition'],row['method'])].append(row)
summary=[]
for key,rows in sorted(grouped.items()):
    positive=[r for r in rows if r['threshold_positive']];noaction=[r for r in rows if not r['physical_action']]
    summary.append(dict(variant=key[0],condition=key[1],method=key[2],n=len(rows),
        duration_mae_seconds=float(np.mean([r['duration_error_seconds'] for r in rows])),
        duration_bias_seconds=float(np.mean([r['duration_bias_seconds'] for r in rows])),
        threshold_positive=len(positive),misses=sum(r['pred_duration_seconds']==0 for r in positive),
        no_action=len(noaction),false_positive_tasks=sum(r['pred_duration_seconds']>0 for r in noaction),
        fp_bins=sum(r['false_positive_bins'] for r in rows),fn_bins=sum(r['false_negative_bins'] for r in rows),
        task_curve_rmse_kw=float(np.sqrt(np.mean([r['task_curve_mse'] for r in rows])))))
write('oracle_metrics.json',metrics);write('oracle_curves.json',curves)
assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==digest for p,digest in inputs.items())
write('oracle_diagnosis.json',dict(scope='Already-seen fixed64base/192variants; oracle diagnosis only, not new independent performance',
    parameters_unchanged=True,source_freeze_unchanged=True,summary=summary,timings=timings,input_sha256=inputs,
    limitations=['True reference unavailable in actual application','Covariance/lambda/sigma remain original even under cleaner input',
        'Interaction prevents additive percentages of reference/process causes','No response-evidence p values reused under oracle input']))
assert_freeze()
print(json.dumps(dict(rows=len(metrics),summary=summary),ensure_ascii=False))
