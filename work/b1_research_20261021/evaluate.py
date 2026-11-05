"""Evaluation-only truth generation, run AFTER predictions have been persisted."""
from pathlib import Path
import csv,json,hashlib
import numpy as np
from scipy.special import expit
ROOT=Path(__file__).resolve().parent
P=json.loads((ROOT/'protocol.json').read_text(encoding='utf-8'))
RAW=ROOT.parent.parent/P['raw_root']

def conditional_truth(x,beta,nodes):
    u,weights=np.polynomial.legendre.leggauss(nodes)
    a=-.5+.7*x[:,0]-.6*x[:,1]
    prob0=expit(a[:,None]+.8*u)
    prob1=expit(a[:,None]+beta+.8*u)
    opening=(.4+.2*(x[:,0]+1))*(.8+.2*x[:,1]**2)
    return opening*.975*((prob1-prob0)@weights/2)

def main():
    assert (ROOT/'predictions.npz').exists()
    receipt=json.loads((ROOT/'fit_receipt.json').read_text())
    pred_hash=hashlib.sha256((ROOT/'predictions.npz').read_bytes()).hexdigest()
    assert pred_hash==receipt['predictions_sha256'] and not receipt['truth_existed_at_fit_start']
    observed=np.load(RAW/'main_observations.npz')
    predictions=np.load(ROOT/'predictions.npz')
    tau=np.empty(predictions['e'].shape)
    rows=[]
    truth_error=0.
    support_failures=[]
    for ri,seed in enumerate(P['replicate_seeds']):
        for si,(name,beta) in enumerate(P['scenarios'].items()):
            te=observed['split'][ri,si]==2
            x=observed['X'][ri,si][te]
            y,d=[observed[k][ri,si][te] for k in ('Y','D')]
            t=conditional_truth(x,beta,80)
            truth_error=max(truth_error,float(np.max(abs(t-conditional_truth(x,beta,160)))))
            tau[ri,si]=t
            p={k:predictions[k][ri,si] for k in predictions.files}
            e=p['e']
            support=bool(e.min()>=.05 and e.max()<=.95)
            scores=p['mu1']-p['mu0']+d*(y-p['mu1'])/e-(1-d)*(y-p['mu0'])/(1-e)
            for group,mask in [('all',np.ones(len(x),bool)),('x_low',x[:,0]<0),('x_high',x[:,0]>=0)]:
                arm_counts=[int(np.sum(mask&(d==k))) for k in (0,1)]
                valid=support and min(arm_counts)>=10
                truth=float(t[mask].mean())
                estimates={'G0':float(y[mask&(d==1)].mean()-y[mask&(d==0)].mean()),
                           'G1':float(p['ridge_effect'][mask].mean()),
                           'G1ML':float((p['mu1']-p['mu0'])[mask].mean()),
                           'G2':float(scores[mask].mean()) if valid else np.nan}
                if not valid:
                    support_failures.append(dict(seed=seed,scenario=name,group=group,arm_counts=arm_counts))
                for method,estimate in estimates.items():
                    rows.append(dict(seed=seed,scenario=name,method=method,group=group,n=int(mask.sum()),
                        estimate=estimate,truth=truth,error=estimate-truth,
                        causal_eligible=not(method=='G0' and name.startswith('observed')),
                        status='ok' if np.isfinite(estimate) else 'unavailable'))
    np.savez_compressed(ROOT/'truth.npz',tau=tau)
    with (ROOT/'metrics.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]))
        writer.writeheader();writer.writerows(rows)
    summary=[]
    for name in P['scenarios']:
        for method in ('G0','G1','G1ML','G2'):
            for group in ('all','x_low','x_high'):
                r=[row for row in rows if row['scenario']==name and row['method']==method and row['group']==group]
                err=np.array([row['error'] for row in r])
                summary.append(dict(scenario=name,method=method,group=group,repetitions=len(r),
                    mean_estimate=float(np.mean([row['estimate'] for row in r])),
                    mean_truth=float(np.mean([row['truth'] for row in r])),bias=float(err.mean()),
                    rmse=float(np.sqrt(np.mean(err**2))),error_mcse=float(err.std(ddof=1)/np.sqrt(len(err))),
                    abs_estimate_gt_005=float(np.mean(np.abs([row['estimate'] for row in r])>.05))))
    paired=[]
    for name in P['scenarios']:
        for baseline in ('G1','G1ML'):
            for group in ('all','x_low','x_high'):
                err2=np.array([r['error'] for r in rows if r['scenario']==name and r['method']=='G2' and r['group']==group])
                errb=np.array([r['error'] for r in rows if r['scenario']==name and r['method']==baseline and r['group']==group])
                delta=err2**2-errb**2
                paired.append(dict(scenario=name,group=group,baseline=baseline,
                    mse_delta=float(delta.mean()),delta_mcse=float(delta.std(ddof=1)/np.sqrt(len(delta))),
                    absolute_error_wins=int(np.sum(abs(err2)<abs(errb)))))
    out=dict(identity=P['identity'],summary=summary,paired=paired,support_failures=support_failures,
        quadrature_max_difference=truth_error,
        limitation='20 repetitions describe this SCM; no CI coverage, real ability or formal 90% acceptance claim')
    (ROOT/'evaluation.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in ROOT.glob('*.py')}
    (ROOT/'run_receipt.json').write_text(json.dumps(dict(protocol_sha256=hashlib.sha256((ROOT/'protocol.json').read_bytes()).hexdigest(),
        code_sha256=hashes,predictions_sha256=pred_hash,truth_after_predictions=True,
        metric_rows=len(rows),support_failure_count=len(support_failures)),indent=2),encoding='utf-8')
    print(json.dumps({'metric_rows':len(rows),'quadrature_max_difference':truth_error,'support_failures':len(support_failures)}))
    for r in summary:
        if r['group']=='all':
            print(r['scenario'],r['method'],'truth_pp',round(100*r['mean_truth'],3),'rmse_pp',round(100*r['rmse'],3),'bias_pp',round(100*r['bias'],3))

if __name__=='__main__':main()
