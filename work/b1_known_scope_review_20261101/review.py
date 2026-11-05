"""Known-reference performance review; no forecasting, model training or tuning."""
from pathlib import Path
import sys,json,hashlib
import numpy as np
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'B1算法'))
from b1_algorithm.api import analyze_events,_default_runtime_config
from b1_algorithm.contracts import provided_reference

def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def native(x):
    if isinstance(x,np.generic):return x.item()
    if isinstance(x,np.ndarray):return x.tolist()
    if isinstance(x,dict):return {k:native(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [native(v) for v in x]
    return x
def write(name,value):
    with (HERE/name).open('x',encoding='utf-8') as f:json.dump(native(value),f,ensure_ascii=False,allow_nan=False,indent=2)
def balanced(rows,method,key,seed=None):
    rr=[r for r in rows if r['method']==method and (seed is None or r['seed']==seed)]
    return float(np.mean([np.mean([np.mean([r[key] for r in rr if r['panel']==p and r['condition']==c]) for c in sorted({r['condition'] for r in rr if r['panel']==p})]) for p in sorted({r['panel'] for r in rr})]))

def main():
    release=ROOT/'work/b1_duration_release_20261101';sources=[release/'test/metrics.json',ROOT/'work/b1_false_unknown_20261101/test/metrics.json',ROOT/'work/b1_false_unknown_v2_20261101/test/metrics.json'];summaries=[];all_rows=[]
    for path in sources:
        rr=read(path);rr=[r for r in rr if r.get('regime','known')=='known' and r['method'] in ['cpop','labs','duration_fusion','retained']]
        for r in rr:
            if r['method']=='retained':r=dict(r,method='duration_fusion')
            all_rows.append(dict(r,source=path.parent.parent.name))
        local=[r for r in all_rows if r['source']==path.parent.parent.name];seeds=sorted({r['seed'] for r in local})
        metrics={m:{k:balanced(local,m,k) for k in ['primary_seconds','cumulative_error_seconds','longest_error_seconds']} for m in ['cpop','duration_fusion','labs']}
        summaries.append(dict(source=path.relative_to(ROOT).as_posix(),inputs=sum(r['method']=='cpop' for r in local),seed_blocks=len(seeds),metrics=metrics,
            improvement_percent=100*(1-metrics['duration_fusion']['primary_seconds']/metrics['cpop']['primary_seconds']),
            improved_seed_blocks=sum(balanced(local,'duration_fusion','primary_seconds',seed)<balanced(local,'cpop','primary_seconds',seed) for seed in seeds),
            counts={m:{k:int(sum(r[k] for r in local if r['method']==m)) for k in ['whole_miss','null_false_positive','short_local_miss']} for m in metrics}))
    write('existing_independent_test_review.json',dict(cohorts=summaries,total_known_inputs=sum(r['inputs'] for r in summaries),
        new_data_generated=False,new_test_claim=False,model_weights_changed=False,known_reference_scope=True))
    # The current production route changes only two duration fields. Replay real
    # public APIs to ensure later reference research has not altered that route.
    selected=[]
    for panel in ['minute','10s']:
        cases=read(release/'test'/panel/'facts.json');kinds=['smooth_weak','interrupted','one_bin_response' if panel=='minute' else 'one_finebin_response','one_bin_gap' if panel=='minute' else 'one_finebin_gap']
        selected += [next(c for c in cases if c['kind']==kind) for kind in kinds]
    expected={r['task_id']:r for r in read(release/'test/curves.json')};records=[]
    for i,c in enumerate(selected):
        task=dict(task_id=c['task_id'],user_id='known-review-'+str(i),meter_id='known-meter-'+str(i),start_min=0.,end_min=30.,notice_min=-15.,request_kw=1.5)
        s=np.array(c['starts_s'])/60;e=np.array(c['ends_s'])/60
        records.append(dict(task=task,starts_min=s,ends_min=e,power_kw=c['power_kw'],reference=provided_reference(task,s,e,c['reference_kw'],available_at_min=-15.),noise_sigma_kw=.05))
    config=_default_runtime_config();config['artifact_dir']=str(HERE/'native/current')
    current=analyze_events(records,process_config=config,process_method='duration_fusion');config['artifact_dir']=str(HERE/'native/cpop')
    original=analyze_events(records,process_config=config,process_method='cpop')
    comparisons=0
    for c,a,b in zip(selected,current,original):
        assert a['status']==b['status']=='ok'
        assert np.max(abs(np.asarray(a['process']['duration_state_curve_kw'])-expected[c['task_id']]['results']['duration_fusion']['prediction']))<1e-12
        for key,value in b['process']['features']['selected_curve'].items():
            if key not in ['cumulative_response_seconds','longest_continuous_response_seconds']:assert a['process']['features']['selected_curve'][key]==value;comparisons+=1
        assert a['outcome']['value']==b['outcome']['value']
    write('public_replay.json',dict(passed=True,known_current_events=len(current),original_CPOP_events=len(original),unchanged_other_feature_comparisons=comparisons,
        matches_frozen_adopted_known_method=True,reference_predictor_called=False,reference_error_tracking_called=False))
    write('scope_decision.json',dict(main_research='Known-observation feature extraction; do not make reference prediction prerequisite for all features.',
        known_reference_method='duration_fusion',reference_tracking='Retained separate research branch, not used for this review.',
        actual_improvements=['cumulative_response_seconds','longest_continuous_response_seconds'],
        other_features='Existing CPOP structural-curve onset/target/recovery and raw energy; no claimed new gains.',
        main_remaining_issue='Threshold-near weak signals and false positives; original task-positive flag deliberately retained.',
        field_or_all_features_completed=False))
    print(json.dumps(native(summaries)),flush=True)
if __name__=='__main__':main()
