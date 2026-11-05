"""Explicit staged small pilot. Fits/selects/calibrates from facts only."""
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
import sys,time
from collections import Counter
import numpy as np
from sklearn.covariance import LedoitWolf
from pilot_common import HERE,ROOT,read,write_new,sha,facts_path,source_identity,assert_identity
from make_data import generate
from reference_models import candidate_specs,fit_model,predict_model,save_model,load_model
from trend_filter import fit_curve
sys.path.insert(0,str(ROOT/'B1算法'))
from b1_algorithm import provided_reference
from b1_algorithm.api import analyze_events,_default_runtime_config
from b1_algorithm.process.api import prepare,_features

METHODS=('tf_standard','tf_gls','cpop')
PROFILE=dict(max_charge_kw=7.2,revised_rebound_bound_policy='declared_headroom')

def phase_facts(phase,variant='non_event'):
    d=read(HERE/'protocol.json')['stages'][phase]
    return read(facts_path(phase,d['seed'],variant))

def selected_reference():
    choice=read(HERE/'reference_selection.json')
    path=ROOT/choice['artifact']
    if sha(path)!=choice['artifact_sha256']:raise RuntimeError('selected reference artifact changed')
    return load_model(path)

def select_reference():
    train=phase_facts('train');val=phase_facts('reference_validation')
    cutoff=max(f['availability']['power_records_available_at_min'] for f in train)
    target=np.asarray([f['power_kw'] for f in val]);rows=[]
    assert cutoff<min(f['task']['notice_min'] for f in val)
    for spec in candidate_specs():
        tick=time.perf_counter();model=fit_model(train,spec,cutoff,seed=7610000)
        fit_seconds=time.perf_counter()-tick
        tick=time.perf_counter();pred=predict_model(model,val);predict_seconds=time.perf_counter()-tick
        artifact=save_model(model,HERE/'models'/spec['id'])
        restored=load_model(artifact)
        assert np.array_equal(pred,predict_model(restored,val))
        write_new(HERE/'reference_validation_predictions'/f"{spec['id']}.json",dict(task_ids=[f['task']['task_id'] for f in val],prediction=pred))
        rows.append(dict(spec=spec,mse=float(np.mean((pred-target)**2)),rmse=float(np.sqrt(np.mean((pred-target)**2))),
            bias=float(np.mean(pred-target)),fit_seconds=fit_seconds,predict_seconds=predict_seconds,
            artifact=artifact.relative_to(ROOT).as_posix(),artifact_sha256=sha(artifact),
            training_rows=model.metadata['training_rows'],training_users=len(model.metadata['training_users']),roundtrip_exact=True))
        print('reference',spec['id'],rows[-1]['rmse'],flush=True)
    selected=min(enumerate(rows),key=lambda v:(v[1]['mse'],v[0]))[1]
    write_new(HERE/'reference_selection.json',dict(stage='internal_only',selected=selected['spec']['id'],
        artifact=selected['artifact'],artifact_sha256=selected['artifact_sha256'],rows=rows,
        validation_users=len({f['task']['user_id'] for f in val}),selection_truth_read=False,fit_cutoff_min=cutoff,
        target='Observed explicitly uncalled non-event meter power; not simulator counterfactual labels'))

def data_for(fact,reference,sigma):
    t=dict(fact['task']);origin=t['start_min']
    t.update(start_min=0.,end_min=t['end_min']-origin,notice_min=t['notice_min']-origin)
    return prepare(np.asarray(fact['starts_min'])-origin,np.asarray(fact['ends_min'])-origin,
        fact['power_kw'],reference,t,sigma,PROFILE)

def extracted(data,prediction):
    f=_features(data,np.asarray(prediction))['selected_curve']
    req=(data['starts']>=0)&(data['starts']<30)
    f.update(mean_reduction_kw=float(np.mean(np.asarray(prediction)[req])),
             peak_reduction_kw=float(np.max(np.asarray(prediction)[req])))
    return f

def scan(prediction):
    task=np.asarray(prediction)[15:45]
    return float(max(np.max(np.convolve(task,np.ones(length),mode='valid'))/np.sqrt(length) for length in (1,3,5,10,15,30)))

def user_false_rate(facts,predictions):
    counts={f['task']['user_id']:False for f in facts};failed=0
    for fact,p in zip(facts,predictions):
        if p is None:failed+=1;continue
        counts[fact['task']['user_id']] |= bool(np.any(np.asarray(p)[15:45]>=.15))
    return dict(n_users=len(counts),false_users=sum(counts.values()),rate=sum(counts.values())/len(counts),unavailable=failed)

