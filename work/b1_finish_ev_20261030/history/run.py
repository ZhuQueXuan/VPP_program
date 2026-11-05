"""One predeclared finite B1 history-representation comparison.

Validation selects once; all test estimators are fitted/scored only afterwards.
The encoder sees train users only and is frozen before either causal cohort.
"""
from pathlib import Path
import os
for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[key] = '1'
import sys
import json
import hashlib
import time
from dataclasses import asdict
from concurrent.futures import ProcessPoolExecutor, as_completed
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT/'B1算法'))
sys.path.insert(0, str(ROOT/'work/b1_ev_mainline_20261030'))
from simulation import generate, potential_outcome
from b1_api import ReferenceWindow, load_reference_model, select_ev_reference
from b1_algorithm.api import _prepare_event
from b1_algorithm.process.api import prepare, _features
from b1_algorithm.effects.continuous import fit_continuous_effects
from b1_algorithm.history import (prepare_ev_history, fit_ev_history_encoder,
    encode_ev_history, save_ev_history_encoder, load_ev_history_encoder)

ASSUMPTIONS = dict(pre_treatment_X=True, consistent_treatment=True, no_interference=True,
    same_outcome_definition=True, conditional_exchangeability=True, randomized_assignment=False)
METHODS = ('C0','stats6','pca6','ae6')
FACTS = ROOT/'data/B1_finish_history_v1_20261030'
REFERENCE = ROOT/'work/b1_formal_v1_20261029/reference/artifact'


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, allow_nan=False,
                  default=lambda v: v.tolist() if isinstance(v,np.ndarray) else float(v) if isinstance(v,np.floating) else int(v) if isinstance(v,np.integer) else str(v))


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def config(seed):
    # Existing common support rules are unchanged. Six added covariates may
    # make a representation unavailable; such refusals remain visible.
    return dict(seed=seed, n_boot=99)


def outcome(record):
    data=prepare(**_prepare_event(record)['request'])
    return _features(data,data['y'])['raw_observed']['cumulative_response_seconds']


def estimate(rows, method, model, seed, grid, reference_dose):
    x=np.array([r['X'] for r in rows])
    h=np.zeros((len(rows),6)) if method=='C0' else np.asarray([encode_ev_history(model,r['history'])['values'] for r in rows])
    result=fit_continuous_effects(np.column_stack([x,h]),[r['dose'] for r in rows],
        [r['outcome'] for r in rows],[r['user_id'] for r in rows],dose_domain=[0.,2.4],
        grid=grid,reference_dose=reference_dose,incentive_unit='元/千瓦时',
        task=dict(task_id='B1-finish-history-30min-q1.5',outcome_name='raw_observed_cumulative_response_seconds',
            outcome_unit='seconds',target_population='supplied_'+rows[0]['partition']+'_users_events3and4',
            window_minutes=[0.,30.],q_kw=1.5,task_pre_treatment=True,
            reference_status='predicted_from_pre_notice_observations',reference_uncertainty='not_propagated'),
        continuous_assignment=True,assumptions=ASSUMPTIONS,config=config(seed))
    result['history_design']=dict(method=method,encoder_model_id=None if model is None else model.model_id,
        current_columns=['deadline_slack','demand_urgency'],history_columns=6,total_input_dimensions=8,
        C0_history_zero_ablation=method=='C0',equal_effective_capacity_claim=False,
        encoder_refit_in_evaluation=False,nuisance_crossfit_within_cohort=True,
        frozen_predictive_head_transfer_claim=False)
    return result


def score(result, truth_by_id, rows, grid, reference_dose):
    # This is an evaluator-only read after the estimated curve is finalized.
    truth=[truth_by_id[r['task_id']] for r in rows]
    target=np.array([np.mean([potential_outcome(float(a),t)['cumulative_response_seconds'] for t in truth]) for a in grid])
    baseline=np.mean([potential_outcome(float(reference_dose),t)['cumulative_response_seconds'] for t in truth])
    contrast=target-baseline
    metric=dict(status=result['status'],events=len(rows),users=len(set(r['user_id'] for r in rows)),
        target_mean_outcomes=target.tolist(),target_contrasts=contrast.tolist(),
        curve_rmse=None,reasons=result.get('reasons'))
    if result['status']=='causal':
        error=np.asarray(result['causal_curve']['contrasts'])-contrast
        metric.update(curve_rmse=float(np.sqrt(np.mean(error**2))),
            maximum_absolute_contrast_error=float(np.max(abs(error))))
    return metric


