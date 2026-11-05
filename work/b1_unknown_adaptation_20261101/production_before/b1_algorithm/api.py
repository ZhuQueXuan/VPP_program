"""Integrated B1 event-to-population pipeline, separate from B2/B3 control APIs."""
import hashlib
import json
from pathlib import Path
from collections.abc import Mapping
import numpy as np
from .contracts import VERSION,SCHEMA,array,number,task_contract,bound_reference,UnavailableReference
from .resources.ev import assess_ev_recovery

def analyze_event(task,starts_min,ends_min,power_kw,reference,noise_sigma_kw,*,process_config=None,process_method=None,ev_config=None,ev_requirement=None):
 """Reference and observed powers must share the bound event and meter grid."""
 record=dict(task=task,starts_min=starts_min,ends_min=ends_min,power_kw=power_kw,reference=reference,noise_sigma_kw=noise_sigma_kw,
             ev_config=ev_config,ev_requirement=ev_requirement)
 return analyze_events([record],process_config=process_config,process_method=process_method)[0]

def _empty_event():
 return dict(schema_version=SCHEMA,algorithm_version=VERSION,status='invalid_input',reasons=[],task=None,process=None,outcome=None,reference=None)

def _default_runtime_config():
 package=Path(__file__).resolve().parent;project=package.parents[1]
 metadata=json.loads((package/'runtime.json').read_text(encoding='utf-8'))
 for name,expected in metadata['sha256'].items():
  path=project/name
  if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
   raise ValueError('configured native runtime missing or changed: '+name)
 return {name:str(project/metadata[name]) for name in ['rscript_path','r_library','artifact_dir']}|{'timeout_seconds':metadata['timeout_seconds']}

def _prepare_event(record,ev_config=None):
 task=record['task'];t=task_contract(task)
 s=array(record['starts_min'],'starts_min');e=array(record['ends_min'],'ends_min');p=array(record['power_kw'],'power_kw')
 if s.shape!=e.shape or p.shape!=s.shape or np.any(e<=s):raise ValueError('matching positive-width metering intervals required')
 b,ref=bound_reference(record['reference'],t,s,e)
 relative_task={**t,'start_min':0.,'end_min':t['end_min']-t['start_min'],'notice_min':t['notice_min']-t['start_min']}
 request=dict(starts_min=s-t['start_min'],ends_min=e-t['start_min'],power_kw=p,reference_kw=b,
              task=relative_task,noise_sigma_kw=record['noise_sigma_kw'],ev_config=record.get('ev_config') if record.get('ev_config') is not None else ev_config)
 return dict(task=t,s=s,e=e,p=p,b=b,reference=ref,request=request)

def _finish_event(context,process):
 t=context['task'];ref=context['reference'];s=context['s'];e=context['e'];p=context['p'];b=context['b']
 result=dict(schema_version=SCHEMA,algorithm_version=VERSION,status='invalid_input',reasons=[],
             task=None,process=None,outcome=None,reference=None)
 try:
  result.update(task=t,reference=ref,process=process,status=process['status'])
  result['reasons']=process.get('reasons',[process['reason']] if process.get('reason') else [])
  eta=process.get('eta_raw')
  if process['status'] in ('ok','degraded') and eta is not None:
   result['outcome']=dict(name='eta_raw',unit='ratio',value=float(eta),task_pre_treatment=t['task_pre_treatment'],
       window_minutes=[0.,t['end_min']-t['start_min']],q_kw=t['request_kw'],
       definition='raw width-weighted supplied pre-notice reference minus actual power, divided by pre-fixed request energy',
       process_fit_used_in_energy=False,reference_process_uncertainty_propagated=False)
  result['input_digest']=hashlib.sha256(json.dumps(dict(task=t,starts=s.tolist(),ends=e.tolist(),power=p.tolist(),reference=b.tolist()),sort_keys=True).encode()).hexdigest()
  json.dumps(result,allow_nan=False)
  return result
 except (ValueError,TypeError,KeyError) as exc:
  result.update(status='invalid_input',reasons=[dict(code='event_contract',detail=str(exc))],outcome=None,reference=None,process=None)
  return result

def analyze_events(records,*,process_config=None,process_method=None,ev_config=None):
 """Validate each event, batch native CPOP requests, preserve order and failures."""
 if not isinstance(records,(list,tuple)):raise ValueError('records must be an ordered list of event records')
 results=[None]*len(records);contexts=[];indices=[];services={}
 for index,record in enumerate(records):
  try:
   if not isinstance(record,Mapping):raise ValueError('event record must be a mapping')
   profile=record.get('ev_config') if record.get('ev_config') is not None else ev_config
   services[index]=assess_ev_recovery(record.get('task'),record.get('starts_min'),record.get('ends_min'),record.get('power_kw'),record.get('ev_requirement'),config=profile)
   contexts.append(_prepare_event(record,ev_config));indices.append(index)
  except (ValueError,TypeError,KeyError) as exc:
   result=_empty_event()
   result['status']='unavailable' if isinstance(exc,UnavailableReference) else 'invalid_input'
   result['reasons']=[dict(code='reference_unavailable' if isinstance(exc,UnavailableReference) else 'event_contract',detail=str(exc))];results[index]=result
 if contexts:
  from .process.batch import identify_process_batch
  from .process.api import resolve_policy,needs_native
  try:
   config=process_config;native_reason=None
   native_needed=False
   for c in contexts:
    try:native_needed=native_needed or needs_native(len(c['s']),resolve_policy(len(c['s']),process_method,delta_min=float(c['e'][0]-c['s'][0])))
    except (ValueError,TypeError):pass
   if config is None and native_needed:
    try:config=_default_runtime_config()
    except (ValueError,OSError) as exc:native_reason='runtime_configuration: '+str(exc)
   processes=identify_process_batch([c['request'] for c in contexts],config=config,method=process_method,native_unavailable_reason=native_reason)
  except (ValueError,OSError) as exc:
   processes=[dict(status='unavailable',method=None,reason='runtime_configuration: '+str(exc),eta_raw=None,
                   features=None,physical_timing=None,uncertainty_status='unavailable') for _ in contexts]
  if len(processes)!=len(contexts):raise RuntimeError('process batch violated event count contract')
  for index,context,process in zip(indices,contexts,processes):results[index]=_finish_event(context,process)
 for index,service in services.items():results[index]['ev_service_recovery']=service
 return results

