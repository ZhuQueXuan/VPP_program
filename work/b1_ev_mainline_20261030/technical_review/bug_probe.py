"""Small contract counterexamples only; no main study or performance rerun."""
from pathlib import Path
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
import sys,json,copy,dataclasses,importlib.util
import numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT/'B1算法'))
from b1_api import analyze_events,provided_reference,EVFactorStudy,fit_ev_factor_curve,select_ev_reference
from b1_algorithm.factors import _inputs
from b1_algorithm.reference.core import ReferenceWindow,ReferenceModel
spec=importlib.util.spec_from_file_location('independent_ev_sim',HERE.parent/'simulation.py')
sim=importlib.util.module_from_spec(spec);spec.loader.exec_module(sim)

class Spy:
    def __init__(self):self.calls=[]
    def predict(self,x):self.calls.append(np.array(x));return np.full(len(x),3.65)

def main():
    factual,_,_=sim.generate(5398100,n_users=4,events_per_user=2,W=5)
    records=[]
    for r in factual:
        records.append(dict(task=r['task'],starts_min=r['starts_min'],ends_min=r['ends_min'],power_kw=r['power_kw'],noise_sigma_kw=r['noise_sigma_kw'],
          reference=provided_reference(r['task'],r['starts_min'],r['ends_min'],r['reference_window']['prior_mean_kw'],available_at_min=r['task']['notice_min'])))
    events=analyze_events(records,process_method='conservative');factors=[r['factor_record'] for r in factual]
    study=EVFactorStudy('probe','yuan/kWh')
    result={};base=_inputs(events,factors,study)
    result['base_events_completed']=all(e['status']=='ok' for e in events)
    bad=copy.deepcopy(events);bad[0]['process'],bad[1]['process']=bad[1]['process'],bad[0]['process']
    try:out=_inputs(bad,factors,study);result['swapped_process_wrong_task_accepted']=True
    except (ValueError,KeyError,TypeError):result['swapped_process_wrong_task_accepted']=False
    bad=copy.deepcopy(events);bad[0]['process']['features']['selected_curve']['cumulative_response_seconds']=3.14159
    try:out=_inputs(bad,factors,study);result['fractional_one_minute_duration_accepted']=out['y'][0]
    except (ValueError,KeyError,TypeError):result['fractional_one_minute_duration_accepted']=False
    bad=copy.deepcopy(events)
    for e in bad:e['task']['request_kw']=2.
    try:out=_inputs(bad,factors,study);result['task_request_disagrees_with_completed_process_accepted']=out['signature'][1]
    except (ValueError,KeyError,TypeError):result['task_request_disagrees_with_completed_process_accepted']=False
    try:
        fit_ev_factor_curve(events,factors,None,dose_domain=[0,2.4],assumptions={'randomized_assignment':False},continuous_assignment=True)
        result['invalid_study_uncaught_exception']=None
    except Exception as exc:result['invalid_study_uncaught_exception']=type(exc).__name__+': '+str(exc)
    # Same synthetic trajectories, with explicit valid caller calendar that
    # differs from the arbitrary numeric minute origin.
    w=ReferenceWindow(**factual[0]['reference_window'])
    expected_hour=(w.clock_hour+3)%24;expected_weekday=(w.weekday+2)%7
    w=dataclasses.replace(w,clock_hour=expected_hour,weekday=expected_weekday)
    spy=Spy();model=ReferenceModel(spy,'functional-probe',-1e12,0,(),(),'probe')
    out=select_ev_reference(model,w,factual[0]['historical_non_event'])
    result['selector_current_reference_status']=out['reference'].reference_status
    result['historical_clock_expected_same_hour']=expected_hour
    result['historical_clock_actual']=float(spy.calls[0][0,1])
    result['historical_calendar_assumes_arbitrary_origin']=bool(abs(spy.calls[0][0,1]-expected_hour)>1e-8)
    foreign=copy.deepcopy(factual[0]['historical_non_event'])
    for h in foreign:h.update(user_id='foreign-user',meter_id='foreign-meter')
    try:out=select_ev_reference(model,w,foreign);result['foreign_user_meter_history_accepted']=out['reference'].reference_status=='available'
    except ValueError:result['foreign_user_meter_history_accepted']=False
    late=copy.deepcopy(factual[0]['historical_non_event'])
    for h in late:h.update(calendar_available_min=h['available_at_min'],temperature_available_min=h['available_at_min'])
    try:out=select_ev_reference(model,w,late);result['after_pseudo_notice_weather_calendar_accepted']=out['reference'].reference_status=='available'
    except ValueError:result['after_pseudo_notice_weather_calendar_accepted']=False
    result.update(scope='small counterexamples only; no scientific experiment rerun',production_files_modified=False)
    result['audit_export_note']='Initial bug_probe.json export hit numpy bool serialization; partial original preserved. This rerun only fixes audit serialization.'
    path=HERE/'bug_probe_checked.json'
    with path.open('x',encoding='utf-8') as stream:json.dump(result,stream,ensure_ascii=False,indent=2)
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
