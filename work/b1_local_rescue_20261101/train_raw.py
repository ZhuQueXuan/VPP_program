from common import *
from raw_features import raw_features
from features_source import export
from evaluate import fast_predict
from sklearn.ensemble import HistGradientBoostingClassifier

def main():
    sources=[]
    for stage in ['validation','stress','test']:
        directory=OLD/stage
        for panel in ['minute','10s']:
            tt={r['task_id']:r for r in read(directory/panel/'truth.json')}
            for c in read(directory/panel/'facts.json'):sources.append((c,tt[c['task_id']],str(directory)))
    for name,stages in [('b1_false_unknown_20261101',['validation','test']),('b1_false_unknown_v2_20261101',['test'])]:
        for stage in stages:
            directory=ROOT/'work'/name/stage;tt={}
            for panel in ['minute','10s']:tt.update({r['task_id']:r for r in read(directory/f'known_{panel}/truth.json')})
            for c in read(directory/'all_facts.json'):
                if c['regime']=='known':sources.append((c,tt[c['task_id']],str(directory)))
    for directory,stages in [(ROOT/'work/b1_known_weak_20261101',['train_stress']),(ROOT/'work/b1_known_functional_20261101',['test','stress_test','stress_continuous']),(HERE,['training'])]:
        for stage in stages:
            tt={}
            for panel in ['minute','10s']:
                for name in ['truth.json','mixed_truth.json']:tt.update({r['task_id']:r for r in read(directory/stage/panel/name)})
            for c in read(directory/stage/'facts.json'):sources.append((c,tt[c['task_id']],str(directory/stage)))
    xs=[];ys=[];ws=[];seen=set();ledger=[]
    for index,(c,t,origin) in enumerate(sources):
        tid=c['task_id']
        if tid in seen:continue
        seen.add(tid);s=np.asarray(c['starts_s']);task=(s>=0)&(s<1800);clean=np.asarray(t['true_reduction_kw']);raw=np.asarray(c['reference_kw'])-np.asarray(c['power_kw']);label=clean>=.15;genuine=c['kind'] in ['one_bin_response','one_minute_response','one_finebin_response'];weak=(clean>.04)&(clean<=.3)
        keep=(np.arange(len(s))%8==index%8)|((abs(raw)>.07)&(abs(raw)<.4)&task)|(weak&task)
        if genuine:keep|=task
        X=raw_features(c);w=np.ones(len(s));w[weak&label]=3.;w[genuine&label&task]=20.;w[(~label)&(raw>.1)&task]=5.
        xs.append(X[keep]);ys.append(label[keep]);ws.append(w[keep]);ledger.append(dict(task_id=tid,source=origin))
    X=np.vstack(xs);Y=np.concatenate(ys);W=np.concatenate(ws)
    for leaves in [31,63]:
        model=HistGradientBoostingClassifier(max_leaf_nodes=leaves,max_iter=220,learning_rate=.06,min_samples_leaf=40,l2_regularization=10.,early_stopping=False,random_state=7750000).fit(X,Y,sample_weight=W)
        payload=export(model);test=X[::max(1,len(X)//1000)];assert np.max(abs(expit(fast_predict(payload,test))-model.predict_proba(test)[:,1]))<1e-12
        write(f'raw{leaves}.json',payload);print('raw model',leaves,'trained',X.shape,flush=True)
    write('raw_training_receipt.json',dict(tasks=len(seen),rows=len(X),features=X.shape[1],ledger=ledger,
        no_CPOP_or_true_shape_fields_in_features=True,genuine_positive_weight=20,hard_negative_weight=5,weak_positive_weight=3,
        all_current_validation_and_final_excluded=True,old_test_explicitly_development=True,export_exact=True))
if __name__=='__main__':main()
