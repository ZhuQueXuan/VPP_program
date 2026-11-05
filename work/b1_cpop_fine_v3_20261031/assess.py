from common import *

def main():
    frozen=read('validation_freeze.json');m=frozen['method'];rows=read('outputs/test_metrics.json');ss=read('outputs/test_summary.json')
    def group(method,condition,kind='all'):
        rr=[r for r in ss if (r['method'],r['condition'],r['kind'])==(method,condition,kind)];assert len(rr)==1;return rr[0]
    a,b=group(m,'all'),group('cpop','all')
    gates=dict(all_outputs_available=all(r['status']=='ok' for r in rows),primary_at_least10percent_improvement=a['primary_seconds']<=.9*b['primary_seconds'],
        gaussian_noninferiority_5s=group(m,'gaussian')['primary_seconds']<=group('cpop','gaussian')['primary_seconds']+5.)
    for c in read('protocol.json')['simulation']['conditions']:
        gates[c+'_null_no_more_false_positive']=group(m,c,'null')['null_false_positive']<=group('cpop',c,'null')['null_false_positive']
        for kind in ['one_minute_response','one_finebin_response']:
            gates[c+'_'+kind+'_no_extra_miss']=group(m,c,kind)['whole_miss']<=group('cpop',c,kind)['whole_miss']
        for kind in ['one_minute_gap','one_finebin_gap']:
            gates[c+'_'+kind+'_duration_noninferiority10s']=group(m,c,kind)['primary_seconds']<=group('cpop',c,kind)['primary_seconds']+10.
    eta={}
    for r in rows:eta.setdefault(r['task_id'],[]).append(r['raw_eta'])
    assert all(len(v)==3 and len(set(v))==1 for v in eta.values())
    seeds=[]
    for seed in read('protocol.json')['simulation']['test']['seeds']:
        d=dict(seed=seed)
        for method in ['cpop',m,'labs']:d[method]=float(np.mean([r['primary_seconds'] for r in rows if r['seed']==seed and r['method']==method]))
        seeds.append(d)
    result=dict(adopt=all(gates.values()),status='limited_gates_passed' if all(gates.values()) else 'not_adopted',
        gates=gates,failed_gates=[k for k,v in gates.items() if not v],kappa=frozen['kappa'],
        primary={c:{method:group(method,c) for method in ['cpop',m,'labs']} for c in ['all']+read('protocol.json')['simulation']['conditions']},
        seed_primary=seeds,raw_eta_identical=True,
        limitation='Known-reference10s synthetic plus existing100ms real artificial noise stability; no real clean truth, counterfactual or5percent guarantee.',
        short_safeguards={kind:{c:{method:group(method,c,kind) for method in ['cpop',m,'labs']} for c in read('protocol.json')['simulation']['conditions']} for kind in ['one_minute_response','one_finebin_response','one_minute_gap','one_finebin_gap','null']})
    write('adoption_decision.json',result)
    print(json.dumps({'adopt':result['adopt'],'failed_gates':result['failed_gates'],'seed_primary':seeds,'primary':result['primary']},ensure_ascii=False),flush=True)
if __name__=='__main__':main()
