"""Saved-only independent candidate, native block-cost, partition and metrics audit.

No production/candidate/generator/optimizer imports and no R calls. Reuses only
the earlier independent audit's pure threshold metrics, never estimator code.
"""
import sys,json,csv,hashlib,math,importlib.util
from pathlib import Path
from collections import defaultdict,Counter
import numpy as np
HERE=Path(__file__).resolve().parents[1];ROOT=HERE.parents[1]
HELPER=ROOT/'work/b1_cpop_improvement_20261031/audit/independent_synthetic.py'
spec=importlib.util.spec_from_file_location('_independent_old_threshold_audit',HELPER)
helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
independent_metrics=helper.metrics;independent_features=helper.features
hashes={};checks=Counter();maximum=0.;cost_maximum=0.;dp_maximum=0.;partitions=0
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(name):
    path=Path(name);path=path if path.is_absolute() else HERE/path
    hashes[path.relative_to(ROOT).as_posix()]=sha(path)
    return json.loads(path.read_text(encoding='utf-8'))
def table(path):
    path=Path(path);hashes[path.relative_to(ROOT).as_posix()]=sha(path)
    with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def check(v,label):
    assert v,label
    checks[label]+=1
def close(a,b,label,tol=1e-8):
    global maximum
    if a is None or b is None:check(a is None and b is None,label);return
    x=np.asarray(a,float);y=np.asarray(b,float);check(x.shape==y.shape,label+' shape')
    delta=float(np.max(np.abs(x-y))) if x.size else 0.;maximum=max(maximum,delta)
    check(np.isfinite(x).all() and np.isfinite(y).all() and delta<=tol*max(1.,float(np.max(np.abs(y))) if y.size else 1.),label)
def proposal(y,x,sigma,command):
    n=len(y);pitch=np.median(np.diff(x));records=[]
    for j in range(1,n):
        center=(x[j-1]+x[j])/2;scores=[]
        for width in [1,2,4]:
            if width>j or j+width>n:continue
            if width==1:value=abs(y[j]-y[j-1])/(sigma*np.sqrt(2))
            else:
                estimates=[];variances=[]
                for ix in [np.arange(j-width,j),np.arange(j,j+width)]:
                    t=(x[ix]-center)/pitch;z=y[ix];tm=t.mean();zm=z.mean()
                    ss=np.sum((t-tm)**2);slope=np.sum((t-tm)*(z-zm))/ss
                    estimates.append(zm-slope*tm);variances.append(1/width+tm*tm/ss)
                value=abs(estimates[0]-estimates[1])/(sigma*np.sqrt(sum(variances)))
            scores.append({'width':width,'score':float(value)})
        records.append({'index':j,'score':max(s['score'] for s in scores),'scales':scores})
    observed=[r['index'] for r in sorted(records,key=lambda r:(-r['score'],r['index']))[:6]]
    commanded=[i for i in range(1,n) if abs(command[i]-command[i-1])>1e-12]
    edges=sorted(set(observed+commanded))
    return {'nodes':[0]+edges+[n],'edges':edges,'observational_edges':observed,'command_edges':commanded,'all_boundary_scores':records}
def replay_segment(rr,x):
    if len(x)==1:return [float(rr[0]['intercept'])]
    segs=[r for r in rr if float(r['x1'])>float(r['x0'])];answer=[]
    for t in x:
        found=[r for r in segs if float(r['x0'])-1e-9<=t<=float(r['x1'])+1e-9]
        r=found[-1] if found else (segs[0] if t<float(segs[0]['x0']) else segs[-1])
        answer.append(float(r['gradient'])*t+float(r['intercept']))
    return answer
def enumerate_partitions(nodes,cache,beta):
    global partitions
    edges=nodes[1:-1];entries=[]
    for mask in range(1<<len(edges)):
        path=[nodes[0]]+[e for j,e in enumerate(edges) if mask&(1<<j)]+[nodes[-1]]
        cost=sum(cache[f'{a}:{b}']['cost'] for a,b in zip(path,path[1:]))
        entries.append((cost,len(path)-2,path));partitions+=1
    return entries
