"""Already-seen pilot reference/bin-error diagnosis; no model/solver calls."""
from pathlib import Path
from collections import defaultdict,Counter
import hashlib,json,time
import numpy as np

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OLD=ROOT/'work/b1_unknown_reference_pilot_20261031'
DATA=ROOT/'data/B1_unknown_reference_pilot_v1_20261031'
hashes={};checks=Counter()
METHODS=('tf_gls','tf_standard','cpop_effective_sigma','cpop_meter_sigma')

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):
    path=Path(path);hashes[path.relative_to(ROOT).as_posix()]=sha(path)
    return json.loads(path.read_text(encoding='utf-8'))
def ck(name,result):
    if not bool(result):raise AssertionError(name)
    checks[name]+=1
def near(name,a,b,tol=1e-11):ck(name,np.allclose(a,b,atol=tol,rtol=0))
def longest(mask):
    best=run=0
    for v in mask:
        run=run+1 if v else 0;best=max(best,run)
    return int(best)
def stats(values):
    a=np.asarray(values,float)
    return dict(n=len(a),mean=float(a.mean()),median=float(np.median(a)),
        min=float(a.min()),max=float(a.max()),q05=float(np.quantile(a,.05)),
        q95=float(np.quantile(a,.95))) if len(a) else dict(n=0)
def correlation(a,b):
    a=np.asarray(a,float);b=np.asarray(b,float)
    return float(np.corrcoef(a,b)[0,1]) if len(a)>1 and np.std(a)>0 and np.std(b)>0 else None
def error_summary(rows):
    if not rows:return dict(n=0)
    return dict(n=len(rows),pooled_rms_kw=float(np.sqrt(np.mean([r['task_mse_kw2'] for r in rows]))),
        task_mean_error_kw=stats([r['task_mean_error_kw'] for r in rows]),
        task_slope_kw_per_minute=stats([r['task_slope_kw_per_minute'] for r in rows]),
        task_mean_error_positive=sum(r['task_mean_error_kw']>0 for r in rows),
        task_mean_error_ge05=sum(r['task_mean_error_kw']>=.05 for r in rows),
        task_mean_error_ge10=sum(r['task_mean_error_kw']>=.10 for r in rows),
        task_mean_error_ge15=sum(r['task_mean_error_kw']>=.15 for r in rows),
        task_any_error_ge15=sum(r['error_ge15_bins']>0 for r in rows),
        task_error_ge15_bins=sum(r['error_ge15_bins'] for r in rows),
        task_error_ge10_bins=sum(r['error_ge10_bins'] for r in rows),
        task_error_ge05_bins=sum(r['error_ge05_bins'] for r in rows),
        task_error_le_minus15_bins=sum(r['error_le_minus15_bins'] for r in rows),
        task_max_error_kw=stats([r['task_max_error_kw'] for r in rows]),
        task_longest_error_ge10=stats([r['error_ge10_longest_bins'] for r in rows]))
def duration_summary(rows):
    if not rows:return dict(n=0)
    positive=[r for r in rows if r['true_bins']>0]
    noaction=[r for r in rows if not r['physical_action']]
    return dict(n=len(rows),truth_positive=len(positive),physical_no_action=len(noaction),
        duration_mae_seconds=float(np.mean([r['duration_error_seconds'] for r in rows])),
        duration_bias_seconds=float(np.mean([r['duration_bias_seconds'] for r in rows])),
        mean_FP_seconds=float(np.mean([r['fp_bins']*60 for r in rows])),
        mean_FN_seconds=float(np.mean([r['fn_bins']*60 for r in rows])),
        mean_mask_symmetric_difference_seconds=float(np.mean([r['mask_mismatch_seconds'] for r in rows])),
        mean_FP_FN_cancellation_seconds=float(np.mean([r['cancellation_seconds'] for r in rows])),
        total_FP_bins=sum(r['fp_bins'] for r in rows),total_FN_bins=sum(r['fn_bins'] for r in rows),
        event_zero_misses=sum(r['pred_bins']==0 for r in positive),
        positive_duration_but_zero_true_overlap=sum(r['pred_bins']>0 and r['tp_bins']==0 for r in positive),
        no_action_positive_duration=sum(r['pred_bins']>0 for r in noaction),
        positive_phenotypes=dict(Counter(r['phenotype'] for r in positive)),
        positive_duration_equal_but_mask_wrong=sum(r['fp_bins']==r['fn_bins'] and r['fp_bins']>0 for r in positive),
        positive_only_duration_mae_seconds=float(np.mean([r['duration_error_seconds'] for r in positive])) if positive else None,
        missed_event_absolute_error_sum_seconds=sum(r['duration_error_seconds'] for r in positive if r['pred_bins']==0),
        detected_positive_absolute_error_sum_seconds=sum(r['duration_error_seconds'] for r in positive if r['pred_bins']>0),
        noaction_absolute_error_sum_seconds=sum(r['duration_error_seconds'] for r in noaction))


