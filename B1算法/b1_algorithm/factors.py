"""EV process-outcome/structural-assumption/continuous-incentive mainline.

Identification is conditional on a declared DAG, not proof of a real DAG.
Treatment-parent screening is training-only auxiliary evidence and never
silently removes covariates required by the declared backdoor analysis.
"""
from dataclasses import dataclass,asdict
from collections.abc import Mapping
from itertools import combinations
import hashlib,json
import numpy as np
from scipy.special import logit
from .contracts import VERSION,SCHEMA,task_contract,number,identifier
from .effects.continuous import fit_continuous_effects


@dataclass(frozen=True)
class EVFactorStudy:
    study_id: str
    incentive_unit: str
    covariates: tuple = ('deadline_slack','demand_urgency')
    assignment: str = 'observational'
    outcome_name: str = 'cumulative_response_seconds'
    outcome_source: str = 'selected_curve'
    target_population: str = 'all_supplied_invited_EV_events'
    graph_edges: tuple | None = None


def _subsets(values):
    for k in range(len(values)+1):yield from combinations(values,k)


def _separated(edges,source,target,condition):
    # Ancestor moralization: reuse the verified old EV backdoor approach,
    # generalized to named continuous pre-treatment factors.
    ancestors={source,target,*condition}
    while True:
        expanded=ancestors|{a for a,b in edges if b in ancestors}
        if expanded==ancestors:break
        ancestors=expanded
    graph={a:set() for a in ancestors}
    for a,b in edges:
        if a in ancestors and b in ancestors:graph[a].add(b);graph[b].add(a)
    for child in ancestors:
        for a,b in combinations([a for a,b in edges if b==child and a in ancestors],2):
            graph[a].add(b);graph[b].add(a)
    visited=set(condition);stack=[source]
    while stack:
        node=stack.pop()
        if node in visited:continue
        if node==target:return False
        visited.add(node);stack.extend(graph[node]-visited)
    return True


def describe_ev_study(study):
    if not isinstance(study,EVFactorStudy):raise ValueError('EVFactorStudy required')
    for name in ('study_id','incentive_unit','target_population'):identifier(getattr(study,name),name)
    cov=study.covariates
    if not isinstance(cov,(tuple,list)) or not 1<=len(cov)<=8 or len(set(cov))!=len(cov):raise ValueError('1..8 unique pre-treatment covariates required')
    reserved={'incentive','offered_incentive','participation','response','eta_raw','cumulative_response_seconds','power_kw','task_id','user_id','meter_id'}
    for name in cov:
        identifier(name,'covariate')
        if name in reserved:raise ValueError('post-treatment/identity/treatment fields cannot be covariates: '+name)
    if study.assignment not in ('observational','randomized'):raise ValueError('assignment must be observational or randomized')
    if study.outcome_name not in ('cumulative_response_seconds','longest_continuous_response_seconds','eta_raw'):raise ValueError('unsupported EV outcome')
    if study.outcome_source not in ('selected_curve','raw_observed','duration_estimates'):raise ValueError('explicit curve, raw-observed or direct-duration measurement required')
    if study.outcome_name=='eta_raw' and study.outcome_source!='raw_observed':raise ValueError('eta must remain the raw interval integral')
    edges=study.graph_edges
    if edges is None:
        edges=[('incentive','participation'),('participation','response'),('incentive','response')]
        for name in cov:
            edges.extend([(name,'participation'),(name,'response')])
            if study.assignment=='observational':edges.append((name,'incentive'))
    roles={name:0 for name in cov}|{'incentive':1,'participation':2,'response':3}
    checked=[]
    for edge in edges:
        if not isinstance(edge,(tuple,list)) or len(edge)!=2:raise ValueError('graph edges must be named pairs')
        a,b=edge
        if a not in roles or b not in roles or a==b or roles[a]>roles[b]:raise ValueError('graph violates declared variables or time order')
        if (a,b) in checked:raise ValueError('duplicate graph edge')
        checked.append((a,b))
    pending=set(roles);removed=set()
    while pending:
        roots={v for v in pending if not any(b==v and a not in removed for a,b in checked)}
        if not roots:raise ValueError('acyclic declared graph required')
        pending-=roots;removed|=roots
    if study.assignment=='randomized' and any(b=='incentive' for a,b in checked):raise ValueError('randomized assignment cannot have declared covariate parents')
    backdoor=[(a,b) for a,b in checked if a!='incentive']
    valid=[list(z) for z in _subsets(cov) if _separated(backdoor,'incentive','response',z)]
    if not valid:raise ValueError('no supported pre-treatment backdoor set in declared graph')
    # Keep all predeclared adjustment factors when valid; an auxiliary screen
    # cannot erase a known confounder. A collider-containing set is not forced.
    selected=list(cov) if list(cov) in valid else valid[0]
    minimal=[z for z in valid if not any(set(other)<set(z) for other in valid)]
    return dict(asdict(study),schema_version='b1.ev-study.v1',graph_edges=[list(v) for v in checked],
        variable_roles={name:'pre_treatment' for name in cov}|{'incentive':'treatment','participation':'post_treatment_mediator','response':'outcome'},
        identification=dict(method='backdoor_on_declared_DAG',valid_sets=valid,minimal_sets=minimal,used_covariates=selected,
                            graph_is_assumed=True,learned_screen_can_change_adjustment=False,hidden_confounding_ruled_out_by_data=False))


