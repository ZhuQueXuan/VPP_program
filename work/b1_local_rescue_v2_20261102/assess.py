"""Independent confirmation accounting; no selection or refit."""
from common import *
from evaluate import gates,summarize,aggregate
from scipy.stats import t as student_t

def verify(stage):
    cases=read(stage+'/facts.json');truth={}
    for panel in ['minute','10s']:
        for name in ['truth.json','mixed_truth.json']:truth.update({r['task_id']:r for r in read(HERE/stage/panel/name)})
    rows=read(stage+'/metrics.json');by={(r['task_id'],r['method']):r for r in rows};checks=0
    assert len(by)==4*len(cases)
    for c in cases:
        dt=c['ends_s'][0]-c['starts_s'][0];values=[v>=.15 for s,v in zip(c['starts_s'],truth[c['task_id']]['true_reduction_kw']) if 0<=s<1800];cum=sum(values)*dt;run=longest=0
        for value in values:run=run+1 if value else 0;longest=max(run,longest)
        ll=longest*dt if longest*dt>=30.-1e-8 else 0.
        for method in ['cpop','labs','retained','candidate']:
            r=by[c['task_id'],method];assert abs(r['true_cumulative_seconds']-cum)<1e-8 and abs(r['true_longest_seconds']-ll)<1e-8
            assert abs(r['primary_seconds']-(abs(r['predicted_cumulative_seconds']-cum)+abs(r['predicted_longest_seconds']-ll))/2)<1e-8
            assert 0<=r['predicted_longest_seconds']<=r['predicted_cumulative_seconds']<=1800.+1e-8
            checks+=4
    return rows,dict(inputs=len(cases),base_trajectories=len({c['base_task_id'] for c in cases}),checks=checks)

def paired(rows):
    differences=[]
    for seed in sorted({r['seed'] for r in rows}):
        block=[r for r in rows if r['seed']==seed];differences.append(aggregate(block,'candidate')['primary_seconds']-aggregate(block,'retained')['primary_seconds'])
    d=np.asarray(differences);margin=student_t.ppf(.975,len(d)-1)*d.std(ddof=1)/np.sqrt(len(d))
    return dict(seed_differences=d,mean=float(d.mean()),monte_carlo95=[float(d.mean()-margin),float(d.mean()+margin)])

def main():
    for p,h in read('freeze.json')['source_sha256'].items():assert sha(ROOT/p)==h,p
    a,ca=verify('main_test');b,cb=verify('weak_test');checks,sa,sb=gates(a,b)
    by_kind={k:{m:aggregate([r for r in b if r['kind']==k],m) for m in ['cpop','labs','retained','candidate']} for k in sorted({r['kind'] for r in b})}
    write('assessment.json',dict(adopted=all(checks.values()),checks=checks,main=sa,weak=sb,weak_by_kind=by_kind,independent_checks=dict(main=ca,weak=cb),paired=dict(main=paired(a),weak=paired(b)),
        previously_seen_test_not_reused_as_final=True,new_localized_interval_support=True,duration_functionals_explicitly_separate=True,no_field_accuracy_claim=True))
    print(json.dumps(native(dict(adopted=all(checks.values()),checks=checks,main=sa['all'],weak_genuine_short=sb['genuine_short_n']))),flush=True)

if __name__=='__main__':main()
