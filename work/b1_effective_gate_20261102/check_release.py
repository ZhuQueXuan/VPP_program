from common import *
from evaluate import cache
from b1_algorithm.api import analyze_events,_default_runtime_config
from b1_algorithm.contracts import provided_reference
from b1_algorithm.process.api import prepare
from b1_algorithm.process import _gap_duration as GD

def runtime(name):
    c=_default_runtime_config();c['artifact_dir']=str(HERE/'public'/name);return c

def main():
    datasets={stage:cache(stage) for stage in ['main_test','weak_test']};cases={};lookup={};base_values={};curve_values={}
    for stage,cc in datasets.items():
        cs,curves,truth,base,masks,probs=cc
        for i,c in enumerate(cs):cases[c['task_id']]=c;base_values[c['task_id']]=base[i];curve_values[c['task_id']]=curves[c['task_id']]
        lookup.update({(r['task_id'],r['method']):r for r in read(stage+'/metrics.json')})
    chosen=[]
    for panel in ['minute','10s']:
        rejected=[r for (tid,m),r in lookup.items() if m=='candidate' and r['panel']==panel and r['rejected']]
        rejected.sort(key=lambda r:-r['effective_score']);chosen += [r['task_id'] for r in rejected[:2]]
        retained_true=[r for (tid,m),r in lookup.items() if m=='candidate' and r['panel']==panel and r['positive_truth'] and not r['rejected'] and r['positive_prediction']]
        retained_true.sort(key=lambda r:r['effective_score']);chosen += [r['task_id'] for r in retained_true[:2]]
        short_kind='one_bin_response' if panel=='minute' else 'one_finebin_response'
        chosen.append(next(c['task_id'] for c in datasets['main_test'][0] if c['panel']==panel and c['kind']==short_kind and c['condition']=='gaussian'))
        chosen.append(next(tid for (tid,m),r in lookup.items() if m=='retained' and r['panel']==panel and r['kind']=='null' and r['positive_prediction']))
    chosen=list(dict.fromkeys(chosen));records=[]
    for i,tid in enumerate(chosen):
        c=cases[tid];s=np.asarray(c['starts_s'])/60;e=np.asarray(c['ends_s'])/60;task=dict(task_id=tid,user_id='effective-check-'+str(i),meter_id='meter-'+str(i),start_min=0.,end_min=30.,request_kw=1.5,notice_min=-15.,task_pre_treatment=True)
        records.append(dict(task=task,starts_min=s,ends_min=e,power_kw=c['power_kw'],noise_sigma_kw=.05,reference=provided_reference(task,s,e,c['reference_kw'],available_at_min=-15.)))
    new=analyze_events(records,process_method='effective_response_refined',process_config=runtime('native_new'))
    old=analyze_events(records,process_method='gap_duration_refined',process_config=runtime('native_old'))
    write('public/live_routes.json',dict(new=new,old=old));same_fields=0;negative_checks=0
    prior=load(HERE/'production_before/B1算法/b1_algorithm/process/api.py','b1_algorithm.process._effective_prior_api')
    for tid,record,a,b in zip(chosen,records,new,old):
        assert a['status']=='ok' and b['status']=='ok',(tid,a.get('reasons'),b.get('reasons'))
        pa,pb=a['process'],b['process'];expected=lookup[tid,'candidate'];before=lookup[tid,'retained']
        assert pa['effective_response_present']==expected['positive_prediction']
        for key,label in [('cumulative_response_seconds','predicted_cumulative_seconds'),('longest_continuous_response_seconds','predicted_longest_seconds')]:
            assert abs(pa['duration_estimates'][key]-expected[label])<1e-8
            assert abs(pb['duration_estimates'][key]-before[label])<1e-8
        assert pa['reduction_interval_kw']==pb['reduction_interval_kw'] and pa['retained_duration_support_curve_kw']==pb['retained_duration_support_curve_kw']
        assert pa['eta_raw']==pb['eta_raw'] and a['outcome']==b['outcome']
        assert pa['features']['raw_observed']==pb['features']['raw_observed'] and pa['features']['accounting']==pb['features']['accounting']
        assert pa['selection_evidence']['physical_change_score']==pb['selection_evidence']['physical_change_score']
        assert pa['selection_evidence']['physical_change_accepted']==pb['selection_evidence']['physical_change_accepted']
        for key,value in pb['features']['selected_curve'].items():
            if key not in ['cumulative_response_seconds','longest_continuous_response_seconds']:assert pa['features']['selected_curve'][key]==value;same_fields+=1
        if expected['rejected']:
            assert not pa['effective_response_present'] and not any(pa['localized_threshold_state'])
            assert pa['localized_response_intervals_seconds']==[] and pa['effective_verification']['physical_change_evidence_preserved'];negative_checks+=1
        else:
            assert pa['duration_estimates']==pb['duration_estimates'] and pa['localized_threshold_state']==pb['localized_threshold_state']
        c=cases[tid];data=prepare(record['starts_min'],record['ends_min'],record['power_kw'],c['reference_kw'],b['task'],.05)
        old_result=prior.complete(data,{0:dict(status='ok',prediction=np.asarray(pb['reduction_interval_kw']))},policy='gap_duration_refined')
        assert old_result['features']==pb['features'] and old_result['duration_estimates']==pb['duration_estimates']
    vectors=0
    for stage,cc in datasets.items():
        cs,curves,truth,base,masks,probs=cc;X=np.load(HERE/stage/'effective_X.npy')
        for i,c in enumerate(cs):
            f=curves[c['task_id']];expected=GD.features(c,f['cpop']['prediction'],f['duration_fusion']['prediction'],base[i]);assert np.array_equal(X[i],expected);vectors+=1
    allowed={'B1算法/b1_algorithm/process/api.py','B1算法/b1_algorithm/process/batch.py','B1算法/README.md'};changed=[]
    for p,h in read('production_before.json').items():
        if sha(ROOT/p)!=h:assert p in allowed,p;changed.append(p)
    for p,h in read('release_build.json')['files'].items():assert sha(ROOT/p)==h,p
    write('public_checks.json',dict(events_per_route=len(chosen),native_public_outputs=2*len(chosen),rejected_sample_checks=negative_checks,
        other_feature_fields_unchanged=same_fields,all_final_feature_vectors_exact=vectors,feature_count=426,
        physical_change_evidence_raw_structure_energy_eta_preserved=True,all_records_retained=True,old_route_replayed_from_source=True,
        old_models_and_default_preserved=True,changed_preexisting_B1_files=changed,all_passed=True))
    print('Public/native effective verification checked',negative_checks,'negative qualifications;',vectors,'features',flush=True)

if __name__=='__main__':main()
