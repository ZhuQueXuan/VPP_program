"""Confirm the native extraction tradeoff on fresh 10 s waveform families.

Before generation: only admit CPOP as a demo candidate within the known-
reference, high-signal family if both duration MAEs improve by at least 5%,
with all 48 outputs and no additional split errors. Near-threshold cases are
a separate stress family. Nothing here decides a new field default.
"""
from statistics import mean

import evaluate as ev
from b1_algorithm.process.api import prepare, cases_for, complete
from b1_algorithm.process._cpop import fit_cases


def main():
    rng = ev.np.random.default_rng(90415001)
    rel = ev.np.arange(-900, 2700, 10)
    rows, prepared, cases = [], [], []
    for i in range(96):
        strong = i < 48
        split = i % 3 == 2
        n = int(rng.integers(8, 150)) if i % 3 else 0
        gap = 5 if split else 0
        onset = int(rng.integers(0, 181 - n - gap))
        a = n // 2 if split else n
        effect = ev.np.zeros(360)
        amplitude = float(rng.uniform(.9, 1.5)) if strong else float(rng.choice([.12, .18, .22, .3]))
        effect[90 + onset:90 + onset + a] = amplitude
        effect[90 + onset + a + gap:90 + onset + n + gap] = amplitude
        ref = 3 + (.12 if i % 2 else 0.) * ev.np.sin(rel / 480)
        noise = .05 if strong else .075
        task = dict(task_id=f'ev-process-confirm-{i}', user_id=f'new-user-{i}', meter_id=f'meter-{i}',
                    start_min=0., end_min=30., request_kw=1.5, notice_min=-15., task_pre_treatment=True)
        data = prepare(rel / 60, (rel+10) / 60, ref - effect + rng.normal(0, noise, 360),
                       ref, task, noise)
        prepared.append(data)
        cases.extend(cases_for(data, base=i*10, include_cv=False))
        rows.append(dict(family='strong' if strong else 'near_threshold',
                         cumulative=10*n if amplitude >= .15 else 0,
                         longest=10*max(a,n-a) if amplitude >= .15 else 0,
                         split=split and amplitude >= .15))
    runtime = ev.HERE.parent / 'b1_mainline_20261029/runtime'
    native, backend = fit_cases(cases, dict(rscript_path=str(runtime/'R-4.6.1/app/bin/Rscript.exe'),
        r_library=str(runtime/'r_library'), artifact_dir=str(ev.HERE/'native'/'process_confirmation'), timeout_seconds=180))
    assert backend['status'] == 'ok', backend
    for i, (data, row) in enumerate(zip(prepared, rows)):
        for method in ('cpop', 'effective_response_refined'):
            out = complete(data, native, base=i*10, policy=method, backend=backend)
            if out['status'] != 'ok':
                row[method] = dict(status=out['status'], reason=out['reason'])
                continue
            durations = out.get('duration_estimates') or out['features']['selected_curve']
            c, l = (durations[k] for k in ('cumulative_response_seconds','longest_continuous_response_seconds'))
            row[method] = dict(status='ok', cumulative=c, longest=l, split=c-l >= 20 - 1e-7)

    stats = {}
    for family in ('strong','near_threshold'):
        group = [r for r in rows if r['family'] == family]
        stats[family] = {}
        for method in ('cpop', 'effective_response_refined'):
            usable = [r for r in group if r[method]['status'] == 'ok']
            stats[family][method] = dict(n=len(usable), total=len(group),
                cumulative_mae=mean(abs(r[method]['cumulative']-r['cumulative']) for r in usable) if usable else None,
                longest_mae=mean(abs(r[method]['longest']-r['longest']) for r in usable) if usable else None,
                split_errors=sum(r[method]['split'] != r['split'] for r in usable) if usable else None)
    old, new = (stats['strong'][m] for m in ('effective_response_refined','cpop'))
    admitted = old['n'] == new['n'] == 48 and all(new[k] <= .95 * old[k]
        for k in ('cumulative_mae', 'longest_mae')) and new['split_errors'] <= old['split_errors']
    ev.save(ev.HERE/'process_confirmation.json', dict(seed=90415001, stats=stats, rows=rows,
        demo_candidate_for_strong_known_reference=admitted, source='new simulated reference-known task waveforms'))
    print(stats, flush=True)


if __name__ == '__main__':
    main()
