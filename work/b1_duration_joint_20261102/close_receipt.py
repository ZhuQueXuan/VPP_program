from common import *

a=read('assessment.json');public=read('public_checks.json')
assert a['adopted'] and all(a['checks'].values()) and public['all_passed']
allowed={'B1算法/b1_algorithm/process/api.py','B1算法/b1_algorithm/process/batch.py','B1算法/README.md'};changed=[]
for path,expected in read('freeze.json')['source_sha256'].items():
    if sha(ROOT/path)!=expected:
        assert path in allowed,path
        assert sha(HERE/'production_before'/path)==expected,path
        changed.append(path)
for path,expected in read('release_build.json')['files'].items():assert sha(ROOT/path)==expected,path
old=ROOT/'work/b1_local_rescue_v2_20261102'
for path,expected in read(old/'completion_receipt.json')['result_sha256'].items():assert sha(old/path)==expected,path
rows=read('main_test/metrics.json')+read('weak_test/metrics.json');independent={}
for method in ['cpop','labs','retained','candidate']:
    rr=[r for r in rows if r['method']==method];parts=[]
    for panel in sorted({r['panel'] for r in rr}):
        conds=[]
        for condition in sorted({r['condition'] for r in rr if r['panel']==panel}):
            subset=[r for r in rr if r['panel']==panel and r['condition']==condition]
            conds.append(sum((abs(r['predicted_cumulative_seconds']-r['true_cumulative_seconds'])+abs(r['predicted_longest_seconds']-r['true_longest_seconds']))/2 for r in subset)/len(subset))
        parts.append(sum(conds)/len(conds))
    independent[method]=sum(parts)/len(parts)
    assert abs(independent[method]-a['summary']['pooled']['all'][method]['primary_seconds'])<1e-8
baseline={r['task_id']:r for r in rows if r['method']=='retained'}
assert all(all(r[k]==baseline[r['task_id']][k] for k in ['positive_prediction','null_false_positive','whole_miss','localized_miss','short_local_miss','genuine_short_miss']) for r in rows if r['method']=='candidate')
paths=['assessment.json','public_checks.json','selected.json','freeze.json','protocol.json','training_receipt.json','production_before.json','release_build.json','README.md']
for stage in ['main_test','weak_test']:
    paths += [stage+'/'+name for name in ['facts.json','curves.json','metrics.json','assessment.json','current_baseline.json','joint_X.npy']]
    for panel in ['minute','10s']:paths += [stage+'/'+panel+'/'+name for name in ['truth.json','mixed_truth.json']]
before=independent['retained'];after=independent['candidate']
write('completion_receipt.json',dict(status='complete',adopted=True,entrypoint='analyze_event(s)(...,process_method="gap_duration_refined")',
    prior_version_preserved='known_local_response',global_default_unchanged=True,known_reference_only=True,
    final_inputs=2808,base_trajectories=792,four_method_outputs=11232,
    primary_duration_MAE_seconds=independent,improvement_percent=100*(1-after/before),
    independently_recomputed_weighted_score=True,all_predefined_gates_passed=True,
    false_positives=dict(before=499,after=499),whole_misses=dict(before=39,after=39),localized_misses=dict(before=101,after=101),genuine_short_misses=dict(inputs=308,before=71,after=71),
    decisions_identical_per_record=True,localized_masks_preserved=True,raw_energy_eta_preserved=True,
    main_duration_seconds=dict(before=23.997395833333336,after=20.836805555555557),weak_duration_seconds=dict(before=95.3107638888889,after=73.34244791666666),
    long_positive_duration_seconds=dict(before=93.3547665641599,after=72.38794147796105),
    selected_configuration=read('selected.json')['config'],selected_targets='Absolute cumulative and absolute longest durations; fraction alternative not selected.',
    training_known_tasks=read('training_receipt.json')['known_tasks'],training_eligible_tasks=read('training_receipt.json')['eligible_tasks'],features=426,
    native_public_outputs=24,all_heldout_feature_vectors_exact=2808,scalar_score_checks=sum(v['scalar_checks'] for v in a['independent_checks'].values()),
    changed_preexisting_files=changed,new_production_files=read('release_build.json')['files'],
    previous_scientific_results_unchanged=True,old_numeric_models_and_default_unchanged=True,
    no_points_deleted_or_replaced=True,no_test_tuning=True,no_reference_forecast_or_report_or_second_block_changes=True,
    remaining_limitations=['Existing detection errors remain.','Durations are direct features, not a newly localized physical power curve.','Minor short finebin duration regression retained; overall short safety gates pass.','Controlled simulation results; no field accuracy claim.'],
    no_new_library_or_GPU_or_deletion_or_external_submission=True,result_sha256={p:sha(HERE/p) for p in paths}))
diagnosis=ROOT/'work/b1_duration_diagnosis_20261102'
for path,expected in read(diagnosis/'protected_sha256.json').items():
    if sha(ROOT/path)!=expected:assert path in allowed,path
with (diagnosis/'completion_receipt.json').open('x',encoding='utf-8') as f:
    json.dump(dict(status='complete',analysis_before_implementation=True,original_diagnosis_files_preserved=True,subsequent_implementation='work/b1_duration_joint_20261102',no_original_sampling_changed=True),f,indent=2)
print('Adopted gap-aware duration refinement:',round(before,2),'to',round(after,2),'seconds; decisions unchanged.',flush=True)