def _inputs(events,factors,study):
    design=describe_ev_study(study)
    if not isinstance(events,(list,tuple)) or not events or not isinstance(factors,(list,tuple)) or len(events)!=len(factors):raise ValueError('matching nonempty event and factor record lists required')
    seen=set();windows={};y=[];X=[];D=[];users=[];measurement=None;tasks=[];methods={};policies=set();fallbacks=0;refs=set();duration_sources=set()
    for event,record in zip(events,factors):
        if not isinstance(event,Mapping) or event.get('schema_version')!=SCHEMA or event.get('algorithm_version')!=VERSION or event.get('status') not in ('ok','degraded'):
            raise ValueError('every event must be a completed supported B1 measurement; no failed event is silently dropped')
        if not isinstance(record,Mapping):raise ValueError('factor record mapping required')
        task=task_contract(event['task']);process=event.get('process');tasks.append(task)
        key=tuple(task[name] for name in ('task_id','user_id','meter_id'))
        if key in seen:raise ValueError('duplicate event identity')
        seen.add(key)
        for name in ('task_id','user_id','meter_id'):
            if record.get(name)!=task[name]:raise ValueError('factor '+name+' does not match event')
        history=windows.setdefault(task['meter_id'],[])
        if any(np.allclose(v,[task['start_min'],task['end_min']],rtol=0,atol=1e-9) for v in history):raise ValueError('duplicate physical meter window, including renamed events')
        history.append([task['start_min'],task['end_min']])
        formed=number(record.get('treatment_set_min'),'treatment_set_min')
        if formed>task['notice_min']+1e-9:raise ValueError('offered incentive must be formed by notice')
        available=record.get('available_at_min');state=record.get('state_as_of_min')
        if not isinstance(available,Mapping) or not isinstance(state,Mapping):raise ValueError('per-factor availability and state timestamps required')
        offer_available=number(available.get('offered_incentive'),'incentive availability')
        if not formed-1e-9<=offer_available<=task['notice_min']+1e-9:raise ValueError('incentive availability must be between formation and notice')
        for name in study.covariates:
            asof=number(state.get(name),name+' state time');known=number(available.get(name),name+' availability')
            if asof>formed+1e-9 or known>formed+1e-9 or known<asof-1e-9:raise ValueError('covariates must be measured and available before treatment formation: '+name)
        D.append(number(record.get('offered_incentive'),'offered_incentive'))
        X.append([number(record.get(name),name) for name in study.covariates]);users.append(task['user_id'])
        if not isinstance(process,Mapping) or process.get('status')!=event['status']:raise ValueError('completed process and event status must agree')
        if process.get('task_id')!=task['task_id'] or not np.isclose(number(process.get('task_duration_min'),'process duration'),task['end_min']-task['start_min'],rtol=0,atol=1e-8) or not np.isclose(number(process.get('request_kw'),'process request'),task['request_kw'],rtol=0,atol=1e-10):
            raise ValueError('completed process identity and task duration/request must match event')
        profile=process.get('analysis_profile');delta=number(process.get('selection_evidence',{}).get('meter_delta_min'),'meter delta')
        if not isinstance(profile,Mapping):raise ValueError('completed measurement profile required')
        signature=[task['end_min']-task['start_min'],task['request_kw'],delta,
            number(profile.get('onset_fraction'),'onset fraction'),number(profile.get('dwell_seconds'),'dwell seconds'),
            number(profile.get('observation_pre_min'),'pre window'),number(profile.get('observation_post_min'),'post window')]
        if measurement is None:measurement=signature
        elif not np.allclose(signature,measurement,atol=1e-8,rtol=0):raise ValueError('same task, meter interval and measurement criterion required; no silent pooling')
        if study.outcome_name=='eta_raw':
            outcome=event.get('outcome',{})
            if outcome.get('name')!='eta_raw' or outcome.get('process_fit_used_in_energy') is not False:raise ValueError('raw eta outcome required')
            if not np.allclose(outcome.get('window_minutes'),[0.,signature[0]],rtol=0,atol=1e-8) or not np.isclose(number(outcome.get('q_kw'),'outcome request'),signature[1],rtol=0,atol=1e-10):raise ValueError('eta outcome and event task disagree')
            value=number(outcome.get('value'),'eta_raw')
            if not np.isclose(value,number(process.get('eta_raw'),'process eta'),rtol=0,atol=1e-12):raise ValueError('eta must match completed process integral')
        else:
            if study.outcome_source=='duration_estimates':
                direct=process.get('duration_estimates',{})
                cumulative=number(direct.get('cumulative_response_seconds'),'direct cumulative duration')
                longest=number(direct.get('longest_continuous_response_seconds'),'direct longest duration')
                if not 0<=longest<=cumulative<=signature[0]*60+1e-7:raise ValueError('direct durations must satisfy0<=longest<=cumulative<=task')
                value=number(direct.get(study.outcome_name),'completed direct duration')
                selected_value=number(process.get('features',{}).get('selected_curve',{}).get(study.outcome_name),'published duration feature')
                if not np.isclose(value,selected_value,rtol=0,atol=1e-7):raise ValueError('direct duration and published feature disagree')
                source=process.get('features',{}).get('sources',{}).get('duration')
                if not isinstance(source,str) or not source:raise ValueError('direct duration requires its recorded measurement source')
                duration_sources.add(source)
                policy=process.get('selection_evidence',{}).get('policy')
                if policy is not None:policies.add(policy)
            else:
                value=number(process.get('features',{}).get(study.outcome_source,{}).get(study.outcome_name),'completed process duration')
            if not 0<=value<=signature[0]*60+1e-7:raise ValueError('duration outside task window')
            if not np.isclose(value/(delta*60),round(value/(delta*60)),rtol=0,atol=1e-7):raise ValueError('duration must count complete meter intervals')
            if study.outcome_source=='selected_curve':
                curve=np.asarray(process.get('reduction_interval_kw'),float)
                if curve.ndim!=1 or not np.isfinite(curve).all() or not np.isclose(len(curve)*delta,signature[0]+signature[5]+signature[6],rtol=0,atol=1e-7):raise ValueError('selected curve and observation profile disagree')
                starts=-signature[5]+np.arange(len(curve))*delta
                mask=(starts>=-1e-8)&(starts<signature[0]-1e-8)&(curve>=signature[3]*signature[1])
                if study.outcome_name=='cumulative_response_seconds':expected=float(mask.sum()*delta*60)
                else:
                    longest=run=0
                    for yes in mask:run=run+1 if yes else 0;longest=max(longest,run)
                    expected=longest*delta*60 if longest*delta*60>=signature[4]-1e-8 else 0.
                if not np.isclose(value,expected,rtol=0,atol=1e-7):raise ValueError('selected duration must match this completed interval curve')
                policy=process.get('selection_evidence',{}).get('policy')
                if policy is not None:policies.add(policy)
        y.append(value);refs.add(event.get('reference',{}).get('reference_status','unknown'))
        method=process.get('method','unknown');methods[method]=methods.get(method,0)+1
        fallbacks+=int(event['status']=='degraded')
    if len(policies)>1:raise ValueError('selected duration must use one declared process policy, including adaptive guarded selection')
    used=design['identification']['used_covariates'];indices=[list(study.covariates).index(v) for v in used]
    all_X=np.asarray(X);adjusted=all_X[:,indices] if indices else np.zeros((len(y),1))
    return dict(design=design,X=adjusted,all_X=all_X,D=np.asarray(D),y=np.asarray(y),users=users,tasks=tasks,signature=measurement,
        methods=methods,fallback_events=fallbacks,reference_status=','.join(sorted(refs)),duration_sources=sorted(duration_sources))