def select_process():
    facts=phase_facts('process_development');reference=predict_model(selected_reference(),facts)
    residual=reference-np.asarray([f['power_kw'] for f in facts])
    estimator=LedoitWolf().fit(residual)
    covariance=estimator.covariance_+np.eye(60)*1e-8
    scalar_variance=max(.05**2,float(np.mean(residual**2)))
    write_new(HERE/'development_error_model.json',dict(covariance=covariance,scalar_variance=scalar_variance,
        sigma_effective=float(np.sqrt(scalar_variance)),residual_mean=residual.mean(axis=0),
        shrinkage=float(estimator.shrinkage_),users=sorted({f['task']['user_id'] for f in facts}),
        task_ids=[f['task']['task_id'] for f in facts],residuals=residual,
        label_cutoff_min=max(f['availability']['power_records_available_at_min'] for f in facts),
        mean_bias_corrected=False,meter_noise_already_included=True))
    chosen={};grids={}
    for method,cov in [('tf_standard',scalar_variance),('tf_gls',covariance)]:
        rows=[]
        for penalty in read(HERE/'protocol.json')['process']['penalties']:
            tick=time.perf_counter();fits=[fit_curve(y,cov,penalty) for y in residual]
            rate=user_false_rate(facts,[fit['prediction'] for fit in fits])
            row=dict(penalty=penalty,**rate,seconds=time.perf_counter()-tick)
            rows.append(row)
            write_new(HERE/'development_solver'/f'{method}_{penalty}.json',fits)
        valid=[r for r in rows if r['unavailable']==0]
        if not valid:raise RuntimeError('no numerically available development candidate: '+method)
        passed=[r for r in valid if r['rate']<=.05]
        selection=min(passed,key=lambda r:r['penalty']) if passed else min(valid,key=lambda r:(r['rate'],r['penalty']))
        chosen[method]=dict(penalty=selection['penalty'],development_target_met=bool(passed),development_false_rate=selection['rate'])
        grids[method]=rows
        print('process',method,chosen[method],flush=True)
    write_new(HERE/'process_selection.json',dict(chosen=chosen,grid=grids,truth_used=False,
        source='Explicit non-event development only; no response-truth tuning',
        raw_FPR_comparability='TF regularization selected using this rule; native CPOP beta fixed at2log60, so raw duration-rate comparisons are configuration-specific, not matched-raw-FPR superiority. Independent rank evidence has common alpha.'))

def process(facts,references,method,label):
    error=read(HERE/'development_error_model.json');sigma=error['sigma_effective'];rows=[];tick=time.perf_counter()
    if method=='cpop':
        records=[]
        for f,ref in zip(facts,references):
            bound=provided_reference(f['task'],f['starts_min'],f['ends_min'],ref,available_at_min=f['task']['notice_min'])
            records.append(dict(task=f['task'],starts_min=f['starts_min'],ends_min=f['ends_min'],power_kw=f['power_kw'],
                reference=bound,noise_sigma_kw=sigma,ev_config=PROFILE))
        config=_default_runtime_config();config['artifact_dir']=str(HERE/'native'/label)
        originals=analyze_events(records,process_method='cpop',process_config=config)
        write_new(HERE/'native_outputs'/f'{label}.json',originals)
        for f,ref,out in zip(facts,references,originals):
            p=out.get('process') or {};pred=p.get('reduction_interval_kw') if p.get('method')=='CPOP' and out['status']=='ok' else None
            rows.append(dict(task_id=f['task']['task_id'],user_id=f['task']['user_id'],method=method,
                status='ok' if pred is not None else 'unavailable',prediction=pred,
                features=extracted(data_for(f,ref,sigma),pred) if pred is not None else None,
                eta_raw=p.get('eta_raw'),solver=dict(engine='native_CPOP',reason=out.get('reasons'),backend=p.get('backend'))))
    else:
        penalty=read(HERE/'process_selection.json')['chosen'][method]['penalty']
        covariance=error['scalar_variance'] if method=='tf_standard' else np.asarray(error['covariance'])
        for f,ref in zip(facts,references):
            data=data_for(f,ref,sigma);fit=fit_curve(data['y'],covariance,penalty);pred=fit['prediction']
            req=(data['starts']>=0)&(data['starts']<30)
            rows.append(dict(task_id=f['task']['task_id'],user_id=f['task']['user_id'],method=method,
                status=fit['status'],prediction=pred,features=extracted(data,pred) if pred is not None else None,
                eta_raw=float(np.sum(data['y'][req])/45),solver={k:v for k,v in fit.items() if k!='prediction'}))
    for row in rows:row['scan_score']=scan(row['prediction']) if row['prediction'] is not None else None
    return rows,dict(label=label,method=method,n_events=len(rows),seconds=time.perf_counter()-tick,status_counts=dict(Counter(r['status'] for r in rows)))

