from common import *
from scipy.stats import t as student_t

def balanced(rows,method,key,seed=None):
    rr=[r for r in rows if r['method']==method and (seed is None or r['seed']==seed)];panels=[]
    for p in ['minute','10s']:
        ss=[r for r in rr if r['panel']==p];cond=[]
        for c in sorted({r['condition'] for r in ss}):cond.append(float(np.mean([r[key] for r in ss if r['condition']==c])))
        panels.append(float(np.mean(cond)))
    return float(np.mean(panels))

def main():
    rows=read('test/metrics.json');stress=read('stress/metrics.json');seeds=read('evaluation_protocol.json')['test_seeds'];methods=['cpop','segment_boost','labs']
    seedrows=[dict(seed=s,**{m:balanced(rows,m,'primary_seconds',s) for m in methods}) for s in seeds]
    differences=np.array([r['segment_boost']-r['cpop'] for r in seedrows]);mean=float(differences.mean());half=float(student_t.ppf(.975,len(seeds)-1)*differences.std(ddof=1)/np.sqrt(len(seeds)))
    values={m:{k:balanced(rows,m,k) for k in ['primary_seconds','cumulative_error_seconds','longest_error_seconds','curve_mse_kw2']} for m in methods}
    counts={m:{k:int(sum(r[k] for r in rows if r['method']==m)) for k in ['short_local_miss','true_gap_filled','null_false_positive','whole_miss']} for m in methods}
    gates=dict(all_outputs_available=all(r['status']=='ok' for r in rows+stress),
        primary_at_least10percent_better=values['segment_boost']['primary_seconds']<=.9*values['cpop']['primary_seconds'],
        paired_seed95_upper_below0=mean+half<0,at_least8of12_seed_blocks_better=int(np.sum(differences<0))>=8,
        cumulative_noninferiority5s=values['segment_boost']['cumulative_error_seconds']<=values['cpop']['cumulative_error_seconds']+5,
        short_local_misses_not_increased=counts['segment_boost']['short_local_miss']<=counts['cpop']['short_local_miss'],
        true_short_gap_fill_not_increased=counts['segment_boost']['true_gap_filled']<=counts['cpop']['true_gap_filled'],
        null_false_not_over_original_plus1=counts['segment_boost']['null_false_positive']<=counts['cpop']['null_false_positive']+1,
        whole_misses_not_over_original_plus2=counts['segment_boost']['whole_miss']<=counts['cpop']['whole_miss']+2,
        near_threshold_stress_noninferiority5s=balanced(stress,'segment_boost','primary_seconds')<=balanced(stress,'cpop','primary_seconds')+5)
    for panel in ['minute','10s']:
        p=[r for r in rows if r['panel']==panel]
        gates[panel+'_primary_noninferiority5s']=np.mean([r['primary_seconds'] for r in p if r['method']=='segment_boost'])<=np.mean([r['primary_seconds'] for r in p if r['method']=='cpop'])+5
    result=dict(adopt=all(gates.values()),gates=gates,failed_gates=[k for k,v in gates.items() if not v],balanced_metrics=values,counts=counts,
        paired_seed_mean_delta_seconds=mean,paired_seed95_interval=[mean-half,mean+half],seed_rows=seedrows,
        stress_balanced_primary={m:balanced(stress,m,'primary_seconds') for m in methods},
        limitation='New controlled known-reference simulations only; no field100ms truth, sensor fault identification or unknown-reference validation.')
    write('assessment.json',result);print(json.dumps(result),flush=True)
if __name__=='__main__':main()