def native_dictionary(stage,facts,caches):
    global cost_maximum
    mapping={};block_total=0
    for folder in sorted((HERE/'native'/(stage+'_blocks')).glob('chunk_*')):
        inp=defaultdict(list)
        for r in table(folder/'input.csv'):inp[int(r['case_id'])].append(r)
        blockdefs={int(r['block_id']):r for r in table(folder/'blocks.csv')}
        native=defaultdict(list)
        for r in table(folder/'segments.csv'):native[int(r['block_id'])].append(r)
        check(set(native)==set(blockdefs),'all native dictionary blocks present')
        for cid,rr in inp.items():
            c=facts[cid];y=np.asarray(c['reference_kw'])-np.asarray(c['power_kw']);x=(np.asarray(c['starts'])+np.asarray(c['ends']))/2
            close([float(r['y']) for r in rr],y,'block batch unchanged y')
            close([float(r['x']) for r in rr],x,'block native input time grid')
            close([float(r['sigma']) for r in rr],np.repeat(c['sigma'],len(y)),'block native original sigma')
            close([float(r['beta']) for r in rr],np.repeat(2*np.log(len(y)),len(y)),'global full-task beta every block')
            check([int(r['index']) for r in rr]==list(range(len(y))),'every original point in native input')
        for bid,definition in blockdefs.items():
            cid=int(definition['case_id']);a=int(definition['a']);b=int(definition['b']);r=caches[cid]['blocks'][f'{a}:{b}'];rr=native[bid]
            check(all(v['status']=='ok' for v in rr) and r['status']=='ok','all native blocks available')
            c=facts[cid];x=((np.asarray(c['starts'])+np.asarray(c['ends']))/2)[a:b]
            y=(np.asarray(c['reference_kw'])-np.asarray(c['power_kw']))[a:b]
            pred=replay_segment(rr,x);close(r['prediction'],pred,'cached native prediction replay')
            beta=2*np.log(len(c['power_kw']));sigma=c['sigma'];rss=float(np.sum(((np.asarray(pred)-y)/sigma)**2))
            cost=rss+beta*r['internal_knots'];delta=abs(cost-r['cost']);cost_maximum=max(cost_maximum,delta)
            close(r['cost'],cost,'native cost independently recomputed',2e-7)
            close(r['cost'],float(rr[0]['native_cost']),'same returned native block cost')
            close(r['beta'],beta,'cached global beta');close(r['sigma'],sigma,'cached unchanged sigma')
            check(r['n_points']==b-a and len(pred)==b-a,'block all points retained')
            if b-a<=2:check(r['internal_knots']==0 and r['cost']==0,'one/two point identifiable zero residual block')
            mapping[(cid,a,b)]=True;block_total+=1
    for i,row in enumerate(caches):
        check(all((i,*map(int,k.split(':'))) in mapping for k in row['blocks']),'saved cache complete native mapping')
    return block_total
