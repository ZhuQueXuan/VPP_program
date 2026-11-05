from pathlib import Path
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[key]='1'
import argparse, copy, hashlib, json, time, warnings
import numpy as np
import pandas as pd
warnings.filterwarnings('ignore',message='X does not have valid feature names')
from reference_api import SafeGBDT, fit_references, split_users, window_average
from ride.simulate import simulate, observe, true_baseline_at
from ride.config import SimConfig, ObsConfig

ROOT=Path(__file__).resolve().parent
PROTOCOL=ROOT/'protocol.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def make(seed,hot,n=200):
    cfg=SimConfig(n_users=n,n_events_per_user=4,hot_concentration=hot,dt0=1.,L_post=90.,n_donors=1,seed=seed)
    sim=simulate(cfg)
    obs=observe(sim,ObsConfig(delta=1.,sigma=.15,p_missing=0.,seed=seed+3))
    return sim,obs

def evaluate(obs,truth,result,seed,hot):
    user=obs.meta['user'].to_numpy();typ=obs.meta['is_ev'].to_numpy()
    test=np.isin(user,result.splits['test'])
    q=obs.meta['q'].to_numpy(float)
    out=[];details=[]
    for method,(be,bp) in result.predictions.items():
        delta=window_average(be-truth,obs)
        pseudo=window_average(bp-obs.Pse,obs)/q[:,None]
        hw=result.halfwidth_eta[method]
        for t in (0,1):
            keep=test&(typ==t)
            clusters=np.unique(user[keep])
            cluster_ok=[]
            for u in clusters:
                rr=keep&(user==u)
                cluster_ok.append(bool(np.all(np.abs(pseudo[rr])<=hw[rr,None])))
            row=dict(seed=seed,hot=hot,resource='EV' if t else 'AC',method=method,
                n_users=len(clusters),n_events=int(keep.sum()),
                bias_kw=float(np.mean(delta[keep])),rmse_kw=float(np.sqrt(np.mean(delta[keep]**2))),
                mae_eta=float(np.mean(np.abs(pseudo[keep]))),pseudo_positive_eta_rate=float(np.mean(pseudo[keep]>.1)),
                latent_event_coverage=float(np.mean(np.abs(delta[keep]/q[keep])<=hw[keep])),
                pseudo_user_simultaneous_coverage=float(np.mean(cluster_ok)),
                halfwidth_eta=float(np.mean(hw[keep])),selected_candidate=result.choices[t] if method=='selected' else method)
            out.append(row)
        for i in np.flatnonzero(test):
            details.append(dict(seed=seed,hot=hot,event_id=int(obs.meta['event_id'].iat[i]),user=int(user[i]),resource='EV' if typ[i] else 'AC',method=method,
                window_reference_error_kw=float(delta[i]),halfwidth_eta=float(hw[i]),q_kw=float(q[i])))
    return out,details

