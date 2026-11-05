"""Frozen-protocol, new-seed EV reference/process/factor/query evaluation.

The final panel is never used for encoder, representation, process or support
selection. Truth is written separately and read only by score_effect/process.
Run only after root review and explicit --start flag; existing runs are kept.
"""
from pathlib import Path
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[key]='1'
import sys
import json
import hashlib
import time
import traceback
from dataclasses import asdict, replace
from concurrent.futures import ProcessPoolExecutor, as_completed
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
PARENT=HERE.parent
sys.path.insert(0,str(ROOT/'B1算法'))
sys.path.insert(0,str(ROOT/'work/b1_ev_mainline_20261030'))
from simulation import generate, potential_outcome
from b1_api import ReferenceWindow, load_reference_model, select_ev_reference, analyze_events
from b1_algorithm.api import _default_runtime_config
from b1_algorithm.factors import EVFactorStudy, describe_ev_study, fit_ev_factor_curve
from b1_algorithm.history import prepare_ev_history, load_ev_history_encoder, encode_ev_history
from b1_algorithm.effects.frozen import (fit_ev_factor_model, query_continuous_model,
    find_incentive_threshold, save_continuous_model)

FACTS=ROOT/'data/B1_finish_chain_v1_20261030'
REFERENCE=ROOT/'work/b1_formal_v1_20261029/reference/artifact'
PROTOCOL_SHA='c9d57fd446c982122d94bc1c102d8314d41e46ab742fbd472cb5fc7e48898ec1'
ASSUMPTIONS=dict(pre_treatment_X=True,consistent_treatment=True,no_interference=True,
    same_outcome_definition=True,conditional_exchangeability=True,randomized_assignment=False)
COVARIATES=('deadline_slack','demand_urgency',*(f'history_{j}' for j in range(6)))
EDGES=[('incentive','participation'),('participation','response'),('incentive','response')]
for name in COVARIATES:
    EDGES.extend([(name,'participation'),(name,'response')])
    if name in COVARIATES[:2]:EDGES.append((name,'incentive'))
EFFECTS=(('ride_revised_duration','ride_revised','cumulative_response_seconds','selected_curve'),
    ('cpop_duration','cpop','cumulative_response_seconds','selected_curve'),
    ('ride_template_duration','ride_template','cumulative_response_seconds','selected_curve'),
    ('raw_duration','cpop','cumulative_response_seconds','raw_observed'),
    ('ride_revised_eta','ride_revised','eta_raw','raw_observed'),
    ('cpop_eta','cpop','eta_raw','raw_observed'),
    ('ride_template_eta','ride_template','eta_raw','raw_observed'))


