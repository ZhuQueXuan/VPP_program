from common import *
from scipy.stats import t as student_t

def balanced(rows,method,key,seed=None):
    values=[]
    for panel in ['minute','10s']:
        rr=[r for r in rows if r['method']==method and r['panel']==panel and (seed is None or r['seed']==seed)]
        values.append(np.mean([np.mean([r[key] for r in rr if r['condition']==c]) for c in sorted({r['condition'] for r in rr})]))
    return float(np.mean(values))

def main():
    rows=read('test/metrics.json');stress=read('stress/metrics.json');seeds=read('evaluation_protocol.json')['test_seeds'];methods=['cpop','duration_fusion','labs']
    seedrows=[dict(seed=s,**{m:balanced(rows,m,'primary_seconds',s) for m in methods}) for s in seeds]
    diff=np.array([r['duration_fusion']-r['cpop'] for r in seedrows]);mean=float(diff.mean());half=float(student_t.ppf(.975,len(diff)-1)*diff.std(ddof=1)/np.sqrt(len(diff)))
    values={m:{k:balanced(rows,m,k) for k in ['primary_seconds','cumulative_error_seconds','longest_error_seconds','curve_mse_kw2']} for m in methods}
    counts={m:{k:int(sum(r[k] for r in rows if r['method']==m)) for k in ['whole_miss','null_false_positive','short_local_miss','true_gap_filled']} for m in methods}
    byid={(r['task_id'],r['method']):r for r in rows}
    identical=all(byid[r['task_id'],'duration_fusion']['whole_miss']==r['whole_miss'] and byid[r['task_id'],'duration_fusion']['null_false_positive']==r['null_false_positive'] for r in rows if r['method']=='cpop')
    gates=dict(all_outputs_available=all(r['status']=='ok' for r in rows+stress),primary_at_least10percent_better=values['duration_fusion']['primary_seconds']<=.9*values['cpop']['primary_seconds'],
        paired_seed95_upper_below0=mean+half<0,at_least8of12_seed_blocks_better=int(np.sum(diff<0))>=8,
        cumulative_noninferiority5s=values['duration_fusion']['cumulative_error_seconds']<=values['cpop']['cumulative_error_seconds']+5,
        no_extra_short_local_miss=counts['duration_fusion']['short_local_miss']<=counts['cpop']['short_local_miss'],
        no_extra_true_gap_fill=counts['duration_fusion']['true_gap_filled']<=counts['cpop']['true_gap_filled'],event_positive_status_identical=identical,
        near_threshold_stress_noninferiority5s=balanced(stress,'duration_fusion','primary_seconds')<=balanced(stress,'cpop','primary_seconds')+5)
    for panel in ['minute','10s']:
        rr=[r for r in rows if r['panel']==panel]
        gates[panel+'_primary_noninferiority5s']=np.mean([r['primary_seconds'] for r in rr if r['method']=='duration_fusion'])<=np.mean([r['primary_seconds'] for r in rr if r['method']=='cpop'])+5
    result=dict(adopt=all(gates.values()),gates=gates,failed_gates=[k for k,v in gates.items() if not v],balanced_metrics=values,counts=counts,
        seed_rows=seedrows,paired_seed_delta_seconds=mean,paired_seed95_interval=[mean-half,mean+half],
        stress_primary={m:balanced(stress,m,'primary_seconds') for m in methods},
        scope='New known-reference controlled simulations; frozen trained models. No field100ms fault recognition or unknown-reference claim.')
    write('assessment.json',result);print(json.dumps(result),flush=True)
if __name__=='__main__':main()
