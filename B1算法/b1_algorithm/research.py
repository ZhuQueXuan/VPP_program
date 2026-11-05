"""Research point one: completed process -> structure -> continuous effects.

Mean curves retain the established Kennedy estimator. Structure, effect
modification, direct derivatives and target crossings answer distinct questions.
"""
from dataclasses import replace
from pathlib import Path
import hashlib
import json
import numpy as np
from .effects.continuous import _config
from .effects.frozen import (FrozenContinuousModel, fit_continuous_model,
    fit_ev_factor_model, query_continuous_model, find_incentive_threshold)
from .effects.nonlinear import (fit_nonlinear_effects, query_nonlinear_effects,
    bias_corrected_curve_summary)
from .structure import discover_factor_structure
from .factors import EVFactorStudy, _inputs


def _frozen(value):
    return FrozenContinuousModel(**value)


def fit_response_research(X, treatment, outcome, users, *, covariate_names,
        task, incentive_unit, dose_domain, reference_dose, assumptions=None,
        continuous_assignment=True, known_density=None, config=None,
        groups=None, discover_structure=True, structure_max_users=120):
    """Resource-neutral factor analysis given a common declared scalar outcome.

    Resource-specific feature extraction supplies Y. This interface does not
    turn a fitted cohort curve into individual future delivery capacity.
    """
    x=np.asarray(X,float);d=np.asarray(treatment,float);y=np.asarray(outcome,float)
    users=list(users);names=list(covariate_names);cfg=_config(config)
    if x.ndim!=2 or len(names)!=x.shape[1] or len(set(names))!=len(names):
        raise ValueError('one unique covariate name per column required')
    options=dict(dose_domain=dose_domain,reference_dose=reference_dose,
        incentive_unit=incentive_unit,task=task,continuous_assignment=continuous_assignment,
        assumptions=assumptions,known_density=known_density,config=cfg)
    mean=fit_continuous_model(x,d,y,users,**options)
    return _assemble(x,d,y,users,names,mean,cfg,known_density,options,
                     groups,discover_structure,structure_max_users)


def _assemble(x,d,y,users,names,mean,cfg,known_density,mean_options,
              groups,discover_structure,structure_max_users):
    p=json.loads(mean.payload_json)
    derivative=fit_nonlinear_effects(x,d,y,users,dose_domain=p['dose_domain'],
        known_density=known_density,config=cfg)
    structure={}
    if discover_structure:
        values=np.column_stack([x,d,y]);nodes=names+['offered_incentive',p['task']['outcome_name']]
        for method in ['fci_kci','pc_kci']:
            structure[method]=discover_factor_structure(values,users,nodes,method=method,
                max_users=structure_max_users,seed=cfg.seed,
                time_tiers=[names,['offered_incentive'],[p['task']['outcome_name']]])
    subgroup_models={}
    for name,spec in (groups or {}).items():
        # Scientific groups are predeclared on baseline variables only.
        column=names.index(spec['covariate']);threshold=float(spec['threshold'])
        mask=x[:,column]<threshold if spec['side']=='below' else x[:,column]>=threshold
        entry=dict(definition=spec,events=int(mask.sum()),users=len(set(np.asarray(users)[mask])),
                   mask=mask.tolist(),status='unsupported')
        try:
            subset_options=dict(mean_options)
            subset_options['known_density']=None if known_density is None else np.asarray(known_density)[mask]
            model=fit_continuous_model(x[mask],d[mask],y[mask],np.asarray(users)[mask],**subset_options)
            entry.update(status='fitted',mean_model=dict(payload_json=model.payload_json,sha256=model.sha256))
        except ValueError as exc:entry['reason']=str(exc)
        subgroup_models[name]=entry
    return dict(schema='b1.research-point-one.v1',status=p['status'],
        method='process_features+nonlinear_structure+continuous_DR+direct_marginal_effects+target_crossings',
        mean_model=dict(payload_json=mean.payload_json,sha256=mean.sha256),derivative_model=derivative,
        structure=structure,groups=subgroup_models,covariate_names=names,
        events=len(y),users=len(set(users)),task=p['task'],incentive_unit=p['incentive_unit'],
        curve_population='fixed supplied population including zero responders',
        graph_controls_adjustment=False,individual_future_capacity=False,
        preferred_marginal_effect='retained_smoothed_derivative',
        inference_scope='conditional fitted-nuisance user sampling; full measurement and smoothing uncertainty not certified')


def fit_research_point_one(events,factor_records,study,*,dose_domain,reference_dose,
        assumptions=None,known_density=None,config=None,groups=None,
        discover_structure=True,structure_max_users=120):
    """Bind genuine first-block outputs and prior factors through the public contract."""
    if not isinstance(study,EVFactorStudy):raise ValueError('EVFactorStudy required')
    data=_inputs(events,factor_records,study);cfg=_config(config)
    mean=fit_ev_factor_model(events,factor_records,study,dose_domain=dose_domain,
        reference_dose=reference_dose,assumptions=assumptions,known_density=known_density,
        config=cfg,continuous_assignment=True)
    p=json.loads(mean.payload_json)
    names=data['design']['identification']['used_covariates']
    opts=dict(dose_domain=dose_domain,reference_dose=reference_dose,
        incentive_unit=study.incentive_unit,task=p['task'],continuous_assignment=True,
        assumptions=assumptions,known_density=known_density,config=cfg)
    model=_assemble(data['X'],data['D'],data['y'],data['users'],names,mean,cfg,
                    known_density,opts,groups,discover_structure,structure_max_users)
    model['study_design']=data['design'];model['outcome_source']=study.outcome_source
    model['process_feature_table']=process_feature_table(events)
    return model


