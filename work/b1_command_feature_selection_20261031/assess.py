"""Evaluate the frozen candidate; never select a replacement on test results."""
from common import *
from collections import defaultdict
def main():
    freeze=read('validation_freeze.json')
    for p,h in freeze['source_sha256'].items():assert sha(HERE/p)==h
    rows=read('outputs/test_metrics.json');summary=read('outputs/test_summary.json')
    total={r['method']:r for r in summary if r['kind']=='all'}
    selected=freeze['selected_candidate'];candidate=total[selected];previous=total['ride_revised']
    checks={'candidate_all_test_outputs_available':candidate['unavailable']==0 and candidate['available']==192,
        'duration_primary_improvement_at_least_10percent':candidate['primary_seconds']<=.9*previous['primary_seconds'],
        'pooled_curve_rmse_did_not_increase':candidate['curve_rmse_kw']<=previous['curve_rmse_kw'],
        'null_false_tasks_no_more_than_previous_plus_one':candidate['null_false_positive']<=previous['null_false_positive']+1}
    seed_rows=[]
    for seed in read('protocol.json')['simulation']['test']['seeds']:
        block={}
        for m in total:
            rr=[r for r in rows if r['seed']==seed and r['method']==m];assert len(rr)==32
            assert all(r['status']=='ok' for r in rr)
            block[m]=float(np.mean([r['primary_seconds'] for r in rr]))
        seed_rows.append({'seed':seed,'primary_seconds':block})
    eta={}
    for r in rows:
        if r['status']=='ok':eta.setdefault(r['task_id'],[]).append(r['raw_eta'])
    assert len(eta)==192 and all(len(v)==7 and len(set(v))==1 for v in eta.values())
    result={'status':'complete_not_deployed','selected_before_test':selected,
       'candidate_passes_frozen_improvement_gate':all(checks.values()),'gate_checks':checks,
       'primary_metric':'Mean of cumulative and longest threshold-duration absolute error, seconds; not response-onset delay',
       'candidate_primary_improvement_vs_revised_percent':100*(1-candidate['primary_seconds']/previous['primary_seconds']),
       'test_all_methods':total,'seed_primary':seed_rows,
       'candidate_beats_revised_seed_count':sum(r['primary_seconds'][selected]<r['primary_seconds']['ride_revised'] for r in seed_rows),
       'CP_beats_revised_seed_count':sum(r['primary_seconds']['cpop']<r['primary_seconds']['ride_revised'] for r in seed_rows),
       'raw_eta_equal_all_methods_all192':True,
       'recommendation':'Do not adopt LABS/GLS as a whole-block replacement. Existing direct command-tracking features remain available; CPOP is the strongest duration/curve comparator in this known-reference simulation, not a claimed project innovation. No automatic production replacement.',
       'scope_limits':['Six new simulated seeds, not field or unknown-reference proof','Different features have different winners; CPOP onset/target/recovery timings are not uniformly best','ODE bounded shape only, no verified energy-debt or ex-ante-demand mechanism','Old RIDE configured rebound cap1q differs from revised headroom policy; independent common-cap analysis retained'],
       'source_sha256':{p:sha(HERE/p) for p in ['protocol.json','validation_freeze.json','facts/test.json','evaluator/test.json','outputs/test_metrics.json','outputs/test_curves.json']}}
    write('selection_decision.json',result)
    fields=['method','total','available','primary_seconds','cumulative_error_seconds','longest_error_seconds','curve_rmse_kw','whole_miss','null_false_positive','onset_error_seconds','onset_error_seconds_n','onset_status_disagreement','target_error_seconds','target_error_seconds_n','target_status_disagreement','seconds']
    with (HERE/'comparison.csv').open('x',encoding='utf-8-sig',newline='') as h:
        w=csv.DictWriter(h,fieldnames=fields);w.writeheader();w.writerows({k:r.get(k) for k in fields} for r in total.values())
    print(json.dumps({'candidate':selected,'gate':checks,'improvement_percent':result['candidate_primary_improvement_vs_revised_percent'],
          'candidate_seed_wins':result['candidate_beats_revised_seed_count'],'CP_seed_wins':result['CP_beats_revised_seed_count'],
          'all_primary_seconds':{m:r['primary_seconds'] for m,r in total.items()}},ensure_ascii=False))
if __name__=='__main__':main()
