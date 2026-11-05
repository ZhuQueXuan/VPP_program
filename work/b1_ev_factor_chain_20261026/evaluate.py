"""Only after observed graph/features/predictions persist, evaluate SCM truth."""
from pathlib import Path
import json,csv,hashlib
import numpy as np
from scipy.special import expit,ndtr
from scipy.stats import binom
BASE=Path(__file__).resolve().parent;ROOT=BASE.parents[1]
RAW=ROOT/'data/驱动因素解耦模拟数据集_B1_ev_factor_chain_v1_20261026'
P=json.loads((BASE/'protocol.json').read_text(encoding='utf-8'))

def reference_truth():
    threshold=3.-.15;f=np.float32(threshold)
    while 3.-float(f)<.15:f=np.nextafter(f,np.float32(-np.inf))
    nxt=np.nextafter(f,np.float32(np.inf));boundary=(float(f)+float(nxt))/2
    q0=float(ndtr((boundary-3)/.05));q1=float(ndtr((boundary-1.5)/.05))
    truth=np.zeros((4,2,2,2));gphys=np.zeros((2,2));targetlevel=np.zeros((2,2,2))
    nullS=float(binom.sf(59,120,q0))
    for x in (0,1):
        for w in (0,1):
            samples=[min(1200-10*k,900+600*x-300*w+10*j) for j in range(-30,31) for k in range(7)]
            g=np.mean(samples);gphys[x,w]=g
            # q1 rounds to1 under this Gaussian scenario; convolution then exact
            # for represented floating probabilities, missing active successes negligible.
            probabilities=[]
            for duration in samples:
                active=int(duration//10)
                if q1==1.:probabilities.append(float(binom.sf(59-active,120-active,q0)))
                else:
                    count=np.arange(active+1);probabilities.append(float(np.sum(binom.pmf(count,active,q1)*binom.sf(59-count,120-active,q0))))
            levels=np.array([g*(q1-q0),np.mean(probabilities)-nullS]);targetlevel[x,w]=levels
            for s,beta in enumerate(P['acceptance_dose_coefficients']):truth[s,x,w]=(expit(-.2+beta-.8*w)-expit(-.2-.8*w))*levels
    return truth,dict(q0=q0,q1=q1,stored_threshold_boundary_kw=boundary,physical_duration_mean_s=gphys.tolist(),accepted_minus_refused_outcome_means=targetlevel.tolist())

def main():
    receipt=json.loads((BASE/'fit_receipt.json').read_text(encoding='utf-8'))
    for file,key in [('predictions.npz','predictions_sha256'),('graphs.json','graphs_sha256'),('observed_features.npz','features_sha256')]:assert hashlib.sha256((BASE/file).read_bytes()).hexdigest()==receipt[key]
    with np.load(RAW/'observations.npz') as z:x=z['X'];w=z['W'];splits=z['user_split']
    pred=np.load(BASE/'predictions.npz');f=np.load(BASE/'observed_features.npz');hidden=np.load(BASE/'hidden_evaluator.npz');graphs=json.loads((BASE/'graphs.json').read_text(encoding='utf-8'))
    truth,truthmeta=reference_truth();rows=[];gr=[];fe=[]
    for r in range(P['repetitions']):
        for s,scene in enumerate(P['scenarios']):
            for split in ('validation','test'):
                ix=pred[split+'_indices'][r];ref=truth[s,x[r,ix],w[r,ix]]
                for group,mask in [('all',np.ones(len(ix),bool)),('X0',x[r,ix]==0),('X1',x[r,ix]==1)]:
                    true=ref[mask].mean(axis=0)
                    for m,method in enumerate(P['methods']):
                        pp=pred[split][r,s,m,mask];available=bool(np.isfinite(pp).all())
                        estimate=np.mean(pp[:,1]-pp[:,0],axis=0) if available else [None,None]
                        for o,name in enumerate(('cumulative_s','long600')):
                            rows.append(dict(seed=P['seed_start']+r,scenario=scene,split=split,group=group,method=method,outcome=name,
                                rows=int(mask.sum()),available=available,true_effect=float(true[o]),estimate=float(estimate[o]) if available else None,
                                error=float(estimate[o]-true[o]) if available else None))
            trueedges={('W','A'),('X','S'),('W','S'),('A','S')}
            if P['acceptance_dose_coefficients'][s]!=0:trueedges.add(('D','A'))
            if not scene.startswith('randomized'):trueedges|={('X','D'),('W','D')}
            learned=graphs[r][s]['learned'];edges=set(map(tuple,learned['edges']));tp=len(edges&trueedges)
            gr.append(dict(seed=P['seed_start']+r,scenario=scene,exact=edges==trueedges,true_positives=tp,false_positives=len(edges-trueedges),false_negatives=len(trueedges-edges),
                precision=tp/len(edges) if edges else 0.,recall=tp/len(trueedges),
                missing_edges=sorted(trueedges-edges),extra_edges=sorted(edges-trueedges),
                adjustment_matches_assumed=learned['suggested_adjustment']['selected']==graphs[r][s]['identification']['selected'],
                unavailable_parent_candidates=sum(not a['available'] for node in learned['local_scores'] for a in node['candidates'])))
            latent=hidden['duration_s'][r,s];continu=f['longest_s'][r,s];cum=f['cumulative_s'][r,s]
            fe.append(dict(seed=P['seed_start']+r,scenario=scene,events=len(cum),cumulative_mae_vs_physical_s=float(np.mean(abs(cum-latent))),
                longest_mae_vs_physical_s=float(np.mean(abs(continu-latent))),
                false_continuous_detections=int(np.sum((latent==0)&(continu>0))),
                false_single_bin_detections=int(np.sum((latent==0)&(cum>0))),
                max_abs_observed_end_debt_kwh=float(np.max(abs(f['debt_end_kwh'][r,s])))))
    for name,rr in [('metrics.csv',rows),('graph_metrics.csv',gr),('feature_metrics.csv',fe)]:
        with (BASE/name).open('w',encoding='utf-8-sig',newline='') as fcsv:
            writer=csv.DictWriter(fcsv,fieldnames=list(rr[0]));writer.writeheader();writer.writerows(rr)
    summary=[]
    for scene in P['scenarios']:
        for split in ('validation','test'):
            for group in ('all','X0','X1'):
                for method in P['methods']:
                    for outcome in ('cumulative_s','long600'):
                        rr=[v for v in rows if all(v[k]==val for k,val in [('scenario',scene),('split',split),('group',group),('method',method),('outcome',outcome)])]
                        valid=[v for v in rr if v['available']];errors=np.array([v['error'] for v in valid])
                        summary.append(dict(scenario=scene,split=split,group=group,method=method,outcome=outcome,repetitions=len(rr),available_repetitions=len(valid),unavailable_repetitions=len(rr)-len(valid),
                            mean_true_effect=float(np.mean([v['true_effect'] for v in rr])),mean_estimate=float(np.mean([v['estimate'] for v in valid])) if valid else None,
                            mean_bias=float(errors.mean()) if len(errors) else None,rmse=float(np.sqrt(np.mean(errors**2))) if len(errors) else None,
                            bias_mcse=float(errors.std(ddof=1)/np.sqrt(len(errors))) if len(errors)>1 else None))
    graphsummary=[]
    for scene in P['scenarios']:
        rr=[v for v in gr if v['scenario']==scene]
        graphsummary.append(dict(scenario=scene,repetitions=len(rr),exact_count=sum(v['exact'] for v in rr),mean_precision=float(np.mean([v['precision'] for v in rr])),mean_recall=float(np.mean([v['recall'] for v in rr])),
            adjustment_agreement_count=sum(v['adjustment_matches_assumed'] for v in rr),unavailable_parent_candidates_total=sum(v['unavailable_parent_candidates'] for v in rr)))
    report=dict(summary=summary,graph_summary=graphsummary,truth=truth.tolist(),truth_metadata=truthmeta,feature_summary=fe,
        limits='causal conclusions conditional on declared EV SCM and assumed adjustment graph; BIC screening with time-prior direction is not complete causal discovery; cumulative and continuous durations differ; bad-adjustment comparator explicitly invalid for total effect')
    (BASE/'evaluation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    for v in summary:
        if v['split']=='test' and v['group']=='all' and v['outcome']=='cumulative_s':print(v['scenario'],v['method'],'true',round(v['mean_true_effect'],2),'estimate',round(v['mean_estimate'],2) if v['mean_estimate'] is not None else None,'RMSE',round(v['rmse'],2) if v['rmse'] is not None else None,'valid',v['available_repetitions'],flush=True)
    print('graphs',graphsummary)

if __name__=='__main__':main()