def audit_stage(stage):
    global dp_maximum
    facts=read(f'facts/{stage}.json');truths=read(f'evaluator/{stage}.json')
    caches=read(f'outputs/{stage}_block_cache.json');proposals=read(f'outputs/{stage}_proposals.json')
    curves=read(f'outputs/{stage}_curves.json');rows=read(f'outputs/{stage}_metrics.json');summary=read(f'outputs/{stage}_summary.json')
    check(len(facts)==len(truths)==len(caches)==len(proposals)==len(curves),'stage task coverage')
    blockcount=native_dictionary(stage,facts,caches)
    ratios=[1.,1.5] if stage=='validation' else [read('validation_freeze.json')['selected_ratio']]
    methods=['cpop']+['jump_'+str(v).replace('.','p') for v in ratios]+['labs']
    check(len(rows)==len(facts)*len(methods),'complete metric row denominator')
    lookup={(r['task_id'],r['method']):r for r in rows};checked=[];etas=defaultdict(list);jumpstats=Counter()
    cpinputs=list((HERE/'native'/(stage+'_original')).glob('process_*/input.csv'));check(len(cpinputs)==1,'one original CP input')
    cpin=defaultdict(list)
    for r in table(cpinputs[0]):cpin[int(r['case_id'])].append(r)
    lin=defaultdict(list);lout=defaultdict(list)
    for r in table(HERE/'labs'/stage/'input.csv'):lin[int(r['case_id'])].append(float(r['y']))
    for r in table(HERE/'labs'/stage/'output.csv'):
        check(r['status']=='ok','LABS native status');lout[int(r['case_id'])].append(float(r['fitted']))
    for i,(c,t,p,cache_row,saved) in enumerate(zip(facts,truths,proposals,caches,curves)):
        ident=c['task']['task_id'];check(all(r['task_id']==ident for r in [t,p,cache_row,saved]),'all artifact task identities')
        y=np.asarray(c['reference_kw'])-np.asarray(c['power_kw']);x=(np.asarray(c['starts'])+np.asarray(c['ends']))/2;beta=2*np.log(len(y))
        check(len(y)==60,'common minute task shape')
        close([float(r['y']) for r in cpin[i]],y,'original CP same observed y')
        close([float(r['sigma']) for r in cpin[i]],np.repeat(c['sigma'],len(y)),'original CP same sigma')
        close(lin[i],y,'LABS same observed y')
        independent=proposal(y,x,c['sigma'],np.asarray(c['command_kw']));actual=p['proposal']
        for key in ['nodes','edges','observational_edges','command_edges']:check(independent[key]==actual[key],'independent proposal '+key)
        for a,b in zip(independent['all_boundary_scores'],actual['all_boundary_scores']):
            close(a['score'],b['score'],'independent multiscale max score')
            for aa,bb in zip(a['scales'],b['scales']):check(aa['width']==bb['width'],'same candidate widths');close(aa['score'],bb['score'],'independent local OLS score')
        cache=cache_row['blocks'];nodes=actual['nodes'];n=len(y)
        check(len(cache)==len(nodes)*(len(nodes)-1)//2,'complete pairwise interval dictionary')
        entries=enumerate_partitions(nodes,cache,beta);full=cache[f'0:{n}']
        baseline=saved['results']['cpop'];close(baseline['prediction'],full['prediction'],'zero-jump original CP literal inclusion')
        close(baseline['native_cost'],full['cost'],'zero-jump same native cost')
        minimum2=min(v+2*beta*j for v,j,path in entries)
        close(minimum2,full['cost'],'ratio2 dominated/no-jump control',2e-7)
        for method in methods:
            fit=saved['results'][method];check(fit['status']=='ok','all stage estimator outputs available')
            if method=='labs':close(fit['prediction'],lout[i],'original author LABS output replay')
            elif method.startswith('jump_'):
                ratio=float(method[5:].replace('p','.'));objectives=[v+ratio*beta*j for v,j,path in entries]
                minimum=min(objectives);delta=abs(fit['objective']-minimum);dp_maximum=max(dp_maximum,delta)
                close(fit['objective'],minimum,'exhaustive partition optimum',2e-7)
                path=[0]+fit['jump_boundaries']+[n]
                check(all(v in nodes for v in path),'selected path only fixed nodes')
                selectedcost=sum(cache[f'{a}:{b}']['cost'] for a,b in zip(path,path[1:]))+ratio*beta*(len(path)-2)
                close(fit['objective'],selectedcost,'selected additive objective')
                pred=np.concatenate([cache[f'{a}:{b}']['prediction'] for a,b in zip(path,path[1:])]);close(fit['prediction'],pred,'selected block concatenation')
                check(fit['selected_blocks']==[[a,b] for a,b in zip(path,path[1:])],'selected interval endpoints')
                check(fit['internal_slope_changes']==sum(cache[f'{a}:{b}']['internal_knots'] for a,b in zip(path,path[1:])),'slope count excludes jump reset count')
                close(fit['jump_cost'],ratio*beta,'jump boundary penalty')
                check(fit['zero_jump_CPOP_included'] and fit['values_and_weights_unchanged'],'no downweight/delete and nesting flags')
                check(fit['physical_subbin_timing_identified'] is False and fit['single_point_sensor_fault_disambiguated'] is False,'physical ambiguity retained')
                check(fit['objective']<=full['cost']+1e-6,'nested objective no worse than CP')
                jumpstats[(method,c['condition'],c['kind'])]+=len(path)-2
            calc,fp,ft=independent_metrics(c,t,fit['prediction'],method,fit.get('seconds',0),0)
            row=lookup[(ident,method)]
            for key,value in calc.items():
                if key=='flagged_count':continue
                if isinstance(value,str):check(row[key]==value,'metric status')
                else:close(row[key],value,'independent metric '+key)
            check(row['jump_count']==len(fit.get('jump_boundaries',[])),'jump count metric')
            close(row['features']['cumulative_response_seconds'],fp['cumulative'],'extracted cumulative')
            close(row['features']['longest_continuous_response_seconds'],fp['longest'],'extracted continuous duration')
            etas[ident].append(row['raw_eta']);checked.append(row)
        if c['kind']=='one_bin_response':check(np.count_nonzero(t['true_reduction_kw'])==1,'real one-bin truth preserved')
        if c['kind']=='one_bin_gap':check(np.sum(np.asarray(t['true_reduction_kw'])[16:45]==0)==1,'real gap truth preserved')
    check(all(len(v)==len(methods) and len(set(v))==1 for v in etas.values()),'raw eta invariant all methods')
    for s in summary:
        rr=[r for r in checked if r['method']==s['method'] and (s['condition']=='all' or r['condition']==s['condition']) and (s['kind']=='all' or r['kind']==s['kind'])]
        check(s['n']==s['available']==len(rr) and s['unavailable']==0,'summary full denominator')
        for key in ['primary_seconds','cumulative_error_seconds','longest_error_seconds','fp_minutes','fn_minutes','peak_error_kw','mean_error_kw','post_rebound_fitted_error_kwh','seconds','jump_count']:close(s[key],np.mean([r[key] for r in rr]),'summary '+key)
        for key in ['curve_mse_kw2','task_curve_mse_kw2']:close(s[key.replace('mse_kw2','rmse_kw')],np.sqrt(np.mean([r[key] for r in rr])),'pooled curve summary')
        for key in ['null_false_positive','threshold_positive','whole_miss','onset_status_disagreement','target_status_disagreement','recovery_status_disagreement']:check(s[key]==sum(r[key] for r in rr),'status summary '+key)
        for key in ['onset_error_seconds','target_error_seconds','recovery_error_seconds']:
            v=[r[key] for r in rr if r[key] is not None];check(s[key+'_n']==len(v),'time conditional denominator');close(s[key],np.mean(v) if v else None,'conditional time mean')
    return {'input_variants':len(facts),'base_tasks':len(facts)//2,'metric_rows':len(rows),'summary_groups':len(summary),'block_fits_checked':blockcount,'summary':summary,
            'jump_count_totals':[{'method':k[0],'condition':k[1],'kind':k[2],'jumps':v} for k,v in jumpstats.items()]}
def main():
    stage=sys.argv[1] if len(sys.argv)>1 else 'all';protocol=read('protocol.json');freeze=read('validation_freeze.json')
    hashes[HELPER.relative_to(ROOT).as_posix()]=sha(HELPER)
    check(protocol['candidate']['active_jump_ratio_grid']==[1.,1.5],'ratio2 excluded before validation selection')
    for path,digest in freeze['source_sha256'].items():check(sha(ROOT/path)==digest,'frozen source unchanged')
    for path,digest in freeze['production_sha256'].items():check(sha(ROOT/path)==digest,'production source unchanged')
    protected=read('protected_before.json');changed=[]
    for path,digest in protected.items():
        check((ROOT/path).is_file(),'protected file exists')
        if path!='AGENTS.md' and sha(ROOT/path)!=digest:changed.append(path)
    check(not changed,'all old scientific files unchanged')
    if stage=='test':
        old=read('audit/validation_audit.json');val=old['validation']
        for path,digest in old['input_sha256'].items():check(sha(ROOT/path)==digest,'validation audit inputs unchanged');hashes[path]=digest
    else:val=audit_stage('validation')
    eligible=[r for r in val['summary'] if r['method'].startswith('jump_') and r['condition']==r['kind']=='all']
    minimum=min(r['primary_seconds'] for r in eligible);chosen=max((r for r in eligible if r['primary_seconds']<=minimum+1e-9),key=lambda r:float(r['method'][5:].replace('p','.')))
    check(chosen['method']==freeze['selected_method'],'validation-only candidate selection')
    close(chosen['primary_seconds'],freeze['validation_primary_seconds'],'frozen validation score')
    check(freeze['test_not_generated_yet'] is True,'test generation after freeze declaration')
    result={'status':'passed','scope':'Independent read-only finite-dictionary, native cost/proposal/metric/selection audit; no estimator fit',
       'validation':val,'selected_method':freeze['selected_method'],'frozen_source_ok':True,'old_scientific_changed':changed,'no_estimator_called':True,'no_parameter_selection':True}
    if stage!='validation':
        check((HERE/'validation_freeze.json').stat().st_mtime<=(HERE/'facts/test.json').stat().st_mtime,'freeze precedes new test mtime')
        test=audit_stage('test');idx={(s['method'],s['condition'],s['kind']):s for s in test['summary']};candidate=freeze['selected_method']
        def g(method,cond,kind='all'):return idx[(method,cond,kind)]
        gates={'all_outputs_available':True,'all_primary_at_least10percent_better':g(candidate,'all')['primary_seconds']<=.9*g('cpop','all')['primary_seconds']}
        for cond in ['gaussian','gaussian_plus_spikes']:
            gates[cond+'_primary_within5s']=g(candidate,cond)['primary_seconds']<=g('cpop',cond)['primary_seconds']+5
            gates[cond+'_curve_within10percent']=g(candidate,cond)['curve_rmse_kw']<=1.1*g('cpop',cond)['curve_rmse_kw']
            gates[cond+'_null_false_within1']=g(candidate,cond,'null')['null_false_positive']<=g('cpop',cond,'null')['null_false_positive']+1
            for kind in ['one_bin_response','one_bin_gap']:
                gates[cond+'_'+kind+'_whole_misses_within1']=g(candidate,cond,kind)['whole_miss']<=g('cpop',cond,kind)['whole_miss']+1
        for kind in ['one_bin_response','one_bin_gap']:gates['gaussian_'+kind+'_primary_within15s']=g(candidate,'gaussian',kind)['primary_seconds']<=g('cpop','gaussian',kind)['primary_seconds']+15
        result.update(test=test,adoption_gates_recomputed=gates,passes_all_adoption_gates=all(gates.values()))
    for path,digest in hashes.items():check(sha(ROOT/path)==digest,'audit inputs unchanged during read')
    result.update({'checks':dict(checks),'n_checks':sum(checks.values()),'maximum_numeric_difference':maximum,
       'maximum_native_cost_absolute_difference':cost_maximum,'maximum_exhaustive_DP_absolute_difference':dp_maximum,
       'exhaustive_partitions_checked':partitions,'input_sha256':hashes,
       'limits':['Only fixed observed candidate dictionary, not all-location jump/ramp optimum','Free level+slope reset, not incoming-slope preservation',
       'Observation-grid continuity can interpolate a jump with two extra slopes; gamma2 is dominated control',
       'Known simulation reference and independent power-shape mechanism are not field net-reduction validation',
       'Paired artificial spike conditions do not add independent users','Audit checks are not performance sample sizes']})
    name='validation_audit.json' if stage=='validation' else 'independent_synthetic.json'
    with (HERE/'audit'/name).open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
    print(json.dumps({'status':'passed','checks':sum(checks.values()),'partitions':partitions,'max_native_cost_difference':cost_maximum,
           'max_DP_difference':dp_maximum,'stage':stage,'gates':result.get('adoption_gates_recomputed')},ensure_ascii=False))
if __name__=='__main__':main()
