from common import *

a=read('assessment.json');public=read('public_checks.json');assert a['adopted'] and all(a['checks'].values()) and public['all_passed']
allowed={'B1算法/b1_algorithm/process/api.py','B1算法/b1_algorithm/process/batch.py','B1算法/README.md'};changed=[]
for p,h in read('freeze.json')['source_sha256'].items():
    if sha(ROOT/p)!=h:
        assert p in allowed,p
        assert sha(HERE/'production_before'/p)==h,p
        changed.append(p)
for p,h in read('release_build.json')['files'].items():assert sha(ROOT/p)==h,p
old=ROOT/'work/b1_duration_joint_20261102'
for p,h in read(old/'completion_receipt.json')['result_sha256'].items():assert sha(old/p)==h,p
rows=read('main_test/metrics.json')+read('weak_test/metrics.json');independent={}
for method in ['cpop','labs','retained','candidate']:
    rr=[r for r in rows if r['method']==method];correct=sum(r['positive_truth']==(r['predicted_cumulative_seconds']>0) for r in rr)
    independent[method]=dict(n=len(rr),correct=correct,accuracy=correct/len(rr))
    assert abs(correct/len(rr)-a['summary']['pooled'][method]['task_accuracy'])<1e-12
by_old={r['task_id']:r for r in rows if r['method']=='retained'};rejected=[r for r in rows if r['method']=='candidate' and r['rejected']]
assert len(rejected)==74 and not any(r['positive_truth'] for r in rejected)
assert all(by_old[r['task_id']]['positive_prediction'] for r in rejected)
assert all(all(r[k]==by_old[r['task_id']][k] for k in ['predicted_cumulative_seconds','predicted_longest_seconds','positive_prediction','localized_miss']) for r in rows if r['method']=='candidate' and not r['rejected'])
paths=['assessment.json','public_checks.json','selected.json','freeze.json','protocol.json','training_receipt.json','production_before.json','release_build.json','diagnosis.json','README.md','method_notes.md']
for stage in ['main_test','weak_test']:
    paths += [stage+'/'+p for p in ['facts.json','curves.json','metrics.json','assessment.json','baseline.json','effective_X.npy']]
    for panel in ['minute','10s']:paths += [stage+'/'+panel+'/'+p for p in ['truth.json','mixed_truth.json']]
write('completion_receipt.json',dict(status='complete',adopted=True,entrypoint='analyze_event(s)(...,process_method="effective_response_refined")',
    prior_version_preserved='gap_duration_refined',global_default_unchanged=True,known_reference_only=True,
    final_inputs=2808,base_trajectories=792,four_method_rows=11232,independently_recomputed_task_accuracy=independent,
    false_effective_tasks=dict(previous=518,current=444,reduction_percent=100*74/518),
    whole_misses=dict(previous=56,current=56),localized_misses=dict(previous=126,current=126),genuine_short_misses=dict(inputs=300,previous=85,current=85),
    rejected_records=74,rejected_base_trajectories=40,new_true_task_rejections=0,all_rejected_real_underthreshold=True,
    main_results_unchanged=True,weak_false_effective_tasks=dict(previous=472,current=398),weak_seed_blocks_improved=4,
    same_batch_duration_MAE_seconds=dict(previous=62.482638888888886,current=61.954282407407405),true_effective_task_duration_values_preserved=True,
    all_records_retained=True,physical_changes_not_erased=True,raw_power_structure_energy_eta_preserved=True,
    public_native_outputs=24,public_rejected_sample_checks=4,all_final_feature_vectors_exact=2808,features=426,
    independent_scalar_checks=sum(v['checks'] for v in a['independent_audit'].values()),all_predefined_gates_passed=True,
    selected_configuration=read('selected.json')['config'],old_math_models_default_preserved=True,previous_scientific_results_preserved=True,
    changed_preexisting_files=changed,new_production_files=read('release_build.json')['files'],
    remaining_limitations=['444 false effective tasks remain.','Physical no-action/anomaly false alarms not improved by this scope.','Scores are not calibrated probabilities or5percent error guarantees.','Controlled simulations, no field accuracy claim.'],
    recent_primary_papers_checked=['arxiv2607.03590,2026NPlinear classification','NeurIPS2025 Conformal Risk Training'],paper_methods_implemented=False,paper_guarantees_not_claimed=True,
    no_current_test_tuning=True,no_reference_forecast_report_or_second_block_changes=True,no_new_library_GPU_deletion_or_external_submission=True,
    result_sha256={p:sha(HERE/p) for p in paths}))
print('Effective verification released: accuracy',round(independent['retained']['accuracy']*100,2),'to',round(independent['candidate']['accuracy']*100,2),'percent; no added misses.',flush=True)
