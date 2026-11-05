"""Evaluate original default-grid CPOP on the frozen input, without refits."""
from pathlib import Path
import hashlib,json,re
import numpy as np
import pandas as pd
from run_process import assess,integrate_segments

ROOT=Path(__file__).resolve().parent;OUT=ROOT/'supplement_native_default'
if (OUT/'receipt.json').exists():raise RuntimeError('default-grid supplement already evaluated')
freeze=json.loads((OUT/'freeze.json').read_text(encoding='utf-8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
for p,h in freeze['sha256'].items():assert sha(p)==h,p
native=pd.read_csv(OUT/'cpop_segments.csv')
arrays=np.load(ROOT/'main/all_curves.npz')
events=json.loads((ROOT/'main/events.json').read_text(encoding='utf-8'))
rows=[];predictions={};cost_differences=[];zero_segments=0
for meta in events:
    i=meta['event_id'];delta=meta['delta_min'];s=np.arange(-15,45-1e-8,delta);e=s+delta;mid=(s+e)/2
    sub=native[native.event_id==i]
    if sub.empty:raise ValueError(f'missing native output {i}')
    k=len(sub)-1  # Preserve the original package cost's own changepoint count.
    zero=sub.x1<=sub.x0
    assert np.allclose(sub.loc[zero,'y0'],sub.loc[zero,'y1'])
    zero_segments+=int(zero.sum())
    valid=sub.loc[~zero]
    assert np.isfinite(valid[['gradient','intercept']].to_numpy()).all()
    # A zero-length endpoint segment contributes no area. Original fitted()
    # emits NaN gradients for these; ignore only empty intervals when parsing.
    average=integrate_segments(valid,s,e)
    point=np.zeros(len(mid));covered=np.zeros(len(mid),int)
    for segment in valid.itertuples():
        mask=(mid>=segment.x0-1e-8)&(mid<=segment.x1+1e-8)
        point[mask]=segment.gradient*mid[mask]+segment.intercept;covered[mask]+=1
    assert np.all(covered>=1)
    y=arrays[f'{i}_y'];mu=arrays[f'{i}_truth']
    sigma=meta['sigma_kw'];ncost=float(sub.native_cost.iloc[0])
    expected=np.sum(((y-point)/sigma)**2)+k*2*np.log(len(y))
    cost_differences.append(abs(expected-ncost))
    for method,pred in [('CPOP_default_binned',point),('CPOP_default_average_projection',average)]:
        rows.append(assess(pred,mu,y,delta,meta,method,float(sub.native_seconds.iloc[0]),
                           dict(native_cost=ncost,knots_count=k,nonempty_segments=len(valid),
                                empty_segments=int(zero.sum()),grid='official_default_x')))
        predictions[f'{i}_{method}']=pred
df=pd.DataFrame(rows);df.delta_min=df.delta_min.round(10)
assert len(df)==1920 and np.isfinite(df.request_rmse).all()
assert max(cost_differences)<1e-5
df.to_csv(OUT/'metrics.csv',index=False)
np.savez_compressed(OUT/'curves.npz',**predictions)
summary=df.groupby(['method','delta_min']).agg(request_rmse=('request_rmse','mean'),
        curve_rmse=('curve_rmse','mean'),n=('event_id','size'),stage_accuracy=('stage_correct','mean'),
        onset_mae_s=('onset_s_abs_error','mean'),onset_n_joint=('onset_s_joint_valid','sum'),
        target_mae_s=('target_s_abs_error','mean'),target_n_joint=('target_s_joint_valid','sum'),
        recovery_mae_s=('recovery_s_abs_error','mean'),recovery_n_joint=('recovery_s_joint_valid','sum')).reset_index()
summary.to_csv(OUT/'summary.csv',index=False)
original=pd.read_csv(ROOT/'main/all_metrics.csv')
merged=pd.concat([original,df],ignore_index=True)
table=merged.pivot(index=['rep','mechanism','delta_min','sigma_kw'],columns='method',values='request_rmse')
contrasts=[]
for candidate in ['RIDE_template_average','Grid_average']:
    for comparator in ['CPOP_default_binned','CPOP_default_average_projection']:
        for stratum in ['all','curved','multiplateau']:
            selection=table if stratum=='all' else table[table.index.get_level_values('mechanism')==stratum]
            for delta in sorted(df.delta_min.unique()):
                g=selection.xs(delta,level='delta_min')
                block=(g[candidate]-g[comparator]).groupby(level='rep').mean()
                se=float(block.std(ddof=1)/np.sqrt(len(block)));mean=float(block.mean())
                contrasts.append(dict(candidate=candidate,comparator=comparator,stratum=stratum,delta_min=delta,
                    candidate_mean=float(g[candidate].mean()),comparator_mean=float(g[comparator].mean()),
                    independent_blocks=len(block),paired_difference=mean,mc95_low=mean-2.093*se,
                    mc95_high=mean+2.093*se,wins_blocks=int((block<0).sum()),
                    scope='same frozen observations; one default setting; secondary subgroup contrasts unadjusted'))
contrasts=pd.DataFrame(contrasts);contrasts.to_csv(OUT/'paired.csv',index=False)
elapsed=float(re.search(r'TOTAL_SECONDS\s+([0-9.]+)',(OUT/'console.log').read_text(encoding='utf-8')).group(1))
receipt=dict(passed=True,no_new_data=True,no_parameter_search=True,n_variants=len(events),n_metric_rows=len(df),
    independent_blocks=20,actual_original_cpop_version='1.0.10',r_batch_elapsed_seconds=elapsed,
    max_native_cost_recompute_difference=max(cost_differences),main_results_sha256_unchanged=True,
    original_zero_length_endpoint_segments=zero_segments,
    parser_adaptation='ignore empty endpoint segments only; raw CSV, fit and native cost unchanged',
    metrics_sha256=sha(OUT/'metrics.csv'),segments_sha256=sha(OUT/'cpop_segments.csv'),
    limitation='known common reference and noise; official default grid, same fixed penalty, finite synthetic scenarios; no real-data or universal dominance claim')
(OUT/'receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
print(summary.to_string(index=False))
print(contrasts.query("candidate=='RIDE_template_average'").to_string(index=False))