def calibrate():
    facts=phase_facts('calibration');references=predict_model(selected_reference(),facts)
    write_new(HERE/'references'/'calibration.json',dict(task_ids=[f['task']['task_id'] for f in facts],prediction=references))
    models={};timings=[]
    for method in METHODS:
        rows,timing=process(facts,references,method,'calibration_'+method);timings.append(timing)
        write_new(HERE/'calibration_outputs'/f'{method}.json',rows)
        maxima={}
        for row in rows:
            if row['scan_score'] is None:raise RuntimeError('calibration unavailable; cannot omit users')
            maxima[row['user_id']]=max(maxima.get(row['user_id'],-float('inf')),row['scan_score'])
        assert len(maxima)==48
        models[method]=dict(user_maxima=maxima,alpha=.05,n_users=48,events_per_user=2,
            calibration_cutoff_min=max(f['availability']['power_records_available_at_min'] for f in facts),
            scope='User-block exchangeability conditional; not field5percent certification')
    write_new(HERE/'event_calibration.json',models);write_new(HERE/'calibration_timing.json',timings)
    artifacts={}
    for name in ['reference_selection.json','process_selection.json','development_error_model.json','event_calibration.json']:
        artifacts[(HERE/name).relative_to(ROOT).as_posix()]=sha(HERE/name)
    for p in (HERE/'models').rglob('*'):
        if p.is_file():artifacts[p.relative_to(ROOT).as_posix()]=sha(p)
    write_new(HERE/'freeze.json',dict(source_identity=source_identity(),artifact_sha256=artifacts,
        validation_generated=False,test_generated=False,formal_selection_approved=False))

def assert_freeze():
    frozen=read(HERE/'freeze.json');assert_identity(frozen['source_identity'])
    for p,h in frozen['artifact_sha256'].items():
        if sha(ROOT/p)!=h:raise RuntimeError('frozen model/config changed:'+p)

def evaluate_phase(phase):
    assert_freeze()
    if phase=='test' and not (HERE/'validation_completed.json').is_file():raise RuntimeError('validation must be completed first')
    generate(phase)
    design=read(HERE/'protocol.json')['stages'][phase];cal=read(HERE/'event_calibration.json')
    timings=[]
    for seed in design.get('seeds',[design.get('seed')]):
        # Same reference_window across paired variants; compute once per base task.
        base=read(facts_path(phase,seed,design['variants'][0]));tick=time.perf_counter()
        references=predict_model(selected_reference(),base);reference_seconds=time.perf_counter()-tick
        write_new(HERE/'references'/f'{phase}_{seed}.json',dict(task_ids=[f['task']['task_id'] for f in base],prediction=references,seconds=reference_seconds))
        for variant in design['variants']:
            facts=read(facts_path(phase,seed,variant))
            assert [f['reference_window'] for f in facts]==[f['reference_window'] for f in base]
            for method in METHODS:
                label=f'{phase}_{seed}_{variant}_{method}'
                rows,timing=process(facts,references,method,label);timings.append(timing)
                cm=cal[method];maxima=np.asarray(list(cm['user_maxima'].values()))
                for row in rows:
                    score=row['scan_score'];pvalue=None if score is None else float((1+np.sum(maxima>=score))/(len(maxima)+1))
                    row.update(evidence_p=pvalue,evidence_status='unavailable' if pvalue is None else 'evidence' if pvalue<=.05 else 'inconclusive')
                write_new(HERE/'outputs'/phase/f'{seed}_{variant}_{method}.json',rows)
                print(label,timing['status_counts'],round(timing['seconds'],3),flush=True)
    write_new(HERE/f'{phase}_completed.json',dict(phase=phase,timings=timings,source_unchanged=True,parameters_changed=False,truth_used_by_process=False))
    assert_freeze()

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['reference','process','calibrate','validation','test'])
    stage=parser.parse_args().stage
    if stage=='reference':select_reference()
    elif stage=='process':select_process()
    elif stage=='calibrate':calibrate()
    else:evaluate_phase(stage)
