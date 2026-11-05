"""Independent mathematical and contract audit; never calls or changes fitting code."""
import os
for name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[name] = '1'
import sys, json, hashlib, copy, math
from pathlib import Path
import numpy as np

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[3]
sys.path.insert(0,str(ROOT/'B1算法'))
from b1_algorithm.contracts import VERSION, SCHEMA, task_contract
from b1_algorithm.api import _prepare_event
from b1_algorithm.response_evidence import (event_scan_score, fit_ev_event_calibration,
    assess_ev_event_evidence, EVEventCalibration, _payload)


def dump(path,value):
    with path.open('x',encoding='utf-8') as f:
        json.dump(value,f,ensure_ascii=False,indent=2,allow_nan=False)


def synthetic(i, user, score_level=.01, start=None, model_id='model-A'):
    start=float(1000+100*i if start is None else start)
    task=dict(task_id='t'+str(i),user_id=user,meter_id='m'+user,resource_type='EV',
              start_min=start,end_min=start+30,request_kw=1.5,notice_min=start-15,
              task_pre_treatment=True)
    starts=start+np.arange(-15.,45.)
    reference=dict(reference_status='available',task_id=task['task_id'],user_id=user,meter_id=task['meter_id'],
        task_start_min=start,task_end_min=start+30,request_kw=1.5,notice_min=start-15,
        starts_min=starts.tolist(),ends_min=(starts+1).tolist(),reference_kw=[3.]*60,
        available_at_min=start-15,method='method-A',model_id=model_id)
    curve=np.r_[np.zeros(15),np.full(30,score_level),np.zeros(15)]
    record=dict(task=task,starts_min=starts.tolist(),ends_min=(starts+1).tolist(),
        power_kw=(3.-curve).tolist(),reference=reference,noise_sigma_kw=.05,
        non_event=True,task_dispatched=False,observed_available_at_min=start+45)
    context=_prepare_event(record)
    digest=hashlib.sha256(json.dumps(dict(task=context['task'],starts=context['s'].tolist(),ends=context['e'].tolist(),
        power=context['p'].tolist(),reference=context['b'].tolist()),sort_keys=True).encode()).hexdigest()
    event=dict(schema_version=SCHEMA,algorithm_version=VERSION,status='ok',task=task_contract(task),
        reference=dict(reference_status='available',available_at_min=start-15,method='method-A',model_id=model_id),
        input_digest=digest,process=dict(status='ok',task_id=task['task_id'],task_duration_min=30.,request_kw=1.5,
            method='cpop',analysis_profile=dict(observation_pre_min=15.,observation_post_min=15.,onset_fraction=.1),
            selection_evidence=dict(meter_delta_min=1.,policy='fixed-cpop',request_to_declared_meter_sigma_ratio=30.),
            reduction_interval_kw=curve.tolist(),features=dict(selected_curve=dict(cumulative_response_seconds=float(np.sum(curve[15:45]>=.15)*60)))))
    return event,record


def attempt(fn):
    try:
        value=fn()
        return dict(accepted=True,value=value if isinstance(value,(str,float,int,bool,list,dict,type(None))) else str(type(value)))
    except Exception as exc:
        return dict(accepted=False,error_type=type(exc).__name__,message=str(exc))


def frozen(payload):
    raw=json.dumps(payload,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)
    return EVEventCalibration(raw,hashlib.sha256(raw.encode()).hexdigest())


