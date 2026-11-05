import os
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='1'
from adapter import *
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold
HERE=Path(__file__).resolve().parent
def save(n,v):
    p=HERE/n;p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8') as f:json.dump(B.native(v),f,ensure_ascii=False,indent=2,allow_nan=False)
parent_model=B.read(PARENT/'model.json');assert parent_model['recovery_mix']==0
for name,value in B.read(PARENT/'selection_freeze.json')['sources'].items():assert B.sha(PARENT/name)==value
rows=B.load('training');curves=B.read(B.HERE/'training/native_curves.json');registry={r['event_id']:r for r in B.read(B.VIEW/'registry.json')}
records=[];row_groups=[]
for row in rows:
    target=row['provisional_targets'];interval=target['recovery_completion_bracket_seconds'];cp=curves.get(row['event_id'],{}).get('cpop',{}).get('prediction',[])
    a=B.arrays(row);initial=P.infer(row,cp,parent_model)
    if a is None or target['anchor_visible_following']!=1 or not initial['detected']:continue
    if interval is None and target['recovery_status'] not in CENSORED:continue
    points=state_points(a,cp,initial['onset_seconds']);positive=[];negative=[]
    for point in points:
        if interval is not None and point['time']==interval[1]:positive.append(point)
        elif point['eligible'] and (interval is None or point['time']<interval[0]):negative.append(point)
    for label,block,total_weight in [(1,positive,.5),(0,negative,.5 if positive else 1.)]:
        for point in block:records.append(dict(event_id=row['event_id'],user_group=registry[row['event_id']]['user_group'],x=point['features'],label=label,weight=total_weight/len(block),time=point['time'],eligible=point['eligible']))
    row_groups.append(row)
X=np.array([r['x'] for r in records]);y=np.array([r['label'] for r in records]);w=np.array([r['weight'] for r in records]);g=np.array([r['user_group'] for r in records]);assert 0<np.sum(y)<len(y)
# This head is conditional on an existing/rescued event. An upstream missed
# event remains a failure in the22-reference full-trajectory score; it does not
# become a manufactured detected event merely to create a training endpoint.
save('training/eligibility.json',dict(all_recovery_targets=sum(r['provisional_targets']['recovery_completion_bracket_seconds'] is not None for r in rows),reachable_endpoint_labels=int(np.sum(y)),upstream_missed_targets_remain_in_full_trajectory_scoring=True))
def fit(indices):
    scaler=StandardScaler().fit(X[indices],sample_weight=w[indices]);lr=LogisticRegression(C=1.,max_iter=2000,random_state=20261102).fit(scaler.transform(X[indices]),y[indices],sample_weight=w[indices])
    return dict(mean=scaler.mean_.tolist(),scale=scaler.scale_.tolist(),coef=lr.coef_[0].tolist(),intercept=float(lr.intercept_[0]))
oof_models={};folds=[]
for fold,(tr,va) in enumerate(GroupKFold(4).split(X,y,g)):
    assert not set(g[tr])&set(g[va]);model=fit(tr)
    for user in set(g[va]):oof_models[user]=model
    folds.append(dict(fold=fold,fit_users=sorted(set(g[tr])),held_users=sorted(set(g[va]))))
configs=[]
for threshold in [.5,.7,.9]:
    pred=[]
    for row in rows:
        cp=curves.get(row['event_id'],{}).get('cpop',{}).get('prediction',[]);user=registry[row['event_id']]['user_group'];model=oof_models.get(user)
        adapted=infer(row,cp,parent_model,dict(model=model,threshold=threshold)) if model is not None else P.infer(row,cp,parent_model)
        base=B.predictions([row],curves,3)[0];base['methods']['candidate']=adapted;pred.append(base)
    stats=B.score(rows,pred);old=stats['cpop'];new=stats['candidate'];safe=new['spurious_recovery']<=old['spurious_recovery'] and new['recovery']['missing']<=old['recovery']['missing'] and new['false_positive']<=old['false_positive'] and new['false_negative']<=old['false_negative']
    configs.append(dict(threshold=threshold,safe=safe,stats=stats));save(f'training/oof_scores_{threshold}.json',stats);save(f'training/oof_predictions_{threshold}.json',pred)
chosen=min(configs,key=lambda r:(not r['safe'],r['stats']['candidate']['joint_capped_interval_mae_seconds'],r['threshold']))
payload=dict(schema='b1.retained-real-recovery-state.v2',parent_method='effective_response_refined',model=fit(np.arange(len(X))),threshold=chosen['threshold'],features=['recorded_power_distance_fraction_of_past_excursion','recorded_current_distance_fraction_of_past_excursion'],physical_effective_duration_supervision=False)
save('model.json',payload);save('training/point_labels.json',records);save('training/selection.json',dict(configurations=configs,chosen=chosen,folds=folds,point_training_rows=len(records),positive_recovery_endpoints=int(np.sum(y)),users=len(set(g))))
save('selection_freeze.json',dict(created_utc=B.now(),sources={p.name:B.sha(p) for p in [HERE/'adapter.py',HERE/'train.py',HERE/'protocol.json']},model_sha256=B.sha(HERE/'model.json'),parent_source_sha256=B.sha(PARENT/'adapter.py'),parent_model_sha256=B.sha(PARENT/'model.json'),before_new_branch_validation=True,validation_not_fitted_or_threshold_selected=True,previous_validation_is_seen_development=True))
print(json.dumps(dict(point_rows=len(records),recovery_endpoints=int(np.sum(y)),users=len(set(g)),selected_threshold=chosen['threshold'],safe=chosen['safe'],oof_comparison=chosen['stats'])),flush=True)
