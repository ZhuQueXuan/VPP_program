from common import *
from scipy.stats import t as student_t

def main():
    for p,h in read('freeze.json')['source_sha256'].items():assert sha(ROOT/p)==h,p
    selected=read('selected.json')['method'];summaries=read('test/summary.json');by={c:{r['method']:r for r in rr} for c,rr in summaries.items()};a=by['main'][selected];old=by['main']['old_retained'];cp=by['main']['tracked_cpop'];s=by['short'][selected];so=by['short']['old_retained']
    rows=read('test/metrics.json');diff=[];vs_cp=[]
    for seed in sorted({r['seed'] for r in rows if r['cohort']=='main'}):
        z={r['method']:r for r in summary([r for r in rows if r['cohort']=='main' and r['seed']==seed])};diff.append(z[selected]['primary_seconds']-z['old_retained']['primary_seconds']);vs_cp.append(z[selected]['primary_seconds']-z['tracked_cpop']['primary_seconds'])
    v=np.array(diff);half=float(student_t.ppf(.975,len(v)-1)*v.std(ddof=1)/np.sqrt(len(v)))
    checks=dict(main_duration10percent_better=a['primary_seconds']<=.9*old['primary_seconds'],paired_seed95upper_below0=v.mean()+half<0,
        same_tracked_cpop_noninferiority=a['primary_seconds']<=cp['primary_seconds'],main_whole_miss_not_increased=a['whole_miss']<=old['whole_miss'],
        main_short_miss_not_increased=a['short_local_miss']<=old['short_local_miss'],main_false_positive_not_increased=a['null_false_positive']<=old['null_false_positive'],
        short_local_miss_not_increased=s['short_local_miss']<=so['short_local_miss'],short_false_positive_not_increased=s['null_false_positive']<=so['null_false_positive'],short_duration_noninferiority5s=s['primary_seconds']<=so['primary_seconds']+5)
    result=dict(adopt=all(checks.values()),selected_method=selected,checks=checks,failed=[k for k,v in checks.items() if not v],summary=summaries,
        main_paired_seed_delta=float(v.mean()),MC_t95=[float(v.mean()-half),float(v.mean()+half)],seed_differences=diff,same_condition_CPOP_seed_differences=vs_cp,
        scope='Controlled retrospective feature extraction, pre-actuation0 contract, native1min. Prediction available at notice is unchanged; no current-task or post-task residual enters error tracking.')
    write('assessment.json',result);print(json.dumps(native(result)),flush=True)
if __name__=='__main__':main()
