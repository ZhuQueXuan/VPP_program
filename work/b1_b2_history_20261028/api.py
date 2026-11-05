"""Optional research forecast. Uses completed same-resource histories only."""
import copy
from datetime import datetime,timedelta
import numpy as np
import joblib
from io_utils import BASE,sha
from legacy import safe_b2,base_forecast,templates
from features import physical,current,extract_one
from models import predict

VERSION='B1-B2-HISTORY-v1-20261028'
REQUIRED=['b','T','q','E','low','high','prob','reference','green_preference','green_attribute','risk','permission']
def stamp(x):
    if not isinstance(x,str):raise ValueError('ISO timestamp string required')
    t=datetime.fromisoformat(x)
    if t.tzinfo is None or t.utcoffset() is None:raise ValueError('timezone-aware timestamp required')
    return t

def histories(case):
    resource=case['resource_id'];event=case['event_id']
    if not isinstance(resource,str) or not resource or not isinstance(event,str) or not event:raise ValueError('nonempty resource_id/event_id required')
    start=stamp(case['start']);cutoff=stamp(case['information_cutoff'])
    if cutoff>start:raise ValueError('information cutoff after current request')
    records=case.get('history',[])
    if not isinstance(records,list) or len(records)>3:raise ValueError('zero to three preceding histories required')
    ids={event};last=None;last_end=None;refs=[];powers=[];amplitudes=[]
    for h in records:
        if h['resource_id']!=resource or not isinstance(h['event_id'],str) or not h['event_id'] or h['event_id'] in ids:raise ValueError('history resource/event binding invalid')
        ids.add(h['event_id']);a=stamp(h['start']);end=stamp(h['observation_end']);available=stamp(h['available_at'])
        if end!=a+timedelta(minutes=120) or end>available or available>cutoff or end>start or (last is not None and (a<=last or a<last_end)):raise ValueError('history must be complete, ordered, nonoverlapping and available before cutoff')
        last=a;last_end=end
        for k in ['b','T','q']:
            if type(h[k]) not in (int,float) or not np.isfinite(h[k]):raise ValueError('history declarations require finite numbers')
        if not (.6<=h['b']<=7 and h['T'] in [60,90,120] and h['q'] in [1.5,3]):raise ValueError('historical task outside supported family')
        ref=np.asarray(h['reference_kw'],float);power=np.asarray(h['measured_kw'],float)
        if ref.shape!=(120,) or power.shape!=(120,) or not np.isfinite(np.r_[ref,power]).all():raise ValueError('complete 120-bin finite history required')
        if np.any(power<-1e-8) or np.any(power>7.2+1e-8) or not np.allclose(ref,h['b']*(np.arange(120)<h['T']),atol=1e-8,rtol=0):raise ValueError('history AC/reference mismatch')
        if abs(power.sum()/60-h['b']*h['T']/60)>1e-8:raise ValueError('history recovery/energy outside ideal task family')
        # Accept only the frozen ideal template family used in this first study.
        reduction=(ref[:30]-power[:30])/h['q'];family=np.vstack([np.zeros(30),templates()])
        if np.min(np.max(abs(family-reduction),axis=1))>1e-8:raise ValueError('history shape outside ideal task family')
        if np.max(abs(power[30:]-((h['b']+np.sum(ref[:30]-power[:30])/60/(h['T']/60-.5))*(np.arange(30,120)<h['T']))))>1e-8:raise ValueError('history recovery shape mismatch')
        refs.append(ref);powers.append(power);amplitudes.append(h['q'])
    return None if len(records)<3 else extract_one(refs,powers,amplitudes)

def predict_with_history(case):
    try:
        case=copy.deepcopy(case);h=histories(case);c=case['current'];original=safe_b2(c)
        if original['status']=='unavailable':return dict(original,interface_version=VERSION)
        if original['status']=='blocked':return dict(original,history_method='policy_block',interface_version=VERSION)
        if not -.4<=c['reference']<=1.8:raise ValueError('current reference outside new history study domain')
        o=physical({k:np.array([c[k]]) for k in REQUIRED});bp=base_forecast(o);X=current(o,bp)
        m=joblib.load(BASE/'models.joblib')[0]
        import json
        selected=json.loads((BASE/'selection.json').read_text(encoding='utf-8'))['selected'][0]
        method=selected if h is not None else 0
        p=predict(m,X,np.zeros((1,6)) if h is None else h['summary'][None],np.zeros((1,90)) if h is None else h['raw'][None],method)[0]
        pa=1-p[0];states=p[1:]/pa;path=c['q']*(p[1:]@templates());result=dict(original)
        result.update(interface_version=VERSION,history_method=['C0','C1','C2','C3'][method],history_count=len(case.get('history',[])),cold_start=h is None,
          six_outcome_probabilities=p.tolist(),acceptance_probability=float(pa),conditional_service_probability=float(states[:2].sum()),service30_v1_probability=float(p[1:3].sum()),
          expected_delivery_kw=float(path.mean()),expected_delivery_kwh=float(path.sum()/60),expected_event_charging_kw=(c['b']-path).tolist(),expected_post_charging_kw=float(c['b']+path.sum()/60/(c['T']/60-.5)),
          conditional_reach90_probability=float(states[:4].sum()),conditional_expected_cumulative90_min=float(states@np.array([30,28,25,15,0])),conditional_expected_continuous90_min=float(states@np.array([30,28,25,15,0])),
          conditional_first_reach_min=float(states@np.array([0,2,5,0,0])/states[:4].sum()),conditional_early_exit_probability=float(states[3]),
          default_execution='history_six_outcome',evidence='new synthetic exact-meter single-EV family; optional completed-history model, not real reliability',
          model_sha=sha(BASE/'models.joblib'),model_replicate=0,population='pooled_new_three_regimes',information_cutoff=case['information_cutoff'])
        for s,prob in zip(result['dynamic_scenarios'],states):s['conditional_probability']=float(prob)
        return result
    except (ValueError,KeyError,TypeError,OverflowError) as e:return dict(status='unavailable',reason=str(e),committed_kw=None,interface_version=VERSION)
