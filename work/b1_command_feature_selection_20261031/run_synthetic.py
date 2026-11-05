"""Shared conditions and features; estimators never receive simulation truth."""
from common import *
from concurrent.futures import ProcessPoolExecutor,as_completed
from sklearn.covariance import LedoitWolf
import common
METHODS=['raw_features','ride_original','ride_revised','tf_standard','tf_gls','cpop','labs_2026']
def data_for(case):
    return prepare(case['starts'],case['ends'],case['power_kw'],case['reference_kw'],case['task'],case['sigma'],
       {'max_charge_kw':7.2,'revised_rebound_bound_policy':'declared_headroom'})
def fit_templates(item):
    i,case=item;data=data_for(case);out={}
    for method,fn in [('ride_original',fit_original_ride),('ride_revised',fit_revised_ride)]:
        start=time.perf_counter();r=fn(data);r['seconds']=time.perf_counter()-start
        out[method]=native(r)
    return i,out
def get_feature(data,pred):return common._features(data,np.asarray(pred))['selected_curve']
def one_metric(case,truth,result,method):
    base={'task_id':case['task']['task_id'],'seed':case['seed'],'kind':case['kind'],'method':method,
          'status':result['status'],'seconds':result.get('seconds',0.)}
    if result['status']!='ok':return {**base,'reason':result.get('reason',result.get('error'))}
    data=data_for(case);pred=np.asarray(result['prediction']);clean=np.asarray(truth['true_reduction_kw'])
    est=get_feature(data,pred);actual=get_feature(data,clean)
    req=slice(15,45);a=clean[req]>=.15;b=pred[req]>=.15
    dc=abs(est['cumulative_response_seconds']-actual['cumulative_response_seconds'])
    dl=abs(est['longest_continuous_response_seconds']-actual['longest_continuous_response_seconds'])
    out={**base,'features':est,'true_features':actual,'primary_seconds':.5*(dc+dl),'cumulative_error_seconds':dc,
         'longest_error_seconds':dl,'fp_minutes':int(np.sum(b&~a)),'fn_minutes':int(np.sum(a&~b)),
         'null_false_positive':case['kind']=='null' and bool(b.any()),'threshold_positive':bool(a.any()),
         'whole_miss':bool(a.any() and not b.any()),'curve_mse_kw2':float(np.mean((pred-clean)**2)),
         'task_curve_mse_kw2':float(np.mean((pred[req]-clean[req])**2)),
         'peak_error_kw':float(abs(np.max(pred[req])-np.max(clean[req]))),
         'mean_error_kw':float(abs(np.mean(pred[req])-np.mean(clean[req]))),
         'post_rebound_fitted_error_kwh':float(abs(np.maximum(-pred[45:],0).sum()-np.maximum(-clean[45:],0).sum())/60),
         'raw_eta':float(np.sum(data['y'][req])/(1.5*30))}
    for key in ['onset_interval_s','target_interval_s']:
        p=est[key];t=actual[key];label=key.replace('_interval_s','')
        out[label+'_status_disagreement']=(p is None)!=(t is None)
        out[label+'_both_present']=p is not None and t is not None
        out[label+'_error_seconds']=abs(p[0]-t[0]) if out[label+'_both_present'] else None
    p=est['power_recovery_time_s'];t=actual['power_recovery_time_s']
    out['recovery_status_disagreement']=(p is None)!=(t is None)
    out['recovery_error_seconds']=abs(p-t) if p is not None and t is not None else None
    return out
def summarize(rows):
    answer=[]
    for method in METHODS:
      for kind in ['all']+read('protocol.json')['simulation']['kinds']:
        group=[r for r in rows if r['method']==method and (kind=='all' or r['kind']==kind)]
        valid=[r for r in group if r['status']=='ok'];n=len(valid)
        if not group:continue
        d={'method':method,'kind':kind,'total':len(group),'available':n,'unavailable':len(group)-n}
        if n:
            for k in ['primary_seconds','cumulative_error_seconds','longest_error_seconds','fp_minutes','fn_minutes','peak_error_kw','mean_error_kw','post_rebound_fitted_error_kwh','seconds']:
                d[k]=float(np.mean([r[k] for r in valid]))
            d['curve_rmse_kw']=float(np.sqrt(np.mean([r['curve_mse_kw2'] for r in valid])))
            d['task_curve_rmse_kw']=float(np.sqrt(np.mean([r['task_curve_mse_kw2'] for r in valid])))
            for k in ['null_false_positive','whole_miss','threshold_positive','onset_status_disagreement','target_status_disagreement','recovery_status_disagreement']:
                d[k]=int(sum(r[k] for r in valid))
            for k in ['onset_error_seconds','target_error_seconds','recovery_error_seconds']:
                v=[r[k] for r in valid if r[k] is not None];d[k]=float(np.mean(v)) if v else None;d[k+'_n']=len(v)
        answer.append(d)
    return answer
