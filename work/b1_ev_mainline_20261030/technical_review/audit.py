"""Small independent contracts/algebra only. Run with python -B, never run.py."""
from pathlib import Path
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
import sys,json,copy,dataclasses,importlib.util,hashlib,argparse
import numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT/'B1算法'))
from b1_api import (EVFactorStudy,describe_ev_study,fit_ev_factor_curve,screen_incentive_parents,
                    analyze_events,provided_reference,fit_continuous_effects,select_ev_reference)
from b1_algorithm.factors import _inputs,_separated
from b1_algorithm.reference.core import ReferenceWindow,ReferenceModel
spec=importlib.util.spec_from_file_location('_small_ev_audit_simulation',HERE.parent/'simulation.py')
sim=importlib.util.module_from_spec(spec);spec.loader.exec_module(sim)
checks=[]
def check(name,ok,detail=None):
    checks.append(dict(name=name,passed=bool(ok),detail=detail))
def rejects(fn):
    try:fn()
    except (ValueError,TypeError,KeyError,OverflowError):return True
    return False
def public_invalid(fn):
    try:r=fn();return r.get('status')=='invalid_input'
    except Exception:return False

class WorkingBooster:
    def __init__(self):self.calls=[]
    def predict(self,x):
        self.calls.append(np.array(x));return 3.2+.01*np.asarray(x)[:,1]+.02*np.asarray(x)[:,2]

def bind(facts):
    records=[]
    for r in facts:
        records.append(dict(task=r['task'],starts_min=r['starts_min'],ends_min=r['ends_min'],power_kw=r['power_kw'],noise_sigma_kw=r['noise_sigma_kw'],
          reference=provided_reference(r['task'],r['starts_min'],r['ends_min'],r['reference_window']['prior_mean_kw'],available_at_min=r['task']['notice_min'])))
    return analyze_events(records,process_method='conservative')

