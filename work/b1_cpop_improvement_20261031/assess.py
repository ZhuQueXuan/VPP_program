"""Frozen adoption checks, with all failures and genuine short actions retained."""
from common import *
def main():
    f=read('validation_freeze.json');method=f['selected_method']
    for p,h in f['source_sha256'].items():assert sha(ROOT/p)==h
    summary=read('outputs/test_summary.json');rows=read('outputs/test_metrics.json')
    def group(m,condition,kind='all'):
        r=[r for r in summary if (r['method'],r['condition'],r['kind'])==(m,condition,kind)]
        assert len(r)==1;return r[0]
    c0=group('cpop','gaussian');c1=group('cpop','gaussian_plus_spikes')
    m0=group(method,'gaussian');m1=group(method,'gaussian_plus_spikes')
    gates={'all_test_outputs_available':all(r['status']=='ok' for r in rows),
        'spike_primary_at_least10percent_better':m1['primary_seconds']<=.9*c1['primary_seconds'],
        'gaussian_primary_noninferiority_5s':m0['primary_seconds']<=c0['primary_seconds']+5,
        'spike_curve_RMSE_not_worse':m1['curve_rmse_kw']<=c1['curve_rmse_kw']}
    for kind in ['one_bin_response','one_bin_gap']:
        a,b=group(method,'gaussian',kind),group('cpop','gaussian',kind)
        gates[kind+'_primary_noninferiority_15s']=a['primary_seconds']<=b['primary_seconds']+15
        gates[kind+'_whole_misses_no_more_than_original_plus_one']=a['whole_miss']<=b['whole_miss']+1
    for condition in ['gaussian','gaussian_plus_spikes']:
        gates[condition+'_null_false_no_more_than_original_plus_one']=group(method,condition,'null')['null_false_positive']<=group('cpop',condition,'null')['null_false_positive']+1
    seed_rows=[]
    for seed in read('protocol.json')['simulation']['test']['seeds']:
        d={'seed':seed}
        for condition in ['gaussian','gaussian_plus_spikes']:
            d[condition]={m:float(np.mean([r['primary_seconds'] for r in rows if r['seed']==seed and r['condition']==condition and r['method']==m])) for m in ['cpop',method,'labs']}
        seed_rows.append(d)
    eta={}
    for r in rows:eta.setdefault(r['task_id'],[]).append(r['raw_eta'])
    assert len(eta)==480 and all(len(v)==3 and len(set(v))==1 for v in eta.values())
    decision={'status':'completed_candidate_not_adopted' if not all(gates.values()) else 'candidate_passed_limited_gates',
       'selected_candidate':method,'selected_kappa':f['selected_kappa'],'adopt':all(gates.values()),
       'gates':gates,'primary_definition':'Mean cumulative and longest threshold-duration absolute error, seconds',
       'test_conditions':{condition:{m:group(m,condition) for m in ['cpop',method,'labs']} for condition in ['all','gaussian','gaussian_plus_spikes']},
       'genuine_short_safeguards':{kind:{m:group(m,'gaussian',kind) for m in ['cpop',method,'labs']} for kind in ['one_bin_response','one_bin_gap']},
       'seed_results':seed_rows,'raw_eta_all480_equal_all3':True,
       'recommendation':'Do not adopt isolated-point weighting v1 as default. Keep original CPOP as the foundation and comparator, LABS comparator, candidate and negative results archived. Distinguishing sensor spikes from genuine short actions requires additional evidence or a different validated design.',
       'no_global_novelty_claim':'CPOP already supports heteroscedastic weighting. Added rule is a task adaptation, not a new changepoint solver or globally robust estimator.',
       'limits':['Known-reference minute simulation, not field or unknown-reference validation','240 independent base tasks; paired conditions are not480 independent tasks','Synthetic power-shape dynamics not real demand/debt/market evidence','Auxiliary real records have no latent clean truth','No5percent detector guarantee'],
       'input_sha256':{str((HERE/p).relative_to(ROOT)):sha(HERE/p) for p in ['protocol.json','validation_freeze.json','facts/test.json','evaluator/test.json','outputs/test_metrics.json','outputs/test_curves.json']}}
    write('adoption_decision.json',decision)
    fields=['method','condition','n','available','primary_seconds','cumulative_error_seconds','longest_error_seconds','curve_rmse_kw','whole_miss','null_false_positive','flagged_count']
    with (HERE/'comparison.csv').open('x',encoding='utf-8-sig',newline='') as h:
        w=csv.DictWriter(h,fieldnames=fields);w.writeheader();w.writerows({k:r.get(k) for k in fields} for r in summary if r['kind']=='all')
    print(json.dumps({'adopt':decision['adopt'],'gates':gates,'test_primary':{c:{m:group(m,c)['primary_seconds'] for m in ['cpop',method,'labs']} for c in ['gaussian','gaussian_plus_spikes']}},ensure_ascii=False))
if __name__=='__main__':main()
