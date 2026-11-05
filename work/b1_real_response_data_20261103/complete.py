"""Record completion of public real-data acquisition/recovery and preparation."""
from pathlib import Path
import csv,json,hashlib
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]

def save(name,value):
    with (HERE/name).open('x',encoding='utf-8') as f:json.dump(value,f,ensure_ascii=False,indent=2,allow_nan=False)

if __name__=='__main__':
    v=json.loads((HERE/'verification.json').read_text(encoding='utf-8'));assert v['passed'] is True
    for snapshot in ('formal_before.json','source_before.json'):
        files=json.loads((HERE/snapshot).read_text(encoding='utf-8'))
        assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in files.items())
    original=ROOT/'data/public_datasets/挪威_iFlex_动态电价试验/iFlex_dataset.RData'
    assert hashlib.md5(original.read_bytes()).hexdigest()=='7547c0931b0cda997609d9e7df70fdd2'
    manifest={str(p.relative_to(HERE)):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in HERE.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    save('artifact_manifest.json',manifest)
    receipt=dict(status='completed_public_real_data_design_audit_and_preparation',
        user_preference='Prefer real data; user confirms no own field offer/task/measurement records currently',
        prior_part3_comparisons_were_simulated=True,new_simulated_samples=0,
        source='https://zenodo.org/records/8248802',license='CC-BY-4.0',
        existing_official_RData_full_recovered=True,full_hourly_rows=13515600,
        full_phase2_hourly_rows=12180000,full_phase2_metered_household_ids=4375,
        prepared_households=718,prepared_household_day_events=14213,assigned_group_days=59,assigned_dates=30,
        chronological_split_household_day_events=dict(train=9581,validation=2213,test=2419),
        actual_consumption=True,actual_ex_ante_reward_price_paths=True,
        actual_price_levels=[2,5,10,15],pure_continuous_scalar_causal_design=False,
        target='household source Hour17/18 2h kWh and24h source-day kWh, auxiliary to EV duration research',
        no_EV_duration_or_individual_counterfactual_truth_fabricated=True,
        train_val_test_date_selection_frozen_before_outcome_extraction=True,
        new_model_fitted=False,new_accuracy_or_improvement_result=False,
        independent_preparation_verification_passed=True,
        encoding_repair='Only Region relinked to official UTF8 metadata; native-R outputs preserved; all other values unchanged.',
        formal_source_model_files_unchanged=61,original_source_files_unchanged=11,retained_old_artifacts_unchanged=376,
        first_part_or_other_algorithms_changed=False,ACN_consumed_test_or_external_raw_opened=False,
        new_dependencies_installed=False,large_raw_CSV_downloaded=False,cmd_or_one_click_files=False,
        deletions=False,commits_or_external_publication=False,artifact_files_hashed=len(manifest),
        next_stage='Real observed-price auxiliary validation with real-consumption metrics; do not force four paths into the original continuous-density estimator or label household kWh as EV duration.')
    save('completion_receipt.json',receipt)
    print(json.dumps(dict(status=receipt['status'],prepared_households=718,real_household_day_events=14213,
        model_fitted=False,verification_passed=True,artifact_files_hashed=len(manifest))))
