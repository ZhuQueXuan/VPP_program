"""Small constructed contract/numeric controls only; no scientific cohort."""
from pathlib import Path
import copy
import json
import time
import numpy as np
from sklearn.gaussian_process.kernels import RBF
from reference_models import (candidate_specs, fit_model, predict_model,
    save_model, load_model, _features, FEATURE_NAMES, HORIZONS)

HERE = Path(__file__).resolve().parent


def fact(user, event=0, *, query=False, level=3.):
    start = (20000 if query else 1000) + user*100 + event*40
    notice = start-15
    prefix = level + .03*np.sin(np.arange(60)/9+user*.2) + .002*user
    prior = level+.06*np.sin(np.arange(60)/8+event*.2)
    rw = dict(task_id=f'{"query" if query else "train"}_{user}_{event}',
        user_id=f'{"new" if query else "old"}_{user}', meter_id=f'{"q" if query else "t"}_{user}',
        resource_type='EV', task_start_min=start, task_end_min=start+30,
        request_kw=1.5, notice_min=notice,
        starts_min=(start+np.arange(-15.,45.)).tolist(),
        ends_min=(start+np.arange(-14.,46.)).tolist(),
        pre_starts_min=(notice+np.arange(-60.,0.)).tolist(),
        pre_ends_min=(notice+np.arange(-59.,1.)).tolist(),
        pre_power_kw=prefix.tolist(), pre_available_min=notice,
        prior_mean_kw=prior.tolist(), prior_available_min=notice-100,
        prior_source_count=2, prior_source_ids=[f'h_{user}_a', f'h_{user}_b'],
        clock_hour=12.+user*.2, weekday=user%7, calendar_available_min=notice-1,
        temperature_c=20.+user*.5, temperature_available_min=notice-1,
        prior_sources_non_event=True)
    target = prefix.mean()+.035*np.cos(np.arange(60)/11)+.4*(prior-prior.mean())
    return dict(reference_window=rw, non_event=True, task_dispatched=False,
        incentive_signal_announced=False, power_kw=target.tolist(),
        availability=dict(power_records_available_at_min=start+45))


