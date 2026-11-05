"""Task-level calibrated response evidence, separate from measured outcomes.

Rank calibration uses independent declared non-event user blocks. It does not
identify an individual counterfactual, change duration/eta, or authorize action.
"""
from dataclasses import dataclass
from pathlib import Path
import hashlib,json,math
from dataclasses import asdict
import numpy as np
from .contracts import VERSION,SCHEMA,number,identifier,task_contract

SCHEMA_CAL='b1.ev-event-calibration.v1'
LENGTHS=(1,3,5,10,15,30)
VALIDITY='rank interpretation requires exchangeable calibration/test user blocks and same block size; not certified under distribution shift'
SCORE_DEFINITION='max window fitted reduction sum/sqrt(length), lengths1/3/5/10/15/30; max repeated events per original user'


def _json(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)


def _read_json(value):
    def pairs(items):
        result={}
        for k,v in items:
            if k in result:raise ValueError('duplicate JSON field: '+k)
            result[k]=v
        return result
    return json.loads(value,object_pairs_hook=pairs)


def _event(event):
    if not isinstance(event,dict) or event.get('schema_version')!=SCHEMA or event.get('algorithm_version')!=VERSION or event.get('status')!='ok':
        raise ValueError('successful complete B1 event required; no unlabelled fallback calibration')
    task=task_contract(event.get('task'));p=event.get('process')
    if not isinstance(p,dict) or p.get('status')!=event['status'] or p.get('task_id')!=task['task_id']:
        raise ValueError('process identity/status mismatch')
    profile=p.get('analysis_profile');ref=event.get('reference')
    if not isinstance(profile,dict) or not isinstance(ref,dict):raise ValueError('bound analysis profile and reference required')
    W=task['end_min']-task['start_min'];q=task['request_kw']
    delta=number(p.get('selection_evidence',{}).get('meter_delta_min'),'meter delta')
    if not np.isclose(W,30,atol=1e-9,rtol=0) or not np.isclose(delta,1.,atol=1e-9,rtol=0):
        raise ValueError('this calibrated score supports complete30min/1min tasks only')
    for field in ('task_duration_min','request_kw'):
        expected=W if field=='task_duration_min' else q
        if not np.isclose(number(p.get(field),field),expected,atol=1e-9,rtol=0):raise ValueError('process task mismatch')
    pre=number(profile.get('observation_pre_min'),'pre');post=number(profile.get('observation_post_min'),'post')
    if pre<0 or post<0 or not np.isclose(pre,round(pre),atol=1e-9,rtol=0) or not np.isclose(post,round(post),atol=1e-9,rtol=0):raise ValueError('complete integer observation windows required')
    raw=np.asarray(p.get('reduction_interval_kw'),dtype=object)
    if raw.ndim!=1 or len(raw)!=round(pre+W+post):raise ValueError('complete fitted interval curve required')
    curve=np.asarray([number(v,'reduction interval') for v in raw]);use=curve[round(pre):round(pre+W)]
    measured=number(p.get('features',{}).get('selected_curve',{}).get('cumulative_response_seconds'),'measured duration')
    expected=float(np.sum(use>=number(profile.get('onset_fraction'),'onset')*q)*60)
    if not np.isclose(measured,expected,atol=1e-8,rtol=0):raise ValueError('duration inconsistent with fitted curve')
    if ref.get('reference_status') not in ('available','provided') or number(ref.get('available_at_min'),'reference availability')>task['notice_min']+1e-9:
        raise ValueError('valid pre-notice reference required')
    refmodel=ref.get('model_id')
    if refmodel is not None:identifier(refmodel,'reference model ID')
    elif ref.get('reference_status')!='provided':raise ValueError('predicted reference model ID required')
    refmethod=identifier(ref.get('method'),'reference method')
    signature=dict(duration=W,q_kw=q,meter_min=delta,profile=profile,process_method=identifier(p.get('method'),'process method'),
        process_policy=p.get('selection_evidence',{}).get('policy'),reference_model_id=refmodel,
        notice_lead_min=task['start_min']-task['notice_min'],
        request_to_sigma=number(p.get('selection_evidence',{}).get('request_to_declared_meter_sigma_ratio'),'request/sigma'))
    _json(signature)
    return task,signature,refmethod,use,measured


