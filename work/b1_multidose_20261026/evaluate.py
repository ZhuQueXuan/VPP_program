"""Evaluator-only population means and crossings, run after observed predictions persist."""
from pathlib import Path
import json,hashlib,csv
from functools import lru_cache
import numpy as np
from scipy.special import expit
from scipy.optimize import brentq
from models import crossing,DOSES,METHODS
BASE=Path(__file__).resolve().parent
P=json.loads((BASE/'protocol.json').read_text(encoding='utf-8'))

@lru_cache(maxsize=32)
def integration_grid(group,nodes):
    z,w=np.polynomial.legendre.leggauss(nodes)
    # Independent uniform x conditional on group, w and U uniform [-1,1].
    x=(z-1)/2 if group=='x_low' else (z+1)/2
    return x[:,None,None],z[None,:,None],z[None,None,:],w[:,None,None]*w[None,:,None]*w[None,None,:]/8

def mean(name,d,group,nodes=32):
    if group=='all':return (mean(name,d,'x_low',nodes)+mean(name,d,'x_high',nodes))/2
    x,w,u,wt=integration_grid(group,nodes)
    base=.12+.12*(x+1)/2+.06*w+.04*u
    if name=='zero':pr=expit(-.5+.7*x-.6*w+.8*u)
    elif name=='linear':pr=base+.22*d/2.4
    elif name=='smooth':pr=expit(-2.5+4*d/2.4+.7*x-.6*w+.8*u)
    elif name=='hinge':pr=base+.3*max(0,d-1.2)/1.2
    else:raise ValueError(name)
    c=(.4+.2*(x+1))*(.8+.2*w*w)
    return np.array([np.sum(pr*wt),np.sum(pr*c*wt)*.975])

