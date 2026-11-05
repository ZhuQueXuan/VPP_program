"""Retrospective process curves with explicit methods and assumption labels."""
from pathlib import Path
from numbers import Real
import json
import numpy as np
from dataclasses import asdict
from ..resources.ev import ev_config as validate_ev_config,ev_task_parameters
from ._cpop import fit_cases,validate_config
from ._template_fit import fit_template
from ._ride_fit import fit_original_ride
from ._ride_revised import fit_revised_ride
from . import _frozen_f0 as f0

def _number(value):return isinstance(value,Real) and not isinstance(value,(bool,np.bool_)) and np.isfinite(value)

def resolve_policy(n_bins,method=None,*,delta_min=None):
    if method is not None:
        if method not in ('ride_template','ride_revised','guarded','cpop','conservative','duration_fusion'):
            raise ValueError('process_method must be ride_template,ride_revised,guarded,cpop,conservative,duration_fusion or None')
        return method
    metadata=json.loads(Path(__file__).with_name('_policy.json').read_text(encoding='utf-8'))
    if metadata['default']!='resolution_profile':return metadata['default']
    if delta_min is None:
        # Compatibility for old fixed-window callers only; live routes supply delta.
        if n_bins not in (360,60,4):raise ValueError('actual meter interval is required outside the legacy fixed window')
        delta_min={360:1/6,60:1.,4:15.}[n_bins]
    for delta,name in ((1/6,'10s'),(1.,'1min'),(15.,'15min')):
        if _number(delta_min) and np.isclose(delta_min,delta,atol=1e-9,rtol=0):return metadata['by_meter'][name]
    raise ValueError('unsupported meter interval for process policy')

def needs_native(n_bins,policy):
    return policy in ('cpop','duration_fusion') or (n_bins>=40 and policy in ('guarded','conservative'))

def prepare(starts_min,ends_min,power_kw,reference_kw,task,noise_sigma_kw,ev_config=None):
    if not isinstance(task,dict):raise ValueError('task_dict_required')
    for key in ('task_id','user_id','meter_id'):
        if not isinstance(task.get(key),str) or not task[key].strip():raise ValueError('task_identity_required:'+key)
    for key in ('start_min','end_min','request_kw','notice_min'):
        if not _number(task.get(key)):raise ValueError('finite task field required:'+key)
    if not np.isclose(task['start_min'],0.,atol=1e-9,rtol=0):raise ValueError('process layer expects task-relative start0')
    W,q=ev_task_parameters(task,process=True);profile=validate_ev_config(ev_config)
    if not _number(noise_sigma_kw) or noise_sigma_kw<=0:raise ValueError('positive_declared_sigma_required')
    arrays=[]
    for values in (starts_min,ends_min,power_kw,reference_kw):
        original=np.asarray(values,dtype=object)
        if original.ndim!=1 or any(not _number(v) for v in original.flat):raise ValueError('finite_numeric_1d_arrays_required')
        arr=np.asarray(values,dtype=float)
        if not np.isfinite(arr).all():raise ValueError('missing_or_nonfinite_observation')
        arrays.append(arr)
    s,e,p,b=arrays
    if len(s)<3 or any(v.shape!=s.shape for v in arrays):raise ValueError('matching_complete_intervals_required')
    delta=float(e[0]-s[0])
    if not any(np.isclose(delta,d,atol=1e-9,rtol=0) for d in (1/6,1.,15.)):raise ValueError('unsupported_meter_resolution')
    count=(profile.observation_pre_min+W+profile.observation_post_min)/delta
    if not np.isclose(count,len(s),atol=1e-7,rtol=0):raise ValueError('complete aligned task and observation window required')
    expected=-profile.observation_pre_min+np.arange(len(s))*delta
    if s.shape!=expected.shape or not np.allclose(s,expected,atol=1e-8,rtol=0) or not np.allclose(e,s+delta,atol=1e-8,rtol=0):
        raise ValueError('incomplete_or_irregular_window')
    if np.any(b<0):raise ValueError('nonnegative_reference_required')
    if not np.any(np.isclose(s,0.,atol=1e-8,rtol=0)) or not np.any(np.isclose(e,W,atol=1e-8,rtol=0)):
        raise ValueError('task must align with complete meter intervals')
    return dict(starts=s,ends=e,y=b-p,power=p,reference=b,sigma=float(noise_sigma_kw),delta=delta,W=W,q=q,profile=profile,
                negative_meter_values=int(np.sum(p<0)),task=dict(task))

def cases_for(data,base=0,include_cv=True):
    n=len(data['y']);folds=(np.floor(data['starts']-data['starts'][0]+1e-8).astype(int)%5)
    cases=[dict(case_id=base,starts=data['starts'],ends=data['ends'],y=data['y'],sigma=data['sigma'],train=np.ones(n,bool))]
    if include_cv and n>=40:
        cases.extend(dict(case_id=base+1+k,starts=data['starts'],ends=data['ends'],y=data['y'],sigma=data['sigma'],train=folds!=k) for k in range(5))
    return cases