def develop():
    spec=read('protocol.json')['simulation']['noise_development'];rng=np.random.default_rng(spec['seed'])
    residuals=rng.normal(0,.05,(spec['users'],60))
    cov=LedoitWolf().fit(residuals)
    write('noise_development.json',{'residuals':residuals,'scalar_variance':float(np.mean(residuals**2)),
          'covariance':cov.covariance_,'shrinkage':float(cov.shrinkage_),
          'known_baseline':True,'predictor_used':False,'source':'Independent non-event observed-meter errors only'})
def execute(stage):
    cases=read(f'facts/{stage}.json');errors=read('noise_development.json')
    if stage=='test':
        f=read('validation_freeze.json')
        for name,value in f['source_sha256'].items():assert sha(HERE/name)==value
        for rel,value in f['production_sha256'].items():assert sha(ROOT/rel)==value
    out={i:{'raw_features':{'status':'ok','prediction':np.asarray(c['reference_kw'])-np.asarray(c['power_kw']),'seconds':0.}} for i,c in enumerate(cases)}
    start=time.perf_counter()
    with ProcessPoolExecutor(max_workers=4) as pool:
      futures=[pool.submit(fit_templates,(i,c)) for i,c in enumerate(cases)]
      for done,future in enumerate(as_completed(futures),1):
        i,result=future.result();out[i].update(result)
        if done%16==0:print(stage,'templates',done,'/',len(cases),flush=True)
    template_wall=time.perf_counter()-start
    cp_cases=[]
    for i,c in enumerate(cases):
        data=data_for(c);cp_cases.append({'case_id':i,'starts':data['starts'],'ends':data['ends'],'y':data['y'],'sigma':data['sigma'],'train':np.ones(60,bool)})
        for method,variance,penalty in [('tf_standard',errors['scalar_variance'],4),('tf_gls',np.asarray(errors['covariance']),2)]:
            tic=time.perf_counter();fit=fit_curve(data['y'],variance,penalty);fit['seconds']=time.perf_counter()-tic
            out[i][method]=fit
    native,backend=fit_cases(cp_cases,runtime(f'native/{stage}'))
    assert backend['status']=='ok',backend
    labs,labmeta=labs_batch([x['y'] for x in cp_cases],f'labs/{stage}')
    for i in range(len(cases)):out[i]['cpop']=native.get(i,{'status':'unavailable'});out[i]['labs_2026']=labs[i]
    # Estimation is complete before evaluator truth is opened.
    write(f'outputs/{stage}_curves.json',[{'task_id':cases[i]['task']['task_id'],'results':out[i]} for i in range(len(cases))])
    truths=read(f'evaluator/{stage}.json');assert len(truths)==len(cases)
    metrics=[]
    for i,c in enumerate(cases):
        assert c['task']['task_id']==truths[i]['task_id']
        for method in METHODS:metrics.append(one_metric(c,truths[i],out[i][method],method))
    summary=summarize(metrics)
    write(f'outputs/{stage}_metrics.json',metrics);write(f'outputs/{stage}_summary.json',summary)
    write(f'outputs/{stage}_runtime.json',{'template_wall_seconds':template_wall,'CP_backend':backend,'LABS':labmeta,'parallel_workers':4,'times_not_exclusive_single_latency':True})
    if stage=='validation':
        choices=[r for r in summary if r['kind']=='all' and r['method'] not in ('raw_features','cpop') and r['unavailable']==0]
        chosen=min(choices,key=lambda r:(r['primary_seconds'],r['seconds']))
        paths=['protocol.json','common.py','simulation.py','run_synthetic.py','labs_batch.R','noise_development.json','vendor/LABS/LABS_functions.R']
        production=read('protected_before.json')
        write('validation_freeze.json',{'selected_candidate':chosen['method'],'validation_primary_seconds':chosen['primary_seconds'],
              'source_sha256':{p:sha(HERE/p) for p in paths},
              'production_sha256':{p:h for p,h in production.items() if p.startswith('B1算法/') or p.endswith('trend_filter.py')},
              'all_method_results_retained':True,'test_not_generated_yet':not (HERE/'facts/test.json').exists(),
              'selection_rule':read('protocol.json')['selection_rule']})
    print(json.dumps([r for r in summary if r['kind']=='all'],ensure_ascii=False),flush=True)
if __name__=='__main__':
    if sys.argv[1]=='develop':develop()
    else:execute(sys.argv[1])
