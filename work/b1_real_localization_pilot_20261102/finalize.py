from pathlib import Path
import json,hashlib,datetime
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
v=read(HERE/'verification.json');a=read(HERE/'assessment.json');freeze=read(HERE/'selection_freeze.json')
assert v['status']=='passed' and not a['production_adopt']
assert not a['validation_detection_noninferiority'] and not a['validation_joint_boundary_better']
for name,value in freeze['source_sha256'].items():assert sha(HERE/name)==value,name
files=[p for p in HERE.rglob('*') if p.is_file() and p.name!='completion_receipt.json']+[ROOT/'data/ACN_real_user_benchmark_v1_20261102/EXPERIMENT_STATUS.md']
receipt=dict(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),status='completed_real_localization_development_pilot;candidate_rejected',inputs=128,training_inputs=96,validation_inputs=32,validation_resolved_anchor_targets=18,validation_onset_targets=11,validation_recovery_targets=7,native_input_supported=127,native_original_curves=254,selected_raw_evidence_k=3,supervised_models_trained=0,training_threshold_configurations=3,formal_production_models_unchanged=True,current_production_method='effective_response_refined',candidate_adopt=False,candidate_additional_validation_false_positive=1,candidate_additional_validation_false_negative=0,candidate_validation_boundary_gain=False,verified_origin_of_one_recovery_error='Fixed return criterion also fails on original observations; no evidence of CPOP segmentation failure in that case.',physical_gold_or_new_certified_real_accuracy=False,test_observation_values_read=False,independent_semantic_review_pending=True,validation_retuned=False,verification_passed=True,no_raw_point_deletion_gap_fill_or_annotation_change=True,no_new_dependencies_GPU_deletion_commit_upload=True,no_reference_prediction_report_or_second_block=True,artifact_sha256={str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in files})
(HERE/'completion_receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(status=receipt['status'],files=len(files),native_curves=254,validation_targets=18,new_FP=1,new_FN=0,adopt=False,test_read=False)),flush=True)
