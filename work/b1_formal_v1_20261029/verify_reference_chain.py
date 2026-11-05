"""Finite actual prediction -> observed process -> population-effect integration.

This is an interface/definition acceptance example, not a performance experiment.
"""
from pathlib import Path
import json,sys,time
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from b1_api import (ReferenceWindow,load_reference_model,predict_reference,analyze_events,
                    estimate_event_effects)
from b1_algorithm.effects import EffectConfig

OUT=Path(__file__).resolve().parent
plan=dict(seed=885200,users=28,events_per_user=2,levels=[0.,1.],
  design='one randomized order of low/high within each user; tasks one week apart, no carryover by construction',
  domain='1min, task30min,q1.5, observation-15..45min, independent.05kW meter noise',
  reference='frozen native LightGBM reference artifact from independent historical training users; no truth supplied to model',
  estimand='relative eta contrast for fixed task and common pre-notice reference rule',
  claim='actual unified call-chain acceptance only; no new aggregate performance or coverage claim')
(OUT/'reference_chain_protocol.json').write_text(json.dumps(plan,indent=2),encoding='utf-8')
model=load_reference_model(OUT/'reference/artifact')
rng=np.random.default_rng(plan['seed']);records=[];X=[];d=[];predictions=[]
tic=time.perf_counter()
for user in range(plan['users']):
 baseline=float(3.+.3*rng.uniform(-1,1));prefix=np.full(60,baseline)
 for event,dose in enumerate(rng.permutation([0.,1.])):
  start=90000.+user*20160.+event*10080.;notice=start-15.
  starts=start+np.arange(-15.,45.);ends=starts+1
  task_id=f'chain-u{user}-e{event}';uid=f'chain-u{user}';meter=f'chain-meter{user}'
  window=ReferenceWindow(task_id=task_id,user_id=uid,meter_id=meter,resource_type='EV',
       task_start_min=start,task_end_min=start+30.,request_kw=1.5,notice_min=notice,
       starts_min=starts,ends_min=ends,pre_starts_min=notice+np.arange(-60.,0.),
       pre_ends_min=notice+np.arange(-59.,1.),pre_power_kw=prefix,pre_available_min=notice,
       prior_mean_kw=np.full(60,baseline),prior_available_min=notice-1.,prior_source_count=2,
       prior_source_ids=(f'prior-{user}-a',f'prior-{user}-b'),clock_hour=12.,weekday=3,
       calendar_available_min=notice-10.,temperature_c=26.,temperature_available_min=notice-1.)
  prediction=predict_reference(model,window)
  assert prediction.reference_status=='available',prediction.reasons
  # A flat task response gives a known raw-energy effect; no simulator truth is
  # passed to either reference model, process selector or effects estimator.
  rel=starts-start
  eta=.1+.2*dose
  reduction=np.where((rel>=0)&(rel<30),1.5*eta,0.)
  power=baseline-reduction+rng.normal(0.,.05,len(starts))
  task=dict(task_id=task_id,user_id=uid,meter_id=meter,start_min=start,end_min=start+30.,
            notice_min=notice,request_kw=1.5,task_pre_treatment=True)
  records.append(dict(task=task,starts_min=starts,ends_min=ends,power_kw=power,
                      reference=prediction,noise_sigma_kw=.05))
  predictions.append(prediction.reference_kw.tolist());X.append([baseline]);d.append(dose)
events=analyze_events(records)
assert all(e['status']=='ok' for e in events),[(i,e['status'],e['reasons']) for i,e in enumerate(events) if e['status']!='ok']
independent=[]
for rec,event in zip(records,events):
 use=(rec['starts_min']>=rec['task']['start_min'])&(rec['ends_min']<=rec['task']['end_min'])
 eta=float(np.sum((rec['reference'].reference_kw[use]-rec['power_kw'][use])*(rec['ends_min'][use]-rec['starts_min'][use]))/45)
 assert abs(eta-event['outcome']['value'])<1e-12
 independent.append(eta)
assumptions=dict(pre_treatment_X=True,consistent_treatment=True,no_interference=True,
                 same_outcome_definition=True,conditional_exchangeability=None,randomized_assignment=True)
result=estimate_event_effects(events,X,d,levels=[0.,1.],assumptions=assumptions,
             known_pi=np.full((len(events),2),.5),effect_config=EffectConfig(seed=885201,n_boot=199))
assert result['status']=='causal',result.get('reasons')
effect=result['causal_curve']['contrasts'][1]
assert abs(effect-.2)<.03,(effect,.2)
counts={}
for event in events:
 method=event['process']['method'];counts[method]=counts.get(method,0)+1
assert all(e['reference']['counterfactual_identified'] is False for e in events)
assert all(e['process']['physical_timing'] is None for e in events)
assert result['uncertainty']['reference_process_uncertainty_propagated'] is False
receipt=dict(passed=True,seed=plan['seed'],users=28,events=56,methods=counts,
             raw_integrals_independently_verified=56,estimated_effect=effect,generator_effect=.2,
             model_id=model.model_id,elapsed_seconds=time.perf_counter()-tic,
             physical_timing_claim=False,full_chain_uncertainty_claim=False,
             scope=plan['claim'])
(OUT/'reference_chain_events.json').write_text(json.dumps(events,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'reference_chain_effect.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'reference_chain_receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(receipt,ensure_ascii=False,indent=2))
