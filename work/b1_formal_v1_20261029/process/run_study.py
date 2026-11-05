from pathlib import Path
from datetime import datetime,timezone
import hashlib,importlib.util,json,sys,time
import numpy as np
import pandas as pd
from dgp import shape,truth_average

ROOT=Path(__file__).resolve().parent;PROJECT=ROOT.parents[2];FORMAL=PROJECT/'b1_algorithm/process'
def package(name,path):
    spec=importlib.util.spec_from_file_location(name,path/'__init__.py',submodule_search_locations=[str(path)])
    mod=importlib.util.module_from_spec(spec);sys.modules[name]=mod;spec.loader.exec_module(mod);return mod
formal=package('b1_formal_process_study',FORMAL)
engine=sys.modules['b1_formal_process_study.api']
native=sys.modules['b1_formal_process_study._cpop']
template=sys.modules['b1_formal_process_study._template_fit']
old=package('b1_previous_process_baselines',PROJECT/'work/b1_mainline_20261029/process')
oldapi=sys.modules['b1_previous_process_baselines.api']
oldmodels=sys.modules['b1_previous_process_baselines.models']
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
TASK=dict(task_id='process-study',user_id='synthetic-user',meter_id='synthetic-meter',start_min=0.,end_min=30.,request_kw=1.5,notice_min=-15.)
CONFIG=dict(rscript_path=str(PROJECT/'work/b1_mainline_20261029/runtime/R-4.6.1/app/bin/Rscript.exe'),
            r_library=str(PROJECT/'work/b1_mainline_20261029/runtime/r_library'),timeout_seconds=1200)

