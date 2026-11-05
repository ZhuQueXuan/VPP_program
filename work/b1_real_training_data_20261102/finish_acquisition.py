from pathlib import Path
import json,hashlib
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];DEST=ROOT/'data/ACN_real_user_benchmark_v1_20261102'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
v=read(DEST/'verification.json');assert v['raw_files']==1878 and v['users']==195 and v['cross_user_split_leaks']==0 and v['trained_models']==0
expected={'dortmund_parameters.csv':'55a479a1a34114a81da6bbc233cda419','dortmund_measurements.csv':'332378d8e25b2edf808f3f05a610fdc1'}
for name,h in expected.items():assert hashlib.md5((HERE/'source_documents'/name).read_bytes()).hexdigest()==h,name
source_hashes={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in (HERE/'source_documents').iterdir() if p.is_file() and p.suffix in ['.json','.csv','.md']}
files=['README.md','split_protocol.json','split_freeze.json','session_manifest.json','training_sessions.json','validation_sessions.json','test_sessions.json','external_test_sessions.json','download_manifest.json','development_profile.json','response_annotation_candidates.json','labeling_protocol.json','verification.json']
state=dict(status='real_corpus_acquired_split_and_checked;response_labels_pending',date='2026-11-02',
    canonical_dataset=DEST.relative_to(ROOT).as_posix(),real_sessions=1878,anonymous_users=195,
    users_by_split=v['users_by_split'],sessions_by_split=v['sessions_by_split'],same_user_never_crosses_partition=True,
    physical_vehicle_identity_certified=False,previously_observed_users_excluded_from_blind=True,test_and_external_response_values_not_inspected=True,
    response_labels=0,clean_power_labels=0,new_models_trained=0,no_real_accuracy_claim=True,
    raw_originals_verified_to_git_snapshot=True,raw_points_not_deleted_or_filled=True,all_source_files_retained=True,
    development_annotation_candidate_sessions=906+205,unreviewed_command_candidates=v['command_candidates'],command_candidate_not_response_truth=True,
    original_production_files_preserved=58,reference_prediction_report_second_block_unchanged=True,
    no_new_dependency_GPU_deletion_commit_or_data_upload=True,
    raw_corpus_bytes=v['raw_bytes'],prior_station_only_split_retired_as_screening=True,
    next_step='Independent observed-response labeling and coverage review, then train/choose only on development; one final locked evaluation, not every iteration.',
    artifact_sha256={name:hashlib.sha256((DEST/name).read_bytes()).hexdigest() for name in files},public_source_documents_sha256=source_hashes)
(DEST/'dataset_receipt.json').write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
(HERE/'completion_receipt.json').write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
print('Real data acquired and user-group split frozen;1878sessions/195users;labels pending;no model fitted',flush=True)
