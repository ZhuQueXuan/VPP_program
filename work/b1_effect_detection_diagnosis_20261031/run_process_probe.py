"""Already-seen paired process oracle diagnostics; never a deployable input."""
import os
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
import sys,json,time,hashlib
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor,as_completed
import numpy as np
import pandas as pd
W=Path(__file__).resolve().parent;R=W.parents[1];OLD=R/'work/b1_finish_ev_20261030/final_chain'
sys.path.insert(0,str(R/'B1算法'))
from b1_algorithm.api import _default_runtime_config
from b1_algorithm.process.batch import identify_process_batch

def read(p):return json.loads(p.read_text(encoding='utf-8'))
def dump(p,v):
    p.parent.mkdir(exist_ok=True,parents=True)
    with p.open('x',encoding='utf-8') as f:json.dump(v,f,ensure_ascii=False,allow_nan=False)
def score(p,t,seed,scenario,condition,method):
    zero=t['cumulative_response_seconds']==0
    row=dict(seed=seed,scenario=scenario,condition=condition,method=method,task_id=t['task_id'],
        shape=t['latent']['shape'],status=p['status'],true_duration=t['cumulative_response_seconds'],
        no_action=int(zero),true_eta=t['eta'])
    if p['status'] in ('ok','degraded'):
        curve=np.asarray(p['reduction_interval_kw']);s=np.asarray(t['relative_starts_min']);use=(s>=0)&(s<t['W_min'])
        duration=p['features']['selected_curve']['cumulative_response_seconds'];raw=p['features']['raw_observed']['cumulative_response_seconds']
        row.update(duration=duration,error=duration-t['cumulative_response_seconds'],mae=abs(duration-t['cumulative_response_seconds']),
            raw_duration=raw,raw_mae=abs(raw-t['cumulative_response_seconds']),
            curve_rmse=float(np.sqrt(np.mean((curve[use]-np.asarray(t['true_reduction_kw'])[use])**2))),
            false_detection=int(zero and duration>0),miss=int(not zero and duration==0),
            eta=p['eta_raw'],eta_error=p['eta_raw']-t['eta'])
    return row

def run(seed):
    rows=[];times=[];indices=[u*5+j for u in range(16) for j in (3,4)]
    target_indices=[u*2+j for u in range(16) for j in (0,1)]
    runtime=_default_runtime_config();runtime.update(artifact_dir=str(W/'process/native'/str(seed)),timeout_seconds=180)
    for scenario in ('positive','zero'):
        facts=read(R/f'data/B1_finish_chain_v1_20261030/{seed}_{scenario}_facts.json')
        truth=read(OLD/f'evaluator/{seed}_{scenario}_truth.json')
        facts=[facts[i] for i in indices];truth=[truth[i] for i in indices]
        for method in ('ride_revised','cpop'):
            saved=read(OLD/f'events/{seed}_{scenario}_{method}.json')
            for event,t in zip([saved[i] for i in target_indices],truth):
                assert event['task']['task_id']==t['task_id']
                rows.append(score(event['process'],t,seed,scenario,'saved_predicted_reference',method))
        for condition in ('true_reference_observed_power','true_reference_noiseless_power'):
            requests=[]
            for f,t in zip(facts,truth):
                assert f['task']['task_id']==t['task_id']
                task=dict(f['task']);start=task['start_min'];task.update(start_min=0.,end_min=30.,notice_min=-15.)
                requests.append(dict(starts_min=(np.asarray(f['starts_min'])-start).tolist(),
                    ends_min=(np.asarray(f['ends_min'])-start).tolist(),
                    power_kw=f['power_kw'] if condition.endswith('observed_power') else t['noiseless_power_kw'],
                    reference_kw=t['true_reference_kw'],task=task,noise_sigma_kw=.05,
                    ev_config=dict(max_charge_kw=7.2,revised_rebound_bound_policy='declared_headroom')))
            for method in ('ride_revised','cpop'):
                tick=time.perf_counter();outputs=identify_process_batch(requests,config=runtime,method=method)
                assert len(outputs)==len(truth)
                dump(W/f'process/events/{seed}_{scenario}_{condition}_{method}.json',dict(
                    diagnostic_only=True,oracle_reference_ex_ante_available=False,condition=condition,events=outputs))
                rows.extend(score(p,t,seed,scenario,condition,method) for p,t in zip(outputs,truth))
                times.append(dict(seed=seed,scenario=scenario,condition=condition,method=method,seconds=time.perf_counter()-tick))
                print(seed,scenario,condition,method,round(times[-1]['seconds'],2),flush=True)
    dump(W/f'process/blocks/{seed}.json',dict(rows=rows,timing=times))
    return rows,times

def main():
    folder=W/'process';folder.mkdir(exist_ok=True)
    if (folder/'started.json').exists():raise RuntimeError('probe already started; preserve output')
    freeze=read(W/'source_freeze.json');dump(folder/'started.json',dict(protocol_sha256=hashlib.sha256((W/'protocol.json').read_bytes()).hexdigest(),source=freeze))
    started=time.perf_counter();rows=[];timing=[];failures=[]
    with ProcessPoolExecutor(max_workers=4) as pool:
        pending={pool.submit(run,seed):seed for seed in range(7240200,7240208)}
        for f in as_completed(pending):
            try:a,b=f.result();rows.extend(a);timing.extend(b)
            except Exception as exc:failures.append(dict(seed=pending[f],error=str(exc)))
    frame=pd.DataFrame(rows);frame.to_csv(folder/'metrics.csv',index=False)
    summary=[]
    for keys,g in frame.groupby(['scenario','condition','method']):
        ok=g[g['status'].isin(['ok','degraded'])]
        summary.append(dict(zip(('scenario','condition','method'),keys),events=len(g),completed=len(ok),
            duration_mae=float(ok.mae.mean()),duration_bias=float(ok.error.mean()),curve_rmse=float(ok.curve_rmse.mean()),
            no_action=int(ok.no_action.sum()),false_detection=int(ok.false_detection.sum()),miss=int(ok.miss.sum()),
            eta_mae=float(ok.eta_error.abs().mean()),raw_duration_mae=float(ok.raw_mae.mean())))
    assert all(hashlib.sha256((R/p).read_bytes()).hexdigest()==digest for p,digest in freeze.items())
    dump(folder/'summary.json',dict(rows=summary,timing=timing,failures=failures,wall_seconds=time.perf_counter()-started,
        source_unchanged=True,subset_variants=512,method_condition_rows=len(rows),is_new_test=False,
        oracle_used_only_in_explicit_diagnostic=True))
    print('DONE',len(rows),'failures',len(failures),'wall',time.perf_counter()-started,flush=True)
if __name__=='__main__':main()
