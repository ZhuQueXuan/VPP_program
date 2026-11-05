"""EV-only functional acceptance; constructed inputs, no performance claims."""
from pathlib import Path
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
import copy,dataclasses,hashlib,importlib.util,json,sys,time
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent;SOURCE=HERE;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'B1算法'))
from b1_api import (EVAnalysisConfig,assess_ev_recovery,analyze_event,analyze_events,provided_reference,
    estimate_event_effects,estimate_metered_effects,ReferenceWindow,load_reference_model,predict_reference,
    calibrate_window_reference,save_reference_model)
from b1_algorithm.reference import WindowCalibrationRecord
from b1_algorithm.effects import EffectConfig
from b1_algorithm.metered_effects import _metered_outcomes
from b1_algorithm import api as pipeline
from b1_algorithm.process.api import resolve_policy

def record(W=30.,q=1.5,maximum=7.2,delta=1.,eta=.5,index=0,pre=15.,post=15.,lead=15.,rebound=False):
    start=10000.+index*300.;s=start+np.arange(-pre,W+post-1e-8,delta);e=s+delta
    baseline=np.full(len(s),.6*maximum);power=baseline.copy();use=(s>=start-1e-8)&(e<=start+W+1e-8)
    power[use]-=q*eta
    if rebound:power[s>=start+W-1e-8]+=q*eta*W/post
    task=dict(task_id=f'ev-{index}',user_id=f'user-{index//2}',meter_id=f'meter-{index//2}',
        start_min=start,end_min=start+W,request_kw=q,notice_min=start-lead,task_pre_treatment=True)
    profile=EVAnalysisConfig(max_charge_kw=maximum,observation_pre_min=pre,observation_post_min=post)
    ref=provided_reference(task,s,e,baseline,available_at_min=start-lead)
    return dict(task=task,starts_min=s,ends_min=e,power_kw=power,reference=ref,noise_sigma_kw=.05,ev_config=profile)

def requirement(rec,deadline=None,remaining=None):
    t=rec['task'];asof=float(rec['starts_min'][0]);deadline=float(rec['ends_min'][-1]) if deadline is None else deadline
    if remaining is None:remaining=.6*rec['ev_config'].max_charge_kw*(deadline-asof)/60.
    return dict(task_id=t['task_id'],user_id=t['user_id'],meter_id=t['meter_id'],power_boundary='single_ev_ac_meter',
        state_as_of_min=asof,available_at_min=t['notice_min'],remaining_ac_kwh=remaining,deadline_min=deadline)

