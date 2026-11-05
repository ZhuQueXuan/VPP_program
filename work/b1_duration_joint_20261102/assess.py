from common import *
from evaluate import gates,aggregate
from scipy.stats import t as student_t

def audit(stage):
    cc=read(stage+'/facts.json');truth={};rows=read(stage+'/metrics.json');by={(r['task_id'],r['method']):r for r in rows};checks=0
    for panel in ['minute','10s']:
        for name in ['truth.json','mixed_truth.json']:truth.update({r['task_id']:r for r in read(HERE/stage/panel/name)})
    assert len(by)==4*len(cc)
    for c in cc:
        dt=c['ends_s'][0]-c['starts_s'][0];mask=[v>=.15 for s,v in zip(c['starts_s'],truth[c['task_id']]['true_reduction_kw']) if 0<=s<1800];cum=sum(mask)*dt;run=longest=0
        for yes in mask:run=run+1 if yes else 0;longest=max(longest,run)
        longest=longest*dt if longest*dt>=30.-1e-8 else 0.
        for method in ['cpop','labs','retained','candidate']:
            r=by[c['task_id'],method];assert abs(r['true_cumulative_seconds']-cum)<1e-8 and abs(r['true_longest_seconds']-longest)<1e-8
            pc,pl=r['predicted_cumulative_seconds'],r['predicted_longest_seconds'];assert 0<=pl<=pc<=1800.+1e-8
            assert abs(r['primary_seconds']-(abs(pc-cum)+abs(pl-longest))/2)<1e-8
            assert (pc>0)==r['positive_prediction'];checks+=5
    return rows,dict(inputs=len(cc),base_trajectories=len({c['base_task_id'] for c in cc}),scalar_checks=checks)

def paired(rows):
    d=[]
    for seed in sorted({r['seed'] for r in rows}):
        rr=[r for r in rows if r['seed']==seed];d.append(aggregate(rr,'candidate')['primary_seconds']-aggregate(rr,'retained')['primary_seconds'])
    d=np.asarray(d);margin=student_t.ppf(.975,len(d)-1)*d.std(ddof=1)/np.sqrt(len(d))
    return dict(seed_differences_seconds=d,mean_difference_seconds=float(d.mean()),monte_carlo95=[float(d.mean()-margin),float(d.mean()+margin)],improved_blocks=int(sum(d<0)),blocks=len(d))

def main():
    for p,h in read('freeze.json')['source_sha256'].items():assert sha(ROOT/p)==h,p
    main,ma=audit('main_test');weak,wa=audit('weak_test');checks,summaries=gates(main,weak)
    kind={k:{m:aggregate([r for r in main+weak if r['kind']==k],m) for m in ['cpop','labs','retained','candidate']} for k in sorted({r['kind'] for r in main+weak})}
    write('assessment.json',dict(adopted=all(checks.values()),checks=checks,summary=summaries,by_kind=kind,independent_checks=dict(main=ma,weak=wa),paired=dict(main=paired(main),weak=paired(weak)),
        direct_duration_estimates_not_a_new_pointwise_curve=True,classification_and_localized_mask_preserved=True,no_test_tuning=True,no_field_accuracy_claim=True))
    print(json.dumps(native(dict(adopted=all(checks.values()),checks=checks,pooled=summaries['pooled']['all'],long=summaries['pooled']['long_effective']))),flush=True)
if __name__=='__main__':main()
