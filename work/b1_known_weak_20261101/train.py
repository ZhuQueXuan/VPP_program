from common import *
from candidate import state_features,export,tree_predict
from task_model import features as event_features
from sklearn.ensemble import HistGradientBoostingClassifier

def truth_for(stage):
    out={}
    for panel in ['minute','10s']:
        for name in ['truth.json','mixed_truth.json']:out.update({t['task_id']:t for t in read(stage+'/'+panel+'/'+name)})
    return out

def previous():
    sources=[]
    for stage in ['validation','stress','test']:
        directory=OLD/stage;cv={r['task_id']:r for r in read(directory/'curves.json')}
        for panel in ['minute','10s']:
            t={r['task_id']:r for r in read(directory/panel/'truth.json')}
            for c in read(directory/panel/'facts.json'):sources.append((c,t[c['task_id']],cv[c['task_id']],directory.as_posix()))
    for name,phases in [('b1_false_unknown_20261101',['validation','test']),('b1_false_unknown_v2_20261101',['test'])]:
      for stage in phases:
        directory=ROOT/'work'/name/stage;cv={r['task_id']:r for r in read(directory/'curves.json')};t={}
        for panel in ['minute','10s']:t.update({r['task_id']:r for r in read(directory/f'known_{panel}/truth.json')})
        for c in read(directory/'all_facts.json'):
            if c['regime']=='known':sources.append((c,t[c['task_id']],cv[c['task_id']],directory.as_posix()))
    return sources

def main():
    sources=previous();newtruth=truth_for('train_stress');newcurves={r['task_id']:r for r in read('train_stress/curves.json')}
    for c in read('train_stress/facts.json'):sources.append((c,newtruth[c['task_id']],newcurves[c['task_id']],'fresh_training_stress'))
    pointX=[];pointY=[];pointW=[];eventX=[];eventY=[];eventShort=[];ledger=[];seen=set()
    for index,(c,t,curve,source) in enumerate(sources):
        if c['task_id'] in seen:continue
        seen.add(c['task_id']);c=dict(c,regime='known');fits=curve['results'];cp=fits['cpop']['prediction'];old=fits['duration_fusion' if 'duration_fusion' in fits else 'retained']['prediction'];clean=np.array(t['true_reduction_kw']);s=np.array(c['starts_s']);task=(s>=0)&(s<1800);step=c['ends_s'][0]-s[0]
        X=state_features(c,cp);pick=np.arange(index%2,len(X),2);pointX.append(X[pick]);pointY.append((clean[pick]>=.15).astype(int));pointW.append(np.where(abs(clean[pick]-.15)<=.1,4.,1.))
        eventX.append(event_features(c,cp,old));eventY.append(bool(np.any(clean[task]>=.15)));eventShort.append(bool(0<np.sum(clean[task]>=.15)*step<=60.+1e-8));ledger.append(dict(task_id=c['task_id'],source=source))
    X=np.vstack(pointX);Y=np.concatenate(pointY);W=np.concatenate(pointW);E=np.vstack(eventX);EY=np.array(eventY);short=np.array(eventShort)
    spec=read('protocol.json');models=[]
    for leaves in spec['state_leaves']:
        name=f'state_leaves{leaves}.json'
        if (HERE/name).exists():models.append(name);continue
        m=HistGradientBoostingClassifier(max_leaf_nodes=leaves,max_iter=spec['state_iterations'],learning_rate=.06,min_samples_leaf=30,l2_regularization=10.,early_stopping=False,random_state=7740000).fit(X,Y,sample_weight=W)
        payload=export(m);check=X[::max(1,len(X)//1000)];assert np.max(abs(expit(tree_predict(payload,check))-m.predict_proba(check)[:,1]))<1e-12
        write(name,payload);models.append(name);print('state model',leaves,flush=True)
    weights=np.where(EY,.5/EY.mean(),.5/(1-EY.mean()))*np.where(short,10.,1.)
    m=HistGradientBoostingClassifier(max_leaf_nodes=15,max_iter=180,learning_rate=.05,min_samples_leaf=20,l2_regularization=10.,early_stopping=False,random_state=7740001).fit(E,EY,sample_weight=weights)
    payload=export(m);native=expit(tree_predict(payload,E));assert np.max(abs(native-m.predict_proba(E)[:,1]))<1e-12;write('event_model.json',payload)
    write('training_receipt.json',dict(cases=len(ledger),point_rows=len(X),point_features=X.shape[1],event_features=E.shape[1],positive_events=int(EY.sum()),true_short_events=int(short.sum()),
        models=models,event_model='event_model.json',model_export_exact=True,training_does_not_include_current_validation_or_test=True,
        all_inputs_known_reference=True,old_release_unchanged=True,ledger=ledger))
    print('training done',len(ledger),len(X),flush=True)
if __name__=='__main__':main()
