"""Independent read-only checks on stored final facts, outputs and scores.

No estimator/process fitting is run here. Selected references are replayed on
only a fixed first/last-event sample to check raw eta arithmetic and digests.
"""
from pathlib import Path
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
import json
import hashlib
import sys
import numpy as np

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT/'B1算法'))
from b1_api import ReferenceWindow,load_reference_model,select_ev_reference
from b1_algorithm.effects.frozen import load_continuous_model,query_continuous_model


def read(path):return json.loads(path.read_text(encoding='utf-8'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def dump(path,value):
    with path.open('x',encoding='utf-8') as f:json.dump(value,f,ensure_ascii=False,indent=2,allow_nan=False)


def main():
    checks={};bad=[]
    def check(name,condition):
        checks[name]=checks.get(name,0)+1
        if not condition:bad.append(dict(check=name,occurrence=checks[name]))
    protocol=read(HERE.parent/'protocol.json');p=protocol['step6'];seeds=p['seeds']
    freeze=read(HERE/'source_freeze.json')
    for name,expected in freeze.items():
        check('live_scientific_source_matches_freeze',sha(ROOT/name)==expected)
        check('retained_source_snapshot_matches_freeze',sha(HERE/'source'/name)==expected)
    metrics=read(HERE/'process.json');rows={(v['seed'],v['scenario'],v['method'],v['task_id']):v for v in metrics}
    check('exact_process_row_count_no_duplicates',len(metrics)==len(rows)==12288)
    model=load_reference_model(ROOT/'work/b1_formal_v1_20261029/reference/artifact')
    expected_indices=[5*u+j for u in range(128) for j in (3,4)]
    query_count=0;all_eta=[]
    for seed in seeds:
        positive=read(ROOT/f'data/B1_finish_chain_v1_20261030/{seed}_positive_facts.json')
        zero=read(ROOT/f'data/B1_finish_chain_v1_20261030/{seed}_zero_facts.json')
        check('all_640_facts_retained_per_scenario',len(positive)==len(zero)==640)
        for a,b in zip(positive,zero):
            check('paired_facts_X_D_reference_input_identical',a['X']==b['X'] and a['offered_incentive']==b['offered_incentive'] and a['reference_window']==b['reference_window'])
            check('paired_facts_identity_identical',a['task']==b['task'])
        for scenario,facts in (('positive',positive),('zero',zero)):
            factor=read(HERE/f'factor_inputs/{seed}_{scenario}.json')
            truth=read(HERE/f'evaluator/{seed}_{scenario}_truth.json')
            check('target_indices_only3and4',factor['target_indices']==expected_indices)
            check('C0_frozen_choice',factor['representation']=='C0')
            targets=[facts[i] for i in expected_indices];target_truth=[truth[i] for i in expected_indices]
            for record,provenance,fact in zip(factor['records'],factor['history'],targets):
                check('factor_identity_matches_target',all(record[k]==fact['task'][k] for k in ('task_id','user_id','meter_id')))
                check('C0_LU_and_six_zero_contract',[record['deadline_slack'],record['demand_urgency']]==fact['X'] and all(record[f'history_{j}']==0 for j in range(6)))
                check('factor_availability_pre_treatment',all(record['state_as_of_min'][k]<=record['available_at_min'][k]<=record['treatment_set_min'] for k in ('deadline_slack','demand_urgency',*(f'history_{j}' for j in range(6)))))
                past=provenance['history'];uid=fact['task']['user_id']
                check('history_exact_events012',len(past)==3 and [r['task_id'] for r in past]==[uid+'-event-'+str(j) for j in range(3)])
                check('history_same_object_and_before_current_notice',all(r['user_id']==uid and r['meter_id']==fact['task']['meter_id'] and r['observation_end_min']<=r['observed_available_at_min']<=fact['task']['notice_min'] for r in past))
                check('no_encoder_refit_or_current_outcome',provenance['encoder_refitted'] is False and provenance['current_outcome_used'] is False)
            bymethod={m:read(HERE/f'events/{seed}_{scenario}_{m}.json') for m in p['processes']}
            for method,events in bymethod.items():
                check('all_256_outputs_retained',len(events)==256)
                for e,t,f in zip(events,target_truth,targets):
                    check('event_completed_and_exact_identity',e['status'] in ('ok','degraded') and e['task']==f['task']=={**e['task']})
                    if e['status'] not in ('ok','degraded'):continue
                    metric=rows[(seed,scenario,method,t['task_id'])];process=e['process']
                    curve=np.asarray(process['reduction_interval_kw']);times=np.asarray(t['relative_starts_min']);use=(times>=0)&(times<30.)
                    threshold=process['analysis_profile']['onset_fraction']*1.5
                    duration=float(np.sum(curve[use]>=threshold)*60.)
                    check('selected_duration_is_exact_count_of_declared_threshold_bins',duration==process['features']['selected_curve']['cumulative_response_seconds'])
                    td=float(np.sum(np.asarray(t['true_reduction_kw'])[use]>=.1*1.5)*60.)
                    check('evaluator_duration_independent_bin_recount',td==t['cumulative_response_seconds'])
                    check('duration_score_recount',abs(duration-td)==metric['duration_mae'])
                    rmse=float(np.sqrt(np.mean((curve[use]-np.asarray(t['true_reduction_kw'])[use])**2)))
                    check('curve_rmse_score_recount',abs(rmse-metric['curve_rmse'])<1e-12)
                    check('false_alarm_recount',metric['false_detection']==int(td==0 and duration>0))
                    check('miss_recount',metric['miss']==int(td>0 and duration==0))
                    check('eta_score_from_same_raw_outcome',metric['eta']==e['outcome']['value']==process['eta_raw'])
            for j in range(256):
                events=[bymethod[m][j] for m in p['processes']]
                check('all_processes_same_bound_raw_input_digest',len(set(e['input_digest'] for e in events))==1)
                check('raw_eta_identical_for_every_target',len(set(e['outcome']['value'] for e in events))==1)
            # Fixed first/last sample; not selected by observed score.
            for j in (0,1,254,255):
                f=targets[j];e=bymethod['cpop'][j]
                selected=select_ev_reference(model,ReferenceWindow(**f['reference_window']),f['historical_non_event'])
                b=np.asarray(selected['reference'].reference_kw);power=np.asarray(f['power_kw']);s=np.asarray(f['starts_min']);ends=np.asarray(f['ends_min'])
                use=(s>=f['task']['start_min'])&(s<f['task']['end_min'])
                eta=float(np.sum((b-power)[use]*(ends-s)[use])/(1.5*30.))
                check('raw_eta_independent_width_integral_sample',abs(eta-e['outcome']['value'])<=1e-12)
                payload=dict(task=e['task'],starts=s.tolist(),ends=ends.tolist(),power=power.tolist(),reference=b.tolist())
                digest=hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()
                check('frozen_reference_replay_matches_bound_input_digest_sample',digest==e['input_digest'])
            eta_results=[]
            for method in p['processes']:
                eta_results.append(read(HERE/f'effects/{seed}_{scenario}_{method}_eta.json'))
            check('eta_effect_status_invariant',len(set(e['status'] for e in eta_results))==1)
            check('eta_effect_curves_invariant',eta_results[0]['causal_curve']==eta_results[1]['causal_curve']==eta_results[2]['causal_curve'])
            all_eta.extend(eta_results)
            for label in ('ride_revised_duration','cpop_duration','ride_template_duration','raw_duration','ride_revised_eta','cpop_eta','ride_template_eta'):
                generic=read(HERE/f'effects/{seed}_{scenario}_{label}.json')
                path=HERE/f'models/{seed}_{scenario}_{label}.json'
                if not path.exists():
                    check('missing_model_is_explicit_unsupported_fit',generic['status']=='unsupported');continue
                frozen=load_continuous_model(path);payload=json.loads(frozen.payload_json)
                expected_x=[[r[k] for k in ('deadline_slack','demand_urgency',*(f'history_{j}' for j in range(6)))] for r in factor['records']]
                check('frozen_model_X_D_users_match_bound_factor_records',payload['X']==expected_x and payload['dose']==[r['offered_incentive'] for r in factor['records']] and payload['users']==[r['user_id'] for r in factor['records']])
                query=read(HERE/f'queries/{seed}_{scenario}_{label}.json');query_count+=1
                check('frozen_query_status_equals_generic',query['status']==generic['status'])
                if generic['status']=='causal':
                    for key in ('contrasts','mean_outcomes'):
                        check('frozen_query_point_equals_same_Kennedy',np.allclose(query['curve'][key],generic['causal_curve'][key],atol=1e-10,rtol=0))
                    for key in ('standard_errors','lower','upper'):
                        check('frozen_query_band_equals_same_Kennedy',np.allclose(query['inference'][key],generic['inference'][key],atol=1e-10,rtol=0))
                if label.endswith('_eta'):
                    check('eta_no_unit_incompatible_threshold_file',not (HERE/f'thresholds/{seed}_{scenario}_{label}.json').exists())
                else:
                    threshold=read(HERE/f'thresholds/{seed}_{scenario}_{label}.json')
                    check('duration_threshold_declared_target_and_mesh',threshold['target_contrast']==120 and threshold['mesh_max_width']<=.04000000001)
            print('audited',seed,scenario,flush=True)
    result=dict(passed=not bad,check_categories=checks,scalar_or_contract_checks=sum(checks.values()),
        failures=bad,main_query_files_checked=query_count,process_rows_checked=len(metrics),
        independent_scoring_or_contract_check=True,estimator_or_process_refitted=False,
        selected_reference_replayed_for_fixed64_target_sample=True,source_freeze_sha256=sha(HERE/'source_freeze.json'))
    dump(HERE/'audit_receipt.json',result)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