def run(mode):
    out=ROOT/mode;out.mkdir(exist_ok=True)
    if (out/'freeze.json').exists():raise RuntimeError('study already started; do not overwrite')
    protocol=json.loads((ROOT/'protocol.json').read_text(encoding='utf-8'))
    seeds=protocol['development_seeds'] if mode=='development' else protocol['test_seeds']
    shipped=json.loads((FORMAL/'_policy.json').read_text(encoding='utf-8'))
    if mode=='test' and shipped['version']=='development_pending':raise RuntimeError('development admission must complete before test')
    frozen=dict(utc=datetime.now(timezone.utc).isoformat(),protocol_sha256=sha(ROOT/'protocol.json'),
                code_sha256={p.name:sha(p) for p in FORMAL.iterdir() if p.is_file()},
                evaluator_sha256=sha(__file__),policy=shipped,no_test_tuning=True)
    (out/'freeze.json').write_text(json.dumps(frozen,ensure_ascii=False,indent=2),encoding='utf-8')
    datasets=[];case_list=[];meta=[];curves={};event=0
    for rep,seed in enumerate(seeds):
        for mech in protocol['mechanisms']:
            sh=shape(seed,mech)
            for dt in protocol['delta_minutes']:
                s=np.arange(-15,45-1e-8,dt);e=s+dt;mu=truth_average(sh,s,e)
                rng=np.random.default_rng(seed+event*13+1729);z=rng.normal(size=len(s))
                for sigma in protocol['sigma_kw']:
                    y=mu+sigma*z;b=np.full(len(s),3.)
                    task=dict(TASK,task_id=f'event-{event}',user_id=f'block-{rep}')
                    data=engine.prepare(s,e,b-y,b,task,sigma)
                    datasets.append(data);case_list.extend(engine.cases_for(data,base=event*10,include_cv=True))
                    meta.append(dict(event_id=event,rep=rep,seed=seed,mechanism=mech,delta_min=round(dt,10),sigma_kw=sigma))
                    curves[f'{event}_truth']=mu;curves[f'{event}_raw']=y;event+=1
    np.savez_compressed(out/'observations.npz',**curves)
    (out/'events.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
    tic=time.perf_counter()
    results,backend=native.fit_cases(case_list,dict(CONFIG,artifact_dir=str(out/'native_calls')))
    (out/'backend.json').write_text(json.dumps(backend,indent=2),encoding='utf-8')
    if backend['status']!='ok':raise RuntimeError('formal study requires actual original CPOP')
    native_arrays={str(k):v['prediction'] for k,v in results.items() if v.get('status')=='ok'}
    np.savez_compressed(out/'native_predictions.npz',**native_arrays)
    (out/'native_elapsed.json').write_text(json.dumps({'seconds':time.perf_counter()-tic,'cases':len(case_list),'variants':len(datasets)}),encoding='utf-8')
    metrics=[];outputs=[];tic=time.perf_counter()
    for data,m in zip(datasets,meta):
        i=m['event_id'];base=i*10;dt=data['delta'];y=data['y'];mu=curves[f'{i}_truth'];req=(data['starts']>=-1e-9)&(data['starts']<30-1e-9)
        conservative=engine.complete(data,results,base=base,policy='conservative')
        guarded=engine.complete(data,results,base=base,policy='guarded')
        unified=guarded if shipped['default']=='guarded' else conservative
        original=results[base]
        baseline_ride,_=oldapi.ride_fit(y,dt,data['sigma'])
        f1,_=oldmodels.original_f1(y,dt,data['sigma'])
        rows=[('unified_default',unified['reduction_interval_kw'],unified['method'],unified['reason']),
              ('guarded_diagnostic',guarded['reduction_interval_kw'],guarded['method'],guarded['reason']),
              ('conservative',conservative['reduction_interval_kw'],conservative['method'],conservative['reason']),
              ('original_CPOP',original['prediction'],'CPOP','original_default_grid'),
              ('RIDE_original',baseline_ride,'RIDE','original_unchanged_candidate'),
              ('raw_F0',y,'raw_F0','raw_rule'),('frozen_F1',f1,'F1','frozen_DP_with_phase_adapter')]
        fulltemplate=template.fit_template(data['starts'],data['ends'],y,data['sigma'])
        if fulltemplate.get('status')=='ok':rows.append(('new_template_candidate',fulltemplate['prediction'],'new_template','success_aware_finite_fit'))
        else:rows.append(('new_template_candidate',None,'unavailable',fulltemplate['reason']))
        for name,pred,chosen,reason in rows:
            rmse=None if pred is None else float(np.sqrt(np.mean((np.asarray(pred)[req]-mu[req])**2)))
            metrics.append(dict(m,method=name,chosen=chosen,reason=reason,request_rmse=rmse,
                                eta_raw=conservative['eta_raw'],status='unavailable' if pred is None else 'ok'))
            if pred is not None:curves[f'{i}_{name}']=np.asarray(pred,float)
        outputs.append(dict(m,unified_method=unified['method'],guarded_method=guarded['method'],
                            guarded_reason=guarded['reason'],selection_evidence=guarded['selection_evidence']))
        if (i+1)%48==0:print(mode,'completed',i+1,'of',len(datasets),'template seconds',time.perf_counter()-tic,flush=True)
    df=pd.DataFrame(metrics);df.to_csv(out/'metrics.csv',index=False)
    np.savez_compressed(out/'curves.npz',**curves)
    (out/'decisions.json').write_text(json.dumps(outputs,indent=2),encoding='utf-8')
    df.groupby(['method','delta_min']).agg(mean_request_rmse=('request_rmse','mean'),n_valid=('request_rmse','count'),n_total=('event_id','size')).reset_index().to_csv(out/'summary.csv',index=False)
    pivot=df.pivot(index=['rep','mechanism','delta_min','sigma_kw'],columns='method',values='request_rmse')
    comparisons=[]
    for candidate in ['unified_default','guarded_diagnostic']:
        for comparator in ['conservative','original_CPOP','RIDE_original','raw_F0','frozen_F1']:
            for resolution in ['all',round(1/6,10),1.,15.]:
                sub=pivot if resolution=='all' else pivot.xs(resolution,level='delta_min')
                diff=(sub[candidate]-sub[comparator]).groupby(level='rep').mean();se=float(diff.std(ddof=1)/np.sqrt(len(diff)))
                comparisons.append(dict(candidate=candidate,comparator=comparator,delta=resolution,blocks=len(diff),
                                         mean_difference=diff.mean(),mc95_low=diff.mean()-2.093*se,mc95_high=diff.mean()+2.093*se,
                                         wins=int((diff<0).sum())))
    pd.DataFrame(comparisons).to_csv(out/'paired.csv',index=False)
    receipt=dict(mode=mode,variants=len(datasets),independent_blocks=len(seeds),n_metric_rows=len(df),
                 all_main_methods_finite=df[df.method!='new_template_candidate'].request_rmse.notna().all().item(),
                 native_case_count=len(case_list),native_seconds=json.loads((out/'native_elapsed.json').read_text())['seconds'],
                 template_seconds=time.perf_counter()-tic,guarded_chosen_counts=pd.Series([x['guarded_method'] for x in outputs]).value_counts().to_dict(),
                 shipped_policy=shipped,main_code_unchanged=all(sha(FORMAL/name)==h for name,h in frozen['code_sha256'].items()))
    (out/'receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(receipt,indent=2),flush=True)

def admit():
    df=pd.read_csv(ROOT/'development/metrics.csv')
    table=df.pivot(index=['rep','event_id'],columns='method',values='request_rmse')
    differences=(table.guarded_diagnostic-table.conservative).groupby(level='rep').mean()
    relative=1-table.guarded_diagnostic.mean()/table.conservative.mean()
    approved=bool((differences<=1e-12).all() and relative>=.01)
    policy=dict(version='formal-process-v1',default='guarded' if approved else 'conservative',guarded_admitted=approved,
                reason='development_prespecified_admission_passed' if approved else 'development_did_not_establish_required_gain',
                development_relative_rmse_improvement=float(relative),development_block_differences=differences.tolist(),
                admission_rule='6of6_nonworse_and_at_least1percent_aggregate_gain',development_metrics_sha256=sha(ROOT/'development/metrics.csv'))
    if json.loads((FORMAL/'_policy.json').read_text())['version']!='development_pending':raise RuntimeError('policy already frozen')
    (FORMAL/'_policy.json').write_text(json.dumps(policy,indent=2),encoding='utf-8')
    (ROOT/'development_admission.json').write_text(json.dumps(policy,indent=2),encoding='utf-8')
    print(json.dumps(policy,indent=2))

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['development','admit','test']);a=parser.parse_args()
    admit() if a.phase=='admit' else run(a.phase)