def main():
    if (HERE/'receipt.json').exists():raise RuntimeError('completed acceptance cannot be overwritten')
    started=time.perf_counter();checks=[];events=[];rows=[]
    def check(name,condition):
        assert condition,name
        checks.append(name)
    matrix=[]
    for maximum in (3.6,7.2,11.):
        for W in (15.,30.,60.):
            for fraction in (.25,.5):
                for delta in (1/6,1.,15.):
                    matrix.append(record(W,q=maximum*fraction,maximum=maximum,delta=delta,index=len(matrix)))
    config=pipeline._default_runtime_config();config.update(artifact_dir=str(HERE/'native_matrix'),timeout_seconds=180)
    results=analyze_events(matrix,process_config=config)
    check('54 legal multi-power multi-task multi-meter inputs complete',len(results)==54 and all(r['status']=='ok' for r in results))
    for rec,result in zip(matrix,results):
        q=rec['task']['request_kw'];W=rec['task']['end_min']-rec['task']['start_min'];dt=rec['ends_min'][0]-rec['starts_min'][0]
        # Subtracting absolute minute clocks introduces picosecond-scale grid
        # rounding; the requested exact integral is compared at 1e-9 ratio.
        check('raw eta matrix '+rec['task']['task_id'],abs(result['outcome']['value']-.5)<1e-9)
        expected='guarded' if dt<.5 else 'ride_template'
        check('actual resolution route '+rec['task']['task_id'],result['process']['selection_evidence']['policy']==expected)
        check('physical timing remains unidentified '+rec['task']['task_id'],result['process']['physical_timing'] is None)
        z,_,_=_metered_outcomes([rec]);start=rec['task']['start_min'];use=(rec['starts_min']>=start-1e-8)&(rec['ends_min']<=start+W+1e-8)
        independent=-sum(float(p)*float(b-a) for a,b,p in zip(rec['starts_min'][use],rec['ends_min'][use],rec['power_kw'][use]))/(q*W)
        check('meter-only variable denominator '+rec['task']['task_id'],abs(z[0]-independent)<1e-12)
        rows.append(dict(task_id=rec['task']['task_id'],duration_min=W,request_kw=q,max_charge_kw=rec['ev_config'].max_charge_kw,
            meter_min=float(dt),eta=result['outcome']['value'],method=result['process']['method'],status=result['status'],metered_Z=float(z[0])))
    pd.DataFrame(rows).to_csv(HERE/'functional_matrix.csv',index=False)
    (HERE/'matrix_events.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    extra=record(15.,q=.9,index=100,pre=30.,post=15.,lead=30.)
    long=record(60.,q=3.6,index=101,pre=60.,post=30.,lead=60.)
    values=analyze_events([extra,long])
    check('custom pre/post and lead do not alter meter routing',all(r['status']=='ok' and r['process']['method']=='RIDE_template_average' for r in values))
    check('same60-row counterexample uses actual one-minute interval',len(extra['power_kw'])==60 and values[0]['process']['selection_evidence']['meter_delta_min']==1.)
    odd=record(15.,q=.9,index=102)
    odd['starts_min']=odd['starts_min'][::2];odd['ends_min']=odd['starts_min']+2;odd['power_kw']=odd['power_kw'][::2]
    odd['reference']=provided_reference(odd['task'],odd['starts_min'],odd['ends_min'],np.full(len(odd['starts_min']),4.32),available_at_min=odd['task']['notice_min'])
    ordered=analyze_events([extra,odd,long])
    check('one bad meter grid does not poison other events',[r['status'] for r in ordered]==['ok','unavailable','ok'])
    low=record(15.,q=.1,index=103);low['noise_sigma_kw']=.15
    check('low signal-to-noise is explicitly uncalibrated',analyze_event(**low)['process']['selection_evidence']['request_less_than_three_meter_sigma'])
    impossible=record(15.,q=7.2,maximum=3.6,eta=0,index=104)
    imp=analyze_event(**impossible)
    check('impossible requests retained as diagnostic rather than removed',imp['status']=='ok' and imp['process']['selection_evidence']['request_exceeds_declared_max'])
    explicit=analyze_events([matrix[i] for i in (1,7,13,19,25,31,37,43,49)],process_method='cpop',process_config=config)
    check('9 variable-task original CPOP calls run',all(r['status']=='ok' and r['process']['method']=='CPOP' for r in explicit))
    # Legacy numeric migration from the archived previous source, no rerun of a main study.
    spec=importlib.util.spec_from_file_location('_b1_ev_legacy',SOURCE/'before_source/b1_algorithm/__init__.py',submodule_search_locations=[str(SOURCE/'before_source/b1_algorithm')])
    legacy=importlib.util.module_from_spec(spec);sys.modules[spec.name]=legacy;spec.loader.exec_module(legacy)
    max_parity=0.
    for i,delta in enumerate((1/6,1.,15.)):
        for eta in (0.,.3,.9):
            rec=record(delta=delta,eta=eta,index=200+i)
            old={k:v for k,v in rec.items() if k!='ev_config'}
            before=legacy.analyze_event(**old,process_config=config);after=analyze_event(**rec,process_config=config)
            diff=float(np.max(np.abs(np.asarray(before['process']['reduction_interval_kw'])-after['process']['reduction_interval_kw'])))
            max_parity=max(max_parity,diff)
            check('legacy curve and accounting '+str((delta,eta)),diff<1e-9 and abs(before['outcome']['value']-after['outcome']['value'])<1e-12)
    # Service accounting uses actual energy and caller-declared deadline, not fitted recovery.
    met=record(W=30.,q=1.5,maximum=7.2,eta=.5,index=300,post=30.,rebound=True)
    met['ev_requirement']=requirement(met)
    unmet=record(W=30.,q=1.5,maximum=7.2,eta=.5,index=301,post=30.)
    unmet['ev_requirement']=requirement(unmet)
    censored=record(index=302);censored['ev_requirement']=requirement(censored,deadline=censored['task']['start_min']+60.)
    recovered=analyze_events([met,unmet,censored])
    check('declared service energy can be met',recovered[0]['ev_service_recovery']['status']=='met')
    check('power recovery is not energy-service satisfaction',recovered[1]['process']['features']['raw_observed']['power_recovery_status']=='recovered' and recovered[1]['ev_service_recovery']['status']=='unmet')
    check('short post-window remains right-censored',recovered[2]['ev_service_recovery']['status']=='right_censored')
    no_max=dataclasses.replace(met['ev_config'],max_charge_kw=None)
    check('missing upper bound does not block metered service energy',assess_ev_recovery(met['task'],met['starts_min'],met['ends_min'],met['power_kw'],met['ev_requirement'],config=no_max)['status']=='met')
    service_cases=[]
    for label,change,expected in (
        ('missing declaration',lambda r:r.update(ev_requirement=None),'unavailable'),
        ('late information',lambda r:r['ev_requirement'].update(available_at_min=r['task']['notice_min']+1),'invalid_input'),
        ('wrong meter',lambda r:r['ev_requirement'].update(meter_id='other'),'invalid_input'),
        ('station boundary',lambda r:r['ev_requirement'].update(power_boundary='station_ac_meter'),'unavailable'),
        ('cut deadline',lambda r:r['ev_requirement'].update(deadline_min=r['task']['end_min']+.5),'unavailable'),
        ('missing state prefix',lambda r:r['ev_requirement'].update(state_as_of_min=r['starts_min'][0]-1),'unavailable'),
    ):
        rec=copy.deepcopy(met);change(rec);result=analyze_event(**rec)
        check('service '+label,result['ev_service_recovery']['status']==expected and result['outcome'] is not None)
        service_cases.append(dict(case=label,service=result['ev_service_recovery']))
    moved=copy.deepcopy(met)
    for key in ('start_min','end_min','notice_min'):moved['task'][key]+=100000.
    moved['starts_min']+=100000.;moved['ends_min']+=100000.
    for key in ('state_as_of_min','available_at_min','deadline_min'):moved['ev_requirement'][key]+=100000.
    moved['reference']=provided_reference(moved['task'],moved['starts_min'],moved['ends_min'],np.full(len(moved['power_kw']),4.32),available_at_min=moved['task']['notice_min'])
    moved_result=analyze_event(**moved)
    check('task and service global-clock translation invariant',abs(moved_result['ev_service_recovery']['delivered_ac_kwh']-recovered[0]['ev_service_recovery']['delivered_ac_kwh'])<1e-12 and moved_result['ev_service_recovery']['status']=='met')
    (HERE/'recovery_events.json').write_text(json.dumps(recovered+[moved_result],ensure_ascii=False,indent=2),encoding='utf-8')
    (HERE/'recovery_edge_cases.json').write_text(json.dumps(service_cases,ensure_ascii=False,indent=2),encoding='utf-8')
    # Predictions from an existing frozen model, with explicit synthetic feature provenance.
    fixture=json.loads((ROOT/'work/b1_formal_v1_20261029/reference/query_fixture.json').read_text(encoding='utf-8'))
    base_window=ReferenceWindow(**fixture);model=load_reference_model(ROOT/'work/b1_formal_v1_20261029/reference/artifact')
    def query_window(rec):
        t=rec['task'];notice=t['notice_min'];n=len(rec['power_kw'])
        return dataclasses.replace(base_window,task_id=t['task_id'],user_id=t['user_id'],meter_id=t['meter_id'],resource_type='EV',
            task_start_min=t['start_min'],task_end_min=t['end_min'],request_kw=t['request_kw'],notice_min=notice,
            starts_min=rec['starts_min'],ends_min=rec['ends_min'],pre_starts_min=notice+np.arange(-60.,0.),
            pre_ends_min=notice+np.arange(-59.,1.),pre_power_kw=np.full(60,3.),pre_available_min=notice,
            prior_mean_kw=np.full(n,3.),prior_available_min=notice-1.,prior_source_count=2,
            prior_source_ids=('past-a','past-b'),calendar_available_min=notice-1.,temperature_available_min=notice-1.)
    assumptions=dict(pre_treatment_X=True,consistent_treatment=True,no_interference=True,same_outcome_definition=True,randomized_assignment=True,conditional_exchangeability=None)
    effect_rows=[];all_effect_events=[];all_meter_records=[];all_X=[];all_d=[]
    for W,q in ((15.,.9),(30.,1.8),(60.,3.6)):
        group=[];X=[];D=[]
        for user in range(30):
            for arm in (0.,1.):
                i=1000+int(W)*100+2*user+int(arm);eta=.1+.2*arm+.01*np.sin(user)
                rec=record(W=W,q=q,maximum=7.2,eta=eta,index=i)
                win=query_window(rec);pred=predict_reference(model,win)
                check('predicted reference available '+str(i),pred.reference_status=='available')
                rec['reference']=pred;group.append(rec);X.append([np.sin(user)]);D.append(arm)
        group_events=analyze_events(group)
        check('unknown-reference chain W'+str(W),all(e['status']=='ok' for e in group_events))
        cfg=EffectConfig(seed=int(W),n_boot=199);prob=np.full((60,2),.5)
        effect=estimate_event_effects(group_events,X,D,levels=[0.,1.],assumptions=assumptions,known_pi=prob,effect_config=cfg)
        meter=estimate_metered_effects(group,X,D,levels=[0.,1.],assumptions=assumptions,known_pi=prob,effect_config=cfg)
        check('same-task effects W'+str(W),effect['status']=='causal' and abs(effect['causal_curve']['contrasts'][1]-.2)<1e-9)
        check('same-task meter-only effects W'+str(W),meter['status']=='causal' and abs(meter['causal_curve']['contrasts'][1]-.2)<1e-9)
        effect_rows.append(dict(duration_min=W,request_kw=q,events=60,eta_effect=effect['causal_curve']['contrasts'][1],metered_effect=meter['causal_curve']['contrasts'][1]))
        all_effect_events.extend(group_events);all_meter_records.extend(group);all_X.extend(X);all_d.extend(D)
    check('heterogeneous task effects cannot be silently pooled',estimate_event_effects(all_effect_events,all_X,all_d,levels=[0.,1.])['status']=='invalid_input')
    check('heterogeneous metered tasks cannot be silently pooled',estimate_metered_effects(all_meter_records,all_X,all_d,levels=[0.,1.])['status']=='invalid_input')
    pd.DataFrame(effect_rows).to_csv(HERE/'effect_chain.csv',index=False)
    # New-task calibration does not borrow an old task's half-width.
    cal_rec=record(index=5000);w=query_window(cal_rec)
    cal=[]
    for user in range(10):
        wc=dataclasses.replace(w,task_id='cal-'+str(user),user_id='cal-user-'+str(user),meter_id='cal-meter-'+str(user),
            task_start_min=20000.,task_end_min=20030.,notice_min=19985.,starts_min=20000.+np.arange(-15.,45.),ends_min=20000.+np.arange(-14.,46.),
            pre_starts_min=19985.+np.arange(-60.,0.),pre_ends_min=19985.+np.arange(-59.,1.),pre_available_min=19985.,
            prior_available_min=19984.,calendar_available_min=19984.,temperature_available_min=19984.)
        pred=predict_reference(model,wc);assert pred.reference_status=='available',pred.reasons
        cal.append(WindowCalibrationRecord(wc,pred.reference_kw+.1,20045.,True))
    calibrate_window_reference(model,cal,20100.)
    matched=predict_reference(model,w);unseen=predict_reference(model,dataclasses.replace(w,task_end_min=w.task_start_min+15.))
    check('matched task calibration signature retained',matched.window_band_eta['task_signature_seen_in_calibration'])
    check('new task gets no inherited old calibration width',unseen.window_band_eta['halfwidth_eta'] is None and not unseen.window_band_eta['task_signature_seen_in_calibration'])
    artifact=HERE/'reference_artifact';save_reference_model(model,artifact);restored=load_reference_model(artifact)
    check('new optional calibration metadata roundtrip',np.array_equal(predict_reference(restored,w).reference_kw,matched.reference_kw))
    receipt=dict(passed=True,n_checks=len(checks),checks=checks,functional_matrix_rows=54,native_CPOP_explicit_cases=9,
        predicted_reference_chain_events=180,causal_task_strata=3,legacy_parity_max_curve_difference=max_parity,
        actual_EV_input_model_reused=True,model_optimization_used_as_observed_response=False,
        elapsed_seconds=time.perf_counter()-started,scope='EV functional and interface acceptance only; constructed examples, not independent performance or real capability validation')
    (HERE/'receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in receipt.items() if k!='checks'},indent=2),flush=True)

if __name__=='__main__':
    if len(sys.argv)>1:
        if len(sys.argv)!=2 or sys.argv[1] not in ('post_review','final_review'):raise ValueError('supported separate acceptance output name required')
        HERE=SOURCE/sys.argv[1];HERE.mkdir(exist_ok=True)
    main()