def estimate_event_effects(event_results,X,treatment,*,assumptions=None,known_pi=None,levels=None,effect_config=None,target_population='supplied_event_population',
                          dose_mode='discrete',dose_domain=None,grid=None,reference_dose=None,incentive_unit=None,known_density=None,continuous_config=None,continuous_assignment=None):
 """Consume completed same-definition event outcomes; never silently drop failures."""
 invalid=dict(schema_version='b1.pipeline-effects.v1',algorithm_version=VERSION,status='invalid_input',reasons=[],causal_curve=None)
 try:
  if not isinstance(event_results,(list,tuple)) or not event_results:raise ValueError('nonempty completed event results required')
  y=[];users=[];keys=[];seen=set();seen_windows={};refs=set();predeclared=True
  for event in event_results:
   if not isinstance(event,Mapping) or event.get('schema_version')!=SCHEMA or event.get('algorithm_version')!=VERSION or event.get('status') not in ('ok','degraded') or event.get('outcome') is None:
    raise ValueError('every event must have a valid B1 outcome; no complete-case dropping is implicit')
   task=task_contract(event['task']);outcome=event['outcome'];key=(task['task_id'],task['user_id'],task['meter_id'])
   if key in seen:raise ValueError('duplicate event identity')
   seen.add(key)
   windows=seen_windows.setdefault(task['meter_id'],[])
   if any(abs(start-task['start_min'])<=1e-9 and abs(end-task['end_min'])<=1e-9 for start,end in windows):
    raise ValueError('duplicate physical meter window, including renamed tasks or users')
   windows.append((task['start_min'],task['end_min']))
   if outcome.get('name')!='eta_raw' or outcome.get('unit')!='ratio' or outcome.get('process_fit_used_in_energy') is not False:
    raise ValueError('common raw eta definition required')
   window=array(outcome['window_minutes'],'outcome.window_minutes')
   q=number(outcome['q_kw'],'outcome.q_kw');value=number(outcome['value'],'outcome.value')
   expected=np.array([0.,task['end_min']-task['start_min']])
   if window.shape!=(2,) or not np.allclose(window,expected,atol=1e-10,rtol=0) or not np.isclose(q,task['request_kw'],atol=1e-12,rtol=0):
    raise ValueError('event task and outcome request/window disagree')
   if outcome.get('task_pre_treatment') is not task['task_pre_treatment']:
    raise ValueError('event task and outcome pre-treatment declaration disagree')
   process=event.get('process')
   if not isinstance(process,Mapping) or process.get('status')!=event['status'] or not np.isclose(number(process.get('eta_raw'),'process.eta_raw'),value,atol=1e-12,rtol=0):
    raise ValueError('outcome must match this completed process raw integral')
   if outcome.get('reference_process_uncertainty_propagated') is not False:
    raise ValueError('full reference/process uncertainty is not certified')
   signature=(tuple(window.tolist()),q)
   keys.append(signature);y.append(value);users.append(task['user_id'])
   refs.add(event['reference']['reference_status'])
   predeclared=predeclared and task['task_pre_treatment'] is True
  if any(k!=keys[0] for k in keys):raise ValueError('heterogeneous task windows/requests need a separate causal target; cannot silently pool')
  from .effects import fit_effects,DEFAULT_LEVELS
  context=dict(task_id='common_task_definition',outcome_name='eta_raw',outcome_unit='ratio',
       window_minutes=list(keys[0][0]),q_kw=keys[0][1],target_population=target_population,
       task_pre_treatment=predeclared,reference_status=','.join(sorted(refs)),reference_uncertainty='not_propagated')
  if dose_mode=='continuous':
   if levels is not None or known_pi is not None or effect_config is not None:raise ValueError('continuous mode uses known_density/continuous_config, not discrete levels/probabilities/config')
   from .effects.continuous import fit_continuous_effects
   result=fit_continuous_effects(X,treatment,y,users,task=context,assumptions=assumptions,known_density=known_density,
       dose_domain=dose_domain,grid=grid,reference_dose=reference_dose,incentive_unit=incentive_unit,config=continuous_config,continuous_assignment=continuous_assignment)
  elif dose_mode=='discrete':
   result=fit_effects(X,treatment,y,users,levels=DEFAULT_LEVELS if levels is None else levels,
       task=context,assumptions=assumptions,known_pi=known_pi,config=effect_config)
  else:raise ValueError('dose_mode must be continuous or discrete')
  result['algorithm_version']=VERSION
  result['pipeline']=dict(input_events=len(y),input_users=len(set(users)),failed_events_dropped=0,
       outcome_from_raw_event_integrals=True,process_fit_used_in_energy=False,
       reference_process_uncertainty_propagated=False)
  return result
 except (ValueError,TypeError,KeyError) as exc:
  invalid['reasons']=[dict(code='pipeline_contract',detail=str(exc))]
  return invalid


def estimate_event_curve(event_results,X,incentive,**options):
 """Continuous offered incentive amount at one common task; direct queries."""
 return estimate_event_effects(event_results,X,incentive,dose_mode='continuous',**options)