def validation_block(seed, protocol):
    start=time.perf_counter()
    p=protocol['step5']; model=load_reference_model(REFERENCE)
    facts,truth,metadata=generate(seed,n_users=p['users_per_block'],events_per_user=p['events_per_user'])
    dump(FACTS/f'{seed}_facts.json',facts)
    dump(HERE/f'evaluator/{seed}_truth.json',truth)
    dump(HERE/f'evaluator/{seed}_metadata.json',metadata)
    records=[]; selections=[]
    for i,row in enumerate(facts):
        selected=select_ev_reference(model,ReferenceWindow(**row['reference_window']),row['historical_non_event'])
        if selected['reference'].reference_status!='available':
            raise RuntimeError('reference unavailable: '+str(selected['reference'].reasons))
        records.append(dict(task=row['task'],starts_min=row['starts_min'],ends_min=row['ends_min'],
            power_kw=row['power_kw'],noise_sigma_kw=row['noise_sigma_kw'],reference=asdict(selected['reference']),
            observed_available_at_min=row['availability']['power_records_available_at_min'],
            ev_config=dict(max_charge_kw=7.2)))
        selections.append(dict(task_id=row['task']['task_id'],**selected['selection']))
        if (i+1)%300==0: print(f'block {seed} reference {i+1}/{len(facts)}',flush=True)
    dump(HERE/f'references/{seed}.json',selections)
    rows=[]; partitions=np.cumsum(p['user_partitions']); k=p['events_per_user']
    for u in range(p['users_per_block']):
        partition='train' if u<partitions[0] else 'validation' if u<partitions[1] else 'test'
        # Protocol fixes history0/1/2 for both target3 and4; target3 is never
        # an extra measured control for target4 in this finite comparison.
        historical=[records[u*k+j] for j in p['history_events']]
        for j in p['target_events']:
            i=u*k+j; f=facts[i];r=records[i]
            prepared=prepare_ev_history(historical,r['task'])
            if prepared['status']!='ok':raise RuntimeError('declared complete history unavailable')
            rows.append(dict(task_id=f['task']['task_id'],user_id=f['task']['user_id'],partition=partition,
                X=f['X'],dose=f['offered_incentive'],outcome=outcome(r),history=prepared))
    dump(HERE/f'prepared/{seed}.json',rows)
    trained={}
    train=[r['history'] for r in rows if r['partition']=='train']
    for method in METHODS[1:]:
        trained[method]=fit_ev_history_encoder(train,method=method,seed=seed)
        save_ev_history_encoder(trained[method],HERE/f'models/{seed}_{method}.json')
    validation=[r for r in rows if r['partition']=='validation']
    truth_by_id={r['task_id']:r for r in truth}
    metrics={}
    for method in METHODS:
        result=estimate(validation,method,trained.get(method),seed,p['evaluation_grid'],p['reference_dose'])
        dump(HERE/f'validation/{seed}_{method}.json',result)
        metrics[method]=score(result,truth_by_id,validation,p['evaluation_grid'],p['reference_dose'])
    dump(HERE/f'validation/{seed}_metrics.json',metrics)
    elapsed=time.perf_counter()-start
    print('validation complete',seed,{m:(v['status'],v['curve_rmse']) for m,v in metrics.items()},'seconds',round(elapsed,2),flush=True)
    return dict(seed=seed,metrics=metrics,elapsed_seconds=elapsed)


