from adapter import *
HERE=Path(__file__).resolve().parent
def save(n,v):
    p=HERE/n;p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8') as f:json.dump(B.native(v),f,ensure_ascii=False,indent=2,allow_nan=False)
freeze=B.read(HERE/'selection_freeze.json')
for name,value in freeze['sources'].items():assert B.sha(HERE/name)==value
assert B.sha(HERE/'model.json')==freeze['model_sha256'] and B.sha(PARENT/'adapter.py')==freeze['parent_source_sha256'] and B.sha(PARENT/'model.json')==freeze['parent_model_sha256']
parent_model=B.read(PARENT/'model.json');model=B.read(HERE/'model.json');rows=B.load('validation');curves=B.read(B.HERE/'validation/native_curves.json');pred=[]
for row in rows:
    cp=curves.get(row['event_id'],{}).get('cpop',{}).get('prediction',[]);adapted=infer(row,cp,parent_model,model);base=B.predictions([row],curves,3)[0];base['methods']['candidate']=adapted;pred.append(base)
stats=B.score(rows,pred);old=stats['cpop'];new=stats['candidate']
save('validation/predictions.json',pred);save('validation/scores.json',stats)
save('assessment.json',dict(status='retained_real_observed_v2_development_validation',parent_method='effective_response_refined',retained_architecture=['CPOP','retained50_column_numeric_features','raw_local_rescue_with_real_trained_qualification','learned_observed_recovery_calibration'],old_physical_weights_outside_domain_not_used=True,comparison=stats,detection_noninferiority=new['false_positive']<=old['false_positive'] and new['false_negative']<=old['false_negative'],recovery_improved=new['recovery']['capped_interval_mae_seconds']<old['recovery']['capped_interval_mae_seconds'],no_new_censored_return=new['spurious_recovery']<=old['spurious_recovery'],production_adopt=False,independent_gold=False,test_values_read=False))
print(json.dumps(stats),flush=True)
