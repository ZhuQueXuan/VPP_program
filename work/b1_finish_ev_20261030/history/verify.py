"""Read-only numerical audit of the finite history study (no encoder refit)."""
from pathlib import Path
import hashlib
import json
import numpy as np

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]


def read(path):return json.loads(path.read_text(encoding='utf-8'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    checks=0;issues=[]
    def check(name,condition):
        nonlocal checks
        checks+=1
        if not condition:issues.append(name)
    protocol=read(HERE.parent/'protocol.json');seeds=protocol['step5']['seeds']
    for relative,digest in read(HERE/'source_freeze.json').items():
        check('frozen source '+relative,sha(ROOT/relative)==digest)
    validation={};test={};all_model_ids={}
    for seed in seeds:
        rows=read(HERE/f'prepared/{seed}.json')
        partitions={name:[r for r in rows if r['partition']==name] for name in ('train','validation','test')}
        users={name:{r['user_id'] for r in value} for name,value in partitions.items()}
        check(f'{seed} partition row counts',all(len(r)==200 for r in partitions.values()))
        check(f'{seed} partition user counts',all(len(r)==100 for r in users.values()))
        check(f'{seed} user separation',not(users['train']&users['validation'] or users['train']&users['test'] or users['test']&users['validation']))
        for r in rows:
            h=r['history'];current=h['current_task'];raw=np.asarray(h['raw']).reshape(3,30)
            check('fixed first three history IDs '+r['task_id'],[p['task_id'].rsplit('-event-',1)[1] for p in h['provenance']]==['0','1','2'])
            check('all history sources legally known '+r['task_id'],all(p['observed_available_at_min']<=h['cutoff_min']<=current['notice_min'] and p['observation_end_min']<=p['observed_available_at_min'] for p in h['provenance']))
            check('same object bound '+r['task_id'],all(p['user_id']==current['user_id']==r['user_id'] and p['meter_id']==current['meter_id'] for p in h['provenance']))
            eta=raw.mean(1);cumulative=(raw>=.1).mean(1);long=[]
            for vector in raw:
                longest=run=0
                for active in vector>=.1:
                    run=run+1 if active else 0;longest=max(longest,run)
                long.append(longest/30)
            values=[eta.mean(),eta[-1],cumulative.mean(),np.mean(long),(eta[-1]-eta[0])/2]
            check('summary independently from raw90 '+r['task_id'],np.allclose(np.asarray(h['summary'])[[0,1,2,3,5]],values,atol=1e-12,rtol=0))
            payload={k:v for k,v in h.items() if k!='prepared_digest'}
            canonical=json.dumps(payload,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)
            check('prepared content digest '+r['task_id'],hashlib.sha256(canonical.encode()).hexdigest()==h['prepared_digest'])
        train=partitions['train']
        for method in ('stats6','pca6','ae6'):
            wrapped=read(HERE/f'models/{seed}_{method}.json');state=wrapped['state']
            canonical=json.dumps(state,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)
            check(f'{seed} {method} model checksum',hashlib.sha256(canonical.encode()).hexdigest()==wrapped['sha256'])
            check(f'{seed} {method} train users only',set(state['training_users'])==users['train'])
            values=np.asarray([r['history']['summary' if method=='stats6' else 'raw'] for r in train])
            check(f'{seed} {method} train-only mean',np.allclose(values.mean(0),state['mean'],atol=0,rtol=0))
            scale=values.std(0);scale[scale<1e-12]=1
            check(f'{seed} {method} train-only scale',np.allclose(scale,state['scale'],atol=0,rtol=0))
            if method=='pca6':
                c=np.asarray(state['components'])
                check(f'{seed} pca orthonormality',np.allclose(c@c.T,np.eye(6),atol=1e-12))
            if method=='ae6':
                shapes=[np.asarray(a).shape for a in state['coefs']]
                count=sum(np.asarray(a).size for a in state['coefs']+state['intercepts'])
                check(f'{seed} ae architecture budget',shapes==[(90,24),(24,6),(6,24),(24,90)] and count==4752 and state['epochs']==60)
            all_model_ids[f'{seed}_{method}']='ev-history-'+wrapped['sha256']
        validation[seed]=read(HERE/f'validation/{seed}_metrics.json')
        test[seed]=read(HERE/f'test/{seed}_metrics.json')
        for phase,metrics in (('validation',validation[seed]),('test',test[seed])):
            for method,m in metrics.items():
                result=read(HERE/f'{phase}/{seed}_{method}.json')
                check(f'{seed} {phase} {method} same eight columns',result['history_design']['total_input_dimensions']==8 and result['history_design']['history_columns']==6)
                if m['status']=='causal':
                    delta=np.asarray(result['causal_curve']['contrasts'])-m['target_contrasts']
                    check(f'{seed} {phase} {method} independent RMSE',abs(np.sqrt(np.mean(delta**2))-m['curve_rmse'])<1e-12)
                else:
                    check(f'{seed} {phase} {method} refusal retained',m['curve_rmse'] is None and result['causal_curve'] is None)
    selection=read(HERE/'selection.json');methods=['C0','stats6','pca6','ae6'];means={}
    for method in methods:
        v=[validation[s][method]['curve_rmse'] for s in seeds]
        means[method]=float(np.mean(v)) if all(x is not None for x in v) else None
    eligible=[m for m in methods[1:] if means['C0'] is not None and means[m] is not None and means[m]<means['C0']]
    winner=min(eligible,key=lambda m:(means[m],methods.index(m))) if eligible else 'C0'
    check('validation selection independently reproduced',winner==selection['selected'] and selection['selection_uses_test'] is False)
    selection_sha=sha(HERE/'selection.json')
    for seed in seeds:
        for method in methods:
            result=read(HERE/f'test/{seed}_{method}.json')
            check('test bound to earlier selection',result['selection_frozen_before_test_sha256']==selection_sha)
    receipt=dict(status='passed' if not issues else 'failed',checks=checks,issues=issues,
        selected=selection['selected'],model_ids=all_model_ids,source_manifest_verified=True,
        analysis_rows=3600,independent_blocks=6,independent_human_review=False,
        note='Checks audit provenance, arithmetic, train partition and validation selection. They are not performance trials.')
    path=HERE/'verification_receipt.json'
    with path.open('x',encoding='utf-8') as stream:json.dump(receipt,stream,ensure_ascii=False,indent=2)
    print(json.dumps(dict(status=receipt['status'],checks=checks,issues=len(issues))))
    if issues:raise RuntimeError(str(issues[:10]))


if __name__=='__main__':main()
