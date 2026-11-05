"""Independent closure of initial findings against a newly identified source."""
import os
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[name]='1'
import copy, json, hashlib, math
from dataclasses import asdict
from audit_initial import (ROOT,OUT,synthetic as initial_fixture,attempt,frozen,dump,
    _prepare_event,fit_ev_event_calibration,assess_ev_event_evidence,event_scan_score,
    EVEventCalibration,_payload,np)
from b1_algorithm.resources.ev import EVAnalysisConfig
from b1_algorithm.response_evidence import load_ev_event_calibration


def fixture(i,user,level=.01,start=None):
    event,record=initial_fixture(i,user,level,start)
    event['reference']=_prepare_event(record)['reference']
    event['process']['analysis_profile']=asdict(EVAnalysisConfig())
    return event,record


def main():
    source_sha=hashlib.sha256((ROOT/'B1算法/b1_algorithm/response_evidence.py').read_bytes()).hexdigest()
    pairs=[fixture(i,'u'+str(i//2),(i+1)/100.) for i in range(4)]
    events=[e for e,r in pairs];records=[r for e,r in pairs]
    model=fit_ev_event_calibration(events,records,calibration_cutoff_min=1400.,reference_policy_id='policy',alpha=.5)
    p=json.loads(model.payload_json)
    query,_=fixture(20,'new',.3,start=6000.)
    closed={}
    for key,value in [('changes_measured_outcomes',True),('nuisance_or_reference_uncertainty_separately_identified',True),
                       ('upper_score_threshold',-1000.),('ledger',[]),('score_definition',False),('validity',True),
                       ('unexpected_extra_field',{'untrusted':True})]:
        bad=copy.deepcopy(p);bad[key]=value
        closed['payload_'+key]=attempt(lambda bad=bad:_payload(frozen(bad)))
    for name,mutate in [
        ('scores_not_from_ledger',lambda p:p.update(user_max_scores=[0.,0.])),
        ('missing_ledger',lambda p:p.pop('ledger')),
        ('bool_signature_numeric',lambda p:p['signature']['profile'].update(onset_fraction=True)),
        ('empty_signature',lambda p:p.update(signature={})),
        ('bool_rank',lambda p:p.update(rank=True)),
        ('bool_events_per_user',lambda p:p.update(events_per_user=True)),
        ('ledger_future_available',lambda p:p['ledger'][0].update(available_min=1401.)),
        ('ledger_duplicate_task',lambda p:p['ledger'][0].update(task_id=p['ledger'][1]['task_id'])),
        ('ledger_negative_score',lambda p:p['ledger'][0].update(score=-1.)),
        ('bool_ledger_score',lambda p:p['ledger'][0].update(score=True)),
        ('wrong_model_class',lambda p:None),
    ]:
        bad=copy.deepcopy(p);mutate(bad)
        closed[name]=attempt(lambda bad=bad,name=name:_payload(object() if name=='wrong_model_class' else frozen(bad)))
    for field,value in [('model_id','different-model'),('method','different-method'),('available_at_min',900.)]:
        bad=copy.deepcopy(events)
        for e in bad:e['reference'][field]=value
        closed['reference_'+field]=attempt(lambda bad=bad:fit_ev_event_calibration(bad,records,calibration_cutoff_min=1400.,reference_policy_id='policy',alpha=.5))
    renamed=copy.deepcopy(query);renamed['task']['notice_min']=5940.;renamed['reference']['available_at_min']=5940.
    closed['query_different_notice_lead']=attempt(lambda:assess_ev_event_evidence(renamed,model,reference_policy_id='policy'))
    de,dr=fixture(99,'u0',.01,start=1000.+1e-10)
    closed['subtolerance_duplicate_physical_window']=attempt(lambda:fit_ev_event_calibration([events[0],de,events[2],events[3]],
        [records[0],dr,records[2],records[3]],calibration_cutoff_min=1400.,reference_policy_id='policy',alpha=.5))
    changed_profile=copy.deepcopy(records)
    for r in changed_profile:r['ev_config']=dict(onset_fraction=.2)
    closed['record_profile_source_mismatch']=attempt(lambda:fit_ev_event_calibration(events,changed_profile,calibration_cutoff_min=1400.,reference_policy_id='policy',alpha=.5))

    mathchecks=[]
    assert p['events_per_user']==2 and len(p['users'])==len(p['user_max_scores'])==2
    assert np.allclose(p['user_max_scores'],[.02*math.sqrt(30),.04*math.sqrt(30)],atol=1e-14,rtol=0)
    mathchecks.append('two original-user maxima preserve full repeated-event block')
    y=np.array([.2,-.3,.1,.4,-.1,.1]*5)
    e=copy.deepcopy(query);e['process']['reduction_interval_kw']=[0.]*15+y.tolist()+[0.]*15
    e['process']['features']['selected_curve']['cumulative_response_seconds']=float(np.sum(y>=.15)*60)
    direct=max(0.,max(sum(y[j:j+m])/math.sqrt(m) for m in (1,3,5,10,15,30) for j in range(31-m)))
    assert abs(event_scan_score(e)['score']-direct)<1e-14
    mathchecks.append('all signed contiguous task windows match brute force')
    before=copy.deepcopy(query);decision=assess_ev_event_evidence(query,model,reference_policy_id='policy')
    assert query==before and decision['decision']=='evidence'
    assert decision['measured_cumulative_seconds']==1800. and decision['non_rejection_means_no_response'] is False
    mathchecks.append('positive evidence keeps measured duration and original event')
    # With two calibration users, alpha .05 has no resolvable rejection rank.
    insufficient=fit_ev_event_calibration(events,records,calibration_cutoff_min=1400.,reference_policy_id='policy',alpha=.05)
    result=assess_ev_event_evidence(query,insufficient,reference_policy_id='policy')
    assert result['status']=='insufficient_calibration' and result['decision']=='inconclusive'
    mathchecks.append('insufficient user count stays explicitly inconclusive')

    additional={}
    bad_records=copy.deepcopy(records)
    for r in bad_records:r['noise_sigma_kw']=.1
    additional['record_noise_source_mismatch']=attempt(lambda:fit_ev_event_calibration(events,bad_records,calibration_cutoff_min=1400.,reference_policy_id='policy',alpha=.5))
    bad_records=copy.deepcopy(records)
    for r in bad_records:r['noise_sigma_kw']=True
    additional['record_bool_noise']=attempt(lambda:fit_ev_event_calibration(events,bad_records,calibration_cutoff_min=1400.,reference_policy_id='policy',alpha=.5))
    # A duplicate field uses different first/last values; standard json silently
    # discards the first declaration, despite a valid checksum for the raw bytes.
    duplicate=model.payload_json[:-1]+',"alpha":0.5}'
    dm=EVEventCalibration(duplicate,hashlib.sha256(duplicate.encode()).hexdigest())
    additional['duplicate_payload_field']=attempt(lambda:_payload(dm))
    malformed=OUT/'round2_duplicate_envelope.json'
    malformed.write_text('{"payload_json":"wrong","payload_json":'+json.dumps(model.payload_json)+',"sha256":'+json.dumps(model.sha256)+'}',encoding='utf-8')
    additional['duplicate_envelope_field']=attempt(lambda:load_ev_event_calibration(malformed))

    receipt=dict(source_sha256=source_sha,closed_checks=closed,mathematical_checks=mathchecks,additional=additional,
        closure_passed=all(not x['accepted'] for x in closed.values()),
        new_accepted=[name for name,x in additional.items() if x['accepted']])
    dump(OUT/'round2_receipt.json',receipt)
    print(json.dumps(dict(source_sha256=source_sha,closure_passed=receipt['closure_passed'],closed_checks=len(closed),math_checks=len(mathchecks),new_accepted=receipt['new_accepted'])))


if __name__=='__main__':main()
