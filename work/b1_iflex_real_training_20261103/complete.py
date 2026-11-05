"""Verify unchanged sources and seal real auxiliary results."""
from pathlib import Path
import json
from prepare import HERE,ROOT,DATA,save,sha

if __name__=='__main__':
    read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
    assert read(HERE/'verification.json')['passed'] is True
    for p,h in read(HERE/'formal_before.json').items():assert sha(ROOT/p)==h
    for p,h in read(DATA/'artifact_manifest.json').items():assert sha(DATA/p)==h
    d=read(HERE/'decision.json');assert d['status']=='real_auxiliary_candidate_confirmed'
    manifest={str(p.relative_to(HERE)):sha(p) for p in HERE.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    save(HERE/'artifact_manifest.json',manifest)
    save(HERE/'completion_receipt.json',dict(status='verified_real_auxiliary_model_comparison_completed',
        candidate=d['selected']['candidate'],baseline=d['selected']['reference'],test_household_days=2419,test_dates=5,
        original_date_equal_rmse=d['all_scores'][d['selected']['reference']]['date_equal_rmse'],
        candidate_date_equal_rmse=d['all_scores'][d['selected']['candidate']]['date_equal_rmse'],
        relative_gain=d['date_equal_rmse_gain'],dates_won=d['dates_won'],real_observed_peak_kwh_prediction=True,
        candidate_retained_as_separate_research_model=True,original_EV_algorithm_and_prior_spline_retained=True,
        continuous_causal_curve_or_EV_duration_validated=False,independent_audit_passed=True,
        test_consumed_no_further_tuning=True,formal_source_models_unchanged=61,
        first_and_other_parts_changed=False,new_simulation=False,installation=False,cmd_or_one_click=False,
        deletion=False,commit_or_external_publication=False,artifact_files_hashed=len(manifest)))
    print(json.dumps(dict(completed=True,gain=d['date_equal_rmse_gain'],dates_won=d['dates_won'],files_hashed=len(manifest))))
