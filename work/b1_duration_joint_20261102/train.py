from common import *
from model import adopted,features,true_durations,eligible
from features_source import export
from b1_algorithm.process import _local_response as LR
from sklearn.ensemble import HistGradientBoostingRegressor

def sources():
    all_cases=[];all_truth={};all_curves={};ledger={}
    def add(directory,cases,truth,curves):
        for c in cases:
            tid=c['task_id']
            if tid in ledger:continue
            f=dict(curves[tid]['results'])
            if 'retained' in f:f['duration_fusion']=f.pop('retained')
            all_cases.append(c);all_truth[tid]=truth[tid];all_curves[tid]=f;ledger[tid]=directory.as_posix()
    for stage in ['validation','stress','test']:
        directory=OLD/stage;curves={r['task_id']:r for r in read(directory/'curves.json')};truth={};cases=[]
        for panel in ['minute','10s']:
            cases+=read(directory/panel/'facts.json');truth.update({r['task_id']:r for r in read(directory/panel/'truth.json')})
        add(directory,cases,truth,curves)
    for name,stages in [('b1_false_unknown_20261101',['validation','test']),('b1_false_unknown_v2_20261101',['test'])]:
        for stage in stages:
            directory=ROOT/'work'/name/stage;curves={r['task_id']:r for r in read(directory/'curves.json')};truth={}
            for panel in ['minute','10s']:truth.update({r['task_id']:r for r in read(directory/f'known_{panel}/truth.json')})
            add(directory,[c for c in read(directory/'all_facts.json') if c['regime']=='known'],truth,curves)
    for name,stages in [('b1_known_weak_20261101',['train_stress']),('b1_known_functional_20261101',['test','stress_test','stress_continuous']),('b1_local_rescue_20261101',['validation','main_test','weak_test']),('b1_local_rescue_v2_20261102',['main_test','weak_test'])]:
        for stage in stages:
            directory=ROOT/'work'/name/stage;truth={}
            for panel in ['minute','10s']:
                for label in ['truth.json','mixed_truth.json']:truth.update({r['task_id']:r for r in read(directory/panel/label)})
            add(directory,read(directory/'facts.json'),truth,{r['task_id']:r for r in read(directory/'curves.json')})
    return all_cases,all_truth,all_curves,ledger

def main():
    cases,truth,curves,ledger=sources();baseline,xx=adopted(cases,curves);X=[];Y=[];W=[];ids=[]
    for i,c in enumerate(cases):
        if not eligible(c,baseline[i]):continue
        f=curves[c['task_id']];clean=np.asarray(truth[c['task_id']]['true_reduction_kw']);dt=c['ends_s'][0]-c['starts_s'][0];actual=true_durations(clean,c['starts_s'],dt)
        X.append(features(c,f['cpop']['prediction'],f['duration_fusion']['prediction'],baseline[i],xx[i]));Y.append([actual[0]/1800.,actual[1]/max(actual[0],dt),actual[1]/1800.]);W.append(3. if 0.04<max(clean)<=.35 else 1.);ids.append(c['task_id'])
    X=np.vstack(X);Y=np.asarray(Y);W=np.asarray(W);np.save(HERE/'training_X.npy',X);np.save(HERE/'training_Y.npy',Y)
    for leaves in read('protocol.json')['leaves']:
        for j,label in enumerate(['cumulative','fraction','absolute']):
            m=HistGradientBoostingRegressor(loss='quantile',quantile=.5,max_leaf_nodes=leaves,max_iter=read('protocol.json')['iterations'],learning_rate=.06,min_samples_leaf=20,l2_regularization=10.,early_stopping=False,random_state=7780000+j).fit(X,Y[:,j],sample_weight=W)
            payload=export(m);assert np.max(abs(LR.fast_predict(payload,X)-m.predict(X)))<1e-9;write(f'{label}{leaves}.json',payload);print('trained',label,leaves,X.shape,flush=True)
    write('training_receipt.json',dict(known_tasks=len(cases),eligible_tasks=len(X),features=X.shape[1],eligible_task_ids=ids,source_ledger=ledger,
        standard_HGB_not_new_solver=True,export_exact=True,no_current_validation_or_final_used=True,prior_tests_explicitly_development=True))
if __name__=='__main__':main()
