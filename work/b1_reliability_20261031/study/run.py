"""Reviewed sequential EV reliability harness; every stage requires --start.

Truth is read only by evaluator functions after process outputs are saved.
Main tests are neither generated nor opened before freeze + explicit test start.
"""
from pathlib import Path
import os
for _key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[_key]='1'
import sys
import json
import time
import traceback
from dataclasses import asdict
from concurrent.futures import ProcessPoolExecutor, as_completed
import numpy as np

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT/'B1算法'))
from generator import (protocol, PROTOCOL_SHA, BASE_SOURCE, FACTS,
    persist_block, dump_new as _dump_new, sha)
from b1_algorithm.reference.core import ReferenceWindow, WindowCalibrationRecord, load_reference_model
from b1_algorithm.reference.ev_selection import select_ev_reference
from b1_algorithm.reference.reliable import (fit_ev_reference_error_model,
    predict_ev_reliable_reference, save_ev_reliable_reference_model,
    load_ev_reliable_reference_model)
from b1_algorithm.api import analyze_events, _default_runtime_config

OLD_REFERENCE=ROOT/'work/b1_formal_v1_20261029/reference/artifact'
PATHS=(('old_cpop','old','cpop'),('old_ride_revised','old','ride_revised'),
       ('new_cpop','new','cpop'),('new_ride_revised','new','ride_revised'))
MODEL_PATH=HERE/'models/reliable_reference.json'


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))