def read(path):return json.loads(path.read_text(encoding='utf-8'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def dump(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as stream:
        json.dump(value,stream,ensure_ascii=False,allow_nan=False,
            default=lambda v:v.tolist() if isinstance(v,np.ndarray) else float(v) if isinstance(v,np.floating) else int(v) if isinstance(v,np.integer) else str(v))


def sources():
    paths=[p for p in (ROOT/'B1算法').rglob('*.py') if p.is_file()]
    paths.extend([PARENT/'protocol.json',HERE/'run.py',HERE/'analyze.py',
        ROOT/'work/b1_ev_mainline_20261030/simulation.py',PARENT/'history/selection.json'])
    paths.extend(p for p in REFERENCE.rglob('*') if p.is_file())
    selection=read(PARENT/'history/selection.json')['selected']
    if selection!='C0':
        paths.extend(PARENT/f'history/models/{seed}_{selection}.json' for seed in range(7130000,7130006))
    return {p.relative_to(ROOT).as_posix():sha(p) for p in sorted(set(paths))}


def bind_references(facts,model):
    records=[];selections=[]
    for i,f in enumerate(facts):
        selected=select_ev_reference(model,ReferenceWindow(**f['reference_window']),f['historical_non_event'])
        if selected['reference'].reference_status!='available':
            raise RuntimeError('reference unavailable: '+str(selected['reference'].reasons))
        records.append(dict(task=f['task'],starts_min=f['starts_min'],ends_min=f['ends_min'],
            power_kw=f['power_kw'],noise_sigma_kw=f['noise_sigma_kw'],reference=asdict(selected['reference']),
            observed_available_at_min=f['availability']['power_records_available_at_min'],
            ev_config=dict(max_charge_kw=7.2,revised_rebound_bound_policy='declared_headroom')))
        selections.append(dict(task_id=f['task']['task_id'],**selected['selection']))
        if (i+1)%128==0:print('reference',facts[0]['task']['task_id'].split('-user-')[0],i+1,flush=True)
    return records,selections


def factor_inputs(facts,records,representation,encoder,p):
    """History0/1/2 only; both target3/4 share that same past source."""
    target_indices=[];factors=[];provenance=[]
    k=p['events_per_user']
    for u in range(p['users_per_block']):
        historical=[records[u*k+j] for j in p['history_events']]
        for j in p['target_events']:
            i=u*k+j;fact=facts[i];record=dict(fact['factor_record'])
            record['available_at_min']=dict(record['available_at_min'])
            record['state_as_of_min']=dict(record['state_as_of_min'])
            history=prepare_ev_history(historical,records[i]['task'])
            if history['status']!='ok':raise RuntimeError('declared three-history source unavailable')
            if representation=='C0':
                encoded=dict(values=[0.]*6,known_at_min=history['known_at_min'],model_id=None,training_user_overlap=False)
            else:
                encoded=encode_ev_history(encoder,history)
                if encoded['training_user_overlap']:raise RuntimeError('new final users overlap encoder training users')
            for z,name in zip(encoded['values'],COVARIATES[2:]):
                record[name]=float(z)
                record['available_at_min'][name]=history['known_at_min']
                record['state_as_of_min'][name]=history['known_at_min']
            target_indices.append(i);factors.append(record)
            provenance.append(dict(task_id=fact['task']['task_id'],representation=representation,
                model_id=encoded.get('model_id'),known_at_min=history['known_at_min'],
                target_notice_min=fact['task']['notice_min'],history=history['provenance'],
                prepared_digest=history['prepared_digest'],values=encoded['values'],
                current_outcome_used=False,encoder_refitted=False))
    return target_indices,factors,provenance


def score_process(outputs,truth,seed,scenario,method):
    rows=[]
    if len(outputs)!=len(truth):raise RuntimeError('process output count mismatch; no dropped rows permitted')
    for event,t in zip(outputs,truth):
        if event.get('task',{}).get('task_id')!=t['task_id']:raise RuntimeError('process identity/order mismatch')
        row=dict(seed=seed,scenario=scenario,method=method,task_id=t['task_id'],user_id=t['user_id'],
            shape=t['latent']['shape'],status=event['status'],true_duration=t['cumulative_response_seconds'],true_eta=t['eta'])
        if event['status'] in ('ok','degraded'):
            p=event['process'];pred=np.asarray(p['reduction_interval_kw']);s=np.asarray(t['relative_starts_min'])
            use=(s>=0)&(s<t['W_min']);duration=p['features']['selected_curve']['cumulative_response_seconds']
            zero=t['cumulative_response_seconds']==0;evidence=p['selection_evidence'];solver=evidence.get('solver_records',[])
            row.update(duration=duration,duration_mae=abs(duration-t['cumulative_response_seconds']),
                duration_bias=duration-t['cumulative_response_seconds'],
                curve_rmse=float(np.sqrt(np.mean((pred[use]-np.asarray(t['true_reduction_kw'])[use])**2))),
                no_action=int(zero),false_detection=int(zero and duration>0),response=int(not zero),miss=int(not zero and duration==0),
                eta=event['outcome']['value'],eta_mae=abs(event['outcome']['value']-t['eta']),
                fallback=int(event['status']=='degraded'),solver_starts=len(solver),failed_starts=sum(not q['accepted'] for q in solver))
        else:row['reasons']=event.get('reasons')
        rows.append(row)
    return rows


def truth_curves(truth,grid,reference):
    # Evaluator-only. No returned potential is passed back to any fitter.
    out={}
    for name in ('cumulative_response_seconds','eta'):
        mean=np.array([np.mean([potential_outcome(float(a),t)[name] for t in truth]) for a in grid])
        base=float(np.mean([potential_outcome(float(reference),t)[name] for t in truth]))
        out[name]=dict(mean=mean.tolist(),contrasts=(mean-base).tolist())
    return out


def score_effect(result,target,seed,scenario,label,events):
    row=dict(seed=seed,scenario=scenario,method=label,status=result['status'],events=events,
        curve_rmse=None,reasons=result.get('reasons'),comparator_rmse={})
    if result['status']=='causal':
        predicted=np.asarray(result['causal_curve']['contrasts']);truth=np.asarray(target['contrasts'])
        row['curve_rmse']=float(np.sqrt(np.mean((predicted-truth)**2)))
        row['max_absolute_error']=float(np.max(abs(predicted-truth)))
        for name,value in (result.get('comparators') or {}).items():
            row['comparator_rmse'][name]=float(np.sqrt(np.mean((np.asarray(value['contrasts'])-truth)**2)))
        band=result['inference'];row['all_grid_truth_in_conditional_band']=bool(np.all((truth>=band['lower'])&(truth<=band['upper'])))
    return row


def query_and_compare(events,factors,study,baseline,seed,scenario,label,p):
    result=dict(seed=seed,scenario=scenario,method=label,fit_status=None,query_status=None,
        same_generic_status=None,maximum_absolute_numeric_difference=None,threshold_status=None,exception=None)
    try:
        model=fit_ev_factor_model(events,factors,study,dose_domain=[0.,2.4],reference_dose=p['reference_dose'],
            assumptions=ASSUMPTIONS,config=dict(seed=seed,n_boot=199),continuous_assignment=True)
        model_path=HERE/f'models/{seed}_{scenario}_{label}.json';model_path.parent.mkdir(parents=True,exist_ok=True)
        save_continuous_model(model,model_path)
        query=query_continuous_model(model,p['grid'])
        dump(HERE/f'queries/{seed}_{scenario}_{label}.json',query)
        threshold=None
        if study.outcome_name!='eta_raw':
            threshold=find_incentive_threshold(model,target_contrast=120.,search_domain=[.4,2.],mesh_step=.04)
            dump(HERE/f'thresholds/{seed}_{scenario}_{label}.json',threshold)
        result.update(fit_status='frozen',query_status=query['status'],same_generic_status=query['status']==baseline['status'],
            model_id=model.sha256,threshold_status='not_applicable_ratio_target_not_declared' if threshold is None else threshold['status'],
            threshold_target_unit=None if threshold is None else 'seconds')
        if query['status']=='causal' and baseline['status']=='causal':
            differences=[]
            for name in ('mean_outcomes','contrasts'):
                differences.extend(abs(np.asarray(query['curve'][name])-np.asarray(baseline['causal_curve'][name])))
            for name in ('standard_errors','lower','upper'):
                differences.extend(abs(np.asarray(query['inference'][name])-np.asarray(baseline['inference'][name])))
            result['maximum_absolute_numeric_difference']=float(max(differences,default=0.))
            result['equivalence_passed']=result['maximum_absolute_numeric_difference']<=1e-10
            if not result['equivalence_passed']:raise AssertionError('frozen query differs from common Kennedy on identical measured outcome')
        elif query['status']=='unsupported' and baseline['status']=='unsupported':result['equivalence_passed']=True
        else:result['equivalence_passed']=False
    except Exception as exc:
        result['exception']=str(exc);result['exception_type']=type(exc).__name__
        if baseline['status']=='unsupported':result['fit_status']='unsupported_at_reference_or_crossfit'
        else:result['equivalence_passed']=False
    return result


def run_seed(seed,index,protocol,selection):
    started=time.perf_counter();p=protocol['step6'];representation=selection['selected']
    encoder_seed=7130000+(index%6)
    encoder=None if representation=='C0' else load_ev_history_encoder(PARENT/f'history/models/{encoder_seed}_{representation}.json')
    model=load_reference_model(REFERENCE)
    runtime=_default_runtime_config();runtime.update(artifact_dir=str(HERE/'native'/str(seed)),timeout_seconds=180)
    process_rows=[];effect_rows=[];timing=[];query_rows=[];failures=[];invariance=[]
    positive,positive_truth,metadata=generate(seed,n_users=p['users_per_block'],events_per_user=p['events_per_user'])
    records,selections=bind_references(positive,model)
    dump(HERE/f'references/{seed}.json',selections)
    for scenario in p['scenarios']:
        facts,truth,meta=(positive,positive_truth,metadata) if scenario=='positive' else generate(seed,
            n_users=p['users_per_block'],events_per_user=p['events_per_user'],scenario='zero')
        dump(FACTS/f'{seed}_{scenario}_facts.json',facts)
        dump(HERE/f'evaluator/{seed}_{scenario}_truth.json',truth)
        dump(HERE/f'evaluator/{seed}_{scenario}_metadata.json',meta)
        if scenario=='zero':
            for a,b in zip(positive,facts):
                if a['X']!=b['X'] or a['offered_incentive']!=b['offered_incentive'] or a['reference_window']!=b['reference_window']:
                    raise AssertionError('paired scenario assignment/reference inputs changed')
        current=[dict(record,power_kw=fact['power_kw']) for record,fact in zip(records,facts)]
        indices,factors,provenance=factor_inputs(facts,current,representation,encoder,p)
        targets=[current[i] for i in indices];target_truth=[truth[i] for i in indices]
        dump(HERE/f'factor_inputs/{seed}_{scenario}.json',dict(records=factors,history=provenance,
            target_indices=indices,encoder_seed=encoder_seed,representation=representation,
            representation_frozen_selection_sha256=sha(PARENT/'history/selection.json')))
        output={}
        for method in p['processes']:
            tick=time.perf_counter()
            try:
                output[method]=analyze_events(targets,process_method=method,process_config=runtime)
                dump(HERE/f'events/{seed}_{scenario}_{method}.json',output[method])
                process_rows.extend(score_process(output[method],target_truth,seed,scenario,method))
            except Exception as exc:
                failure=dict(seed=seed,scenario=scenario,phase='process',method=method,error=str(exc),traceback=traceback.format_exc())
                dump(HERE/f'failures/{seed}_{scenario}_process_{method}.json',failure);failures.append(failure)
                process_rows.extend(dict(seed=seed,scenario=scenario,method=method,task_id=t['task_id'],
                    user_id=t['user_id'],status='exception',true_duration=t['cumulative_response_seconds']) for t in target_truth)
            timing.append(dict(seed=seed,scenario=scenario,phase='process',method=method,events=len(targets),seconds=time.perf_counter()-tick))
            print('process complete',seed,scenario,method,round(timing[-1]['seconds'],2),flush=True)
        # All fits precede the evaluator's potential outcome read below.
        fitted={}
        for label,method,name,source in EFFECTS:
            study=EVFactorStudy('B1-final-EV-30min-q1.5-'+label,'元/千瓦时',covariates=COVARIATES,
                outcome_name=name,outcome_source=source,graph_edges=tuple(EDGES))
            tick=time.perf_counter()
            result=fit_ev_factor_curve(output.get(method,[]),factors,study,dose_domain=[0.,2.4],grid=p['grid'],
                reference_dose=p['reference_dose'],assumptions=ASSUMPTIONS,config=dict(seed=seed,n_boot=199),continuous_assignment=True)
            result['frozen_history_design']=dict(representation=representation,encoder_seed=encoder_seed,
                encoder_refitted=False,current_conditions=COVARIATES[:2],history_columns=COVARIATES[2:],
                history_role='past measured prognostic variables; L/U retained as declared confounders',
                selected_before_final_panel_sha256=sha(PARENT/'history/selection.json'))
            dump(HERE/f'effects/{seed}_{scenario}_{label}.json',result);fitted[label]=result
            query_rows.append(query_and_compare(output.get(method,[]),factors,study,result,seed,scenario,label,p))
            timing.append(dict(seed=seed,scenario=scenario,phase='effect_and_frozen_query',method=label,events=len(targets),seconds=time.perf_counter()-tick))
        # Eta is a ratio. The predeclared120-second threshold is duration-only.
        eta=[]
        for method in p['processes']:
            events=output.get(method,[])
            eta.append([e.get('outcome',{}).get('value') for e in events])
        invariance.append(dict(seed=seed,scenario=scenario,raw_eta_identical_across_processes=eta[0]==eta[1]==eta[2],
            events=len(targets),eta_effect_contrasts_identical=all(fitted[a+'_eta'].get('causal_curve')==fitted['cpop_eta'].get('causal_curve') for a in ('ride_revised','ride_template'))))
        target=truth_curves(target_truth,p['grid'],p['reference_dose'])
        dump(HERE/f'evaluator/{seed}_{scenario}_target_curves.json',target)
        for label,method,name,source in EFFECTS:
            effect_rows.append(score_effect(fitted[label],target['eta' if name=='eta_raw' else name],seed,scenario,label,len(targets)))
    result=dict(seed=seed,process=process_rows,effects=effect_rows,queries=query_rows,timing=timing,
        invariance=invariance,failures=failures,encoder_seed=encoder_seed,representation=representation,
        elapsed_seconds=time.perf_counter()-started)
    dump(HERE/f'blocks/{seed}.json',result)
    print('block complete',seed,round(result['elapsed_seconds'],2),flush=True)
    return result


def contract_check():
    protocol=read(PARENT/'protocol.json')
    assert sha(PARENT/'protocol.json')==PROTOCOL_SHA
    design=describe_ev_study(EVFactorStudy('B1-final-contract','元/千瓦时',covariates=COVARIATES,graph_edges=tuple(EDGES)))
    assert design['identification']['used_covariates']==list(COVARIATES)
    assert ['deadline_slack','demand_urgency'] in design['identification']['minimal_sets']
    assert protocol['step6']['seeds']==list(range(7240200,7240208))
    assert len(set(protocol['step5']['seeds'])&set(protocol['step6']['seeds']))==0
    return dict(protocol_sha256=PROTOCOL_SHA,passed=True,main_panel_generated=False,
        graph=design,encoder_mapping={str(s):7130000+i%6 for i,s in enumerate(protocol['step6']['seeds'])})


def main(start=False):
    if not start:
        print(json.dumps(contract_check(),ensure_ascii=False,indent=2));return
    if (HERE/'source_freeze.json').exists():raise RuntimeError('final study already started; preserve original output')
    contract_check();protocol=read(PARENT/'protocol.json');selection=read(PARENT/'history/selection.json')
    freeze=sources();dump(HERE/'source_freeze.json',freeze)
    for name in freeze:
        original=ROOT/name;destination=HERE/'source'/name
        destination.parent.mkdir(parents=True,exist_ok=True)
        with destination.open('xb') as stream:stream.write(original.read_bytes())
    dump(HERE/'run_design.json',dict(protocol_sha256=PROTOCOL_SHA,selection=selection,
        encoder_mapping={str(s):7130000+i%6 for i,s in enumerate(protocol['step6']['seeds'])},
        histories=[0,1,2],targets=[3,4],selection_sha256=sha(PARENT/'history/selection.json'),
        full_chain_coverage_validated=False,new_causal_estimator=False,real_EV_evidence=False))
    started=time.perf_counter();blocks=[];errors=[]
    with ProcessPoolExecutor(max_workers=4) as pool:
        pending={pool.submit(run_seed,seed,i,protocol,selection):seed for i,seed in enumerate(protocol['step6']['seeds'])}
        for future in as_completed(pending):
            try:blocks.append(future.result())
            except Exception as exc:
                failure=dict(seed=pending[future],phase='block',error=str(exc),traceback=traceback.format_exc())
                dump(HERE/f'failures/{pending[future]}_block.json',failure);errors.append(failure)
    blocks.sort(key=lambda b:b['seed'])
    for key in ('process','effects','queries','timing','invariance'):
        values=[row for block in blocks for row in block[key]]
        dump(HERE/f'{key}.json',values)
        if key!='effects':pd.DataFrame(values).to_csv(HERE/f'{key}.csv',index=False)
    unchanged=freeze==sources()
    receipt=dict(completed=not errors and unchanged,attempted_blocks=8,completed_blocks=len(blocks),
        failures=errors,source_unchanged=unchanged,wall_seconds=time.perf_counter()-started,
        factual_variants=8*128*5*2,target_factual_variants=8*128*2*2,
        expected_process_rows=8*128*2*2*3,actual_process_rows=sum(len(b['process']) for b in blocks),
        real_EV_validation=False,new_causal_estimator=False,process_default_changed=False,
        no_score_driven_rerun=True,truth_used_only_by_evaluator=True,history_selection_before_final_panel=True)
    dump(HERE/'receipt.json',receipt)
    print('final chain complete',json.dumps(receipt,ensure_ascii=False),flush=True)


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--start',action='store_true')
    main(parser.parse_args().start)
