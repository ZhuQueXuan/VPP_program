"""Optional relative-energy effects; no absolute reference or process fitting.

Z=-actual task energy/pre-fixed request energy. Its arm contrasts equal those
of net delivery when the natural reference is treatment-invariant. Absolute Z
levels must never be interpreted as absolute net delivery or available capacity.
"""
from collections.abc import Mapping
import numpy as np
from .contracts import VERSION, array, task_contract
from .resources.ev import ev_task_parameters


def _metered_outcomes(records):
    if not isinstance(records,(list,tuple)) or not records:
        raise ValueError('nonempty ordered complete event records required')
    outcomes=[];users=[];seen=set();seen_windows={};predeclared=True;definition=None
    for record in records:
        if not isinstance(record,Mapping):raise ValueError('each event must be a mapping')
        task=task_contract(record.get('task'))
        W,q=ev_task_parameters(task)
        if definition is None:definition=(W,q)
        elif not np.allclose([W,q],definition,rtol=0,atol=1e-9):
            raise ValueError('metered effects require one common task duration/request; analyze different task definitions separately')
        key=(task['task_id'],task['user_id'],task['meter_id'])
        if key in seen:raise ValueError('duplicate task/user/meter identity')
        seen.add(key)
        windows=seen_windows.setdefault(task['meter_id'],[])
        if any(abs(start-task['start_min'])<=1e-9 and abs(end-task['end_min'])<=1e-9 for start,end in windows):
            raise ValueError('duplicate physical meter window, including renamed tasks or users')
        windows.append((task['start_min'],task['end_min']))
        starts=array(record.get('starts_min'),'starts_min');ends=array(record.get('ends_min'),'ends_min')
        power=array(record.get('power_kw'),'power_kw')
        if starts.shape!=ends.shape or power.shape!=starts.shape:raise ValueError('matching complete meter arrays required')
        delta=float(ends[0]-starts[0])
        if not any(np.isclose(delta,d,rtol=0,atol=1e-9) for d in (1/6,1.,15.)) or not np.allclose(ends-starts,delta,rtol=0,atol=1e-9):
            raise ValueError('complete regular10second/1minute/15minute meter intervals required')
        if len(starts)>1 and not np.allclose(starts[1:],ends[:-1],rtol=0,atol=1e-9):
            raise ValueError('ordered contiguous nonoverlapping meter intervals required')
        use=(starts>=task['start_min']-1e-9)&(ends<=task['end_min']+1e-9)
        if use.sum()!=int(round(W/delta)) or not np.isclose(starts[use][0],task['start_min'],rtol=0,atol=1e-9) or not np.isclose(ends[use][-1],task['end_min'],rtol=0,atol=1e-9):
            raise ValueError('complete task with boundaries aligned to meter intervals required; no partial-bin allocation')
        value=-float(np.sum(power[use]*(ends[use]-starts[use])))/(q*W)
        if not np.isfinite(value):raise ValueError('nonfinite metered task energy')
        outcomes.append(value);users.append(task['user_id'])
        predeclared=predeclared and task['task_pre_treatment'] is True
    return np.asarray(outcomes),users,predeclared


def estimate_metered_effects(records,X,treatment,*,assumptions=None,known_pi=None,levels=None,
                            effect_config=None,target_population='supplied_event_population'):
    """Estimate relative actual-energy effects using the existing AIPW core.

    Records contain task, starts_min, ends_min and power_kw. No reference,
    response-selection or fitted process is required; every record must be valid.
    Fixed task/common-population causal assumptions remain caller declarations.
    """
    try:
        y,users,predeclared=_metered_outcomes(records)
        from .effects import fit_effects,DEFAULT_LEVELS
        t=task_contract(records[0]['task']);W,q=ev_task_parameters(t)
        task=dict(task_id='common_metered_EV_task',outcome_name='negative_normalized_actual_energy',
            outcome_unit='ratio',window_minutes=[0.,W],q_kw=q,target_population=target_population,
            task_pre_treatment=predeclared,reference_status='not_required_for_relative_metered_energy',
            reference_uncertainty='not_applicable')
        result=fit_effects(X,treatment,y,users,levels=DEFAULT_LEVELS if levels is None else levels,
            task=task,assumptions=assumptions,known_pi=known_pi,config=effect_config)
        result['algorithm_version']=VERSION
        result['metered_pipeline']=dict(input_events=len(y),input_users=len(set(users)),failed_events_dropped=0,
            reference_required=False,process_fit_used=False,outcome_name=task['outcome_name'],
            positive_contrast='less actual task energy than the reference incentive arm',
            absolute_levels_are_net_delivery=False,
            net_delivery_contrast_equivalence='requires treatment-invariant natural reference and pre-fixed common task window/request',
            reference_process_uncertainty_propagated=False)
        return result
    except (ValueError,TypeError,KeyError,OverflowError) as exc:
        return dict(schema_version='b1.metered-effects.v1',algorithm_version=VERSION,status='invalid_input',
            reasons=[dict(code='metered_event_contract',detail=str(exc))],causal_curve=None,
            metered_pipeline=dict(reference_required=False,failed_events_dropped=0))
