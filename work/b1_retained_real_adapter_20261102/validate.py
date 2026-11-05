from pathlib import Path
from adapter import *
HERE=Path(__file__).resolve().parent
def save(n,v):
    p=HERE/n;p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8') as f:json.dump(B.native(v),f,ensure_ascii=False,indent=2,allow_nan=False)
freeze=B.read(HERE/'selection_freeze.json')
for name,value in freeze['sources'].items():assert B.sha(HERE/name)==value,name
assert B.sha(HERE/'model.json')==freeze['model_sha256']
payload=B.read(HERE/'model.json');rows=B.load('validation');curves=B.read(B.HERE/'validation/native_curves.json');pred=[]
for row in rows:
    cp=curves.get(row['event_id'],{}).get('cpop',{}).get('prediction',[])
    adapted=infer(row,cp,payload);base=B.predictions([row],curves,3)[0];base['methods']['candidate']=adapted;pred.append(base)
stats=B.score(rows,pred);old=stats['cpop'];new=stats['candidate']
save('validation/predictions.json',pred);save('validation/scores.json',stats)
assessment=dict(status='retained_method_real_observation_adaptation_development_result',parent_method='effective_response_refined',same_CPOP_curves=True,training_event_labels=62,training_recovery_targets=22,selected_recovery_mix=payload['recovery_mix'],rescue_threshold=payload['rescue_threshold'],comparison=stats,detection_noninferiority=new['false_positive']<=old['false_positive'] and new['false_negative']<=old['false_negative'],boundary_improved=new['joint_capped_interval_mae_seconds']<old['joint_capped_interval_mae_seconds'],no_extra_censored_return=new['spurious_recovery']<=old['spurious_recovery'],adopt_production=False,reason='Real-observed research branch; old physical-duration targets and independent gold unavailable. Development validation already seen; final test closed.',test_values_read=False)
save('assessment.json',assessment)
print(json.dumps(assessment),flush=True)
