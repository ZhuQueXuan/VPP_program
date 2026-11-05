"""Independent, read-only prediction/provenance review; never calls fit."""
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[k]='1'
from pathlib import Path
import ast
import hashlib
import json
import time
from collections import Counter
import numpy as np
import lightgbm as lgb
from reference_models import load_model,predict_model

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
FACTS=ROOT/'data/B1_unknown_reference_pilot_v1_20261031'
hashes={};checks=Counter()

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):
    hashes[Path(p).relative_to(ROOT).as_posix()]=sha(p)
    return json.loads(Path(p).read_text(encoding='utf-8'))
def ck(name,v):
    if not bool(v):raise AssertionError(name)
    checks[name]+=1
def near(name,a,b,tol=1e-11):ck(name,np.allclose(a,b,atol=tol,rtol=0))

def independently_mapped(f):
    w=f['reference_window'];prefix=np.array(w['pre_power_kw'],float)
    start=np.array(w['pre_starts_min']);end=np.array(w['pre_ends_min'])
    keep=(start>=w['notice_min']-60-1e-9)&(end<=w['notice_min']+1e-9)
    prefix=prefix[keep]
    ck('full legal prefix',len(prefix)==60)
    offset=float(np.mean(prefix));blocks=prefix.reshape(4,15).mean(1)-offset
    shape=np.array(w['prior_mean_kw'])-np.mean(w['prior_mean_kw'])
    horizon=np.arange(.5,60.,1.);hour=w['clock_hour']+(horizon-15.)/60.
    x=np.column_stack([np.repeat(blocks[None,:],60,axis=0),shape,horizon/60.,
        np.sin(hour*np.pi/12.),np.cos(hour*np.pi/12.),
        np.repeat(np.sin(w['weekday']*2*np.pi/7.),60),
        np.repeat(np.cos(w['weekday']*2*np.pi/7.),60),
        np.repeat(w['temperature_c'],60)])
    return x,offset

