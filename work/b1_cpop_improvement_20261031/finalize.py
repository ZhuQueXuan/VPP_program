"""Close the bounded study; verification only, no estimators or new selection."""
from common import *
import re
def main():
    count=0
    def check(value):
        nonlocal count
        assert value;count+=1
    protection=read('protection_receipt.json')
    check(protection['scientific_unchanged'] and protection['changed']==['AGENTS.md'])
    frozen=read('validation_freeze.json')
    for rel,h in frozen['source_sha256'].items():check(sha(ROOT/rel)==h)
    for rel,h in frozen['production_sha256'].items():check(sha(ROOT/rel)==h)
    check(frozen['selected_kappa']==5 and frozen['test_not_generated_yet'])
    decision=read('adoption_decision.json')
    check(not decision['adopt'])
    check(not decision['gates']['spike_primary_at_least10percent_better'])
    check(not decision['gates']['one_bin_response_whole_misses_no_more_than_original_plus_one'])
    check(decision['raw_eta_all480_equal_all3'])
    syn=read('audit/independent_synthetic.json');real=read('audit/independent_real.json')
    check(syn['status']==real['status']=='passed')
    check(not syn['candidate_safe_to_adopt_by_protocol'])
    check(real['all_available'] and real['output_rows']==1296)
    inputs={}
    for d in [syn,real]:
        for rel,h in d['input_sha256'].items():
            if rel=='AGENTS.md':continue
            if rel not in inputs:check(sha(ROOT/rel)==h);inputs[rel]=h
            else:check(inputs[rel]==h)
    check(read('controls_receipt.json')['max_curve_difference']==0)
    check(len(read('outputs/validation_metrics.json'))==800)
    check(len(read('outputs/test_metrics.json'))==1440)
    check(len(read('real_metrics.json'))==1296)
    check(all(r['status']=='ok' for r in read('outputs/test_metrics.json')+read('real_metrics.json')))
    text=(HERE/'README.md').read_text(encoding='utf-8')
    for value in ['22.250','55.625','23.000','56.125','68.250','147.500','3','24']:
        check(value in text)
    check((HERE/'method_introduction.md').is_file() and (HERE/'sources.json').is_file())
    receipt={
       'status':'completed_not_adopted','date':'2026-10-31',
       'authorized_scope':'First-block CPOP improvement v1 and original CPOP/LABS comparison; one subagent for four-method introduction, reused for independent audits',
       'candidate':{'module':'candidate.py','version':'cpop-isolated-point-weight-v1','selected_kappa':5,
          'changes':['Local isolated-point data-dependent loss weights','Command-edge protection','Retained ambiguity/weight diagnostics; source values and raw integrals untouched'],
          'not_claimed':['New dynamic-programming core','Globally robust objective theorem','Physical noise-variance estimation','Real sensor-fault truth']},
       'validation':{'independent_base_tasks':80,'paired_inputs':160,'internal_candidate_kappas':[3,4,5],
          'all_method_outputs':800,'selected_before_test':True},
       'test':{'independent_base_tasks':240,'seed_blocks':6,'paired_inputs':480,'methods':3,
          'outputs':1440,'all_available':True,'same_reference_task_measurement_noise_information':True,
          'reference':'Explicit known simulation baseline, not forecast or command',
          'genuine_single_bin_responses_and_gaps_retained':True},
       'main_primary_seconds':{'gaussian':{'original_cpop':22.25,'candidate':23.,'labs':68.25},
          'gaussian_plus_spikes':{'original_cpop':55.625,'candidate':56.125,'labs':147.5}},
       'adoption':{'approved':False,'gates':decision['gates'],'reason':'No duration improvement; genuine single-bin response misses3/24 vs original0/24'},
       'real_auxiliary':{'original_events':144,'recordings':18,'inputs':432,'outputs':1296,'all_available':True,
          'no_new_real_holdout_or_latent_truth_claim':True,'same_method_extra_spike_longest_time_change_seconds':
            {'original_cpop':1.8548611111111113,'candidate':.7645833333333334,'labs':.38680555555555557},
          'interpretation':'Local artificial-noise stability benefit cannot override failed genuine-action safety gate'},
       'four_methods':'CPOP, LABS, teacher RIDE (RED interpreted from repository), earliest F0 with later F1 distinguished',
       'root_verification_checks_not_samples':count,'independent_audit_checks_not_samples':{'synthetic':syn['n_checks'],'real':real['n_checks']},
       'verified_input_files':len(inputs),'protected_scientific_files':protection['files']-1,
       'production_code_API_or_default_changed':False,'old_scientific_records_changed':False,
       'forecaster_trained':False,'effects_or_reports_changed':False,
       'installed_deleted_uploaded_committed':False,
       'core_source_sha256':{p:sha(HERE/p) for p in ['candidate.py','common.py','protocol.json','simulation.py','run_synthetic.py','run_real.py','weighted_cpop_batch.R','labs_batch.R','README.md','method_introduction.md','sources.json']}}
    write('completion_receipt.json',receipt)
    for rel in re.findall(r'\]\(([^)]+)\)',text):
        if not rel.startswith(('http','D:','C:')):check((HERE/rel).is_file())
    manifest={p.relative_to(HERE).as_posix():sha(p) for p in sorted(HERE.rglob('*')) if p.is_file() and p.name!='artifact_manifest.json' and '__pycache__' not in p.parts}
    write('artifact_manifest.json',manifest)
    print(json.dumps({'status':'complete_not_adopted','root_checks':count,'verified_inputs':len(inputs),
       'protected_science':protection['files']-1,'artifacts':len(manifest),'actual_new_prediction_models':0},ensure_ascii=False))
if __name__=='__main__':main()