def fit_ev_factor_curve(event_results,factor_records,study,*,dose_domain,grid=None,reference_dose=None,
                        assumptions=None,known_density=None,config=None,continuous_assignment=None):
    """Bind completed process outcomes to legal prior factors and declared DAG."""
    try:
        if not isinstance(study,EVFactorStudy):raise ValueError('EVFactorStudy required')
        if assumptions is not None and not isinstance(assumptions,Mapping):raise ValueError('assumptions mapping required')
        if assumptions is not None and assumptions.get('randomized_assignment') is not None:
            if not isinstance(assumptions['randomized_assignment'],(bool,np.bool_)) or bool(assumptions['randomized_assignment'])!=(study.assignment=='randomized'):
                raise ValueError('study assignment and randomized assumption disagree')
        data=_inputs(event_results,factor_records,study);W,q=data['signature'][:2]
        task=dict(task_id=study.study_id,outcome_name=study.outcome_name,outcome_unit='ratio' if study.outcome_name=='eta_raw' else 'seconds',
            target_population=study.target_population,window_minutes=[0.,W],q_kw=q,
            task_pre_treatment=all(t['task_pre_treatment'] is True for t in data['tasks']),
            reference_status=data['reference_status'],reference_uncertainty='not_propagated')
        result=fit_continuous_effects(data['X'],data['D'],data['y'],data['users'],dose_domain=dose_domain,grid=grid,
            reference_dose=reference_dose,incentive_unit=study.incentive_unit,task=task,assumptions=assumptions,
            known_density=known_density,config=config,continuous_assignment=continuous_assignment)
        result['study_design']=data['design']
        result['outcome_measurement']=dict(name=study.outcome_name,source=study.outcome_source,
            criterion='published direct duration estimate with recorded provenance' if study.outcome_source=='duration_estimates' else 'all task bins above profile.onset_fraction*request; dwell only for longest continuous duration',
            direct_duration_sources=data['duration_sources'],
            model_fit_used=study.outcome_name!='eta_raw' and study.outcome_source in ('selected_curve','duration_estimates'),
            methods=data['methods'],fallback_events=data['fallback_events'],physical_timing_identified=False,
            latent_response_effect_identified=False,reference_process_uncertainty_propagated=False,
            effect_interpretation='effect on the declared estimated/observed outcome, conditional on supplied identification assumptions')
        result['factor_pipeline']=dict(schema_version='b1.ev-factor-pipeline.v1',events=len(data['y']),users=len(set(data['users'])),
            failed_events_dropped=0,post_treatment_covariates_used=False,raw_eta_definition_unchanged=True,
            factor_time_checks='state and availability no later than treatment formation; offered signal available by notice')
        return result
    except (ValueError,TypeError,KeyError,OverflowError) as exc:
        return dict(schema_version='b1.ev-factor-pipeline.v1',status='invalid_input',reasons=[dict(code='factor_contract',detail=str(exc))],
                    causal_curve=None,standardized_association=None,inference=None)


