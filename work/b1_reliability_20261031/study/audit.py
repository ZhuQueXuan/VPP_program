"""Independent read-only arithmetic/identity audit; no scientific fitting."""
from pathlib import Path
import json
import hashlib
import math
from collections import defaultdict
import numpy as np

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
DATA=ROOT/'data/B1_reliability_v1_20261031'
PATHS=(('old_cpop','old'),('old_ride_revised','old'),('new_cpop','new'),('new_ride_revised','new'))
LENGTHS=(1,3,5,10,15,30)


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def independent_score(event):
    # Direct window loops, without the implementation's cumsum or score helper.
    curve=event['process']['reduction_interval_kw'][15:45]
    return max(0.,max(math.fsum(curve[j:j+length])/math.sqrt(length)
        for length in LENGTHS for j in range(31-length)))


def main():
    if not (HERE/'test/receipt.json').is_file():raise RuntimeError('wait for phase1 complete')
    checks=0
    def ck(condition,why):
        nonlocal checks
        if not condition:raise AssertionError(why)
        checks+=1
    p=read(HERE.parent/'protocol.json');frozen=read(HERE/'freeze_candidate.json')
    for rel,expected in frozen['source_identity'].items():ck(sha(ROOT/rel)==expected,'frozen scientific source '+rel)
    ck(sha(HERE/'models/reliable_reference.json')==frozen['reliable_reference_sha256'],'reference artifact identity')
    for path,expected in frozen['calibration_models'].items():ck(sha(HERE/'models'/f'evidence_{path}.json')==expected,'calibration artifact identity '+path)
    model=read(HERE/'models/reliable_reference.json')['payload']
    ck(len(model['training_users'])==192 and len(model['training_records'])==384,'reference training split')
    ck(model['n_training_rows']==384*60,'non-event training horizon rows')
    cal_models={};cal_users=set()
    for path,kind in PATHS:
        envelope=read(HERE/'models'/f'evidence_{path}.json');payload=json.loads(envelope['payload_json'])
        ck(hashlib.sha256(envelope['payload_json'].encode()).hexdigest()==envelope['sha256'],'calibration checksum')
        events=read(HERE/'calibration/events'/f'{path}.json')
        records=read(HERE/'calibration/records'/f'{path}.json')
        blocks=defaultdict(list)
        for event,record,ledger in zip(events,records,payload['ledger']):
            ck(record['non_event'] is True and record['task_dispatched'] is False,'explicit undelivered calibration source')
            ck(event['status']=='ok','no raw fallback calibrated')
            digest=hashlib.sha256(json.dumps(dict(task=event['task'],starts=record['starts_min'],ends=record['ends_min'],
                power=record['power_kw'],reference=record['reference']['reference_kw']),sort_keys=True).encode()).hexdigest()
            ck(digest==event['input_digest']==ledger['input_digest'],'independent exact calibration binding')
            score=independent_score(event)
            ck(abs(score-ledger['score'])<1e-10,'independent calibration score')
            blocks[event['task']['user_id']].append(score)
            ck(record['observed_available_at_min']<=payload['cutoff_min'],'calibration complete')
        ck(len(events)==192 and len(blocks)==96 and all(len(v)==2 for v in blocks.values()),'96 original two-event user blocks')
        expected=sorted(max(v) for v in blocks.values())
        ck(np.allclose(expected,payload['user_max_scores'],atol=1e-10,rtol=0),'user maxima distribution')
        ck(payload['rank']==math.ceil(97*.95)==93,'finite-sample rank')
        cal_models[path]=payload;cal_users.update(payload['users'])
    summaries={};n_outputs=0;n_events=0;all_query_users=set()
    for phase,seeds,nusers,shift in (('validation',p['data']['validation_seeds'],32,4032000),('test',p['data']['test_seeds'],64,6048000)):
        counts=defaultdict(int)
        for seed in seeds:
            canonical=read(DATA/phase/f'{seed}_strong_facts.json')
            ck(len(canonical)==nusers*2,'block event count')
            users={f['task']['user_id'] for f in canonical};all_query_users.update(users)
            ck(len(users)==nusers and not users&cal_users and not users&set(model['training_users']),'training calibration query users separated')
            refs={k:read(HERE/phase/'references'/f'{seed}_{k}.json')['references'] for k in ('old','new')}
            for scenario in ('strong','weak','null'):
                facts=read(DATA/phase/f'{seed}_{scenario}_facts.json')
                truth=read(HERE/phase/'evaluator'/f'{seed}_{scenario}_truth.json')
                n_events+=len(facts)
                for index,(f,c,t) in enumerate(zip(facts,canonical,truth)):
                    user,event=divmod(index,2);task=f['task'];window=f['reference_window']
                    ck(task['start_min']==200000+180*user+20160*event+shift,'absolute task time shift')
                    ck(f['reference_window']==c['reference_window'] and f['historical_non_event']==c['historical_non_event'] and f['factor_record']==c['factor_record'],'paired declared conditions')
                    ck(max(window['pre_ends_min'])<=task['notice_min'],'legal pre-notice prefix')
                    ck(window['prior_available_min']<=task['notice_min'] and all(h['available_at_min']<task['notice_min'] for h in f['historical_non_event']),'legal historical labels')
                    ck(window['clock_hour']==(task['start_min']%1440)/60 and window['weekday']==int(task['start_min']//1440)%7,'whole-week calendar preserved')
                    factor=f['factor_record']
                    ck(factor['treatment_set_min']==task['notice_min'] and factor['available_at_min']['offered_incentive']==task['notice_min'] and factor['available_at_min']['deadline_slack']<task['notice_min'] and factor['state_as_of_min']['demand_urgency']<task['notice_min'],'factor clock and legal L/U')
                    r=np.asarray(t['true_reduction_kw'])[15:45]
                    ck(abs(float(r.sum()/45)-t['eta'])<1e-12,'independent truth integral')
                    ck(float(np.count_nonzero(r>=.1*t['q_kw'])*60)==t['cumulative_response_seconds'],'independent truth cumulative duration')
                    ck(np.allclose(np.asarray(f['power_kw']),np.asarray(t['true_reference_kw'])-np.asarray(t['true_reduction_kw'])+np.asarray(t['measurement_error_kw']),atol=1e-13,rtol=0),'factual natural response noise equation')
                    ck(t['threshold_positive']==(t['cumulative_response_seconds']>0),'true threshold-positive denominator')
                    if scenario=='null':ck(not t['physical_action'] and np.all(r==0),'physical null not original zero-effect mechanism')
                for path,kind in PATHS:
                    output=read(HERE/phase/'events'/f'{seed}_{scenario}_{path}.json')
                    decisions=read(HERE/phase/'decisions'/f'{seed}_{scenario}_{path}.json')
                    cm=cal_models[path]
                    ck(len(output)==len(facts)==len(decisions),'all output rows preserved')
                    for f,event,decision,ref in zip(facts,output,decisions,refs[kind]):
                        counts[event['status']]+=1;n_outputs+=1
                        ck(event['status']=='ok' and decision['status']=='assessed','successful output and evidence availability')
                        ck(event['task']['task_id']==f['task']['task_id']==ref['task_id'],'all identities align')
                        ck(model['fit_cutoff_min']<cm['cutoff_min']<f['task']['notice_min'],'training and calibration complete before query')
                        eta=math.fsum(b-y for b,y in zip(ref['reference_kw'][15:45],f['power_kw'][15:45]))/45
                        ck(abs(eta-event['outcome']['value'])<1e-12,'independent actual-power eta integration')
                        curve=np.asarray(event['process']['reduction_interval_kw'])[15:45]
                        duration=float(np.count_nonzero(curve>=.1*f['task']['request_kw'])*60)
                        ck(duration==event['process']['features']['selected_curve']['cumulative_response_seconds']==decision['measured_cumulative_seconds'],'fitted duration unchanged by evidence')
                        score=independent_score(event)
                        ck(abs(score-decision['score']['score'])<1e-10,'independent query scan')
                        rankp=(1+sum(v>=decision['score']['score'] for v in cm['user_max_scores']))/97
                        ck(rankp==decision['rank_p_value'],'independent rank p including ties')
                        ck(decision['decision']==('evidence' if rankp<=.05 else 'inconclusive'),'independent evidence decision')
                        ck(decision['measured_duration_overwritten'] is False and decision['raw_eta_overwritten'] is False,'no rewritten outcomes')
        summaries[phase]=dict(statuses=dict(counts),n_blocks=len(seeds))
    ck(n_outputs==1536+12288,'planned four-path validation and main output count')
    result=dict(passed=True,n_checks=checks,n_factual_variants_audited=n_events,n_process_outputs_audited=n_outputs,
        phases=summaries,fit_cutoff_min=model['fit_cutoff_min'],calibration_cutoff_min=cal_models['new_cpop']['cutoff_min'],
        source_identity_unchanged=True,model_or_algorithm_refit=False,raw_eta_and_duration_preserved=True,
        score_audit='Direct finite windows via math.fsum, separately from formal cumulative-sum implementation; rank p independently counted with conservative ties.',
        scope='Read-only arithmetic, identity, legal time and finite-rank audit. Check count is not a performance sample size.',
        main_receipt_sha256=sha(HERE/'test/receipt.json'))
    with (HERE/'audit_receipt.json').open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,allow_nan=False,indent=2)
    print(json.dumps(result),flush=True)


if __name__=='__main__':main()
