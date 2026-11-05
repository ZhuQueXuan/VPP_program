"""Small reproducible usage example, never launches research experiments."""
from pathlib import Path
import argparse,json
import numpy as np
from . import analyze_event,analyze_events,provided_reference,estimate_event_effects,__version__
from .effects import EffectConfig

def demo(output):
 task=dict(task_id='demo-single',user_id='demo-user',meter_id='demo-meter',start_min=1000.,
           end_min=1030.,notice_min=985.,request_kw=1.5,task_pre_treatment=True)
 s=task['start_min']+np.arange(-15.,45.);e=s+1.;b=np.full(len(s),3.)
 relative=s-task['start_min'];reduction=np.where((relative>=3)&(relative<30),1.2,0.)
 p=b-reduction+np.random.default_rng(991001).normal(0,.05,len(s))
 reference=provided_reference(task,s,e,b,available_at_min=task['notice_min'])
 event=analyze_event(task,s,e,p,reference,.05)
 rng=np.random.default_rng(991002);records=[];X=[];d=[]
 for user in range(140):
  x=float(rng.uniform(-1,1))
  for k,dose in enumerate(rng.permutation([0.,1.])):
   start=10000.+user*240.+k*120.;ss=start+np.arange(-15.,45.,15.);ee=ss+15.
   tt=dict(task_id=f'demo-{user}-{k}',user_id=f'demo-{user}',meter_id=f'demo-meter-{user}',
           start_min=start,end_min=start+30.,notice_min=start-15.,request_kw=1.5,task_pre_treatment=True)
   bb=np.full(4,3.);eta=.1+.2*dose+.03*x+float(rng.normal(0,.01))
   pp=bb-np.array([0.,1.5*eta,1.5*eta,0.])
   rr=provided_reference(tt,ss,ee,bb,available_at_min=tt['notice_min'])
   records.append(dict(task=tt,starts_min=ss,ends_min=ee,power_kw=pp,reference=rr,noise_sigma_kw=.05))
   X.append([x]);d.append(dose)
 events=analyze_events(records)
 assumptions=dict(pre_treatment_X=True,consistent_treatment=True,no_interference=True,
        same_outcome_definition=True,conditional_exchangeability=None,randomized_assignment=True)
 effects=estimate_event_effects(events,X,d,levels=[0.,1.],known_pi=np.full((len(events),2),.5),
            assumptions=assumptions,effect_config=EffectConfig(seed=991003))
 result=dict(algorithm_version=__version__,scope='synthetic usage demonstration; not a research-performance or real-data result',
             single_event=event,population_effect_example=effects)
 output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
 output.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
 print('B1 version:',__version__)
 print('Single-event status:',event['status'],'method:',event.get('process',{}).get('method'))
 print('Population effect status:',effects['status'])
 if effects.get('causal_curve'):print('Relative effect:',effects['causal_curve']['contrasts'][1])
 print('Saved:',output.resolve())
 return result

def main():
 parser=argparse.ArgumentParser(description='B1 formal algorithm usage example; no main experiments.')
 parser.add_argument('--demo',action='store_true');parser.add_argument('--out',default='outputs/B1正式版示例.json')
 args=parser.parse_args()
 if not args.demo:parser.print_help();return
 result=demo(args.out)
 if result['single_event']['status'] not in ('ok','degraded') or result['population_effect_example']['status']!='causal':
  raise SystemExit(1)
if __name__=='__main__':main()
