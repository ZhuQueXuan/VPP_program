from common import *
from task_model import features,export
from sklearn.ensemble import HistGradientBoostingClassifier
import sklearn

def labels(stage):
    output={}
    paths=[HERE/stage/'unknown/truth.json']
    if stage!='train':paths += [HERE/stage/f'known_{p}/truth.json' for p in ['minute','10s']]
    for path in paths:output.update({r['task_id']:r for r in read(path)})
    return output

def evaluate(stage,model=None,threshold=None,name='candidate'):
    cases=read(stage+'/all_facts.json');curves={r['task_id']:r for r in read(stage+'/curves.json')};truth=labels(stage)
    probs=expit(DF._tree_predict(model,np.load(HERE/stage/'features.npy'))) if model else None;rows=[]
    for i,c in enumerate(cases):
        fits=curves[c['task_id']]['results'];s=np.array(c['starts_s']);step=float(c['ends_s'][0]-s[0]);t=np.array(truth[c['task_id']]['true_reduction_kw'])
        if model:
            original=np.array(fits['retained']['prediction']);accepted=bool(probs[i]>=threshold)
            fits=dict(fits,**{name:dict(status='ok',prediction=original if accepted else np.zeros(len(original)),score=float(probs[i]),accepted=accepted)})
        for method,fit in fits.items():
            assert fit['status']=='ok'
            m=measure(fit['prediction'],t,s,step)
            short=m['positive_truth'] and m['true_cumulative_seconds']<=60.+1e-8
            r={k:c[k] for k in ['task_id','base_task_id','regime','panel','seed','kind','condition']}
            r.update(method=method,status=fit['status'],short_n=short,short_local_miss=short and m['localized_miss'],**m)
            if model and method==name:r.update(score=fit['score'],accepted=fit['accepted'])
            rows.append(r)
    return rows

def train():
    X=[];Y=[];regimes=[];ledger=[]
    for stage in ['validation','stress','test']:
        curves={r['task_id']:r for r in read(OLD/stage/'curves.json')}
        for panel in ['minute','10s']:
            truth={r['task_id']:r for r in read(OLD/stage/panel/'truth.json')}
            for c in read(OLD/stage/panel/'facts.json'):
                c['regime']='known';fit=curves[c['task_id']]['results'];s=np.array(c['starts_s']);t=np.array(truth[c['task_id']]['true_reduction_kw'])
                X.append(features(c,fit['cpop']['prediction'],fit['duration_fusion']['prediction']));Y.append(bool(np.any(t[(s>=0)&(s<1800)]>=.15)));regimes.append('known')
                ledger.append(dict(task_id=c['task_id'],source='previous_release_seen_'+stage,regime='known'))
    cases=read('train/all_facts.json');truth=labels('train');unknownX=np.load(HERE/'train/features.npy')
    for c,x in zip(cases,unknownX):
        s=np.array(c['starts_s']);t=np.array(truth[c['task_id']]['true_reduction_kw']);X.append(x);Y.append(bool(np.any(t[(s>=0)&(s<1800)]>=.15)));regimes.append('unknown');ledger.append(dict(task_id=c['task_id'],regime='unknown',source='fresh_training'))
    X=np.vstack(X);Y=np.array(Y);weights=np.array([len(regimes)/(2*regimes.count(r)) for r in regimes]);spec=read('protocol.json')['models'];models=[]
    for leaves in spec['leaves']:
        model=HistGradientBoostingClassifier(max_leaf_nodes=leaves,max_iter=spec['iterations'],learning_rate=spec['learning_rate'],min_samples_leaf=spec['min_leaf'],l2_regularization=spec['l2'],early_stopping=False,random_state=7710000).fit(X,Y,sample_weight=weights)
        payload=export(model);p=expit(DF._tree_predict(payload,X));assert np.max(abs(p-model.predict_proba(X)[:,1]))<1e-12
        name=f'model_leaves{leaves}.json';write(name,payload);models.append(name)
    write('training_ledger.json',dict(n=len(Y),positive=int(Y.sum()),features=X.shape[1],by_regime={r:regimes.count(r) for r in set(regimes)},rows=ledger,
        sklearn=sklearn.__version__,model_export_exact=True,features_exclude=['kind','condition','seed','truth','user_id','task_id'],
        reused_prior_seen_tests_for_NEW_classifier=True,previous_adopted_model_retrained=False))
    np.savez_compressed(HERE/'training_arrays.npz',X=X,y=Y,weights=weights)
    write('training_models.json',models);print('trained',X.shape,flush=True)

def choose():
    all_summary=[];eligible=[]
    for modelpath in read('training_models.json'):
      for threshold in read('protocol.json')['thresholds']:
        rows=evaluate('validation',read(modelpath),threshold);ss=summary(rows);by={(r['regime'],r['method']):r for r in ss};valid=True;score=0.
        for regime in ['known','unknown']:
            a=by[regime,'candidate'];cp=by[regime,'cpop'];old=by[regime,'retained']
            valid &= a['null_false_positive']<cp['null_false_positive'] and a['short_local_miss']<=old['short_local_miss']
            valid &= a['whole_miss']<=old['whole_miss']+.01*max(1,old['positive_truth']) and a['localized_miss']<=old['localized_miss']+.01*max(1,old['positive_truth'])
            valid &= a['primary_seconds']<=cp['primary_seconds'] and a['primary_seconds']<=old['primary_seconds']+5.
            score+=a['null_false_positive']/max(1,cp['null_false_positive'])+.25*a['primary_seconds']/max(.1,old['primary_seconds'])
        entry=dict(model=modelpath,threshold=threshold,eligible=bool(valid),score=score,summary=ss);all_summary.append(entry)
        if valid:eligible.append(entry)
    write('validation_selection.json',all_summary)
    eligible.sort(key=lambda r:r['score']);write('eligible.json',eligible)
    if not eligible:print('NO candidate meets validation criteria',flush=True);return
    selected=eligible[0];write('selected.json',selected)
    source=[p for p in HERE.glob('*.py')]+[HERE/'protocol.json',HERE/'selected.json',HERE/selected['model']]
    source += [ROOT/'work/b1_reliability_20261031/study/generator.py',ROOT/'work/b1_ev_mainline_20261030/simulation.py',ROOT/'work/b1_reliability_20261031/study/models/reliable_reference.json']
    source += [p for p in (ROOT/'B1算法').rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    write('test_freeze.json',dict(selected_model_sha256=sha(HERE/selected['model']),source_sha256={p.relative_to(ROOT).as_posix():sha(p) for p in source},test_not_generated=True))
    write('validation_metrics.json',evaluate('validation',read(selected['model']),selected['threshold']))
    print(json.dumps(native(selected)),flush=True)
if __name__=='__main__':globals()[sys.argv[1]]()
