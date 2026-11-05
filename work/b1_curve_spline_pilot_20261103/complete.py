"""Record verified research completion without changing the fitted algorithms."""
from pathlib import Path
import hashlib,json
from prepare import hashes,save
HERE=Path(__file__).resolve().parent

if __name__=='__main__':
    v=json.loads((HERE/'verification.json').read_text(encoding='utf-8'))
    api=json.loads((HERE/'candidate_api_verification.json').read_text(encoding='utf-8'))
    decision=json.loads((HERE/'decision.json').read_text(encoding='utf-8'))
    assert v['passed'] and api['status']=='passed'
    assert hashes()==json.loads((HERE/'formal_before.json').read_text(encoding='utf-8'))
    files={str(p.relative_to(HERE)):hashlib.sha256(p.read_bytes()).hexdigest()
           for p in HERE.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    save(HERE/'artifact_manifest.json',files)
    receipt=dict(status='complete_for_authorized_factor_audit_and_single_curve_comparison',
        results=decision['status'],main_candidate='shared Kennedy DR pseudo-outcomes + global cubic smoothing spline',
        current_default='unchanged Kennedy DR local linear',
        mean_curve_rmse_seconds={k:r['mean_curve_rmse'] for k,r in decision['aggregate'].items()},
        independent_confirmation_seed_blocks=8,confirmation_curves=48,all_confirmation_curves_included=True,
        new_data_are_simulated=True,field_or_independent_physical_validation=False,
        second_part_scope='audit and common prospective factor definition only; no graph learner changed',
        third_part_scope='implemented, compared, saved and independently checked reusable research candidate',
        other_parts_changed=False,first_part_kept_frozen=True,
        verification_passed=True,candidate_api_verification_passed=True,
        formal_source_and_model_files_unchanged=len(hashes()),artifact_files_hashed=len(files),
        protocol_execution_clarification='inference_band_fitting=False means no new candidate inference procedure: the unchanged formal baseline API still computes its existing conditional band during the shared fit. Those baseline bands were not reused for the spline.',
        installations=False,cmd_or_one_click_files_created=False,deletions=False,commits_or_external_publication=False,
        future_rule='This confirmation is consumed; no further lambda selection, replacement draws or repeat confirmation on it.')
    save(HERE/'completion_receipt.json',receipt)
    print(json.dumps(dict(status=receipt['status'],verification_passed=True,
        formal_files_unchanged=len(hashes()),artifact_files_hashed=len(files)),ensure_ascii=False))
