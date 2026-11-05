"""Requested stratified analysis of frozen outputs; no fits or tuning."""
from pathlib import Path
import json
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'supplement'
OUT.mkdir(exist_ok=True)
if (OUT/'receipt.json').exists():raise RuntimeError('supplement already frozen')
df=pd.read_csv(ROOT/'main/all_metrics.csv')
base=df.pivot(index=['rep','mechanism','delta_min','sigma_kw'],columns='method',values='request_rmse')
results=[]
for comparator in ['CPOP_original_R','F1_frozen_segment_adapter','Grid_average']:
    for stratum in ['all','curved','multiplateau','template_outside_combined','other_mechanisms']:
        mask=np.ones(len(base),dtype=bool)
        mechanism=base.index.get_level_values('mechanism')
        if stratum in ['curved','multiplateau']:mask=mechanism==stratum
        elif stratum=='template_outside_combined':mask=mechanism.isin(['curved','multiplateau'])
        elif stratum=='other_mechanisms':mask=~mechanism.isin(['curved','multiplateau'])
        subset=base[mask]
        for delta in sorted(df.delta_min.unique()):
            g=subset.xs(delta,level='delta_min')
            block=(g['RIDE_template_average']-g[comparator]).groupby(level='rep').mean()
            se=float(block.std(ddof=1)/np.sqrt(len(block)));mean=float(block.mean())
            results.append(dict(candidate='RIDE_template_average',comparator=comparator,stratum=stratum,
                                delta_min=delta,independent_blocks=len(block),observation_variants=len(g),
                                candidate_mean=g['RIDE_template_average'].mean(),comparator_mean=g[comparator].mean(),
                                paired_difference=mean,mc95_low=mean-2.093*se,mc95_high=mean+2.093*se,
                                wins_blocks=int((block<0).sum()),
                                scope='secondary subgroup analysis of frozen test; no multiplicity adjustment; not a new experiment'))
pd.DataFrame(results).to_csv(OUT/'template_paired.csv',index=False)

curves=np.load(ROOT/'main/all_curves.npz')
meta=json.loads((ROOT/'main/events.json').read_text(encoding='utf-8'))
segs=pd.read_csv(ROOT/'main/cpop_segments.csv')
amplitudes=[]
for m in meta:
    i=m['event_id'];rows=segs[segs.event_id==i]
    # For linear segments the extreme is attained at an endpoint; include
    # the same half-bin endpoint extrapolation used by primary scoring.
    times=np.unique(np.r_[-15,rows.x0.to_numpy(),rows.x1.to_numpy(),45])
    extremes=[]
    for j,row in enumerate(rows.itertuples()):
        lo=min(-15,row.x0) if j==0 else row.x0
        hi=max(45,row.x1) if j==len(rows)-1 else row.x1
        extremes.extend([row.gradient*lo+row.intercept,row.gradient*hi+row.intercept])
    y=curves[f'{i}_y'];pred=curves[f'{i}_CPOP_original_R']
    amplitudes.append(dict(event_id=i,rep=m['rep'],delta_min=round(m['delta_min'],10),
                           native_max_abs_latent_kw=float(np.max(np.abs(extremes))),
                           native_min_latent_kw=float(min(extremes)),native_max_latent_kw=float(max(extremes)),
                           native_max_abs_projected_average_kw=float(np.max(np.abs(pred))),
                           observed_max_abs_average_kw=float(np.max(np.abs(y))),
                           native_knots=len(rows)-1))
pd.DataFrame(amplitudes).to_csv(OUT/'cpop_amplitude_diagnostic.csv',index=False)
pd.DataFrame(amplitudes).groupby('delta_min').agg(
    median_max_abs_latent_kw=('native_max_abs_latent_kw','median'),
    max_abs_latent_kw=('native_max_abs_latent_kw','max'),
    max_abs_projected_average_kw=('native_max_abs_projected_average_kw','max'),
    max_abs_observed_average_kw=('observed_max_abs_average_kw','max')).to_csv(OUT/'cpop_amplitude_summary.csv')
(OUT/'receipt.json').write_text(json.dumps(dict(analysis_only=True,new_fitting=False,
    frozen_main_unchanged=True,n_template_subgroup_rows=len(results),n_amplitude_rows=len(amplitudes),
    caveat='posthoc diagnostic and secondary subgroup comparisons; no simultaneous guarantee'),indent=2),encoding='utf-8')
print(pd.DataFrame(results).query("comparator=='CPOP_original_R' and stratum in ['all','curved','multiplateau']").to_string(index=False))
