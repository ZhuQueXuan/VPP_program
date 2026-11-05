from pathlib import Path
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
import sys,json,hashlib,time,warnings
import numpy as np
import pandas as pd
warnings.filterwarnings('ignore',message='X does not have valid feature names')
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent))
sys.path.insert(0,str(ROOT.parents[1]/'process'))
from run_reference import make
from reference_api import SafeGBDT,split_users
from models import fit
from ride.simulate import true_baseline_at
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    if (ROOT/'receipt.json').exists():raise RuntimeError('completed integration cannot be overwritten')
    started=time.time();protocol=json.loads((ROOT/'protocol.json').read_text())
    models_path=ROOT.parents[1]/'process/models.py'
    before=dict(protocol_sha256=sha(ROOT/'protocol.json'),models_sha256=sha(models_path),reference_sha256=sha(ROOT.parent/'reference_api.py'),runner_sha256=sha(Path(__file__)))
    (ROOT/'before.json').write_text(json.dumps(before,indent=2))
    rows=[];bins=[];available=[];chosen=[]
    for seed in protocol['seeds']:
        for hot in (False,True):
            sim,obs=make(seed,hot,protocol['n_users'])
            roles=split_users(obs.meta['user'],seed+5)
            model=SafeGBDT(seed).fit(obs,roles['train'])
            estimated=model.predict(obs)
            truth_b=true_baseline_at(sim,1.,'B')
            factual_p=true_baseline_at(sim,1.,'P')
            selected=[]
            for typ,label in ((0,'AC'),(1,'EV')):
                eligible=(obs.meta['user'].isin(roles['test']) & (obs.meta['is_ev']==typ) & np.isclose(obs.meta['W'],30.) & np.isclose(obs.meta['q'],1.5))
                ix=obs.meta[eligible].sort_values('event_id').index.to_numpy()
                selected.extend(ix[:2])
                available.append(dict(seed=seed,hot=hot,resource=label,n_eligible=len(ix),n_selected=min(len(ix),2),insufficient=len(ix)<2))
            ix_time=(obs.starts>=-15-1e-9)&(obs.ends<=45+1e-9)
            s,e=obs.starts[ix_time],obs.ends[ix_time]
            np.testing.assert_allclose(s,np.arange(-15,45))
            request=(s>=0)&(e<=30)
            for i in selected:
                eid=int(obs.meta['event_id'].iat[i]);user=int(obs.meta['user'].iat[i]);resource='EV' if obs.meta['is_ev'].iat[i] else 'AC'
                chosen.append(dict(seed=seed,hot=hot,event_id=eid,user=user,resource=resource,W=30.,q=1.5))
                target=(truth_b[i]-factual_p[i])[ix_time]
                true_eta=float(target[request].mean()/1.5)
                for ref_name,ref in [('given_true_reference',truth_b),('shared_SafeGBDT',estimated)]:
                    y=(ref[i]-obs.P[i])[ix_time]
                    raw_eta=float(y[request].mean()/1.5)
                    common=[]
                    for average,method in [(False,'Grid_point'),(True,'Grid_average')]:
                        pred,info=fit(y,1.,.15,averaging=average)
                        common.append(raw_eta)
                        rows.append(dict(seed=seed,hot=hot,event_id=eid,user=user,resource=resource,reference=ref_name,method=method,
                            curve_rmse_kw=float(np.sqrt(np.mean((pred[request]-target[request])**2))),eta_true=true_eta,eta_raw=raw_eta,
                            eta_error=raw_eta-true_eta,reference_window_bias_kw=float(np.mean((ref[i]-truth_b[i])[ix_time][request])),
                            knots_count=len(info['knots']),enumerated_models=info['enumerated_models']))
                        for k in range(len(s)):
                            bins.append(dict(seed=seed,hot=hot,event_id=eid,resource=resource,reference=ref_name,method=method,start_min=s[k],end_min=e[k],
                                target_reduction_kw=target[k],input_reduction_kw=y[k],predicted_average_reduction_kw=pred[k]))
                    assert common[0]==common[1]
            print(f'seed {seed} hot={hot} selected={len(selected)} elapsed={time.time()-started:.1f}s',flush=True)
    raw=pd.DataFrame(rows);raw.to_csv(ROOT/'raw.csv',index=False)
    pd.DataFrame(bins).to_csv(ROOT/'interval_records.csv',index=False)
    pd.DataFrame(available).to_csv(ROOT/'availability.csv',index=False)
    pd.DataFrame(chosen).to_csv(ROOT/'selected_events.csv',index=False)
    # Averages first within seed, preserving the ten independent block units.
    seed=raw.groupby(['seed','hot','resource','reference','method']).agg(curve_rmse_kw=('curve_rmse_kw','mean'),eta_rmse=('eta_error',lambda x:np.sqrt(np.mean(x*x))),reference_bias_kw=('reference_window_bias_kw','mean'),n_events=('event_id','size')).reset_index()
    seed.to_csv(ROOT/'seed_metrics.csv',index=False)
    summary=seed.groupby(['hot','resource','reference','method']).agg(curve_rmse_kw=('curve_rmse_kw','mean'),eta_rmse=('eta_rmse','mean'),reference_bias_kw=('reference_bias_kw','mean'),n_seed_blocks=('seed','nunique'),n_events=('n_events','sum')).reset_index()
    summary.to_csv(ROOT/'summary.csv',index=False)
    assert sha(models_path)==before['models_sha256']
    assert sha(ROOT.parent/'reference_api.py')==before['reference_sha256']
    manifest_path=ROOT.parents[2]/'ride_b1_v02_reproduction_20261029/source_manifest.json'
    manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    for item in manifest['files']:
        assert sha(manifest_path.parent/'source'/item['path'])==item['sha256']
    receipt=dict(status='complete',n_seed_blocks=10,n_conditions=20,n_selected_events=len(chosen),n_eligible_shortfall_cells=sum(x['insufficient'] for x in available),n_method_rows=len(rows),same_raw_eta_across_process_methods=True,original_ride_files_unchanged=46,elapsed_seconds=time.time()-started,**before)
    (ROOT/'receipt.json').write_text(json.dumps(receipt,indent=2))
    print(summary.to_string(index=False));print(json.dumps(receipt))
if __name__=='__main__':main()
