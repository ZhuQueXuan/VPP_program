"""Frozen algorithms on actual observed ordinary charging, no simulation."""
from common import *
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime,timezone
from b1_algorithm.reference.core import ReferenceWindow
from b1_algorithm.reference.reliable import load_ev_reliable_reference_model,predict_ev_reliable_reference
from b1_algorithm.api import analyze_events,_default_runtime_config

def duration(curve):
    a=np.asarray(curve)[15:45]>=.15;edges=np.diff(np.r_[False,a,False].astype(int));runs=np.flatnonzero(edges==-1)-np.flatnonzero(edges==1)
    return dict(cumulative_seconds=float(a.sum()*60),longest_seconds=float(max(runs,default=0)*60),positive=bool(a.any()))

def main():
    for path,expected in read('freeze.json')['source_sha256'].items():assert sha(ROOT/path)==expected,path
    groups=defaultdict(dict)
    for row in read('dortmund_minutes_checked.json'):groups[row['recording']][row['minute']]=row
    model=load_ev_reliable_reference_model(ROOT/'work/b1_reliability_20261031/study/models/reliable_reference.json');records=[];ledger=[];excluded=[]
    for c in read('selection.json'):
        rows=groups[c['member']];a=c['analysis_start_minute'];origin=rows[a]['origin_ms']/60000.;start=origin+a+15.;notice=origin+a
        prefix=np.array([rows[i]['power_kw'] for i in range(a-60,a)]);h1=np.array([rows[i]['power_kw'] for i in range(a-180,a-120)]);h2=np.array([rows[i]['power_kw'] for i in range(a-120,a-60)])
        s=origin+a+np.arange(60);p=np.array([rows[i]['power_kw'] for i in range(a,a+60)]);dt=datetime.fromtimestamp(start*60,tz=timezone.utc)
        task=dict(task_id=c['case_id'],user_id=c['member'],meter_id=c['member']+'::grid-PQA',start_min=start,end_min=start+30,notice_min=notice,request_kw=1.5,resource_type='EV',task_pre_treatment=True)
        w=ReferenceWindow(task_id=task['task_id'],user_id=task['user_id'],meter_id=task['meter_id'],resource_type='EV',task_start_min=start,task_end_min=start+30,request_kw=1.5,notice_min=notice,
            starts_min=s,ends_min=s+1,pre_starts_min=origin+np.arange(a-60,a),pre_ends_min=origin+np.arange(a-59,a+1),pre_power_kw=prefix,pre_available_min=notice,
            prior_mean_kw=.5*(h1+h2),prior_available_min=origin+a-60,prior_source_count=2,prior_source_ids=(c['member']+f'::minutes{a-180}-{a-120}',c['member']+f'::minutes{a-120}-{a-60}'),
            clock_hour=dt.hour+dt.minute/60+dt.second/3600,weekday=dt.weekday(),calendar_available_min=notice,
            temperature_c=25.,temperature_available_min=notice,prior_sources_non_event=True)
        ref=predict_ev_reliable_reference(model,w)
        ledger.append(dict(selection=c,reference_window=asdict(w),reference=asdict(ref),
            unused_temperature_placeholder='25C required numeric API field; old31-feature model does not read temperature/calendar, not a measured ambient value',actual_task_dispatched=False,
            reference_case_role='Retrospective external validation; model trained on simulations, not a claim that model was deployed when historical data were collected'))
        if ref.reference_status!='available':excluded.append(dict(case_id=c['case_id'],reason=ref.reasons));continue
        records.append(dict(task=task,starts_min=s,ends_min=s+1,power_kw=p,reference=asdict(ref),noise_sigma_kw=.05))
    write('input_ledger.json',ledger);write('reference_unavailable.json',excluded);write('records.json',records)
    config=_default_runtime_config();config['timeout_seconds']=180;config['artifact_dir']=str(HERE/'native/old')
    old=analyze_events(records,process_config=config,process_method='duration_fusion');config['artifact_dir']=str(HERE/'native/new')
    new=analyze_events(records,process_config=config,process_method='reference_tracked_duration')
    write('old_events.json',old);write('new_events.json',new)
    helper=load(ROOT/'work/b1_cpop_fine_v3_20261031/common.py','unchanged_labs_real_batch');helper.HERE=HERE
    arrays=[]
    for record,before,after in zip(records,old,new):
        assert before['status']=='ok',before['reasons'];assert after['status']=='ok',after['reasons']
        arrays.append(np.array(record['reference']['reference_kw'])-record['power_kw'])
        arrays.append(np.array(after['process']['conditional_reference_interval_kw'])-record['power_kw'])
    (HERE/'native/labs').mkdir(parents=True,exist_ok=True);labs,meta=helper.labs_batch(arrays,'native/labs')
    output=[]
    for i,(record,before,after) in enumerate(zip(records,old,new)):
        power=np.array(record['power_kw']);forecast=np.array(record['reference']['reference_kw']);conditional=np.array(after['process']['conditional_reference_interval_kw']);use=slice(15,45)
        methods=dict(original_cpop=before['process']['reduction_interval_kw'],retained=before['process']['duration_state_curve_kw'],
            same_corrected_cpop=after['process']['reduction_interval_kw'],current=after['process']['duration_state_curve_kw'],
            original_labs=labs[2*i]['prediction'],same_corrected_labs=labs[2*i+1]['prediction'])
        assert before['outcome']['value']==after['outcome']['value'] and before['reference']==after['reference']
        output.append(dict(case_id=record['task']['task_id'],recording=record['task']['user_id'],observed_power_mean_kw=float(power[use].mean()),
            prior_prediction_RMSE_kw=float(np.sqrt(np.mean((forecast[use]-power[use])**2))),conditional_prediction_RMSE_kw=float(np.sqrt(np.mean((conditional[use]-power[use])**2))),
            prior_prediction_MAE_kw=float(np.mean(abs(forecast[use]-power[use]))),conditional_prediction_MAE_kw=float(np.mean(abs(conditional[use]-power[use]))),
            methods={m:dict(prediction=p,**duration(p)) for m,p in methods.items()},
            no_new_regulation_dispatched=True,ground_truth_role='Actual meter power for background forecasting; not a labelled DR response duration'))
    write('results.json',output)
    summary=dict(selected=len(ledger),available_references=len(records),unavailable_references=excluded,records=len({r['recording'] for r in output}),
        prior_RMSE_kw=float(np.sqrt(np.mean([r['prior_prediction_RMSE_kw']**2 for r in output]))),conditional_RMSE_kw=float(np.sqrt(np.mean([r['conditional_prediction_RMSE_kw']**2 for r in output]))),
        prior_MAE_kw=float(np.mean([r['prior_prediction_MAE_kw'] for r in output])),conditional_MAE_kw=float(np.mean([r['conditional_prediction_MAE_kw'] for r in output])),
        RMSE_improved_windows=sum(r['conditional_prediction_RMSE_kw']<r['prior_prediction_RMSE_kw'] for r in output),
        background_outputs={m:dict(positive_windows=sum(r['methods'][m]['positive'] for r in output),cumulative_seconds_mean=float(np.mean([r['methods'][m]['cumulative_seconds'] for r in output])),longest_seconds_mean=float(np.mean([r['methods'][m]['longest_seconds'] for r in output]))) for m in output[0]['methods']},
        real_response_duration_MAE=None,real_short_response_sensitivity=None,all_inputs_actual_meter_data=True,no_synthetic_response_or_noise=True,models_retrained=False)
    write('summary.json',summary);print(json.dumps(native(summary)),flush=True)
if __name__=='__main__':main()
