from pathlib import Path
import importlib.util,json,sys
import numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];PARENT=HERE.parent
spec=importlib.util.spec_from_file_location('frozen_retained_v2',PARENT/'state_v2/adapter.py');A=importlib.util.module_from_spec(spec);spec.loader.exec_module(A);B=A.B
def save(n,v):
    p=HERE/n;p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8') as f:json.dump(B.native(v),f,ensure_ascii=False,indent=2,allow_nan=False)
for name,value in B.read(HERE/'before_selection_freeze.json')['files'].items():assert B.sha(ROOT/name)==value,name
for name,value in B.read(HERE/'label_freeze.json')['files'].items():assert B.sha(HERE/name)==value,name
rows=B.read(HERE/'inputs.json');assert all(r['split']=='validation' for r in rows)
spec=importlib.util.spec_from_file_location('native_baseline_helpers',ROOT/'work/b1_cpop_fine_v3_20261031/common.py');H=importlib.util.module_from_spec(spec);spec.loader.exec_module(H);H.HERE=HERE
cases=[];vectors=[];ids=[]
for r in rows:
    a=B.arrays(r)
    if a is None:continue
    j=len(ids);ids.append(r['event_id']);n=len(a['p']);x=np.arange(1,n+1,dtype=float);cases.append(dict(case_id=j,starts=x-.5,ends=x+.5,y=a['p'],sigma=B.context(a)['sigma_p'],train=np.ones(n,bool)));vectors.append(a['p'])
(HERE/'native/labs').mkdir(parents=True,exist_ok=False)
cp,cpmeta=H.cp_batch(cases,'native/cpop');labs,lbmeta=H.labs_batch(vectors,'native/labs');curves={key:dict(cpop=cp[j],labs=labs[j]) for j,key in enumerate(ids)}
save('native_curves.json',curves);save('native_receipt.json',dict(cpop=cpmeta,labs=lbmeta))
parent_model=B.read(PARENT/'model.json');state_model=B.read(PARENT/'state_v2/model.json');pred=[]
for row in rows:
    curve=curves.get(row['event_id'],{}).get('cpop',{}).get('prediction',[]);base=B.predictions([row],curves,3)[0];base['methods']['candidate']=A.infer(row,curve,parent_model,state_model);pred.append(base)
stats=B.score(rows,pred);old=stats['cpop'];new=stats['candidate']
save('predictions.json',pred);save('scores.json',stats);save('assessment.json',dict(status='additional_real_development_confirmation',same_validation_users_new_nonoverlapping_windows=True,comparison=stats,detection_noninferiority=new['false_positive']<=old['false_positive'] and new['false_negative']<=old['false_negative'],recovery_improved=new['recovery']['capped_interval_mae_seconds']<old['recovery']['capped_interval_mae_seconds'],no_extra_censored_return=new['spurious_recovery']<=old['spurious_recovery'],frozen_before_selection_and_labels=True,retrained_or_retuned=False,independent_gold=False,production_adopt=False,test_values_read=False))
print(json.dumps(stats),flush=True)
