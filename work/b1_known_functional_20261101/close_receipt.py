"""Close the adopted known-reference extraction experiment without refitting."""
from common import *
from assess_confirmation import audit

assert read('confirmation_assessment.json')['adoption_gates_pass']
assert all(read('continuous_assessment.json')['checks'].values())
assert read('public_checks.json')['raw_energy_and_eta_identical']
frozen=read('freeze.json')['source_sha256'];changed=[]
allowed={'B1算法/b1_algorithm/process/api.py','B1算法/b1_algorithm/process/batch.py','B1算法/README.md'}
for path,expected in frozen.items():
    if sha(ROOT/path)!=expected:
        assert path in allowed,path
        assert sha(HERE/'production_before'/path)==expected,path
        changed.append(path)
for path,expected in read('release_build.json')['files'].items():assert sha(ROOT/path)==expected,path
rows,extra=audit('stress_continuous')
assert extra['inputs']==312
result_files=['confirmation_assessment.json','continuous_assessment.json','public_checks.json','freeze.json','selected.json','confirmation_plan.json','production_before.json','release_build.json']
for stage in ['test','stress_test','stress_continuous']:
    result_files += [stage+'/'+name for name in ['facts.json','curves.json','metrics.json']]
    for panel in ['minute','10s']:result_files += [stage+'/'+panel+'/'+name for name in ['truth.json','mixed_truth.json']]
receipt=dict(status='complete',adopted=True,entrypoint='analyze_event(s)(...,process_method="known_response_duration")',
    preserved_previous_entrypoint='duration_fusion',unchanged_global_default=True,
    known_reference_only=True,reference_forecasting_not_expanded=True,report_and_second_block_unchanged=True,
    final_inputs=3588,base_trajectories=1012,method_rows=14352,
    main_duration_MAE_seconds=dict(cpop=38.68229166666667,labs=86.76866319444444,retained=35.65234375,new=21.821180555555557),
    main_improvement_over_retained_percent=100*(1-21.821180555555557/35.65234375),
    main_zero_action_false_positives=dict(denominator=168,cpop=89,labs=46,retained=89,new=80),
    main_short_location_misses=dict(denominator=264,cpop=2,labs=160,retained=2,new=2),
    weak_stress_MAE_seconds=dict(cpop=196.25806677890012,labs=237.42108585858585,retained=185.12521043771045,new=152.74726430976432),
    weak_stress_short_location_misses=dict(denominator=121,cpop=82,labs=109,retained=86,new=86),
    remaining_problems=['Weak short response localization remains poor; no new misses but no fix.',
        'False positives improve modestly; fixed-spike and mixed-anomaly false alarms do not decrease.',
        'Ordinary Gaussian conditions essentially unchanged; most improvement is duration under anomalies.'],
    source_changes=changed,new_files=read('release_build.json')['files'],
    old_mathematics_and_weights_unchanged=True,all_frozen_work_sources_and_models_unchanged=True,
    independent_metric_checks=44928+33696+extra['checks'],continuous_metric_audit=extra,
    public_native_events=36,public_feature_vectors_exact=3588,raw_energy_identical=True,
    points_deleted_or_replaced=False,field_accuracy_validated=False,
    strict_validation_screen_passed=False,strict_validation_failure_retained=True,
    independent_confirmation_plan_written_before_final_draws=True,independent_confirmation_gates_passed=True,
    no_final_test_tuning=True,no_new_library_or_deletion_or_external_submission=True,
    observer_check_correction='Old internal complete replay initially received a serialized list, causing unavailable; corrected observer to pass native numpy vector. Frozen estimator/results unchanged.',
    result_sha256={p:sha(HERE/p) for p in result_files})
write('completion_receipt.json',receipt)
print('Adopted known-reference duration improvement; source and result checks complete',flush=True)
