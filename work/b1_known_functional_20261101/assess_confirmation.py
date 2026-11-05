"""Post-freeze observer: no fitting, selection, threshold or estimator changes."""
from common import *
from evaluate import aggregate,truth_for
from scipy.stats import t as student_t

def audit(stage):
    facts=read(stage+'/facts.json');curves=read(stage+'/curves.json');rows=read(stage+'/metrics.json');truth=truth_for(HERE,stage)
    assert len({c['task_id'] for c in facts})==len(facts)
    lookup={(r['task_id'],r['method']):r for r in rows};assert len(lookup)==4*len(facts)
    checks=0
    for c,curve in zip(facts,curves):
        assert c['task_id']==curve['task_id'];s=np.array(c['starts_s']);use=(s>=0)&(s<1800);dt=c['ends_s'][0]-s[0];true=np.asarray(truth[c['task_id']]['true_reduction_kw'])[use]>=.15
        count=int(true.sum());best=run=0
        for value in true:run=run+1 if value else 0;best=max(best,run)
        tc=count*dt;tl=best*dt if best*dt>=30.-1e-8 else 0.
        for method in ['cpop','labs','retained','candidate']:
            r=lookup[c['task_id'],method];pc=r['predicted_cumulative_seconds'];pl=r['predicted_longest_seconds']
            assert abs(r['true_cumulative_seconds']-tc)<1e-7
            assert abs(r['true_longest_seconds']-tl)<1e-7
            assert abs(r['primary_seconds']-(abs(pc-tc)+abs(pl-tl))/2)<1e-7
            assert 0<=pl<=pc<=1800 and (pl==0 or pl>=30.-1e-8)
            if method!='candidate':
                pp=np.asarray(curve['results'][method]['prediction'])[use]>=.15
                run=best=0
                for value in pp:run=run+1 if value else 0;best=max(best,run)
                assert abs(pc-pp.sum()*dt)<1e-7
                assert abs(pl-(best*dt if best*dt>=30.-1e-8 else 0.))<1e-7
            checks+=6
    return rows,dict(inputs=len(facts),base_trajectories=len({c['base_task_id'] for c in facts}),method_rows=len(rows),checks=checks)

def paired(rows,subset=None):
    rr=[r for r in rows if subset is None or r[subset]];d=[]
    for seed in sorted({r['seed'] for r in rr}):
        block=[r for r in rr if r['seed']==seed]
        d.append(aggregate(block,'candidate')['primary_seconds']-aggregate(block,'retained')['primary_seconds'])
    d=np.asarray(d);se=float(d.std(ddof=1)/np.sqrt(len(d)));margin=float(student_t.ppf(.975,len(d)-1))*se
    return dict(seed_differences_seconds=d,mean_difference_seconds=float(d.mean()),monte_carlo_95_percent_interval=[float(d.mean()-margin),float(d.mean()+margin)],improved_seed_blocks=int(sum(d<0)),blocks=len(d))

def main():
    for p,h in read('freeze.json')['source_sha256'].items():assert sha(ROOT/p)==h,p
    output={};data={}
    for stage in ['test','stress_test']:
        rows,info=audit(stage);data[stage]=rows
        summary={subset or 'all':{m:aggregate(rows,m,subset) for m in ['cpop','labs','retained','candidate']} for subset in [None,'weak','explicit_gap','short_n']}
        conditions={c:{m:aggregate([r for r in rows if r['condition']==c],m) for m in ['cpop','labs','retained','candidate']} for c in sorted({r['condition'] for r in rows})}
        # Actual no-action records are distinguished from weak actions that
        # physically occur but never attain the effective response threshold.
        nulls=[r for r in rows if r['kind']=='null'];zero={m:dict(n=sum(r['method']==m for r in nulls),false_positives=sum(r['null_false_positive'] for r in nulls if r['method']==m)) for m in ['cpop','labs','retained','candidate']}
        output[stage]=dict(summary=summary,conditions=conditions,zero_action=zero,independent_audit=info,paired=paired(rows),weak_paired=paired(rows,'weak'))
    a=output['test']['summary'];b=output['stress_test']['summary'];checks={}
    checks['weak10percent_gain']=b['weak']['candidate']['primary_seconds']<=.9*b['weak']['retained']['primary_seconds']
    checks['main_noninferiority2s']=a['all']['candidate']['primary_seconds']<=a['all']['retained']['primary_seconds']+2
    checks['main_fewer_false']=a['all']['candidate']['null_false_positive']<a['all']['retained']['null_false_positive']
    for name,summary in [('test',a),('stress_test',b)]:
        for key in ['short_local_miss','whole_miss']:checks[name+'_'+key]=summary['all']['candidate'][key]<=summary['all']['retained'][key]
        checks[name+'_gap_duration_noninferiority5s']=summary['explicit_gap']['candidate']['longest_error_seconds']<=summary['explicit_gap']['retained']['longest_error_seconds']+5
        checks[name+'_short_duration_noninferiority5s']=summary['short_n']['candidate']['primary_seconds']<=summary['short_n']['retained']['primary_seconds']+5
    write('confirmation_assessment.json',dict(checks=checks,adoption_gates_pass=all(checks.values()),stages=output,
        no_field_accuracy_claim=True,all_final_results_retained=True,no_tuning_on_final=True,
        localization_uses_retained_structural_support=True,new_duration_estimates_not_a_new_pointwise_power_curve=True))
    print(json.dumps(native(dict(checks=checks,adoption=all(checks.values()),summaries={k:v['summary'] for k,v in output.items()}))),flush=True)

if __name__=='__main__':main()
