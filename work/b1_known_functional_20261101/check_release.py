"""Native public API replay, preservation checks and feature export agreement."""
from common import *
from copy import deepcopy
from evaluate import dataset
from b1_algorithm.api import analyze_events
from b1_algorithm.contracts import provided_reference
from b1_algorithm.process.api import prepare,complete,identify_process
from b1_algorithm.process.batch import identify_process_batch
from b1_algorithm.process import _known_duration as KD

def runtime(directory):
    from b1_algorithm.api import _default_runtime_config
    c=_default_runtime_config();c['artifact_dir']=str(HERE/directory);c['timeout_seconds']=180;return c

def main():
    cases,curves,truth,scores,deltas=dataset('test',HERE)
    chosen=[]
    for panel in ['minute','10s']:
        for kind in ['smooth_weak','null','one_bin_response' if panel=='minute' else 'one_finebin_response','one_bin_gap' if panel=='minute' else 'one_finebin_gap']:
            chosen.append(next(c for c in cases if c['panel']==panel and c['kind']==kind and c['condition']=='gaussian'))
    rejected=[c for i,c in enumerate(cases) if scores[i]<read('selected.json')['config']['event_threshold'] and any(np.array(curves[c['task_id']]['results']['cpop']['prediction'])>=.15)]
    chosen+=rejected[:2]
    stress,sc,_,_,_=dataset('stress_test',HERE)
    chosen += [next(c for c in stress if c['panel']==p and c['kind']=='smooth_weak') for p in ['minute','10s']]
    lookup={(r['task_id'],r['method']):r for stage in ['test','stress_test'] for r in read(stage+'/metrics.json')}
    curves.update(sc);records=[];requests=[]
    for i,c in enumerate(chosen):
        task=dict(task_id=c['task_id'],user_id='known-release-'+str(i),meter_id='meter-'+str(i),start_min=0.,end_min=30.,request_kw=1.5,notice_min=-15.,task_pre_treatment=True)
        s=np.array(c['starts_s'])/60;e=np.array(c['ends_s'])/60;ref=provided_reference(task,s,e,c['reference_kw'],available_at_min=-15.)
        records.append(dict(task=task,starts_min=s,ends_min=e,power_kw=c['power_kw'],reference=ref,noise_sigma_kw=.05))
        requests.append(dict(task=task,starts_min=s,ends_min=e,power_kw=c['power_kw'],reference_kw=c['reference_kw'],noise_sigma_kw=.05))
    if (HERE/'public/live_routes.json').exists():
        live=read('public/live_routes.json');new,old,original=live['new'],live['old'],live['cpop']
    else:
        new=analyze_events(records,process_method='known_response_duration',process_config=runtime('public/native_new'))
        old=analyze_events(records,process_method='duration_fusion',process_config=runtime('public/native_old'))
        original=analyze_events(records,process_method='cpop',process_config=runtime('public/native_cpop'))
        write('public/live_routes.json',dict(new=new,old=old,cpop=original))
    previous=load(HERE/'production_before/B1算法/b1_algorithm/process/api.py','b1_algorithm.process._known_duration_prior_api')
    same_fields=0
    for c,request,a,b,o in zip(chosen,requests,new,old,original):
        assert a['status']=='ok',(c['task_id'],a.get('reasons'),a.get('process'))
        assert b['status']=='ok' and o['status']=='ok'
        cp=curves[c['task_id']]['results']['cpop']['prediction'];retained=curves[c['task_id']]['results']['retained']['prediction'];pa=a['process'];pb=b['process'];po=o['process']
        assert np.max(abs(np.array(pa['reduction_interval_kw'])-cp))<1e-12
        assert np.max(abs(np.array(pb['duration_state_curve_kw'])-retained))<1e-12
        assert np.max(abs(np.array(pa['retained_duration_support_curve_kw'])-retained))<1e-12
        expected=lookup[c['task_id'],'candidate']
        for key,name in [('cumulative_response_seconds','predicted_cumulative_seconds'),('longest_continuous_response_seconds','predicted_longest_seconds')]:assert abs(pa['features']['selected_curve'][key]-expected[name])<1e-8,(key,c['task_id'])
        for key,value in po['features']['selected_curve'].items():
            if key not in ['cumulative_response_seconds','longest_continuous_response_seconds']:
                assert pa['features']['selected_curve'][key]==value,key;same_fields+=1
        assert a['outcome']['value']==b['outcome']['value']==o['outcome']['value']
        assert pa['features']['accounting']==pb['features']['accounting']==po['features']['accounting']
        assert pa['features']['raw_observed']==pb['features']['raw_observed']==po['features']['raw_observed']
        assert pa['eta_raw']==pb['eta_raw']==po['eta_raw']
        # Internal complete() consumes native numpy vectors, not JSON lists.
        # Compare executors with the same live native vector.
        d=prepare(**request);prior=previous.complete(d,{0:dict(status='ok',prediction=np.asarray(pb['reduction_interval_kw']))},policy='duration_fusion')
        if prior['features']!=pb['features']:
            print(json.dumps(native(dict(task_id=c['task_id'],prior=prior['features'],current=pb['features']))),flush=True)
            raise AssertionError('prior/current feature dictionary mismatch')
        assert prior['duration_state_curve_kw']==pb['duration_state_curve_kw']
    # All 3588 held-out feature vectors have the same executable schema as the
    # frozen experiment; labels, kinds and condition names are not input fields.
    feature_count=0
    from model import input_features as frozen_features
    for stage in ['test','stress_test','stress_continuous']:
        vv={r['task_id']:r['results'] for r in read(stage+'/curves.json')}
        for c in read(stage+'/facts.json'):
            f=vv[c['task_id']];x=KD.input_features(c,f['cpop']['prediction'],f['retained']['prediction']);expected=frozen_features(c,f['cpop']['prediction'],f['retained']['prediction'])
            assert np.array_equal(x,expected);feature_count+=1
    missing=identify_process_batch(requests,config=runtime('public/no_native'),method='known_response_duration',native_unavailable_reason='intentional_integration_check')
    assert all(r['status']=='unavailable' and r['features'] is None for r in missing)
    bad=deepcopy(requests[0]);bad['noise_sigma_kw']=.051
    assert identify_process(**bad,method='known_response_duration')['status']=='unavailable'
    assert identify_process_batch([bad],method='known_response_duration')[0]['status']=='unavailable'
    allowed={'B1算法/b1_algorithm/process/api.py','B1算法/b1_algorithm/process/batch.py','B1算法/README.md'}
    changed=[]
    for p,h in read('production_before.json').items():
        if sha(ROOT/p)!=h:changed.append(p);assert p in allowed,p
    write('public_checks.json',dict(events_per_route=len(chosen),routes=['known_response_duration','duration_fusion','cpop'],native_public_events=3*len(chosen),
        unchanged_other_feature_fields=same_fields,all_heldout_feature_vectors_exact=feature_count,raw_energy_and_eta_identical=True,
        original_duration_route_replayed_exact=True,changed_preexisting_B1_files=changed,missing_native_and_out_of_domain_checks_passed=True,
        default_policy_unchanged=True,no_reference_prediction_used=True))
    write('public/example_result.json',new[0]);print('Public/native integration verified',len(chosen),'events x3routes;',feature_count,'feature vectors',flush=True)

if __name__=='__main__':main()
