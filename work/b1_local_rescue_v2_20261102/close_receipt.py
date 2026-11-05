from common import *

assessment=read('assessment.json');public=read('public_checks.json')
assert assessment['adopted'] and all(assessment['checks'].values())
assert public['all_passed'] and public['rescued_records_verified']==8
allowed={'B1算法/b1_algorithm/process/api.py','B1算法/b1_algorithm/process/batch.py','B1算法/README.md'}
changed=[]
for p,h in read('freeze.json')['source_sha256'].items():
    if sha(ROOT/p)!=h:
        assert p in allowed,p
        assert sha(HERE/'production_before'/p)==h,p
        changed.append(p)
for p,h in read('release_build.json')['files'].items():assert sha(ROOT/p)==h,p
rows=read('weak_test/metrics.json');new=[r for r in rows if r['method']=='candidate' and r['new_bins']>0]
assert sum(r['new_bins'] for r in new)==sum(r['new_true_bins'] for r in new)==8
files=['assessment.json','public_checks.json','selected.json','confirmation_plan.json','freeze.json','production_before.json','release_build.json','README.md']
for stage in ['main_test','weak_test']:
    files += [stage+'/'+f for f in ['facts.json','curves.json','metrics.json','assessment.json','state_X.npy']]
    for panel in ['minute','10s']:files += [stage+'/'+panel+'/'+f for f in ['truth.json','mixed_truth.json']]
write('completion_receipt.json',dict(status='complete',adopted=True,entrypoint='analyze_event(s)(...,process_method="known_local_response")',
    previous_version_preserved='known_response_duration',global_default_unchanged=True,
    final_inputs=2808,base_trajectories=792,four_method_outputs=11232,
    weak_genuine_short_records=165,weak_genuine_short_misses=dict(cpop=66,labs=116,previous=67,current=59),
    weak_short_miss_reduction_percent=100*8/67,
    weak_short_duration_MAE_seconds=dict(previous=15.375,current=13.270833333333334),
    weak_false_effective_tasks=dict(negative_inputs=774,previous=482,current=482),
    weak_physically_no_action_false_tasks=dict(inputs=168,previous=76,current=76),
    main_false_tasks=dict(previous=40,current=40),main_true_short_misses=dict(inputs=132,previous=0,current=0),
    main_duration_MAE_seconds=dict(previous=25.48090277777778,current=25.48090277777778),
    recovered_records=8,recovered_base_trajectories=len({r['base_task_id'] for r in new}),recovered_seed_blocks=len({r['seed'] for r in new}),
    newly_positive_bins=8,newly_false_positive_bins=0,
    remaining_short_misses=59,remaining_problem='Limited independent rescue only for previously zero tasks; existing wrong-position and long oscillatory problems remain.',
    public_native_event_outputs=24,all_heldout_raw_feature_vectors_exact=2808,
    source_changes=changed,new_production_files=read('release_build.json')['files'],
    old_mathematics_models_and_default_preserved=True,raw_eta_and_energy_preserved=True,points_deleted_or_replaced=False,
    original_CPOP_and_LABS_controls_preserved=True,reference_prediction_report_second_block_changed=False,
    previous_failed_version_preserved='work/b1_local_rescue_20261101/completion_receipt.json',
    strict_development10percent_screen_passed=False,independent_confirmation_gates_passed=True,
    final_population='Fresh continuous uniform stratified weak amplitudes; do not combine earlier failed fixed-grid scores as a single sequence.',
    no_tuning_on_current_final=True,no_field_accuracy_claim=True,no_new_library_deletion_or_external_submission=True,
    overall_weak_duration_improvement_significance_claim=False,
    result_sha256={p:sha(HERE/p) for p in files}))
print('Release complete:8 weak-short records recovered; no new false positives; prior version intact.',flush=True)