def run():
    tick=time.perf_counter()
    out=HERE/'reference_controls'
    if (out/'receipt.json').exists():
        raise FileExistsError('control receipt already exists; use a fresh output name')
    out.mkdir(parents=True,exist_ok=True)
    checks=[]
    def check(name, result):
        if not result:
            raise AssertionError(name)
        checks.append(name)
    def reject(name, fn):
        try:
            fn()
        except (ValueError, FileExistsError):
            checks.append(name)
        else:
            raise AssertionError('expected rejection: '+name)
    train=[fact(u,e) for u in range(6) for e in range(2)]
    queries=[fact(u,query=True) for u in range(3)]
    models={}
    diffs={}
    for spec in candidate_specs():
        model=fit_model(train,spec,fit_cutoff_min=5000,seed=5)
        models[spec['id']]=model
        pred=predict_model(model,queries)
        check(spec['id']+' complete 60-horizon prediction',pred.shape==(3,60) and np.isfinite(pred).all())
        check(spec['id']+' shared exact 8-horizon training count',model.metadata['training_rows']==12*8 and model.metadata['training_horizons']==list(HORIZONS))
        check(spec['id']+' train identities',len(model.metadata['training_users'])==6 and len(model.metadata['training_task_ids'])==12)
        stripped=[dict(reference_window=q['reference_window']) for q in queries]
        check(spec['id']+' prediction reads RW only',np.array_equal(pred,predict_model(model,stripped)))
        poisoned=copy.deepcopy(queries)
        for q in poisoned:
            q.update(power_kw=['not readable'], latent=object(), observed_participation=True,
                simulation_variant='truth-must-not-enter', offered_incentive=float('nan'))
        check(spec['id']+' future/truth/dose fields ignored',np.array_equal(pred,predict_model(model,poisoned)))
        p=save_model(model,out/spec['id'])
        restored=predict_model(load_model(p),stripped)
        check(spec['id']+' native serialization exact',np.array_equal(pred,restored))
        reject(spec['id']+' artifact overwrite rejected',lambda:save_model(model,out/spec['id']))
        if spec['family']=='gaussian_process':
            tx=np.concatenate([_features(t)[0][list(HORIZONS)] for t in train])
            ty=np.concatenate([(np.asarray(t['power_kw'])-_features(t)[1])[list(HORIZONS)] for t in train])
            mean=tx.mean(0);scale=tx.std(0);scale[scale==0]=1.
            z=(tx-mean)/scale
            dist=np.sum((z[:,None,:]-z[None,:,:])**2,axis=2)
            K=.04*np.exp(-.5*dist/spec['length_scale']**2)+.0025*np.eye(len(z))
            alpha=np.linalg.solve(K,ty)
            qx=np.concatenate([_features(q)[0] for q in queries]);qz=(qx-mean)/scale
            d=np.sum((qz[:,None,:]-z[None,:,:])**2,axis=2)
            expected=(.04*np.exp(-.5*d/spec['length_scale']**2)@alpha).reshape(3,60)+np.array([_features(q)[1] for q in queries])[:,None]
            delta=float(np.max(abs(expected-pred)));diffs[spec['id']]=delta
            check(spec['id']+' independent dense GP solve',delta<1e-11)
    check('all four candidates use one training data digest',len({m.metadata['training_digest'] for m in models.values()})==1)
    model=models['gp_rbf07']
    def altered_train(change):
        data=copy.deepcopy(train);change(data);return fit_model(data,candidate_specs()[2],5000,seed=5)
    reject('postnotice prefix rejected',lambda:altered_train(lambda d:d[0]['reference_window']['pre_ends_min'].__setitem__(-1,d[0]['reference_window']['notice_min']+1)))
    reject('non-event label mandatory',lambda:altered_train(lambda d:d[0].update(non_event=False)))
    reject('announced non-event forbidden',lambda:altered_train(lambda d:d[0].update(incentive_signal_announced=True)))
    reject('late label rejected',lambda:altered_train(lambda d:d[0]['availability'].update(power_records_available_at_min=5001)))
    reject('premature label availability rejected',lambda:altered_train(lambda d:d[0]['availability'].update(power_records_available_at_min=0)))
    reject('bool training label rejected',lambda:altered_train(lambda d:d[0]['power_kw'].__setitem__(0,True)))
    reject('non-event historical sources mandatory',lambda:altered_train(lambda d:d[0]['reference_window'].update(prior_sources_non_event=False)))
    reject('renamed physical duplicate rejected',lambda:altered_train(lambda d:d.append(dict(d[0],reference_window=dict(d[0]['reference_window'],task_id='renamed_duplicate')))))
    reject('training user cannot query',lambda:predict_model(model,[dict(reference_window=dict(queries[0]['reference_window'],user_id='old_0'))]))
    reject('fit after notice rejected',lambda:predict_model(model,[dict(reference_window=dict(queries[0]['reference_window'],task_start_min=1000,task_end_min=1030,notice_min=985,starts_min=list(np.arange(985.,1045.)),ends_min=list(np.arange(986.,1046.)),pre_starts_min=list(np.arange(925.,985.)),pre_ends_min=list(np.arange(926.,986.)),pre_available_min=985,prior_available_min=900,calendar_available_min=984,temperature_available_min=984))]))
    reject('unknown spec rejected',lambda:fit_model(train,dict(id='gp_rbf07',family='gaussian_process',length_scale=.7001),5000))
    broken=copy.deepcopy(model);broken.gp_alpha[:]=-1e6
    reject('negative prediction explicit, never clipped',lambda:predict_model(broken,queries))
    artifact=json.loads((out/'gp_rbf07/model.json').read_text(encoding='utf-8'))
    artifact['sha256']='0'*64
    bad=out/'corrupt_checksum.json';bad.write_text(json.dumps(artifact),encoding='utf-8')
    reject('serialization corruption rejected',lambda:load_model(bad))
    receipt=dict(scope='constructed micro-controls only; no study cohort or truth fitting',
        passed=len(checks),checks=checks,independent_gp_max_abs_difference=diffs,
        feature_names=list(FEATURE_NAMES),training_facts=12,query_facts=3,
        seconds=time.perf_counter()-tick,
        formal_feature_or_response_comparison=False,new_prediction_algorithm=False)
    (out/'receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps(dict(passed=len(checks),seconds=receipt['seconds'],gp_diffs=diffs)))


if __name__=='__main__':run()