def run():
    tick=time.perf_counter();P=read(HERE/'protocol.json');F=read(HERE/'freeze.json')
    S=read(HERE/'reference_selection.json')
    for p,h in F['source_identity'].items():ck('frozen source unchanged',sha(ROOT/p)==h)
    for p,h in F['artifact_sha256'].items():ck('frozen scientific artifact unchanged',sha(ROOT/p)==h)
    # Read facts, not evaluator labels; use one strong member for paired test IDs.
    stage_facts={};users={};times={};blocks={}
    for phase,d in P['stages'].items():
        data=[];blockset=[]
        for seed in d.get('seeds',[d.get('seed')]):
            variant=d['variants'][0]
            fs=read(FACTS/phase/f'{seed}_{variant}_facts.json')
            data.extend(fs);blockset.append(set(f['task']['user_id'] for f in fs))
            ck('unique original users within test seed blocks',all(not blockset[-1]&s for s in blockset[:-1]))
        stage_facts[phase]=data;users[phase]=set(f['task']['user_id'] for f in data)
        times[phase]=dict(first_notice=min(f['task']['notice_min'] for f in data),
            final_label=max(f['availability']['power_records_available_at_min'] for f in data))
        ck('two events per original user',set(Counter(f['task']['user_id'] for f in data).values())=={2})
        for f in data:
            w=f['reference_window'];notice=f['task']['notice_min']
            ck('all current helper inputs available by notice',max(w[k] for k in ('pre_available_min','prior_available_min','calendar_available_min','temperature_available_min'))<=notice)
            ck('no postnotice prefix observations',max(w['pre_ends_min'])<=notice)
            history={h['source_id']:h for h in f['historical_non_event']}
            hs=[history[k] for k in w['prior_source_ids']]
            ck('history identity and chronology',all(h['user_id']==w['user_id'] and h['meter_id']==w['meter_id'] and h['non_event'] is True and h['available_at_min']<=notice for h in hs))
            near('actual prior source mean',w['prior_mean_kw'],np.mean([h['power_kw'][-60:] for h in hs],0))
            ck('calendar agrees with whole-week shift',w['clock_hour']==(w['task_start_min']%1440)/60 and w['weekday']==int(w['task_start_min']//1440)%7)
    phases=list(P['stages'])
    for i,a in enumerate(phases):
        for b in phases[i+1:]:ck('independent users across all stages',not users[a]&users[b])
    for a,b in zip(phases,phases[1:]):ck('label completion precedes next stage',times[a]['final_label']<times[b]['first_notice'])
    train=stage_facts['train'];val=stage_facts['reference_validation']
    ck('actual finite cohort sizes',len(train)==128 and len(users['train'])==64 and len(val)==64 and len(users['reference_validation'])==32)
    ck('uncalled actual observed training/selection labels',all(f['non_event'] is True and f['task_dispatched'] is False and f['incentive_signal_announced'] is False for f in train+val))
    ix=np.array([0,8,16,25,34,43,51,59]);maps=[independently_mapped(f) for f in train]
    X=np.concatenate([x[ix] for x,o in maps]);Y=np.concatenate([(np.array(f['power_kw'])-o)[ix] for f,(x,o) in zip(train,maps)])
    ck('1024 actual shared horizon labels',X.shape==(1024,11) and Y.shape==(1024,))
    vmaps=[independently_mapped(f) for f in val];VX=np.concatenate([x for x,o in vmaps]);offsets=np.array([o for x,o in vmaps])
    target=np.array([f['power_kw'] for f in val]);scores=[];rows=[];digests=[]
    for row in S['rows']:
        path=ROOT/row['artifact'];env=read(path)
        ck('candidate envelope integrity',hashlib.sha256(env['payload_json'].encode('utf-8')).hexdigest()==env['sha256'])
        payload=json.loads(env['payload_json']);m=payload['metadata'];digests.append(m['training_digest'])
        ck('candidate path SHA exact',sha(path)==row['artifact_sha256'])
        ck('training users and task identities exact',m['training_users']==sorted(users['train']) and m['training_task_ids']==sorted(f['task']['task_id'] for f in train))
        ck('training cutoff and completion',m['fit_cutoff_min']==times['train']['final_label'] and m['training_label_completion_max_min']==times['train']['final_label'])
        near('training-only scaler mean',payload['scaler_mean'],X.mean(0))
        scales=X.std(0);scales[scales==0]=1.
        near('training-only scaler scale',payload['scaler_scale'],scales)
        # Use saved scaler below; independent feature arithmetic can round at ~1e-16.
        Z=(X-payload['scaler_mean'])/payload['scaler_scale'];VZ=(VX-payload['scaler_mean'])/payload['scaler_scale']
        if m['spec']['family']=='lightgbm':
            tree=path.parent/'tree.txt';ck('native tree integrity',sha(tree)==payload['tree_sha256'])
            engine=lgb.Booster(model_file=str(tree));pred=engine.predict(VZ,num_threads=1).reshape(len(val),60)+offsets[:,None]
            kernel_residual=None
        else:
            near('same GP standardized train features',Z,payload['gp_train_x'])
            p=m['engine_params'];ck('fixed kernel, no optimizing',p['amplitude']==.04 and p['white_noise_variance']==.0025 and p['optimizer'] is None and p['alpha']==0.)
            z=np.array(payload['gp_train_x']);alpha=np.array(payload['gp_alpha']);length=p['length_scale']
            dist=np.sum((z[:,None,:]-z[None,:,:])**2,axis=2)
            K=.04*np.exp(-dist/(2*length*length))+.0025*np.eye(len(z))
            kernel_residual=float(np.max(abs(K@alpha-Y)))
            ck('saved GP weights satisfy native kernel equations',kernel_residual<1e-10)
            parts=[]
            for begin in range(0,len(VZ),128):
                dist=np.sum((VZ[begin:begin+128,None,:]-z[None,:,:])**2,axis=2)
                parts.append(.04*np.exp(-dist/(2*length*length))@alpha)
            pred=np.concatenate(parts).reshape(len(val),60)+offsets[:,None]
        saved=read(HERE/'reference_validation_predictions'/f"{m['spec']['id']}.json")
        ck('prediction row identity exact',saved['task_ids']==[f['task']['task_id'] for f in val])
        replay_delta=float(np.max(abs(pred-np.array(saved['prediction']))))
        ck('independent full60 reference validation replay',replay_delta<1e-10)
        restored=load_model(path)
        ck('loaded-model saved roundtrip exact',np.array_equal(predict_model(restored,val),np.array(saved['prediction'])))
        mse=float(np.mean((pred-target)**2));bias=float(np.mean(pred-target))
        near('selection score from observed labels only',[mse,np.sqrt(mse),bias],[row['mse'],row['rmse'],row['bias']])
        scores.append(mse);rows.append(dict(id=m['spec']['id'],mse=mse,rmse=np.sqrt(mse),bias=bias,
            replay_max_abs_difference=replay_delta,kernel_equation_max_residual=kernel_residual))
    ck('same training cohort digest all candidates',len(set(digests))==1)
    ck('selected minimum finite observed-MSE candidate',S['selected']==S['rows'][int(np.argmin(scores))]['spec']['id'])
    selected=load_model(ROOT/S['artifact'])
    for phase,d in P['stages'].items():
        if phase in ('train','reference_validation'):continue
        for seed in d.get('seeds',[d.get('seed')]):
            data=read(FACTS/phase/f"{seed}_{d['variants'][0]}_facts.json")
            # process-development references are saved in its error model, not reference folder.
            if phase=='process_development':continue
            name='calibration.json' if phase=='calibration' else f'{phase}_{seed}.json'
            saved=read(HERE/'references'/name)
            ck('shared frozen selected reference exact replay',np.array_equal(np.array(saved['prediction']),predict_model(selected,data)))
    tree=ast.parse((HERE/'run.py').read_text(encoding='utf-8'))
    node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='select_reference')
    strings={n.value for n in ast.walk(node) if isinstance(n,ast.Constant) and isinstance(n.value,str)}
    ck('selector source names only train and reference-validation stages',{'train','reference_validation'}<=strings and not {'test','validation','evaluator','truth'}&strings)
    ck('selector explicitly internal role',S['stage']=='internal_only')
    for p,h in hashes.items():ck('review inputs unchanged',sha(ROOT/p)==h)
    receipt=dict(status='passed',scope='Read-only reference result audit; no fitting, generation, tuning or evaluator truth read',
        checks=dict(checks),n_checks=sum(checks.values()),source_files=len(F['source_identity']),
        input_files=len(hashes),users_by_stage={k:len(v) for k,v in users.items()},times_by_stage=times,
        training_rows=1024,training_records=128,training_users=64,selection_records=64,selection_users=32,
        selection_target='full60 observed non-event meter power',selected=S['selected'],rows=rows,
        no_new_fit=True,no_evaluator_truth_read=True,no_test_based_selection=True,
        provenance_limit='Hashes and saved source verify within-run consistency, not trusted external timestamps or unseen execution history.',
        sha256=hashes,seconds=time.perf_counter()-tick)
    output=HERE/'reference_result_review_receipt.json'
    with output.open('x',encoding='utf-8') as stream:json.dump(receipt,stream,ensure_ascii=False,allow_nan=False,indent=2)
    print(json.dumps(dict(status='passed',checks=sum(checks.values()),files=len(hashes),selected=S['selected'],seconds=receipt['seconds'])))

if __name__=='__main__':run()