def event_scan_score(event):
    """One event statistic: scan all declared windows; calibration covers scan."""
    task,signature,method,y,measured=_event(event)
    cumulative=np.r_[0.,np.cumsum(y)]
    candidates=[]
    for m in LENGTHS:
        values=(cumulative[m:]-cumulative[:-m])/math.sqrt(m)
        j=int(np.argmax(values));candidates.append((float(values[j]),m,j))
    value,m,j=max(candidates)
    return dict(score=max(0.,value),window_length_min=m,window_start_min=j,
        unit='kW*sqrt(min)',lengths_min=list(LENGTHS),measured_cumulative_seconds=measured,
        task_id=task['task_id'])


@dataclass(frozen=True)
class EVEventCalibration:
    payload_json: str
    sha256: str


def _payload(model):
    if not isinstance(model,EVEventCalibration) or not isinstance(model.payload_json,str) or not isinstance(model.sha256,str):raise ValueError('EVEventCalibration with string payload/checksum required')
    if hashlib.sha256(model.payload_json.encode('utf-8')).hexdigest()!=model.sha256:raise ValueError('calibration checksum mismatch')
    p=_read_json(model.payload_json)
    expected={'schema','alpha','cutoff_min','reference_policy_id','signature','reference_methods','users','events_per_user','user_max_scores','rank','upper_score_threshold','ledger','score_definition','validity','nuisance_or_reference_uncertainty_separately_identified','changes_measured_outcomes'}
    if not isinstance(p,dict) or set(p)!=expected or p.get('schema')!=SCHEMA_CAL:raise ValueError('calibration schema/fields mismatch')
    _json(p)
    alpha=number(p.get('alpha'),'alpha');cutoff=number(p.get('cutoff_min'),'cutoff')
    if not 0<alpha<1:raise ValueError('alpha outside(0,1)')
    users=p.get('users');scores=p.get('user_max_scores')
    if not isinstance(users,list) or not isinstance(scores,list) or len(users)!=len(scores) or len(users)<2:raise ValueError('unique calibration user blocks required')
    for u in users:identifier(u,'calibration user')
    if users!=sorted(set(users)):raise ValueError('sorted unique original users required')
    a=np.asarray([number(v,'calibration score') for v in scores])
    if np.any(a<0) or np.any(np.diff(a)<0):raise ValueError('nonnegative sorted calibration scores required')
    if type(p.get('events_per_user')) is not int or p['events_per_user']<1:raise ValueError('balanced calibration block size required')
    if type(p.get('rank')) is not int or p.get('rank')!=math.ceil((len(a)+1)*(1-alpha)):raise ValueError('invalid finite rank')
    if not isinstance(p.get('signature'),dict) or not isinstance(p.get('reference_methods'),list) or not p['reference_methods']:raise ValueError('calibration signature required')
    sig=p['signature']
    if set(sig)!={'duration','q_kw','meter_min','profile','process_method','process_policy','reference_model_id','request_to_sigma','notice_lead_min'}:raise ValueError('invalid signature fields')
    for name in ('duration','q_kw','meter_min','request_to_sigma','notice_lead_min'):
        if number(sig[name],'signature.'+name)<=0:raise ValueError('positive signature values required')
    if sig['duration']!=30. or sig['meter_min']!=1.:raise ValueError('unsupported calibrated task')
    identifier(sig['process_method'],'process method');identifier(sig['process_policy'],'process policy')
    if sig['reference_model_id'] is not None:identifier(sig['reference_model_id'],'reference model')
    from .resources.ev import ev_config
    if asdict(ev_config(sig['profile']))!=sig['profile']:raise ValueError('invalid profile')
    for method in p['reference_methods']:identifier(method,'reference method')
    if p['reference_methods']!=sorted(set(p['reference_methods'])):raise ValueError('unique reference methods required')
    ledger=p['ledger'];blocks={};tasks=set();physical={}
    fields={'task_id','user_id','meter_id','available_min','input_digest','score','start_min','end_min','observation_start_min','observation_end_min'}
    if not isinstance(ledger,list):raise ValueError('calibration ledger required')
    for row in ledger:
        if not isinstance(row,dict) or set(row)!=fields:raise ValueError('invalid calibration ledger fields')
        for key in ('task_id','user_id','meter_id'):identifier(row[key],key)
        if row['task_id'] in tasks:raise ValueError('duplicate calibration ledger task')
        tasks.add(row['task_id']);available=number(row['available_min'],'label availability')
        start=number(row['start_min'],'start');end=number(row['end_min'],'end')
        obsstart=number(row['observation_start_min'],'observation start');obsend=number(row['observation_end_min'],'observation end')
        if end-start!=sig['duration'] or obsstart!=start-sig['profile']['observation_pre_min'] or obsend!=end+sig['profile']['observation_post_min'] or not obsend<=available<=cutoff:raise ValueError('invalid calibration ledger time')
        if not isinstance(row['input_digest'],str) or len(row['input_digest'])!=64 or any(c not in '0123456789abcdef' for c in row['input_digest']):raise ValueError('invalid input digest')
        old=physical.setdefault(row['meter_id'],[])
        if any(abs(start-a)<=1e-9 and abs(end-b)<=1e-9 for a,b in old):raise ValueError('duplicate physical ledger task')
        old.append((start,end));score=number(row['score'],'ledger score')
        if score<0:raise ValueError('negative scan score')
        blocks.setdefault(row['user_id'],[]).append(score)
    if sorted(blocks)!=users or any(len(v)!=p['events_per_user'] for v in blocks.values()) or sorted(max(v) for v in blocks.values())!=scores:raise ValueError('scores/user blocks not bound to ledger')
    threshold=p['upper_score_threshold'];expected_threshold=scores[p['rank']-1] if p['rank']<=len(scores) else None
    if expected_threshold is None:
        if threshold is not None:raise ValueError('unresolved threshold must be null')
    elif number(threshold,'upper threshold')!=expected_threshold:raise ValueError('threshold differs from finite rank')
    if p['validity']!=VALIDITY or p['score_definition']!=SCORE_DEFINITION or p['changes_measured_outcomes'] is not False or p['nuisance_or_reference_uncertainty_separately_identified'] is not False:raise ValueError('invalid calibration interpretation flags')
    identifier(p.get('reference_policy_id'),'reference policy')
    return p