def screen_incentive_parents(event_results,factor_records,study,training_users,*,dose_domain):
    """Auxiliary Gaussian BIC on logit dose, restricted to training users.

    Direction comes from the prior timeline. This is only the assignment
    subgraph, not a full causal graph or an automatic adjustment selector.
    """
    data=_inputs(event_results,factor_records,study)
    if not isinstance(training_users,(tuple,list,set)) or not training_users:raise ValueError('explicit training-user IDs required')
    selected=set(training_users)
    if any(not isinstance(v,str) or not v for v in selected) or not selected<=set(data['users']):raise ValueError('training users must be existing original string IDs')
    lo,hi=[number(v,'dose domain') for v in dose_domain]
    if lo<0 or hi<=lo or np.any((data['D']<=lo)|(data['D']>=hi)):raise ValueError('open continuous domain required for logit screen')
    use=np.array([v in selected for v in data['users']]);x=data['all_X'][use];z=logit((data['D'][use]-lo)/(hi-lo));n=len(z)
    if n<50:raise ValueError('at least50 training events for auxiliary parent screening')
    scores=[]
    for indices in _subsets(tuple(range(x.shape[1]))):
        design=np.column_stack([np.ones(n),x[:,indices]]) if indices else np.ones((n,1))
        coef,_,rank,_=np.linalg.lstsq(design,z,rcond=None)
        if rank!=design.shape[1]:continue
        rss=float(np.sum((z-design@coef)**2))
        bic=n*np.log(max(rss/n,1e-15))+(design.shape[1]+1)*np.log(n)
        scores.append(dict(parents=[study.covariates[j] for j in indices],bic=float(bic)))
    best=min(scores,key=lambda s:(s['bic'],len(s['parents']),s['parents']))
    return dict(schema_version='b1.ev-incentive-screen.v1',selected_parents=best['parents'],scores=scores,
        training_users=sorted(selected),training_events=n,used_outcome_values=False,
        direction_source='declared pre-treatment timeline',distribution_assumption='Gaussian linear regression on normalized logit dose',
        full_EV_graph_learned=False,changes_declared_adjustment=False,
        required_adjustment=data['design']['identification']['used_covariates'])


def analyze_ev_factor_study(records,factor_records,study,*,process_config=None,process_method=None,ev_config=None,**curve_options):
    """Run actual event analysis, then the same-bound EV factor analysis."""
    from .api import analyze_events
    events=analyze_events(records,process_config=process_config,process_method=process_method,ev_config=ev_config)
    return dict(schema_version='b1.ev-study-run.v1',events=events,
                factor_analysis=fit_ev_factor_curve(events,factor_records,study,**curve_options))