def select(blocks):
    summaries={}
    for method in METHODS:
        values=[b['metrics'][method] for b in blocks]
        available=[v['status']=='causal' and v['curve_rmse'] is not None for v in values]
        summaries[method]=dict(available_blocks=int(sum(available)),total_blocks=len(blocks),
            all_blocks_available=bool(all(available)),
            mean_curve_rmse=float(np.mean([v['curve_rmse'] for v in values])) if all(available) else None,
            block_statuses=[v['status'] for v in values],
            block_curve_rmse=[v['curve_rmse'] for v in values])
    selected='C0'; eligible=[]; base=summaries['C0']['mean_curve_rmse']
    if base is not None:
        eligible=[m for m in METHODS[1:] if summaries[m]['all_blocks_available'] and summaries[m]['mean_curve_rmse']<base]
        if eligible:selected=min(eligible,key=lambda m:(summaries[m]['mean_curve_rmse'],METHODS.index(m)))
    return dict(schema='b1.history-validation-selection.v1',selected=selected,summaries=summaries,
        eligible_improvements=eligible,selection_uses_test=False,
        fallback_reason=None if selected!='C0' else 'No candidate with all validation blocks available and a strictly smaller mean contrast-curve RMSE than an available C0.',
        rule='all validation blocks causal/available and lower mean contrast RMSE than C0; ties prefer simpler; unavailable C0 implies conservative C0 fallback')


def test_block(seed,protocol,selection_sha):
    p=protocol['step5'];rows=[r for r in read(HERE/f'prepared/{seed}.json') if r['partition']=='test']
    truth_by_id={r['task_id']:r for r in read(HERE/f'evaluator/{seed}_truth.json')}
    metrics={}
    for method in METHODS:
        model=None if method=='C0' else load_ev_history_encoder(HERE/f'models/{seed}_{method}.json')
        result=estimate(rows,method,model,seed,p['evaluation_grid'],p['reference_dose'])
        result['selection_frozen_before_test_sha256']=selection_sha
        dump(HERE/f'test/{seed}_{method}.json',result)
        metrics[method]=score(result,truth_by_id,rows,p['evaluation_grid'],p['reference_dose'])
    dump(HERE/f'test/{seed}_metrics.json',metrics)
    print('test complete',seed,{m:(v['status'],v['curve_rmse']) for m,v in metrics.items()},flush=True)
    return dict(seed=seed,metrics=metrics)


def main():
    started=time.perf_counter();protocol=read(HERE.parent/'protocol.json')
    if (HERE/'source_freeze.json').exists():raise RuntimeError('main study already started; no automatic rerun/overwrite')
    paths=[Path(__file__),ROOT/'B1算法/b1_algorithm/history.py',HERE.parent/'protocol.json',
           ROOT/'work/b1_ev_mainline_20261030/simulation.py']
    dump(HERE/'source_freeze.json',{p.relative_to(ROOT).as_posix():sha(p) for p in paths})
    blocks=[]
    with ProcessPoolExecutor(max_workers=2) as pool:
        pending=[pool.submit(validation_block,seed,protocol) for seed in protocol['step5']['seeds']]
        for future in as_completed(pending):blocks.append(future.result())
    blocks.sort(key=lambda b:b['seed'])
    selection=select(blocks);dump(HERE/'selection.json',selection)
    selection_sha=sha(HERE/'selection.json')
    print('FROZEN VALIDATION SELECTION',selection['selected'],selection_sha,flush=True)
    tests=[]
    with ProcessPoolExecutor(max_workers=2) as pool:
        pending=[pool.submit(test_block,seed,protocol,selection_sha) for seed in protocol['step5']['seeds']]
        for future in as_completed(pending):tests.append(future.result())
    tests.sort(key=lambda b:b['seed'])
    dump(HERE/'summary.json',dict(validation=blocks,test=tests,selection=selection,
        selected_test_mean_rmse=float(np.mean([b['metrics'][selection['selected']]['curve_rmse'] for b in tests]))
            if all(b['metrics'][selection['selected']]['curve_rmse'] is not None for b in tests) else None,
        wall_seconds=time.perf_counter()-started,independent_blocks=6,
        users_per_block=300,factual_events=9000,target_event_rows=3600,
        model_training_user_rows=1200,validation_rows=1200,test_rows=1200,
        real_data_validation=False,new_causal_estimator=False))
    print('history study complete',round(time.perf_counter()-started,2),flush=True)


if __name__=='__main__':main()
