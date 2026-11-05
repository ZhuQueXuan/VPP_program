"""Held-out future factual Y scores only; no generator/hidden traits imports."""
from pathlib import Path
import json,csv,hashlib
import numpy as np
BASE=Path(__file__).resolve().parent;ROOT=BASE.parents[1]
RAW=ROOT/'data/驱动因素解耦模拟数据集_B1_history_prediction_v1_20261026'
P=json.loads((BASE/'protocol.json').read_text(encoding='utf-8'))
METHODS=['C0_current','C1_history_summary','C2_history_shape','C3_history_PCA']

def main():
    receipt=json.loads((BASE/'fit_receipt.json').read_text(encoding='utf-8'))
    assert hashlib.sha256((BASE/'predictions.npz').read_bytes()).hexdigest()==receipt['predictions_sha256']
    with np.load(RAW/'observations.npz') as z:y=z['Y'];conditions=z['conditions']
    pred=np.load(BASE/'predictions.npz');rows=[]
    for r in range(P['repetitions']):
        for s,scene in enumerate(P['scenarios']):
            for split in ('validation','test'):
                ix=pred[split+'_indices'][r];yy=y[r,s,ix[:,0],ix[:,1]];x=conditions[r,ix[:,0],ix[:,1],1]
                groups=[('all',np.ones(len(ix),bool)),('x_low',x<0),('x_high',x>=0)]
                if split=='test':groups+=[('event_'+str(j),ix[:,1]==j) for j in P['test_target_events']]
                for group,mask in groups:
                    for m,method in enumerate(METHODS):
                        pp=pred[split][r,s,m];errors=pp[mask]-yy[mask]
                        rows.append(dict(seed=P['seed_start']+r,scenario=scene,split=split,group=group,method=method,
                            rows=int(mask.sum()),users=int(len(np.unique(ix[mask,0]))),mse=float(np.mean(errors**2)),
                            rmse=float(np.sqrt(np.mean(errors**2))),mae=float(np.mean(abs(errors))),bias=float(errors.mean()),
                            out_of_unit_interval_count=int(np.sum((pp[mask]<0)|(pp[mask]>1)))))
    with (BASE/'metrics.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    summary=[];paired=[]
    for scene in P['scenarios']:
        for split in ('validation','test'):
            groups=['all','x_low','x_high']+(['event_9','event_10','event_11'] if split=='test' else [])
            for group in groups:
                for method in METHODS:
                    a=[v for v in rows if v['scenario']==scene and v['split']==split and v['group']==group and v['method']==method]
                    summary.append(dict(scenario=scene,split=split,group=group,method=method,repetitions=len(a),
                        total_target_rows=sum(v['rows'] for v in a),pooled_rmse=float(np.sqrt(np.mean([v['mse'] for v in a]))),
                        mean_mae=float(np.mean([v['mae'] for v in a])),mean_bias=float(np.mean([v['bias'] for v in a])),
                        out_of_unit_interval_count=sum(v['out_of_unit_interval_count'] for v in a)))
                for base,new in [(METHODS[0],METHODS[1]),(METHODS[1],METHODS[2]),(METHODS[1],METHODS[3]),(METHODS[2],METHODS[3])]:
                    a=[v for v in rows if v['scenario']==scene and v['split']==split and v['group']==group and v['method']==base]
                    b=[v for v in rows if v['scenario']==scene and v['split']==split and v['group']==group and v['method']==new]
                    delta=np.array([v['mse'] for v in b])-np.array([v['mse'] for v in a])
                    paired.append(dict(scenario=scene,split=split,group=group,baseline=base,candidate=new,repetitions=len(delta),
                        candidate_minus_baseline_mse=float(delta.mean()),mcse=float(delta.std(ddof=1)/np.sqrt(len(delta))),
                        candidate_better_count=int(np.sum(delta<0)),differences=delta.tolist()))
    ev=dict(summary=summary,paired=paired,
        scope='Future observed factual Y prediction on held-out users and later calendar; shared scenario variants not independent; prequential previous test curves are allowed only after completion; no causal/real-world or deep-learning claim')
    (BASE/'evaluation.json').write_text(json.dumps(ev,indent=2),encoding='utf-8')
    for v in summary:
        if v['split']=='test' and v['group']=='all':print(v['scenario'],v['method'],'RMSEpp',round(v['pooled_rmse']*100,3),flush=True)
    for v in paired:
        if v['split']=='test' and v['group']=='all':print(v['scenario'],v['candidate'],'vs',v['baseline'],'MSEdelta',round(v['candidate_minus_baseline_mse'],6),'better',v['candidate_better_count'],flush=True)

if __name__=='__main__':main()
