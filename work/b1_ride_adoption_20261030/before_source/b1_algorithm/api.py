"""Integrated B1 event-to-population pipeline, separate from B2/B3 control APIs."""
import hashlib
import json
from pathlib import Path
from collections.abc import Mapping
import numpy as np
from .contracts import VERSION,SCHEMA,array,number,task_contract,bound_reference,UnavailableReference

def analyze_event(task,starts_min,ends_min,power_kw,reference,noise_sigma_kw,*,process_config=None):
 """Reference and observed powers must share the bound event and meter grid."""
 record=dict(task=task,starts_min=starts_min,ends_min=ends_min,power_kw=power_kw,reference=reference,noise_sigma_kw=noise_sigma_kw)
 return analyze_events([record],process_config=process_config)[0]

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

def _prepare_event(record):
 task=record['task'];t=task_contract(task)
 s=array(record['starts_min'],'starts_min');e=array(record['ends_min'],'ends_min');p=array(record['power_kw'],'power_kw')
 if s.shape!=e.shape or p.shape!=s.shape or np.any(e<=s):raise ValueError('matching positive-width metering intervals required')
 b,ref=bound_reference(record['reference'],t,s,e)
 relative_task={**t,'start_min':0.,'end_min':t['end_min']-t['start_min'],'notice_min':t['notice_min']-t['start_min']}
 request=dict(starts_min=s-t['start_min'],ends_min=e-t['start_min'],power_kw=p,reference_kw=b,
              task=relative_task,noise_sigma_kw=record['noise_sigma_kw'])
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

def analyze_events(records,*,process_config=None):
 """Validate each event, batch native CPOP requests, preserve order and failures."""
 if not isinstance(records,(list,tuple)):raise ValueError('records must be an ordered list of event records')
 results=[None]*len(records);contexts=[];indices=[]
 for index,record in enumerate(records):
  try:
   if not isinstance(record,Mapping):raise ValueError('event record must be a mapping')
   contexts.append(_prepare_event(record));indices.append(index)
  except (ValueError,TypeError,KeyError) as exc:
   result=_empty_event()
   result['status']='unavailable' if isinstance(exc,UnavailableReference) else 'invalid_input'
   result['reasons']=[dict(code='reference_unavailable' if isinstance(exc,UnavailableReference) else 'event_contract',detail=str(exc))];results[index]=result
 if contexts:
  from .process.batch import identify_process_batch
  try:
   config=_default_runtime_config() if process_config is None and any(len(c['s'])>=40 for c in contexts) else process_config
   processes=identify_process_batch([c['request'] for c in contexts],config=config)
  except (ValueError,OSError) as exc:
   processes=[dict(status='unavailable',method=None,reason='runtime_configuration: '+str(exc),eta_raw=None,
                   features=None,physical_timing=None,uncertainty_status='unavailable') for _ in contexts]
  if len(processes)!=len(contexts):raise RuntimeError('process batch violated event count contract')
  for index,context,process in zip(indices,contexts,processes):results[index]=_finish_event(context,process)
 return results

def estimate_event_effects(event_results,X,treatment,*,assumptions=None,known_pi=None,levels=None,effect_config=None,target_population='supplied_event_population'):
 """Consume completed same-definition event outcomes; never silently drop failures."""
 invalid=dict(schema_version='b1.pipeline-effects.v1',algorithm_version=VERSION,status='invalid_input',reasons=[],causal_curve=None)
 try:
  if not isinstance(event_results,(list,tuple)) or not event_results:raise ValueError('nonempty completed event results required')
  y=[];users=[];keys=[];seen=set();refs=set();predeclared=True
  for event in event_results:
   if not isinstance(event,Mapping) or event.get('schema_version')!=SCHEMA or event.get('algorithm_version')!=VERSION or event.get('status') not in ('ok','degraded') or event.get('outcome') is None:
    raise ValueError('every event must have a valid B1 outcome; no complete-case dropping is implicit')
   task=task_contract(event['task']);outcome=event['outcome'];key=(task['task_id'],task['user_id'],task['meter_id'])
   if key in seen:raise ValueError('duplicate event identity')
   seen.add(key)
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
  result=fit_effects(X,treatment,y,users,levels=DEFAULT_LEVELS if levels is None else levels,
       task=context,assumptions=assumptions,known_pi=known_pi,config=effect_config)
  result['algorithm_version']=VERSION
  result['pipeline']=dict(input_events=len(y),input_users=len(set(users)),failed_events_dropped=0,
       outcome_from_raw_event_integrals=True,process_fit_used_in_energy=False,
       reference_process_uncertainty_propagated=False)
  return result
 except (ValueError,TypeError,KeyError) as exc:
  invalid['reasons']=[dict(code='pipeline_contract',detail=str(exc))]
  return invalid
