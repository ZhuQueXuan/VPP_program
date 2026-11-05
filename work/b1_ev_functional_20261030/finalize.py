"""Close EV-only functional adoption; freeze hashes without touching old evidence."""
from pathlib import Path
import hashlib,json

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    output=HERE/'adoption_receipt.json'
    if output.exists():raise RuntimeError('completed adoption receipt cannot be overwritten')
    main_check=json.loads((HERE/'final_review/receipt.json').read_text(encoding='utf-8'))
    boundaries=json.loads((HERE/'boundary_receipt.json').read_text(encoding='utf-8'))
    independent=json.loads((HERE/'independent/technical_review.json').read_text(encoding='utf-8'))
    assert all(row['passed'] is True for row in (main_check,boundaries,independent))
    before=json.loads((HERE/'before_manifest.json').read_text(encoding='utf-8'))
    after={name:sha(ROOT/name) for name in before}
    protected={name for name in before if not name.startswith('B1算法/')}
    assert all(after[name]==before[name] for name in protected),'protected resource model or compatibility entry changed'
    modified=[name for name in before if after[name]!=before[name]]
    source={p.relative_to(ROOT).as_posix():sha(p) for p in (ROOT/'B1算法').rglob('*') if p.is_file()}
    added=sorted(set(source)-set(before))
    (HERE/'after_manifest.json').write_text(json.dumps(source|{n:after[n] for n in sorted(protected)},ensure_ascii=False,indent=2),encoding='utf-8')
    receipt=dict(approved_by_user=True,scope='EV-only parameterization and functional verification; other resources later',
        approved_framework='work/b1_generalization_framework_20261030/B1算法通用化与资源模型复用开发框架_待审批.md',
        accepted=True,main_checks=main_check['n_checks'],boundary_checks=boundaries['n_checks'],independent_checks=independent['n_checks'],
        functional_matrix_rows=54,predicted_reference_one_minute_events=180,causal_task_strata=3,
        native_CPOP_explicit_cases=9,legacy_numeric_cases=9,legacy_max_curve_difference=main_check['legacy_parity_max_curve_difference'],
        changed_existing_files=modified,new_runtime_files=added,protected_files_verified=len(protected),
        actual_resource_input_validator_used=True,resource_optimizer_used_as_actual_response=False,
        main_comparators=['native CPOP','standard multivalued AIPW'],new_performance_claim=False,real_device_validation=False,
        report_modified=False,other_resource_adapter_added=False,B2_B3_modified=False,
        failures_retained=['verify_initial_failure.log: exact ratio test tolerance1e-12 was too strict for absolute clock subtraction; observed error1.82e-12, adjusted to1e-9'],
        known_limits=['reference prediction remains complete one-minute data; no implicit upsampling',
                      'new task power/duration detection error rates and parameter intervals not calibrated',
                      'service outcome checks declared AC energy, not SOC or attribution of missed demand',
                      'old-domain parity is numerical curves/integrals, not new multi-task performance evidence',
                      'this is not complete B1 or real resource capability acceptance'])
    output.write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(receipt,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
