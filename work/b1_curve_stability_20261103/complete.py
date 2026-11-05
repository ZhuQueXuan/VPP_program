"""Close the authorized diagnosis and single-candidate comparison."""
from pathlib import Path
import hashlib,json
from prepare import save,formal_hashes
HERE=Path(__file__).resolve().parent

if __name__=='__main__':
    verification=json.loads((HERE/'verification.json').read_text(encoding='utf-8'))
    assert verification['passed'] is True
    decision=json.loads((HERE/'decision.json').read_text(encoding='utf-8'))
    assert formal_hashes()==json.loads((HERE/'formal_before.json').read_text(encoding='utf-8'))
    old=HERE.parent/'b1_curve_spline_pilot_20261103'
    before=json.loads((HERE/'retained_before.json').read_text(encoding='utf-8'))
    assert all(hashlib.sha256((old/n).read_bytes()).hexdigest()==h for n,h in before.items())
    artifact={str(f.relative_to(HERE)):hashlib.sha256(f.read_bytes()).hexdigest()
        for f in HERE.rglob('*') if f.is_file() and '__pycache__' not in f.parts}
    save(HERE/'artifact_manifest.json',artifact)
    save(HERE/'completion_receipt.json',dict(
        status='completed_diagnosis_and_one_new_comparison_no_new_improvement',
        result=decision['status'],retained_version='unchanged previous lambda_mean1e-4 spline candidate',
        formal_default='unchanged original Kennedy DR local linear',
        confirmation_retained_rmse=decision['aggregate']['retained_S']['mean_curve_rmse'],
        confirmation_candidate_rmse=decision['aggregate']['adaptive_1']['mean_curve_rmse'],
        relative_gain=decision['comparisons']['retained_S']['relative_gain'],
        old_diagnosis_blocks=8,old_diagnosis_cohorts=48,old_cohorts_used_for_tuning=0,
        new_development_cohorts=24,new_confirmation_cohorts=96,new_confirmation_independent_blocks=12,
        all_confirmation_cohorts_included=True,verification_passed=True,
        full_cohort_pseudo_outcomes_shared_across_methods=True,
        all_old_retained_artifacts_unchanged=len(before),formal_source_model_files_unchanged=len(formal_hashes()),
        artifact_files_hashed=len(artifact),new_candidate_adopted=False,
        secondary_mathematical_bound='Truth-only combination ceiling is explanatory after evaluation, not a deployable estimator or a change to trial scores.',
        physical_or_field_validation=False,first_part_changed=False,other_parts_changed=False,
        new_dependencies=False,cmd_or_one_click_files=False,deletions=False,commits_or_external_publication=False,
        consumed_confirmation_rule='No parameter updates, replacement draws or repeated confirmation; next hypothesis requires fresh development and evaluation.'))
    print(json.dumps(dict(status='completed',new_candidate_adopted=False,old_retained_artifacts_unchanged=len(before),
        formal_files_unchanged=len(formal_hashes()),artifact_files_hashed=len(artifact))))