def json_native(value):
    if isinstance(value,np.ndarray):return value.tolist()
    if isinstance(value,np.generic):return value.item()
    if isinstance(value,dict):return {k:json_native(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [json_native(v) for v in value]
    return value


def dump_new(path,value):return _dump_new(path,json_native(value))


def native_config(label):
    config=_default_runtime_config()
    config['artifact_dir']=str(HERE/'native'/label)
    return config


def source_identity():
    paths=[p for p in (ROOT/'B1算法').rglob('*') if p.is_file() and p.suffix in ('.py','.R','.json')]
    paths.extend(HERE/name for name in ('generator.py','run.py','analyze.py'))
    paths.extend((HERE.parent/'protocol.json',HERE/'harness_design.json',BASE_SOURCE))
    paths.extend(p for p in OLD_REFERENCE.rglob('*') if p.is_file())
    return {p.relative_to(ROOT).as_posix():sha(p) for p in sorted(set(paths))}


def assert_identity(expected):
    actual=source_identity()
    if actual!=expected:
        changed=[k for k in sorted(set(actual)|set(expected)) if actual.get(k)!=expected.get(k)]
        raise RuntimeError('frozen runtime/source identity changed: '+str(changed))


def facts_path(phase,seed,variant):return FACTS/phase/f'{seed}_{variant}_facts.json'


def load_facts(phase,seed,variant):
    facts=read(facts_path(phase,seed,variant))
    if not facts:raise RuntimeError('no events')
    return facts


def prepare():
    p=protocol();d=p['data'];tick=time.perf_counter()
    train=persist_block('train',d['train_seed'],d['train_users'],d['clock_shifts_min']['train'],('non_event',))
    cal=persist_block('calibration',d['calibration_seed'],d['calibration_users'],d['clock_shifts_min']['calibration'],('non_event',))
    tf=load_facts('train',d['train_seed'],'non_event')
    cf=load_facts('calibration',d['calibration_seed'],'non_event')
    fit_cutoff=max(f['availability']['power_records_available_at_min'] for f in tf)
    cal_cutoff=max(f['availability']['power_records_available_at_min'] for f in cf)
    assert fit_cutoff<min(f['task']['notice_min'] for f in cf)
    assert not ({f['task']['user_id'] for f in tf}&{f['task']['user_id'] for f in cf})
    records=[]
    for f in tf:
        if f.get('non_event') is not True or f.get('task_dispatched') is not False:
            raise RuntimeError('training requires explicit undelivered non-event observations')
        records.append(WindowCalibrationRecord(ReferenceWindow(**f['reference_window']),f['power_kw'],
            f['availability']['power_records_available_at_min'],non_event=True))
    # No evaluator truth file has been read by the training code.
    model=fit_ev_reference_error_model(records,fit_cutoff_min=fit_cutoff,seed=d['train_seed'])
    save_ev_reliable_reference_model(model,MODEL_PATH)
    restored=load_ev_reliable_reference_model(MODEL_PATH)
    assert restored.sha256==model.sha256
    a=predict_ev_reliable_reference(model,ReferenceWindow(**cf[0]['reference_window']))
    b=predict_ev_reliable_reference(restored,ReferenceWindow(**cf[0]['reference_window']))
    assert a.reference_status=='available' and b.reference_status=='available'
    assert np.array_equal(a.reference_kw,b.reference_kw)
    info=dict(stage='prepare',protocol_sha256=PROTOCOL_SHA,train=train,calibration=cal,
        model_id=model.model_id,model_sha256=model.sha256,artifact_sha256=sha(MODEL_PATH),
        fit_cutoff_min=fit_cutoff,calibration_label_cutoff_min=cal_cutoff,
        training_users=len(model.training_users),training_events=len(records),
        calibration_users=len({f['task']['user_id'] for f in cf}),calibration_events=len(cf),
        roundtrip_exact=True,truth_read_by_fitter=False,seconds=time.perf_counter()-tick,
        source_identity=source_identity())
    dump_new(HERE/'prepare_receipt.json',info)
    print(json.dumps({k:v for k,v in info.items() if k not in ('source_identity','train','calibration')}),flush=True)
    return info


def bind_references(facts,kind):
    model=load_reference_model(OLD_REFERENCE) if kind=='old' else load_ev_reliable_reference_model(MODEL_PATH)
    references=[];ledger=[]
    for index,f in enumerate(facts):
        w=ReferenceWindow(**f['reference_window'])
        if kind=='old':
            selected=select_ev_reference(model,w,f['historical_non_event'])
            prediction=selected['reference'];selection=selected['selection']
        else:
            prediction=predict_ev_reliable_reference(model,w)
            selection=dict(method='ev_prefix_centered_ridge',current_response_used=False,
                model_retrained=False,fit_cutoff_min=model.fit_cutoff_min)
        references.append(asdict(prediction))
        ledger.append(dict(task_id=f['task']['task_id'],**selection))
        if (index+1)%128==0:print('reference',kind,index+1,flush=True)
    return references,ledger


def bound_records(facts,references):
    records=[]
    for fact,reference in zip(facts,references):
        if reference['task_id']!=fact['task']['task_id']:raise RuntimeError('reference identity mismatch')
        records.append(dict(task=fact['task'],starts_min=fact['starts_min'],ends_min=fact['ends_min'],
            power_kw=fact['power_kw'],noise_sigma_kw=fact['noise_sigma_kw'],reference=reference,
            observed_available_at_min=fact['availability']['power_records_available_at_min'],
            non_event=fact.get('non_event'),task_dispatched=fact.get('task_dispatched'),
            ev_config=dict(max_charge_kw=7.2,revised_rebound_bound_policy='declared_headroom')))
    return records


def process_path(facts,references,label,method):
    records=bound_records(facts,references)
    tick=time.perf_counter()
    output=analyze_events(records,process_method=method,process_config=native_config(label))
    seconds=time.perf_counter()-tick
    if len(output)!=len(facts):raise RuntimeError('process row count changed; cannot drop')
    return output,dict(label=label,method=method,n_events=len(output),seconds=seconds,
        statuses={s:sum(o['status']==s for o in output) for s in sorted({o['status'] for o in output})})


def unavailable_outputs(facts,error):
    return [dict(status='exception',task=f['task'],process=None,outcome=None,reasons=[error]) for f in facts]


def evidence_api():
    # Root supplies the formal module. Keeping imports here permits generator
    # and prepare controls before the independently reviewed module is ready.
    from b1_algorithm import response_evidence
    return response_evidence


def reference_policy(kind):
    if kind=='old':
        model=load_reference_model(OLD_REFERENCE)
        source=sha(ROOT/'B1算法/b1_algorithm/reference/ev_selection.py')
        return 'old_selected_3-'+model.model_id+'-'+source[:16]
    model=load_ev_reliable_reference_model(MODEL_PATH)
    return 'new_frozen-'+model.model_id


def calibration_model_path(label):return HERE/'models'/f'evidence_{label}.json'


def calibrate_path(pathspec):
    label,kind,method=pathspec;p=protocol();d=p['data'];seed=d['calibration_seed']
    facts=load_facts('calibration',seed,'non_event')
    assert all(f['non_event'] is True and f['task_dispatched'] is False for f in facts)
    references,selection=bind_references(facts,kind)
    dump_new(HERE/'calibration/references'/f'{label}.json',dict(references=references,selection=selection))
    records=bound_records(facts,references)
    dump_new(HERE/'calibration/records'/f'{label}.json',records)
    try:
        output,timing=process_path(facts,references,'calibration_'+label,method)
    except Exception as exc:
        error=dict(type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc())
        dump_new(HERE/'calibration/failures'/f'{label}.json',error)
        output=unavailable_outputs(facts,error);timing=dict(label=label,method=method,seconds=None,n_events=len(facts))
    dump_new(HERE/'calibration/events'/f'{label}.json',output)
    dump_new(HERE/'calibration/timing'/f'{label}.json',timing)
    api=evidence_api();cutoff=max(f['availability']['power_records_available_at_min'] for f in facts)
    policy=reference_policy(kind)
    model=api.fit_ev_event_calibration(output,records,calibration_cutoff_min=cutoff,
        reference_policy_id=policy,alpha=p['calibration']['alpha'])
    path=calibration_model_path(label);path.parent.mkdir(parents=True,exist_ok=True)
    api.save_ev_event_calibration(model,path)
    restored=api.load_ev_event_calibration(path)
    if restored.sha256!=model.sha256:raise RuntimeError('calibration model roundtrip changed')
    payload=json.loads(model.payload_json)
    return dict(label=label,kind=kind,method=method,n_events=len(output),timing=timing,
        reference_policy_id=policy,calibration_id=model.sha256,artifact_sha256=sha(path),
        cutoff_min=cutoff,n_users=len(payload['users']),events_per_user=payload['events_per_user'],
        rank=payload['rank'],threshold=payload['upper_score_threshold'],
        reference_methods=payload['reference_methods'],model_roundtrip_exact=True)


def calibration():
    p=protocol();prep=read(HERE/'prepare_receipt.json')
    # Reliable reference identity must still match its preparation artifact.
    if sha(MODEL_PATH)!=prep['artifact_sha256']:raise RuntimeError('reference artifact changed')
    start_identity=source_identity();rows=[]
    with ProcessPoolExecutor(max_workers=4) as pool:
        futures={pool.submit(calibrate_path,path):path for path in PATHS}
        for future in as_completed(futures):
            row=future.result();rows.append(row);print('calibration process complete',row['label'],flush=True)
    assert_identity(start_identity)
    dump_new(HERE/'calibration/receipt.json',dict(paths=rows,source_identity=start_identity,
        protocol_sha256=PROTOCOL_SHA,reference_artifact_sha256=sha(MODEL_PATH)))
    return rows


def evaluate_outputs(outputs,truth,references,seed,variant,path_label,decisions=None):
    if not(len(outputs)==len(truth)==len(references)):raise RuntimeError('evaluator count mismatch')
    rows=[]
    for i,(event,t,reference) in enumerate(zip(outputs,truth,references)):
        if event.get('task',{}).get('task_id')!=t['task_id']:raise RuntimeError('evaluator identity/order mismatch')
        action=bool(t['physical_action']);positive=bool(t['threshold_positive'])
        row=dict(seed=seed,scenario=variant,path=path_label,task_id=t['task_id'],user_id=t['user_id'],
            status=event['status'],true_duration=t['cumulative_response_seconds'],true_eta=t['eta'],
            physical_action=action,no_action=not action,threshold_positive=positive,
            physical_subthreshold=t['physical_subthreshold'],shape=t['latent']['shape'],
            weak_subtype=t.get('weak_subtype'),weak_amplitude_fraction=t.get('weak_amplitude_fraction'),
            observed_under_factual_participation=t['observed_under_factual_participation'],
            reference_status=reference['reference_status'])
        use=(np.asarray(t['relative_starts_min'])>=0)&(np.asarray(t['relative_starts_min'])<t['W_min'])
        if reference['reference_status']=='available':
            error=np.asarray(reference['reference_kw'])[use]-np.asarray(t['true_reference_kw'])[use]
            row.update(reference_bias_kw=float(np.mean(error)),reference_rmse_kw=float(np.sqrt(np.mean(error**2))),
                reference_max_positive_error_kw=float(np.max(error)),reference_fraction_above_physical_threshold=float(np.mean(error>=.1*t['q_kw'])))
        if event['status'] in ('ok','degraded'):
            duration=event['process']['features']['selected_curve']['cumulative_response_seconds']
            fitted=np.asarray(event['process']['reduction_interval_kw'])[use]
            row.update(duration=duration,duration_mae=abs(duration-t['cumulative_response_seconds']),
                duration_bias=duration-t['cumulative_response_seconds'],
                raw_positive_duration=duration>0,false_positive_duration=(not action and duration>0),
                threshold_response_duration_miss=positive and duration==0,
                curve_rmse_kw=float(np.sqrt(np.mean((fitted-np.asarray(t['true_reduction_kw'])[use])**2))),
                eta=event['outcome']['value'],eta_mae=abs(event['outcome']['value']-t['eta']),
                fallback=event['status']=='degraded')
        else:row['reasons']=event.get('reasons')
        if decisions is not None:row['evidence_decision']=decisions[i]
        rows.append(row)
    return rows


def assess_outputs(outputs,label,kind):
    api=evidence_api();model=api.load_ev_event_calibration(calibration_model_path(label));policy=reference_policy(kind)
    decisions=[]
    for event in outputs:
        try:decisions.append(api.assess_ev_event_evidence(event,model,reference_policy_id=policy))
        except (ValueError,TypeError,KeyError) as exc:
            decisions.append(dict(status='unavailable',decision=None,error_type=type(exc).__name__,reason=str(exc)))
    return decisions


def evaluate_block(phase,seed):
    p=protocol();d=p['data'];prep=read(HERE/'prepare_receipt.json')
    n_users=d['validation_users_per_block'] if phase=='validation' else d['test_users_per_block']
    variants=tuple(d['test_scenarios']);tick=time.perf_counter()
    paths=persist_block(phase,seed,n_users,d['clock_shifts_min'][phase],variants)
    canonical=load_facts(phase,seed,variants[0]);refs={};timing=[];metric_rows=[];failure_rows=[]
    assert min(f['task']['notice_min'] for f in canonical)>prep['calibration_label_cutoff_min']>prep['fit_cutoff_min']
    for kind in ('old','new'):
        started=time.perf_counter();refs[kind],selection=bind_references(canonical,kind)
        dump_new(HERE/phase/'references'/f'{seed}_{kind}.json',dict(references=refs[kind],selection=selection))
        timing.append(dict(phase='reference',kind=kind,seed=seed,seconds=time.perf_counter()-started,n_events=len(canonical)))
    for variant in variants:
        facts=load_facts(phase,seed,variant)
        if any(f['reference_window']!=c['reference_window'] or f['task']!=c['task'] or
            f['factor_record']!=c['factor_record'] for f,c in zip(facts,canonical)):
            raise RuntimeError('response variants changed declared pre-notice conditions')
        saved={};decisions={}
        for label,kind,method in PATHS:
            try:
                output,clock=process_path(facts,refs[kind],f'{phase}_{seed}_{variant}_{label}',method)
            except Exception as exc:
                error=dict(seed=seed,scenario=variant,path=label,type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc())
                failure_rows.append(error);dump_new(HERE/phase/'failures'/f'{seed}_{variant}_{label}.json',error)
                output=unavailable_outputs(facts,error);clock=dict(label=label,method=method,seconds=None,n_events=len(facts))
            dump_new(HERE/phase/'events'/f'{seed}_{variant}_{label}.json',output)
            decision=assess_outputs(output,label,kind)
            dump_new(HERE/phase/'decisions'/f'{seed}_{variant}_{label}.json',decision)
            saved[label]=output;decisions[label]=decision
            timing.append(dict(seed=seed,scenario=variant,phase='process',**clock))
            print('process complete',phase,seed,variant,label,clock.get('seconds'),flush=True)
        # All process and evidence outputs for this variant are saved before
        # opening evaluator truth. Truth cannot affect models or decisions.
        truth=read(HERE/phase/'evaluator'/f'{seed}_{variant}_truth.json')
        for label,kind,method in PATHS:
            metric_rows.extend(evaluate_outputs(saved[label],truth,refs[kind],seed,variant,label,decisions[label]))
        # Same reference/raw input gives eta exactly, independently of process.
        for kind in ('old','new'):
            a=saved[kind+'_cpop'];b=saved[kind+'_ride_revised']
            for one,two in zip(a,b):
                if one.get('outcome') and two.get('outcome') and one['outcome']['value']!=two['outcome']['value']:
                    raise RuntimeError('raw eta changed across process paths')
    result=dict(phase=phase,seed=seed,n_users=n_users,n_base_events=len(canonical),
        variants=list(variants),all_rows=len(metric_rows),metric_rows=metric_rows,timing=timing,
        failures=failure_rows,data=paths,seconds=time.perf_counter()-tick)
    dump_new(HERE/phase/'blocks'/f'{seed}.json',result)
    return {k:v for k,v in result.items() if k not in ('metric_rows','data')}


def evaluation_stage(phase):
    p=protocol();cal=read(HERE/'calibration/receipt.json');identity=cal['source_identity']
    assert_identity(identity)
    if phase=='test':
        frozen=read(HERE/'freeze_candidate.json')
        if frozen['source_identity']!=identity or frozen['calibration_receipt_sha256']!=sha(HERE/'calibration/receipt.json'):
            raise RuntimeError('test candidate differs from reviewed validation freeze')
    seeds=p['data']['validation_seeds'] if phase=='validation' else p['data']['test_seeds']
    tick=time.perf_counter();rows=[]
    with ProcessPoolExecutor(max_workers=4) as pool:
        futures={pool.submit(evaluate_block,phase,seed):seed for seed in seeds}
        for future in as_completed(futures):
            row=future.result();rows.append(row);print('block complete',phase,row['seed'],row['seconds'],flush=True)
    assert_identity(identity)
    result=dict(phase=phase,protocol_sha256=PROTOCOL_SHA,source_identity=identity,
        blocks=sorted(rows,key=lambda r:r['seed']),seconds=time.perf_counter()-tick,
        calibration_receipt_sha256=sha(HERE/'calibration/receipt.json'),no_test_tuning=True,
        main_test_generated=phase=='test',all_events_retained=True)
    dump_new(HERE/phase/'receipt.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in ('source_identity','blocks')}),flush=True)
    return result


def freeze():
    cal=read(HERE/'calibration/receipt.json');val=read(HERE/'validation/receipt.json')
    assert_identity(cal['source_identity'])
    if val['calibration_receipt_sha256']!=sha(HERE/'calibration/receipt.json'):raise RuntimeError('calibration changed')
    result=dict(protocol_sha256=PROTOCOL_SHA,source_identity=cal['source_identity'],
        calibration_receipt_sha256=sha(HERE/'calibration/receipt.json'),
        validation_receipt_sha256=sha(HERE/'validation/receipt.json'),
        reliable_reference_sha256=sha(MODEL_PATH),
        calibration_models={label:sha(calibration_model_path(label)) for label,_,_ in PATHS},
        candidate_changed_after_validation=False,selection_or_tuning_on_test=False,
        gate='root reviewed validation before invoking this explicit freeze stage')
    dump_new(HERE/'freeze_candidate.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='source_identity'}),flush=True)
    return result


def main():
    import argparse
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--stage',choices=['prepare','calibration','validation','freeze','test'],required=True)
    ap.add_argument('--start',action='store_true')
    args=ap.parse_args()
    if not args.start:raise SystemExit('reviewed stage requires explicit --start')
    protocol()
    if args.stage=='prepare':prepare()
    elif args.stage=='calibration':calibration()
    elif args.stage=='validation':evaluation_stage('validation')
    elif args.stage=='freeze':freeze()
    elif args.stage=='test':evaluation_stage('test')


if __name__=='__main__':main()
