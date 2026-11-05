"""Record the completed research branch without modifying frozen results."""
from pathlib import Path
import datetime, hashlib, json

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
read = lambda p: json.loads(p.read_text(encoding='utf-8'))
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
verification = read(HERE/'verification.json')
assert verification['status'] == 'passed'
assert verification['checks']['production_files_unchanged'] == 58
assert verification['checks']['confirmation_original_native_input_and_output_cases'] == 64
files = sorted(p for p in HERE.rglob('*') if p.is_file() and p.name != 'completion_receipt.json')
status = ROOT/'data/ACN_real_user_benchmark_v1_20261102/REAL_ADAPTATION_STATUS.md'
files.append(status)
receipt = dict(
    created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    status='completed_real_observation_research_adaptation_with_preliminary_gain',
    retained_production_method='effective_response_refined',
    research_entry='work/b1_retained_real_adapter_20261102/state_v2/adapter.py:infer',
    keep_research_branch=True, production_adopt=False,
    preserved_production_files=58, preserved_prior_artifacts=177,
    old_physical_weights_changed=False,
    shared_numeric_features='exact retained DF block and50-column local representation',
    new_models='standard real-trained logistic event verifier and2-feature conditional recovery verifier',
    supervision='provisional single-assistant raw observation review; independent review pending',
    train_windows=96, event_training_labels=62,
    recovery_training_rows=235, reachable_positive_endpoints=21,
    total_training_recovery_targets_scored=22,
    seen_validation_windows=32, additional_validation_windows=32,
    additional_validation_users=22, new_validation_users=0,
    confirmation_model_frozen_before_window_selection=True,
    confirmation_labels_frozen_before_new_model_outputs=True,
    confirmation_retrained_or_retuned=False,
    prospective_recovery_comparison=dict(
        n=8, missing_penalty_seconds=180,
        capped_interval_mae_seconds=dict(cpop=31.875, adapted=22.875, labs=93.125),
        interval_reduction=1-22.875/31.875,
        endpoint_mae_seconds=dict(cpop=31.875, adapted=23.375),
        endpoint_reduction=1-23.375/31.875,
        missing=dict(cpop=1, adapted=1, labs=4),
        anchor_resolved_labels=22, cpop_false_positive=0, adapted_false_positive=0,
        cpop_false_negative=0, adapted_false_negative=0,
        primary_gain_case=129, new_early_return_case=133, still_missing_case=147),
    supported_target='observed local change, onset, recovery-completion and observed onset-to-return span',
    physical_effective_qualification_and_C_L='unsupported/null in new branch; unchanged old production retained',
    actual_data_changes='add32 validation-role nonoverlapping raw windows and provisional labels; original bytes unchanged',
    final_test_observation_values_read=False, external_test_observation_values_read=False,
    forecast_changed=False, report_changed=False, second_block_changed=False,
    dependencies_installed=False, points_deleted=False, gaps_filled=False,
    files_deleted=False, gpu_used=False, committed_or_uploaded=False,
    verification=verification,
    artifact_sha256={p.relative_to(ROOT).as_posix():sha(p) for p in files})
with (HERE/'completion_receipt.json').open('x',encoding='utf-8') as stream:
    json.dump(receipt,stream,ensure_ascii=False,indent=2,allow_nan=False)
print(json.dumps(dict(status=receipt['status'],artifacts=len(files),production_adopt=False)))
