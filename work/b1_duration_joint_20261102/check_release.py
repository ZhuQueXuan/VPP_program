from common import *
from evaluate import cache
from model import features as frozen_features
from b1_algorithm.api import analyze_events,_default_runtime_config
from b1_algorithm.contracts import provided_reference
from b1_algorithm.process.api import prepare
from b1_algorithm.process import _gap_duration as GD

def runtime(name):
    c=_default_runtime_config();c['artifact_dir']=str(HERE/'public'/name);return c

def main():
    cases={};metrics={};cache_values={};chosen=[]
    for stage in ['main_test','weak_test']:
        cc=cache(stage);cache_values[stage]=cc
        for c in cc[0]:cases[c['task_id']]=c
        metrics.update({(r['task_id'],r['method']):r for r in read(stage+'/metrics.json')})
    for panel in ['minute','10s']:
        for kind in ['interrupted','one_bin_response' if panel=='minute' else 'one_finebin_response','null']:
            chosen.append(next(c['task_id'] for c in cache_values['main_test'][0] if c['panel']==panel and c['kind']==kind and c['condition']=='gaussian'))
    ranked=[]
    for tid in cases:
        old=metrics[tid,'retained'];new=metrics[tid,'candidate'];ranked.append((old['primary_seconds']-new['primary_seconds'],tid))
    chosen += [tid for _,tid in sorted(ranked,reverse=True)[:3]]+[tid for _,tid in sorted(ranked)[:3]]
    chosen=list(dict.fromkeys(chosen));records=[]
    for i,tid in enumerate(chosen):
        c=cases[tid];task=dict(task_id=tid,user_id='gap-check-'+str(i),meter_id='meter-'+str(i),start_min=0.,end_min=30.,request_kw=1.5,notice_min=-15.,task_pre_treatment=True);s=np.asarray(c['starts_s'])/60;e=np.asarray(c['ends_s'])/60
        records.append(dict(task=task,starts_min=s,ends_min=e,power_kw=c['power_kw'],noise_sigma_kw=.05,reference=provided_reference(task,s,e,c['reference_kw'],available_at_min=-15.)))
    new=analyze_events(records,process_method='gap_duration_refined',process_config=runtime('native_new'))
    old=analyze_events(records,process_method='known_local_response',process_config=runtime('native_old'))
    write('public/live_routes.json',dict(new=new,old=old));same_fields=0
    prior=load(HERE/'production_before/B1算法/b1_algorithm/process/api.py','b1_algorithm.process._gap_duration_prior_api')
    for tid,c_record,a,b in zip(chosen,records,new,old):
        assert a['status']=='ok' and b['status']=='ok',(tid,a.get('reasons'),b.get('reasons'))
        pa,pb=a['process'],b['process'];want=metrics[tid,'candidate'];before=metrics[tid,'retained']
        for key,label in [('cumulative_response_seconds','predicted_cumulative_seconds'),('longest_continuous_response_seconds','predicted_longest_seconds')]:
            assert abs(pa['features']['selected_curve'][key]-want[label])<1e-8,(tid,key,pa['features']['selected_curve'][key],want[label])
            assert abs(pb['features']['selected_curve'][key]-before[label])<1e-8
        for key in ['localized_threshold_state','localized_response_intervals_seconds','rescued_response_intervals_seconds','retained_duration_support_curve_kw','reduction_interval_kw','effective_response_present']:
            assert pa[key]==pb[key],(tid,key)
        for key,value in pb['features']['selected_curve'].items():
            if key not in ['cumulative_response_seconds','longest_continuous_response_seconds']:
                assert pa['features']['selected_curve'][key]==value;same_fields+=1
        assert pa['features']['accounting']==pb['features']['accounting'] and pa['features']['raw_observed']==pb['features']['raw_observed']
        assert pa['eta_raw']==pb['eta_raw'] and a['outcome']==b['outcome']
        data=prepare(c_record['starts_min'],c_record['ends_min'],c_record['power_kw'],cases[tid]['reference_kw'],b['task'],.05)
        original=prior.complete(data,{0:dict(status='ok',prediction=np.asarray(pb['reduction_interval_kw']))},policy='known_local_response')
        assert original['features']==pb['features'] and original['duration_estimates']==pb['duration_estimates']
    feature_vectors=0
    for stage,cc in cache_values.items():
        cases_stage,curves,truth,baseline,masks,predictions=cc;X=np.load(HERE/stage/'joint_X.npy')
        for i,c in enumerate(cases_stage):
            f=curves[c['task_id']];support=f['retained' if 'retained' in f else 'duration_fusion']['prediction'];actual=GD.features(c,f['cpop']['prediction'],support,baseline[i]);assert np.array_equal(actual,X[i]);feature_vectors+=1
    allowed={'B1算法/b1_algorithm/process/api.py','B1算法/b1_algorithm/process/batch.py','B1算法/README.md'};changed=[]
    for p,h in read('production_before.json').items():
        if sha(ROOT/p)!=h:assert p in allowed,p;changed.append(p)
    for p,h in read('release_build.json')['files'].items():assert sha(ROOT/p)==h,p
    write('public_checks.json',dict(events_per_route=len(chosen),native_public_events=2*len(chosen),unchanged_other_feature_fields=same_fields,
        heldout_feature_vectors_exact=feature_vectors,heldout_features=426,classification_and_localized_masks_exact=True,
        raw_energy_eta_unchanged=True,prior_route_replayed_from_source=True,old_models_and_default_unchanged=True,
        changed_preexisting_B1_files=changed,all_passed=True))
    print('Public native and feature export checks passed',len(chosen),'events x2;',feature_vectors,'feature vectors',flush=True)

if __name__=='__main__':main()
