"""Predeclared all-case adoption gates; no test-based configuration selection."""
from common import *
def main():
    f=read('validation_freeze.json');m=f['selected_method']
    for p,h in f['source_sha256'].items():assert sha(ROOT/p)==h
    summary=read('outputs/test_summary.json');rows=read('outputs/test_metrics.json')
    def group(method,condition,kind='all'):
        rr=[r for r in summary if (r['method'],r['condition'],r['kind'])==(method,condition,kind)]
        assert len(rr)==1;return rr[0]
    gates={'all_outputs_available':all(r['status']=='ok' for r in rows),
       'primary_all_conditions_at_least10percent_better':group(m,'all')['primary_seconds']<=.9*group('cpop','all')['primary_seconds']}
    for condition in ['gaussian','gaussian_plus_spikes']:
        a,b=group(m,condition),group('cpop',condition)
        gates[condition+'_primary_noninferiority_5s']=a['primary_seconds']<=b['primary_seconds']+5
        gates[condition+'_curve_RMSE_not_over_original_times1_10']=a['curve_rmse_kw']<=1.1*b['curve_rmse_kw']
        gates[condition+'_null_false_not_over_original_plus1']=group(m,condition,'null')['null_false_positive']<=group('cpop',condition,'null')['null_false_positive']+1
        # Conservative interpretation of "short": preserve both brief weak
        # responses and the genuine one-bin safeguard, not only a chosen subset.
        for kind in ['one_bin_response','brief_weak']:
            gates[condition+'_'+kind+'_misses_not_over_original_plus1']=group(m,condition,kind)['whole_miss']<=group('cpop',condition,kind)['whole_miss']+1
    for kind in ['one_bin_response','one_bin_gap']:
        gates[kind+'_gaussian_primary_noninferiority_15s']=group(m,'gaussian',kind)['primary_seconds']<=group('cpop','gaussian',kind)['primary_seconds']+15
    seed=[]
    for value in read('protocol.json')['simulation']['test']['seeds']:
        d={'seed':value}
        for condition in ['gaussian','gaussian_plus_spikes']:
            d[condition]={method:float(np.mean([r['primary_seconds'] for r in rows if r['seed']==value and r['condition']==condition and r['method']==method])) for method in ['cpop',m,'labs']}
        seed.append(d)
    eta={}
    for r in rows:eta.setdefault(r['task_id'],[]).append(r['raw_eta'])
    assert len(eta)==480 and all(len(v)==3 and len(set(v))==1 for v in eta.values())
    d={'status':'complete_not_adopted' if not all(gates.values()) else 'passed_limited_simulation_gates',
       'adopt':all(gates.values()),'selected_method':m,'ratio_selected_only_on_validation':f['selected_ratio'],
       'adoption_gates':gates,'main_summary':{c:{method:group(method,c) for method in ['cpop',m,'labs']} for c in ['all','gaussian','gaussian_plus_spikes']},
       'genuine_single_bin':{condition:{method:group(method,condition,'one_bin_response') for method in ['cpop',m,'labs']} for condition in ['gaussian','gaussian_plus_spikes']},
       'brief_weak':{condition:{method:group(method,condition,'brief_weak') for method in ['cpop',m,'labs']} for condition in ['gaussian','gaussian_plus_spikes']},
       'null':{condition:{method:group(method,condition,'null') for method in ['cpop',m,'labs']} for condition in ['gaussian','gaussian_plus_spikes']},
       'seed_primary':seed,'all480_raw_eta_same_across3':True,
       'recommendation':'Keep original CPOP foundation and LABS control. Candidate v2 retained as a tested structural prototype; adopt only if all frozen benefit/safety gates hold. No global default switch.',
       'scope':['240 independent new simulated base tasks,480 paired inputs','Known reference, not field/unknown-reference proof',
          'No dropping/weighting of points; adding reset freedom does not identify sensor outliers','Finite boundary dictionary optimum, not all-position GRACE or latent physical timing',
          'No5percent calibrated detection claim;24null tasks per condition are insufficient for certification'],
       'input_sha256':{(HERE/p).relative_to(ROOT).as_posix():sha(HERE/p) for p in ['protocol.json','validation_freeze.json','facts/test.json','evaluator/test.json','outputs/test_curves.json','outputs/test_metrics.json']}}
    write('adoption_decision.json',d)
    fields=['method','condition','n','available','primary_seconds','cumulative_error_seconds','longest_error_seconds','curve_rmse_kw','whole_miss','null_false_positive','jump_count','seconds']
    with (HERE/'comparison.csv').open('x',encoding='utf-8-sig',newline='') as h:
        w=csv.DictWriter(h,fieldnames=fields);w.writeheader();w.writerows({k:r.get(k) for k in fields} for r in summary if r['kind']=='all')
    print(json.dumps({'adopt':d['adopt'],'failed_gates':[k for k,v in gates.items() if not v],
       'primary':{method:group(method,'all')['primary_seconds'] for method in ['cpop',m,'labs']},
       'eta_identical':True},ensure_ascii=False))
if __name__=='__main__':main()
