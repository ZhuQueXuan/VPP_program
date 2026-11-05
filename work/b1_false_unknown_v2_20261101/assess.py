"""Evaluate frozen binary predictions on all tasks, including rejected ones."""
from common import *
from train_choose import evaluate
from scipy.stats import t as student_t

def main():
    frozen=read('test_freeze.json')
    for path,expected in frozen['source_sha256'].items():assert sha(ROOT/path)==expected,path
    selected=read('selected.json');rows=evaluate('test',read(selected['model']),selected['threshold'])
    write('test/metrics.json',rows);ss=summary(rows);write('test/summary.json',ss);by={(r['regime'],r['method']):r for r in ss};checks={};intervals={}
    for regime in ['known','unknown']:
        a=by[regime,'candidate'];old=by[regime,'retained'];cp=by[regime,'cpop']
        checks[regime+'_fewer_false_positives']=a['null_false_positive']<cp['null_false_positive']
        checks[regime+'_short_misses_not_increased']=a['short_local_miss']<=old['short_local_miss']
        checks[regime+'_whole_misses_increase_at_most1pp']=a['whole_miss']<=old['whole_miss']+.01*old['positive_truth']
        checks[regime+'_localized_misses_increase_at_most1pp']=a['localized_miss']<=old['localized_miss']+.01*old['positive_truth']
        checks[regime+'_duration_better_than_original']=a['primary_seconds']<=cp['primary_seconds']
        checks[regime+'_duration_not_worse_than_retained5s']=a['primary_seconds']<=old['primary_seconds']+5
        differences=[]
        for seed in sorted({r['seed'] for r in rows if r['regime']==regime}):
            st=summary([r for r in rows if r['seed']==seed and r['regime']==regime]);bd={r['method']:r for r in st};differences.append(bd['candidate']['primary_seconds']-bd['cpop']['primary_seconds'])
        diff=np.array(differences);half=float(student_t.ppf(.975,len(diff)-1)*diff.std(ddof=1)/np.sqrt(len(diff)))
        intervals[regime]=dict(seed_differences=diff,mean=float(diff.mean()),MC_t95=[float(diff.mean()-half),float(diff.mean()+half)])
    short_rows=evaluate('short_test',read(selected['model']),selected['threshold']);write('short_test/metrics.json',short_rows);short_summary=summary(short_rows);write('short_test/summary.json',short_summary);sb={r['method']:r for r in short_summary}
    checks['extra_unknown60s_short_misses_not_increased']=sb['candidate']['short_local_miss']<=sb['retained']['short_local_miss']
    checks['extra_unknown60s_duration_not_worse_than_CPOP5s']=sb['candidate']['primary_seconds']<=sb['cpop']['primary_seconds']+5
    result=dict(adopt=all(checks.values()),checks=checks,failed=[k for k,v in checks.items() if not v],summary=ss,paired_seed_intervals=intervals,short_summary=short_summary,
        limitations='Controlled data; shared predicted reference at1min only for unknown. Learned threshold response class, no field fault labels, no certified5percent false-alarm guarantee.',
        adoption_means='Candidate can be retained only if safety and benefits pass; existing duration_fusion remains available unchanged regardless.')
    write('assessment.json',result);print(json.dumps(native(result)),flush=True)
if __name__=='__main__':main()
