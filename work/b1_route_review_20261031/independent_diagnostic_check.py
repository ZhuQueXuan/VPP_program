"""Independent saved-output verification. No estimator import or fitting."""
from pathlib import Path
import csv, json, hashlib, math
from collections import Counter
import numpy as np

R = Path(__file__).resolve().parents[2]
O = Path(__file__).resolve().parent
S = R / 'work/b1_reliability_20261031/study/test'
hashes = {}
def read(p):
    hashes[p.relative_to(R).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    return json.loads(p.read_text(encoding='utf8'))
def yes(x):
    assert x in ('True','False')
    return x == 'True'
def close(x,y):
    assert math.isclose(float(x),float(y),rel_tol=1e-10,abs_tol=1e-8),(x,y)
def overlap(a,b,left,right):
    return np.maximum(0., np.minimum(b,right)-np.maximum(a,left))/(b-a)

summary = json.loads((O/'saved_process_diagnosis.json').read_text(encoding='utf8'))
csvrows = list(csv.DictReader((O/'saved_process_diagnosis.csv').open(encoding='utf8',newline='')))
csvmap = {x['task_id']:x for x in csvrows}
assert len(csvmap)==len(csvrows)==1024
recomputed=[]
witnesses=[]
max_error=0.
for seed in sorted({int(x['seed']) for x in csvrows}):
    ts=read(S/'evaluator'/f'{seed}_weak_truth.json')
    fs=read(R/'data/B1_reliability_v1_20261031/test'/f'{seed}_weak_facts.json')
    refs=read(S/'references'/f'{seed}_new.json')['references']
    vs=read(S/'events'/f'{seed}_weak_new_ride_revised.json')
    cs=read(S/'events'/f'{seed}_weak_new_cpop.json')
    assert len(ts)==len(fs)==len(refs)==len(vs)==len(cs)==128
    for t,f,ref,v,c in zip(ts,fs,refs,vs,cs):
        ident=t['task_id']
        assert ident==f['task']['task_id']==ref['task_id']==v['task']['task_id']==c['task']['task_id']
        z=csvmap[ident]
        assert t['weak_subtype']==z['subtype']
        start=np.asarray(f['starts_min'])-f['task']['start_min']
        end=np.asarray(f['ends_min'])-f['task']['start_min']
        assert np.all(end-start==1.)
        assert f['task']['end_min']-f['task']['start_min']==30.
        task=(start>=0)&(end<=30.)
        truth=np.asarray(t['true_reduction_kw'])
        original_true_duration=float(np.sum((truth[task]>=.15)*(end[task]-start[task]))*60)
        close(original_true_duration,t['cumulative_response_seconds'])
        positive=original_true_duration>0
        assert positive==t['threshold_positive']==yes(z['threshold_positive'])
        reference=np.asarray(ref['reference_kw'])
        residual=reference-np.asarray(f['power_kw'])
        sig=float(f['noise_sigma_kw'])
        ev=v['process']['selection_evidence']
        n=len(residual)
        assert n==ev['n_bins']==60
        best=ev['solver_records'][ev['selected_solver']]
        assert best['accepted'] and best['success']
        k={1:8,2:10}[best['structure']]
        bic=best['rss']/sig**2+k*math.log(n)
        null=float(residual@residual)/sig**2
        gate_bic=bic<null
        gate_amp=ev['parameters']['positive_ratio']>=.1
        detected=gate_bic and gate_amp
        assert detected==ev['detected']==yes(z['template_detected'])
        assert gate_bic==yes(z['gate_bic']) and gate_amp==yes(z['gate_amplitude'])
        close(bic-null,z['bic_minus_null'])
        vd=v['process']['features']['selected_curve']['cumulative_response_seconds']
        cd=c['process']['features']['selected_curve']['cumulative_response_seconds']
        close(vd,z['template_duration']);close(cd,z['cpop_duration'])
        miss=positive and vd==0
        cmiss=positive and cd==0
        assert miss==yes(z['template_miss']) and cmiss==yes(z['cpop_miss'])
        row=dict(subtype=t['weak_subtype'],positive=positive,miss=miss,cpop_miss=cmiss,
            amp_only=miss and gate_bic and not gate_amp,
            after_detection=miss and detected,witness=False,witness_miss_better_pass=False)
        if t['weak_subtype'] in ('brief3','brief6') and positive:
            # The evaluator parameters enter only this diagnostic calculation.
            # Direct rectangle overlap integrates the signal; no production
            # interval_components, template function, or optimizer is imported.
            fine=np.asarray(t['relative_fine_midpoints_min'])
            fine_active=(fine>=.25+1.5*t['latent']['delay_uniform']) & (fine<.25+1.5*t['latent']['delay_uniform']+t['weak_rectangle_minutes']) & (fine<30.)
            chosen_fine=fine[fine_active]
            left=float(chosen_fine[0]-1/12)
            right=float(chosen_fine[-1]+1/12)
            hold=right-left
            q=float(f['task']['request_kw'])
            amplitude=q*float(t['weak_amplitude_fraction'])
            debt_kwmin=float(np.sum(truth[task]*(end[task]-start[task])))
            rebound_minutes=debt_kwmin/1.8
            w=amplitude*overlap(start,end,left,right)-1.8*overlap(start,end,30.,30.+rebound_minutes)
            exact=float(np.max(np.abs(w-truth)));max_error=max(max_error,exact)
            assert exact<1e-10
            # M1: [delay,rise,hold,release,wait,rebound] and 2 amplitudes.
            times=np.array([left,0.,hold,0.,30.-right,rebound_minutes])
            profile=v['process']['analysis_profile']
            upper=np.array([30.,min(profile['template_ramp_max_min'],30.),30.,profile['template_release_max_min'],max(float(end[-1]),1.),profile['template_rebound_max_min']])
            assert np.all(times>=-1e-12) and np.all(times<=upper+1e-12)
            assert 0<=t['weak_amplitude_fraction']<=profile['template_level_max_ratio']
            headroom=max(0.,profile['max_charge_kw']-float(np.max(reference)))
            close(ev['rebound_max_ratio'],headroom/q)
            assert ev['rebound_bound_source']=='declared_max_minus_max_supplied_reference'
            assert profile['revised_rebound_bound_policy']=='declared_headroom'
            assert 1.8<=headroom+1e-10
            wrss=float(np.sum((w-residual)**2))
            wbic=wrss/sig**2+8*math.log(n)
            beats=wbic<bic-1e-8
            passes=wbic<null
            close(wbic-null,z['witness_bic_minus_null'])
            assert beats==yes(z['witness_beats_selected_bic'])
            assert passes==yes(z['witness_passes'])
            row['witness']=True
            row['witness_miss_better_pass']=miss and beats and passes
            witnesses.append(dict(task_id=ident,seed=seed,subtype=t['weak_subtype'],times_min=times.tolist(),upper_bounds_min=upper.tolist(),amplitude_ratio=t['weak_amplitude_fraction'],rebound_ratio=1.8/q,rebound_bound_ratio=headroom/q,exact_error=exact,witness_k=8,selected_k=k,witness_rss=wrss,selected_rss=best['rss'],witness_bic_minus_null=wbic-null,selected_bic_minus_null=bic-null,template_miss=miss,beats_selected=beats,passes_null=passes))
        recomputed.append(row)

positive=[x for x in recomputed if x['positive']]
def ag(rows):
    return dict(n=len(rows),template_miss=sum(x['miss'] for x in rows),cpop_miss=sum(x['cpop_miss'] for x in rows),amplitude_only=sum(x['amp_only'] for x in rows),after_detection=sum(x['after_detection'] for x in rows),witness_n=sum(x['witness'] for x in rows),missed_with_exact_witness_beats_selected_and_passes=sum(x['witness_miss_better_pass'] for x in rows))
overall=ag(positive)
assert overall==dict(n=690,template_miss=151,cpop_miss=38,amplitude_only=148,after_detection=3,witness_n=358,missed_with_exact_witness_beats_selected_and_passes=55)
for field,val in overall.items():
    mapping={'amplitude_only':'template_miss_amplitude_only','after_detection':'template_miss_after_detection'}
    assert summary['overall'][mapping.get(field,field)]==val
by={sub:ag([x for x in positive if x['subtype']==sub]) for sub in ('brief3','brief6','sustained')}
for sub,values in by.items():
    for field,val in values.items():
        mapping={'amplitude_only':'template_miss_amplitude_only','after_detection':'template_miss_after_detection'}
        assert summary['by_subtype'][sub][mapping.get(field,field)]==val
assert hashes=={p.replace('\\','/'):h for p,h in summary['input_sha256'].items()}
assert len(hashes)==40
assert all(hashlib.sha256((R/p).read_bytes()).hexdigest()==h for p,h in hashes.items())
samples=witnesses[:2]+witnesses[-2:]
result=dict(status='passed',checker='independent rectangle-overlap formula; no production imports, optimization, new facts or parameter selection',checker_note='Initial manifest assertion used slash-normalized keys against Windows backslash keys; normalized both sides and reran. No scientific count or numerical assertion changed.',source_files=len(hashes),source_hashes_match_parent_manifest=True,source_hashes_unchanged_after_read=True,csv_rows=len(csvrows),unique_task_ids=len(csvmap),overall=overall,by_subtype=by,witnesses_directly_integrated=len(witnesses),max_witness_curve_error=max_error,samples_first_two_last_two=samples,limitations=['Truth-derived legal witnesses are evaluator-only existence/objective comparisons, not usable initializations, estimator output, routing or new test performance.','55 shows a better feasible M1 solution exists under the same saved residual/sigma/BIC objective; it does not show how an observable algorithm can find it.','Witness legality checked against actual declared_headroom and time/amplitude bounds; no claim of unique physical identification.','This reuses already-seen test outputs and is not an independent performance test.'],input_sha256=hashes)
(O/'independent_diagnostic_check.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8')
print(json.dumps({k:v for k,v in result.items() if k not in ('input_sha256','samples_first_two_last_two')},ensure_ascii=False,indent=2))
