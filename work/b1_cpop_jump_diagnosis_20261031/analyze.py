"""Read-only decomposition of the frozen v2 experiment; no fits or selection."""
import hashlib
import json
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
SOURCE = ROOT / 'work/b1_cpop_jump_v2_20261031'

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def read(p):
    return json.loads(p.read_text(encoding='utf-8'))

def longest(mask):
    best = run = 0
    for value in mask:
        run = run + 1 if value else 0
        best = max(best, run)
    return best

def durations(mask):
    return (int(np.sum(mask))*60, longest(mask)*60)

def main():
    paths = [SOURCE/p for p in ['facts/test.json', 'evaluator/test.json',
        'outputs/test_curves.json', 'outputs/test_metrics.json',
        'validation_freeze.json', 'candidate.py', 'adoption_decision.json']]
    paths += [p for p in (ROOT/'B1算法').rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    before = {p.relative_to(ROOT).as_posix(): sha(p) for p in paths}
    facts = {r['task']['task_id']: r for r in read(SOURCE/'facts/test.json')}
    truths = {r['task_id']: r for r in read(SOURCE/'evaluator/test.json')}
    curves = read(SOURCE/'outputs/test_curves.json')
    metrics = {(r['task_id'],r['method']): r for r in read(SOURCE/'outputs/test_metrics.json')}
    checks = 0
    pair_rows, null_rows, examples = [], [], []
    for case in curves:
        tid = case['task_id']; f = facts[tid]; t = truths[tid]
        starts = np.asarray(f['starts'])
        use = (starts >= 0) & (starts < 30)
        tau = .1*f['task']['request_kw']
        true = np.asarray(t['true_reduction_kw'])[use]
        raw = (np.asarray(f['reference_kw'])-np.asarray(f['power_kw']))[use]
        truth_mask = true >= tau
        actual = durations(truth_mask)
        predictions = {}
        for method in ['cpop', 'jump_1p0', 'labs']:
            pred = np.asarray(case['results'][method]['prediction'])[use]
            mask = pred >= tau; d = durations(mask)
            saved = metrics[tid, method]
            assert d == (saved['features']['cumulative_response_seconds'],
                         saved['features']['longest_continuous_response_seconds'])
            assert actual == (saved['true_features']['cumulative_response_seconds'],
                              saved['true_features']['longest_continuous_response_seconds'])
            assert int(np.sum(mask & ~truth_mask)) == saved['fp_minutes']
            assert int(np.sum(~mask & truth_mask)) == saved['fn_minutes']
            assert .5*sum(abs(a-b) for a,b in zip(d,actual)) == saved['primary_seconds']
            checks += 5
            predictions[method] = (pred, mask, d, saved)
        a, am, ad, ar = predictions['cpop']
        b, bm, bd, br = predictions['jump_1p0']
        changed = am != bm
        distances = np.minimum(abs(a[changed]-tau), abs(b[changed]-tau))
        pair_rows.append(dict(task_id=tid, kind=f['kind'], condition=t['condition'],
            changed_bins=int(changed.sum()), changed_distances_kw=distances.tolist(),
            cumulative_changed=ad[0]!=bd[0], longest_changed=ad[1]!=bd[1],
            cpop_primary=ar['primary_seconds'], v2_primary=br['primary_seconds'],
            cpop_cumulative=ar['cumulative_error_seconds'], v2_cumulative=br['cumulative_error_seconds'],
            cpop_longest=ar['longest_error_seconds'], v2_longest=br['longest_error_seconds'],
            cpop_task_curve_mse=ar['task_curve_mse_kw2'], v2_task_curve_mse=br['task_curve_mse_kw2']))
        if changed.any():
            examples.append(dict(task_id=tid, kind=f['kind'], condition=t['condition'],
                changed_minutes=starts[use][changed].tolist(),
                cpop_changed_kw=a[changed].tolist(), v2_changed_kw=b[changed].tolist(),
                true_changed_kw=true[changed].tolist(), true_duration=actual,
                cpop_duration=ad, v2_duration=bd,
                primary_delta=br['primary_seconds']-ar['primary_seconds']))
        if f['kind'] == 'null':
            indices = np.asarray(t['injected_indices'], dtype=int)
            adds = np.asarray(t['injected_residual_additions_kw'])
            positive_minutes = starts[indices[adds > 0]].tolist()
            fitted_minutes = {m:starts[use][predictions[m][1]].tolist() for m in predictions}
            null_rows.append(dict(task_id=tid, condition=t['condition'],
                positive_spike_minutes=positive_minutes, raw_positive_minutes=starts[use][raw>=tau].tolist(),
                fitted_positive_minutes=fitted_minutes,
                cpop_duration=ad, v2_duration=bd,
                cpop_matches_raw=bool(np.array_equal(am,raw>=tau)),
                v2_matches_raw=bool(np.array_equal(bm,raw>=tau)),
                cpop_positive=bool(am.any()), v2_positive=bool(bm.any()),
                positive_spike=bool(len(positive_minutes))))
    summaries = []
    for condition in ['all','gaussian','gaussian_plus_spikes']:
        rr = [r for r in pair_rows if condition=='all' or r['condition']==condition]
        ds = np.array([d for r in rr for d in r['changed_distances_kw']])
        s = dict(condition=condition, n=len(rr),
            identical_threshold_mask=sum(r['changed_bins']==0 for r in rr),
            changed_bins=sum(r['changed_bins'] for r in rr),
            cumulative_changed=sum(r['cumulative_changed'] for r in rr),
            longest_changed=sum(r['longest_changed'] for r in rr),
            improved_primary=sum(r['v2_primary']<r['cpop_primary'] for r in rr),
            worsened_primary=sum(r['v2_primary']>r['cpop_primary'] for r in rr),
            changed_bin_nearest_fit_distance_within_025kw=int(np.sum(ds<=.025)),
            changed_bin_nearest_fit_distance_within_05kw=int(np.sum(ds<=.05)),
            changed_bin_distance_median_kw=float(np.median(ds)))
        for method in ['cpop','v2']:
            for value in ['primary','cumulative','longest']:
                s[method+'_'+value+'_mae_seconds']=float(np.mean([r[method+'_'+value] for r in rr]))
            s[method+'_task_curve_pooled_rmse_kw']=float(np.sqrt(np.mean([r[method+'_task_curve_mse'] for r in rr])))
        summaries.append(s)
    null_summary=[]
    for condition in ['gaussian','gaussian_plus_spikes']:
        rr=[r for r in null_rows if r['condition']==condition]
        null_summary.append(dict(condition=condition,n=len(rr),
            original_positive=sum(r['cpop_positive'] for r in rr),v2_positive=sum(r['v2_positive'] for r in rr),
            positive_spike_count=sum(r['positive_spike'] for r in rr),
            exactly_same_cp_v2_positive_masks=sum(r['fitted_positive_minutes']['cpop']==r['fitted_positive_minutes']['jump_1p0'] for r in rr),
            cp_mask_equals_raw=sum(r['cpop_matches_raw'] for r in rr),v2_mask_equals_raw=sum(r['v2_matches_raw'] for r in rr),
            cp_positive_iff_positive_injected_spike=all(r['cpop_positive']==r['positive_spike'] for r in rr),
            cp_positive_minutes_equal_positive_injected_spikes=all(r['fitted_positive_minutes']['cpop']==sorted(r['positive_spike_minutes']) for r in rr),
            v2_positive_minutes_equal_positive_injected_spikes=all(r['fitted_positive_minutes']['jump_1p0']==sorted(r['positive_spike_minutes']) for r in rr)))
    kind_summary=[]
    for kind in sorted(set(r['kind'] for r in pair_rows)):
        rr=[r for r in pair_rows if r['kind']==kind]
        kind_summary.append(dict(kind=kind,n=len(rr),primary_total_delta_seconds=sum(r['v2_primary']-r['cpop_primary'] for r in rr)))
    after = {p.relative_to(ROOT).as_posix(): sha(p) for p in paths}
    assert before == after
    result=dict(scope='Frozen already-seen test, descriptive decomposition only; no new fit, selection or independent performance claim',
        summaries=summaries,null_summary=null_summary,kind_primary_deltas=kind_summary,
        largest_worsenings=sorted(examples,key=lambda r:-r['primary_delta'])[:5],
        largest_improvements=sorted(examples,key=lambda r:r['primary_delta'])[:3],
        checks=checks,scientific_sources_unchanged=True,input_sha256=before)
    for name,value in [('diagnosis.json',result),('paired_cases.json',pair_rows),('null_cases.json',null_rows),('changed_cases.json',examples)]:
        with (HERE/name).open('x',encoding='utf-8') as h:
            json.dump(value,h,ensure_ascii=False,allow_nan=False,indent=2)
    print(json.dumps({k:result[k] for k in ['summaries','null_summary','kind_primary_deltas','largest_worsenings','checks','scientific_sources_unchanged']},ensure_ascii=False))

if __name__=='__main__':
    main()
