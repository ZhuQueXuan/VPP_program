"""Read-only audit of already seen reliability outputs. No fitting or tuning.

Evaluator-only exact rectangular witnesses diagnose optimization gaps, never
provide an estimator initialization, routing rule, or a new performance test.
"""
import sys
sys.dont_write_bytecode = True
import json, csv, hashlib
from pathlib import Path
from collections import Counter
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'B1算法'))
from b1_algorithm.process._ride_revised import interval_components
STUDY=ROOT/'work/b1_reliability_20261031/study/test'
OUT=Path(__file__).resolve().parent
inputs={}
def read(p):
    inputs[str(p.relative_to(ROOT))]=hashlib.sha256(p.read_bytes()).hexdigest()
    return json.loads(p.read_text(encoding='utf8'))
rows=[]
for blockpath in sorted((STUDY/'blocks').glob('*.json')):
    seed=int(blockpath.stem)
    truth=read(STUDY/'evaluator'/f'{seed}_weak_truth.json')
    facts=read(ROOT/'data/B1_reliability_v1_20261031/test'/f'{seed}_weak_facts.json')
    refs=read(STUDY/'references'/f'{seed}_new.json')['references']
    ev=read(STUDY/'events'/f'{seed}_weak_new_ride_revised.json')
    cp=read(STUDY/'events'/f'{seed}_weak_new_cpop.json')
    for t,f,r,v,c in zip(truth,facts,refs,ev,cp):
        assert t['task_id']==f['task']['task_id']==v['task']['task_id']==c['task']['task_id']==r['task_id']
        s=np.asarray(f['starts_min'])-f['task']['start_min'];e=np.asarray(f['ends_min'])-f['task']['start_min']
        ref=np.asarray(r['reference_kw']);p=np.asarray(f['power_kw']);y=ref-p
        task=(s>=0)&(s<30);sigma=f['noise_sigma_kw'];n=len(y)
        se=v['process']['selection_evidence'];par=se['parameters'];selected=se['solver_records'][se['selected_solver']]
        k=8 if selected['structure']==1 else 10
        null=float(y@y)/sigma**2;bic=selected['rss']/sigma**2+k*np.log(n)
        gate_bic=bic<null;gate_amp=par['positive_ratio']>=.1
        duration=v['process']['features']['selected_curve']['cumulative_response_seconds']
        cd=c['process']['features']['selected_curve']['cumulative_response_seconds']
        err=ref-np.asarray(t['true_reference_kw'])
        true=np.asarray(t['true_reduction_kw'])
        active=task&(true>=.15)
        row=dict(seed=seed,task_id=t['task_id'],subtype=t['weak_subtype'],amplitude_fraction=t['weak_amplitude_fraction'],
          shape=t['latent']['shape'],true_duration=t['cumulative_response_seconds'],threshold_positive=t['threshold_positive'],
          template_duration=duration,cpop_duration=cd,template_miss=t['threshold_positive'] and duration==0,
          cpop_miss=t['threshold_positive'] and cd==0,template_detected=se['detected'],
          gate_bic=bool(gate_bic),gate_amplitude=bool(gate_amp),selected_amplitude=par['positive_ratio'],
          selected_structure=selected['structure'],bic_minus_null=float(bic-null),
          residual_above_threshold_bins=int(np.sum(task&(y>=.15))),
          reference_bias_kw=float(np.mean(err[task])),reference_rmse_kw=float(np.sqrt(np.mean(err[task]**2))),
          reference_bias_active_kw=float(np.mean(err[active])) if active.any() else None,
          minimum_success_rss=min(a['rss'] for a in se['solver_records'] if a['accepted']),
          all_solver_accepted=sum(a['accepted'] for a in se['solver_records']),
          witness_exact_error=None,witness_bic_minus_null=None,witness_beats_selected_bic=None,witness_passes=None)
        assert bool(se['detected'])==(gate_bic and gate_amp)
        assert (duration==0) or bool(se['detected'])
        if t['weak_subtype'] in ('brief3','brief6') and t['threshold_positive']:
            # Evaluator truth only: the known rectangle begins on the fine
            # simulator grid; recharge at W has deterministic 1.8kW rate.
            d0=.25+1.5*t['latent']['delay_uniform']
            fine=np.asarray(t['relative_fine_midpoints_min'])
            act=(fine>=d0)&(fine<d0+t['weak_rectangle_minutes'])&(fine<30)
            d=float(fine[np.flatnonzero(act)[0]]-1/12)
            hold=float(act.sum()/6)
            rb=float(true[task].sum()/1.8)
            times=np.array([d,0.,hold,0.,30-d-hold,rb])
            pos,neg=interval_components(times,30,s,e,1)
            witness=1.5*t['weak_amplitude_fraction']*pos-1.8*neg
            exact=float(np.max(np.abs(witness-true)))
            assert exact<1e-10
            assert times.min()>=0 and 1.8/1.5<=se['rebound_max_ratio']+1e-9
            wrss=float(np.sum((witness-y)**2));wbic=wrss/sigma**2+8*np.log(n)
            row.update(witness_exact_error=exact,witness_bic_minus_null=float(wbic-null),
               witness_beats_selected_bic=bool(wbic<bic-1e-8),witness_passes=bool(wbic<null))
        rows.append(row)