def _features(data,pred):
    s,e=data['starts'],data['ends'];delta=data['delta'];t=np.r_[s,e[-1]]*60
    profile=data['profile'];q=data['q'];W=data['W']
    dwell=max(1,int(np.ceil(profile.dwell_seconds/(60*delta)-1e-9)));b=data['reference']
    def extract(r):
        result=f0.extract(t,b,b-r,t0=0,t1=W*60,q=q,dwell_samples=dwell,
            onset_kw=profile.onset_fraction*q,target_fraction=profile.target_fraction,recovery_band_kw=profile.recovery_fraction*q)
        mask=(s>=-1e-9)&(s<W-1e-9)&(r>=profile.onset_fraction*q)
        result['cumulative_response_seconds']=float(np.sum(mask)*delta*60)
        longest=run=0
        for yes in mask:
            run=run+1 if yes else 0;longest=max(longest,run)
        result['longest_continuous_response_seconds']=float(longest*delta*60) if longest>=dwell else 0.
        return result
    selected=extract(pred);raw=extract(data['y'])
    return dict(selected_curve=selected,raw_observed=raw,
        accounting=dict(source='raw_observed_interval_integral',request_net_kwh=raw['request_net_kwh'],
                        post_rebound_kwh=raw['post_rebound_kwh'],remaining_debt_kwh=raw['remaining_debt_kwh'],
                        energy_recovery_status=raw['energy_recovery_status']),
        interpretation='observed_threshold_and_dwell; physical action and participation not inferred')

def _result(data,pred,status,method,reason,evidence,backend=None):
    req=(data['starts']>=-1e-9)&(data['starts']<data['W']-1e-9)
    return dict(status=status,method=method,reason=reason,task_id=data['task']['task_id'],
        selection_evidence=dict(evidence,meter_delta_min=data['delta'],negative_meter_values=data['negative_meter_values'],
            request_to_declared_meter_sigma_ratio=data['q']/data['sigma'],
            request_less_than_three_meter_sigma=data['q']<3*data['sigma'],detection_error_rate_calibrated=False,
            request_exceeds_declared_max=False if data['profile'].max_charge_kw is None else data['q']>data['profile'].max_charge_kw),
        analysis_profile=asdict(data['profile']),task_duration_min=data['W'],request_kw=data['q'],features=_features(data,pred),
        eta_raw=float(np.sum(data['y'][req]*(data['ends'][req]-data['starts'][req]))/(data['q']*data['W'])),
        reduction_interval_kw=[float(v) for v in pred],physical_timing=None,
        physical_timing_status='not_identified_by_this_retrospective_observation_API',
        uncertainty_status='process_confidence_interval_not_validated',backend=backend)

