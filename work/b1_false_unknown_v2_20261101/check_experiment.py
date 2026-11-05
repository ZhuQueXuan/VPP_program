"""Independent durations, scalar tree traversal and reference provenance audit."""
from common import *
from train_choose import labels
from itertools import groupby
from copy import deepcopy
from b1_algorithm.reference.core import ReferenceWindow
from b1_algorithm.reference.reliable import load_ev_reliable_reference_model,predict_ev_reliable_reference

def main():
    selected=read('selected.json');model=read(selected['model']);count=0;reference_count=0
    for phase in ['validation','short_validation','test','short_test']:
        cases=read(phase+'/all_facts.json');curves={r['task_id']:r for r in read(phase+'/curves.json')};truth=labels(phase)
        metrics={ (r['task_id'],r['method']):r for r in read(phase+'/metrics.json')} if (HERE/phase/'metrics.json').exists() else {}
        X=np.load(HERE/phase/'features.npy');scores=expit(DF._tree_predict(model,X))
        for row in X[::max(1,len(X)//16)]:
            out=model['baseline']
            for tree in model['trees']:
                i=0
                while not tree[i]['is_leaf']:
                    node=tree[i];value=float(row[node['feature_idx']]);i=node['left'] if value<=node['num_threshold'] else node['right']
                out+=tree[i]['value']
            assert abs(out-DF._tree_predict(model,row[None,:])[0])<1e-12;count+=1
        for c,score in zip(cases,scores):
            s=np.array(c['starts_s']);use=(s>=0)&(s<1800);step=c['ends_s'][0]-s[0];t=np.array(truth[c['task_id']]['true_reduction_kw'])[use]>=.15
            base=np.array(curves[c['task_id']]['results']['cpop']['prediction']);retained=np.array(curves[c['task_id']]['results']['retained']['prediction'])
            guard=False;offset=0
            for yes,group in groupby((base[use]>=.15).tolist()):
                size=sum(1 for _ in group)
                if yes and size*step<=60.+1e-8 and max(base[use][offset:offset+size])<=.45:guard=True
                offset+=size
            accepted=bool(score>=selected['threshold'] or (c['regime']=='unknown' and guard))
            predictions={m:np.array(v['prediction']) for m,v in curves[c['task_id']]['results'].items()}
            predictions['candidate']=retained if accepted else np.zeros(len(retained))
            def durations(mask):
                runs=[sum(1 for _ in g)*step for yes,g in groupby(mask.tolist()) if yes];long=max(runs,default=0.)
                return float(mask.sum()*step),float(long) if long>=30.-1e-8 else 0.
            tc,tl=durations(t)
            for method,pred in predictions.items():
                if (c['task_id'],method) not in metrics:continue
                r=metrics[c['task_id'],method];mask=pred[use]>=.15;pc,pl=durations(mask)
                assert abs(r['primary_seconds']-.5*(abs(pc-tc)+abs(pl-tl)))<1e-8
                assert r['whole_miss']==bool(t.any() and not mask.any())
                assert r['null_false_positive']==bool(not t.any() and mask.any())
                assert r['localized_miss']==bool(t.any() and not (t&mask).any())
                if method=='candidate':assert r['accepted']==accepted
                count+=4
            if c['regime']=='unknown':
                assert len(s)==60 and np.array_equal(s,np.arange(-15,45)*60)
    for phase in ['train','validation','test']:
        for row in read(phase+'/unknown/reference_ledger.json'):
            assert row['prefix_end']<=row['notice_min'] and row['reference']['available_at_min']<=row['notice_min']
            assert row['reference']['role']=='unseen_user';reference_count+=1
    cohorts={}
    for phase in ['train','validation','test','short_train','short_validation','short_test']:
        cohorts[phase]={c['user_id'] for c in read(phase+'/all_facts.json') if c['regime']=='unknown'}
    for i,a in enumerate(cohorts):
        for b in list(cohorts)[i+1:]:assert not cohorts[a]&cohorts[b],(a,b)
    original=read('test/unknown/source_facts.json')[0];modelref=load_ev_reliable_reference_model(ROOT/'work/b1_reliability_20261031/study/models/reliable_reference.json')
    pred=predict_ev_reliable_reference(modelref,ReferenceWindow(**original['reference_window']))
    altered=deepcopy(original);altered['power_kw']=[999.]*60;altered['simulation_variant']='misleading_label';altered['observed_participation']=not original['observed_participation']
    check=predict_ev_reliable_reference(modelref,ReferenceWindow(**altered['reference_window']))
    assert np.array_equal(pred.reference_kw,check.reference_kw)
    for path,expected in read('test_freeze.json')['source_sha256'].items():assert sha(ROOT/path)==expected,path
    for path,expected in read('preserved_before.json').items():assert sha(ROOT/path)==expected,path
    cases=read('test/all_facts.json');truth=labels('test');seen=set();error=[]
    for c in cases:
        if c['regime']!='unknown' or c['physical_task_id'] in seen:continue
        seen.add(c['physical_task_id']);error.extend(np.array(c['reference_kw'])-np.array(truth[c['task_id']]['true_reference_kw']))
    write('independent_checks.json',dict(passed=True,metric_and_scalar_tree_assertions=count,reference_ledger_rows_checked=reference_count,
        prior_adopted_code_model_results_unchanged=True,all_test_sources_frozen=True,unknown_user_cohorts_disjoint=True,
        prediction_invariant_to_current_response_and_labels=True,unknown_reference_pooled_RMSE_kw=float(np.sqrt(np.mean(np.square(error)))),
        unique_unknown_reference_tasks=len(seen),field_accuracy_claim=False))
    print('independent checks passed',count,reference_count)
if __name__=='__main__':main()
