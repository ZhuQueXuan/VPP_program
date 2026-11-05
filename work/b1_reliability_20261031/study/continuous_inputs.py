"""Phase 2 shared facts/process inputs, only after phase 1 has finished.

No effect fitting/selection is performed here. Positive/zero denote the original
simulator's incentive-effect mechanisms; zero is not redefined as no action.
"""
from pathlib import Path
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
import sys
import json
import time
from concurrent.futures import ProcessPoolExecutor,as_completed
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import run
from generator import BASE,FACTS,shift_fact,protocol,PROTOCOL_SHA,sha


def block(phase,seed):
    p=protocol()['continuous_after_reliability']
    n_users=p['validation_users'] if phase=='validation' else p['test_users']
    shift=8064000 if phase=='validation' else 10080000
    scenarios=('positive',) if phase=='validation' else ('positive','zero')
    base=HERE/'continuous'/phase;rows=[];canonical=None;reference=None;selection=None;tick=time.perf_counter()
    for scenario in scenarios:
        facts,truth,meta=BASE.generate(seed,n_users=n_users,events_per_user=p['events_per_user'],scenario=scenario)
        facts=[shift_fact(f,shift) for f in facts]
        for f in facts:f.update(non_event=False,task_dispatched=True,incentive_signal_announced=True,simulation_variant=scenario)
        if phase=='test':
            selected=run.read(HERE.parent/'effects/selection_receipt.json')
            if min(f['task']['notice_min'] for f in facts)<=selected['validation_times']['final_label_available_min']:
                raise RuntimeError('test notices must follow completed validation selection')
        for t in truth:t['clock_shift_min']=shift
        if canonical is None:
            canonical=facts
            reference,selection=run.bind_references(facts,'new')
            run.dump_new(base/'references'/f'{seed}.json',dict(references=reference,selection=selection))
        elif any(a['reference_window']!=b['reference_window'] or a['factor_record']!=b['factor_record'] for a,b in zip(canonical,facts)):
            raise RuntimeError('original continuous paired conditions changed')
        source=FACTS/f'continuous_{phase}'
        factpath=source/f'{seed}_{scenario}_facts.json'
        truthpath=base/'evaluator'/f'{seed}_{scenario}_truth.json'
        metapath=source/f'{seed}_{scenario}_metadata.json'
        run.dump_new(factpath,facts);run.dump_new(truthpath,truth)
        run.dump_new(metapath,dict(meta,clock_shift_min=shift,protocol_sha256=PROTOCOL_SHA,
            original_simulator_sha256=sha(run.BASE_SOURCE),reference_model_id=run.load_ev_reliable_reference_model(run.MODEL_PATH).model_id,
            zero_interpretation='zero incentive effect, original baseline participation and actions retained; not a null physical-action label'))
        factors=[f['factor_record'] for f in facts]
        factorpath=base/'factor_inputs'/f'{seed}_{scenario}.json'
        run.dump_new(factorpath,factors)
        output,timing=run.process_path(facts,reference,f'continuous_{phase}_{seed}_{scenario}','cpop')
        eventpath=base/'events'/f'{seed}_{scenario}.json'
        run.dump_new(eventpath,output)
        # Preserve the entire event population. Failures block factor fitting;
        # they are never silently removed to get a convenient sample.
        good=sum(e['status']=='ok' for e in output)
        row=dict(phase=phase,seed=seed,scenario=scenario,n_users=n_users,n_events=len(facts),
            valid_events=good,all_events_preserved=True,factors=str(factorpath),events=str(eventpath),
            evaluator_truth=str(truthpath),facts=str(factpath),metadata=str(metapath),
            min_notice_min=min(f['task']['notice_min'] for f in facts),
            max_label_available_min=max(f['availability']['power_records_available_at_min'] for f in facts),
            timing=timing,sha256={str(p.relative_to(run.ROOT)):sha(p) for p in (factpath,truthpath,metapath,factorpath,eventpath)})
        rows.append(row);print('continuous input complete',phase,seed,scenario,len(output),timing['seconds'],flush=True)
    result=dict(seed=seed,phase=phase,rows=rows,seconds=time.perf_counter()-tick)
    run.dump_new(base/'blocks'/f'{seed}.json',result)
    return result


def stage(phase):
    if not (HERE/'test/receipt.json').is_file():raise RuntimeError('phase 1 main test must finish before phase 2 inputs')
    protocol()
    frozen=run.read(HERE/'freeze_candidate.json')
    run.assert_identity(frozen['source_identity'])
    if sha(run.MODEL_PATH)!=frozen['reliable_reference_sha256']:raise RuntimeError('reference differs from phase 1 freeze')
    p=protocol()['continuous_after_reliability']
    seeds=[p['validation_seed']] if phase=='validation' else p['test_seeds']
    if phase=='test' and not (HERE/'continuous/validation/receipt.json').is_file():raise RuntimeError('continuous validation inputs missing')
    if phase=='test':
        selection=run.read(HERE.parent/'effects/selection_receipt.json')
        if sha(HERE.parent/'effects/selection.json')!=selection['selection_artifact_sha256']:
            raise RuntimeError('frozen continuous selection changed before test generation')
    base_identity=run.source_identity();identity=dict(base_identity)
    identity[str(Path(__file__).relative_to(run.ROOT)).replace('\\','/')]=sha(__file__)
    reference_sha=sha(run.MODEL_PATH);tick=time.perf_counter();blocks=[]
    with ProcessPoolExecutor(max_workers=4) as pool:
        futures={pool.submit(block,phase,seed):seed for seed in seeds}
        for future in as_completed(futures):blocks.append(future.result())
    if sha(run.MODEL_PATH)!=reference_sha:raise RuntimeError('frozen reference changed')
    run.assert_identity(base_identity)
    if identity[str(Path(__file__).relative_to(run.ROOT)).replace('\\','/')]!=sha(__file__):raise RuntimeError('phase 2 harness source changed')
    result=dict(phase=phase,schema='b1.reliability-continuous-inputs.v1',
        blocks=sorted(blocks,key=lambda x:x['seed']),seconds=time.perf_counter()-tick,
        source_identity=identity,reference_artifact_sha256=reference_sha,protocol_sha256=PROTOCOL_SHA,
        model_refit=False,effects_fit=False,events_filtered=False,
        scalar_factor_schema='JSON list of original factor_record dicts, L/U only, absolute availability shifted',
        events_schema='JSON list of full B1 analyze_events outputs; same frozen reference plus native original CPOP')
    run.dump_new(HERE/'continuous'/phase/'receipt.json',result)
    print(json.dumps(dict(phase=phase,n_blocks=len(blocks),seconds=result['seconds'])),flush=True)
    return result


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--phase',choices=['validation','test'],required=True);p.add_argument('--start',action='store_true')
    a=p.parse_args()
    if not a.start:raise SystemExit('explicit root start required after phase 1 completion')
    stage(a.phase)