def checks():
    sim,obs=make(905001,True,80)
    split=split_users(obs.meta['user'],905001)
    g=SafeGBDT(905001).fit(obs,split['train'])
    a=g.predict(obs)
    other=copy.deepcopy(obs)
    # Only post-notice actual measurements change: predictions must be identical.
    lead=obs.meta['lead'].to_numpy()[:,None]
    post=obs.starts[None,:]>=-lead-1e-9
    other.P[post]+=1000
    other.meta['dep_decl']+=10000
    other.meta['e_rem']+=10000
    np.testing.assert_array_equal(a,g.predict(other))
    other=copy.deepcopy(obs)
    for key in ('hist_dep','hist_erem','pse_dep','pse_erem'):
        other.day_meta[key]=np.full_like(other.day_meta[key],99999.)
    np.testing.assert_array_equal(a,g.predict(other))
    g2=SafeGBDT(905001).fit(other,split['train'])
    np.testing.assert_array_equal(a,g2.predict(other))
    result=fit_references(obs,split,905001)
    for t,c in result.choices.items():
        tab=result.selection_table.query('resource==@t')
        assert c==tab.sort_values(['mae_eta','candidate']).iloc[0]['candidate']
    bad=dict(split);bad['test']=bad['train'][:1]
    try:fit_references(obs,bad,905001)
    except ValueError:pass
    else:raise AssertionError('overlapping users accepted')
    trial=np.ones_like(obs.P);_,_,win,_=__import__('ride.baseline',fromlist=['masks']).masks(obs)
    first=np.flatnonzero(win[0])[0];trial[0,first]=np.nan
    assert np.isnan(window_average(trial,obs)[0])
    np.testing.assert_allclose(window_average(np.ones_like(obs.P),obs),1.)
    receipt=dict(passed=True,checks=['post-notice-power invariance','declared-departure and energy unused','historical/pseudo endpoint metadata unused in prediction and fit','selection minimizes absolute error by type','overlapping roles rejected','missing task-bin rejected','width-weighted task mean'],protocol_sha256=sha(PROTOCOL))
    (ROOT/'checks.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print(json.dumps(receipt))

def main():
    p=argparse.ArgumentParser();p.add_argument('--checks',action='store_true');args=p.parse_args()
    if args.checks:checks();return
    if not (ROOT/'checks.json').exists():raise RuntimeError('run checks first')
    if (ROOT/'receipt.json').exists():raise RuntimeError('main result already exists; do not overwrite')
    protocol=json.loads(PROTOCOL.read_text(encoding='utf-8'))
    start=time.time();rows=[];details=[];selections=[];calibrations=[];hashes=[]
    for seed in protocol['main_seeds']:
        for hot in (False,True):
            sim,obs=make(seed,hot,protocol['n_users'])
            split=split_users(obs.meta['user'],seed+5)
            res=fit_references(obs,split,seed)
            truth=true_baseline_at(sim,1.,'B')
            out,det=evaluate(obs,truth,res,seed,hot)
            rows.extend(out);details.extend(det)
            selections.append(res.selection_table.assign(seed=seed,hot=hot))
            calibrations.append(res.calibration_table.assign(seed=seed,hot=hot))
            # Hash independent observable/truth arrays without retaining high-volume synthetic time series.
            hh=hashlib.sha256()
            for arr in (obs.P,obs.Hist,obs.Pse,truth):hh.update(np.asarray(arr).tobytes())
            hashes.append(dict(seed=seed,hot=hot,data_sha256=hh.hexdigest(),user_splits={k:list(map(int,v)) for k,v in split.items()}))
            del sim,obs,res
        pd.DataFrame(rows).to_csv(ROOT/'raw.csv',index=False)
        print(f'seed {seed} done elapsed {time.time()-start:.1f}s',flush=True)
    raw=pd.DataFrame(rows);detail=pd.DataFrame(details)
    raw.to_csv(ROOT/'raw.csv',index=False);detail.to_csv(ROOT/'test_events.csv',index=False)
    pd.concat(selections).to_csv(ROOT/'selection_scores.csv',index=False)
    pd.concat(calibrations).to_csv(ROOT/'calibration_scores.csv',index=False)
    fields=['bias_kw','rmse_kw','mae_eta','pseudo_positive_eta_rate','latent_event_coverage','pseudo_user_simultaneous_coverage','halfwidth_eta']
    summary=raw.groupby(['hot','resource','method'])[fields].mean().reset_index()
    summary.to_csv(ROOT/'summary.csv',index=False)
    frequency=raw.query("method=='selected'").groupby(['hot','resource','selected_candidate']).size().reset_index(name='count')
    frequency.to_csv(ROOT/'selection_frequency.csv',index=False)
    # Paired improvement CI uses 20 seed-level values, not 2400 repeated event rows.
    paired=[]
    from scipy.stats import t
    for (hot,resource),sub in raw.groupby(['hot','resource']):
        pivot=sub.pivot(index='seed',columns='method',values='rmse_kw')
        for c in ('gbdt','selected'):
            diff=(pivot[c]-pivot['prev10']).to_numpy()
            half=t.ppf(.975,len(diff)-1)*np.std(diff,ddof=1)/np.sqrt(len(diff))
            paired.append(dict(hot=hot,resource=resource,candidate=c,n_seeds=len(diff),mean_rmse_difference_kw=diff.mean(),lower95=diff.mean()-half,upper95=diff.mean()+half))
    pd.DataFrame(paired).to_csv(ROOT/'paired_differences.csv',index=False)
    (ROOT/'data_identity.json').write_text(json.dumps(hashes,indent=2),encoding='utf-8')
    receipt=dict(status='complete',n_seed_blocks=20,n_paired_conditions=40,total_simulated_events=32000,n_test_metric_rows=len(raw),test_event_rows=len(detail),elapsed_seconds=time.time()-start,protocol_sha256=sha(PROTOCOL),api_sha256=sha(ROOT/'reference_api.py'),runner_sha256=sha(Path(__file__)),data_regenerable=True)
    (ROOT/'receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print(summary.to_string(index=False));print(json.dumps(receipt))

if __name__=='__main__':main()
