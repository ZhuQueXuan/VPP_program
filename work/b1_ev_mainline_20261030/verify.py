"""Mainline public contract, causal role and compatibility checks."""
from pathlib import Path
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
import sys,json,copy,dataclasses,importlib.util
import numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];sys.path.insert(0,str(ROOT/'B1算法'))
from b1_api import (EVFactorStudy,describe_ev_study,fit_ev_factor_curve,screen_incentive_parents,
    fit_continuous_effects,estimate_event_curve,analyze_events)
from b1_algorithm.factors import _inputs
from run import ASSUMPTIONS

checks=[]
def check(name,condition):
    assert condition,name
    checks.append(name)

def main(receipt_name='verification.json'):
    if Path(receipt_name).name!=receipt_name:raise ValueError('receipt must be a local filename')
    target=HERE/receipt_name
    if target.exists():raise RuntimeError('completed verification cannot be overwritten')
    seed=5312100;study=EVFactorStudy('test-study','元/千瓦时')
    facts=json.loads((ROOT/f'data/B1_EV_mainline_v1_20261030/{seed}_positive_facts.json').read_text(encoding='utf-8'))
    factors=[r['factor_record'] for r in facts]
    events=json.loads((HERE/f'events/{seed}_positive_ride_template.json').read_text(encoding='utf-8'))
    description=describe_ev_study(study)
    check('observational fork requires both declared conditions',description['identification']['minimal_sets']==[['deadline_slack','demand_urgency']])
    randomized=describe_ev_study(dataclasses.replace(study,assignment='randomized'))
    check('randomized graph admits empty backdoor set',[] in randomized['identification']['minimal_sets'])
    for label,changed in [('post treatment adjustment',dataclasses.replace(study,covariates=('participation',))),
       ('unknown graph node',dataclasses.replace(study,graph_edges=(('unknown','response'),))),
       ('graph cycle',dataclasses.replace(study,graph_edges=(('deadline_slack','demand_urgency'),('demand_urgency','deadline_slack')))),
       ('time backwards',dataclasses.replace(study,graph_edges=(('response','deadline_slack'),))),
       ('eta cannot use fit',dataclasses.replace(study,outcome_name='eta_raw'))]:
        try:describe_ev_study(changed)
        except ValueError:check(label,True)
        else:raise AssertionError(label)
    options=dict(dose_domain=[0,2.4],grid=[.6,1.,1.6],reference_dose=.6,assumptions=ASSUMPTIONS,
                 continuous_assignment=True,config=dict(n_boot=99,return_audit=True,seed=72))
    data=_inputs(events,factors,study)
    public=fit_ev_factor_curve(events,factors,study,**options)
    check('actual process to factor curve supported',public['status'] in ('causal','unsupported'))
    context=dict(task_id=study.study_id,outcome_name=study.outcome_name,outcome_unit='seconds',target_population=study.target_population,
        window_minutes=[0,30.],q_kw=1.5,task_pre_treatment=True,reference_status=data['reference_status'],reference_uncertainty='not_propagated')
    direct=fit_continuous_effects(data['X'],data['D'],data['y'],data['users'],task=context,incentive_unit=study.incentive_unit,**options)
    check('public bridge equals shared continuous core',public['status']==direct['status'] and public['causal_curve']==direct['causal_curve'] and public['inference']==direct['inference'])
    check('does not claim latent physical effect or full measurement CI',public['outcome_measurement']['latent_response_effect_identified'] is False and public['outcome_measurement']['reference_process_uncertainty_propagated'] is False)
    check('refusals retained without reading participation as covariate',len(factors)==public['factor_pipeline']['events'] and public['factor_pipeline']['post_treatment_covariates_used'] is False)
    for label,mutate in [
      ('wrong task',lambda f:f[0].update(task_id='other')),
      ('wrong meter',lambda f:f[0].update(meter_id='other')),
      ('future offer',lambda f:f[0].update(treatment_set_min=events[0]['task']['notice_min']+1)),
      ('post incentive covariate',lambda f:f[0]['available_at_min'].update(deadline_slack=f[0]['treatment_set_min']+.5)),
      ('late state',lambda f:f[0]['state_as_of_min'].update(demand_urgency=f[0]['treatment_set_min']+1)),
      ('availability before state',lambda f:f[0]['available_at_min'].update(deadline_slack=f[0]['state_as_of_min']['deadline_slack']-1)),
      ('boolean condition',lambda f:f[0].update(deadline_slack=True)),
      ('missing time mapping',lambda f:f[0].update(available_at_min=None))]:
        changed=copy.deepcopy(factors);mutate(changed)
        value=fit_ev_factor_curve(events,changed,study,**options)
        check(label,value['status']=='invalid_input' and value['causal_curve'] is None)
    broken=copy.deepcopy(events);broken[0]['status']='unavailable'
    check('bad events never complete-case dropped',fit_ev_factor_curve(broken,factors,study,**options)['status']=='invalid_input')
    changed=copy.deepcopy(events);changed[0]['process']['analysis_profile']['onset_fraction']=.2
    check('mixed outcome criterion rejected',fit_ev_factor_curve(changed,factors,study,**options)['status']=='invalid_input')
    training=sorted(set(data['users']))[:120]
    screen=screen_incentive_parents(events,factors,study,training,dose_domain=[0,2.4])
    changed=copy.deepcopy(factors)
    for r in changed:
        if r['user_id'] not in training:r['offered_incentive']=.2
    screen2=screen_incentive_parents(events,changed,study,training,dose_domain=[0,2.4])
    check('test-user doses cannot change train graph screen',screen==screen2)
    check('screen never changes required adjustment',screen['required_adjustment']==['deadline_slack','demand_urgency'] and screen['changes_declared_adjustment'] is False)
    cents=copy.deepcopy(factors)
    for r in cents:r['offered_incentive']*=100
    currency=screen_incentive_parents(events,cents,dataclasses.replace(study,incentive_unit='分/千瓦时'),training,dose_domain=[0,240])
    check('screen logit normalizes currency units',currency['selected_parents']==screen['selected_parents'] and np.max(abs(np.array([r['bic'] for r in currency['scores']])-np.array([r['bic'] for r in screen['scores']])))<1e-9)
    # Existing eta pipeline and frozen source produce unchanged curves.
    spec=importlib.util.spec_from_file_location('_b1_before_ev_mainline',HERE/'before_source/b1_algorithm/__init__.py',submodule_search_locations=[str(HERE/'before_source/b1_algorithm')])
    old=importlib.util.module_from_spec(spec);sys.modules[spec.name]=old;spec.loader.exec_module(old)
    eta_study=dataclasses.replace(study,outcome_name='eta_raw',outcome_source='raw_observed')
    eta=fit_ev_factor_curve(events,factors,eta_study,**options)
    old_options=dict(dose_domain=[0,2.4],grid=[.6,1.,1.6],reference_dose=.6,incentive_unit='元/千瓦时',
                     assumptions=ASSUMPTIONS,continuous_config=options['config'],continuous_assignment=True)
    current_eta=estimate_event_curve(events,data['all_X'],data['D'],**old_options)
    old_eta=old.api.estimate_event_curve(events,data['all_X'],data['D'],**old_options)
    check('old eta curves preserved',eta['status']==old_eta['status']==current_eta['status'] and eta['causal_curve']==old_eta['causal_curve']==current_eta['causal_curve'])
    check('raw eta is not fitted duration',eta['outcome_measurement']['model_fit_used'] is False)
    result=dict(passed=True,n_checks=len(checks),checks=checks,events=len(events),mainline_measured_outcome_bridge=True,
                old_eta_unchanged=True,scientific_performance_claim=False)
    with target.open('x',encoding='utf-8') as stream:json.dump(result,stream,ensure_ascii=False,indent=2)
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--receipt',default='verification.json')
    main(parser.parse_args().receipt)
