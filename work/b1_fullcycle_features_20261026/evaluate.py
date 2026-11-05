"""Post-extraction noiseless observable-criterion evaluator, no method import."""
from pathlib import Path
import json,csv,hashlib,math
import numpy as np
BASE=Path(__file__).resolve().parent;ROOT=BASE.parents[1]
RAW=ROOT/'data/驱动因素解耦模拟数据集_B1_fullcycle_features_v1_20261026'
P=json.loads((BASE/'protocol.json').read_text(encoding='utf-8'))

def truth_at_grid(native,row):
    dt=row['dt_s'];n=row['n'];factor=dt//10
    r=np.array([math.fsum(native[j:j+factor])/factor for j in range(0,n*factor,factor)])
    t=np.arange(n)*dt;dwell=math.ceil(30/dt);req=(t>=600)&(t<1800)
    def first(predicate,start,stop):
        for j in range(start,stop-dwell+1):
            if all(predicate(r[k]) for k in range(j,j+dwell)):return float(t[j])
        return None
    onset=first(lambda v:v>=.15,600//dt,1800//dt)
    target=first(lambda v:v>=1.35,600//dt,1800//dt)
    longest=0
    # Direct enumerate maximal true runs, no implementation helper reused.
    bins=np.flatnonzero(req&(r>=.15));chunks=np.split(bins,np.flatnonzero(np.diff(bins)>1)+1) if len(bins) else []
    longest=max([len(c)*dt for c in chunks if len(c)>=dwell]+[0])
    recovery=first(lambda v:abs(v)<=.15,1800//dt,n) if onset is not None else None
    powerstatus='not_applicable' if onset is None else ('recovered' if recovery is not None else 'right_censored')
    stage='no_response' if onset is None else ('response' if target is not None else 'partial')
    if row['observation']=='missing_request':onset=target=None;longest=None;stage=powerstatus='unavailable';recovery=None
    if row['observation']=='missing_post':powerstatus='unavailable';recovery=None
    reqenergy=math.fsum(r[req])*dt/3600
    debt=math.fsum(r[t>=600])*dt/3600
    return dict(onset_s=onset,target_s=target,duration_s=longest,stage=stage,power_recovery_status=powerstatus,power_recovery_s=recovery,
        request_net_kwh=None if row['observation']=='missing_request' else reqenergy,
        debt_kwh=None if row['observation'].startswith('missing_') else debt),r

def main():
    receipt=json.loads((BASE/'extraction_receipt.json').read_text(encoding='utf-8'))
    for file,key in [('predictions.json','predictions_sha256'),('fitted_reductions.npz','fits_sha256')]:assert hashlib.sha256((BASE/file).read_bytes()).hexdigest()==receipt[key]
    rows=json.loads((RAW/'observation_index.json').read_text(encoding='utf-8'));pred=json.loads((BASE/'predictions.json').read_text(encoding='utf-8'))
    hidden=np.load(BASE/'hidden_native.npz')['reduction_kw'];fit=np.load(BASE/'fitted_reductions.npz')['reduction_kw'];public=np.load(RAW/'observations.npz')['power_obs_kw']
    metrics=[];truths=[]
    for i,row in enumerate(rows):
        truth,r=truth_at_grid(hidden[row['latent_id']],row);truths.append(dict(observation_id=i,**truth))
        for m in range(2):
            out=pred[2*i+m];assert out['observation_id']==i
            rec={**row,'method':out['method'],'stage_correct':out['stage']==truth['stage'],
                'request_available':out['request_net_kwh'] is not None,'power_status_correct':out['power_recovery_status']==truth['power_recovery_status'],
                'power_status':out['power_recovery_status'],'energy_balance_status':out['balance']['status'],
                'onset_false_detection':truth['stage']=='no_response' and out['onset_s'] is not None,
                'internal_cut_count':out['internal_cut_count']}
            for key in ('onset_s','target_s','duration_s','power_recovery_s','request_net_kwh'):
                t=truth[key];v=out[key];rec['true_'+key]=t;rec['estimated_'+key]=v
                rec[key+'_error']=float(v-t) if t is not None and v is not None else None
                rec[key+'_within30']=bool(t is not None and v is not None and abs(v-t)<=30) if key.endswith('_s') else None
            finite=np.isfinite(public[i,:row['n']]);rf=fit[2*i+m,:row['n']]
            rec['curve_mse_kw2']=float(np.mean((rf[finite]-r[finite])**2))
            debt=truth['debt_kwh'];bal=out['balance']
            rec['balance_interval_covered']=bool(debt is not None and bal['lower_kwh'] is not None and bal['lower_kwh']-1e-12<=debt<=bal['upper_kwh']+1e-12)
            rec['balance_true_within_margin']=None if debt is None else debt<=.01
            rec['balance_wrong_decisive']=bool(debt is not None and ((bal['status']=='within_margin' and debt>.01) or (bal['status']=='above_margin' and debt<=.01)))
            metrics.append(rec)
    with (BASE/'metrics.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(metrics[0]));writer.writeheader();writer.writerows(metrics)
    (BASE/'evaluation_truth.json').write_text(json.dumps(truths,indent=2),encoding='utf-8')
    summary=[]
    # Keep every observation condition; no complete-case-only overall accuracy.
    for case in P['mechanisms']:
        for obs in P['observations']:
            for sigma in P['noise_sigma_native_kw']:
                for dt in P['dt_s']:
                    for method in ('F0_raw_rule','F1_segment_rule'):
                        rr=[v for v in metrics if v['mechanism']==case and v['observation']==obs and v['sigma_native_kw']==sigma and v['dt_s']==dt and v['method']==method]
                        n=len(rr);a=dict(mechanism=case,observation=obs,sigma_native_kw=sigma,dt_s=dt,method=method,denominator=n,
                            stage_correct_count=sum(v['stage_correct'] for v in rr),power_status_correct_count=sum(v['power_status_correct'] for v in rr),
                            false_onset_count=sum(v['onset_false_detection'] for v in rr),request_available_count=sum(v['request_available'] for v in rr),
                            curve_rmse_kw=float(np.sqrt(np.mean([v['curve_mse_kw2'] for v in rr]))),
                            mean_internal_cuts=float(np.mean([v['internal_cut_count'] for v in rr])),
                            balance_interval_covered_count=sum(v['balance_interval_covered'] for v in rr),
                            balance_evaluable_count=sum(v['balance_true_within_margin'] is not None for v in rr),
                            balance_wrong_decisive_count=sum(v['balance_wrong_decisive'] for v in rr))
                        a['balance_status_counts']={s:sum(v['energy_balance_status']==s for v in rr) for s in ('within_margin','above_margin','unresolved','right_censored','unavailable')}
                        for key in ('onset_s','target_s','duration_s','power_recovery_s','request_net_kwh'):
                            eligible=sum(v['true_'+key] is not None for v in rr);err=[v[key+'_error'] for v in rr if v[key+'_error'] is not None]
                            a[key]=dict(truth_eligible=eligible,paired_available=len(err),conditional_mae=float(np.mean(abs(np.array(err)))) if err else None,
                                conditional_bias=float(np.mean(err)) if err else None,
                                within30_count=sum(v[key+'_within30'] is True for v in rr) if key.endswith('_s') else None)
                        summary.append(a)
    paired=[]
    for case in P['mechanisms']:
        for sigma in P['noise_sigma_native_kw']:
            for dt in P['dt_s']:
                a=[v for v in metrics if v['mechanism']==case and v['observation']=='full' and v['sigma_native_kw']==sigma and v['dt_s']==dt]
                f0=[v for v in a if v['method']=='F0_raw_rule'];f1=[v for v in a if v['method']=='F1_segment_rule']
                result=dict(mechanism=case,sigma_native_kw=sigma,dt_s=dt,denominator=len(f0))
                for key in ('onset_s','duration_s','power_recovery_s'):
                    diffs=[abs(b[key+'_error'])-abs(a[key+'_error']) for a,b in zip(f0,f1) if a[key+'_error'] is not None and b[key+'_error'] is not None]
                    result[key]=dict(paired_count=len(diffs),mean_F1_minus_F0_absolute_error=float(np.mean(diffs)) if diffs else None,
                        mcse=float(np.std(diffs,ddof=1)/np.sqrt(len(diffs))) if len(diffs)>1 else None,F1_better_count=sum(v<0 for v in diffs))
                paired.append(result)
    report=dict(summary=summary,full_observation_paired=paired,limits='No pooled independence across shared variants, no tested superiority guarantee, physical action vs noiseless grid threshold distinguished; conditional MAE always accompanied by all eligible counts')
    (BASE/'evaluation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    for sigma in P['noise_sigma_native_kw']:
        for dt in P['dt_s']:
            for method in ('F0_raw_rule','F1_segment_rule'):
                rr=[v for v in metrics if v['observation']=='full' and v['sigma_native_kw']==sigma and v['dt_s']==dt and v['method']==method]
                print(sigma,dt,method,'stage',sum(v['stage_correct'] for v in rr),'/',len(rr),'falseonset',sum(v['onset_false_detection'] for v in rr),'durationMAE',np.mean([abs(v['duration_s_error']) for v in rr if v['duration_s_error'] is not None]),flush=True)

if __name__=='__main__':main()
