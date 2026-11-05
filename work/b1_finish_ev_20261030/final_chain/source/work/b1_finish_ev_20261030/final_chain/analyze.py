"""Read-only scores and finite-block paired summaries; no tuning or reruns."""
from pathlib import Path
import json
import hashlib
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]


def read(path):return json.loads(path.read_text(encoding='utf-8'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def dump(path,value):
    with path.open('x',encoding='utf-8') as f:json.dump(value,f,ensure_ascii=False,indent=2,allow_nan=False)


def paired(blocks,candidate='ride_revised',baseline='cpop'):
    pairs=[]
    for seed,group in blocks.groupby('seed'):
        values=group.set_index('method')['value']
        if candidate in values and baseline in values and np.isfinite(values[candidate]) and np.isfinite(values[baseline]):
            pairs.append(dict(seed=int(seed),candidate=float(values[candidate]),baseline=float(values[baseline]),
                difference=float(values[candidate]-values[baseline])))
    delta=np.array([p['difference'] for p in pairs])
    mean=float(delta.mean()) if len(delta) else None
    se=float(delta.std(ddof=1)/np.sqrt(len(delta))) if len(delta)>1 else None
    return dict(candidate=candidate,baseline=baseline,complete_paired_blocks=len(pairs),pairs=pairs,
        mean_difference=mean,blocks_candidate_lower=int(sum(delta<0)),
        descriptive_MC95=None if se is None else [mean-1.96*se,mean+1.96*se],
        interpretation='eight simulated seed blocks; normal Monte Carlo summary, not real-world reliability interval')


def main():
    receipt=read(HERE/'receipt.json');process=pd.DataFrame(read(HERE/'process.json'))
    effects=read(HERE/'effects.json');queries=read(HERE/'queries.json');invariance=read(HERE/'invariance.json')
    timing=pd.DataFrame(read(HERE/'timing.json'));summaries=[]
    for (scenario,method),rows in process.groupby(['scenario','method']):
        ok=rows[rows['status'].isin(['ok','degraded'])]
        summaries.append(dict(scenario=scenario,method=method,expected_events=len(rows),completed_events=len(ok),
            statuses={str(k):int(v) for k,v in rows['status'].value_counts().items()},
            duration_mae=float(ok['duration_mae'].mean()) if len(ok) else None,
            curve_rmse=float(ok['curve_rmse'].mean()) if len(ok) else None,
            no_action=int(ok['no_action'].sum()),false_detection=int(ok['false_detection'].sum()),
            response=int(ok['response'].sum()),miss=int(ok['miss'].sum()),fallback=int(ok['fallback'].sum()),
            solver_starts=int(ok['solver_starts'].sum()),failed_solver_starts=int(ok['failed_starts'].sum())))
    primary=[]
    for scenario in ('pooled_equal_positive_zero','positive','zero'):
        rows=process if scenario.startswith('pooled') else process[process['scenario']==scenario]
        blocks=rows.groupby(['seed','method'],as_index=False)['duration_mae'].mean().rename(columns={'duration_mae':'value'})
        primary.append(dict(scenario=scenario,metric='duration_mae_seconds',**paired(blocks)))
    curve=[]
    for scenario in ('positive','zero'):
        for method in sorted(set(e['method'] for e in effects)):
            values=[e for e in effects if e['scenario']==scenario and e['method']==method]
            available=[e for e in values if e['status']=='causal' and e['curve_rmse'] is not None]
            comparators={name:float(np.mean([e['comparator_rmse'][name] for e in available]))
                for name in ('plugin_shared_outcome','unadjusted_local_linear','straight_line_same_pseudo_outcome')} if available else {}
            curve.append(dict(scenario=scenario,method=method,expected_blocks=8,available_blocks=len(available),
                statuses={status:sum(e['status']==status for e in values) for status in sorted(set(e['status'] for e in values))},
                mean_curve_rmse_available=float(np.mean([e['curve_rmse'] for e in available])) if available else None,
                conditional_band_all_grid_included_blocks=sum(e.get('all_grid_truth_in_conditional_band',False) for e in available),
                comparator_mean_rmse_available=comparators))
    effect_pairs=[]
    for scenario in ('pooled_equal_positive_zero','positive','zero'):
        rows=[e for e in effects if e['method'] in ('ride_revised_duration','cpop_duration') and
            (scenario.startswith('pooled') or e['scenario']==scenario)]
        frame=pd.DataFrame(rows)
        # A paired pooled block requires both scenario effects available for
        # both methods. Never average away a support refusal.
        complete=[]
        for seed,g in frame.groupby('seed'):
            expected=4 if scenario.startswith('pooled') else 2
            if len(g)!=expected or not (g['status']=='causal').all() or not np.isfinite(pd.to_numeric(g['curve_rmse'],errors='coerce')).all():continue
            for method,m in g.groupby('method'):
                complete.append(dict(seed=seed,method=method.replace('_duration',''),value=float(m['curve_rmse'].mean())))
        effect_pairs.append(dict(scenario=scenario,metric='latent_contrast_curve_rmse_seconds',
            **paired(pd.DataFrame(complete,columns=['seed','method','value']))))
    query_summary=dict(total_effect_queries=len(queries),
        successful_equivalence_checks=sum(q.get('equivalence_passed') is True for q in queries),
        failed_equivalence_checks=[q for q in queries if q.get('equivalence_passed') is False],
        unavailable_frozen_fits=[q for q in queries if q.get('fit_status')!='frozen'],
        maximum_absolute_numeric_difference=max((q['maximum_absolute_numeric_difference'] for q in queries if q['maximum_absolute_numeric_difference'] is not None),default=None),
        duration_threshold_states={str(state):sum(q['threshold_status']==state for q in queries) for state in sorted(set(q['threshold_status'] for q in queries if q['threshold_status'] is not None))})
    aggregate_timing=[]
    for (phase,method),g in timing.groupby(['phase','method']):
        aggregate_timing.append(dict(phase=phase,method=method,batch_seconds_sum=float(g['seconds'].sum()),
            calls=len(g),events=int(g['events'].sum()),concurrency=4,exclusive_latency_measurement=False))
    result=dict(schema='b1.final-chain.assessment.v1',receipt=receipt,process=summaries,
        primary_process_paired=primary,effects=curve,primary_effect_paired=effect_pairs,
        query_equivalence_and_threshold=query_summary,invariance=invariance,timing=aggregate_timing,
        scientific_limitations=['Synthetic single EV task family only; no real user, SOC or capacity evidence.',
            'Eight independent blocks; positive/zero and methods are paired, not additional independent experiments.',
            'Kennedy DR is shared; query equivalence is functionality and reuse, not superiority to the same estimator.',
            'Conditional bands omit smoothing, nuisance, reference and process errors; no full-chain coverage claim.',
            'Threshold states describe smoothed mean on the declared mesh; no optimal pricing or threshold coverage claim.',
            'Process remains optional. Better process duration does not imply improved raw eta effect.',
            'No tuning, process/default replacement or representation reselection on this final panel.'])
    dump(HERE/'assessment.json',result)
    science=[p for p in HERE.rglob('*') if p.is_file() and p.suffix in ('.json','.csv','.py') and p.name!='scientific_files_sha256.json']
    science.extend(p for p in (ROOT/'data/B1_finish_chain_v1_20261030').glob('*') if p.is_file())
    dump(HERE/'scientific_files_sha256.json',{p.relative_to(ROOT).as_posix():sha(p) for p in sorted(science)})
    print(json.dumps(dict(primary_process_paired=primary,primary_effect_paired=effect_pairs,queries=query_summary,
        scientific_manifest_sha256=sha(HERE/'scientific_files_sha256.json')),ensure_ascii=False,indent=2))


if __name__=='__main__':main()
