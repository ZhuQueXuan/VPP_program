from common import *
from evaluate import gates,summary

def audit(stage):
    cc=read(stage+'/facts.json');rows=read(stage+'/metrics.json');truth={};by={(r['task_id'],r['method']):r for r in rows};checks=0
    for panel in ['minute','10s']:
        for name in ['truth.json','mixed_truth.json']:truth.update({r['task_id']:r for r in read(HERE/stage/panel/name)})
    assert len(by)==4*len(cc)
    for c in cc:
        tid=c['task_id'];dt=c['ends_s'][0]-c['starts_s'][0];mask=[v>=.15 for s,v in zip(c['starts_s'],truth[tid]['true_reduction_kw']) if 0<=s<1800];cum=sum(mask)*dt;run=longest=0
        for yes in mask:run=run+1 if yes else 0;longest=max(run,longest)
        longest=longest*dt if longest*dt>=30.-1e-8 else 0.
        for method in ['cpop','labs','retained','candidate']:
            r=by[tid,method];pc,pl=r['predicted_cumulative_seconds'],r['predicted_longest_seconds'];assert abs(r['true_cumulative_seconds']-cum)<1e-8 and abs(r['true_longest_seconds']-longest)<1e-8
            assert (pc>0)==r['positive_prediction'];assert abs(r['primary_seconds']-(abs(pc-cum)+abs(pl-longest))/2)<1e-8;assert 0<=pl<=pc<=1800.+1e-8;checks+=5
        a,b=by[tid,'retained'],by[tid,'candidate']
        if not b['rejected']:assert all(a[k]==b[k] for k in ['predicted_cumulative_seconds','predicted_longest_seconds','positive_prediction','localized_miss'])
    return rows,dict(inputs=len(cc),base_trajectories=len({c['base_task_id'] for c in cc}),checks=checks)

def main():
    for p,h in read('freeze.json')['source_sha256'].items():assert sha(ROOT/p)==h,p
    a,ca=audit('main_test');b,cb=audit('weak_test');checks,summaries=gates(a,b);rejected=[r for r in a+b if r['method']=='candidate' and r['rejected']]
    seed_details={str(seed):summary([r for r in a+b if r['seed']==seed]) for seed in sorted({r['seed'] for r in a+b})}
    write('assessment.json',dict(adopted=all(checks.values()),checks=checks,summary=summaries,per_seed=seed_details,independent_audit=dict(main=ca,weak=cb),
        rejected_records=len(rejected),rejected_base_trajectories=len({r['base_task_id'] for r in rejected}),rejected_true_effective=sum(r['positive_truth'] for r in rejected),
        rejected_physical_no_action=sum(r['physical_no_action'] for r in rejected),rejected_real_underthreshold=sum(not r['physical_no_action'] for r in rejected),
        physical_observation_preserved=True,negative_decisions_not_inconclusive_dropped_records=True,no_field_accuracy_claim=True,no_final_tuning=True))
    print(json.dumps(native(dict(adopted=all(checks.values()),checks=checks,pooled=summaries['pooled']))),flush=True)
if __name__=='__main__':main()
