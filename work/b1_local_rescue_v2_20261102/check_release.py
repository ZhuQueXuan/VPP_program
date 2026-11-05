from common import *
from evaluate import cache,score
from b1_algorithm.api import analyze_events,_default_runtime_config
from b1_algorithm.contracts import provided_reference
from b1_algorithm.process.api import prepare,complete
from b1_algorithm.process import _local_response as LR
from raw_features import RAW_INDICES

def runtime(label):
    c=_default_runtime_config();c['artifact_dir']=str(HERE/'public'/label);return c

def main():
    source={};case_lookup={};metric_lookup={};all_added=[]
    for stage in ['main_test','weak_test']:
        cc=cache(stage);cases,curves,truth,baseline,physical,slices,pp=cc
        for c in cases:case_lookup[c['task_id']]=c;source[c['task_id']]=curves[c['task_id']]
        rows=read(stage+'/metrics.json')
        metric_lookup.update({(r['task_id'],r['method']):r for r in rows})
        all_added += [r['task_id'] for r in rows if r['method']=='candidate' and r['new_bins']>0]
    chosen=[case_lookup[tid] for tid in all_added]
    for panel in ['minute','10s']:
        for kind in ['smooth_weak','one_bin_response' if panel=='minute' else 'one_finebin_response']:
            chosen.append(next(c for c in case_lookup.values() if c['panel']==panel and c['kind']==kind and c['seed']==7762000 and c['condition']=='gaussian'))
    records=[]
    for i,c in enumerate(chosen):
        task=dict(task_id=c['task_id'],user_id='local-check-'+str(i),meter_id='meter-'+str(i),start_min=0.,end_min=30.,request_kw=1.5,notice_min=-15.,task_pre_treatment=True)
        s=np.asarray(c['starts_s'])/60;e=np.asarray(c['ends_s'])/60
        records.append(dict(task=task,starts_min=s,ends_min=e,power_kw=c['power_kw'],noise_sigma_kw=.05,reference=provided_reference(task,s,e,c['reference_kw'],available_at_min=-15.)))
    new=analyze_events(records,process_method='known_local_response',process_config=runtime('native_new'))
    old=analyze_events(records,process_method='known_response_duration',process_config=runtime('native_old'))
    write('public/live_routes.json',dict(new=new,old=old));field_checks=0;rescued=0
    previous=load(HERE/'production_before/B1算法/b1_algorithm/process/api.py','b1_algorithm.process._local_response_prior_api')
    for c,a,b in zip(chosen,new,old):
        assert a['status']=='ok' and b['status']=='ok',(c['task_id'],a.get('reasons'),b.get('reasons'))
        pa,pb=a['process'],b['process'];expected=metric_lookup[c['task_id'],'candidate'];retained=metric_lookup[c['task_id'],'retained']
        for key,label in [('cumulative_response_seconds','predicted_cumulative_seconds'),('longest_continuous_response_seconds','predicted_longest_seconds')]:assert abs(pa['features']['selected_curve'][key]-expected[label])<1e-8
        assert pa['eta_raw']==pb['eta_raw'] and a['outcome']==b['outcome']
        assert pa['features']['accounting']==pb['features']['accounting'] and pa['features']['raw_observed']==pb['features']['raw_observed']
        assert pa['reduction_interval_kw']==pb['reduction_interval_kw']
        for key,value in pb['features']['selected_curve'].items():
            if key not in ['cumulative_response_seconds','longest_continuous_response_seconds']:
                assert pa['features']['selected_curve'][key]==value;field_checks+=1
        if expected['new_bins']>0:
            assert retained['predicted_cumulative_seconds']==0 and expected['predicted_cumulative_seconds']>0
            assert pa['rescued_response_intervals_seconds'];rescued+=1
            assert sum(pa['localized_threshold_state'])==expected['new_bins']
        else:assert pa['features']['selected_curve']==pb['features']['selected_curve']
        # Re-execute the prior method from the actual preserved source with the
        # same live native numpy curve, matching its internal interface.
        data=prepare(np.array(c['starts_s'])/60,np.array(c['ends_s'])/60,c['power_kw'],c['reference_kw'],b['task'],.05)
        prior=previous.complete(data,{0:dict(status='ok',prediction=np.asarray(pb['reduction_interval_kw']))},policy='known_response_duration')
        assert prior['features']==pb['features'] and prior['duration_estimates']==pb['duration_estimates']
    # Exact raw-only feature export for every held-out observed grid point.
    vectors=0;rows=0
    for stage in ['main_test','weak_test']:
        cases=read(stage+'/facts.json');sl=read(stage+'/slices.json');xx=np.load(HERE/stage/'state_X.npy',mmap_mode='r')
        for c,(a,b) in zip(cases,sl):
            actual=LR.raw_features(c);assert np.array_equal(actual,xx[a:b,RAW_INDICES]);vectors+=1;rows+=len(actual)
    changed=[];allowed={'B1算法/b1_algorithm/process/api.py','B1算法/b1_algorithm/process/batch.py','B1算法/README.md'}
    for p,h in read('production_before.json').items():
        if sha(ROOT/p)!=h:assert p in allowed,p;changed.append(p)
    for p,h in read('release_build.json')['files'].items():assert sha(ROOT/p)==h,p
    write('public_checks.json',dict(events_per_route=len(chosen),public_native_events=2*len(chosen),rescued_records_verified=rescued,
        unchanged_other_feature_fields=field_checks,raw_only_feature_vectors_exact=vectors,raw_only_point_rows_exact=rows,
        original_route_replayed_from_preserved_source=True,raw_eta_and_energy_unchanged=True,default_policy_unchanged=True,
        changed_preexisting_B1_files=changed,all_passed=True))
    print('Public native release verified',rescued,'rescued records;',vectors,'heldout tasks',flush=True)

if __name__=='__main__':main()
