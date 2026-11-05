"""Score the pre-test frozen CPOP sensitivity, without fitting or selecting."""
from collections import defaultdict
import numpy as np
from pilot_common import HERE,read,write_new,facts_path,truth_path
from assess import summarize
from run import data_for,extracted,assert_freeze

def evaluate(phase):
    assert_freeze();design=read(HERE/'protocol.json')['stages'][phase]
    main=read(HERE/f'{phase}_metrics.json')
    lookup={(r['seed'],r['variant'],r['task_id']):r for r in main if r['method']=='cpop'}
    rows=[];user_blocks=[]
    for seed in design.get('seeds',[design.get('seed')]):
        for variant in design['variants']:
            facts=read(facts_path(phase,seed,variant));truth=read(truth_path(phase,seed,variant))
            outputs=read(HERE/'sensitivity_outputs'/phase/f'{seed}_{variant}.json')
            for fact,t,o in zip(facts,truth,outputs):
                assert fact['task']['task_id']==t['task_id']==o['task_id']
                true=np.asarray(t['true_reduction_kw']);b=np.asarray(t['true_reference_kw'])
                tf=extracted(data_for({**fact,'power_kw':(b-true).tolist()},b,.05),true)
                f=o['features'];pred=None if o['prediction'] is None else np.asarray(o['prediction'])
                onset=f['onset_interval_s'] if f else None;true_onset=tf['onset_interval_s']
                row=dict(lookup[(seed,variant,t['task_id'])],method='cpop_meter_sigma',status=o['status'],
                    pred_duration=f['cumulative_response_seconds'] if f else None,pred_onset=onset,
                    evidence_p=o['evidence_p'],evidence_status=o['evidence_status'],
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
                    onset_error_seconds=abs(float(np.mean(onset))-float(np.mean(true_onset))) if onset is not None and true_onset is not None else None)
                rows.append(row)
            users=defaultdict(list)
            for o in outputs:users[o['user_id']].append(o)
            assert all(len(v)==2 for v in users.values())
            user_blocks.append(dict(seed=seed,variant=variant,users=len(users),
                evidence_users=sum(any(r['evidence_status']=='evidence' for r in v) for v in users.values())))
    groups=defaultdict(list)
    for r in rows:groups[r['variant']].append(r)
    result=dict(phase=phase,method='cpop_meter_sigma',sigma=.05,validation_seen_when_designed=True,
        test_used_for_setting_selection=False,groups=[dict(variant=k,**summarize(v)) for k,v in sorted(groups.items())],
        user_blocks=user_blocks,rows=len(rows),same_algorithm_as_main_comparator=True)
    write_new(HERE/f'sensitivity_{phase}_assessment.json',result)
    write_new(HERE/f'sensitivity_{phase}_metrics.json',rows)
    print(__import__('json').dumps(result,ensure_ascii=False))

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['validation','test']);evaluate(p.parse_args().phase)
