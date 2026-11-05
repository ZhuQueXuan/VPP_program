"""EV-only settings and retrospective declared-service energy accounting.

The existing EV capability model supplies input validation, never an observed
trajectory. This module issues no control or capacity commitment.
"""
from collections.abc import Mapping
from dataclasses import dataclass,asdict,fields
from functools import lru_cache
from pathlib import Path
import importlib.util,sys
import numpy as np
from ..contracts import number,array,task_contract

@dataclass(frozen=True)
class EVAnalysisConfig:
    max_charge_kw: float | None = None
    observation_pre_min: float = 15.
    observation_post_min: float = 15.
    onset_fraction: float = .1
    target_fraction: float = .9
    recovery_fraction: float = .1
    dwell_seconds: float = 30.
    template_level_max_ratio: float = 1.5
    template_rebound_max_ratio: float = 1.
    template_ramp_max_min: float = 30.
    template_release_max_min: float = 30.
    template_rebound_max_min: float = 180.
    revised_rebound_bound_policy: str = 'configured_ratio'

def ev_config(value=None):
    if value is None:value=EVAnalysisConfig()
    if isinstance(value,Mapping):
        extra=set(value)-{f.name for f in fields(EVAnalysisConfig)}
        if extra:raise ValueError('unknown EV configuration fields: '+str(sorted(extra)))
        value=EVAnalysisConfig(**value)
    if not isinstance(value,EVAnalysisConfig):raise ValueError('EVAnalysisConfig or explicit settings mapping required')
    a=asdict(value)
    for name in a:
        if name=='revised_rebound_bound_policy':
            if not isinstance(a[name],str) or a[name] not in ('configured_ratio','declared_headroom'):raise ValueError('revised rebound bound policy must be configured_ratio or declared_headroom')
            continue
        if name=='max_charge_kw' and a[name] is None:continue
        a[name]=number(a[name],'ev_config.'+name)
    if a['max_charge_kw'] is not None and not .1<=a['max_charge_kw']<=22:raise ValueError('declared AC EV maximum supports0.1..22kW')
    if a['observation_pre_min'] not in (15.,30.,60.) or a['observation_post_min'] not in (15.,30.):raise ValueError('EV observation pre15/30/60 and post15/30 minutes supported')
    if not 0<a['onset_fraction']<=1 or not 0<a['recovery_fraction']<=1 or not 0<a['target_fraction']<=1.5:raise ValueError('positive bounded EV feature fractions required')
    if not 0<a['dwell_seconds']<=300:raise ValueError('EV dwell seconds must be in(0,300]')
    if a['target_fraction']<a['onset_fraction']:raise ValueError('target fraction cannot be below onset fraction')
    if not .05<=a['template_level_max_ratio']<=20 or not .02<=a['template_rebound_max_ratio']<=20:raise ValueError('positive supported template amplitude bounds required')
    for name in ('template_ramp_max_min','template_release_max_min','template_rebound_max_min'):
        if not 0<a[name]<=180:raise ValueError('template time bounds must be in(0,180]minutes')
    return EVAnalysisConfig(**a)

def ev_task_parameters(task,*,process=False):
    if task.get('resource_type','EV')!='EV':raise ValueError('EV task required; other resource adapters are deferred')
    duration=number(task['end_min'],'end_min')-number(task['start_min'],'start_min')
    q=number(task['request_kw'],'request_kw')
    if not np.isfinite(duration) or duration<=0:raise ValueError('positive finite EV task duration required')
    if not .1<=q<=22.:raise ValueError('EV request amplitude supports0.1..22kW')
    if process:
        lead=number(task['start_min'],'start_min')-number(task['notice_min'],'notice_min')
        if not any(np.isclose(lead,t,rtol=0,atol=1e-9) for t in (15.,30.,60.)):raise ValueError('EV process notice lead supports15/30/60minutes')
    return float(duration),q

@lru_cache(maxsize=1)
def _existing_ev_validator():
    root=Path(__file__).resolve().parents[3]
    path=root/'资源能力模型/03_电动汽车充电设施/code/capability_model.py'
    spec=importlib.util.spec_from_file_location('_b1_existing_ev_constraints',path)
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
    return module.prepare

