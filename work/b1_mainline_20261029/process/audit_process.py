"""Independent output and provenance audit; never refits main experiments."""
from pathlib import Path
import hashlib,json
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parent
MAIN=ROOT/'main'
df=pd.read_csv(MAIN/'all_metrics.csv')
curves=np.load(MAIN/'all_curves.npz')
meta=json.loads((MAIN/'events.json').read_text(encoding='utf-8'))
freeze=json.loads((ROOT/'main_freeze.json').read_text(encoding='utf-8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert sha(ROOT/'protocol.json')==freeze['protocol_and_code']['protocol.json']
assert sha(ROOT/'models.py')==freeze['protocol_and_code']['models.py']
protected={p:sha(p)==h for p,h in freeze['original_sources'].items()}
assert all(protected.values())
assert len(df)==960*6 and df.groupby('event_id').size().eq(6).all()

def first_run(mask,indices,dwell):
    for j in range(len(indices)-dwell+1):
        group=indices[j:j+dwell]
        if np.all(np.diff(group)==1) and np.all(mask[group]):return int(group[0])
    return None

checked=0;max_rmse_delta=0.;max_eta_delta=0.
direct=[]
native=pd.read_csv(MAIN/'cpop_segments.csv')
for row in meta:
    i=row['event_id'];dt=row['delta_min'];s=np.arange(-15,45-1e-8,dt);e=s+dt
    req=np.flatnonzero((s>=-1e-9)&(s<30-1e-9));post=np.flatnonzero(s>=30-1e-9)
    mu=curves[f'{i}_truth'];y=curves[f'{i}_y']
    for metric in df[df.event_id==i].itertuples():
        pred=curves[f'{i}_{metric.method}']
        rmse=float(np.linalg.norm(pred[req]-mu[req])/np.sqrt(len(req)))
        eta=float(np.sum(y[req])*dt/45)
        max_rmse_delta=max(max_rmse_delta,abs(rmse-metric.request_rmse))
        max_eta_delta=max(max_eta_delta,abs(eta-metric.eta_raw))
        dwell=max(1,int(np.ceil(.5/dt-1e-9)))
        onset=first_run(pred>=.15,req,dwell)
        target=first_run(pred>=1.35,req,dwell)
        for key,index in [('onset_s',onset),('target_s',target)]:
            actual=getattr(metric,key)
            assert (index is None and np.isnan(actual)) or (index is not None and abs(actual-s[index]*60)<1e-7)
            checked+=1
        recovery=first_run(np.abs(pred)<=.15,post,dwell) if onset is not None else None
        actual=metric.recovery_s
        assert (recovery is None and np.isnan(actual)) or (recovery is not None and abs(actual-s[recovery]*60)<1e-7)
        checked+=1
    # Diagnostic: original CPOP midpoint predictions used as binned values.
    # This is an alternative operational interpretation, not frozen primary.
    sub=native[native.event_id==i]
    mid=(s+e)/2;point=np.zeros(len(mid))
    for j,seg in enumerate(sub.itertuples()):
        mask=(mid>=seg.x0-1e-8)&(mid<=seg.x1+1e-8)
        point[mask]=seg.gradient*mid[mask]+seg.intercept
    direct.append(dict(event_id=i,rep=row['rep'],delta_min=round(dt,10),mechanism=row['mechanism'],
                       cpop_direct_binned_request_rmse=float(np.sqrt(np.mean((point[req]-mu[req])**2))),
                       cpop_direct_weighted_rss=float(np.sum(((y-point)/row['sigma_kw'])**2)),
                       native_cost=float(sub.native_cost.iloc[0]),native_knots=len(sub)-1))
assert max_rmse_delta<1e-10 and max_eta_delta<1e-12
direct=pd.DataFrame(direct)
direct.to_csv(MAIN/'cpop_direct_binned_diagnostic.csv',index=False)
direct.groupby('delta_min').cpop_direct_binned_request_rmse.agg(['mean','count']).to_csv(MAIN/'cpop_direct_binned_summary.csv')
# Cost() from native R independently agrees with the fitted segment parameters.
expected=direct.cpop_direct_weighted_rss+direct.native_knots*2*np.log(np.array([len(curves[f'{i}_y']) for i in direct.event_id]))
cost_delta=float(np.max(np.abs(expected-direct.native_cost)))
assert cost_delta<1e-5
summary=pd.read_csv(MAIN/'summary.csv')
assert len(summary)==18 and summary.n.eq(320).all()
paired=pd.read_csv(MAIN/'paired.csv')
assert len(paired)==15 and paired.independent_blocks.eq(20).all() and paired.mean_difference.notna().all()
out=dict(passed=True,protected_original_files=len(protected),protected_originals_unchanged=True,
         frozen_model_protocol_unchanged=True,n_output_rows=len(df),independent_feature_checks=checked,
         max_rmse_recompute_delta=max_rmse_delta,max_eta_recompute_delta=max_eta_delta,
         native_cpop_cost_recompute_max_delta=cost_delta,
         all_three_resolution_groups_complete=True,
         posthoc_diagnostic='CPOP direct midpoint prediction treated as binned power; no change to primary projection metric',
         evaluation_parser_corrections='see parser_correction.json; no model or test parameter change')
(ROOT/'audit_receipt.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(out,ensure_ascii=False,indent=2))
print(direct.groupby('delta_min').cpop_direct_binned_request_rmse.mean())
