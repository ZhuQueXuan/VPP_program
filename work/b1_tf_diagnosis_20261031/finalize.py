"""Read-only synthesis checks and manifest; no estimator or optimizer imports."""
from pathlib import Path
import hashlib,json,re
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
def read(name): return json.loads((HERE/name).read_text(encoding='utf-8'))
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
checks=0
def check(condition):
    global checks
    assert condition
    checks+=1

protection=read('protection_receipt.json')
check(protection['scientific_unchanged'])
check(protection['changed']==['AGENTS.md'])
hashed={}
for name in ['oracle_diagnosis.json','reference_error_analysis_receipt.json',
             'oracle_independent_check.json','factorial_diagnosis.json',
             'calibration_diagnosis.json']:
    d=read(name)
    for rel,digest in d['input_sha256'].items():
        check(sha(ROOT/rel)==digest)
        hashed[rel]=digest
oracle=read('oracle_diagnosis.json')
check(oracle['parameters_unchanged'] and oracle['source_freeze_unchanged'])
check(len(read('oracle_curves.json'))==1728)
check(len(read('oracle_metrics.json'))==1728)
def group(variant,condition,method):
    rows=[r for r in oracle['summary'] if (r['variant'],r['condition'],r['method'])==(variant,condition,method)]
    check(len(rows)==1)
    return rows[0]
for method,expected in [('tf_gls',[182.8125,63.75,1.875]),('cpop_meter',[148.125,45.9375,30.0])]:
    for condition,value in zip(['saved_reference_with_noise','true_reference_with_noise','true_reference_no_noise'],expected):
        r=group('weak',condition,method)
        check(r['n']==64 and r['duration_mae_seconds']==value)
for method,expected in [('tf_gls',[10,0,0]),('cpop_meter',[5,0,0])]:
    for condition,value in zip(['saved_reference_with_noise','true_reference_with_noise','true_reference_no_noise'],expected):
        check(group('null',condition,method)['false_positive_tasks']==value)
independent=read('oracle_independent_check.json')
check(independent['status']=='passed' and independent['curves_checked']==1728)
factorial=read('factorial_diagnosis.json')
check(factorial['fits']==1536 and factorial['n_base_tasks']==64)
check(not factorial['new_configuration_selected'] and not factorial['original_selection_changed'])
check(factorial['all_original_source_and_read_inputs_unchanged'])
identity=read('factorial_freeze_identity_check.json')
check(identity['passed'] and identity['max_curve_difference']==0)
theory=read('calibration_diagnosis.json')['theory']
check(theory['n_cal_users']==48 and theory['tail_order_r']==2)
check(theory['minimum_n_for_second_largest_threshold_PAC95_005']==93)
check(abs(theory['fixed_calibration_q_quantiles']['0.95']-.09505862462413558)<1e-13)
check(read('reference_error_analysis_receipt.json')['no_fit'])
check(read('reference_error_analysis_receipt.json')['no_parameter_selection'])
receipt={
    'status':'passed', 'date':'2026-10-31',
    'scope':'First-block diagnosis and evidence-based proposal only; report postponed',
    'original_full_scope':{'base_tasks':256,'users':128,'paired_variants':768},
    'controlled_scope':{'fixed_base_tasks':64,'users':32,'paired_variants':192,'selection':'First 8 users per original block, both events; not error-selected'},
    'new_process_solves':{'oracle_TF':768,'oracle_CP':384,'covariance_lambda_TF':1536},
    'oracle_rows':{'saved_baseline':576,'new_controlled':1152,'total':1728},
    'new_independent_facts':False, 'new_predictor_training':False,
    'new_hyperparameter_selection':False,'candidate_implemented':False,
    'production_code_or_default_changed':False,'original_results_changed':False,
    'calibration_permutations':'5000 diagnostic user-block permutations; not new samples or adopted calibration',
    'scientific_protection':protection,
    'audit_checks_not_performance_samples':{'root':checks,'reference':15511,'oracle_independent':39124,'calibration':5868},
    'verified_input_files':len(hashed),
    'diagnostic_conclusion':'Reference signed low-frequency error is an important upstream bottleneck; covariance weighting and score/calibration design also have independent limitations. No additive causal percentages or new method superiority claim.',
    'next_step':'Legal pre-notice non-event reference-error correction first; separate point-duration validation and length-aware task evidence, new matched user-block calibration; CPOP remains block-level comparator.',
    'limits':['Already-seen simulated pilot only','Oracle true reference is unavailable in deployment','No adopted threshold or formal 5% risk certification','No second-block or report work'],
    'input_sha256':hashed
}
(HERE/'diagnosis_receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
for target in re.findall(r'\]\(([^)]+)\)',(HERE/'README.md').read_text(encoding='utf-8')):
    if not target.startswith('http'):check((HERE/target).is_file())
manifest={p.relative_to(HERE).as_posix():sha(p) for p in sorted(HERE.rglob('*')) if p.is_file() and p.name!='artifact_manifest.json' and '__pycache__' not in p.parts}
(HERE/'artifact_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'status':'passed','root_checks':checks,'verified_input_files':len(hashed),'manifest_files':len(manifest),'protected_scientific_files':protection['files_before']-1},ensure_ascii=False))