def fit_ev_event_calibration(events,calibration_records,*,calibration_cutoff_min,reference_policy_id,alpha=.05):
    """Fit ranks on explicitly declared, already completed, non-dispatched tasks."""
    cutoff=number(calibration_cutoff_min,'calibration cutoff');alpha=number(alpha,'alpha');identifier(reference_policy_id,'reference policy')
    if not 0<alpha<1 or not isinstance(events,(list,tuple)) or not events or not isinstance(calibration_records,(list,tuple)) or len(events)!=len(calibration_records):raise ValueError('matching nonempty event/record lists and valid alpha required')
    from .api import _prepare_event
    blocks={};seen=set();windows={};signature=None;methods=set();ledger=[]
    for event,record in zip(events,calibration_records):
        task,sig,method,_,_= _event(event)
        if not isinstance(record,dict) or record.get('non_event') is not True or record.get('task_dispatched') is not False:
            raise ValueError('explicit non_event=True and task_dispatched=False required; do not select observed nonresponders')
        context=_prepare_event(record)
        if context['task']!=task:raise ValueError('non-event record task does not bind event')
        sigma=number(record.get('noise_sigma_kw'),'calibration record sigma')
        if sigma<=0 or not np.isclose(sig['request_to_sigma'],task['request_kw']/sigma,atol=1e-10,rtol=0):raise ValueError('noise declaration not bound to process')
        if _json(context['reference'])!=_json(event['reference']):raise ValueError('reference metadata not bound to calibration source')
        from .resources.ev import ev_config
        if asdict(ev_config(record.get('ev_config')))!=sig['profile']:raise ValueError('profile not bound to calibration record')
        digest=hashlib.sha256(json.dumps(dict(task=context['task'],starts=context['s'].tolist(),ends=context['e'].tolist(),power=context['p'].tolist(),reference=context['b'].tolist()),sort_keys=True).encode()).hexdigest()
        if digest!=event.get('input_digest'):raise ValueError('calibration power/reference not bound to actual event')
        available=number(record.get('observed_available_at_min'),'observed availability')
        if available<float(context['e'][-1])-1e-9 or available>cutoff+1e-9:raise ValueError('all calibration labels must be complete by cutoff')
        if task['task_id'] in seen:raise ValueError('duplicate calibration event')
        seen.add(task['task_id']);key=(task['meter_id'],task['start_min'],task['end_min'])
        if any(key[0]==a and abs(key[1]-b)<=1e-9 and abs(key[2]-c)<=1e-9 for a,b,c in windows):raise ValueError('renamed duplicate physical event')
        windows[key]=True
        if signature is None:signature=sig
        elif _json(signature)!=_json(sig):raise ValueError('one process/reference/profile/noise/task signature per calibrator required')
        score=event_scan_score(event)['score'];blocks.setdefault(task['user_id'],[]).append(score);methods.add(method)
        ledger.append(dict(task_id=task['task_id'],user_id=task['user_id'],meter_id=task['meter_id'],available_min=available,input_digest=digest,score=score,start_min=task['start_min'],end_min=task['end_min'],observation_start_min=float(context['s'][0]),observation_end_min=float(context['e'][-1])))
    counts={len(v) for v in blocks.values()}
    if len(blocks)<2 or len(counts)!=1:raise ValueError('at least two balanced original-user blocks required')
    scores=sorted(max(v) for v in blocks.values());rank=math.ceil((len(scores)+1)*(1-alpha))
    p=dict(schema=SCHEMA_CAL,alpha=alpha,cutoff_min=cutoff,reference_policy_id=reference_policy_id,signature=signature,
        reference_methods=sorted(methods),users=sorted(blocks),events_per_user=counts.pop(),user_max_scores=scores,rank=rank,
        upper_score_threshold=scores[rank-1] if rank<=len(scores) else None,ledger=ledger,
        score_definition=SCORE_DEFINITION,
        validity=VALIDITY,
        nuisance_or_reference_uncertainty_separately_identified=False,changes_measured_outcomes=False)
    payload=_json(p);model=EVEventCalibration(payload,hashlib.sha256(payload.encode()).hexdigest());_payload(model);return model


