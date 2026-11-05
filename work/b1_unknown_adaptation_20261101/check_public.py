from common import *
from b1_algorithm.api import analyze_events,_default_runtime_config
from b1_algorithm.reference.core import ReferenceWindow
from b1_algorithm.reference.reliable import load_ev_reliable_reference_model,predict_ev_reliable_reference
from dataclasses import asdict

def main():
    facts=read('test/facts.json');curves={r['task_id']:r for r in read('test/curves.json')};metrics={(r['task_id'],r['method']):r for r in read('test/metrics.json')};sources={f['task']['task_id']:f for f in read('test/source_facts.json')};chosen=[]
    for cohort,kinds in [('main',['strong','weak','null']),('short',['short','null'])]:
        for kind in kinds:
            for condition in ['ordinary','spikes']:chosen.append(next(c for c in facts if c['cohort']==cohort and c['kind']==kind and c['condition']==condition))
    model=load_ev_reliable_reference_model(ROOT/'work/b1_reliability_20261031/study/models/reliable_reference.json');records=[]
    for c in chosen:
        f=sources[c['physical_task_id']];p=predict_ev_reliable_reference(model,ReferenceWindow(**f['reference_window']));assert np.max(abs(p.reference_kw-c['reference_kw']))<1e-12
        task=dict(f['task'],task_id=c['task_id']);ref=asdict(p);ref['task_id']=c['task_id']
        records.append(dict(task=task,starts_min=f['starts_min'],ends_min=f['ends_min'],power_kw=c['power_kw'],reference=ref,noise_sigma_kw=.05))
    config=_default_runtime_config();config['artifact_dir']=str(HERE/'functional/new_native');config['timeout_seconds']=180
    new=analyze_events(records,process_config=config,process_method='reference_tracked_duration')
    config['artifact_dir']=str(HERE/'functional/old_native');old=analyze_events(records,process_config=config,process_method='duration_fusion')
    for c,a,b in zip(chosen,new,old):
        assert a['status']=='ok',a.get('reasons');assert b['status']=='ok'
        expected=curves[c['task_id']]['results'];assert np.max(abs(np.array(a['process']['duration_state_curve_kw'])-expected['tracked_retained']['prediction']))<1e-12
        assert np.max(abs(np.array(b['process']['duration_state_curve_kw'])-expected['old_retained']['prediction']))<1e-12
        assert np.max(abs(np.array(a['process']['reduction_interval_kw'])-expected['tracked_cpop']['prediction']))<1e-12
        r=metrics[c['task_id'],'tracked_retained'];f=a['process']['features']['selected_curve']
        assert abs(f['cumulative_response_seconds']-r['predicted_cumulative_seconds'])<1e-7
        assert abs(f['longest_continuous_response_seconds']-r['predicted_longest_seconds'])<1e-7
        assert a['outcome']['value']==b['outcome']['value'];assert a['reference']==b['reference']
        assert a['process']['features']['accounting']==b['process']['features']['accounting']
    allowed={'B1算法/b1_algorithm/process/api.py','B1算法/b1_algorithm/process/batch.py','B1算法/README.md'};changed=[]
    for path,h in read('production_before.json').items():
        if sha(ROOT/path)!=h:changed.append(path)
        assert sha(HERE/'production_before'/Path(path).relative_to('B1算法'))==h
    assert set(changed)<=allowed,changed
    for path,h in read('preserved_before.json').items():
        if path not in allowed:assert sha(ROOT/path)==h,path
    write('public_checks.json',dict(passed=True,new_public_events=len(new),old_public_events=len(old),matched_frozen_test_curves=True,
        original_notice_reference_and_raw_energy_identical=True,original_duration_model_unchanged=True,source_snapshots_verified=True,changed_files=changed))
    write('functional/example_result.json',new[0]);print('real public/native comparison passed',len(new))
if __name__=='__main__':main()
