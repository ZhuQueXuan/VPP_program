import os
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='1'
from candidate import *
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold
oldpoints=read(PREVIOUS/'state_v2/training/point_labels.json');rows=B.load('training');by={r['event_id']:r for r in rows};curves=read(B.HERE/'training/native_curves.json');parent,oldmodel=parent_models();features={}
for row in rows:
    cp=curves.get(row['event_id'],{}).get('cpop',{}).get('prediction',[]);initial=P.infer(row,cp,parent)
    features[row['event_id']]={r['time']:r['features'] for r in points(B.arrays(row),cp,initial['onset_seconds'])}
records=[dict(r,x=features[r['event_id']][r['time']]) for r in oldpoints]
X=np.array([r['x'] for r in records]);y=np.array([r['label'] for r in records]);w=np.array([r['weight'] for r in records]);g=np.array([r['user_group'] for r in records])
def fit(ix):
    s=StandardScaler().fit(X[ix],sample_weight=w[ix]);m=LogisticRegression(C=1.,max_iter=2000,random_state=20261103).fit(s.transform(X[ix]),y[ix],sample_weight=w[ix])
    return dict(mean=s.mean_,scale=s.scale_,coef=m.coef_[0],intercept=float(m.intercept_[0]))
models={};folds=[]
for fold,(tr,va) in enumerate(GroupKFold(4).split(X,y,g)):
    assert not set(g[tr])&set(g[va]);model=fit(tr)
    for user in set(g[va]):models[user]=model
    folds.append(dict(fold=fold,fit_users=sorted(set(g[tr])),held_users=sorted(set(g[va]))))
registry={r['event_id']:r for r in read(B.VIEW/'registry.json')};pred=[]
for row in rows:
    cp=curves.get(row['event_id'],{}).get('cpop',{}).get('prediction',[]);user=registry[row['event_id']]['user_group'];model=models.get(user)
    new=infer(row,cp,parent,dict(model=model,threshold=.7)) if model is not None else P.infer(row,cp,parent)
    base=B.predictions([row],curves,3)[0];base['methods']['candidate']=new;pred.append(base)
stats=B.score(rows,pred);old=read(PREVIOUS/'state_v2/training/oof_scores_0.7.json')['candidate'];new=stats['candidate']
checks=dict(interval_gain1=new['recovery']['capped_interval_mae_seconds']<=.99*old['recovery']['capped_interval_mae_seconds'],endpoint_nonincrease=new['recovery']['capped_first_observed_mae_seconds']<=old['recovery']['capped_first_observed_mae_seconds'],missing_nonincrease=new['recovery']['missing']<=old['recovery']['missing'],spurious_nonincrease=new['spurious_recovery']<=old['spurious_recovery'],fp_nonincrease=new['false_positive']<=old['false_positive'],fn_nonincrease=new['false_negative']<=old['false_negative'])
save('training/point_labels.json',records);save('training/oof_predictions.json',pred);save('training/oof_scores.json',stats);save('training/folds.json',folds)
save('candidate_model.json',dict(schema='closing.recovery.v1',model=fit(np.arange(len(X))),threshold=.7,features=['relative_power_distance','relative_current_distance','log_absolute_power_distance_z','log_absolute_current_distance_z']))
save('training_decision.json',dict(candidate_eligible=all(checks.values()),checks=checks,retained_oof=old,candidate_oof=new,candidate_budget=1,no_validation_tuning=True))
paths=list(HERE.glob('*.py'))+[HERE/'protocol.json',HERE/'candidate_model.json',HERE/'training_decision.json']+[PREVIOUS/'adapter.py',PREVIOUS/'model.json',PREVIOUS/'state_v2/adapter.py',PREVIOUS/'state_v2/model.json']
paths += [ROOT/p for p in read(ROOT/'work/b1_residual_false_20261102/protected_before.json')]
save('model_freeze.json',dict(created_utc=now(),before_any_test_observation_read=True,files={p.relative_to(ROOT).as_posix():sha(p) for p in paths},candidate_eligible=all(checks.values()),test_budget=1))
print(json.dumps(native(dict(checks=checks,candidate_eligible=all(checks.values()),old_recovery=old['recovery'],new_recovery=new['recovery']))),flush=True)