def assess_ev_recovery(task,starts_min,ends_min,power_kw,requirement=None,*,config=None):
    """Check declared remaining grid-side energy at its declared deadline.

    Requirement binds task/user/meter and includes state_as_of_min,
    available_at_min, remaining_ac_kwh and deadline_min. All are caller-declared
    conditions; neither final delivered energy nor actual departure is imputed.
    """
    base=dict(status='unavailable',reason=None,delivered_ac_kwh=None,remaining_ac_kwh=None,
        shortfall_ac_kwh=None,observed_until_min=None,physical_service_certified=False,
        interpretation='declared_grid_side_requirement_checked_against_metered_energy; not SOC or authorization')
    if requirement is None:return dict(base,reason='declared_energy_and_deadline_not_supplied')
    try:
        t=task_contract(task);ev_task_parameters(t);cfg=ev_config(config)
        if not isinstance(requirement,Mapping):raise ValueError('EV requirement mapping required')
        for name in ('task_id','user_id','meter_id'):
            if requirement.get(name)!=t[name]:raise ValueError('EV requirement '+name+' must match task')
        if requirement.get('power_boundary')!='single_ev_ac_meter':
            return dict(base,reason='single_EV_AC_meter_boundary_declaration_required')
        asof=number(requirement.get('state_as_of_min'),'state_as_of_min')
        available=number(requirement.get('available_at_min'),'available_at_min')
        remaining=number(requirement.get('remaining_ac_kwh'),'remaining_ac_kwh')
        deadline=number(requirement.get('deadline_min'),'deadline_min')
        if remaining<0 or asof>t['notice_min']+1e-9 or available>t['notice_min']+1e-9 or deadline<=asof:
            raise ValueError('nonnegative energy, pre-notice snapshot/availability and later declared deadline required')
        if available<asof-1e-9:raise ValueError('snapshot cannot be available before its state time')
        base.update(remaining_ac_kwh=remaining,state_as_of_min=asof,deadline_min=deadline,
            source='caller_declared_before_notice',task_exceeds_declared_connection=t['end_min']>deadline+1e-9)
        if cfg.max_charge_kw is not None:
            case=dict(evidence_mode='declared_scenario',station_limit_kw=cfg.max_charge_kw,
                vehicles=[dict(id=t['user_id'],arrival_min=0.,departure_min=deadline-asof,remaining_ac_kwh=remaining,max_kw=cfg.max_charge_kw)])
            prepared,missing=_existing_ev_validator()(case)
            if prepared is None:raise ValueError('existing EV input validation missing: '+str(missing))
            base['resource_rule_source']='existing_EV_CAP_v1.prepare; no schedule optimization used'
            base['requirement_exceeds_declared_max_energy']=remaining>cfg.max_charge_kw*(deadline-asof)/60.+1e-7
        else:base['resource_rule_source']='energy/deadline declarations only; no declared charging upper bound'
        s=array(starts_min,'starts_min');e=array(ends_min,'ends_min');p=array(power_kw,'power_kw')
        if s.shape!=e.shape or p.shape!=s.shape or np.any(e<=s) or (len(s)>1 and not np.allclose(s[1:],e[:-1],rtol=0,atol=1e-8)):
            raise ValueError('complete ordered nonoverlapping meter intervals required')
        if not np.any(np.isclose(s,asof,rtol=0,atol=1e-8)):
            return dict(base,reason='snapshot_start_not_covered_or_not_meter_aligned')
        until=min(deadline,float(e[-1]));base['observed_until_min']=until
        if until<=asof:return dict(base,reason='no_metered_requirement_window')
        if not np.any(np.isclose(e,until,rtol=0,atol=1e-8)):
            return dict(base,reason='declared_deadline_not_meter_aligned')
        use=(s>=asof-1e-8)&(e<=until+1e-8)
        delivered=float(np.sum(p[use]*(e[use]-s[use]))/60.)
        if not np.isfinite(delivered):raise ValueError('nonfinite integrated charging energy')
        base.update(delivered_ac_kwh=delivered,shortfall_ac_kwh=max(0.,remaining-delivered),
            negative_meter_bins=int(np.sum(p[use]<0)),
            above_declared_max_bins=None if cfg.max_charge_kw is None else int(np.sum(p[use]>cfg.max_charge_kw)))
        if until<deadline-1e-8:return dict(base,status='right_censored',reason='observation_ends_before_declared_deadline')
        return dict(base,status='met' if delivered>=remaining-1e-7 else 'unmet',reason='complete_declared_deadline_energy_accounting')
    except (ValueError,TypeError,KeyError,OverflowError,OSError,ImportError) as exc:
        return dict(base,status='invalid_input',reason=str(exc))
