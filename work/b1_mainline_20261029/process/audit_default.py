from pathlib import Path
import hashlib,json
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'supplement_native_default'
segments=pd.read_csv(OUT/'cpop_segments.csv');metrics=pd.read_csv(OUT/'metrics.csv')
empty=segments.x1<=segments.x0
assert empty.sum()==28 and segments.loc[empty,'event_id'].nunique()==28
assert np.allclose(segments.loc[empty,'y0'],segments.loc[empty,'y1'])
assert np.isfinite(segments.loc[~empty,['gradient','intercept']].to_numpy()).all()
assert metrics.groupby('event_id').size().eq(2).all() and len(metrics)==1920
truth=np.load(ROOT/'main/all_curves.npz');fits=np.load(OUT/'curves.npz')
events=json.loads((ROOT/'main/events.json').read_text(encoding='utf-8'))
err=0.
for m in events:
    i=m['event_id'];dt=m['delta_min'];s=np.arange(-15,45-1e-8,dt);ix=(s>=-1e-9)&(s<30-1e-9)
    for method in ['CPOP_default_binned','CPOP_default_average_projection']:
        error=np.linalg.norm(fits[f'{i}_{method}'][ix]-truth[f'{i}_truth'][ix])/np.sqrt(ix.sum())
        reported=metrics[(metrics.event_id==i)&(metrics.method==method)].request_rmse.iloc[0]
        err=max(err,abs(float(error)-reported))
assert err<1e-10
frozen=json.loads((OUT/'freeze.json').read_text(encoding='utf-8'))
for p,h in frozen['sha256'].items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==h,p
out=dict(passed=True,all960_native_events_present=True,original_empty_segments=28,affected_events=28,
         n_independent_rmse_recomputations=1920,max_rmse_delta=err,
         frozen_main_inputs_and_outputs_unchanged=True,default_fit_no_rerun=True)
(OUT/'audit.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
print(json.dumps(out,indent=2))
