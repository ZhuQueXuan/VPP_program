"""Independent event-contract, complete-outcome and grouped-effect acceptance."""
from pathlib import Path
import copy,json,sys
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from b1_api import analyze_event,analyze_events,provided_reference,estimate_event_effects
from b1_algorithm.effects import EffectConfig

OUT=Path(__file__).resolve().parent
checks=[]
def checked(name,condition):
 if not condition:raise AssertionError(name)
 checks.append(name)
def base_record(index=0,eta=.3,shift=0.):
 start=1000.+index*120+shift
 task=dict(task_id=f'task-{index}',user_id=f'user-{index//2}',meter_id=f'meter-{index//2}',
       start_min=start,end_min=start+30,notice_min=start-15,request_kw=1.5,task_pre_treatment=True)
 s=np.arange(start-15,start+45,15.);e=s+15;b=np.full(4,3.)
 p=b-np.array([0.,eta*1.5,eta*1.5,0.])
 ref=provided_reference(task,s,e,b,available_at_min=task['notice_min'])
 return dict(task=task,starts_min=s,ends_min=e,power_kw=p,reference=ref,noise_sigma_kw=.05)

base=base_record();one=analyze_event(**base)
checked('coarse_complete_event',one['status']=='ok' and one['process']['method']=='raw_coarse')
checked('independent_raw_integral',abs(one['outcome']['value']-.3)<1e-12)
checked('physical_timing_withheld',one['process']['physical_timing'] is None)
shifted=analyze_event(**base_record(shift=100000.))
checked('absolute_clock_translation',shifted['process']['features']==one['process']['features'] and shifted['outcome']['value']==one['outcome']['value'])

mutations={
 'wrong_reference_user':lambda r:r['reference'].update(user_id='another'),
 'wrong_reference_meter':lambda r:r['reference'].update(meter_id='another'),
 'wrong_reference_task':lambda r:r['reference'].update(task_id='another'),
 'wrong_reference_request':lambda r:r['reference'].update(request_kw=3.),
 'wrong_reference_notice':lambda r:r['reference'].update(notice_min=984.),
 'late_reference':lambda r:r['reference'].update(available_at_min=986.),
 'wrong_reference_grid':lambda r:r['reference']['starts_min'].__setitem__(0,984.),
 'mixed_boolean_power':lambda r:r.update(power_kw=[True,2.5,2.5,3.]),
 'numeric_strings_power':lambda r:r.update(power_kw=['3','2.5','2.5','3']),
 'missing_power':lambda r:r.update(power_kw=[3.,None,2.5,3.]),
 'infinite_power':lambda r:r.update(power_kw=[3.,float('inf'),2.5,3.]),
 'overflow_task':lambda r:r['task'].update(request_kw=10**400),
 'numeric_identity':lambda r:r['task'].update(user_id=1),
 'nonjson_reference_metadata':lambda r:r['reference'].update(window_band_eta={'width':float('nan')}),
}
for name,mutate in mutations.items():
 r=copy.deepcopy(base);mutate(r);result=analyze_event(**r)
 checked(name,result['status']=='invalid_input' and result['outcome'] is None)
 json.dumps(result,allow_nan=False)
r=copy.deepcopy(base);r['noise_sigma_kw']=True
checked('boolean_noise_unavailable',analyze_event(**r)['status']=='unavailable')
r=copy.deepcopy(base);r['reference']={'reference_status':'unavailable','reasons':['missing_pre_notice_temperature']}
checked('upstream_reference_unavailability_preserved',analyze_event(**r)['status']=='unavailable')
records=[copy.deepcopy(base),dict(task={}),base_record(1)]
batch=analyze_events(records)
checked('batch_order_and_failures',[r['status'] for r in batch]==['ok','invalid_input','ok'])

rng=np.random.default_rng(885100)
cohort=[];X=[];d=[]
for user in range(300):
 x=float(rng.uniform(-1,1));order=rng.permutation([0.,1.])
 for event,dose in enumerate(order):
  eta=.1+.2*dose+.03*x+float(rng.normal(0,.01))
  cohort.append(base_record(2*user+event,eta));X.append([x]);d.append(dose)
events=analyze_events(cohort)
assumptions=dict(pre_treatment_X=True,consistent_treatment=True,no_interference=True,
                 same_outcome_definition=True,conditional_exchangeability=None,randomized_assignment=True)
probabilities=np.full((len(events),2),.5)
cfg=EffectConfig(seed=885101,n_boot=199)
effect=estimate_event_effects(events,X,d,levels=[0.,1.],assumptions=assumptions,known_pi=probabilities,effect_config=cfg)
checked('actual_event_to_effect_pipeline',effect['status']=='causal' and effect['pipeline']['input_events']==600)
checked('event_user_grouping',effect['diagnostics']['users']==300 and effect['diagnostics']['original_user_fold_integrity'])
checked('positive_effect_numerical_sanity',abs(effect['causal_curve']['contrasts'][1]-.2)<.03)
unconfirmed=estimate_event_effects(events,X,d,levels=[0.,1.],effect_config=cfg)
checked('unconfirmed_is_association',unconfirmed['status']=='association' and unconfirmed['causal_curve'] is None and unconfirmed['inference'] is None)
unsupported=estimate_event_effects(events,X,[0.]*600,levels=[0.,1.],assumptions=assumptions,known_pi=probabilities,effect_config=cfg)
checked('sparse_dose_support_is_withheld',unsupported['status']=='unsupported' and unsupported['causal_curve'] is None)

for label,change in [
 ('no_implicit_failure_dropping',lambda e:e[3].update(outcome=None,status='unavailable')),
 ('duplicate_event_rejected',lambda e:e.__setitem__(3,copy.deepcopy(e[2]))),
 ('task_outcome_request_mismatch',lambda e:e[3]['outcome'].update(q_kw=3.)),
 ('task_outcome_window_mismatch',lambda e:e[3]['outcome'].update(window_minutes=[0.,60.])),
 ('changed_raw_eta_rejected',lambda e:e[3]['outcome'].update(value=0.)),
]:
 altered=copy.deepcopy(events);change(altered)
 result=estimate_event_effects(altered,X,d,levels=[0.,1.],effect_config=cfg)
 checked(label,result['status']=='invalid_input' and result['causal_curve'] is None)

for output in [one,events,effect,unconfirmed,unsupported]:json.dumps(output,allow_nan=False)
(OUT/'pipeline_effect_example.json').write_text(json.dumps(effect,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'coarse_event_example.json').write_text(json.dumps(one,ensure_ascii=False,indent=2),encoding='utf-8')
receipt=dict(passed=True,checks=checks,n_checks=len(checks),events=600,users=300,seed=885100,
 scope='new complete-event integration acceptance; coarse provided reference; not a new performance or coverage experiment',
 estimated_effect=effect['causal_curve']['contrasts'][1],true_generator_effect=.2)
(OUT/'pipeline_verification.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(receipt,ensure_ascii=False,indent=2))