def main():
    source_sha=hashlib.sha256((ROOT/'B1算法/b1_algorithm/response_evidence.py').read_bytes()).hexdigest()
    pairs=[synthetic(i,'u'+str(i//2),score_level=(i+1)/100.) for i in range(4)]
    events=[x[0] for x in pairs];records=[x[1] for x in pairs]
    model=fit_ev_event_calibration(events,records,calibration_cutoff_min=1400.,reference_policy_id='policy',alpha=.5)
    p=json.loads(model.payload_json)
    expected_scores=[.02*math.sqrt(30),.04*math.sqrt(30)]
    assert np.allclose(p['user_max_scores'],expected_scores,rtol=0,atol=1e-14)
    assert p['events_per_user']==2 and len(p['user_max_scores'])==2
    mathematical_checks=['two events collapse to one max per user','rank uses two users, not four rows']

    # Brute force all allowed intervals independently; signed reductions remain signed.
    y=np.array([.2,-.3,.1,.4,-.1,.1]*5)
    scan_event=copy.deepcopy(events[0]);scan_event['process']['reduction_interval_kw']=[0.]*15+y.tolist()+[0.]*15
    scan_event['process']['features']['selected_curve']['cumulative_response_seconds']=float(np.sum(y>=.15)*60)
    direct=max(0.,max(sum(y[j:j+m])/math.sqrt(m) for m in (1,3,5,10,15,30) for j in range(31-m)))
    assert np.isclose(event_scan_score(scan_event)['score'],direct,rtol=0,atol=1e-14)
    mathematical_checks.append('full task scan agrees with direct signed sums')
    outside=copy.deepcopy(scan_event);outside['process']['reduction_interval_kw'][:15]=[1000.]*15
    outside['process']['reduction_interval_kw'][45:]=[1000.]*15
    assert event_scan_score(outside)['score']==event_scan_score(scan_event)['score']
    mathematical_checks.append('pre and post windows excluded from scan')

    # Exhaust all ranks of a 96-user calibration list, including duplicated ties.
    scores=np.repeat(np.arange(24,dtype=float),4)
    rank=math.ceil(97*.95);threshold=scores[rank-1]
    for score in np.arange(-.5,24,.5):
        probability=(1+sum(v>=score for v in scores))/97
        assert (probability<=.05)==(score>threshold)
    assert (1+sum(v>=threshold for v in scores))/97>.05
    mathematical_checks.extend(['96-user alpha .05 finite rank is 93','ties at threshold are inconclusive','rank p and strict score threshold agree'])
    query,_=synthetic(20,'new-user',score_level=.3,start=6000.)
    before=copy.deepcopy(query)
    assessed=assess_ev_event_evidence(query,model,reference_policy_id='policy')
    assert query==before
    assert assessed['measured_cumulative_seconds']==query['process']['features']['selected_curve']['cumulative_response_seconds']
    assert assessed['measured_duration_overwritten'] is False and assessed['raw_eta_overwritten'] is False
    mathematical_checks.append('assessment preserves supplied event and duration')

    hostile={}
    for key,value in [('changes_measured_outcomes',True),('nuisance_or_reference_uncertainty_separately_identified',True),
                       ('upper_score_threshold',-1000.),('ledger',[]),('score_definition',False),('validity',True),
                       ('unexpected_extra_field',{'untrusted':True})]:
        bad=copy.deepcopy(p);bad[key]=value
        hostile['payload_'+key]=attempt(lambda bad=bad:_payload(frozen(bad)))
    bad=copy.deepcopy(p);bad['user_max_scores']=[0.,0.]
    hostile['scores_not_from_ledger']=attempt(lambda:assess_ev_event_evidence(query,frozen(bad),reference_policy_id='policy'))
    bad=copy.deepcopy(p);del bad['ledger']
    hostile['missing_ledger']=attempt(lambda:_payload(frozen(bad)))
    bad=copy.deepcopy(p);bad['signature']['profile']['onset_fraction']=True
    hostile['bool_signature_numeric']=attempt(lambda:_payload(frozen(bad)))
    bad=copy.deepcopy(p);bad['signature']={}
    hostile['empty_signature']=attempt(lambda:_payload(frozen(bad)))

    # Reference summaries must agree with the original bound record, not just vectors.
    relabelled=copy.deepcopy(events)
    for e in relabelled:
        e['reference']['model_id']='different-model'
        e['reference']['method']='different-method'
    hostile['relabelled_reference_metadata']=attempt(lambda:fit_ev_event_calibration(relabelled,records,
        calibration_cutoff_min=1400.,reference_policy_id='policy',alpha=.5))

    # The process signature currently omits notice lead.
    shifted_notice=copy.deepcopy(query);shifted_notice['task']['notice_min']=shifted_notice['task']['start_min']-60.
    shifted_notice['reference']['available_at_min']=shifted_notice['task']['notice_min']
    hostile['query_different_notice_lead']=attempt(lambda:assess_ev_event_evidence(shifted_notice,model,reference_policy_id='policy'))

    # A renamed same meter-window with sub-tolerance timestamp perturbation is one event.
    dupe_event,dupe_record=synthetic(99,'u0',score_level=.01,start=1000.+1e-10)
    duplicated_events=[events[0],dupe_event,events[2],events[3]]
    duplicated_records=[records[0],dupe_record,records[2],records[3]]
    hostile['subtolerance_duplicate_physical_window']=attempt(lambda:fit_ev_event_calibration(duplicated_events,duplicated_records,
        calibration_cutoff_min=1400.,reference_policy_id='policy',alpha=.5))

    receipt=dict(source_sha256=source_sha,mathematical_checks=mathematical_checks,
                 mathematical_check_count=len(mathematical_checks),hostile=hostile,
                 scope='synthetic contracts and exact rank/scan math only; no main data/native solver')
    dump(OUT/'initial_receipt.json',receipt)
    print(json.dumps(dict(source_sha256=source_sha,mathematical_checks=len(mathematical_checks),
                         accepted_hostile=[k for k,v in hostile.items() if v['accepted']]),ensure_ascii=False))


if __name__=='__main__':main()