def assess_ev_event_evidence(event,model,*,reference_policy_id):
    """Return evidence/inconclusive; never set an outcome to zero or drop a row."""
    p=_payload(model);task,sig,method,_,measured=_event(event)
    if reference_policy_id!=p['reference_policy_id'] or _json(sig)!=_json(p['signature']) or method not in p['reference_methods']:
        raise ValueError('event does not match calibrated reference/process/task/profile/noise policy')
    if task['notice_min']<=p['cutoff_min']+1e-9:raise ValueError('calibration must complete before query notice')
    if task['user_id'] in p['users']:raise ValueError('calibration users cannot be reused as independent queries')
    scan=event_scan_score(event);scores=np.asarray(p['user_max_scores']);rankp=float((1+np.sum(scores>=scan['score']))/(len(scores)+1))
    enough=p['rank']<=len(scores)
    return dict(schema='b1.ev-response-evidence.v1',status='assessed' if enough else 'insufficient_calibration',
        decision='evidence' if enough and rankp<=p['alpha'] else 'inconclusive',rank_p_value=rankp,alpha=p['alpha'],
        score=scan,calibration_id=model.sha256,reference_policy_id=reference_policy_id,
        calibration_users=len(scores),calibration_events_per_user=p['events_per_user'],
        measured_cumulative_seconds=measured,measured_duration_overwritten=False,raw_eta_overwritten=False,
        non_rejection_means_no_response=False,physical_counterfactual_identified=False,
        inference_scope=p['validity'],use_for_total_effect='keep all supplied events, including inconclusive; do not condition on evidence')


def save_ev_event_calibration(model,path):
    _payload(model)
    with Path(path).open('x',encoding='utf-8') as f:f.write(_json(dict(payload_json=model.payload_json,sha256=model.sha256)))


def load_ev_event_calibration(path):
    path=Path(path)
    if path.stat().st_size>10_000_000:raise ValueError('oversized calibration artifact')
    value=_read_json(path.read_text(encoding='utf-8'))
    if not isinstance(value,dict) or set(value)!={'payload_json','sha256'}:raise ValueError('invalid calibration envelope')
    model=EVEventCalibration(**value);_payload(model);return model
