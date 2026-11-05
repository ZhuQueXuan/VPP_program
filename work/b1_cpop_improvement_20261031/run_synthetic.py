"""Fit first, then open evaluator truths; bounded validation freezes before test."""
from common import *
from candidate import observation_weights
def old_metrics():
    path=PREVIOUS/'run_synthetic.py'
    spec=importlib.util.spec_from_file_location('_unchanged_feature_metric_kernel',path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    return m
def summarize(rows,methods):
    answer=[]
    for method in methods:
      for condition in ['all','gaussian','gaussian_plus_spikes']:
        for kind in ['all']+read('protocol.json')['simulation']['kinds']:
            rr=[r for r in rows if r['method']==method and (condition=='all' or r['condition']==condition) and (kind=='all' or r['kind']==kind)]
            if not rr:continue
            valid=[r for r in rr if r['status']=='ok'];d={'method':method,'condition':condition,'kind':kind,'n':len(rr),'available':len(valid),'unavailable':len(rr)-len(valid)}
            if valid:
                for k in ['primary_seconds','cumulative_error_seconds','longest_error_seconds','fp_minutes','fn_minutes','peak_error_kw','mean_error_kw','post_rebound_fitted_error_kwh','seconds','flagged_count']:
                    d[k]=float(np.mean([r[k] for r in valid]))
                for k in ['curve_mse_kw2','task_curve_mse_kw2']:d[k.replace('mse_kw2','rmse_kw')]=float(np.sqrt(np.mean([r[k] for r in valid])))
                for k in ['null_false_positive','threshold_positive','whole_miss','onset_status_disagreement','target_status_disagreement','recovery_status_disagreement']:d[k]=int(sum(r[k] for r in valid))
                for k in ['onset_error_seconds','target_error_seconds','recovery_error_seconds']:
                    v=[r[k] for r in valid if r[k] is not None];d[k]=float(np.mean(v)) if v else None;d[k+'_n']=len(v)
            answer.append(d)
    return answer
def execute(stage):
    if stage=='test':
        frozen=read('validation_freeze.json')
        for p,h in frozen['source_sha256'].items():assert sha(ROOT/p)==h,p
        kappas=[frozen['selected_kappa']]
    else:kappas=[3.,4.,5.]
    cases=read(f'facts/{stage}.json');methods=['cpop']+[f'candidate_k{int(k)}' for k in kappas]+['labs']
    cp=[];weighted=[];weights={};out={i:{} for i in range(len(cases))}
    for i,c in enumerate(cases):
        s=np.asarray(c['starts'],float);e=np.asarray(c['ends'],float);y=np.asarray(c['reference_kw'])-np.asarray(c['power_kw'])
        cp.append({'case_id':i,'starts':s,'ends':e,'y':y,'sigma':c['sigma'],'train':np.ones(len(y),bool)})
        for j,k in enumerate(kappas):
            record=observation_weights(y,c['sigma'],c['command_kw'],kappa=k)
            ident=i*len(kappas)+j;weights[ident]=record
            weighted.append({'case_id':ident,'starts':s,'ends':e,'y':y,'sigma_vector':record['sigma_vector']})
    original,cpmeta=fit_cases(cp,runtime(f'native/{stage}_original'));assert cpmeta['status']=='ok',cpmeta
    changed,wmeta=weighted_batch(weighted,f'native/{stage}_weighted')
    labs,lmeta=labs_batch([c['y'] for c in cp],f'labs/{stage}')
    for i,c in enumerate(cases):
        out[i]['cpop']=original.get(i,{'status':'unavailable'});out[i]['labs']=labs[i]
        for j,k in enumerate(kappas):
            ident=i*len(kappas)+j;r=changed[ident];r['weight_diagnostics']=weights[ident]
            out[i][f'candidate_k{int(k)}']=r
    # The truth file is not opened until every algorithm has finished fitting.
    write(f'outputs/{stage}_curves.json',[{'task_id':c['task']['task_id'],'base_task_id':c['base_task_id'],
          'condition':c['condition'],'results':out[i]} for i,c in enumerate(cases)])
    truths=read(f'evaluator/{stage}.json');kernel=old_metrics();rows=[]
    for i,(c,t) in enumerate(zip(cases,truths)):
        assert c['task']['task_id']==t['task_id']
        for method in methods:
            result=out[i][method];r=kernel.one_metric(c,t,result,method)
            r.update(condition=c['condition'],base_task_id=c['base_task_id'],
                 flagged_count=len(result.get('weight_diagnostics',{}).get('flagged_points',[])))
            if r['status']=='ok' and method.startswith('candidate') and out[i]['cpop']['status']=='ok':
                x=kernel.get_feature(kernel.data_for(c),out[i]['cpop']['prediction'])['cumulative_response_seconds']
                z=r['features']['cumulative_response_seconds']
                r['unvalidated_duration_sensitivity_range_seconds']=[min(x,z),max(x,z)]
                r['sensitivity_range_is_confidence_interval']=False
            rows.append(r)
    summary=summarize(rows,methods)
    write(f'outputs/{stage}_metrics.json',rows);write(f'outputs/{stage}_summary.json',summary)
    write(f'outputs/{stage}_runtime.json',{'original':cpmeta,'weighted':wmeta,'labs':lmeta,'not_exclusive_single_case_latency':True})
    if stage=='validation':
        candidates=[r for r in summary if r['condition']==r['kind']=='all' and r['method'].startswith('candidate') and r['unavailable']==0]
        chosen=min(candidates,key=lambda r:(r['primary_seconds'],-int(r['method'][-1])))
        paths=[HERE/p for p in ['common.py','candidate.py','protocol.json','simulation.py','run_synthetic.py','weighted_cpop_batch.R','labs_batch.R','controls.py']]
        paths+=[PREVIOUS/'simulation.py',PREVIOUS/'run_synthetic.py',PREVIOUS/'vendor/LABS/LABS_functions.R']
        protected=read('protected_before.json');prod={p:h for p,h in protected.items() if p.startswith('B1算法/')}
        write('validation_freeze.json',{'selected_kappa':float(chosen['method'][-1]),'selected_method':chosen['method'],
            'validation_primary_seconds':chosen['primary_seconds'],'source_sha256':{p.relative_to(ROOT).as_posix():sha(p) for p in paths},
            'production_sha256':prod,'test_not_generated_yet':not (HERE/'facts/test.json').exists(),
            'selection_rule':read('protocol.json')['selection'],'source_selection_not_adoption':True})
    print(json.dumps([r for r in summary if r['kind']=='all'],ensure_ascii=False),flush=True)
if __name__=='__main__':execute(sys.argv[1])
