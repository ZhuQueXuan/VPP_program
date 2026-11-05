from common import *
from b1_algorithm.process import api as API,_duration_fusion as DF
import sys
def truth_features(c,clean):
    s=np.asarray(c['starts_s']);e=np.asarray(c['ends_s']);dt=e[0]-s[0];mask=(s>=0)&(s<1800)&(clean>=.15);dwell=max(1,int(np.ceil(30/dt-1e-9)))
    def first_run(flags,indexes):
        run=0
        for j in indexes:
            run=run+1 if flags[j] else 0
            if run>=dwell:return int(j-dwell+1)
        return None
    longest=run=0
    for yes in mask:run=run+1 if yes else 0;longest=max(longest,run)
    ix=np.flatnonzero((s>=0)&(s<1800));on=first_run(clean>=.15,ix);post=np.flatnonzero(s>=1800);recovery=first_run(abs(clean)<=.15,post) if on is not None else None
    return dict(cumulative_response_seconds=float(mask.sum()*dt),longest_continuous_response_seconds=float(longest*dt) if longest>=dwell else 0.,onset_seconds=None if on is None else float(s[on]),recovery_seconds=None if recovery is None else float(s[recovery]),request_net_kwh=float(np.sum(clean[ix]*dt)/3600),eta=float(np.sum(clean[ix]*dt)/(1.5*1800)))
def timing(point,truth,penalty):
    if truth is None:return dict(reference_available=False,missing=False,false_feature=point is not None,error_seconds=None)
    return dict(reference_available=True,missing=point is None,false_feature=False,error_seconds=float(penalty if point is None else min(penalty,abs(point-truth))))
def main():
    for p,h in read(HERE/'model_freeze.json')['files'].items():assert sha(ROOT/p)==h,p
    current_common=sys.modules['common']
    legacy_common=load(ROOT/'work/b1_duration_release_20261101/common.py','closing_legacy_generator_common')
    sys.modules['common']=legacy_common
    g=load(ROOT/'work/b1_duration_release_20261101/generation.py','closing_known_generator');g.HERE=HERE
    # The generator uses its shared common.write global; rebind only this module's
    # imported I/O functions, leaving all previous experiment files untouched.
    g.write=save;g.read=lambda name:read(HERE/name)
    cases=[];truth={};cached=(HERE/'known_test/native_curves.json').exists()
    for panel in ['minute','10s']:
        prefix='known_test/'+panel;block=read(HERE/prefix/'facts.json') if cached else g.generate(panel,[8813000,8813001],1,prefix);cases+=block;truth.update({r['task_id']:r for r in read(HERE/prefix/'truth.json')})
    if cached:
        stored=read(HERE/'known_test/native_curves.json');cp={int(k):v for k,v in stored['cpop'].items()};lb={int(k):v for k,v in stored['labs'].items()}
    else:
        (HERE/'known_test/native/labs').mkdir(parents=True,exist_ok=False);cp,lb,meta=g.baseline_batches(cases,'known_test/native');save('known_test/native_curves.json',dict(cpop=cp,labs=lb));save('known_test/native_receipt.json',meta)
    sys.modules['common']=current_common
    for fits in [cp,lb]:
        for result in fits.values():
            if result['status']=='ok':result['prediction']=np.asarray(result['prediction'],float)
    rows=[];outputs=[];handoff=[]
    for j,c in enumerate(cases):
        s=np.asarray(c['starts_s'])/60;e=np.asarray(c['ends_s'])/60;task=dict(task_id=c['task_id'],user_id=c['base_task_id'],meter_id=c['base_task_id'],start_min=0.,end_min=30.,request_kw=1.5,notice_min=-15.);data=API.prepare(s,e,c['power_kw'],c['reference_kw'],task,.05);DF.validate_domain(data)
        native_fits={0:cp[j]};methods=dict(cpop=API.complete(data,native_fits,policy='cpop'),labs=API.complete(data,{0:lb[j]},policy='cpop'),retained=API.complete(data,native_fits,policy='effective_response_refined'))
        clean=np.asarray(truth[c['task_id']]['true_reduction_kw']);actual=truth_features(c,clean)
        outputs.append(dict(task_id=c['task_id'],methods=methods,truth=actual))
        raw_energy=float(np.sum(data['y'][(s>=0)&(s<30)]*(e-s)[(s>=0)&(s<30)])/60)
        for name,result in methods.items():
            assert result['status']=='ok',(c['task_id'],name,result.get('reason'));f=result['features']['selected_curve'];raw=result['features']['accounting'];on=f['onset_interval_s'];rec=f['power_recovery_time_s'];cum=f['cumulative_response_seconds'];longest=f['longest_continuous_response_seconds'];truepos=actual['cumulative_response_seconds']>0;positive=cum>0
            rows.append(dict(task_id=c['task_id'],base_task_id=c['base_task_id'],panel=c['panel'],condition=c['condition'],kind=c['kind'],method=name,cumulative_error=abs(cum-actual['cumulative_response_seconds']),longest_error=abs(longest-actual['longest_continuous_response_seconds']),onset=timing(None if on is None else on[1],actual['onset_seconds'],1800),recovery=timing(rec,actual['recovery_seconds'],900),energy_error=abs(raw['request_net_kwh']-actual['request_net_kwh']),eta_error=abs(result['eta_raw']-actual['eta']),false_positive=bool(not truepos and positive),false_negative=bool(truepos and not positive),short_truth=bool(0<actual['cumulative_response_seconds']<=60),short_miss=bool(0<actual['cumulative_response_seconds']<=60 and not positive)))
            assert np.isclose(raw['request_net_kwh'],raw_energy,rtol=0,atol=1e-10)
            assert np.isclose(result['eta_raw'],raw_energy/.75,rtol=0,atol=1e-10)
        f=methods['retained']['features'];handoff.append(dict(task_id=c['task_id'],user_group=c['base_task_id'],data_kind='truth_simulation_not_field',simulation_seed=c['seed'],condition=c['condition'],request_kw=1.5,task_duration_seconds=1800,known_reference=True,features=f['selected_curve'],raw_accounting=f['accounting'],delivery_ratio=methods['retained']['eta_raw'],effective_response_present=methods['retained']['effective_response_present'],not_filtered_by_positive=True,offered_incentive=None,pre_treatment_factors=None))
    summary={}
    for name in ['cpop','labs','retained']:
        rr=[r for r in rows if r['method']==name];out=dict(n=len(rr))
        for key in ['cumulative_error','longest_error','energy_error','eta_error']:out[key]=float(np.mean([r[key] for r in rr]))
        for key in ['false_positive','false_negative','short_truth','short_miss']:out[key]=sum(r[key] for r in rr)
        for feature in ['onset','recovery']:
            vv=[r[feature] for r in rr];out[feature]=dict(n=sum(v['reference_available'] for v in vv),missing=sum(v['missing'] for v in vv),false_feature=sum(v['false_feature'] for v in vv),mae_seconds=float(np.mean([v['error_seconds'] for v in vv if v['reference_available']])) if any(v['reference_available'] for v in vv) else None)
        out['duration_primary_seconds']=.5*(out['cumulative_error']+out['longest_error']);out['task_accuracy']=1-(out['false_positive']+out['false_negative'])/len(rr);summary[name]=out
    save('known_test/outputs.json',outputs);save('known_test/metrics.json',rows);save('known_test/assessment.json',summary);save('handoff/known_features.json',handoff)
    print(json.dumps(native(summary)),flush=True)
if __name__=='__main__':main()
