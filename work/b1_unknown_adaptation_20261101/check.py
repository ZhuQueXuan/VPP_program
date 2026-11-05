"""Independent duration, no-lookahead and staged public-output replay."""
from common import *
from error_tracking import predict
from itertools import groupby
from b1_algorithm.process.api import prepare

def main():
    model=read(read('error_tracking/selection.json')['selected']['model']);stage=load(HERE/'staged_reference_tracking.py','b1_algorithm.process._tracking_stage')
    stage._model=lambda:(model,sha(HERE/read('error_tracking/selection.json')['selected']['model']))
    count=0;replayed=0;references_before=[];references_after=[];seen=set();groups={};rmse=[]
    for phase in ['validation','test']:
        facts=read(phase+'/facts.json');truth={r['task_id']:r for r in read(phase+'/truth.json')};curves={r['task_id']:r for r in read(phase+'/curves.json')};metrics={(r['task_id'],r['method']):r for r in read(phase+'/metrics.json')};bias={r['task_id']:np.array(r['conditional_error_kw']) for r in read(phase+'/bias_prediction.json')}
        for i,c in enumerate(facts):
            s=np.array(c['starts_s']);e=np.array(c['ends_s']);use=(s>=0)&(s<1800);y=np.array(c['reference_kw'])-np.array(c['power_kw']);t=np.array(truth[c['task_id']]['true_reduction_kw']);b=predict(model,y)[0]
            assert np.max(abs(b-bias[c['task_id']]))<1e-12
            altered=y.copy();altered[15:]=np.arange(45)*99;assert np.array_equal(predict(model,altered)[0],b)
            key=(phase,c['physical_task_id'])
            if key in groups:assert np.array_equal(groups[key],b)
            else:groups[key]=b
            def dur(mask):
                runs=[sum(1 for _ in g) for yes,g in groupby(mask.tolist()) if yes];long=max(runs,default=0)*60
                return mask.sum()*60.,float(long) if long>=30 else 0.
            tm=t[use]>=.15;tc,tl=dur(tm)
            for method,fit in curves[c['task_id']]['results'].items():
                assert fit['status']=='ok';mask=np.array(fit['prediction'])[use]>=.15;pc,pl=dur(mask);r=metrics[c['task_id'],method]
                assert abs(r['primary_seconds']-.5*(abs(pc-tc)+abs(pl-tl)))<1e-8
                assert r['null_false_positive']==bool(not tm.any() and mask.any())
                assert r['localized_miss']==bool(tm.any() and not np.any(tm&mask));count+=3
            if i%max(1,len(facts)//8)==0:
                task=dict(task_id=c['task_id'],user_id=c['user_id'],meter_id='check-meter',start_min=0.,end_min=30.,notice_min=-15.,request_kw=1.5)
                data=prepare(s/60,e/60,c['power_kw'],c['reference_kw'],task,.05);before=data['y'].copy();prepared=stage.prepare_tracking(data)
                result=stage.complete_tracking(prepared,{0:curves[c['task_id']]['results']['tracked_cpop']},0,dict(status='ok',source='saved_native_replay'))
                assert np.max(abs(np.array(result['duration_state_curve_kw'])-curves[c['task_id']]['results']['tracked_retained']['prediction']))<1e-12
                assert np.array_equal(before,data['y']);eta=float(np.sum(y[use])/45)
                assert abs(result['eta_raw']-eta)<1e-12;replayed+=1
            if phase=='test' and c['cohort']=='main' and c['physical_task_id'] not in seen:
                seen.add(c['physical_task_id']);true=np.array(truth[c['task_id']]['true_reference_kw']);references_before.extend((np.array(c['reference_kw'])-true)[use]);references_after.extend((np.array(c['reference_kw'])-b-true)[use])
    for p,h in read('freeze.json')['source_sha256'].items():assert sha(ROOT/p)==h,p
    for p,h in read('preserved_before.json').items():assert sha(ROOT/p)==h,p
    tr=read('reference/train_facts.json');val=read('reference/validation_facts.json');test=read('test/source_facts.json')
    sets=[{f['task']['user_id'] for f in fs} for fs in [tr,val,test]]
    assert all(not sets[a]&sets[b] for a,b in [(0,1),(0,2),(1,2)])
    assert model['fit_cutoff']<min(f['task']['notice_min'] for f in test)
    assert all(max(f['reference_window']['pre_ends_min'])<=f['task']['notice_min'] for f in test)
    out=dict(passed=True,independent_metric_relations=count,staged_output_replays=replayed,tracking_invariant_to_task_and_rebound=True,tracking_identical_across_response_variants=True,
        previous_code_models_and_results_unchanged=True,frozen_source_verified=True,users_disjoint=True,task_reference_RMSE_before=float(np.sqrt(np.mean(np.square(references_before)))),
        task_conditional_reference_RMSE_after=float(np.sqrt(np.mean(np.square(references_after)))),unique_reference_tasks=len(seen),
        correction_is_retrospective_not_notice_time_prediction=True)
    write('independent_checks.json',out);print(json.dumps(out),flush=True)
if __name__=='__main__':main()
