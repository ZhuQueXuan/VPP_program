"""Descriptive strata and pooled reference errors from already frozen outputs."""
from pathlib import Path
import json
import numpy as np
HERE=Path(__file__).resolve().parent


def read(path):return json.loads(path.read_text(encoding='utf-8'))


def main():
    if not (HERE/'test/receipt.json').is_file():raise RuntimeError('phase1 incomplete')
    result={}
    for phase in ('validation','test'):
        receipt=read(HERE/phase/'receipt.json');rows=[];reference_errors={'old':[],'new':[]}
        for b in receipt['blocks']:
            seed=b['seed'];rows.extend(read(HERE/phase/'blocks'/f'{seed}.json')['metric_rows'])
            truth=read(HERE/phase/'evaluator'/f'{seed}_strong_truth.json')
            for kind in reference_errors:
                refs=read(HERE/phase/'references'/f'{seed}_{kind}.json')['references']
                reference_errors[kind].extend((np.asarray(r['reference_kw'])[15:45]-np.asarray(t['true_reference_kw'])[15:45]).tolist() for r,t in zip(refs,truth))
        strata=[]
        for scenario in ('strong','weak','null'):
            for path in ('old_cpop','old_ride_revised','new_cpop','new_ride_revised'):
                group=[r for r in rows if r['scenario']==scenario and r['path']==path]
                for label,key in (('physical_no_action','no_action'),('true_threshold_positive','threshold_positive'),('physical_subthreshold','physical_subthreshold')):
                    subset=[r for r in group if r[key]];valid=[r for r in subset if r.get('duration_mae') is not None]
                    strata.append(dict(scenario=scenario,path=path,stratum=label,n=len(subset),n_valid=len(valid),
                        duration_mae_seconds=float(np.mean([r['duration_mae'] for r in valid])) if valid else None,
                        duration_bias_seconds=float(np.mean([r['duration_bias'] for r in valid])) if valid else None,
                        raw_eta_mae=float(np.mean([r['eta_mae'] for r in valid])) if valid else None,
                        curve_rmse_kw_mean=float(np.mean([r['curve_rmse_kw'] for r in valid])) if valid else None))
        reference={}
        for kind,errors in reference_errors.items():
            a=np.asarray(errors)
            reference[kind]=dict(unique_base_tasks=len(a),task_bins=a.size,pooled_bias_kw=float(a.mean()),
                pooled_rmse_kw=float(np.sqrt(np.mean(a*a))),point_error_q95_kw=float(np.quantile(a,.95)),
                point_error_q99_kw=float(np.quantile(a,.99)),
                tasks_mean_error_above_physical_threshold=int(np.sum(a.mean(axis=1)>=.1*1.5)),
                task_mean_error_q95_kw=float(np.quantile(a.mean(axis=1),.95)))
        result[phase]=dict(stratified_errors=strata,unique_task_reference_errors=reference)
    artifact=dict(phases=result,source='Saved block metric rows, references, and evaluator truth; no process/effect model refitted or filtered.',
        reference_weighting='Each unique base task once; natural reference shared by all paired strong/weak/null variants.',
        duration_weighting='Event equal within each separately disclosed scenario and truth stratum. Truth strata are evaluator-only and do not route inference.')
    with (HERE/'stratified_metrics.json').open('x',encoding='utf-8') as f:json.dump(artifact,f,ensure_ascii=False,allow_nan=False,indent=2)
    print(json.dumps({phase:values['unique_task_reference_errors'] for phase,values in result.items()}),flush=True)


if __name__=='__main__':main()
