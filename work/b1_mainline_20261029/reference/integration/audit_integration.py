from pathlib import Path
import json,hashlib
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parent
primary=json.loads((ROOT.parent/'receipt.json').read_text())
assert hashlib.sha256((ROOT.parent/'run_reference.py').read_bytes()).hexdigest()==primary['runner_sha256']
assert hashlib.sha256((ROOT.parent/'reference_api.py').read_bytes()).hexdigest()==primary['api_sha256']
raw=pd.read_csv(ROOT/'raw.csv')
bins=pd.read_csv(ROOT/'interval_records.csv')
checked=0
for keys,g in bins.groupby(['seed','hot','event_id','reference','method']):
    seed,hot,eid,ref,method=keys
    row=raw[(raw.seed==seed)&(raw.hot==hot)&(raw.event_id==eid)&(raw.reference==ref)&(raw.method==method)].iloc[0]
    req=g[(g.start_min>=0)&(g.end_min<=30)]
    truth=req.target_reduction_kw.to_numpy()
    pred=req.predicted_average_reduction_kw.to_numpy()
    y=req.input_reduction_kw.to_numpy()
    np.testing.assert_allclose(np.sqrt(np.mean((pred-truth)**2)),row.curve_rmse_kw,atol=1e-6,rtol=0)
    # Original simulator arrays and the given-reference integral use float32
    # reductions; independent CSV reread sums in float64. Permit 1e-6 ratio
    # roundoff rather than changing already-frozen scientific output.
    np.testing.assert_allclose(y.mean()/1.5,row.eta_raw,atol=1e-6,rtol=0)
    np.testing.assert_allclose(truth.mean()/1.5,row.eta_true,atol=1e-6,rtol=0)
    checked+=1
pivot=raw.pivot(index=['seed','hot','event_id','reference'],columns='method',values='eta_raw')
np.testing.assert_array_equal(pivot.Grid_average,pivot.Grid_point)
availability=pd.read_csv(ROOT/'availability.csv')
selected=pd.read_csv(ROOT/'selected_events.csv')
assert availability.n_selected.sum()==len(selected)==52
assert (selected.W==30).all() and (selected.q==1.5).all()
# Pool only to give a descriptive small-sample overview, not a new formal ranking.
overview=raw.groupby(['reference','method']).agg(curve_rmse_kw=('curve_rmse_kw','mean'),eta_rmse=('eta_error',lambda x:np.sqrt(np.mean(x*x))),n_cases=('event_id','size')).reset_index()
overview.to_csv(ROOT/'descriptive_overview.csv',index=False)
receipt=dict(passed=True,n_independent_seed_blocks=10,selected_paired_event_records=len(selected),per_method_record_checks=checked,identical_raw_eta_pairs=len(pivot),shortfall_cells=int(availability.insufficient.sum()),no_new_or_replacement_seed=True,eta_absolute_numeric_tolerance=1e-6,curve_rmse_kw_numeric_tolerance=1e-6,reason_for_tolerance='float32 simulator reductions and float32 CSV decimal serialization versus independent float64 CSV sums; scientific outputs unchanged')
(ROOT/'audit_receipt.json').write_text(json.dumps(receipt,indent=2))
print(overview.to_string(index=False));print(json.dumps(receipt))
