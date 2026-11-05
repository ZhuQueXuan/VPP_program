"""Pre-test frozen original-meter-sigma sensitivity; no main result mutation."""
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
import sys,time
from collections import Counter
import numpy as np
from pilot_common import HERE,ROOT,read,write_new,sha,facts_path
from run import phase_facts,process,selected_reference,predict_model,PROFILE,data_for,extracted,scan,assert_freeze
from b1_algorithm import provided_reference
from b1_algorithm.api import analyze_events,_default_runtime_config

def fit(facts,references,label):
    tick=time.perf_counter();records=[]
    for f,ref in zip(facts,references):
        records.append(dict(task=f['task'],starts_min=f['starts_min'],ends_min=f['ends_min'],power_kw=f['power_kw'],
            reference=provided_reference(f['task'],f['starts_min'],f['ends_min'],ref,available_at_min=f['task']['notice_min']),
            noise_sigma_kw=.05,ev_config=PROFILE))
    config=_default_runtime_config();config['artifact_dir']=str(HERE/'native_sensitivity'/label)
    original=analyze_events(records,process_method='cpop',process_config=config)
    write_new(HERE/'sensitivity_native_outputs'/f'{label}.json',original)
    out=[]
    for f,ref,o in zip(facts,references,original):
        p=o.get('process') or {};curve=p.get('reduction_interval_kw') if o['status']=='ok' and p.get('method')=='CPOP' else None
        out.append(dict(task_id=f['task']['task_id'],user_id=f['task']['user_id'],method='cpop_meter_sigma',
            status='ok' if curve is not None else 'unavailable',prediction=curve,
            features=extracted(data_for(f,ref,.05),curve) if curve is not None else None,
            eta_raw=p.get('eta_raw'),scan_score=scan(curve) if curve is not None else None))
    return out,dict(label=label,n=len(out),seconds=time.perf_counter()-tick,status_counts=dict(Counter(r['status'] for r in out)))

def calibrate():
    assert_freeze()
    # The supplementary choice must predate generation of any main test facts.
    if (HERE/'data_receipts'/'test.json').exists():raise RuntimeError('supplement must freeze before test')
    facts=phase_facts('calibration');refs=read(HERE/'references'/'calibration.json')['prediction']
    rows,timing=fit(facts,refs,'calibration');maxima={}
    for row in rows:
        if row['scan_score'] is None:raise RuntimeError('cannot omit unavailable calibration')
        uid=row['user_id'];maxima[uid]=max(maxima.get(uid,-float('inf')),row['scan_score'])
    assert len(maxima)==48
    write_new(HERE/'sensitivity_calibration_outputs.json',rows)
    write_new(HERE/'sensitivity_calibration.json',dict(maxima=maxima,alpha=.05,sigma=.05,timing=timing))
    write_new(HERE/'supplement_freeze.json',dict(script_sha256=sha(__file__),
        protocol_sha256=sha(HERE/'supplement_protocol.json'),calibration_sha256=sha(HERE/'sensitivity_calibration.json'),
        main_freeze_sha256=sha(HERE/'freeze.json'),test_generated=False,validation_seen=True))

def evaluate(phase):
    assert_freeze();fr=read(HERE/'supplement_freeze.json')
    assert fr['script_sha256']==sha(__file__) and fr['protocol_sha256']==sha(HERE/'supplement_protocol.json')
    assert fr['calibration_sha256']==sha(HERE/'sensitivity_calibration.json') and fr['main_freeze_sha256']==sha(HERE/'freeze.json')
    if not (HERE/f'{phase}_completed.json').exists():raise RuntimeError('read same already processed main facts only')
    design=read(HERE/'protocol.json')['stages'][phase];cal=read(HERE/'sensitivity_calibration.json')
    maxima=np.asarray(list(cal['maxima'].values()));timings=[]
    for seed in design.get('seeds',[design.get('seed')]):
        refs=read(HERE/'references'/f'{phase}_{seed}.json')['prediction']
        for variant in design['variants']:
            facts=read(facts_path(phase,seed,variant));rows,timing=fit(facts,refs,f'{phase}_{seed}_{variant}')
            timings.append(timing)
            for row in rows:
                pv=None if row['scan_score'] is None else float((1+np.sum(maxima>=row['scan_score']))/49)
                row.update(evidence_p=pv,evidence_status='unavailable' if pv is None else 'evidence' if pv<=.05 else 'inconclusive')
            write_new(HERE/'sensitivity_outputs'/phase/f'{seed}_{variant}.json',rows)
            print('meter_sigma',phase,seed,variant,timing['status_counts'],flush=True)
    write_new(HERE/f'sensitivity_{phase}_completed.json',dict(timings=timings,parameters_changed=False))

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['calibrate','validation','test']);a=p.parse_args()
    calibrate() if a.stage=='calibrate' else evaluate(a.stage)
