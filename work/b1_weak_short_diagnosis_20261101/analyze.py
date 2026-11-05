"""Read-only trace of saved weak-short misses; no refit or candidate changes."""
import json,hashlib
from pathlib import Path
from collections import Counter,defaultdict
import numpy as np

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];SOURCE=ROOT/'work/b1_known_functional_20261101'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def native(v):
    if isinstance(v,np.ndarray):return v.tolist()
    if isinstance(v,np.generic):return v.item()
    if isinstance(v,dict):return {k:native(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)):return [native(x) for x in v]
    return v
def write(name,v):
    with (HERE/name).open('x',encoding='utf-8') as f:json.dump(native(v),f,ensure_ascii=False,indent=2,allow_nan=False)
def runs(mask,s,dt):
    ix=np.diff(np.r_[False,mask,False].astype(int));return [[float(s[a]),float(s[b-1]+dt)] for a,b in zip(np.flatnonzero(ix==1),np.flatnonzero(ix==-1))]

def main():
    files=[p for p in (ROOT/'B1算法').rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    receipt=read(SOURCE/'completion_receipt.json')
    files += [SOURCE/p for p in receipt['result_sha256']]
    files += [SOURCE/p for p in ['candidate.py','model.py','evaluate.py','physical_event_model.json','cumulative_leaves63.json','longest_leaves63.json']]
    protected={str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in files}
    for p,h in receipt['result_sha256'].items():assert sha(SOURCE/p)==h,p
    cases=read(SOURCE/'stress_test/facts.json');curves={r['task_id']:r['results'] for r in read(SOURCE/'stress_test/curves.json')};metrics={(r['task_id'],r['method']):r for r in read(SOURCE/'stress_test/metrics.json')}
    truth={};recipe={}
    for panel in ['minute','10s']:
        for name in ['truth.json','mixed_truth.json']:truth.update({r['task_id']:r for r in read(SOURCE/'stress_test'/panel/name)})
        recipe.update({r['task_id']:r for r in read(SOURCE/'stress_test'/panel/'generation_recipe.json')})
    threshold=read(SOURCE/'selected.json')['config']['event_threshold'];rows=[]
    for c in cases:
        tid=c['task_id'];r=metrics[tid,'candidate']
        if not r['short_n']:continue
        s=np.asarray(c['starts_s']);dt=c['ends_s'][0]-s[0];task=(s>=0)&(s<1800);clean=np.asarray(truth[tid]['true_reduction_kw']);tm=(clean>=.15)&task;y=np.asarray(c['reference_kw'])-np.asarray(c['power_kw']);f=curves[tid];cp=np.asarray(f['cpop']['prediction']);old=np.asarray(f['retained']['prediction']);cm=(cp>=.15)&task;om=(old>=.15)&task
        cp_hit=bool(np.any(cm&tm));old_hit=bool(np.any(om&tm));accepted=r['event_score']>=threshold
        new_hit=bool(accepted and r['positive_prediction'] and old_hit)
        assert (not cp_hit)==metrics[tid,'cpop']['short_local_miss']
        assert (not old_hit)==metrics[tid,'retained']['short_local_miss']
        assert (not new_hit)==r['short_local_miss']
        cp_runs=runs(cm,s,dt);overlap_runs=[v for v in cp_runs if any((s[tm]>=v[0])&(s[tm]<v[1]))]
        native_knots=int(f['cpop']['native_knots'])
        rows.append(dict(task_id=tid,base_task_id=c['base_task_id'],panel=c['panel'],kind=c['kind'],condition=c['condition'],seed=c['seed'],
            genuine_rectangular_short=c['kind'] in ['one_bin_response','one_minute_response','one_finebin_response'],
            effective_short_definition='True above0.15kW occupied duration>0 and<=60s, not physical action duration',
            effective_seconds=r['true_cumulative_seconds'],physical_above0p04_seconds=float(sum((clean>.04)&task)*dt),half_peak_seconds=float(sum((clean>=.5*max(clean[task]))&task)*dt),
            clean_peak=float(max(clean[task])),threshold_margin_kw=float(max(clean[task])-.15),
            cp_hit=cp_hit,retained_hit=old_hit,candidate_hit=new_hit,cp_positive_any=bool(cm.any()),retained_positive_any=bool(om.any()),new_positive_any=r['positive_prediction'],
            new_gate_accepted=accepted,event_score=r['event_score'],new_gate_threshold=threshold,
            lost_in_retained=bool(cp_hit and not old_hit),rescued_in_retained=bool(not cp_hit and old_hit),lost_in_new_gate=bool(old_hit and not new_hit),
            raw_above_threshold_at_true_location=bool(np.any(y[tm]>=.15)),raw_max_at_true_location=float(max(y[tm])),cp_max_at_true_location=float(max(cp[tm])),retained_max_at_true_location=float(max(old[tm])),
            cp_signal_at_true_location_above0p04=bool(np.any(cp[tm]>.04)),cp_peak_in_task=float(max(cp[task])),
            true_intervals=runs(tm,s,dt),cp_intervals=cp_runs,retained_intervals=runs(om,s,dt),cp_overlapping_run_seconds=[b-a for a,b in overlap_runs],native_knots=native_knots,
            retained_decision=f['retained']['decision'],old_cumulative=metrics[tid,'retained']['predicted_cumulative_seconds'],new_cumulative=r['predicted_cumulative_seconds'],
            true_indices=np.flatnonzero(tm),trace_at_true_indices=dict(time_s=s[tm],clean=clean[tm],observed=y[tm],cpop=cp[tm],retained=old[tm])))
    def tally(rr):
        return dict(records=len(rr),base_trajectories=len({r['base_task_id'] for r in rr}),cp_misses=sum(not r['cp_hit'] for r in rr),retained_misses=sum(not r['retained_hit'] for r in rr),new_misses=sum(not r['candidate_hit'] for r in rr),
            old_extra_losses=sum(r['lost_in_retained'] for r in rr),old_rescues=sum(r['rescued_in_retained'] for r in rr),new_gate_losses=sum(r['lost_in_new_gate'] for r in rr),new_gate_rejections=sum(not r['new_gate_accepted'] for r in rr),
            whole_no_positive=sum(not r['new_positive_any'] for r in rr),wrong_location_positive=sum(not r['candidate_hit'] and r['new_positive_any'] for r in rr))
    cp_miss=[r for r in rows if not r['cp_hit']];failed=[r for r in rows if not r['candidate_hit']];extra=[r for r in rows if r['lost_in_retained']]
    summary=dict(all=tally(rows),failed=tally(failed),by_kind={k:tally([r for r in rows if r['kind']==k]) for k in sorted({r['kind'] for r in rows})},
        by_condition={k:tally([r for r in rows if r['condition']==k]) for k in sorted({r['condition'] for r in rows})},
        cpop_miss_observation_split={str(k):tally([r for r in cp_miss if r['raw_above_threshold_at_true_location']==k]) for k in [True,False]},
        cpop_miss_signal_remaining={str(k):tally([r for r in cp_miss if r['cp_signal_at_true_location_above0p04']==k]) for k in [True,False]},
        new_gate_rejections_among_failed=sum(not r['new_gate_accepted'] for r in failed),
        cpop_miss_threshold_margins=dict(Counter(round(r['threshold_margin_kw'],6) for r in cp_miss)),
        no_finebin_positive_truth_in_stress_subset=not any(r['kind']=='one_finebin_response' for r in rows),
        physical_short_base_failures=sorted({r['base_task_id'] for r in failed if r['genuine_rectangular_short']}),
        duration_only_new_estimator_does_not_change_location_mask=True)
    # Show the peak assignment across shapes to diagnose test coverage only.
    coverage={}
    for c in cases:
        if c['condition']!='gaussian':continue
        s=np.asarray(c['starts_s']);use=(s>=0)&(s<1800);peak=float(max(np.asarray(truth[c['task_id']]['true_reduction_kw'])[use]));key=c['panel']+'/'+c['kind']
        coverage.setdefault(key,[]).append(round(peak,6))
    coverage={k:dict(Counter(v)) for k,v in coverage.items()}
    write('trace.json',rows);write('additional_retained_losses.json',extra);write('diagnosis.json',summary);write('shape_amplitude_coverage.json',coverage)
    for p,h in protected.items():assert sha(ROOT/p)==h,p
    write('protected_sha256.json',protected)
    print(json.dumps(native(summary),ensure_ascii=False),flush=True)

if __name__=='__main__':main()
