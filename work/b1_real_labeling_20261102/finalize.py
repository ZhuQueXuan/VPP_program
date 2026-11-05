from pathlib import Path
import json,hashlib,datetime
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
DATA=ROOT/'data/ACN_real_user_benchmark_v1_20261102';OUT=DATA/'annotations/batch_20261102'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
verification=read(HERE/'verification.json');summary=read(OUT/'batch_summary.json')
assert verification['status']=='passed'
assert summary['models_fit']==summary['independent_gold_labels']==0
assert not verification['sealed_test_observation_values_parsed']
(OUT/'review_rubric.json').write_text((HERE/'review_rubric.json').read_text(encoding='utf-8'),encoding='utf-8')
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
freeze=dict(created_utc=now,status='single_assistant_first_pass_frozen;independent_review_pending',file_sha256={p.name:sha(p) for p in sorted(OUT.iterdir()) if p.is_file() and p.name!='annotation_freeze.json'},not_a_gold_label_freeze=True,selection_freeze_sha256=sha(HERE/'selection_freeze.json'))
(OUT/'annotation_freeze.json').write_text(json.dumps(freeze,ensure_ascii=False,indent=2),encoding='utf-8')
files=[p for p in HERE.rglob('*') if p.is_file() and p.name!='completion_receipt.json']+[DATA/'ANNOTATION_STATUS.md']+[p for p in OUT.iterdir() if p.is_file()]
receipt=dict(created_utc=now,status='completed_initial_real_development_label_review;independent_review_pending',dataset='data/ACN_real_user_benchmark_v1_20261102',annotation_directory=str(OUT.relative_to(ROOT)).replace('\\','/'),summary=summary,verification_status=verification['status'],models_trained=0,production_algorithm_changed=False,test_or_external_observation_values_inspected=False,independent_physical_gold_established=False,label_studio_import_tested=False,no_new_accuracy_or_improvement_claim=True,original_CPOP_LABS_and_beneficial_version_preserved=True,no_new_dependency_GPU_deletion_upload_or_commit=True,reference_prediction_report_second_block_unchanged=True,artifact_sha256={str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in files})
(HERE/'completion_receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(status=receipt['status'],artifact_files=len(files),windows=summary['windows'],production_files_unchanged=verification['checks']['unchanged_production_files'],test_values_read=False,models_fit=0)),flush=True)
