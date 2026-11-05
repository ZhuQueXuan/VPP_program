"""Evaluator-only truth access after all phase predictions are saved."""
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
import csv,math
from collections import defaultdict
import numpy as np
from pilot_common import HERE,ROOT,read,write_new,facts_path,truth_path
from run import METHODS,data_for,extracted,assert_freeze

def summarize(group):
    ok=[r for r in group if r['status']=='ok'];na=[r for r in group if not r['physical_action']]
    positive=[r for r in group if r['threshold_positive']];both=[r for r in ok if r['onset_error_seconds'] is not None]
    def avg(key):return float(np.mean([r[key] for r in ok])) if ok else None
    return dict(events=len(group),available=len(ok),unavailable=len(group)-len(ok),
        duration_mae_seconds=avg('duration_error_seconds'),duration_bias_seconds=avg('duration_bias_seconds'),
        longest_mae_seconds=avg('longest_error_seconds'),curve_task_rmse_kw=float(np.sqrt(np.mean([r['curve_task_mse'] for r in ok]))) if ok else None,
        mean_reduction_mae_kw=avg('mean_error_kw'),peak_reduction_mae_kw=avg('peak_error_kw'),
        eta_raw_mae=avg('eta_error'),post_rebound_mae_kwh=avg('rebound_error_kwh'),
        power_recovery_status_agreement=avg('power_recovery_agreement'),
        energy_recovery_status_agreement=avg('energy_recovery_agreement'),
        no_action=len(na),false_positive_duration=sum(r['pred_duration'] is not None and r['pred_duration']>0 for r in na),
        false_positive_duration_rate=sum(r['pred_duration'] is not None and r['pred_duration']>0 for r in na)/len(na) if na else None,
        threshold_positive=len(positive),missed_positive_duration=sum(r['pred_duration']==0 for r in positive),
        unavailable_positive=sum(r['pred_duration'] is None for r in positive),
        missed_positive_rate=sum(r['pred_duration']==0 for r in positive)/len(positive) if positive else None,
        no_action_false_evidence=sum(r['evidence_status']=='evidence' for r in na),
        positive_inconclusive=sum(r['evidence_status']=='inconclusive' for r in positive),
        onset_both_defined=len(both),onset_mae_conditional_seconds=float(np.mean([r['onset_error_seconds'] for r in both])) if both else None,
        positive_missing_onset=sum(r['pred_onset'] is None for r in positive))

