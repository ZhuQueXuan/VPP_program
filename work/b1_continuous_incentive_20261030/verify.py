"""Functional, DR algebra, units, support and public pipeline checks."""
from pathlib import Path
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
import sys,json,copy,dataclasses,importlib.util
import numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];sys.path.insert(0,str(ROOT/'B1算法'))
from b1_api import (fit_continuous_effects,ContinuousEffectConfig,analyze_event,analyze_events,provided_reference,
    estimate_event_curve,estimate_metered_curve,EVAnalysisConfig,ReferenceWindow,load_reference_model,predict_reference)
from b1_algorithm.effects.continuous import _dr_pseudo_outcome,local_linear_weights
from run import generate,TASK,ASSUMPTIONS

checks=[]
def check(name,condition):
    assert condition,name
    checks.append(name)

def task_record(index,W=37.,delta=1.,eta=.3):
    start=10000.+index*300.;s=start+np.arange(-15,W+15-1e-8,delta);e=s+delta
    task=dict(task_id='new-'+str(index),user_id='u-'+str(index//4),meter_id='m-'+str(index//4),
        start_min=start,end_min=start+W,notice_min=start-15,request_kw=1.5,task_pre_treatment=True)
    b=np.full(len(s),3.);p=b.copy();p[(s>=start-1e-8)&(e<=start+W+1e-8)]-=1.5*eta
    return dict(task=task,starts_min=s,ends_min=e,power_kw=p,noise_sigma_kw=.05,
        reference=provided_reference(task,s,e,b,available_at_min=start-15))

def main():
    if (HERE/'verification.json').exists():raise RuntimeError('completed verification must not be overwritten')
    x,d,y,users,pdf,assumptions,truth=generate(30103099,'randomized_saturating',users=180)
    options=dict(dose_domain=[0.,2.4],incentive_unit='元/千瓦时（模拟）',task=TASK,continuous_assignment=True,
                 assumptions=assumptions,known_density=pdf,config=dict(n_boot=99,return_audit=True,seed=41))
    base=fit_continuous_effects(x,d,y,users,**options)
    check('continuous input supports actual non-tier amounts',base['status']=='causal')
    queried=fit_continuous_effects(x,d,y,users,grid=[.73,.85,1.17],**options)
    check('query arbitrary amounts directly',queried['status']=='causal' and queried['causal_curve']['incentive_values']==[.73,.85,1.17])
    all_query=fit_continuous_effects(x,d,y,users,grid=sorted(set(np.linspace(0,2.4,81).tolist()+[.73,.85,1.17])),**options)
    for amount,value in zip(queried['causal_curve']['incentive_values'],queried['causal_curve']['contrasts']):
        j=all_query['causal_curve']['incentive_values'].index(amount)
        check('query does not depend on plot grid '+str(amount),abs(value-all_query['causal_curve']['contrasts'][j])<1e-12)
    folded=np.asarray(base['audit']['fold_by_event'])
    check('same original user always same crossfit fold',all(len(set(folded[users==u]))==1 for u in set(users)))
    check('band does not certify full causal coverage',base['inference']['coverage_for_unsmoothed_causal_curve_validated'] is False)
    # Yuan <-> cents changes density and bandwidth units, not the response.
    converted=dict(options);converted.update(dose_domain=[0.,240.],known_density=pdf/100.,incentive_unit='分/千瓦时（模拟）')
    units=fit_continuous_effects(x,d*100,y,users,**converted)
    check('currency unit equivariance',units['status']=='causal' and np.max(abs(np.array(units['causal_curve']['contrasts'])-base['causal_curve']['contrasts']))<1e-10)
    # Exact conditional-expectation DR algebra, without fitting or simulation error.
    a=np.linspace(.01,.99,99);z=np.array([-1.,1.]);p=1+.6*z[:,None]*(2*a[None,:]-1)
    m=.2+.4*np.sin(np.pi*a);mu=m[None,:]+.3*z[:,None]*(1+a[None,:]);badmu=.1+.1*a[None,:]+.05*z[:,None]
    for outcome_ok,density_ok in ((True,True),(True,False),(False,True),(False,False)):
        chosen=mu if outcome_ok else badmu;pi=p if density_ok else np.ones_like(p)
        # Equal target X weights: both numerator marginal and m marginal come
        # from the same nuisance definitions; condition X|D uses true p.
        pseudo=_dr_pseudo_outcome(mu,chosen,chosen.mean(0),pi,pi.mean(0))
        expected=(.5*p*pseudo).sum(0);error=float(np.max(abs(expected-m)))
        check('DR algebra '+str((outcome_ok,density_ok)),error<1e-12 if outcome_ok or density_ok else error>.02)
    L=local_linear_weights(d,np.array([0.,.73,2.4]),.2)
    check('local weights reproduce constants',np.max(abs(L@np.ones(len(d))-1))<1e-12)
    check('local weights reproduce lines including one-sided limits',np.max(abs(L@d-np.array([0.,.73,2.4])))<1e-12)
    try:local_linear_weights(np.ones(20),np.array([1.]),.2)
    except ValueError:check('singular local fit rejected',True)
    else:raise AssertionError('singular local fit accepted')
    # Explicit input and statistical design boundaries.
    mutations=[('unknown design',{'continuous_assignment':None}),('outside query',{'grid':[2.5]}),
       ('outside reference',{'reference_dose':-1.}),('missing unit',{'incentive_unit':''}),
       ('negative domain',{'dose_domain':[-1.,2.4]}),('invalid density',{'known_density':np.zeros(len(d))}),
       ('unsupported nonuniform known density',{'known_density':pdf*2}),('boolean config',{'config':{'n_boot':True}})]
    for label,change in mutations:
        opt=options|change;r=fit_continuous_effects(x,d,y,users,**opt)
        check(label,r['status']=='invalid_input' and r['causal_curve'] is None)
    seven=np.resize(np.linspace(.1,2.3,7),len(d))
    check('seven discrete arms not relabelled continuous',fit_continuous_effects(x,seven,y,users,**options)['status']=='invalid_input')
    atom=d.copy();atom[0]=0.
    check('zero point mass mixed design rejected',fit_continuous_effects(x,atom,y,users,**options)['status']=='invalid_input')
    gap=np.where(d<1.2,d*.6,2.4-(2.4-d)*.6)
    check('no bridging an unobserved incentive gap',fit_continuous_effects(x,gap,y,users,grid=[0.,1.2,2.4],**options)['status']=='unsupported')
    unclear=options|{'assumptions':dict(assumptions,pre_treatment_X=None)}
    association=fit_continuous_effects(x,d,y,users,**unclear)
    check('unconfirmed causal assumptions yield association only',association['status']=='association' and association['causal_curve'] is None and association['inference'] is None)
    # Free task lengths; grid alignment still required.
    free=[]
    for i,(W,delta) in enumerate(((20.,1.),(37.,1.),(45.,15.),(75.,1.),(75.,15.),(5.5,1/6),(120.,1.))):
        r=analyze_event(**task_record(i,W,delta),process_method='ride_template')
        check('free task duration '+str((W,delta)),r['status']=='ok' and abs(r['outcome']['value']-.3)<1e-8)
        free.append(dict(duration=W,meter_interval=delta,status=r['status'],eta=r['outcome']['value']))
    cut=task_record(8,37.5,1.)
    check('cut task interval remains unsupported',analyze_event(**cut)['status']=='unavailable')
    # Actual public event and meter curves share constant-reference contrasts.
    group=[]
    for i,value in enumerate(y[:400]):group.append(task_record(100+i,45.,15.,float(value)))
    events=analyze_events(group,process_method='conservative')
    check('complete coarse event batch is preserved',all(e['status']=='ok' for e in events))
    shared=dict(dose_domain=[0,2.4],grid=[.73,.85,1.17],incentive_unit='元/千瓦时（模拟）',
        continuous_assignment=True,assumptions=assumptions,known_density=pdf[:400],continuous_config=dict(n_boot=99,seed=41))
    event_curve=estimate_event_curve(events,x[:400],d[:400],**shared)
    meter_curve=estimate_metered_curve(group,x[:400],d[:400],**shared)
    check('public complete-events curve chain',event_curve['status']=='causal')
    check('public meter-only curve chain',meter_curve['status']=='causal')
    check('constant reference cancels in continuous incentive contrast',np.max(abs(np.asarray(event_curve['causal_curve']['contrasts'])-meter_curve['causal_curve']['contrasts']))<1e-10)
    mixed=copy.deepcopy(events);mixed[-1]['task']['request_kw']=2.
    check('heterogeneous task definitions still rejected',estimate_event_curve(mixed,x[:400],d[:400],**shared)['status']=='invalid_input')
    # Existing 1-minute reference model accepts a free37-minute task, without
    # extending its already-frozen relative-time prediction domain.
    fixture=json.loads((ROOT/'work/b1_formal_v1_20261029/reference/query_fixture.json').read_text(encoding='utf-8'))
    w=ReferenceWindow(**fixture);start=w.task_start_min
    w=dataclasses.replace(w,resource_type='EV',task_end_min=start+37.,starts_min=start+np.arange(-15.,52.),ends_min=start+np.arange(-14.,53.),prior_mean_kw=np.full(67,3.))
    model=load_reference_model(ROOT/'work/b1_formal_v1_20261029/reference/artifact');pred=predict_reference(model,w)
    check('free duration legal one-minute predicted reference',pred.reference_status=='available')
    # Migration parity on original supported task: archived source vs current.
    spec=importlib.util.spec_from_file_location('_b1_cont_previous',HERE/'before_source/b1_algorithm/__init__.py',submodule_search_locations=[str(HERE/'before_source/b1_algorithm')])
    legacy=importlib.util.module_from_spec(spec);sys.modules[spec.name]=legacy;spec.loader.exec_module(legacy)
    for i,delta in enumerate((1/6,1.,15.)):
        rec=task_record(10+i,30.,delta);old=legacy.analyze_event(**rec,process_method='ride_template');new=analyze_event(**rec,process_method='ride_template')
        check('old task numerical parity '+str(delta),old['status']==new['status']=='ok' and abs(old['outcome']['value']-new['outcome']['value'])<1e-12 and np.max(abs(np.array(old['process']['reduction_interval_kw'])-new['process']['reduction_interval_kw']))<1e-10)
    (HERE/'free_duration_cases.json').write_text(json.dumps(free,indent=2),encoding='utf-8')
    (HERE/'arbitrary_amount_predictions.json').write_text(json.dumps(queried,ensure_ascii=False,indent=2),encoding='utf-8')
    (HERE/'pipeline_event_curve.json').write_text(json.dumps(event_curve,ensure_ascii=False,indent=2),encoding='utf-8')
    result=dict(passed=True,n_checks=len(checks),checks=checks,arbitrary_amounts=[.73,.85,1.17],
        function_only_EV_events=400,DR_four_quadrants_checked=True,old_curves_preserved=True,new_performance_superiority_claim=False)
    (HERE/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
