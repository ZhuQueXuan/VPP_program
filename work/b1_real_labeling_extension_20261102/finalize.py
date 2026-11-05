from pathlib import Path
import json,hashlib,datetime
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];DATA=ROOT/'data/ACN_real_user_benchmark_v1_20261102';OUT=DATA/'annotations/batch_20261102_b';VIEW=DATA/'prepared/observed_localization_pilot_v1_20261102'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
verification=read(HERE/'verification.json');combined=read(HERE/'combined_summary.json')
assert verification['status']=='passed' and verification['new_models_fit']==0
assert verification['checks']['prepared_development_rows_preserve_inputs_labels_and_roles']==128
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
freeze=dict(created_utc=now,status='second_single_assistant_first_pass_frozen;independent_review_pending',file_sha256={p.name:sha(p) for p in sorted(OUT.iterdir()) if p.is_file() and p.name!='annotation_freeze.json'},not_physical_gold=True,selection_freeze_sha256=sha(HERE/'selection_freeze.json'))
(OUT/'annotation_freeze.json').write_text(json.dumps(freeze,ensure_ascii=False,indent=2),encoding='utf-8')
files=[p for p in HERE.rglob('*') if p.is_file() and p.name!='completion_receipt.json']+[DATA/'ANNOTATION_STATUS.md']+[p for p in OUT.iterdir() if p.is_file()]+[p for p in VIEW.iterdir() if p.is_file()]
receipt=dict(created_utc=now,status='completed_real_development_annotation_expansion_and_provisional_training_inputs',new_windows=64,combined=combined,verification_passed=True,independent_review_pending=True,models_fit=0,new_real_accuracy=None,production_changed=False,test_observation_values_read=False,original_points_unchanged=True,original_CPOP_LABS_and_beneficial_version_preserved=True,no_reference_prediction_report_or_second_block=True,no_install_GPU_deletion_upload_or_commit=True,artifact_sha256={str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in files})
(HERE/'completion_receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(status=receipt['status'],files=len(files),windows=128,users=118,production_files_unchanged=verification['checks']['production_files_unchanged'],test_read=False,models_fit=0)),flush=True)
