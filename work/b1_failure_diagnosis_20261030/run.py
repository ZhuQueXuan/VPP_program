"""Paired root-cause ablations. No production files or old outputs are edited."""
from pathlib import Path
import os
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
import sys,json,hashlib,time
from concurrent.futures import ProcessPoolExecutor,as_completed
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];OLD=ROOT/'work/b1_ev_mainline_20261030'
sys.path.insert(0,str(ROOT/'B1算法'))
from b1_api import ReferenceWindow,load_reference_model,predict_reference
from b1_algorithm.api import _default_runtime_config
from b1_algorithm.process.api import prepare,cases_for,complete
from b1_algorithm.process._cpop import fit_cases
from b1_algorithm.process import _ride_identify as identify,_ride_template as template

def read(path):return json.loads(path.read_text(encoding='utf-8'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as stream:json.dump(value,stream,ensure_ascii=False,indent=2,allow_nan=False)
def clean_json(value):
    if isinstance(value,dict):return {k:clean_json(v) for k,v in value.items()}
    if isinstance(value,(tuple,list)):return [clean_json(v) for v in value]
    if isinstance(value,np.ndarray):return clean_json(value.tolist())
    if isinstance(value,(float,np.floating)):return float(value) if np.isfinite(value) else None
    if isinstance(value,np.integer):return int(value)
    if isinstance(value,np.bool_):return bool(value)
    return value

def data_for(row,truth,level):
    task=dict(row['task']);start=task['start_min'];task.update(start_min=0.,end_min=30.,notice_min=-15.)
    s=np.asarray(row['starts_min'])-start;e=np.asarray(row['ends_min'])-start
    natural=np.asarray(truth['true_reference_kw']);p=np.asarray(row['power_kw'] if level=='oracle_noise' else truth['noiseless_power_kw']).copy()
    if level=='no_post_rebound':p[s>=30.]=natural[s>=30.]
    config=dict(max_charge_kw=7.2)
    if level=='relaxed_rebound':config['template_rebound_max_ratio']=1.5
    return prepare(s,e,p,natural,task,.05,config)

def score(output,data,truth,seed,scenario,level,method,shape):
    row=dict(seed=seed,scenario=scenario,level=level,method=method,shape=shape,task_id=truth['task_id'],
        status=output['status'],true_duration=truth['cumulative_response_seconds'])
    if output['status'] not in ('ok','degraded'):return row
    target=np.asarray(truth['true_reduction_kw']).copy();s=np.asarray(truth['relative_starts_min']);use=(s>=0)&(s<30)
    if level=='no_post_rebound':target[s>=30.]=0
    curve=np.asarray(output['reduction_interval_kw']);features=output['features']['selected_curve'];raw=output['features']['raw_observed']
    error=features['cumulative_response_seconds']-truth['cumulative_response_seconds'];zero=truth['cumulative_response_seconds']==0
    row.update(curve_rmse=float(np.sqrt(np.mean((curve[use]-target[use])**2))),duration_error=float(error),duration_mae=abs(float(error)),
        raw_duration_mae=abs(raw['cumulative_response_seconds']-truth['cumulative_response_seconds']),
        no_action=int(zero),false_detection=int(zero and features['cumulative_response_seconds']>0),response=int(not zero),
        miss=int(not zero and features['cumulative_response_seconds']==0),
        post_rmse=float(np.sqrt(np.mean((curve[s>=30]-target[s>=30])**2))),
        eta_error=float(output['eta_raw']-truth['eta']),fallback=int(output['status']=='degraded'),
        selected_structure=output.get('selection_evidence',{}).get('structure'))
    if data is not None:row['fit_RSS']=float(np.sum((curve-data['y'])**2))
    return row

def event_input(data):
    p=data['profile']
    return identify.EventInput(s=data['starts'],e=data['ends'],r=data['y'],q=data['q'],W=data['W'],obs_end=float(data['ends'][-1]),
        a_max=p.template_level_max_ratio,b_max=p.template_rebound_max_ratio,sigma=data['sigma'],sB=0.,delta=data['delta'],is_ev=1,event_id=0,
        ramp_limit_min=p.template_ramp_max_min,release_limit_min=p.template_release_max_min,rebound_limit_min=p.template_rebound_max_min)

def near_step_witness(truth):
    r=np.asarray(truth['true_reduction_kw']);s=np.asarray(truth['relative_starts_min']);q=truth['q_kw'];W=truth['W_min']
    positive=np.flatnonzero((s>=0)&(s<W)&(r>0));amplitude=float(r[positive].max())
    first,last=positive[0],positive[-1]
    start=float(s[first]+1-r[first]/amplitude);end=float(s[last]+r[last]/amplitude)
    b=1.8/q;duration=float(np.sum(r[(s>=0)&(s<W)])/1.8)
    theta=np.array([start,0.,amplitude/q,W-start,0.,b,duration,end-start,W-end])
    return theta

def run_seed(seed):
    model=load_reference_model(ROOT/'work/b1_formal_v1_20261029/reference/artifact');selections=read(OLD/f'reference/{seed}_selection.json')
    runtime=_default_runtime_config();runtime.update(artifact_dir=str(HERE/'native'/str(seed)),timeout_seconds=180)
    rows=[];details={};reference_errors=[];probes=[]
    for scenario in ('positive','zero'):
        facts=read(ROOT/f'data/B1_EV_mainline_v1_20261030/{seed}_{scenario}_facts.json')[:32]
        truths=read(OLD/f'evaluator/{seed}_{scenario}_truth.json')[:32]
        old={m:read(OLD/f'events/{seed}_{scenario}_{m}.json')[:32] for m in ('ride_template','cpop')}
        for i,(row,truth) in enumerate(zip(facts,truths)):
            assert row['task']['task_id']==truth['task_id']==old['ride_template'][i]['task']['task_id']
            pred=predict_reference(model,ReferenceWindow(**row['reference_window']),method=selections[i]['method'])
            s=np.asarray(truth['relative_starts_min']);use=(s>=0)&(s<30);err=pred.reference_kw-np.asarray(truth['true_reference_kw'])
            reference_errors.append(dict(seed=seed,scenario=scenario,task_id=truth['task_id'],mae=float(np.mean(abs(err[use]))),bias=float(err[use].mean()),shape=truth['latent']['shape']))
            for method in old:
                output=old[method][i]['process'];rows.append(score(output,None,truth,seed,scenario,'selected_noise',method,truth['latent']['shape']))
        for level in ('oracle_noise','oracle_clean','no_post_rebound','relaxed_rebound'):
            dataset=[data_for(f,t,level) for f,t in zip(facts,truths)]
            if level!='relaxed_rebound':
                cases=[]
                for i,data in enumerate(dataset):cases.extend(cases_for(data,base=i,include_cv=False))
                native,backend=fit_cases(cases,runtime)
                assert backend['status']=='ok',backend
                cpop=[complete(data,native,base=i,policy='cpop',backend=backend) for i,data in enumerate(dataset)]
            else:
                # Only an RIDE parameter changes; CPOP input and settings are
                # exactly oracle_clean, hence reuse the same stored output.
                cpop=details[f'{scenario}_oracle_clean_cpop']
            ride=[complete(data,{},policy='ride_template') for data in dataset]
            for method,outputs in [('ride_template',ride),('cpop',cpop)]:
                details[f'{scenario}_{level}_{method}']=outputs
                for out,data,truth in zip(outputs,dataset,truths):rows.append(score(out,data,truth,seed,scenario,level,method,truth['latent']['shape']))
        if scenario=='positive':
            indices=[i for i,t in enumerate(truths) if t['latent']['shape']=='near_step' and t['cumulative_response_seconds']>0][:2]
            for index in indices:
                truth=truths[index];data=data_for(facts[index],truth,'relaxed_rebound');ev=event_input(data);theta=near_step_witness(truth)
                witness=ev.q*template.interval_average(theta,ev.W,ev.s,ev.e)
                assert np.max(abs(witness-data['y']))<1e-10
                lb,ub=identify._bounds(ev,2);assert np.all(theta>=lb-1e-9) and np.all(theta<=ub+1e-9)
                records=[]
                for nstarts in (3,12):
                    output=identify.identify_event(ev,structures=(0,1,2),n_starts=nstarts,ci_method='none',lr_crit=None,seed=711)
                    th=np.array([output['th_'+name] for name in template.PARAM_NAMES_M2])
                    fitted=ev.q*template.interval_average(th,ev.W,ev.s,ev.e) if output['A_hat'] else np.zeros(len(ev.s))
                    mask=(ev.s>=0)&(ev.s<30)&(fitted>=.15)
                    records.append(dict(minimum_starts=nstarts,bic1=output['bic1'],bic2=output['bic2'],structure=output['struct'],
                        fitted_RSS=float(np.sum((fitted-ev.r)**2)),duration_error=float(mask.sum()*60-truth['cumulative_response_seconds']),
                        m2_RSS=float((output['bic2']-9*np.log(len(ev.r)))*ev.sigma**2)))
                probes.append(dict(seed=seed,task_id=truth['task_id'],witness_theta=theta.tolist(),witness_RSS=float(np.sum((witness-data['y'])**2)),
                    witness_feasible_in_relaxed_bounds=True,witness_bic2=float(9*np.log(len(ev.r))),fits=records))
    write(HERE/f'blocks/{seed}.json',clean_json(dict(rows=rows,reference_errors=reference_errors,probes=probes)))
    write(HERE/f'curves/{seed}.json',clean_json(details));print('completed diagnostic seed',seed,flush=True)
    return rows,reference_errors,probes

def controls(runtime):
    s=np.arange(-15.,45.);e=s+1.;W=30.;q=1.5;rng=np.random.default_rng(6382100)
    cases={
        'M1_immediate_rebound':[1.,1.,.8,15.,1.,.6,10.,0.,0.],
        'M1_release_at_task_end':[1.,2.,.8,27.,1.,.6,10.,0.,0.],
        'M2_end_gap_delayed_rebound':[1.,0.,.8,29.,0.,.6,10.,16.,13.],
        'M2_internal_gap_immediate_rebound':[1.,1.,.8,20.,1.,.6,10.,8.,3.],
    }
    inputs=[];truths=[];labels=[]
    for name,theta in cases.items():
        truth=q*template.interval_average(np.array(theta),W,s,e)
        for noise in (False,True):
            observed=truth+rng.uniform(-np.sqrt(3)*.05,np.sqrt(3)*.05,len(s)) if noise else truth.copy()
            task=dict(task_id=name+str(noise),user_id='control-user',meter_id='control-meter',start_min=0.,end_min=W,notice_min=-15.,request_kw=q)
            inputs.append(prepare(s,e,3.5-observed,np.full(len(s),3.5),task,.05,dict(max_charge_kw=7.2)))
            truths.append(truth);labels.append((name,noise))
    native,backend=fit_cases([case for i,d in enumerate(inputs) for case in cases_for(d,base=i,include_cv=False)],runtime)
    rows=[]
    for i,(data,truth,(name,noise)) in enumerate(zip(inputs,truths,labels)):
        use=(s>=0)&(s<W);target=float(np.sum(use&(truth>=.15))*60)
        for method in ('ride_template','cpop'):
            out=complete(data,native,base=i,policy=method,backend=backend);curve=np.array(out['reduction_interval_kw'])
            rows.append(dict(control=name,noisy=noise,method=method,status=out['status'],curve_rmse=float(np.sqrt(np.mean((curve[use]-truth[use])**2))),
                duration_mae=abs(out['features']['selected_curve']['cumulative_response_seconds']-target),
                fitted_RSS=float(np.sum((curve-data['y'])**2)),structure=out['selection_evidence'].get('structure')))
    write(HERE/'positive_controls.json',rows)

def main():
    if (HERE/'diagnosis_receipt.json').exists() or (HERE/'source_freeze.json').exists():raise RuntimeError('do not overwrite/restart frozen diagnosis')
    protocol=read(HERE/'protocol.json');start=time.perf_counter()
    source={p.relative_to(ROOT).as_posix():sha(p) for p in (ROOT/'B1算法').rglob('*') if p.is_file()}
    source.update({p.relative_to(ROOT).as_posix():sha(p) for p in (HERE/'protocol.json',HERE/'run.py',OLD/'simulation.py')})
    write(HERE/'source_freeze.json',source)
    rows=[];refs=[];probes=[]
    with ProcessPoolExecutor(max_workers=4) as executor:
        pending={executor.submit(run_seed,seed):seed for seed in protocol['seeds']}
        for future in as_completed(pending):
            values=future.result();rows.extend(values[0]);refs.extend(values[1]);probes.extend(values[2])
    pd.DataFrame(rows).to_csv(HERE/'diagnostic_metrics.csv',index=False);pd.DataFrame(refs).to_csv(HERE/'reference_metrics.csv',index=False)
    write(HERE/'optimization_probes.json',clean_json(probes))
    runtime=_default_runtime_config();runtime.update(artifact_dir=str(HERE/'native/controls'),timeout_seconds=180);controls(runtime)
    assert all(sha(ROOT/name)==value for name,value in source.items())
    write(HERE/'diagnosis_receipt.json',dict(completed=True,diagnostic_factual_variants=512,independent_blocks=8,
        process_metric_rows=len(rows),optimization_probe_cases=len(probes),positive_control_cases=8,
        old_outputs_modified=False,production_source_modified=False,model_adopted=False,
        data_are_seen_diagnostic_not_new_test=True,elapsed_seconds=time.perf_counter()-start))
    print('completed diagnosis',time.perf_counter()-start,flush=True)
if __name__=='__main__':main()
