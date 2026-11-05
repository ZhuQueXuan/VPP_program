"""Freeze current source and EV-only continuous-function acceptance."""
from pathlib import Path
import ast,hashlib,json

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    target=HERE/'adoption_receipt.json'
    if target.exists():raise RuntimeError('completed adoption cannot be overwritten')
    before=json.loads((HERE/'before_manifest.json').read_text(encoding='utf-8'))
    protected={n:v for n,v in before.items() if not n.startswith('B1算法/')}
    assert all(sha(ROOT/n)==v for n,v in protected.items()),'protected resource model or old compatibility entry changed'
    functional=json.loads((HERE/'verification.json').read_text(encoding='utf-8'))
    independent=json.loads((HERE/'technical_review/independent_receipt.json').read_text(encoding='utf-8'))
    compatibility=json.loads((HERE/'compatibility_receipt.json').read_text(encoding='utf-8'))
    study=json.loads((HERE/'study_receipt.json').read_text(encoding='utf-8'))
    assert functional['passed'] and independent['passed'] and compatibility['passed'] and study['completed']
    for row in study['summary']:assert row['successful_curves']==(0 if row['scenario']=='deterministic_no_support' else 12)
    for name,expected in independent['reviewed_sha256'].items():
        if not name.endswith('/plotting.py'):assert sha(ROOT/name)==expected,'estimation changed after independent review'
    for p in (ROOT/'B1算法').rglob('*.py'):ast.parse(p.read_text(encoding='utf-8-sig'),filename=str(p))
    current={p.relative_to(ROOT).as_posix():sha(p) for p in (ROOT/'B1算法').rglob('*') if p.is_file()}
    after=current|{name:sha(ROOT/name) for name in protected}
    (HERE/'after_manifest.json').write_text(json.dumps(after,ensure_ascii=False,indent=2),encoding='utf-8')
    result=dict(accepted=True,user_requested='continuous incentive amounts and directly evaluated curved effects at one common task; no forced straight line',
        main_function_checks=functional['n_checks'],independent_checks=independent['n_checks'],compatibility_checks=compatibility['checks'],
        repetitions=12,scenarios=5,factual_variants=144000,independent_unit='12 seed blocks; paired mechanism variants are not independent studies',
        runtime_new_files=sorted(set(current)-set(before)),changed_existing_files=[name for name in before if after.get(name)!=before[name]],
        protected_files=len(protected),protected_files_unchanged=True,old_discrete_scores_equal=True,
        free_task_duration=True,reference_forecast_time_domain_expanded=False,raw_energy_definition_unchanged=True,
        mature_method='Kennedy continuous DR pseudo-outcome plus local-linear smoothing; RIDE continuous architecture reused',
        arbitrary_queries_tested=[.73,.85,1.17],observed_doses_binned=False,forced_linear=False,forced_monotone=False,
        figure_outputs_visually_checked=4,post_review_fix='generic ratio y-axis labeling only; 8-case compatibility receipt',
        full_unsmoothed_curve_confidence_coverage_verified=False,real_EV_validation=False,new_estimator_superiority_claim=False,
        report_modified=False,other_resource_added=False,B2_B3_changed=False,zip_or_doubleclick_launcher_created=False,
        retained_limits=['pure continuous design only; zero atom mixtures explicitly unsupported',
                         'estimated conditional density assumes a logit-normal model; known design accepts uniform randomized only',
                         'support diagnostics are not proof of causal identification',
                         'sampling band excludes smoothing, nuisance and reference/process uncertainty',
                         'existing reference forecast stays within task-relative[-120,+90]minutes',
                         'current batch limit12000 events and30 pre-treatment covariates'])
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ('changed_existing_files','retained_limits')},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