def query_research_point_one(model,amounts,*,target_contrast=120.,include_bias_correction=True,refit_draws=0,refit_seed=0):
    """Direct queries using frozen fitted state; no interpolation or refitting."""
    if model.get('schema')!='b1.research-point-one.v1':raise ValueError('research point one model required')
    a=np.asarray(amounts,float);mean=_frozen(model['mean_model'])
    curve=query_continuous_model(mean,a)
    direct=query_nonlinear_effects(model['derivative_model'],a)
    threshold=(find_incentive_threshold(mean,target_contrast=target_contrast,
        search_domain=[float(a[0]),float(a[-1])],mesh_step=float(np.min(np.diff(a))))
        if len(a)>1 else dict(status='single_query_no_search_interval',point_crossings=[]))
    out=dict(schema='b1.research-point-one-query.v1',status=curve['status'],
        mean_curve=curve,direct_marginal_effect=direct,retained_smoothed_derivative=curve.get('sensitivity'),
        target_threshold=threshold,structure=model['structure'],group_effects={},refitted=False,
        target_contrast_seconds=target_contrast,causal_interpretation=model['status'])
    out['marginal_effect']=direct if model.get('preferred_marginal_effect')=='direct_derivative' else curve.get('sensitivity')
    out['marginal_effect_method']=model.get('preferred_marginal_effect','retained_smoothed_derivative')
    if include_bias_correction:
        out['bias_corrected_threshold']=bias_corrected_curve_summary(mean,a,target_contrast=target_contrast)
    for name,entry in model['groups'].items():
        if entry['status']!='fitted':
            out['group_effects'][name]={k:v for k,v in entry.items() if k!='mask'};continue
        subgroup=query_continuous_model(_frozen(entry['mean_model']),a)
        out['group_effects'][name]=dict(definition=entry['definition'],events=entry['events'],users=entry['users'],
            mean_curve=subgroup,direct_marginal_effect=query_nonlinear_effects(
                model['derivative_model'],a,event_mask=np.asarray(entry['mask'],bool)),
            interpretation='compensation effect within this fixed pretreatment subgroup, not effect of changing its baseline condition')
    if refit_draws:
        from .effects.refit import refit_curve_uncertainty
        out['refit_uncertainty']=refit_curve_uncertainty(model,a,draws=refit_draws,seed=refit_seed,target_contrast=target_contrast)
        out['uncertainty_refitting_performed']=True
    return out


def run_research_point_one(records,factor_records,study,*,process_method='effective_response_refined',
                           process_config=None,ev_config=None,**fit_options):
    """Raw interval measurements -> unchanged native extraction -> full factor study."""
    from .api import analyze_events
    events=analyze_events(records,process_method=process_method,process_config=process_config,ev_config=ev_config)
    model=fit_research_point_one(events,factor_records,study,**fit_options)
    return dict(events=events,model=model)


def process_feature_table(events):
    rows=[]
    for event in events:
        p=event.get('process') or {};f=(p.get('features') or {}).get('selected_curve') or {}
        row=dict(task_id=(event.get('task') or {}).get('task_id'),status=event.get('status'),
            features=dict(f),duration_source=(p.get('features') or {}).get('sources',{}).get('duration'))
        if p.get('reduction_interval_kw') is not None:
            curve=np.asarray(p['reduction_interval_kw'],float)
            delta=p['selection_evidence']['meter_delta_min']*60
            pre=p['analysis_profile']['observation_pre_min']*60
            starts=-pre+np.arange(len(curve))*delta
            inside=(starts>=-1e-7)&(starts<p['task_duration_min']*60-1e-7)
            segment=curve[inside];rates=np.diff(segment)/delta
            row['structural_power_features']=dict(max_reduction_kw=float(segment.max()),
                peak_fraction_of_request=float(segment.max()/p['request_kw']),
                max_increase_in_reduction_kw_per_second=float(max(0.,rates.max())) if len(rates) else 0.,
                max_decrease_in_reduction_kw_per_second=float(max(0.,-rates.min())) if len(rates) else 0.,
                source='original fitted interval power curve; interval-scale descriptors, not subinterval physical transition truth')
        rows.append(row)
    return rows


def save_research_point_one(model,path):
    payload=json.dumps(model,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
    with Path(path).open('x',encoding='utf-8') as f:
        json.dump(dict(payload=model,sha256=hashlib.sha256(payload.encode()).hexdigest()),f,ensure_ascii=False)


def load_research_point_one(path):
    envelope=json.loads(Path(path).read_text(encoding='utf-8'))
    payload=json.dumps(envelope['payload'],ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
    if hashlib.sha256(payload.encode()).hexdigest()!=envelope['sha256']:raise ValueError('research model checksum mismatch')
    return envelope['payload']
