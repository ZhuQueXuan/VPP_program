"""Final provenance checks only; no estimator or extra parameter selection."""
from common import *
import re
def main():
    checks=0
    def check(v):
        nonlocal checks
        assert v;checks+=1
    protection=read('protection_receipt.json')
    check(protection['scientific_unchanged'] and protection['changed']==['AGENTS.md'])
    frozen=read('validation_freeze.json')
    check(frozen['selected_ratio']==1. and frozen['test_not_generated_yet'])
    for p,h in frozen['source_sha256'].items():check(sha(ROOT/p)==h)
    for p,h in frozen['production_sha256'].items():check(sha(ROOT/p)==h)
    syn=read('audit/independent_synthetic.json');real=read('audit/independent_real.json')
    check(syn['status']==real['status']=='passed')
    check(syn['frozen_source_ok'] and not syn['passes_all_adoption_gates'])
    check(real['all_available'] and real['real_events']==72 and real['metric_rows']==648)
    seen={}
    for audit in [syn,real]:
        for p,h in audit['input_sha256'].items():
            if p=='AGENTS.md':continue
            if p in seen:check(seen[p]==h)
            else:check(sha(ROOT/p)==h);seen[p]=h
    check(read('controls_receipt.json')['native_full_block_max_curve_difference']==0.)
    decision=read('adoption_decision.json')
    check(not decision['adopt'] and decision['all480_raw_eta_same_across3'])
    check([k for k,v in decision['adoption_gates'].items() if not v]==['primary_all_conditions_at_least10percent_better'])
    check(len(read('outputs/validation_metrics.json'))==640 and len(read('outputs/test_metrics.json'))==1440)
    check(len(read('real_metrics.json'))==648)
    check(all(r['status']=='ok' for r in read('outputs/test_metrics.json')+read('real_metrics.json')))
    selected=frozen['selected_method']
    check(decision['genuine_single_bin']['gaussian'][selected]['whole_miss']==0)
    check(decision['null']['gaussian_plus_spikes'][selected]['null_false_positive']==17)
    check(decision['main_summary']['all'][selected]['primary_seconds']==47.8125)
    check(decision['main_summary']['all']['cpop']['primary_seconds']==44.875)
    receipt={
       'status':'completed_not_adopted','date':'2026-10-31','first_block_only':True,'report_postponed':True,
       'version':'cpop-finite-jump-block-v2','implementation':'candidate.py',
       'modification':'Native continuous-CPOP blocks combined with unpruned optional free level/slope resets on an observed finite candidate dictionary; original zero-reset family included.',
       'point_values_changed':False,'point_weights_changed':False,'minimum_duration_filter_added':False,
       'model_scope':'Fixed candidate dictionary optimum, not arbitrary boundary GRACE, not incoming-slope-preserving jumps or latent within-bin timing',
       'validation':{'independent_bases':80,'paired_inputs':160,'outputs':640,'active_ratios':[1.,1.5],
           'selected_ratio':1.,'ratio2_only_dominated_math_control':True,'test_generated_after_freeze':True},
       'test':{'new_independent_bases':240,'seed_blocks':6,'paired_inputs':480,'outputs':1440,'all_available':True,
           'given_reference_not_predictor_or_field_proof':True},
       'primary_all_seconds':{'cpop':44.875,'v2':47.8125,'labs':105.25},
       'short_response':{'genuine_onebin_gaussian_misses':{'cpop':0,'v2':0,'labs':24},'n':24,
           'brief_weak_gaussian_misses':{'cpop':3,'v2':2,'labs':4}},
       'false_positive_null_spikes':{'n':24,'cpop':17,'v2':17,'labs':2},
       'adopt':False,'failed_gates':['overall duration improvement>=10%'],
       'recommendation':'Keep original CPOP foundation and LABS control; preserve v2 prototype and negative results. No production/default change or further tuning on this test.',
       'real_auxiliary':{'old_recordings':18,'old_events':72,'input_variants':216,'outputs':648,'all_available':True,
           'new_real_holdout':False,'latent_accuracy_claim':False,'same_method_extra_spike_longest_change_seconds':
             {'cpop':1.8638888888888887,'v2':1.8527777777777774,'labs':.4041666666666667}},
       'verification_not_performance_sample_counts':{'synthetic':syn['n_checks'],'real':real['n_checks'],
            'synthetic_exhaustive_partitions':syn['exhaustive_partitions_checked'],'real_exhaustive_partitions':real['exhaustive_partitions_checked']},
       'protected_scientific_files':protection['files']-1,'verified_input_files':len(seen),
       'production_source_API_default_changed':False,'old_scientific_records_changed':False,
       'forecaster_trained':False,'effects_B2B3B4_or_reports_changed':False,'installed_deleted_uploaded_committed':False,
       'source_sha256':{p:sha(HERE/p) for p in ['README.md','candidate.py','common.py','blocks_batch.R','labs_batch.R','protocol.json','simulation.py','run_synthetic.py','run_real.py','adoption_decision.json']}}
    write('completion_receipt.json',receipt)
    text=(HERE/'README.md').read_text(encoding='utf-8')
    for rel in re.findall(r'\]\(([^)]+)\)',text):
        if not rel.startswith(('http','D:','C:')):check((HERE/rel).is_file())
    manifest={p.relative_to(HERE).as_posix():sha(p) for p in sorted(HERE.rglob('*')) if p.is_file() and p.name!='artifact_manifest.json' and '__pycache__' not in p.parts}
    write('artifact_manifest.json',manifest)
    print(json.dumps({'status':'complete_not_adopted','root_checks':checks,'verified_inputs':len(seen),
        'protected_science':protection['files']-1,'artifacts':len(manifest)},ensure_ascii=False))
if __name__=='__main__':main()
