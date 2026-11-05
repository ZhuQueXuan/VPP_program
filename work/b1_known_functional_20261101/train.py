from common import *
from model import input_features,durations
from candidate import export,tree_predict
from sklearn.ensemble import HistGradientBoostingClassifier,HistGradientBoostingRegressor

DEV=ROOT/'work/b1_known_weak_20261101'

def load_development():
    helper=load(DEV/'train.py','existing_known_training_sources');sources=helper.previous();truth=helper.truth_for('train_stress')
    # Helpers resolve to this module's HERE; use explicit paths for the newly
    # generated training panel retained in the first attempt.
    return sources

def main():
    helper=load(DEV/'train.py','old_known_training_source');sources=helper.previous();truth={}
    for panel in ['minute','10s']:
        for name in ['truth.json','mixed_truth.json']:truth.update({r['task_id']:r for r in read(DEV/'train_stress'/panel/name)})
    curves={r['task_id']:r for r in read(DEV/'train_stress/curves.json')}
    for c in read(DEV/'train_stress/facts.json'):sources.append((c,truth[c['task_id']],curves[c['task_id']],'fresh_training_stress'))
    X=[];target=[];event=[];short=[];weight=[];ledger=[];seen=set()
    for c,t,r,source in sources:
        if c['task_id'] in seen:continue
        seen.add(c['task_id']);fits=r['results'];old=fits['duration_fusion' if 'duration_fusion' in fits else 'retained']['prediction'];cp=fits['cpop']['prediction'];s=np.array(c['starts_s']);use=(s>=0)&(s<1800);step=c['ends_s'][0]-s[0];clean=np.array(t['true_reduction_kw']);actual=durations(clean,s,step);before=durations(old,s,step);peak=float(clean[use].max())
        X.append(input_features(c,cp,old));target.append(actual-before);event.append(peak>.04);short.append(0<actual[0]<=60.+1e-8);weight.append(4. if .04<peak<=.3 else 1.);ledger.append(dict(task_id=c['task_id'],source=source))
    X=np.vstack(X);Y=np.array(target);EY=np.array(event);short=np.array(short);weights=np.array(weight);names=[]
    for leaves in read('protocol.json')['duration_leaves']:
      for index,label in enumerate(['cumulative','longest']):
        m=HistGradientBoostingRegressor(loss='quantile',quantile=.5,max_leaf_nodes=leaves,max_iter=180,learning_rate=.06,min_samples_leaf=20,l2_regularization=10.,early_stopping=False,random_state=7740000+index).fit(X,Y[:,index],sample_weight=weights)
        payload=export(m);assert np.max(abs(tree_predict(payload,X)-m.predict(X)))<1e-9
        name=f'{label}_leaves{leaves}.json';write(name,payload);names.append(name)
    W=np.where(EY,.5/EY.mean(),.5/(1-EY.mean()))*np.where(short,10.,1.)
    m=HistGradientBoostingClassifier(max_leaf_nodes=15,max_iter=180,learning_rate=.05,min_samples_leaf=20,l2_regularization=10.,early_stopping=False,random_state=7740001).fit(X,EY,sample_weight=W);payload=export(m)
    assert np.max(abs(expit(tree_predict(payload,X))-m.predict_proba(X)[:,1]))<1e-12;write('physical_event_model.json',payload)
    write('training_receipt.json',dict(cases=len(X),features=X.shape[1],models=names,physical_event_target='Peak physical action>0.04, not threshold crossing',true_short_cases=int(short.sum()),ledger=ledger,export_exact=True,reference_prediction_not_used=True))
    print('functional models trained',X.shape,flush=True)
if __name__=='__main__':main()
