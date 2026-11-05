from common import *
from evaluate import cache,score,summary,gates
def verify():
    for manifest in ['freeze.json','confirmation_freeze.json']:
        for p,h in read(manifest)['source_sha256'].items():assert sha(ROOT/p)==h,p
def final(stage):
    verify();rows=score(cache(stage),read('selected.json')['config']);write(stage+'/metrics.json',rows);write(stage+'/assessment.json',summary(rows));print(stage,json.dumps(native(summary(rows))),flush=True)
def assess():
    verify();a=read('main_confirmation/metrics.json');b=read('weak_confirmation/metrics.json');old_a=read('main_test/metrics.json');old_b=read('weak_test/metrics.json')
    check,s=gates(a,b);combined_check,combined=gates(a+old_a,b+old_b);prior=read('assessment.json');initial_safety={k:v for k,v in prior['checks'].items() if k!='false_reduction10'}
    decision=all(check.values()) and all(combined_check.values()) and all(initial_safety.values())
    write('confirmation_decision.json',dict(adopted=decision,one_fixed_confirmation=True,selected_config_unchanged=True,no_new_fit=True,initial_result=prior,confirmation_checks=check,combined_checks=combined_check,confirmation_summary=s,combined_summary=combined,
        per_seed={str(seed):summary([r for r in a+b if r['seed']==seed]) for seed in sorted({r['seed'] for r in a+b})},no_further_confirmation_of_same_candidate=True))
    print(json.dumps(native(dict(adopted=decision,confirmation_checks=check,combined_checks=combined_check,confirmation=s['pooled'],combined=combined['pooled']))),flush=True)
if __name__=='__main__':assess() if sys.argv[1]=='assess' else final(sys.argv[1])
