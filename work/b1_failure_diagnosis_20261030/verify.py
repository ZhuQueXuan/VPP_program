"""Recompute diagnostic invariants and saved metrics without running solvers."""
from pathlib import Path
import json,sys,hashlib
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];OLD=ROOT/'work/b1_ev_mainline_20261030'
sys.path.insert(0,str(ROOT/'B1算法'))
from b1_algorithm.process._ride_template import interval_average
from run import data_for
def read(path):return json.loads(path.read_text(encoding='utf-8'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    target=HERE/'verification_receipt.json'
    if target.exists():raise RuntimeError('completed audit cannot be overwritten')
    freeze=read(HERE/'source_freeze.json');assert all(sha(ROOT/k)==v for k,v in freeze.items())
    protected=read(OLD/'final_manifest.json')['protected_files'];assert len(protected)==75
    assert all(sha(ROOT/k)==v for k,v in protected.items())
    raw_old=read(OLD/'corrective_replay_receipt.json');assert all(sha(ROOT/k)==v for k,v in raw_old['original_raw_sha256'].items())
    assert all(sha(ROOT/k)==v for k,v in raw_old['original_event_sha256'].items())
    metrics=pd.read_csv(HERE/'diagnostic_metrics.csv');assert len(metrics)==5120
    count=0;scalar_checks=0;witness_checks=0
    for seed in read(HERE/'protocol.json')['seeds']:
        saved=read(HERE/f'curves/{seed}.json')
        for scenario in ('positive','zero'):
            facts=read(ROOT/f'data/B1_EV_mainline_v1_20261030/{seed}_{scenario}_facts.json')[:32]
            truths=read(OLD/f'evaluator/{seed}_{scenario}_truth.json')[:32]
            group=metrics[(metrics.seed==seed)&(metrics.scenario==scenario)]
            assert len(group)==320
            for i,(f,t) in enumerate(zip(facts,truths)):
                assert f['task']['task_id']==t['task_id'];s=np.array(t['relative_starts_min']);use=(s>=0)&(s<30)
                clean=data_for(f,t,'oracle_clean');noisy=data_for(f,t,'oracle_noise');remove=data_for(f,t,'no_post_rebound');relax=data_for(f,t,'relaxed_rebound')
                assert np.max(abs(clean['y']-np.asarray(t['true_reduction_kw'])))<1e-12
                assert np.max(abs(noisy['y']-clean['y']+np.asarray(t['measurement_error_kw'])))<1e-12
                assert np.array_equal(clean['y'][use],remove['y'][use]) and np.all(remove['y'][s>=30]==0)
                assert np.array_equal(clean['y'],relax['y']) and clean['sigma']==relax['sigma']==.05
                for level in ('oracle_noise','oracle_clean','no_post_rebound','relaxed_rebound'):
                    truth=np.asarray(t['true_reduction_kw']).copy()
                    if level=='no_post_rebound':truth[s>=30]=0
                    for method in ('ride_template','cpop'):
                        output=saved[f'{scenario}_{level}_{method}'][i];curve=np.array(output['reduction_interval_kw'])
                        assert output['status']=='ok';r=group[(group.level==level)&(group.method==method)&(group.task_id==t['task_id'])].iloc[0]
                        duration=float(np.sum(use&(curve>=.15))*60)
                        rmse=float(np.sqrt(np.mean((curve[use]-truth[use])**2)))
                        assert abs(r['duration_mae']-abs(duration-t['cumulative_response_seconds']))<1e-9
                        assert abs(r['curve_rmse']-rmse)<1e-12
                        scalar_checks+=2;count+=1
                for method in ('ride_template','cpop'):
                    original=read(OLD/f'events/{seed}_{scenario}_{method}.json')[i]['process']
                    r=group[(group.level=='selected_noise')&(group.method==method)&(group.task_id==t['task_id'])].iloc[0]
                    assert abs(r['duration_mae']-abs(original['features']['selected_curve']['cumulative_response_seconds']-t['cumulative_response_seconds']))<1e-9
                    scalar_checks+=1
                a=saved[f'{scenario}_oracle_clean_cpop'][i];b=saved[f'{scenario}_relaxed_rebound_cpop'][i]
                assert a==b
    for p in read(HERE/'optimization_probes.json'):
        seed=p['seed'];truths=read(OLD/f'evaluator/{seed}_positive_truth.json')
        truth=next(t for t in truths if t['task_id']==p['task_id']);s=np.asarray(truth['relative_starts_min']);theta=np.array(p['witness_theta'])
        fitted=1.5*interval_average(theta,30.,s,s+1)
        assert np.max(abs(fitted-np.asarray(truth['true_reduction_kw'])))<1e-10
        witness_checks+=1
    receipt=dict(passed=True,source_files_matched=len(freeze),protected_files_matched=75,
        old_raw_files_matched=len(raw_old['original_raw_sha256']),old_event_files_matched=len(raw_old['original_event_sha256']),
        process_outputs_recomputed=count,metric_scalars_recomputed=scalar_checks,feasible_witness_checks=witness_checks,
        true_reference_and_noise_ablation_exact=True,post_ablation_preserves_task_power_and_target=True,
        relaxed_rebound_does_not_change_CPOP=True,solver_reruns=False,model_adopted=False)
    with target.open('x',encoding='utf-8') as stream:json.dump(receipt,stream,ensure_ascii=False,indent=2)
    print(json.dumps(receipt))
if __name__=='__main__':main()
