"""Independent scalar accounting and replay of existing four lost state values."""
import sys,json,hashlib
from pathlib import Path
from collections import Counter
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

cases=read(SOURCE/'stress_test/facts.json');curves=read(SOURCE/'stress_test/curves.json');truth={}
for panel in ['minute','10s']:
    for name in ['truth.json','mixed_truth.json']:
        for r in read(SOURCE/'stress_test'/panel/name):truth[r['task_id']]=r['true_reduction_kw']
metrics={(r['task_id'],r['method']):r for r in read(SOURCE/'stress_test/metrics.json')};record=read(HERE/'trace.json');saved={r['task_id']:r for r in record};counts=Counter();checks=0
for c,f in zip(cases,curves):
    step=c['ends_s'][0]-c['starts_s'][0];tid=c['task_id'];correct=[i for i,(s,v) in enumerate(zip(c['starts_s'],truth[tid])) if 0<=s<1800 and v>=.15]
    if not (0<len(correct)*step<=60.+1e-8):continue
    cp=any(f['results']['cpop']['prediction'][i]>=.15 for i in correct);old=any(f['results']['retained']['prediction'][i]>=.15 for i in correct);new=old and metrics[tid,'candidate']['event_score']>=.025 and metrics[tid,'candidate']['positive_prediction']
    assert [cp,old,new]==[saved[tid]['cp_hit'],saved[tid]['retained_hit'],saved[tid]['candidate_hit']]
    counts['short']+=1;counts['cp_miss']+=not cp;counts['old_miss']+=not old;counts['new_miss']+=not new;counts['new_gate_loss']+=old and not new;checks+=4
assert dict(counts)==dict(short=121,cp_miss=82,old_miss=86,new_miss=86,new_gate_loss=0)
sys.path.insert(0,str(ROOT/'B1算法'))
from b1_algorithm.process import _duration_fusion as DF
from scipy.special import expit
meta,models,_=DF._artifacts();slices=read(SOURCE/'stress_test/slices.json');X=np.load(SOURCE/'stress_test/state_X.npy',mmap_mode='r');details=[]
for c,sl,f in zip(cases,slices,curves):
    tid=c['task_id'];r=saved.get(tid)
    if not r or not r['lost_in_retained']:continue
    a,b=sl;xx=X[a:b,:42];indices=r['true_indices'];prob=expit(DF._tree_predict(models['state.json'],xx));quantile=DF._tree_predict(models['quantile.json'],xx)*.05
    for i in indices:
        assert prob[i]<meta['configuration']['threshold']
        assert abs(f['results']['retained']['prediction'][i]-min(quantile[i],.149999))<1e-10
        checks+=2
    assert min(r['cp_overlapping_run_seconds'])>60.
    details.append(dict(task_id=tid,cp_overlapping_run_seconds=r['cp_overlapping_run_seconds'],
        state_probability_at_true_indices=prob[indices],state_threshold=meta['configuration']['threshold'],
        q50_prediction_at_true_indices=quantile[indices],short_protection_did_not_apply=True))
coverage=read(HERE/'shape_amplitude_coverage.json')
fine_coverage={k:v for k,v in coverage.items() if k.startswith('10s/one_') and k.endswith('response')}
assert all(float(peak)<.15 for v in fine_coverage.values() for peak in v)
for p,h in read(HERE/'protected_sha256.json').items():assert sha(ROOT/p)==h,p
write('independent_checks.json',dict(scalar_counts=dict(counts),checks=checks,four_state_failures=details,
    oscillatory_physical_support_seconds_range=[min(r['physical_above0p04_seconds'] for r in record if r['kind']=='oscillatory'),max(r['physical_above0p04_seconds'] for r in record if r['kind']=='oscillatory')],
    fine_rectangular_response_peak_coverage=fine_coverage,
    all_protected_source_models_results_identical=True,no_fit_or_new_data_or_estimator_change=True))
print(json.dumps(native(dict(counts=dict(counts),four_state_failures=details,fine_coverage=fine_coverage)),ensure_ascii=False),flush=True)
