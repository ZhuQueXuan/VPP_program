from common import *
from b1_algorithm.api import analyze_events,_default_runtime_config
from b1_algorithm.contracts import provided_reference
cases=read(HERE/'endtoend/physical_inputs.json');expected=read(HERE/'endtoend/first_block_outputs.json');indices=[0,1,320,321];records=[]
for i in indices:
    c=cases[i];s=np.asarray(c['starts_s'])/60;e=np.asarray(c['ends_s'])/60;t=c['task'];records.append(dict(task=t,starts_min=s,ends_min=e,power_kw=c['power_kw'],noise_sigma_kw=.05,reference=provided_reference(t,s,e,c['reference_kw'],available_at_min=-15.)))
cfg=_default_runtime_config();cfg['artifact_dir']=str(HERE/'endtoend/public_native');out=analyze_events(records,process_method='effective_response_refined',process_config=cfg)
for i,r in zip(indices,out):
    assert r['status']=='ok',(i,r.get('reasons'));p=r['process'];before=expected[i]['process'];assert p['duration_estimates']==before['duration_estimates'];assert p['features']==before['features'];assert p['eta_raw']==before['eta_raw'];assert p['localized_threshold_state']==before['localized_threshold_state']
save('endtoend/public_outputs.json',out);save('endtoend/public_check.json',dict(status='passed',replay_events=4,new_independent_samples=0,public_api_matches_frozen_process_outputs=True))
print('First-block public/native replay matched4 events',flush=True)
