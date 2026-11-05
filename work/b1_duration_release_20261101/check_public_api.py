"""Real public API/native integration checks against frozen held-out outputs."""
from common import *
from copy import deepcopy
from b1_algorithm.api import analyze_events
from b1_algorithm.contracts import provided_reference
from b1_algorithm.process.api import prepare,complete,identify_process
from b1_algorithm.process.batch import identify_process_batch
from b1_algorithm.resources.ev import EVAnalysisConfig

def main():
    curves={r['task_id']:r for r in read('test/curves.json')};metrics={(r['task_id'],r['method']):r for r in read('test/metrics.json')}
    cases=[]
    for panel in ['minute','10s']:
        all_cases=read('test/'+panel+'/facts.json')
        kinds=['smooth_weak','interrupted','one_bin_response' if panel=='minute' else 'one_finebin_response','one_bin_gap' if panel=='minute' else 'one_finebin_gap']
        cases += [next(c for c in all_cases if c['kind']==kind) for kind in kinds]
    records=[];requests=[]
    for i,c in enumerate(cases):
        task=dict(task_id=c['task_id'],user_id='check-user-'+str(i),meter_id='check-meter-'+str(i),start_min=0.,end_min=30.,request_kw=1.5,notice_min=-15.,task_pre_treatment=True)
        s=np.array(c['starts_s'])/60;e=np.array(c['ends_s'])/60
        ref=provided_reference(task,s,e,c['reference_kw'],available_at_min=-15.)
        records.append(dict(task=task,starts_min=s,ends_min=e,power_kw=c['power_kw'],reference=ref,noise_sigma_kw=.05))
        requests.append(dict(task=task,starts_min=s,ends_min=e,power_kw=c['power_kw'],reference_kw=c['reference_kw'],noise_sigma_kw=.05))
    results=analyze_events(records,process_method='duration_fusion',process_config=runtime('functional/native_new'))
    originals=analyze_events(records,process_method='cpop',process_config=runtime('functional/native_original'))
    for c,new,original in zip(cases,results,originals):
        assert new['status']=='ok',new.get('reasons')
        cp=np.array(curves[c['task_id']]['results']['cpop']['prediction']);f=np.array(curves[c['task_id']]['results']['duration_fusion']['prediction'])
        assert np.max(abs(np.array(new['process']['reduction_interval_kw'])-cp))<1e-12
        assert np.max(abs(np.array(original['process']['reduction_interval_kw'])-cp))<1e-12
        assert np.max(abs(np.array(new['process']['duration_state_curve_kw'])-f))<1e-12
        expected=metrics[c['task_id'],'duration_fusion']['features']['selected_curve']
        for key in ['cumulative_response_seconds','longest_continuous_response_seconds']:
            assert abs(new['process']['features']['selected_curve'][key]-expected[key])<1e-8
        for key,value in original['process']['features']['selected_curve'].items():
            if key not in ['cumulative_response_seconds','longest_continuous_response_seconds']:
                assert new['process']['features']['selected_curve'][key]==value,key
        assert new['outcome']['value']==original['outcome']['value']
        assert new['process']['features']['accounting']==original['process']['features']['accounting']
    unavailable=identify_process_batch(requests,config=runtime('functional/no_native'),method='duration_fusion',native_unavailable_reason='deliberate_check')
    assert all(r['status']=='unavailable' and r['features'] is None and r['eta_raw'] is None for r in unavailable)
    bad=deepcopy(requests[0]);bad['noise_sigma_kw']=.051
    assert identify_process_batch([bad],method='duration_fusion')[0]['status']=='unavailable'
    assert identify_process(**bad,method='duration_fusion')['status']=='unavailable'
    data=prepare(**requests[0])
    for key,value in [('q',2.),('W',20.),('delta',15.),('sigma',.1)]:
        d=dict(data,**{key:value});r=complete(d,{0:dict(status='ok',prediction=curves[cases[0]['task_id']]['results']['cpop']['prediction'])},policy='duration_fusion')
        assert r['status']=='unavailable',(key,r)
    changed=[];protected=read('protected_before.json')
    for path,expected in protected.items():
        if sha(ROOT/path)!=expected:changed.append(path)
    allowed=['B1算法/b1_algorithm/process/api.py','B1算法/b1_algorithm/process/batch.py','B1算法/README.md']
    assert set(changed)<=set(allowed),changed
    before=read('production_before.json')
    for path,expected in before.items():
        snapshot=HERE/'production_before'/Path(path).relative_to('B1算法');assert sha(snapshot)==expected,path
    write('public_api_checks.json',dict(real_native_new_events=len(results),real_native_original_events=len(originals),unavailable_events=len(unavailable),
        out_of_domain_checks=6,all_passed=True,changed_preexisting_files=changed,old_source_snapshots_verified=True,
        original_policy_sha256=sha(ROOT/'B1算法/b1_algorithm/process/_policy.json'),default_changed=False,
        observer_note='assessment.json saved successfully; assess.py console print failed numpy-bool serialization after saving. Frozen assessment and metrics were not modified.'))
    write('functional/example_result.json',results[0]);print('public/native checks passed',len(results))
if __name__=='__main__':main()