def run():
    tick=time.perf_counter();protocol=read(OLD/'protocol.json');freeze=read(OLD/'freeze.json')
    for path,h in freeze['source_identity'].items():ck('frozen source identity',sha(ROOT/path)==h)
    refs_rows=[];rows=[];null_rows=[];unique=set();all_masks={};null_debug=[]
    for seed in protocol['stages']['test']['seeds']:
        refs=read(OLD/'references'/f'test_{seed}.json')
        ref=np.array(refs['prediction'],float)
        canonical_truth=None;canonical_task=None
        for variant in ('strong','weak','null'):
            facts=read(DATA/'test'/f'{seed}_{variant}_facts.json')
            truth=read(OLD/'evaluator'/'test'/f'{seed}_{variant}_truth.json')
            outputs={m:read(OLD/'outputs'/'test'/f'{seed}_{variant}_{"cpop" if m=="cpop_effective_sigma" else m}.json') for m in METHODS if m!='cpop_meter_sigma'}
            outputs['cpop_meter_sigma']=read(OLD/'sensitivity_outputs'/'test'/f'{seed}_{variant}.json')
            ck('complete aligned rows',len(facts)==len(truth)==len(ref)==64 and all(len(v)==64 for v in outputs.values()))
            if canonical_truth is None:
                canonical_truth=[t['true_reference_kw'] for t in truth];canonical_task=[f['task'] for f in facts]
            else:
                ck('paired shared natural reference',canonical_truth==[t['true_reference_kw'] for t in truth])
                ck('paired shared task',canonical_task==[f['task'] for f in facts])
            for i,(f,t,bhat) in enumerate(zip(facts,truth,ref)):
                task_id=t['task_id'];ck('reference row task binding',task_id==f['task']['task_id']==refs['task_ids'][i])
                b=np.array(t['true_reference_kw']);true=np.array(t['true_reduction_kw']);power=np.array(f['power_kw']);noise=np.array(t['measurement_error_kw'])
                err=bhat-b;raw=bhat-power
                near('raw reduction identity',raw,true+err-noise)
                sl=slice(15,45);e=err[sl];rawtask=raw[sl];truemask=true[sl]>=.15
                ck('truth duration bin definition',int(truemask.sum())*60==t['cumulative_response_seconds'])
                if variant=='null':
                    ck('null no physical response',not t['physical_action'] and not np.any(true))
                key=(seed,task_id)
                if variant=='strong':
                    ck('unique base task count',key not in unique);unique.add(key)
                    x=np.arange(30,dtype=float)+.5;x-=x.mean()
                    r=dict(seed=seed,task_id=task_id,user_id=f['task']['user_id'],
                        full_window_mse_kw2=float(np.mean(err**2)),task_mse_kw2=float(np.mean(e**2)),
                        task_mean_error_kw=float(e.mean()),task_slope_kw_per_minute=float(x@e/(x@x)),
                        task_max_error_kw=float(e.max()),task_min_error_kw=float(e.min()),
                        error_ge15_bins=int(np.sum(e>=.15)),error_ge10_bins=int(np.sum(e>=.10)),error_ge05_bins=int(np.sum(e>=.05)),
                        error_le_minus15_bins=int(np.sum(e<=-.15)),error_ge10_longest_bins=longest(e>=.10))
                    refs_rows.append(r)
                for m in METHODS:
                    o=outputs[m][i];ck('process task binding',o['task_id']==task_id and o['status']=='ok' and o['prediction'] is not None)
                    pred=np.array(o['prediction'],float);mask=pred[sl]>=.15
                    fp=int(np.sum(mask&~truemask));fn=int(np.sum(~mask&truemask));tp=int(np.sum(mask&truemask))
                    diff=int(mask.sum())-int(truemask.sum())
                    near('stored fitted duration',int(mask.sum())*60,o['features']['cumulative_response_seconds'])
                    ck('signed duration FP-FN identity',diff==fp-fn)
                    mismatch=(fp+fn)*60;absolute=abs(diff)*60;cancel=2*min(fp,fn)*60
                    ck('absolute duration mismatch cancellation identity',mismatch==absolute+cancel)
                    if not np.any(truemask):phenotype='no_true_threshold_bins'
                    elif not np.any(mask):phenotype='event_completely_missed'
                    elif not fp and not fn:phenotype='mask_exact'
                    elif fp and not fn:phenotype='only_overextension'
                    elif fn and not fp:phenotype='only_shortening'
                    else:phenotype='mixed_FP_FN_timing'
                    r=dict(seed=seed,variant=variant,method=m,task_id=task_id,user_id=f['task']['user_id'],
                        subtype=t.get('weak_subtype'),amplitude_fraction=t.get('weak_amplitude_fraction'),
                        physical_action=t['physical_action'],true_bins=int(truemask.sum()),pred_bins=int(mask.sum()),
                        fp_bins=fp,fn_bins=fn,tp_bins=tp,duration_error_seconds=absolute,duration_bias_seconds=diff*60,
                        mask_mismatch_seconds=mismatch,cancellation_seconds=cancel,phenotype=phenotype,
                        reference_task_mean_error_kw=float(e.mean()),reference_task_slope_kw_per_minute=float(x@e/(x@x)),
                        raw_above15_bins=int(np.sum(rawtask>=.15)),raw_longest_above15_bins=longest(rawtask>=.15),
                        fit_longest_above15_bins=longest(mask),
                        fitted_positive_raw_negative_bins=int(np.sum(mask&(rawtask<.15))),
                        raw_positive_fitted_negative_bins=int(np.sum((rawtask>=.15)&~mask)),
                        raw_task_max_kw=float(rawtask.max()),fitted_task_max_kw=float(pred[sl].max()),
                        fitted_exceeds_full_raw_max=bool(pred[sl].max()>raw.max()+1e-12))
                    rows.append(r);all_masks[(seed,variant,task_id,m)]=mask
                    if variant=='null':null_rows.append(r)
                if variant=='null':
                    gls=rows[-4];cp=rows[-1]
                    ck('null row method ordering',gls['method']=='tf_gls' and cp['method']=='cpop_meter_sigma')
                    if gls['pred_bins']>0 or cp['pred_bins']>0:
                        null_debug.append(dict(seed=seed,task_id=task_id,reference_error=e.tolist(),raw_reduction=rawtask.tolist(),
                            truth_reduction=true[sl].tolist(),gls_prediction=outputs['tf_gls'][i]['prediction'][15:45],
                            cp_meter_prediction=outputs['cpop_meter_sigma'][i]['prediction'][15:45]))
    ck('256 unique base tasks',len(unique)==256)
    refmap={(r['seed'],r['task_id']):r for r in refs_rows}
    sets={m:{(r['seed'],r['task_id']) for r in null_rows if r['method']==m and r['pred_bins']>0} for m in METHODS}
    gls,cp=sets['tf_gls'],sets['cpop_meter_sigma']
    groups={'shared_GLS_CPmeter':gls&cp,'GLS_only':gls-cp,'CPmeter_only':cp-gls,'neither':unique-(gls|cp)}
    nullgroups=[]
    for group,keys in groups.items():
        selected=[r for r in null_rows if (r['seed'],r['task_id']) in keys]
        methods={}
        for m in METHODS:
            rs=[r for r in selected if r['method']==m]
            methods[m]=dict(n=len(rs),positive_tasks=sum(r['pred_bins']>0 for r in rs),
                raw_any_above15_tasks=sum(r['raw_above15_bins']>0 for r in rs),
                raw_at_least2_consecutive_tasks=sum(r['raw_longest_above15_bins']>=2 for r in rs),
                raw_at_least5_consecutive_tasks=sum(r['raw_longest_above15_bins']>=5 for r in rs),
                fitted_positive_but_raw_no_bin_above15=sum(r['pred_bins']>0 and r['raw_above15_bins']==0 for r in rs),
                raw_threshold_bins=sum(r['raw_above15_bins'] for r in rs),fitted_threshold_bins=sum(r['pred_bins'] for r in rs),
                fitted_positive_raw_negative_bins=sum(r['fitted_positive_raw_negative_bins'] for r in rs),
                raw_positive_fitted_negative_bins=sum(r['raw_positive_fitted_negative_bins'] for r in rs),
                fitted_exceeds_full_raw_max_tasks=sum(r['fitted_exceeds_full_raw_max'] for r in rs),
                mean_duration_seconds=float(np.mean([r['pred_bins']*60 for r in rs])) if rs else None)
        nullgroups.append(dict(group=group,n_tasks=len(keys),reference=error_summary([refmap[k] for k in keys]),
            by_method=methods,task_ids=[dict(seed=k[0],task_id=k[1]) for k in sorted(keys)]))
    summaries=[];weakstrata=[];lengthstrata=[];phenotype_error=[]
    for m in METHODS:
        for variant in ('strong','weak','null'):
            selected=[r for r in rows if r['method']==m and r['variant']==variant]
            summaries.append(dict(method=m,variant=variant,**duration_summary(selected)))
        positive=[r for r in rows if r['method']==m and r['variant']=='weak' and r['true_bins']>0]
        for subtype in ('brief3','brief6','sustained'):
            for amp in (.14,.20):
                selected=[r for r in positive if r['subtype']==subtype and r['amplitude_fraction']==amp]
                weakstrata.append(dict(method=m,subtype=subtype,amplitude_fraction=amp,**duration_summary(selected)))
        for name,lo,hi in [('1_to_3min',0,3),('over3_to6min',3,6),('over6_to15min',6,15),('over15min',15,30)]:
            selected=[r for r in positive if lo<r['true_bins']<=hi]
            lengthstrata.append(dict(method=m,true_duration_group=name,**duration_summary(selected)))
        for ph in ('event_completely_missed','mask_exact','only_overextension','only_shortening','mixed_FP_FN_timing'):
            selected=[r for r in positive if r['phenotype']==ph]
            phenotype_error.append(dict(method=m,phenotype=ph,n=len(selected),
                absolute_error_sum_seconds=sum(r['duration_error_seconds'] for r in selected),
                mae_seconds=float(np.mean([r['duration_error_seconds'] for r in selected])) if selected else None))
    correlations=[]
    for m in METHODS:
        rs=[r for r in rows if r['method']==m and r['variant']=='weak' and r['true_bins']>0]
        correlations.append(dict(method=m,scope='weak true-positive events only, descriptive associations',n=len(rs),
            ref_bias_vs_duration_bias=correlation([r['reference_task_mean_error_kw'] for r in rs],[r['duration_bias_seconds'] for r in rs]),
            ref_slope_vs_duration_bias=correlation([r['reference_task_slope_kw_per_minute'] for r in rs],[r['duration_bias_seconds'] for r in rs]),
            ref_bias_vs_duration_abs_error=correlation([r['reference_task_mean_error_kw'] for r in rs],[r['duration_error_seconds'] for r in rs])))
    for path,h in hashes.items():ck('read scientific input unchanged',sha(ROOT/path)==h)
    result=dict(scope='Already-seen four pilot test blocks; diagnosis only, no fit/optimizer/new parameters or new independent samples',
        unique_base_tasks=256,original_users=128,paired_variants=768,method_rows=len(rows),
        reference=error_summary(refs_rows),full_window_pooled_reference_rms_kw=float(np.sqrt(np.mean([r['full_window_mse_kw2'] for r in refs_rows]))),
        null_overlap=dict(gls=len(gls),cp_meter=len(cp),intersection=len(gls&cp),gls_only=len(gls-cp),cp_meter_only=len(cp-gls)),
        null_groups=nullgroups,duration_summaries=summaries,weak_subtype_amplitude_strata=weakstrata,
        weak_true_duration_strata=lengthstrata,weak_positive_error_by_phenotype=phenotype_error,
        reference_feature_associations=correlations,base_reference_rows=refs_rows,event_method_rows=rows,
        null_either_method_false_curve_examples_all=null_debug,
        interpretation=['FP/FN bins are exact measurement-error accounting, not causal attribution to reference versus fitting.',
            'Fitted-only threshold crossings describe the existing transformation and do not by themselves imply a solver bug.',
            'Slope/bias associations do not identify intervention effects or explain percentages of MAE.',
            'Four blocks and paired/repeated events cannot support population guarantees.'],
        no_model_fit=True,no_solver_call=True,no_hyperparameter_selection=True,
        checks=dict(checks),n_checks=sum(checks.values()),input_file_sha256=hashes,seconds=time.perf_counter()-tick)
    with (HERE/'reference_error_analysis.json').open('x',encoding='utf-8') as h:json.dump(result,h,ensure_ascii=False,indent=2,allow_nan=False)
    print(json.dumps(dict(reference=result['reference'],null_overlap=result['null_overlap'],duration_summaries=summaries,
        weak_positive_error_by_phenotype=phenotype_error,correlations=correlations,checks=sum(checks.values()),files=len(hashes)),ensure_ascii=False))

if __name__=='__main__':run()
