"""Separated development/validation/test for the finite template repair."""
from pathlib import Path
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
import sys,json,time,hashlib,importlib.util
from concurrent.futures import ProcessPoolExecutor,as_completed
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'B1算法'))
from b1_api import load_reference_model,ReferenceWindow,select_ev_reference,analyze_events
from b1_algorithm.api import _default_runtime_config
spec=importlib.util.spec_from_file_location('repair_simulation',ROOT/'work/b1_ev_mainline_20261030/simulation.py')
sim=importlib.util.module_from_spec(spec);spec.loader.exec_module(sim)
METHODS=('ride_template','ride_revised','cpop')
def read(path):return json.loads(path.read_text(encoding='utf-8'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as stream:json.dump(value,stream,ensure_ascii=False,indent=2,allow_nan=False)
def identities():
    files={p.relative_to(ROOT).as_posix():sha(p) for p in (ROOT/'B1算法').rglob('*') if p.is_file()}
    files.update({p.relative_to(ROOT).as_posix():sha(p) for p in (HERE/'protocol.json',HERE/'run.py',ROOT/'work/b1_ev_mainline_20261030/simulation.py')})
    return files
def metrics(outputs,truths,seed,scenario,method,panel):
    rows=[]
    for event,t in zip(outputs,truths):
        r=dict(seed=seed,scenario=scenario,method=method,panel=panel,task_id=t['task_id'],shape=t['latent']['shape'],status=event['status'],
            true_duration=t['cumulative_response_seconds'],true_eta=t['eta'])
        if event['status'] in ('ok','degraded'):
            p=event['process'];s=np.asarray(t['relative_starts_min']);use=(s>=0)&(s<t['W_min']);pred=np.asarray(p['reduction_interval_kw'])
            value=p['features']['selected_curve']['cumulative_response_seconds'];delta=value-t['cumulative_response_seconds'];zero=t['cumulative_response_seconds']==0
            evidence=p['selection_evidence'];records=evidence.get('solver_records',[])
            r.update(curve_rmse=float(np.sqrt(np.mean((pred[use]-np.asarray(t['true_reduction_kw'])[use])**2))),duration_mae=abs(delta),duration_bias=delta,
                no_action=int(zero),false_detection=int(zero and value>0),response=int(not zero),miss=int(not zero and value==0),
                eta=event['outcome']['value'],eta_mae=abs(event['outcome']['value']-t['eta']),fallback=int(event['status']=='degraded'),
                solver_starts=len(records),failed_starts=sum(not q['accepted'] for q in records),
                independent_wait=evidence.get('independent_post_release_wait',False))
        rows.append(r)
    return rows
def bind(facts,model):
    records=[];choices=[]
    for f in facts:
        choice=select_ev_reference(model,ReferenceWindow(**f['reference_window']),f['historical_non_event'])
        assert choice['reference'].reference_status=='available'
        records.append(dict(task=f['task'],starts_min=f['starts_min'],ends_min=f['ends_min'],power_kw=f['power_kw'],reference=choice['reference'],
            noise_sigma_kw=f['noise_sigma_kw'],ev_config=dict(max_charge_kw=7.2,revised_rebound_bound_policy='declared_headroom')))
        choices.append(choice['selection'])
    return records,choices
def run_seed(seed,phase,config,stress=False,source_phase=None):
    source_phase=source_phase or phase
    model=load_reference_model(ROOT/'work/b1_formal_v1_20261029/reference/artifact')
    runtime=_default_runtime_config();runtime.update(artifact_dir=str(HERE/phase/'native'/str(seed)),timeout_seconds=180)
    rows=[];timing=[]
    positive,truth,meta=sim.generate(seed,n_users=config['users'],events_per_user=config['events_per_user'])
    base,choices=bind(positive,model);write(HERE/phase/f'reference/{seed}.json',choices)
    for scenario in ('positive','zero'):
        facts,truth,meta=(positive,truth,meta) if scenario=='positive' else sim.generate(seed,n_users=config['users'],events_per_user=config['events_per_user'],scenario='zero')
        records=[dict(r,power_kw=f['power_kw']) for r,f in zip(base,facts)]
        raw_path=ROOT/f'data/B1_template_repair_v1_20261030/{source_phase}/{seed}_{scenario}_facts.json'
        if raw_path.exists():assert read(raw_path)==facts,'existing development facts changed'
        else:write(raw_path,facts)
        write(HERE/phase/f'evaluator/{seed}_{scenario}_truth.json',truth)
        for method in METHODS:
            start=time.perf_counter();outputs=analyze_events(records,process_method=method,process_config=runtime)
            timing.append(dict(seed=seed,panel='main',scenario=scenario,method=method,events=len(outputs),seconds=time.perf_counter()-start))
            write(HERE/phase/f'events/{seed}_{scenario}_{method}.json',outputs)
            rows.extend(metrics(outputs,truth,seed,scenario,method,'main'))
    if stress:
        for W in (20,37):
            facts,truth,meta=sim.generate(seed+10000,n_users=8,events_per_user=2,W=W,noise_sigma_kw=.15)
            records,choices=bind(facts,model)
            write(ROOT/f'data/B1_template_repair_v1_20261030/{phase}/{seed}_stress{W}_facts.json',facts)
            write(HERE/phase/f'evaluator/{seed}_stress{W}_truth.json',truth)
            for method in METHODS:
                start=time.perf_counter();outputs=analyze_events(records,process_method=method,process_config=runtime)
                timing.append(dict(seed=seed,panel=f'stress{W}',scenario='positive',method=method,events=len(outputs),seconds=time.perf_counter()-start))
                write(HERE/phase/f'events/{seed}_stress{W}_{method}.json',outputs)
                rows.extend(metrics(outputs,truth,seed,'positive',method,f'stress{W}'))
    write(HERE/phase/f'blocks/{seed}.json',dict(metrics=rows,timing=timing));print('completed',phase,seed,flush=True)
    return rows,timing
def main(phase,run_id=None):
    if run_id is not None and (phase!='development' or Path(run_id).name!=run_id):raise ValueError('named reruns only for development')
    label=run_id or phase
    directory=HERE/label;config=read(HERE/'protocol.json')[phase]
    if (directory/'source_freeze.json').exists():raise RuntimeError('phase already frozen; preserve output instead of restarting')
    if phase=='validation' and not (HERE/'development/receipt.json').exists():raise RuntimeError('development must finish before validation')
    if phase=='test':
        freeze=read(HERE/'final_candidate_freeze.json')
        assert freeze['validation_completed'] and all(sha(ROOT/k)==v for k,v in freeze['source'].items())
    write(directory/'source_freeze.json',identities());start=time.perf_counter();rows=[];timing=[]
    for name in identities():
        path=ROOT/name;destination=directory/'source'/name
        destination.parent.mkdir(parents=True,exist_ok=True)
        with destination.open('xb') as stream:stream.write(path.read_bytes())
    with ProcessPoolExecutor(max_workers=min(4,len(config['seeds']))) as executor:
        pending=[executor.submit(run_seed,seed,label,config,phase=='test',phase) for seed in config['seeds']]
        for f in as_completed(pending):
            values=f.result();rows.extend(values[0]);timing.extend(values[1])
    assert read(directory/'source_freeze.json')==identities(),'scientific source changed during run'
    pd.DataFrame(rows).to_csv(directory/'metrics.csv',index=False);pd.DataFrame(timing).to_csv(directory/'timing.csv',index=False)
    write(directory/'receipt.json',dict(completed=True,phase=phase,run_label=label,repeated_development=run_id is not None,independent_blocks=len(config['seeds']),
        main_factual_variants=len(config['seeds'])*config['users']*config['events_per_user']*2,method_rows=len(rows),
        elapsed_seconds=time.perf_counter()-start,oracle_used_by_fitting=False,models_compared=list(METHODS)))
    print('finished',phase,time.perf_counter()-start,flush=True)
if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['development','validation','test'])
    parser.add_argument('--run-id')
    args=parser.parse_args();main(args.phase,args.run_id)