def evaluate(phase):
    assert_freeze();design=read(HERE/'protocol.json')['stages'][phase]
    if not (HERE/f'{phase}_completed.json').is_file():raise RuntimeError('all process outputs must precede truth scoring')
    sigma=read(HERE/'development_error_model.json')['sigma_effective']
    rows=[];reference=[];user_evidence=[];energy={};solver_gaps=[]
    for seed in design.get('seeds',[design.get('seed')]):
        refs=read(HERE/'references'/f'{phase}_{seed}.json')['prediction']
        for variant in design['variants']:
            facts=read(facts_path(phase,seed,variant));truth=read(truth_path(phase,seed,variant))
            outputs={m:read(HERE/'outputs'/phase/f'{seed}_{variant}_{m}.json') for m in METHODS}
            assert len(facts)==len(truth)==len(refs) and all(len(v)==len(facts) for v in outputs.values())
            for index,(fact,t,ref) in enumerate(zip(facts,truth,refs)):
                assert fact['task']['task_id']==t['task_id']
                true=np.asarray(t['true_reduction_kw']);b=np.asarray(t['true_reference_kw'])
                oracle_fact={**fact,'power_kw':(b-true).tolist()}
                tf=extracted(data_for(oracle_fact,b,sigma),true)
                assert abs(tf['cumulative_response_seconds']-t['cumulative_response_seconds'])<1e-9
                assert abs(tf['longest_continuous_response_seconds']-t['longest_continuous_response_seconds'])<1e-9
                if variant==design['variants'][0]:reference.append(dict(seed=seed,task_id=t['task_id'],
                    mse=float(np.mean((np.asarray(ref)-b)**2)),bias=float(np.mean(np.asarray(ref)-b))))
                for method in METHODS:
                    o=outputs[method][index];assert o['task_id']==t['task_id']
                    f=o['features'];pred=None if o['prediction'] is None else np.asarray(o['prediction'])
                    if method!='cpop' and o['status']=='ok':solver_gaps.append(o['solver']['gap'])
                    key=(seed,variant,t['task_id']);energy.setdefault(key,[]).append(o['eta_raw'])
                    true_onset=tf['onset_interval_s'];pred_onset=f['onset_interval_s'] if f else None
                    row=dict(seed=seed,variant=variant,method=method,task_id=t['task_id'],user_id=fact['task']['user_id'],status=o['status'],
                        physical_action=t['physical_action'],threshold_positive=t['threshold_positive'],weak_subtype=t.get('weak_subtype'),
                        weak_amplitude_fraction=t.get('weak_amplitude_fraction'),true_duration=t['cumulative_response_seconds'],
                        pred_duration=f['cumulative_response_seconds'] if f else None,
                        pred_onset=pred_onset,truth_onset=true_onset,evidence_p=o['evidence_p'],evidence_status=o['evidence_status'],
                        duration_error_seconds=abs(f['cumulative_response_seconds']-t['cumulative_response_seconds']) if f else None,
                        duration_bias_seconds=f['cumulative_response_seconds']-t['cumulative_response_seconds'] if f else None,
                        longest_error_seconds=abs(f['longest_continuous_response_seconds']-t['longest_continuous_response_seconds']) if f else None,
                        curve_task_mse=float(np.mean((pred[15:45]-true[15:45])**2)) if pred is not None else None,
                        mean_error_kw=abs(f['mean_reduction_kw']-tf['mean_reduction_kw']) if f else None,
                        peak_error_kw=abs(f['peak_reduction_kw']-tf['peak_reduction_kw']) if f else None,
                        eta_error=abs(o['eta_raw']-t['eta']) if o['eta_raw'] is not None else None,
                        rebound_error_kwh=abs(f['post_rebound_kwh']-tf['post_rebound_kwh']) if f else None,
                        power_recovery_agreement=float(f['power_recovery_status']==tf['power_recovery_status']) if f else None,
                        energy_recovery_agreement=float(f['energy_recovery_status']==tf['energy_recovery_status']) if f else None,
                        onset_error_seconds=abs(float(np.mean(pred_onset))-float(np.mean(true_onset))) if pred_onset is not None and true_onset is not None else None)
                    rows.append(row)
            for method,output in outputs.items():
                groups=defaultdict(list)
                for o in output:groups[o['user_id']].append(o)
                assert all(len(v)==2 for v in groups.values())
                user_evidence.append(dict(seed=seed,variant=variant,method=method,users=len(groups),
                    evidence_users=sum(any(r['evidence_status']=='evidence' for r in v) for v in groups.values()),
                    any_positive_duration_users=sum(any(r['features'] and r['features']['cumulative_response_seconds']>0 for r in v) for v in groups.values())))
    # Same reference/raw energy for all process methods. Failure must be explicit.
    energy_equal=all(len(v)==3 and all(x is not None for x in v) and max(v)-min(v)<1e-12 for v in energy.values())
    groups=defaultdict(list);blocks=defaultdict(list);weak=defaultdict(list)
    for r in rows:
        groups[(r['variant'],r['method'])].append(r);blocks[(r['seed'],r['variant'],r['method'])].append(r)
        if r['variant']=='weak' and r['threshold_positive']:weak[(r['weak_subtype'],str(r['weak_amplitude_fraction']),r['method'])].append(r)
    summaries=[dict(variant=k[0],method=k[1],**summarize(v)) for k,v in sorted(groups.items())]
    block_summaries=[dict(seed=k[0],variant=k[1],method=k[2],**summarize(v)) for k,v in sorted(blocks.items())]
    paired=[]
    for variant in design['variants']:
        differences=[]
        for seed in design.get('seeds',[design.get('seed')]):
            a=summarize(blocks[(seed,variant,'tf_gls')])['duration_mae_seconds']
            b=summarize(blocks[(seed,variant,'cpop')])['duration_mae_seconds']
            if a is not None and b is not None:differences.append(a-b)
        mean=float(np.mean(differences));interval=None
        if len(differences)>1:
            from scipy.stats import t
            half=float(t.ppf(.975,len(differences)-1)*np.std(differences,ddof=1)/np.sqrt(len(differences)))
            interval=[mean-half,mean+half]
        paired.append(dict(variant=variant,n_seed_blocks=len(differences),differences_seconds=differences,
            mean_difference_seconds=mean,descriptive_MC95_t=interval,
            claim='Small paired-seed descriptive comparison, not field confidence or general superiority'))
    result=dict(phase=phase,rows=len(rows),factual_variants=len(rows)//3,
        base_tasks=len(reference),methods=list(METHODS),block_level_formal_comparator='cpop',
        main_candidate='tf_gls',internal_reproduction='tf_standard',
        groups=summaries,seed_blocks=block_summaries,paired_duration=paired,
        weak_strata=[dict(subtype=k[0],amplitude=k[1],method=k[2],**summarize(v)) for k,v in sorted(weak.items())],
        user_block_evidence=user_evidence,raw_eta_equal_across_methods=energy_equal,
        all_outputs_ok=all(r['status']=='ok' for r in rows),max_solver_gap=max(solver_gaps) if solver_gaps else None,
        reference_diagnostic=dict(base_tasks=len(reference),pooled_rmse_kw=float(np.sqrt(np.mean([r['mse'] for r in reference]))),bias_kw=float(np.mean([r['bias'] for r in reference]))),
        limitations=['Only native1min W30/q1.5 smooth-natural-load EV simulation',
            'No field, natural stopping, actual departure or missing-window validation',
            'Mature estimators and covariance adaptation, no new process estimator claimed',
            'TF selection and default CPOP have different raw-FPR tuning; common independent rank evidence is separate',
            'Feature point outputs, not calibrated feature confidence intervals',
            'No second response-analysis block experiments or formal adoption'])
    write_new(HERE/f'{phase}_assessment.json',result)
    write_new(HERE/f'{phase}_metrics.json',rows)
    with (HERE/f'{phase}_metrics.csv').open('x',newline='',encoding='utf-8') as h:
        writer=csv.DictWriter(h,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    print(__import__('json').dumps(dict(phase=phase,groups=summaries,paired=paired,raw_eta_equal=energy_equal,all_ok=result['all_outputs_ok']),ensure_ascii=False),flush=True)

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['validation','test']);evaluate(p.parse_args().phase)