def main():
    start_hash=hashlib.sha256((BASE/'predictions.npz').read_bytes()).hexdigest()
    receipt=json.loads((BASE/'fit_receipt.json').read_text())
    assert start_hash==receipt['prediction_sha256'] and not receipt['truth_existed_before_fit']
    prediction=np.load(BASE/'predictions.npz')['curve']
    truth=np.empty((4,2,3,7));continuous=np.full((4,3,2),np.nan)
    quadrature_error=0.
    true_brackets={}
    for si,name in enumerate(P['scenarios']):
        for gi,group in enumerate(P['groups']):
            t=np.column_stack([mean(name,float(d),group,32) for d in DOSES])
            t64=np.column_stack([mean(name,float(d),group,64) for d in DOSES])
            quadrature_error=max(quadrature_error,float(np.max(abs(t-t64))))
            truth[si,:,gi,:]=t
            for ei,delta in enumerate((.10,.05)):
                true_brackets[(si,gi,ei)]=crossing(t[1],delta)
                if t[1,-1]-t[1,0]>=delta:
                    continuous[si,gi,ei]=brentq(lambda d:mean(name,float(d),group)[1]-t[1,0]-delta,0.,2.4)
    # Independent exact moments for linear mechanism, not a copy of the integration algorithm.
    exact=np.array([.6,.5,.7])*(13/15)*.975*.22
    assert np.max(abs(truth[1,1,:,-1]-truth[1,1,:,0]-exact))<1e-12
    assert np.max(abs(truth[1,0,:,-1]-truth[1,0,:,0]-.22))<1e-12
    np.savez_compressed(BASE/'evaluation_truth.npz',curve=truth,continuous_roots=continuous)
    rows=[];threshold_rows=[]
    for ri,seed in enumerate(P['seeds']):
        for si,name in enumerate(P['scenarios']):
            for oi,outcome in enumerate(P['outcomes']):
                for gi,group in enumerate(P['groups']):
                    t=truth[si,oi,gi]
                    for mi,method in enumerate(METHODS):
                        c=prediction[ri,si,oi,gi,mi]
                        row=dict(seed=seed,scenario=name,outcome=outcome,group=group,method=method,
                            curve_rmse=float(np.sqrt(np.mean((c-t)**2))),
                            sensitivity_rmse=float(np.sqrt(np.mean(((np.diff(c)-np.diff(t))/.4)**2))),
                            endpoint_gain_error=float((c[-1]-c[0])-(t[-1]-t[0])),
                            negative_steps=int(np.sum(np.diff(c)<-1e-10)))
                        rows.append(row)
                        if oi!=1:continue
                        for ei,delta in enumerate((.10,.05)):
                            r=crossing(c,delta);ref=true_brackets[(si,gi,ei)];root=continuous[si,gi,ei]
                            exact_status=r['status']==ref['status']
                            bracket_correct=exact_status and (r['status']!='bracket' or (r['lower']==ref['lower'] and r['upper']==ref['upper']))
                            threshold_rows.append(dict(seed=seed,scenario=name,group=group,method=method,delta=delta,
                                status=r['status'],lower=r['lower'],upper=r['upper'],
                                true_status=ref['status'],true_lower=ref['lower'],true_upper=ref['upper'],
                                continuous_root=float(root) if np.isfinite(root) else None,
                                state_and_grid_correct=bracket_correct,
                                continuous_root_contained=bool(r['status']=='bracket' and np.isfinite(root) and r['lower']-1e-10<=root<=r['upper']+1e-10),
                                spurious_bracket=ref['status']=='not_reached' and r['status']=='bracket'))
    for name,data in [('metrics.csv',rows),('crossings.csv',threshold_rows)]:
        with (BASE/name).open('w',encoding='utf-8-sig',newline='') as f:
            wr=csv.DictWriter(f,fieldnames=list(data[0]));wr.writeheader();wr.writerows(data)
    summary=[]
    for si,name in enumerate(P['scenarios']):
        for oi,outcome in enumerate(P['outcomes']):
            for gi,group in enumerate(P['groups']):
                for mi,method in enumerate(METHODS):
                    r=[v for v in rows if v['scenario']==name and v['outcome']==outcome and v['group']==group and v['method']==method]
                    rm=np.array([v['curve_rmse'] for v in r]);sens=np.array([v['sensitivity_rmse'] for v in r])
                    rec=dict(scenario=name,outcome=outcome,group=group,method=method,
                        pooled_curve_rmse=float(np.sqrt(np.mean(rm**2))),
                        mean_curve_rmse=float(rm.mean()),rmse_mcse=float(rm.std(ddof=1)/np.sqrt(20)),
                        pooled_sensitivity_rmse=float(np.sqrt(np.mean(sens**2))),
                        nonmonotonic_repetitions=int(sum(v['negative_steps']>0 for v in r)))
                    if oi==1:
                        cr=[v for v in threshold_rows if v['scenario']==name and v['group']==group and v['method']==method and v['delta']==.1]
                        rec.update(true_crossing=true_brackets[(si,gi,0)],
                            correct_grid_count=sum(v['state_and_grid_correct'] for v in cr),
                            bracket_count=sum(v['status']=='bracket' for v in cr),
                            ambiguous_count=sum(v['status']=='ambiguous_nonmonotone' for v in cr),
                            not_reached_count=sum(v['status']=='not_reached' for v in cr),
                            root_contained_count=sum(v['continuous_root_contained'] for v in cr),
                            spurious_bracket_count=sum(v['spurious_bracket'] for v in cr))
                    summary.append(rec)
    paired=[]
    for si,name in enumerate(P['scenarios']):
        for oi,outcome in enumerate(P['outcomes']):
            for gi,group in enumerate(P['groups']):
                t=truth[si,oi,gi];base=np.mean((prediction[:,si,oi,gi,1]-t)**2,axis=-1)
                flex=np.mean((prediction[:,si,oi,gi,2]-t)**2,axis=-1);delta=flex-base
                paired.append(dict(scenario=name,outcome=outcome,group=group,
                    spline_minus_linear_mse=float(delta.mean()),delta_mcse=float(delta.std(ddof=1)/np.sqrt(20)),
                    spline_better_count=int(np.sum(delta<0))))
    report=dict(summary=summary,paired=paired,quadrature_max_error=quadrature_error,
        exact_linear_gain=exact.tolist(),limits='grid crossing is a predefined result-margin crossing, not a hard economic or physical kink; no CI or formal acceptance')
    (BASE/'evaluation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('quadrature max',quadrature_error,'metrics',len(rows),'crossings',len(threshold_rows))
    for s in summary:
        if s['outcome']=='delivery' and s['group']=='all':
            print(s['scenario'],s['method'],'curveRMSEpp',round(100*s['pooled_curve_rmse'],3),'correct10pp',s['correct_grid_count'],'ambiguous',s['ambiguous_count'],'notreached',s['not_reached_count'])

if __name__=='__main__':main()
