"""Root's independent raw-fact/chronology audit of the history specialist."""
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
from pathlib import Path
import json,hashlib,sys
from dataclasses import asdict
import numpy as np
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'B1算法'))
from b1_api import ReferenceWindow,load_reference_model,select_ev_reference
from b1_algorithm.history import prepare_ev_history,load_ev_history_encoder,encode_ev_history
H=R/'work/b1_finish_ev_20261030/history';N=0
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def check(value,label):
    global N
    assert value,label
    N+=1
model=load_reference_model(R/'work/b1_formal_v1_20261029/reference/artifact')
selection=read(H/'selection.json');selectionsha=hashlib.sha256((H/'selection.json').read_bytes()).hexdigest()
for seed in range(7130000,7130006):
    facts=read(R/f'data/B1_finish_history_v1_20261030/{seed}_facts.json')
    prepared=read(H/f'prepared/{seed}.json');byid={r['task_id']:r for r in prepared}
    splits={s:{r['user_id'] for r in prepared if r['partition']==s} for s in ('train','validation','test')}
    check(all(len(v)==100 for v in splits.values()),'user counts')
    check(not (splits['train']&splits['validation'] or splits['train']&splits['test'] or splits['test']&splits['validation']),'disjoint users')
    for method in ('stats6','pca6','ae6'):
        enc=load_ev_history_encoder(H/f'models/{seed}_{method}.json');state=json.loads(enc.payload_json)
        check(set(state['training_users'])==splits['train'],'encoder train only')
        for partition in ('validation','test'):
            fit=read(H/f'{partition}/{seed}_{method}.json')
            check(fit['history_design']['encoder_refit_in_evaluation'] is False,'no encoder refit')
            if partition=='test':check(fit['selection_frozen_before_test_sha256']==selectionsha,'frozen validation choice')
    # Reconstruct predictions from raw facts, independently of stored raw90.
    for u in (0,100,200):
        records=[];manual=[]
        for f in facts[u*5:u*5+3]:
            reference=select_ev_reference(model,ReferenceWindow(**f['reference_window']),f['historical_non_event'])['reference']
            b=np.asarray(reference.reference_kw);power=np.asarray(f['power_kw']);starts=np.asarray(f['starts_min']);ends=np.asarray(f['ends_min'])
            task=f['task'];inside=(starts>=task['start_min']-1e-8)&(ends<=task['end_min']+1e-8)
            # Reference query covers the same full observation intervals.
            manual.extend(((b-power)[inside]/task['request_kw']).tolist())
            records.append(dict(task=task,starts_min=f['starts_min'],ends_min=f['ends_min'],power_kw=f['power_kw'],noise_sigma_kw=f['noise_sigma_kw'],reference=asdict(reference),observed_available_at_min=f['availability']['power_records_available_at_min'],ev_config={'max_charge_kw':7.2}))
        for j in (3,4):
            current=facts[u*5+j]['task'];stored=byid[current['task_id']]
            recomputed=prepare_ev_history(records,current)
            check(np.allclose(manual,stored['history']['raw'],rtol=0,atol=1e-12),'raw residual90 from facts')
            check(recomputed==stored['history'],'source rebind reproduces exact history')
            raw=np.asarray(manual).reshape(3,30)
            check(abs(np.mean(raw)-stored['history']['summary'][0])<1e-12,'eta summary independently integrated')
            check(abs(np.mean(raw>=.1)-stored['history']['summary'][2])<1e-12,'duration summary independently counted')
            for method in ('stats6','pca6','ae6'):
                enc=load_ev_history_encoder(H/f'models/{seed}_{method}.json');a=encode_ev_history(enc,recomputed)
                check(len(a['values'])==6 and a['training_user_overlap']==(u==0),'encode group identity')
                check(a['known_at_min']<=current['notice_min'],'no future control')
    for row in prepared:
        h=row['history'];check(all(p['task_id'].rsplit('-',1)[-1] in ('0','1','2') for p in h['provenance']),'fixed histories, not current result')
check(selection['selected']=='C0' and selection['selection_uses_test'] is False,'selection as frozen rule')
receipt=dict(passed=N,independent_reviewer='root; independent from history implementation agent',raw_reconstruction_users=18,target_replays=36,selection_sha256=selectionsha,changed_scientific_outputs=False)
(R/'work/b1_finish_ev_20261030/independent_history_receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
print(receipt)
