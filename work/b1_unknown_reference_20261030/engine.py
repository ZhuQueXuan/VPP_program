"""Evaluation harness only; formal running source remains in B1算法/."""
from pathlib import Path
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[key] = '1'
import dataclasses, hashlib, importlib.util, json, sys
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = ROOT / 'B1算法'
RIDE = ROOT / 'work/ride_b1_v02_reproduction_20261029/source/ride_b1'
sys.path.insert(0,str(SOURCE)); sys.path.insert(0,str(RIDE))
from b1_algorithm.reference import ReferenceWindow, ReferenceTrainingRecord, fit_reference, predict_reference, save_reference_model
from b1_algorithm.process import api as process
from b1_algorithm.process import _cpop as native
from b1_algorithm.api import _default_runtime_config as runtime_config
from ride.config import SimConfig, ObsConfig
from ride.simulate import simulate, observe, true_baseline_at

def load_module(name,path,package=False):
    spec=importlib.util.spec_from_file_location(name,path/'__init__.py' if package else path,
         submodule_search_locations=[str(path)] if package else None)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    return module

old = load_module('_unknown_reference_old_process',ROOT/'work/b1_mainline_20261029/process',True)
oldapi=sys.modules['_unknown_reference_old_process.api']
dgp=load_module('_unknown_reference_shapes',ROOT/'work/b1_formal_v1_20261029/process/dgp.py')
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()

def adjust_pre15(predicted,power,starts,ends):
    use=(starts>=-30)&(ends<=-15)
    assert use.sum()==15 and np.all(ends[use]<=-15)
    shift=float(np.mean(np.asarray(power,float)[use]-np.asarray(predicted,float)[use]))
    return np.maximum(0.,np.asarray(predicted,float)+shift),shift

def user_roles(users,seed):
    users=np.random.default_rng(seed+5).permutation(sorted(set(users)))
    return dict(train=users[:40],selection=users[40:56],calibration=users[56:68],test=users[68:])

def window(obs,i,uid,tid,start,prior,prefix,temperature,weekday,sources):
    lead=float(obs.meta['lead'].iat[i]);notice=start-lead
    pre=obs.ends<=-lead+1e-9
    return ReferenceWindow(task_id=tid,user_id=uid,meter_id='meter-'+uid,resource_type='EV',
        task_start_min=start,task_end_min=start+30.,request_kw=1.5,notice_min=notice,
        starts_min=start+obs.starts,ends_min=start+obs.ends,
        pre_starts_min=start+obs.starts[pre],pre_ends_min=start+obs.ends[pre],pre_power_kw=prefix[pre],
        pre_available_min=notice,prior_mean_kw=prior,prior_available_min=notice-1.,
        prior_source_count=len(sources),prior_source_ids=tuple(sources),clock_hour=float(obs.meta['hour'].iat[i]),
        weekday=int(weekday),calendar_available_min=notice-1.,temperature_c=float(temperature),temperature_available_min=notice-1.)

def generate(seed,out,data_dir):
    sim=simulate(SimConfig(n_users=80,n_events_per_user=2,ev_share=1.,window_choices=(30.,30.),
        dt0=1.,L_post=90.,n_donors=1,seed=seed))
    obs=observe(sim,ObsConfig(delta=1.,sigma=.15,p_missing=0.,seed=seed+3))
    roles=user_roles(obs.meta['user'],seed)
    records=[];ledger=[]
    for i in np.flatnonzero(obs.meta['user'].isin(roles['train']).to_numpy()):
        uid=f'{seed}-u{obs.meta["user"].iat[i]}'
        for j in range(2,10):
            start=100000.+1440*j;tid=f'{seed}-history-{i}-{j}'
            sources=[f'{seed}-history-{i}-{k}' for k in range(j)]
            w=window(obs,i,uid,tid,start,obs.Hist[i,:j].mean(0),obs.Hist[i,j],
                obs.day_meta['hist_temp'][i,j],obs.day_meta['hist_weekday'][i,j],sources)
            completed=float(max(w.ends_min));latest_prior=100000.+1440*(j-1)+90
            assert latest_prior < w.notice_min and completed<=120000.
            records.append(ReferenceTrainingRecord(w,obs.Hist[i,j],completed,True))
            ledger.append(dict(task_id=tid,user_id=uid,start_min=start,end_of_data_min=completed,
                latest_prior_end_min=latest_prior,notice_min=w.notice_min,sources=sources))
    model=fit_reference(records,120000.,seed)
    model_dir=out/f'model_{seed}';save_reference_model(model,model_dir)
    candidates=obs.meta[obs.meta['user'].isin(roles['test']) & np.isclose(obs.meta['lead'],15.)].sort_values('event_id')
    selected=candidates.drop_duplicates('user').index.to_numpy()[:2]
    btrue=true_baseline_at(sim,1.,'B').astype(float)
    use=(obs.starts>=-15)&(obs.ends<=45);s=obs.starts[use].astype(float);e=obs.ends[use].astype(float)
    blobs={};contexts=[]
    for order,i in enumerate(selected):
        start=300000.+1440*int(i);uid=f'{seed}-u{obs.meta["user"].iat[i]}'
        tid=f'{seed}-context-{i}'
        w=window(obs,i,uid,tid,start,obs.Hist[i].mean(0),obs.P[i],obs.meta['temp'].iat[i],
                 obs.meta['weekday'].iat[i],[f'{seed}-history-{i}-{j}' for j in range(10)])
        prediction=predict_reference(model,w)
        assert prediction.reference_status=='available',prediction.reasons
        assert uid not in model.training_users
        pre=(obs.starts>=-30)&(obs.ends<=-15)
        assert pre.sum()==15
        adjusted,shift=adjust_pre15(prediction.reference_kw,obs.P[i],obs.starts,obs.ends)
        references=dict(oracle_diagnostic=btrue[i,use],fixed_gbdt=prediction.reference_kw[use],
                        gbdt_pre15_shift=adjusted[use])
        rng=np.random.default_rng(seed+50000+int(i));noise=rng.normal(0.,.15,len(s))
        base=btrue[i,use]
        blobs[f'{order}_baseline']=base;blobs[f'{order}_noise']=noise
        blobs[f'{order}_prefix']=obs.P[i,pre].astype(float)
        blobs[f'{order}_prefix_prediction']=prediction.reference_kw[pre]
        blobs[f'{order}_full_prediction']=prediction.reference_kw
        blobs[f'{order}_full_meter']=obs.P[i].astype(float)
        for name,ref in references.items():blobs[f'{order}_ref_{name}']=ref
        contexts.append(dict(seed=seed,context=int(order),source_event=int(i),user_id=uid,task_id=tid,
            shift_kw=shift,adjustment_floor_bins=int(np.sum(prediction.reference_kw[use]+shift<0)),model_id=model.model_id,references=references,baseline=base,noise=noise,s=s,e=e,
            query_notice_min=w.notice_min,fit_cutoff_min=model.fit_cutoff_min))
    data_dir.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(data_dir/f'contexts_{seed}.npz',starts=s,ends=e,**blobs)
    # Full observable historical panel permits independent training reconstruction.
    np.savez_compressed(data_dir/f'history_{seed}.npz',Hist=obs.Hist,P=obs.P,
        hist_temp=obs.day_meta['hist_temp'],hist_weekday=obs.day_meta['hist_weekday'],starts=obs.starts,ends=obs.ends)
    obs.meta.to_csv(data_dir/f'metadata_{seed}.csv',index=False)
    (out/f'ledger_{seed}.json').write_text(json.dumps(dict(seed=seed,roles={k:list(map(int,v)) for k,v in roles.items()},
        training=ledger,selected=[{k:v for k,v in c.items() if k not in ('references','baseline','noise','s','e')} for c in contexts],
        selected_contexts=len(contexts),shortfall=2-len(contexts),availability='explicit synthetic chronological declarations'),indent=2),encoding='utf-8')
    return contexts

