from common import *
rows=load('training');curves=fit_native(rows,'training');scores=[]
for k in [2,3,4]:
    pred=predictions(rows,curves,k);stats=score(rows,pred);save(f'training/predictions_k{k}.json',pred);save(f'training/scores_k{k}.json',stats)
    cp=stats['cpop'];new=stats['candidate'];safe=new['false_positive']<=cp['false_positive'] and new['false_negative']<=cp['false_negative']
    scores.append(dict(k=k,safe=safe,candidate=new,cpop=cp))
chosen=min(scores,key=lambda v:(not v['safe'],max(0,v['candidate']['false_positive']-v['cpop']['false_positive']),max(0,v['candidate']['false_negative']-v['cpop']['false_negative']),v['candidate']['joint_capped_interval_mae_seconds'],v['k']))
save('training/selection.json',dict(configurations=scores,selected=chosen,selection_uses_training_only=True))
save('selection_freeze.json',dict(created_utc=now(),selected_k=chosen['k'],training_safety_passed=chosen['safe'],before_validation_algorithm_outputs=True,source_sha256={p.name:sha(p) for p in [HERE/'protocol.json',HERE/'common.py',HERE/'train_select.py']},input_training_sha256=sha(VIEW/'training.json'),input_validation_sha256=sha(VIEW/'validation.json'),validation_labels_not_used_for_selection=True))
print(json.dumps(dict(selected_k=chosen['k'],safe=chosen['safe'],training_comparison=chosen)),flush=True)