def strict_history_metadata(factual):
    # Known synthetic clock convention; these are metadata for a FUNCTIONAL
    # case, not an attempt to infer metadata from real historical power.
    h=copy.deepcopy(factual['historical_non_event']);uid=factual['task']['user_id'];meter=factual['task']['meter_id']
    rel0=factual['reference_window']['pre_starts_min'][0]-factual['task']['start_min']
    for r in h:
        start=r['starts_min'][0]-rel0
        r.update(user_id=uid,meter_id=meter,reference_context=dict(clock_hour=(start%1440)/60,weekday=int(start//1440)%7,
                 calendar_available_min=start-16.,temperature_available_min=start-16.))
    return h

def main(outname):
    target=HERE/outname
    if target.exists():raise RuntimeError('preserve earlier receipt')
    study=EVFactorStudy('independent_factor_audit','yuan/kWh')
    design=describe_ev_study(study)
    check('observational_two_forks_require_both_factors',design['identification']['minimal_sets']==[['deadline_slack','demand_urgency']])
    randomized=dataclasses.replace(study,assignment='randomized')
    check('randomized_declared_graph_has_empty_minimal_set',[] in describe_ev_study(randomized)['identification']['minimal_sets'])
    check('fork_unconditioned_open',not _separated([('L','D'),('L','R')],'D','R',[]))
    check('fork_conditioned_closed',_separated([('L','D'),('L','R')],'D','R',['L']))
    collider=[('L','D'),('L','C'),('Z','C'),('Z','R')]
    check('collider_without_condition_closed',_separated(collider,'D','R',[]))
    check('collider_condition_opens_path',not _separated(collider,'D','R',['C']))
    for name,bad in [('post_treatment_A',dataclasses.replace(study,covariates=('participation',))),
      ('pre_cycle',dataclasses.replace(study,graph_edges=(('deadline_slack','demand_urgency'),('demand_urgency','deadline_slack')))),
      ('self_edge',dataclasses.replace(study,graph_edges=(('incentive','incentive'),))),
      ('wrong_time_order',dataclasses.replace(study,graph_edges=(('participation','incentive'),))),
      ('unknown_node',dataclasses.replace(study,graph_edges=(('unmeasured','response'),))),
      ('random_graph_with_D_parent',dataclasses.replace(randomized,graph_edges=(('deadline_slack','incentive'),)))]:
        check('graph_reject_'+name,rejects(lambda b=bad:describe_ev_study(b)))
    facts,_,_=sim.generate(5398200,n_users=60,events_per_user=2,W=5,assignment='randomized')
    events=bind(facts);factors=[r['factor_record'] for r in facts]
    check('small_actual_meter_events_complete',len(events)==120 and all(e['status']=='ok' for e in events))
    base=_inputs(events,factors,randomized)
    manual=[];eta=[]
    for r in facts:
        s=np.asarray(r['starts_min']);e=np.asarray(r['ends_min']);q=r['task']['request_kw']
        use=(s>=r['task']['start_min'])&(e<=r['task']['end_min'])
        reduction=np.asarray(r['reference_window']['prior_mean_kw'])-r['power_kw']
        manual.append(float(((reduction[use]>=q*.1)*(e-s)[use]*60).sum()))
        eta.append(float((reduction[use]*(e-s)[use]).sum()/(q*5)))
    check('selected_duration_matches_independent_raw_threshold_in_coarse_route',np.max(abs(base['y']-manual))<1e-12)
    rawstudy=dataclasses.replace(randomized,outcome_source='raw_observed')
    check('raw_duration_matches_independent_count',np.max(abs(_inputs(events,factors,rawstudy)['y']-manual))<1e-12)
    etastudy=dataclasses.replace(randomized,outcome_name='eta_raw',outcome_source='raw_observed')
    check('raw_eta_preserves_independent_integral',np.max(abs(_inputs(events,factors,etastudy)['y']-eta))<1e-12)
    for name,mutator in [
      ('wrong_factor_identity',lambda e,f:f[0].update(user_id='foreign')),
      ('factor_state_after_formation',lambda e,f:f[0]['state_as_of_min'].update(deadline_slack=f[0]['treatment_set_min']+1)),
      ('factor_available_after_formation',lambda e,f:f[0]['available_at_min'].update(demand_urgency=f[0]['treatment_set_min']+1)),
      ('availability_before_state',lambda e,f:f[0]['available_at_min'].update(deadline_slack=f[0]['state_as_of_min']['deadline_slack']-1)),
      ('reward_formed_after_notice',lambda e,f:f[0].update(treatment_set_min=e[0]['task']['notice_min']+1)),
      ('wrong_meter_criterion',lambda e,f:e[0]['process']['analysis_profile'].update(onset_fraction=.11)),
      ('failed_event',lambda e,f:e[0].update(status='unavailable')),
      ('duplicate_identity',lambda e,f:(e.__setitem__(1,copy.deepcopy(e[0])),f.__setitem__(1,copy.deepcopy(f[0])))),
      ('process_task_mismatch',lambda e,f:e[0]['process'].update(task_id='foreign-process')),
      ('fractional_meter_duration',lambda e,f:e[0]['process']['features']['selected_curve'].update(cumulative_response_seconds=3.14159)),
      ('selected_duration_disagrees_with_curve',lambda e,f:e[0]['process']['features']['selected_curve'].update(cumulative_response_seconds=(e[0]['process']['features']['selected_curve']['cumulative_response_seconds']+60)%360)),
      ('task_process_request_mismatch',lambda e,f:[r['task'].update(request_kw=2.) for r in e])]:
        ee,ff=copy.deepcopy(events),copy.deepcopy(factors);mutator(ee,ff)
        check('contract_reject_'+name,rejects(lambda:_inputs(ee,ff,randomized)))
    check('invalid_study_returns_invalid_not_uncaught_exception',public_invalid(lambda:fit_ev_factor_curve(events,factors,None,dose_domain=[0,2.4],assumptions={'randomized_assignment':True})))
    options=dict(dose_domain=[0,2.4],grid=[.5,1.2,1.9],reference_dose=1.2,continuous_assignment=True,
      known_density=np.full(len(facts),1/2.4),assumptions=dict(pre_treatment_X=True,consistent_treatment=True,no_interference=True,
      same_outcome_definition=True,randomized_assignment=True),config=dict(n_boot=99,bandwidth=.6,min_local_events=5,min_local_users=3,min_local_ess=5.,max_weighted_smd=1.,seed=934))
    curve=fit_ev_factor_curve(events,factors,randomized,**options)
    check('small_public_factor_curve_supported',curve['status']=='causal',curve.get('reasons'))
    W,q=base['signature'][:2]
    context=dict(task_id=randomized.study_id,outcome_name=randomized.outcome_name,outcome_unit='seconds',target_population=randomized.target_population,
      window_minutes=[0,W],q_kw=q,task_pre_treatment=True,reference_status=base['reference_status'],reference_uncertainty='not_propagated')
    direct=fit_continuous_effects(base['X'],base['D'],base['y'],base['users'],task=context,incentive_unit=randomized.incentive_unit,**options)
    check('public_factor_equals_same_continuous_core',curve['status']==direct['status']=='causal' and
      np.max(abs(np.array(curve['causal_curve']['contrasts'])-direct['causal_curve']['contrasts']))<1e-12)
    obscure=options|{'assumptions':options['assumptions']|{'pre_treatment_X':None}}
    c=fit_ev_factor_curve(events,factors,randomized,**obscure)
    check('unknown_assumptions_return_only_association',c['status']=='association' and c['causal_curve'] is None and c['inference'] is None)
    training=sorted(set(base['users']))[:30]
    screen=screen_incentive_parents(events,factors,randomized,training,dose_domain=[0,2.4])
    altered=copy.deepcopy(factors)
    for r in altered:
        if r['user_id'] not in training:r.update(offered_incentive=2.3,deadline_slack=4.,demand_urgency=-3.)
    other=screen_incentive_parents(events,altered,randomized,training,dose_domain=[0,2.4])
    check('parent_screen_ignores_evaluation_values',screen==other)
    cents=copy.deepcopy(factors)
    for r in cents:r['offered_incentive']*=100
    cs=screen_incentive_parents(events,cents,dataclasses.replace(randomized,incentive_unit='cent/kWh'),training,dose_domain=[0,240])
    check('parent_screen_yuan_cent_equivariance',screen['selected_parents']==cs['selected_parents'] and
      max(abs(a['bic']-b['bic']) for a,b in zip(screen['scores'],cs['scores']))<1e-10)
    check('screen_never_changes_declared_adjustment',screen['changes_declared_adjustment'] is False and screen['required_adjustment']==base['design']['identification']['used_covariates'])
    # Honest synthetic history metadata, shared with the same user/meter.
    w=ReferenceWindow(**facts[0]['reference_window']);hist=strict_history_metadata(facts[0])
    model=ReferenceModel(WorkingBooster(),'functional-audit',-1e12,0,(),(),'audit')
    chosen=select_ev_reference(model,w,hist)
    check('small_history_selector_available',chosen['reference'].reference_status=='available')
    ledger=chosen['selection']['ledger'];byid={h['source_id']:h for h in hist}
    check('each_pseudo_prior_strictly_earlier',all(len(v['prior_sources'])>=2 and all(byid[k]['available_at_min']<=v['pseudo_notice_min'] for k in v['prior_sources']) for v in ledger))
    for name,mutator in [
      ('not_non_event',lambda h:h[0].update(non_event=False)),
      ('duplicate_source',lambda h:h[1].update(source_id=h[0]['source_id'])),
      ('current_task_source',lambda h:h[0].update(source_id=w.task_id)),
      ('future_label',lambda h:h[0].update(available_at_min=w.notice_min+1)),
      ('foreign_user',lambda h:h[0].update(user_id='foreign')),
      ('foreign_meter',lambda h:h[0].update(meter_id='foreign')),
      ('late_weather',lambda h:[r['reference_context'].update(temperature_available_min=r['available_at_min']) for r in h]),
      ('late_calendar',lambda h:[r['reference_context'].update(calendar_available_min=r['available_at_min']) for r in h])]:
        h=copy.deepcopy(hist);mutator(h)
        check('history_reject_'+name,rejects(lambda:select_ev_reference(model,w,h)))
    wrong=dataclasses.replace(w,prior_mean_kw=np.asarray(w.prior_mean_kw)+.1)
    check('history_reject_wrong_prior',rejects(lambda:select_ev_reference(model,wrong,hist)))
    # Move the numerical absolute-minute origin, preserving physical calendar.
    shift=123.
    fields={k:np.asarray(getattr(w,k))+shift for k in ('starts_min','ends_min','pre_starts_min','pre_ends_min')}
    fields.update({k:getattr(w,k)+shift for k in ('task_start_min','task_end_min','notice_min','pre_available_min','prior_available_min','calendar_available_min','temperature_available_min')})
    w2=dataclasses.replace(w,**fields);h2=copy.deepcopy(hist)
    for h in h2:
        for key in ('starts_min','ends_min'):h[key]=(np.asarray(h[key])+shift).tolist()
        h['available_at_min']+=shift
        for key in ('calendar_available_min','temperature_available_min'):h['reference_context'][key]+=shift
    two=select_ev_reference(model,w2,h2)
    err=max(abs(chosen['selection']['mean_history_task_mae_kw'][k]-two['selection']['mean_history_task_mae_kw'][k]) for k in ('gbdt','prev10'))
    check('selector_invariant_to_absolute_minute_origin',err<1e-10,float(err))
    sources=['B1算法/b1_algorithm/factors.py','B1算法/b1_algorithm/reference/ev_selection.py']
    receipt=dict(passed=all(v['passed'] for v in checks),n_checks=len(checks),checks=checks,
      issues=[v for v in checks if not v['passed']],production_files_modified=False,main_study_rerun=False,
      scope='120 five-minute synthetic raw-coarse functional cases; graph/contract/unit algebra only, not research performance',
      audit_correction='First audit_receipt.json weather/calendar negatives mutated obsolete top-level metadata, not current reference_context. Corrected only this audit and preserved earlier receipt; no production changes.',
      source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources})
    with target.open('x',encoding='utf-8') as stream:json.dump(receipt,stream,ensure_ascii=False,indent=2)
    print(json.dumps(receipt,ensure_ascii=False,indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',default='audit_receipt.json');main(parser.parse_args().out)
