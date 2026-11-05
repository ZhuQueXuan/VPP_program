from common import *
from source_data import sources
from model import current_baseline,scope
from features_source import export
from b1_algorithm.process import _local_response as LR,_known_duration as KD
from sklearn.ensemble import HistGradientBoostingClassifier

def main():
    cases,truth,curves,ledger=sources()
    previous=ROOT/'work/b1_duration_joint_20261102'
    for stage in ['main_validation','weak_validation','main_test','weak_test']:
        directory=previous/stage;tt={}
        for panel in ['minute','10s']:
            for name in ['truth.json','mixed_truth.json']:tt.update({r['task_id']:r for r in read(directory/panel/name)})
        ff={r['task_id']:r['results'] for r in read(directory/'curves.json')}
        for c in read(directory/'facts.json'):
            tid=c['task_id']
            if tid in truth:continue
            f=ff[tid]
            if 'retained' in f:f['duration_fusion']=f.pop('retained')
            cases.append(c);truth[tid]=tt[tid];curves[tid]=f;ledger[tid]=directory.as_posix()
    base,masks,X=current_baseline(cases,curves);use=[];Y=[];W=[];ids=[]
    for i,c in enumerate(cases):
        if not scope(c,base[i]):continue
        s=np.asarray(c['starts_s']);dt=c['ends_s'][0]-s[0];actual=KD.durations(truth[c['task_id']]['true_reduction_kw'],s,dt);positive=actual[0]>0
        use.append(i);Y.append(positive);W.append(50. if 0<actual[0]<=60.+1e-8 else 5. if positive else 1.);ids.append(c['task_id'])
    X=X[use];Y=np.asarray(Y);W=np.asarray(W);np.save(HERE/'training_X.npy',X);np.save(HERE/'training_Y.npy',Y)
    for leaves in read('protocol.json')['leaves']:
        m=HistGradientBoostingClassifier(max_leaf_nodes=leaves,max_iter=read('protocol.json')['iterations'],learning_rate=.05,min_samples_leaf=30,l2_regularization=10.,early_stopping=False,random_state=7790000).fit(X,Y,sample_weight=W)
        payload=export(m);assert np.max(abs(expit(LR.fast_predict(payload,X))-m.predict_proba(X)[:,1]))<1e-12
        write(f'verifier{leaves}.json',payload);print('trained effective verifier',leaves,X.shape,flush=True)
    write('training_receipt.json',dict(known_tasks=len(cases),eligible_tasks=len(X),features=X.shape[1],positive_tasks=int(Y.sum()),eligible_ids=ids,source_ledger=ledger,
        old_tests_explicitly_development=True,no_current_validation_final_used=True,original_effective_truth_unchanged=True,physical_change_not_negated=True,export_exact=True))
if __name__=='__main__':main()