positive=[r for r in rows if r['threshold_positive']]
def aggregate(group):
    misses=[r for r in group if r['template_miss']]
    return dict(n=len(group),template_miss=sum(r['template_miss'] for r in group),cpop_miss=sum(r['cpop_miss'] for r in group),
      template_miss_bic_only=sum(not r['gate_bic'] and r['gate_amplitude'] for r in misses),
      template_miss_amplitude_only=sum(r['gate_bic'] and not r['gate_amplitude'] for r in misses),
      template_miss_both_gates=sum(not r['gate_bic'] and not r['gate_amplitude'] for r in misses),
      template_miss_after_detection=sum(r['template_detected'] for r in misses),
      template_miss_raw_any_above=sum(r['residual_above_threshold_bins']>0 for r in misses),
      witness_n=sum(r['witness_exact_error'] is not None for r in group),
      missed_with_exact_witness_beats_selected_and_passes=sum(r['template_miss'] and r['witness_beats_selected_bic'] is True and r['witness_passes'] is True for r in group),
      reference_bias_kw_mean=float(np.mean([r['reference_bias_kw'] for r in group])) if group else None,
      missed_reference_bias_kw_mean=float(np.mean([r['reference_bias_kw'] for r in misses])) if misses else None)
summary=dict(scope='Already-seen 8-block reliability test; no refit, new facts, tuning or estimator change.',
  overall=aggregate(positive),by_subtype={},by_amplitude={},by_subtype_amplitude={},sustained_shape={},
  input_sha256=inputs)
for key in sorted({r['subtype'] for r in positive}):summary['by_subtype'][key]=aggregate([r for r in positive if r['subtype']==key])
for key in sorted({r['amplitude_fraction'] for r in positive}):summary['by_amplitude'][str(key)]=aggregate([r for r in positive if r['amplitude_fraction']==key])
for sub in sorted({r['subtype'] for r in positive}):
    for amp in sorted({r['amplitude_fraction'] for r in positive}):
        summary['by_subtype_amplitude'][f'{sub}_{amp}']=aggregate([r for r in positive if r['subtype']==sub and r['amplitude_fraction']==amp])
for key in sorted({r['shape'] for r in positive if r['subtype']=='sustained'}):summary['sustained_shape'][key]=aggregate([r for r in positive if r['subtype']=='sustained' and r['shape']==key])
with (OUT/'saved_process_diagnosis.csv').open('w',encoding='utf8',newline='') as h:
    w=csv.DictWriter(h,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
(OUT/'saved_process_diagnosis.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8')
assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==digest for p,digest in inputs.items())
print(json.dumps({k:v for k,v in summary.items() if k!='input_sha256'},ensure_ascii=False,indent=2))
