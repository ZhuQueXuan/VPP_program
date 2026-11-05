"""Frozen finite development and fresh test; never overwrite completed stages."""
from engine import *
import argparse, time
from datetime import datetime, timezone
from scipy.stats import t

def source_hashes():
    files=[p for p in SOURCE.rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    files += list((RIDE/'ride').glob('*.py'))
    files += [HERE/'engine.py',HERE/'run.py',HERE/'protocol.json',HERE/'check.py',
              ROOT/'b123_api.py',ROOT/'work/b1_formal_v1_20261029/process/dgp.py',
              ROOT/'work/b1_mainline_20261029/process/api.py']
    return {str(p.relative_to(ROOT)):sha(p) for p in files}

def paired_values(values):
    values=np.asarray(values,float);n=len(values);mean=float(values.mean())
    half=float(t.ppf(.975,n-1)*values.std(ddof=1)/np.sqrt(n)) if n>1 else float('nan')
    return dict(blocks=n,mean_difference=mean,mc95_low=mean-half,mc95_high=mean+half,wins=int(np.sum(values<0)))

def summarize(df,out):
    summaries=[]
    for (reference,method),a in df.groupby(['reference','method']):
        none=a[a.mechanism=='none'];active=a[a.mechanism!='none']
        summaries.append(dict(reference=reference,method=method,n_variants=len(a),n_seed_blocks=a.seed.nunique(),
            mean_curve_rmse_kw=a.groupby('seed').curve_rmse_kw.mean().mean(),
            none_false_positive_fraction=none.groupby('seed').onset_detected.mean().mean(),none_denominator=len(none),
            onset_mae_s=active.onset_abs_error_s.mean(),onset_matched=int(active.onset_abs_error_s.notna().sum()),
            onset_truth_available=int(active.truth_onset_detected.sum()),
            onset_missed=int((active.truth_onset_detected & ~active.onset_detected).sum()),
            recovery_mae_s=active.recovery_abs_error_s.mean(),recovery_matched=int(active.recovery_abs_error_s.notna().sum()),
            recovery_truth_available=int(active.truth_recovery_detected.sum()),
            mean_reference_bias_kw=a.groupby('seed').reference_bias_kw.mean().mean(),
            eta_rmse=float(np.sqrt(np.mean(a.eta_error**2))),unavailable_fraction=float((a.status!='ok').mean())))
    pd.DataFrame(summaries).to_csv(out/'summary.csv',index=False)
    comparisons=[]
    for reference in df.reference.unique():
        p=df[df.reference==reference].pivot(index=['seed','context','mechanism'],columns='method',values='curve_rmse_kw')
        for comparator in ('native_CPOP_default','original_RIDE_template_3starts'):
            diff=(p['frozen_guarded']-p[comparator]).groupby(level='seed').mean()
            comparisons.append(dict(reference=reference,candidate='frozen_guarded',comparator=comparator,**paired_values(diff)))
    pd.DataFrame(comparisons).to_csv(out/'method_paired.csv',index=False)
    correction=[]
    for method in df.method.unique():
        p=df[df.method==method].pivot(index=['seed','context','mechanism'],columns='reference',values='curve_rmse_kw')
        diff=(p.gbdt_pre15_shift-p.fixed_gbdt).groupby(level='seed').mean()
        f=df[(df.method==method)&(df.mechanism=='none')].pivot(index=['seed','context'],columns='reference',values='onset_detected')
        fpr=float((f.gbdt_pre15_shift.astype(float)-f.fixed_gbdt.astype(float)).groupby(level='seed').mean().mean())
        correction.append(dict(method=method,relative_curve_improvement=float(1-p.gbdt_pre15_shift.mean()/p.fixed_gbdt.mean()),
            no_action_fpr_difference=fpr,all_blocks_nonworse=bool((diff<=1e-12).all()),**paired_values(diff)))
    pd.DataFrame(correction).to_csv(out/'correction_paired.csv',index=False)
    return correction

def run(phase):
    out=HERE/phase
    if out.exists():raise RuntimeError('phase already exists; preserve it and inspect, never overwrite')
    protocol=json.loads((HERE/'protocol.json').read_text(encoding='utf-8'))
    if phase=='test':
        development=json.loads((HERE/'development/receipt.json').read_text(encoding='utf-8'))
        if not development['complete']:raise RuntimeError('development incomplete')
    checks=json.loads((HERE/'checks.json').read_text(encoding='utf-8'))
    if not checks['passed']:raise RuntimeError('checks required')
    out.mkdir();before=source_hashes();started=time.perf_counter()
    (out/'freeze.json').write_text(json.dumps(dict(utc=datetime.now(timezone.utc).isoformat(),hashes=before,
        phase=phase,protocol_sha256=sha(HERE/'protocol.json')),indent=2),encoding='utf-8')
    seeds=protocol[phase+'_seeds'];contexts=[]
    data_dir=ROOT/'data/B1_unknown_reference_v1_20261030'/phase
    for seed in seeds:
        contexts.extend(generate(seed,out,data_dir))
        print(phase,'generated',seed,'contexts',len(contexts),'seconds',round(time.perf_counter()-started,1),flush=True)
    entries,cases,arrays=datasets(contexts)
    counts={seed:sum(c['seed']==seed for c in contexts) for seed in seeds}
    assert all(n>=1 for n in counts.values()),'retain empty block and stop; do not replace seeds'
    np.savez_compressed(out/'inputs_and_truth.npz',**arrays)
    config=runtime_config();config.update(artifact_dir=str(out/'native_calls'),timeout_seconds=1200)
    print(phase,'native CPOP cases',len(cases),flush=True)
    native_results,backend=native.fit_cases(cases,config)
    (out/'backend.json').write_text(json.dumps(backend,indent=2),encoding='utf-8')
    assert backend['status']=='ok' and all(v.get('status')=='ok' for v in native_results.values()),backend
    assert len(native_results)==len(cases)
    print(phase,'native CPOP done seconds',round(time.perf_counter()-started,1),flush=True)
    rows=[];decisions=[];predictions={}
    for entry in entries:
        index=entry['index'];data=entry['data']
        result=process.complete(data,native_results,base=index*10,policy='guarded',backend=backend)
        assert result['status']=='ok',result
        ride_curve,ride_info=oldapi.ride_fit(data['y'],1.,.15)
        options=[('native_CPOP_default',native_results[index*10]['prediction'],'CPOP'),
                 ('frozen_guarded',result['reduction_interval_kw'],result['method']),
                 ('original_RIDE_template_3starts',ride_curve,'RIDE_3starts')]
        for method,curve,chosen in options:
            assert np.isfinite(curve).all(),(index,method)
            predictions[f'{index}_{method}']=np.asarray(curve)
            rows.append(score(entry,curve,method,chosen))
        decisions.append(dict(index=index,seed=entry['seed'],context=entry['context'],reference=entry['reference'],
            mechanism=entry['mechanism'],method=result['method'],evidence=result['selection_evidence'],ride=ride_info))
        if (index+1)%12==0:
            pd.DataFrame(rows).to_csv(out/'metrics_partial.csv',index=False)
            print(phase,'fitted',index+1,'/',len(entries),'seconds',round(time.perf_counter()-started,1),flush=True)
    df=pd.DataFrame(rows);df.to_csv(out/'metrics.csv',index=False)
    np.savez_compressed(out/'method_curves.npz',**predictions)
    (out/'decisions.json').write_text(json.dumps(decisions,indent=2),encoding='utf-8')
    correction=summarize(df,out)
    required=[r for r in correction if r['method'] in ('native_CPOP_default','frozen_guarded')]
    if phase=='development':
        admitted=all(r['all_blocks_nonworse'] and r['relative_curve_improvement']>=.05 and r['no_action_fpr_difference']<=.05+1e-12 for r in required)
    else:
        admitted=development['candidate_admitted'] and all(r['mc95_high']<0 and r['no_action_fpr_difference']<=.05+1e-12 for r in required)
    assert source_hashes()==before,'protected code changed during study'
    common=df.groupby(['seed','context','mechanism','reference']).eta_raw.agg(['min','max'])
    assert np.max(common['max']-common['min'])==0.
    receipt=dict(complete=True,phase=phase,independent_seed_blocks=len(seeds),contexts=len(contexts),
        physical_context_shape_variants=len(contexts)*4,reference_variants=len(entries),method_rows=len(df),native_cases=len(cases),
        context_shortfalls={str(k):2-v for k,v in counts.items() if v<2},
        candidate_admitted=bool(admitted),default_changed=False,raw_eta_identical_across_methods=True,
        protected_hashes_unchanged=True,elapsed_seconds=time.perf_counter()-started,
        scope='controlled interval-response stress panel on RIDE EV load backgrounds; not full author pipeline, real validation, or causal effect evaluation')
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print(json.dumps(receipt,indent=2),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase',choices=('development','test'));run(p.parse_args().phase)
