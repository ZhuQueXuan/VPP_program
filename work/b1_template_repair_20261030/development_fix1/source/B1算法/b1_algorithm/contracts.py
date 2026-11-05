"""Strict, versioned event contracts for the integrated B1 algorithm."""
from dataclasses import asdict, is_dataclass
import json
import math
import numbers
from collections.abc import Mapping
import numpy as np

VERSION='1.0.0'
SCHEMA='b1.event.v1'

class UnavailableReference(ValueError):
 pass

def number(value,name):
 if isinstance(value,(bool,np.bool_)) or not isinstance(value,numbers.Real):
  raise ValueError(name+' must be a finite real number, not bool/string')
 try:value=float(value)
 except (OverflowError,TypeError,ValueError):raise ValueError(name+' exceeds the supported finite numeric range')
 if not math.isfinite(value):raise ValueError(name+' must be finite')
 return value

def identifier(value,name):
 if not isinstance(value,str) or not value.strip():raise ValueError(name+' must be a nonempty string identifier; numeric IDs require an explicit upstream schema conversion')
 return value

def array(value,name):
 raw=np.asarray(value,dtype=object)
 if raw.ndim!=1 or len(raw)==0:
  raise ValueError(name+' must be a nonempty numeric vector, without booleans/strings')
 result=np.array([number(item,name) for item in raw],dtype=float)
 return result

def task_contract(task):
 if not isinstance(task,Mapping):raise ValueError('task must be a mapping')
 if task.get('resource_type','EV')!='EV':raise ValueError('this event API currently supports EV only; other resource adapters are deferred')
 result={name:identifier(task.get(name),name) for name in ['task_id','user_id','meter_id']}
 for name in ['start_min','end_min','request_kw','notice_min']:
  result[name]=number(task.get(name),'task.'+name)
 if result['end_min']<=result['start_min'] or result['request_kw']<=0 or result['notice_min']>result['start_min']:
  raise ValueError('require positive predeclared task and notice no later than start')
 result['task_pre_treatment']=task.get('task_pre_treatment')
 if result['task_pre_treatment'] is not None and not isinstance(result['task_pre_treatment'],(bool,np.bool_)):
  raise ValueError('task_pre_treatment must be a boolean/null declaration')
 if result['task_pre_treatment'] is not None:result['task_pre_treatment']=bool(result['task_pre_treatment'])
 return result

def bound_reference(reference,task,starts,ends):
 data=asdict(reference) if is_dataclass(reference) else reference
 if not isinstance(data,Mapping):raise ValueError('a bound reference prediction or provided reference record is required')
 if data.get('reference_status')=='unavailable':
  raise UnavailableReference('reference unavailable: '+str(data.get('reasons',data.get('reason','not available'))))
 if data.get('reference_status') not in ('available','provided'):
  raise ValueError('reference unavailable: '+str(data.get('reasons',data.get('reason','not available'))))
 for name in ['task_id','user_id','meter_id']:
  if identifier(data.get(name),'reference.'+name)!=task[name]:raise ValueError('reference '+name+' does not match event task')
 for source,target in [('task_start_min','start_min'),('task_end_min','end_min'),('request_kw','request_kw'),('notice_min','notice_min')]:
  if not np.isclose(number(data.get(source),'reference.'+source),task[target],atol=1e-10,rtol=0):
   raise ValueError('reference '+source+' does not match event task definition')
 rs=array(data.get('starts_min'),'reference.starts_min');re=array(data.get('ends_min'),'reference.ends_min')
 b=array(data.get('reference_kw'),'reference.reference_kw')
 if rs.shape!=starts.shape or re.shape!=ends.shape or b.shape!=starts.shape or not np.allclose(rs,starts,atol=1e-8,rtol=0) or not np.allclose(re,ends,atol=1e-8,rtol=0):
  raise ValueError('reference meter intervals must exactly match this event')
 asof=number(data.get('available_at_min'),'reference.available_at_min')
 if asof>task['notice_min']+1e-9:raise ValueError('reference inputs/model were not available at event notice')
 method=identifier(data.get('method','provided'),'reference.method')
 model_id=data.get('model_id')
 if model_id is not None:model_id=identifier(model_id,'reference.model_id')
 band=data.get('window_band_eta')
 if band is not None and not isinstance(band,Mapping):raise ValueError('reference window metadata must be a JSON mapping or null')
 band=json.loads(json.dumps(band,allow_nan=False))
 return b,dict(reference_status=data['reference_status'],method=method,
               model_id=model_id,available_at_min=asof,counterfactual_identified=False,
               window_band_eta=band,uncertainty_propagated=False)

def provided_reference(task,starts_min,ends_min,reference_kw,*,available_at_min):
 t=task_contract(task);s=array(starts_min,'starts_min');e=array(ends_min,'ends_min');b=array(reference_kw,'reference_kw')
 if e.shape!=s.shape or b.shape!=s.shape or np.any(e<=s):raise ValueError('matching positive-width metering intervals required')
 record=dict(reference_status='provided',task_id=t['task_id'],user_id=t['user_id'],meter_id=t['meter_id'],
       starts_min=s.tolist(),ends_min=e.tolist(),reference_kw=b.tolist(),available_at_min=number(available_at_min,'available_at_min'),
       task_start_min=t['start_min'],task_end_min=t['end_min'],request_kw=t['request_kw'],notice_min=t['notice_min'],
       method='caller_declared_reference',model_id=None,counterfactual_identified=False)
 bound_reference(record,t,s,e)
 return record
