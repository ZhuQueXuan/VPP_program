import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
from pathlib import Path
import sys,json,hashlib,copy,math
import numpy as np
R=Path(__file__).resolve().parents[2];W=Path(__file__).parent;sys.path.insert(0,str(R/'B1算法'))
from b1_api import provided_reference
from b1_algorithm.api import _prepare_event,_finish_event
from b1_algorithm.process.api import prepare,_result
from b1_algorithm.response_evidence import *
checks=[]
def check(name,v):
    assert v,name
    checks.append(name)
def rejects(name,fn):
    try:fn()
    except (ValueError,TypeError,OSError):checks.append(name);return
    raise AssertionError(name)
def event(user,c,start=1000,eventidx=0):
    start=float(start+200*user+80*eventidx);s=start+np.arange(-15,45);e=s+1
    task=dict(task_id=f'null-u{user}-e{eventidx}',user_id=f'u{user}',meter_id=f'm{user}',start_min=start,end_min=start+30,notice_min=start-15,request_kw=1.5,task_pre_treatment=True)
    y=np.zeros(60);y[15:45]=c
    rec=dict(task=task,starts_min=s.tolist(),ends_min=e.tolist(),power_kw=(4-y).tolist(),noise_sigma_kw=.05,
        reference=provided_reference(task,s,e,np.full(60,4.),available_at_min=start-15),
        non_event=True,task_dispatched=False,observed_available_at_min=float(e[-1]))
    context=_prepare_event(rec);data=prepare(**context['request'])
    output=_result(data,y,'ok','functional_fixed_curve',None,dict(policy='control_only'))
    return _finish_event(context,output),rec
events=[];records=[]
for u in range(20):
    for j in range(2):
        a,b=event(u,.001*(u+1)*(j+1),eventidx=j);events.append(a);records.append(b)
model=fit_ev_event_calibration(events,records,calibration_cutoff_min=6000,reference_policy_id='fixed-control')
p=json.loads(model.payload_json)
check('one maximum per original user',len(p['user_max_scores'])==20 and p['events_per_user']==2)
check('rank finite n plus one',p['rank']==20)
check('hand user max scores',np.allclose(p['user_max_scores'],np.arange(1,21)*.002*np.sqrt(30),atol=1e-14,rtol=0))
q,_=event(99,.3,start=20000);before=copy.deepcopy(q)
a=assess_ev_event_evidence(q,model,reference_policy_id='fixed-control')
check('upper rank evidence',a['decision']=='evidence' and a['rank_p_value']==1/21)
check('outcome and curve immutable',q==before and a['measured_duration_overwritten'] is False and a['raw_eta_overwritten'] is False)
null,_=event(100,0.,start=20000)
check('ties conservative',assess_ev_event_evidence(null,model,reference_policy_id='fixed-control')['rank_p_value']==1.)
check('do not call inconclusive no response',assess_ev_event_evidence(null,model,reference_policy_id='fixed-control')['non_rejection_means_no_response'] is False)
# Exact exhaustive rank control over an exchangeable distinct-score fixture.
all_scores=np.arange(21,dtype=float)
reject_count=sum((1+sum(np.delete(all_scores,k)>=all_scores[k]))/21<=.05 for k in range(21))
check('exchangeable finite ranks reject only1of21',reject_count==1)
for u in (0,1,5):
    old,_=event(u,.3,start=20000)
    rejects('no calibration user reuse'+str(u),lambda old=old:assess_ev_event_evidence(old,model,reference_policy_id='fixed-control'))
early,_=event(90,.3,start=-20000)
rejects('cal label cannot be future',lambda:assess_ev_event_evidence(early,model,reference_policy_id='fixed-control'))
rejects('policy binding',lambda:assess_ev_event_evidence(q,model,reference_policy_id='other'))
bad=copy.deepcopy(q);bad['process']['analysis_profile']['onset_fraction']=.2
rejects('profile/duration binding',lambda:assess_ev_event_evidence(bad,model,reference_policy_id='fixed-control'))
bad=copy.deepcopy(q);bad['reference']['model_id']='other'
rejects('reference identity binding',lambda:assess_ev_event_evidence(bad,model,reference_policy_id='fixed-control'))
bad=copy.deepcopy(records);bad[0]['task_dispatched']=True
rejects('not selected observed nonresponders',lambda:fit_ev_event_calibration(events,bad,calibration_cutoff_min=6000,reference_policy_id='fixed-control'))
bad=copy.deepcopy(records);bad[0]['power_kw'][0]+=1
rejects('input digest binds calibration labels',lambda:fit_ev_event_calibration(events,bad,calibration_cutoff_min=6000,reference_policy_id='fixed-control'))
rejects('duplicates',lambda:fit_ev_event_calibration(events+[events[0]],records+[records[0]],calibration_cutoff_min=6000,reference_policy_id='fixed-control'))
rejects('cutoff',lambda:fit_ev_event_calibration(events,records,calibration_cutoff_min=2000,reference_policy_id='fixed-control'))
rejects('bool alpha',lambda:fit_ev_event_calibration(events,records,calibration_cutoff_min=6000,reference_policy_id='fixed-control',alpha=True))
small=fit_ev_event_calibration(events[:4],records[:4],calibration_cutoff_min=6000,reference_policy_id='fixed-control')
check('finite sample insufficient alpha resolution',assess_ev_event_evidence(q,small,reference_policy_id='fixed-control')['status']=='insufficient_calibration')
path=W/'control_calibration.json';save_ev_event_calibration(model,path)
check('JSON roundtrip exact',load_ev_event_calibration(path)==model)
rejects('refuse overwrite',lambda:save_ev_event_calibration(model,path))
rejects('payload wrong type',lambda:load_ev_event_calibration(W/'protocol.json'))
(W/'evidence_control_receipt.json').write_text(json.dumps(dict(passed=len(checks),checks=checks,mathematical_control_only=True),indent=2),encoding='utf-8')
print('passed',len(checks))
