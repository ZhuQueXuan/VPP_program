"""Read-only scientific output recomputation; no fits or policy changes."""
from pathlib import Path
import hashlib,json
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parent;PROJECT=ROOT.parents[2];FORMAL=PROJECT/'b1_algorithm/process'
def audit(mode):
    directory=ROOT/mode
    frozen=json.loads((directory/'freeze.json').read_text(encoding='utf-8'))
    data=np.load(directory/'curves.npz');observed=np.load(directory/'observations.npz')
    rows=pd.read_csv(directory/'metrics.csv');events=json.loads((directory/'events.json').read_text(encoding='utf-8'))
    decisions=json.loads((directory/'decisions.json').read_text(encoding='utf-8'))
    assert len(rows)==8*len(events) and rows.groupby('event_id').size().eq(8).all()
    rmse_delta=eta_delta=0.;n_checks=0
    for event in events:
        i=event['event_id'];dt=event['delta_min'];s=np.arange(-15,45-1e-8,dt)
        # Use canonical count to avoid rounded1/6 minute accumulated boundaries.
        if np.isclose(dt,1/6):s=np.arange(-15,45-1e-8,1/6);dt=1/6
        req=(s>=-1e-9)&(s<30-1e-9)
        eta=float(observed[f'{i}_raw'][req].sum()*dt/45)
        for row in rows[rows.event_id==i].itertuples():
            eta_delta=max(eta_delta,abs(row.eta_raw-eta))
            if row.status=='unavailable':
                assert row.method=='new_template_candidate' and len(s)==4;continue
            pred=data[f'{i}_{row.method}'];truth=observed[f'{i}_truth']
            error=float(np.linalg.norm(pred[req]-truth[req])/np.sqrt(req.sum()))
            rmse_delta=max(rmse_delta,abs(error-row.request_rmse));n_checks+=1
        if len(s)==4:
            # Delivered raw residual is b-(b-y), differing from generator y by
            # roundoff only; the coarse gate must preserve it, not round it.
            np.testing.assert_array_equal(data[f'{i}_guarded_diagnostic'],data[f'{i}_raw_F0'])
            np.testing.assert_array_equal(data[f'{i}_unified_default'],data[f'{i}_raw_F0'])
            np.testing.assert_allclose(data[f'{i}_raw_F0'],observed[f'{i}_raw'],atol=1e-12,rtol=0)
        selected=decisions[i]
        if selected['guarded_method']=='task_template_average':
            evidence=selected['selection_evidence']
            assert evidence['gate_status']=='passed' and evidence['relative_validation_mse_reduction']>=.1
            assert evidence['mean_block_gain']>evidence['block_se']
        policy=frozen['policy']['default']
        np.testing.assert_array_equal(data[f'{i}_unified_default'],data[f'{i}_guarded_diagnostic' if policy=='guarded' else f'{i}_conservative'])
    assert rmse_delta<1e-10 and eta_delta<1e-12
    unchanged={name:hashlib.sha256((FORMAL/name).read_bytes()).hexdigest()==h for name,h in frozen['code_sha256'].items()}
    # Development was followed by an explicit validation-only contract repair
    # and a predeclared policy admission. Test must preserve every frozen file.
    if mode=='test':assert all(unchanged.values()),unchanged
    for name,origin in json.loads((FORMAL/'SOURCE_ORIGIN.json').read_text(encoding='utf-8')).items():
        if origin.get('vendored_unchanged'):
            assert hashlib.sha256((FORMAL/name).read_bytes()).hexdigest()==origin['sha256']
            assert hashlib.sha256(Path(origin['source']).read_bytes()).hexdigest()==origin['sha256']
    receipt=dict(passed=True,mode=mode,variants=len(events),independent_blocks=rows.rep.nunique(),
        output_rows=len(rows),independent_rmse_recomputations=n_checks,max_rmse_delta=rmse_delta,
        max_common_eta_delta=eta_delta,coarse_information_gate_verified=True,
        template_selection_needs_observed_validation_gate=True,shipped_default_matches_pretest_policy=True,
        frozen_code_unchanged=unchanged,original_vendored_sources_unchanged=True)
    (directory/'audit.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print(json.dumps(receipt,indent=2))
if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['development','test']);audit(p.parse_args().mode)
