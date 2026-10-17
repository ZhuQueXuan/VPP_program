"""Independent source/truth/metric checks and SVD reconstruction of series."""
from pathlib import Path
import csv
import hashlib
import json
import math
from collections import defaultdict
import numpy as np

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
DATA=ROOT/'data/驱动因素解耦模拟数据集_v2'
ATOL=1e-8;RTOL=1e-6

def read(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def close(a,b):return math.isclose(a,b,abs_tol=ATOL,rel_tol=RTOL)
def main():
    a,b=HERE/'runs/RUN01',HERE/'runs/RUN02'
    receipts=[json.loads((p/'receipt.json').read_text(encoding='utf-8')) for p in [a,b]]
    assert all(r['status']=='completed' and r['source_unchanged'] for r in receipts)
    assert receipts[0]['source_sha256']==receipts[1]['source_sha256']
    assert all(sha(ROOT/k)==v for k,v in receipts[0]['source_sha256'].items())
    repeat={}
    for fn in ['predictions.csv','metrics_by_group.csv','summary.csv','fold_membership.csv','prepared_model_rows.csv']:
        x,y=read(a/fn),read(b/fn); assert len(x)==len(y)
        maxdiff=0.0;cells=0
        for rx,ry in zip(x,y):
            assert rx.keys()==ry.keys()
            for k,v in rx.items():
                if v==ry[k]:continue
                try:xn,yn=float(v),float(ry[k])
                except ValueError:raise AssertionError((fn,k,v,ry[k]))
                assert close(xn,yn),(fn,k,v,ry[k])
                maxdiff=max(maxdiff,abs(xn-yn));cells+=1
        repeat[fn]={'rows':len(x),'byte_equal':sha(a/fn)==sha(b/fn),'unequal_numeric_cells':cells,'max_abs_diff':maxdiff}
    inputs=read(DATA/'01_predecision_inputs.csv'); observed=read(DATA/'02_observed_responses.csv')
    truth=read(DATA/'03_counterfactual_truth_evaluation_only.csv')
    imap={r['case_id']:r for r in inputs};omap={r['case_id']:r for r in observed}
    tmap={(r['case_id'],float(r['intervention_incentive_yuan_per_kwh'])):float(r['potential_completion_ratio']) for r in truth}
    assert len(tmap)==13824
    for cid,r in imap.items():
        assert float(omap[cid]['completion_ratio'])==tmap[(cid,float(r['incentive_yuan_per_kwh']))]
    # Rebuild all metric groups directly from original truth, using stdlib arithmetic.
    groups=defaultdict(list)
    pred=read(a/'predictions.csv')
    for p in pred:
        cid=p['case_id'];r=imap[cid];v=float(p['contrast_price'])
        assert r['split'] in ['validation','test'] and p['split']==r['split']
        actual=tmap[(cid,v)]-tmap[(cid,.4)];estimate=float(p['estimated_effect'])
        if r['model_family'] in ['pv','storage']: assert actual==0
        tags=[('overall','all'),('type',r['resource_type_id']),('aggregation',r['aggregation_id'])]
        tags.append(('declared_null','pv_storage') if r['model_family'] in ['pv','storage'] else ('other_families','non_null_design'))
        for kind,label in tags:groups[(p['split'],p['model'],v,kind,label)].append((estimate,actual))
    maximum=0.0;count=0
    for r in read(a/'metrics_by_group.csv'):
        key=(r['split'],r['model'],float(r['contrast_price']),r['group_kind'],r['group'])
        pairs=groups[key];n=len(pairs); assert n==int(r['n'])
        e=[x-y for x,y in pairs]
        calculated={'true_mean_pp':100*math.fsum(y for x,y in pairs)/n,
          'estimated_mean_pp':100*math.fsum(x for x,y in pairs)/n,'bias_pp':100*math.fsum(e)/n,
          'mae_pp':100*math.fsum(abs(v) for v in e)/n,'rmse_pp':100*math.sqrt(math.fsum(v*v for v in e)/n),
          'abs_prediction_over_5pp_fraction':sum(abs(x)>.05 for x,y in pairs)/n}
        for k,v in calculated.items():
            assert close(v,float(r[k])),(key,k,v,r[k]);count+=1;maximum=max(maximum,abs(v-float(r[k])))
    # Check group isolation independently from written fold map.
    fm=read(a/'fold_membership.csv')
    for fold in ['0','1','2']:
        fit={r['aggregation_id'] for r in fm if r['fold']==fold and r['role']=='fit'}
        residual={r['aggregation_id'] for r in fm if r['fold']==fold and r['role']=='residual'}
        assert not fit&residual and len(fit)==2 and len(residual)==1
    enc=json.loads((a/'encoding.json').read_text(encoding='utf-8'));features=enc['features']
    prepared=read(a/'prepared_model_rows.csv');train=[r for r in prepared if r['split']=='train']
    X=np.array([[float(r[c]) for c in features] for r in train])
    saved=np.load(a/'series_reconstruction.npz')
    assert np.allclose(saved['Z'],X,atol=ATOL,rtol=RTOL)
    mu=X.mean(axis=0);sd=X.std(axis=0);sd=np.where(sd>1e-9,sd,1)
    B=np.column_stack([np.ones(len(X)),(X-mu)/sd])
    A=saved['phi_res'];D=(A[:,:,None]*B[:,None,:]).reshape(len(X),-1)
    u,s,vt=np.linalg.svd(D,full_matrices=False)
    penalty=1e-4*np.sum(D*D)/D.shape[1]
    beta=vt.T@((s/(s*s+penalty))*(u.T@saved['y_res']))
    assert np.allclose(beta,saved['beta'],atol=ATOL,rtol=RTOL)
    data_by_id={r['case_id']:r for r in prepared}
    series_diff=0.0;series_count=0
    for p in pred:
        if p['model']!='DML_SERIES':continue
        row=data_by_id[p['case_id']];z=np.array([float(row[c]) for c in features]);basis=np.r_[1,(z-mu)/sd]
        j=[.8,1.2,1.6].index(float(p['contrast_price']))
        value=float(basis@beta.reshape(3,B.shape[1])[j])
        assert close(value,float(p['estimated_effect']))
        series_diff=max(series_diff,abs(value-float(p['estimated_effect'])));series_count+=1
    # Range diagnostics only; no rows removed or routed after seeing errors.
    bounds={};ood={}
    for split in ['validation','test']:
        z=np.array([[float(r[c]) for c in features] for r in prepared if r['split']==split])
        ood[split]=int(((z<X.min(axis=0)-1e-12)|(z>X.max(axis=0)+1e-12)).any(axis=1).sum())
    result={'status':'passed','source_and_colleague_core_unchanged':True,'run_repeat':repeat,
      'factual_potential_matches':3456,'reserved_prediction_rows':len(pred),'metric_cells_independently_checked':count,
      'metric_max_abs_diff':maximum,'series_svd_predictions_checked':series_count,'series_svd_max_abs_diff':series_diff,
      'aggregation_folds_disjoint':True,'outside_train_feature_box':ood,
      'interpretation':'Computational reproducibility only, not a new physical dataset or independent real causal identification'}
    (HERE/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
