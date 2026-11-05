"""Shared input/feature comparison; one frozen mixed-structure candidate."""
from common import *
from candidate import propose_edges,cache_blocks,choose_partition
def summary_rows(rows,methods):
    answer=[]
    for method in methods:
      for condition in ['all','gaussian','gaussian_plus_spikes']:
        for kind in ['all']+read('protocol.json')['simulation']['kinds']:
            rr=[r for r in rows if r['method']==method and (condition=='all' or r['condition']==condition) and (kind=='all' or r['kind']==kind)]
            if not rr:continue
            valid=[r for r in rr if r['status']=='ok'];d={'method':method,'condition':condition,'kind':kind,'n':len(rr),'available':len(valid),'unavailable':len(rr)-len(valid)}
            if valid:
                for key in ['primary_seconds','cumulative_error_seconds','longest_error_seconds','fp_minutes','fn_minutes','peak_error_kw','mean_error_kw','post_rebound_fitted_error_kwh','seconds','jump_count']:
                    d[key]=float(np.mean([r[key] for r in valid]))
                for key in ['curve_mse_kw2','task_curve_mse_kw2']:d[key.replace('mse_kw2','rmse_kw')]=float(np.sqrt(np.mean([r[key] for r in valid])))
                for key in ['null_false_positive','threshold_positive','whole_miss','onset_status_disagreement','target_status_disagreement','recovery_status_disagreement']:d[key]=int(sum(r[key] for r in valid))
                for key in ['onset_error_seconds','target_error_seconds','recovery_error_seconds']:
                    v=[r[key] for r in valid if r[key] is not None];d[key]=float(np.mean(v)) if v else None;d[key+'_n']=len(v)
            answer.append(d)
    return answer
def method_for(ratio):return 'jump_'+str(ratio).replace('.','p')
def execute(stage):
    if stage=='test':
        f=read('validation_freeze.json')
        for p,h in f['source_sha256'].items():assert sha(ROOT/p)==h,p
        for p,h in f['production_sha256'].items():assert sha(ROOT/p)==h,p
        ratios=[f['selected_ratio']]
    else:ratios=read('protocol.json')['candidate']['active_jump_ratio_grid']
    cases=read(f'facts/{stage}.json');cp=[];cache_input=[];proposals={};proposal_times={}
    for i,c in enumerate(cases):
        s=np.asarray(c['starts'],float);e=np.asarray(c['ends'],float);y=np.asarray(c['reference_kw'])-np.asarray(c['power_kw']);x=(s+e)/2
        cp.append({'case_id':i,'starts':s,'ends':e,'y':y,'sigma':c['sigma'],'train':np.ones(len(y),bool)})
        tic=time.perf_counter();p=propose_edges(y,x,c['sigma'],c['command_kw']);proposal_times[i]=time.perf_counter()-tic;proposals[i]=p
        cache_input.append({'case_id':i,'x':x,'y':y,'sigma':c['sigma'],'proposal':p})
    write(f'outputs/{stage}_proposals.json',[{'task_id':c['task']['task_id'],'proposal':proposals[i]} for i,c in enumerate(cases)])
    original,ometa=fit_cases(cp,runtime(f'native/{stage}_original'));assert ometa['status']=='ok',ometa
    caches,cachemeta=cache_blocks(cache_input,f'native/{stage}_blocks')
    # The original CPOP family is literally the full cached block.
    maxdiff=0.
    for i,c in enumerate(cases):
        full=caches[i][f"0:{len(cp[i]['y'])}"]
        if full['status']=='ok' and original[i]['status']=='ok':
            diff=float(np.max(np.abs(np.asarray(full['prediction'])-np.asarray(original[i]['prediction']))));maxdiff=max(maxdiff,diff)
            assert diff<1e-7 and abs(full['cost']-original[i]['native_cost'])<1e-6
    labs,lmeta=labs_batch([c['y'] for c in cp],f'labs/{stage}')
    out={};methods=['cpop']+[method_for(r) for r in ratios]+['labs']
    for i,c in enumerate(cases):
        out[i]={'cpop':original[i],'labs':labs[i]}
        for ratio in ratios:
            tic=time.perf_counter();fit=choose_partition(proposals[i],caches[i],c['sigma'],len(cp[i]['y']),ratio)
            fit['seconds']=proposal_times[i]+sum(r.get('seconds',0) for r in caches[i].values())+time.perf_counter()-tic
            out[i][method_for(ratio)]=fit
    write(f'outputs/{stage}_block_cache.json',[{'task_id':c['task']['task_id'],'blocks':caches[i]} for i,c in enumerate(cases)])
    write(f'outputs/{stage}_curves.json',[{'task_id':c['task']['task_id'],'base_task_id':c['base_task_id'],'condition':c['condition'],'results':out[i]} for i,c in enumerate(cases)])
    # Estimation has finished; now and only now read evaluator truth.
    truths=read(f'evaluator/{stage}.json');kernel=load_module(PREVIOUS/'run_synthetic.py','_audited_unchanged_feature_metrics');rows=[]
    for i,(c,t) in enumerate(zip(cases,truths)):
        assert c['task']['task_id']==t['task_id']
        for method in methods:
            fit=out[i][method];r=kernel.one_metric(c,t,fit,method)
            r.update(condition=c['condition'],base_task_id=c['base_task_id'],jump_count=len(fit.get('jump_boundaries',[])))
            rows.append(r)
    summary=summary_rows(rows,methods)
    write(f'outputs/{stage}_metrics.json',rows);write(f'outputs/{stage}_summary.json',summary)
    write(f'outputs/{stage}_runtime.json',{'original':ometa,'block_search':cachemeta,'labs':lmeta,'native_full_cache_max_curve_difference':maxdiff,
        'candidate_seconds_include_all_blocks_not_only_selected':True,'not_exclusive_single_case_latency':True})
    if stage=='validation':
        candidates=[r for r in summary if r['method'].startswith('jump_') and r['kind']==r['condition']=='all' and r['unavailable']==0]
        minimum=min(r['primary_seconds'] for r in candidates)
        chosen=max((r for r in candidates if r['primary_seconds']<=minimum+1e-9),key=lambda r:float(r['method'][5:].replace('p','.')))
        ratio=float(chosen['method'][5:].replace('p','.'))
        paths=[HERE/p for p in ['common.py','candidate.py','blocks_batch.R','labs_batch.R','protocol.json','simulation.py','controls.py','run_synthetic.py']]
        paths += [V1/'simulation.py',PREVIOUS/'simulation.py',PREVIOUS/'run_synthetic.py',PREVIOUS/'vendor/LABS/LABS_functions.R']
        protected=read('protected_before.json')
        write('validation_freeze.json',{'selected_method':chosen['method'],'selected_ratio':ratio,'validation_primary_seconds':chosen['primary_seconds'],
           'source_sha256':{p.relative_to(ROOT).as_posix():sha(p) for p in paths},
           'production_sha256':{p:h for p,h in protected.items() if p.startswith('B1算法/')},
           'test_not_generated_yet':not (HERE/'facts/test.json').exists(),'adoption_not_implied':True,
           'selection':read('protocol.json')['selection']})
    print(json.dumps([{k:r[k] for k in ['method','condition','primary_seconds','curve_rmse_kw','whole_miss','available','jump_count']} for r in summary if r['kind']=='all'],ensure_ascii=False),flush=True)
if __name__=='__main__':execute(sys.argv[1])
