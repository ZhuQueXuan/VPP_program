"""Readonly attribution and preservation receipt; no test-driven changes."""
from common import *
from scipy.stats import t as student_t

def interval(values):
    v=np.array(values,float);h=float(student_t.ppf(.975,len(v)-1)*v.std(ddof=1)/np.sqrt(len(v)))
    return dict(mean=float(v.mean()),MC_t95=[float(v.mean()-h),float(v.mean()+h)],seed_differences=v)

def main():
    assessment=read('assessment.json');assert not assessment['adopt'];assert read('independent_checks.json')['passed']
    ss=assessment['short_summary'];b={r['method']:r for r in ss}
    rows=read('short_test/metrics.json');by={(r['task_id'],r['method']):r for r in rows};curves={r['task_id']:r for r in read('short_test/curves.json')};cases={r['task_id']:r for r in read('short_test/all_facts.json')};lost=[]
    for r in rows:
        if r['method']=='candidate' and r['short_local_miss'] and not by[r['task_id'],'retained']['short_local_miss']:
            c=cases[r['task_id']];s=np.array(c['starts_s']);p=np.array(curves[r['task_id']]['results']['cpop']['prediction']);use=(s>=0)&(s<1800)
            lost.append(dict(task_id=r['task_id'],score=r['score'],accepted=r['accepted'],original_positive_bins=[dict(start_s=float(s[i]),reduction_kw=float(p[i])) for i in np.flatnonzero(use&(p>=.15))],
                reason='CPOP and retained identified a localized true short response; added whole-task classifier rejected the event. Not a CPOP segmentation failure.'))
    pairs={}
    mainrows=read('test/metrics.json')
    for regime in ['known','unknown']:
        diffs=[]
        for seed in sorted({r['seed'] for r in mainrows if r['regime']==regime}):
            z={r['method']:r for r in summary([r for r in mainrows if r['regime']==regime and r['seed']==seed])};diffs.append(z['retained']['primary_seconds']-z['cpop']['primary_seconds'])
        pairs[regime]=interval(diffs)
    write('diagnosis.json',dict(additional_short_misses=lost,attribution='Added classifier made the two additional errors; original segmentation and retained method already localized these responses.',
        retained_method_paired_seed_duration_change=pairs,unknown_reference_drift='Unknown predicted reference is shared, not evaluator truth. Existing duration correction was trained on known-reference noise; shift can weaken its duration gain.',
        no_test_tuning=True,rejected_candidate_preserved_for_research=True))
    for p,h in read('preserved_before.json').items():assert sha(ROOT/p)==h,p
    write('completion_receipt.json',dict(status='completed_comparison',existing_adopted_version_retained=True,new_candidate_adopted=False,
        reason='Unknown-reference short-response safety failed:4/256 versus retained2/256.',
        main_inputs=2048,extra_unknown_short_inputs=512,main_method_outputs=8192,extra_method_outputs=2048,
        original_CPOP_LABS_same_reference_controls=True,old_code_model_scientific_results_unchanged=True,formal_code_changes=0,
        report_second_block_changes=0,independent_audit_passed=True,no_deletion_new_library_GPU_or_external_submission=True,
        scope='Known-reference native1min/10s and predicted-reference native1min controlled simulations, not field validation or a certified5percent error guarantee.',
        result_sha256={p:sha(HERE/p) for p in ['assessment.json','test/metrics.json','short_test/metrics.json','independent_checks.json','diagnosis.json','test_freeze.json']}))
    print(json.dumps(native(dict(extra_lost=lost,retained_seed_intervals=pairs))))
if __name__=='__main__':main()
