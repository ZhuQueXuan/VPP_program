from common import *
from b1_algorithm.api import analyze_events,_default_runtime_config
from b1_algorithm.contracts import provided_reference
cases=read(HERE/'known_test/minute/facts.json')+read(HERE/'known_test/10s/facts.json');expected={r['task_id']:r['methods']['retained'] for r in read(HERE/'known_test/outputs.json')};selected=[]
for panel in ['minute','10s']:
    for kind in ['smooth_weak','interrupted','null','one_bin_response' if panel=='minute' else 'one_finebin_response']:
        selected.append(next(c for c in cases if c['panel']==panel and c['kind']==kind and c['condition']=='gaussian'))
records=[]
for c in selected:
    s=np.asarray(c['starts_s'])/60;e=np.asarray(c['ends_s'])/60;task=dict(task_id=c['task_id'],user_id=c['base_task_id'],meter_id=c['base_task_id'],start_min=0.,end_min=30.,request_kw=1.5,notice_min=-15.,task_pre_treatment=True)
    records.append(dict(task=task,starts_min=s,ends_min=e,power_kw=c['power_kw'],noise_sigma_kw=.05,reference=provided_reference(task,s,e,c['reference_kw'],available_at_min=-15.)))
cfg=_default_runtime_config();cfg['artifact_dir']=str(HERE/'public_native');result=analyze_events(records,process_method='effective_response_refined',process_config=cfg)
for c,r in zip(selected,result):
    assert r['status']=='ok',(c['task_id'],r.get('reasons'));old=expected[c['task_id']];p=r['process']
    assert p['features']==old['features'];assert p['duration_estimates']==old['duration_estimates'];assert p['eta_raw']==old['eta_raw'];assert p['localized_threshold_state']==old['localized_threshold_state']
    assert r['outcome']['value']==p['eta_raw'] and r['outcome']['process_fit_used_in_energy'] is False
save('public_replay.json',result);save('public_checks.json',dict(status='passed',native_public_events=len(result),matches_known_acceptance_outputs=True,new_independent_sample_count=0))
print('Public native feature and accounting replay passed:',len(result),flush=True)
