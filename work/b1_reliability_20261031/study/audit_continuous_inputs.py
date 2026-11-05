"""Read-only shared-input audit, using observations only and no evaluator truth."""
from pathlib import Path
import json
import hashlib
import math
import numpy as np
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
DATA=ROOT/'data/B1_reliability_v1_20261031'


def read(p):return json.loads(Path(p).read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    p=read(HERE.parent/'protocol.json')['continuous_after_reliability']
    selection=read(HERE.parent/'effects/selection_receipt.json')
    if sha(HERE.parent/'effects/selection.json')!=selection['selection_artifact_sha256']:raise AssertionError('selection changed')
    checks=0
    def ck(ok,why):
        nonlocal checks
        if not ok:raise AssertionError(why)
        checks+=1
    manifest=read(HERE/'phase1_scientific_files_sha256.json')
    for rel,expected in manifest['files'].items():ck(sha(ROOT/rel)==expected,'phase1 artifact changed '+rel)
    reference_id=read(HERE/'models/reliable_reference.json')['model_id']
    train=set(read(HERE/'models/reliable_reference.json')['payload']['training_users'])
    cal=set(json.loads(read(HERE/'models/evidence_new_cpop.json')['payload_json'])['users'])
    validation_users=set();counts={};source_hashes={}
    for phase,seeds,nusers,scenarios,shift in (('validation',[p['validation_seed']],256,('positive',),8064000),('test',p['test_seeds'],128,('positive','zero'),10080000)):
        counts[phase]=0
        for seed in seeds:
            base=HERE/'continuous'/phase
            refs=read(base/'references'/f'{seed}.json')['references'];canonical=None
            for scenario in scenarios:
                fp=DATA/f'continuous_{phase}'/f'{seed}_{scenario}_facts.json'
                ep=base/'events'/f'{seed}_{scenario}.json';xp=base/'factor_inputs'/f'{seed}_{scenario}.json'
                facts,events,factors=read(fp),read(ep),read(xp)
                for path in (fp,ep,xp):source_hashes[path.relative_to(ROOT).as_posix()]=sha(path)
                ck(len(facts)==len(events)==len(factors)==nusers*2,'unfiltered input and output counts')
                users={f['task']['user_id'] for f in facts};ck(len(users)==nusers and not users&train and not users&cal,'independent users')
                if phase=='validation':validation_users.update(users)
                else:ck(not users&validation_users,'selection/test users separated')
                if canonical is None:canonical=facts
                for index,(fact,event,factor,ref) in enumerate(zip(facts,events,factors,refs)):
                    ck(event['status']=='ok' and event['process']['method']=='CPOP','unchanged original CPOP on every event')
                    ck(factor==fact['factor_record'],'original factor records retained')
                    ck(factor==canonical[index]['factor_record'] and fact['reference_window']==canonical[index]['reference_window'] and fact['historical_non_event']==canonical[index]['historical_non_event'],'paired positive/zero exogenous observations')
                    task=fact['task'];user,j=divmod(index,2)
                    ck(task['start_min']==200000+180*user+20160*j+shift,'all absolute task clocks shifted')
                    ck(max(fact['reference_window']['pre_ends_min'])<=task['notice_min'] and max(h['available_at_min'] for h in fact['historical_non_event'])<=task['notice_min'],'legal prefix and historical observations')
                    ck(ref['model_id']==reference_id and ref['available_at_min']<=task['notice_min'],'same frozen reference available')
                    ck(event['reference']['model_id']==reference_id,'same reference supplied to every factor estimator')
                    ck(factor['treatment_set_min']==task['notice_min'] and all(factor['available_at_min'][name]<task['notice_min'] for name in ('deadline_slack','demand_urgency')),'L/U pre-treatment availability')
                    eta=math.fsum(b-y for b,y in zip(ref['reference_kw'][15:45],fact['power_kw'][15:45]))/45
                    ck(abs(eta-event['outcome']['value'])<1e-12,'independent raw eta integral')
                    duration=np.count_nonzero(np.asarray(event['process']['reduction_interval_kw'])[15:45]>=.1*1.5)*60
                    ck(duration==event['process']['features']['selected_curve']['cumulative_response_seconds'],'measured cumulative duration')
                    ck(fact['non_event'] is False and fact['task_dispatched'] is True,'both positive and zero-effect mechanisms are dispatched tasks')
                    if phase=='test':ck(task['notice_min']>selection['validation_times']['final_label_available_min'],'selection labels completed before all tests')
                    counts[phase]+=1
    result=dict(passed=True,n_checks=checks,events=counts,total_events=sum(counts.values()),
        original_phase1_files_unchanged=manifest['n_files'],phase1_manifest_sha256=sha(HERE/'phase1_scientific_files_sha256.json'),
        selection_artifact_sha256=selection['selection_artifact_sha256'],source_sha256=source_hashes,
        truth_files_opened=False,model_fits=False,evidence_filtering=False,
        scope='Observed-input identity, pairing, time availability and integration audit; no evaluator truth or effect selection/refitting.')
    target=HERE/'continuous/input_audit_receipt.json'
    with target.open('x',encoding='utf8') as f:json.dump(result,f,ensure_ascii=False,allow_nan=False,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k!='source_sha256'}),flush=True)


if __name__=='__main__':main()