def datasets(contexts):
    arrays={};entries=[];cases=[]
    for c in contexts:
        for shape_index,mechanism in enumerate(('none','partial','slow','multiplateau')):
            desired=dgp.truth_average(dgp.shape(c['seed']+c['source_event']*37,mechanism),c['s'],c['e'])
            target=np.minimum(desired,c['baseline'])
            assert np.all(target>=0) and np.all(c['baseline']-target>=-1e-12)
            power=c['baseline']-target+c['noise']
            identity=f'{c["seed"]}_{c["context"]}_{mechanism}'
            arrays[identity+'_truth']=target;arrays[identity+'_power']=power
            for reference,ref in c['references'].items():
                index=len(entries)
                task=dict(task_id=identity,user_id=c['user_id'],meter_id='m-'+c['user_id'],
                          start_min=0.,end_min=30.,notice_min=-15.,request_kw=1.5)
                data=process.prepare(c['s'],c['e'],power,ref,task,.15)
                cases.extend(process.cases_for(data,index*10,True))
                entries.append(dict(index=index,seed=c['seed'],context=c['context'],mechanism=mechanism,
                    reference=reference,user_id=c['user_id'],identity=identity,data=data,target=target,
                    baseline=c['baseline'],shift_kw=c['shift_kw'],adjustment_floor_bins=c['adjustment_floor_bins']))
    return entries,cases,arrays

def feature_values(data,curve):
    return process._features(data,np.asarray(curve))['selected_curve']

def score(entry,curve,method,chosen):
    data=entry['data'];target=entry['target'];req=(data['starts']>=0)&(data['ends']<=30)
    features=feature_values(data,curve);truth=feature_values(data,target)
    def point(feat,key):
        value=feat[key]
        return None if value is None else (float(value[1]) if isinstance(value,list) else float(value))
    onset=point(features,'onset_interval_s');true_onset=point(truth,'onset_interval_s')
    recovery=point(features,'power_recovery_time_s');true_recovery=point(truth,'power_recovery_time_s')
    raw_eta=float(np.mean(data['y'][req])/1.5);true_eta=float(np.mean(target[req])/1.5)
    meta={k:entry[k] for k in ('index','seed','context','mechanism','reference','user_id','identity','shift_kw','adjustment_floor_bins')}
    return dict(meta,method=method,chosen=chosen,status='ok',curve_rmse_kw=float(np.sqrt(np.mean((np.asarray(curve)[req]-target[req])**2))),
        onset_detected=onset is not None,truth_onset_detected=true_onset is not None,
        onset_abs_error_s=None if onset is None or true_onset is None else abs(onset-true_onset),
        recovery_detected=recovery is not None,truth_recovery_detected=true_recovery is not None,
        recovery_abs_error_s=None if recovery is None or true_recovery is None else abs(recovery-true_recovery),
        eta_raw=raw_eta,eta_true=true_eta,eta_error=raw_eta-true_eta,
        reference_bias_kw=float(np.mean((data['reference']-entry['baseline'])[req])))