def complete(data,native,base=0,policy='conservative',backend=None):
    n=len(data['y'])
    if policy=='duration_fusion':
        from ._duration_fusion import fit_duration_fusion
        try:
            original=native.get(base,{})
            if original.get('status')!='ok':raise ValueError('original_CPOP_unavailable')
            fitted=fit_duration_fusion(data,original['prediction'])
            result=_result(data,original['prediction'],'ok','CPOP_duration_fusion','validated_duration_refinement',
                dict(n_bins=n,policy=policy,**{k:v for k,v in fitted.items() if k!='prediction'}),backend)
            refined=_features(data,fitted['prediction'])['selected_curve']
            for key in ('cumulative_response_seconds','longest_continuous_response_seconds'):
                result['features']['selected_curve'][key]=refined[key]
            result['features']['sources']=dict(duration='frozen_duration_state_model_with_CPOP_safeguards',
                other_process_features='original_CPOP_structural_curve',accounting='raw_observed_interval_integral')
            result['duration_state_curve_kw']=[float(v) for v in fitted['prediction']]
            result['duration_state_curve_role']='threshold-state representation for duration only; not a physical power estimate'
            return result
        except (ValueError,TypeError,KeyError,OSError) as ex:
            return dict(status='unavailable',method='CPOP_duration_fusion',reason=str(ex),selection_evidence=dict(policy=policy),
                features=None,eta_raw=None,physical_timing=None,uncertainty_status='unavailable',backend=backend)
    if policy=='ride_revised':
        fitted=fit_revised_ride(data)
        evidence=dict(n_bins=n,policy=policy,curve_role='revised_template_interval_average_prediction',
            physical_stage_parameters_identified=False,coarse_assumption_sensitive=False,
            global_optimum_certified=False)
        if fitted['status']=='ok':
            evidence.update({k:v for k,v in fitted.items() if k not in ('status','prediction')})
            return _result(data,fitted['prediction'],'ok','RIDE_revised_template_average','checked_revised_RIDE_candidate',
                evidence,dict(status='ok',engine='revised_RIDE_python; R_not_required'))
        evidence['failure_reason']=fitted['reason']
        if 'solver_records' in fitted:evidence['solver_records']=fitted['solver_records']
        return _result(data,data['y'],'degraded','raw_F0','revised_ride_unavailable_explicit_raw_fallback',
            evidence,dict(status='unavailable',engine='revised_RIDE_python',reason=fitted['reason']))
    if policy=='ride_template':
        fitted=fit_original_ride(data)
        evidence=dict(n_bins=n,policy=policy,meter_delta_min=data['delta'],
            curve_role='template_assumed_interval_average_prediction',physical_stage_parameters_identified=False,
            coarse_assumption_sensitive=n<40,original_optimizer_convergence_certified=False)
        if fitted['status']=='ok':
            evidence.update(structure=fitted['structure'],detected=fitted['detected'],
                n_starts_minimum=fitted['n_starts_minimum'],selection=fitted['selection'])
            return _result(data,fitted['prediction'],'ok','RIDE_template_average','original_RIDE_template_selected',
                evidence,dict(status='ok',engine='original_RIDE_python; R_not_required'))
        evidence['failure_reason']=fitted['reason']
        return _result(data,data['y'],'degraded','raw_F0','ride_unavailable_explicit_raw_fallback',
            evidence,dict(status='unavailable',engine='original_RIDE_python',reason=fitted['reason']))
    if n<40 and policy!='cpop':return _result(data,data['y'],'ok','raw_coarse','too_few_meter_bins_for_continuous_process_identification',
                             dict(n_bins=n,information_gate='coarse'),backend)
    full=native.get(base,{})
    if full.get('status')!='ok':return _result(data,data['y'],'degraded','raw_F0','cpop_unavailable_explicit_raw_fallback',
                                                  dict(n_bins=n,backend_reason=(backend or {}).get('reason','native_case_failed')),backend)
    chosen=full['prediction'];method='CPOP';reason='conservative_native_cpop_default';evidence=dict(n_bins=n,policy=policy)
    if policy=='guarded':
        folds=np.floor(data['starts']-data['starts'][0]+1e-8).astype(int)%5
        c_pred=np.full(n,np.nan);t_pred=np.full(n,np.nan)
        gate_ok=True
        for k in range(5):
            valid=folds==k;fit=native.get(base+1+k,{})
            template=fit_template(data['starts'],data['ends'],data['y'],data['sigma'],q=data['q'],W=data['W'],profile=data['profile'],train=~valid)
            if fit.get('status')!='ok' or template.get('status')!='ok':gate_ok=False;break
            c_pred[valid]=fit['prediction'][valid];t_pred[valid]=template['prediction'][valid]
        evidence['gate_status']='validation_unavailable'
        if gate_ok:
            c_loss=(c_pred-data['y'])**2;t_loss=(t_pred-data['y'])**2
            block_ids=np.floor(data['starts']-data['starts'][0]+1e-8).astype(int)
            gains=np.array([np.mean((c_loss-t_loss)[block_ids==b]) for b in np.unique(block_ids)])
            gain=float(gains.mean());se=float(gains.std(ddof=1)/np.sqrt(len(gains)))
            relative=float(1-t_loss.mean()/max(c_loss.mean(),1e-15))
            passed=relative>=.1 and gain>se
            evidence.update(gate_status='passed' if passed else 'not_passed',relative_validation_mse_reduction=relative,
                            mean_block_gain=gain,block_se=se,decision_rule='10percent_and_one_block_SE;not_a_confidence_claim')
            if passed:
                template=fit_template(data['starts'],data['ends'],data['y'],data['sigma'],q=data['q'],W=data['W'],profile=data['profile'])
                if template.get('status')=='ok':
                    chosen=template['prediction'];method='task_template_average';reason='observed_bin_validation_gate_passed'
                else:reason='template_full_fit_failed_returned_to_cpop'
            else:reason='template_validation_gate_not_passed_returned_to_cpop'
    return _result(data,chosen,'ok',method,reason,evidence,backend)

def identify_process(starts_min,ends_min,power_kw,reference_kw,task,noise_sigma_kw,config=None,*,method=None,ev_config=None):
    try:
        data=prepare(starts_min,ends_min,power_kw,reference_kw,task,noise_sigma_kw,ev_config)
        config=validate_config(config)
        policy=resolve_policy(len(data['y']),method,delta_min=data['delta'])
        if policy=='duration_fusion':
            from ._duration_fusion import validate_domain
            validate_domain(data)
    except (ValueError,TypeError,OverflowError) as ex:
        return dict(status='unavailable',method=None,reason=str(ex),selection_evidence={},features=None,eta_raw=None,
                    physical_timing=None,uncertainty_status='unavailable')
    if not needs_native(len(data['y']),policy):return complete(data,{},policy=policy)
    native,backend=fit_cases(cases_for(data,include_cv=policy=='guarded'),config)
    return complete(data,native,policy=policy,backend=backend)
