"""Close provenance and review receipts, without fitting or changing results."""
from common import *
import re
checks=0
def check(v):
    global checks
    assert v
    checks+=1
def main():
    protection=read('protection_receipt.json')
    check(protection['scientific_unchanged']);check(protection['changed']==['AGENTS.md'])
    syn=read('independent_audit/synthetic_audit.json')
    real=read('design_review/independent_real/real_audit.json')
    check(syn['status']=='passed');check(real['status']=='passed')
    check(real['metric_rows']==1728 and real['cases']==144)
    seen={}
    for name in ['real_preparation_receipt.json','design_review/independent_real/real_audit.json']:
        d=read(name)
        hashes=d.get('input_sha256',d.get('source_sha256',{}))
        for path,digest in hashes.items():
            if path in seen:check(seen[path]==digest);continue
            check(sha(ROOT/path)==digest);seen[path]=digest
    frozen=read('validation_freeze.json')
    check(frozen['selected_candidate']=='labs_2026' and frozen['test_not_generated_yet'])
    for path,digest in frozen['source_sha256'].items():check(sha(HERE/path)==digest)
    decision=read('selection_decision.json')
    check(not decision['candidate_passes_frozen_improvement_gate'])
    check(decision['CP_beats_revised_seed_count']==6)
    sm=read('outputs/test_metrics.json');vm=read('outputs/validation_metrics.json')
    rm=read('real_metrics.json')
    check(len(sm)==1344 and len(vm)==448 and len(rm)==1728)
    check(all(r['status']=='ok' for r in sm+vm))
    check(sum(r['status']=='ok' for r in rm)==1699)
    unavailable=[r for r in rm if r['status']!='ok']
    check(len(unavailable)==29 and all(r['method']=='tf_standard' and r['condition']=='original_observation' for r in unavailable))
    prep=read('real_preparation_receipt.json')
    check(prep['source_hashes_unchanged'] and not prep['preparation_failures_replaced'])
    check(sha(HERE/'real_cases.json')==prep['cases_sha256'])
    text=(HERE/'README.md').read_text(encoding='utf-8')
    check('| 标准TF | 23.75 | 65.63 | 44.69 | .03938 |' in text)
    check('| 原CPOP对照 | 21.56 | 29.06 | **25.31** | **.03452** |' in text)
    summary={r['method']:r for r in read('outputs/test_summary.json') if r['kind']=='all'}
    check(summary['tf_standard']['cumulative_error_seconds']==23.75)
    check(summary['tf_standard']['longest_error_seconds']==65.625)
    completion={
       'status':'complete','study_date':'2026-10-31',
       'scope':'Literature search, actual estimator reproduction and bounded first-block comparison; report postponed',
       'literature_candidate':{'name':'LABS','date':'2026-08-21','type':'author preprint and native R source',
          'paper':'https://arxiv.org/abs/2608.21122','repository':'https://github.com/pfryz/LABS',
          'commit':'0bb0524dec39336a2e0d032287ce092e2968145a','license':'MIT for original author code'},
       'simulation':{'noise_development_users':128,'validation_tasks':64,'test_tasks':192,'test_seeds':6,
          'methods':7,'validation_outputs':448,'test_outputs':1344,'all_available':True,
          'known_reference_not_field_or_unknown_reference_proof':True,'no_forecaster_trained':True},
       'real':{'original_recordings':18,'selected_real_events':144,'directions':{'up':72,'down':72},
          'conditions':3,'inputs':432,'outputs':1728,'available':1699,'TF_certificate_rejections':29,
          'added_perturbations_are_not_new_real_events':True,'latent_truth_accuracy_claim':False,
          'RIDE_seconds_current_domain_not_applicable':True},
       'frozen_selection':{'candidate':'labs_2026','gate_passed':False,
           'duration_improvement_percent':decision['candidate_primary_improvement_vs_revised_percent'],
           'reason':'Less than10% improvement and pooled curve RMSE increased'},
       'recommendation':'Keep direct instruction/measurement feature definitions; CPOP is the strongest present duration/curve baseline for known-reference tasks. No new candidate whole-block adoption or automatic CPOP replacement of the research mainline.',
       'evidence_limits':['Different timing/weak/interrupt features have different winners','Synthetic ODE power-shape model is not real energy-demand/market validation',
          'Added-spike LABS benefit is local; cumulative target-duration stability is not uniformly better',
          'TF low-noise seconds certificate failures are implementation-domain limitations, not proof of inherent model invalidity'],
       'production_source_default_or_API_changed':False,'old_scientific_data_results_changed':False,
       'second_block_or_report_changed':False,'new_dependencies_installed':False,
       'deleted_or_uploaded_or_committed':False,
       'protection':protection,'root_verified_inputs':len(seen),
       'independent_audits':{'synthetic':'independent_audit/synthetic_audit.json','real':'design_review/independent_real/real_audit.json'},
       'audit_checks_are_not_performance_samples':True,'source_sha256':{p:sha(HERE/p) for p in ['README.md','protocol.json','validation_freeze.json','selection_decision.json','real_comparison_receipt.json']}}
    write('completion_receipt.json',completion)
    for target in re.findall(r'\]\(([^)]+)\)',text):
        if not target.startswith(('http','D:','C:')):check((HERE/target).is_file())
    manifest={p.relative_to(HERE).as_posix():sha(p) for p in sorted(HERE.rglob('*')) if p.is_file() and p.name!='artifact_manifest.json' and '__pycache__' not in p.parts}
    write('artifact_manifest.json',manifest)
    print(json.dumps({'status':'complete','checks':checks,'verified_inputs':len(seen),'artifact_files':len(manifest),
           'protected_scientific_files':protection['files']-1,'candidate_adopted':False},ensure_ascii=False))
if __name__=='__main__':main()
