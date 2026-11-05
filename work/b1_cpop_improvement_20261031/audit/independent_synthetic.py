"""Read-only independent weighting, native input/output, metrics and gates audit.

No candidate, generator, feature implementation, optimizer, or R is imported.
"""
import sys,json,csv,hashlib,math
from pathlib import Path
from collections import defaultdict,Counter
import numpy as np
HERE=Path(__file__).resolve().parents[1];ROOT=HERE.parents[1]
hashes={};checks=Counter();maximum=0.
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(name):
    path=HERE/name;hashes[path.relative_to(ROOT).as_posix()]=sha(path)
    return json.loads(path.read_text(encoding='utf-8'))
def table(path):
    path=Path(path);hashes[path.relative_to(ROOT).as_posix()]=sha(path)
    with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def check(test,label):
    assert test,label
    checks[label]+=1
def close(a,b,label,tol=1e-8):
    global maximum
    if a is None or b is None:check(a is None and b is None,label);return
    if isinstance(a,(bool,np.bool_)) or isinstance(b,(bool,np.bool_)):
        check(bool(a)==bool(b),label);return
    x=np.asarray(a,float);y=np.asarray(b,float)
    check(x.shape==y.shape,label+' shape')
    delta=float(np.max(np.abs(x-y))) if x.size else 0.
    maximum=max(maximum,delta)
    check(np.isfinite(x).all() and np.isfinite(y).all() and delta<=tol*max(1.,float(np.max(np.abs(y))) if y.size else 1.),label)
def independent_weights(y,sigma,command,kappa):
    y=np.asarray(y);command=np.asarray(command);n=len(y)
    protected={i for j in range(1,n) if abs(command[j]-command[j-1])>1e-12 for i in range(max(0,j-1),min(n,j+2))}
    scales=np.repeat(sigma,n);flagged=[]
    for i in range(2,n-2):
        if i in protected:continue
        a=y[i-2:i];b=y[i+1:i+3]
        if abs(np.median(a)-np.median(b))>2.5*sigma or max(a)-min(a)>3*sigma or max(b)-min(b)>3*sigma:continue
        neighbors=np.asarray([y[i-2],y[i-1],y[i+1],y[i+2]])
        center=float(np.median(neighbors));scale=max(sigma,1.482602218505602*np.median(np.abs(neighbors-center)))
        residual=float(y[i]-center)
        if abs(residual)>kappa*scale:
            scales[i]=max(sigma,abs(residual)/kappa);flagged.append(i)
    return scales,flagged,sorted(protected)
def features(y):
    y=np.asarray(y);a=y[15:45]>=.15
    longest=run=0
    for v in a:
        run=run+1 if v else 0;longest=max(longest,run)
    def first(level):
        ix=np.flatnonzero(y[15:45]>=level)
        return float(max(0,int(ix[0])-1)*60) if len(ix) else None
    onset=first(.15);target=first(1.35)
    post=np.flatnonzero(np.abs(y[45:])<=.15)
    recovery=float((30+int(post[0]))*60) if onset is not None and len(post) else None
    return {'cumulative':int(a.sum())*60.,'longest':longest*60.,'onset':onset,'target':target,'recovery':recovery,'mask':a}
def metrics(case,truth,pred,method,seconds,flags):
    pred=np.asarray(pred);clean=np.asarray(truth['true_reduction_kw'])
    p=features(pred);t=features(clean);pc=abs(p['cumulative']-t['cumulative']);pl=abs(p['longest']-t['longest'])
    req=slice(15,45);raw=np.asarray(case['reference_kw'])-np.asarray(case['power_kw'])
    m={'status':'ok','seconds':seconds,'flagged_count':flags,
       'primary_seconds':.5*(pc+pl),'cumulative_error_seconds':pc,'longest_error_seconds':pl,
       'fp_minutes':int(np.sum(p['mask']&~t['mask'])),'fn_minutes':int(np.sum(t['mask']&~p['mask'])),
       'null_false_positive':case['kind']=='null' and bool(p['mask'].any()),
       'threshold_positive':bool(t['mask'].any()),'whole_miss':bool(t['mask'].any() and not p['mask'].any()),
       'curve_mse_kw2':float(np.mean((pred-clean)**2)),
       'task_curve_mse_kw2':float(np.mean((pred[req]-clean[req])**2)),
       'peak_error_kw':float(abs(pred[req].max()-clean[req].max())),
       'mean_error_kw':float(abs(pred[req].mean()-clean[req].mean())),
       'post_rebound_fitted_error_kwh':float(abs(np.maximum(-pred[45:],0).sum()-np.maximum(-clean[45:],0).sum())/60),
       'raw_eta':float(raw[req].sum()/45)}
    for name in ['onset','target','recovery']:
        m[name+'_status_disagreement']=(p[name] is None)!=(t[name] is None)
        m[name+'_error_seconds']=abs(p[name]-t[name]) if p[name] is not None and t[name] is not None else None
    return m,p,t
def native_predictions(segment_path,n_expected):
    groups=defaultdict(list)
    for r in table(segment_path):groups[int(r['case_id'])].append(r)
    check(len(groups)==n_expected,'native segment case coverage')
    answer={}
    for i,rr in groups.items():
        check(all(r['status']=='ok' for r in rr),'native status ok')
        segs=[r for r in rr if float(r['x1'])>float(r['x0'])]
        vals=[]
        for x in np.arange(-14.5,45.,1.):
            matches=[r for r in segs if float(r['x0'])-1e-9<=x<=float(r['x1'])+1e-9]
            r=matches[-1] if matches else (segs[0] if x<float(segs[0]['x0']) else segs[-1])
            vals.append(float(r['gradient'])*x+float(r['intercept']))
        answer[i]=vals
    return answer
def audit_stage(stage):
    facts=read('facts/'+stage+'.json');truths=read('evaluator/'+stage+'.json')
    curves=read('outputs/'+stage+'_curves.json');savedmetrics=read('outputs/'+stage+'_metrics.json')
    summary=read('outputs/'+stage+'_summary.json')
    bymetric={(r['task_id'],r['method']):r for r in savedmetrics}
    kappas=[3.,4.,5.] if stage=='validation' else [read('validation_freeze.json')['selected_kappa']]
    methods=['cpop']+['candidate_k'+str(int(k)) for k in kappas]+['labs']
    check(len(facts)==len(truths)==len(curves),'case lengths match')
    check(len(savedmetrics)==len(facts)*len(methods),'full metric row coverage')
    origpaths=list((HERE/'native'/(stage+'_original')).glob('process_*/input.csv'))
    check(len(origpaths)==1,'one native original input')
    cpinput=defaultdict(list)
    for r in table(origpaths[0]):cpinput[int(r['case_id'])].append(r)
    winput=defaultdict(list)
    for r in table(HERE/'native'/(stage+'_weighted')/'input.csv'):winput[int(r['case_id'])].append(r)
    cpfit=native_predictions(origpaths[0].with_name('segments.csv'),len(facts))
    wfit=native_predictions(HERE/'native'/(stage+'_weighted')/'segments.csv',len(facts)*len(kappas))
    labsin=defaultdict(list);labsout=defaultdict(list)
    for r in table(HERE/'labs'/stage/'input.csv'):labsin[int(r['case_id'])].append(float(r['y']))
    for r in table(HERE/'labs'/stage/'output.csv'):
        check(r['status']=='ok','native LABS status');labsout[int(r['case_id'])].append(float(r['fitted']))
    recovered=[];etas={};flag_counts=Counter()
    for i,(c,t,s) in enumerate(zip(facts,truths,curves)):
        ident=c['task']['task_id'];check(ident==t['task_id']==s['task_id'],'task identity')
        check(c['base_task_id']==t['base_task_id']==s['base_task_id'],'paired task identity')
        y=np.asarray(c['reference_kw'])-np.asarray(c['power_kw']);command=np.asarray(c['command_kw'])
        close([float(r['x']) for r in cpinput[i]],np.arange(-14.5,45.),'native times minutes')
        close([float(r['y']) for r in cpinput[i]],y,'native CP same y')
        close([float(r['sigma']) for r in cpinput[i]],np.full(60,.05),'native CP scalar sigma')
        check(all(r['train']=='1' for r in cpinput[i]),'CP full input no hidden selected bins')
        close(labsin[i],y,'native LABS same y')
        for method in methods:
            result=s['results'][method];check(result['status']=='ok','all fits available')
            pred=np.asarray(result['prediction']);check(pred.shape==(60,),'native-length output')
            flags=0
            if method=='cpop':close(pred,cpfit[i],'original CP native output replay')
            elif method=='labs':close(pred,labsout[i],'LABS native output replay')
            else:
                j=methods.index(method)-1;key=i*len(kappas)+j;k=kappas[j]
                scales,flagged,protected=independent_weights(y,c['sigma'],command,k)
                diag=result['weight_diagnostics'];flags=len(flagged)
                close(diag['sigma_vector'],scales,'independent weight sigma')
                check([r['index'] for r in diag['flagged_points']]==flagged,'independent flagged positions')
                check(diag['protected_indices']==protected,'independent command protection')
                check(diag['short_action_disambiguation_available'] is False,'ambiguity openly retained')
                check(diag['source_values_preserved'] is True,'observations untouched flag')
                close([float(r['y']) for r in winput[key]],y,'weighted same actual y')
                close([float(r['x']) for r in winput[key]],np.arange(-14.5,45.),'weighted same time')
                close([float(r['sigma']) for r in winput[key]],scales,'native R vector sd matches screening')
                close(pred,wfit[key],'weighted native output replay')
                for r in diag['flagged_points']:
                    close(r['weight_ratio'],(.05/scales[r['index']])**2,'actual squared weight ratio')
                flag_counts[(method,c['condition'],c['kind'])]+=flags
            calc,p,truth=metrics(c,t,pred,method,result.get('seconds',0),flags)
            saved=bymetric[(ident,method)]
            for key,value in calc.items():
                if isinstance(value,str):check(saved[key]==value,'metric '+key)
                else:close(saved[key],value,'metric '+key)
            close(saved['features']['cumulative_response_seconds'],p['cumulative'],'saved extracted cumulative')
            close(saved['features']['longest_continuous_response_seconds'],p['longest'],'saved extracted longest')
            if method.startswith('candidate'):
                original=features(s['results']['cpop']['prediction'])['cumulative']
                close(saved['unvalidated_duration_sensitivity_range_seconds'],[min(original,p['cumulative']),max(original,p['cumulative'])],'sensitivity is comparison not CI')
                check(saved['sensitivity_range_is_confidence_interval'] is False,'not a validated CI')
            etas.setdefault(ident,[]).append(saved['raw_eta'])
            recovered.append({**saved,**calc})
        if c['kind']=='one_bin_response':
            check(int(np.count_nonzero(t['true_reduction_kw']))==1,'genuine one-bin action truth retained')
        if c['kind']=='one_bin_gap':
            check(np.sum(np.asarray(t['true_reduction_kw'])[16:45]==0)==1,'genuine one-bin gap truth retained')
    check(all(len(v)==len(methods) and len(set(v))==1 for v in etas.values()),'raw eta exact across methods')
    for s in summary:
        rr=[r for r in recovered if r['method']==s['method'] and (s['condition']=='all' or r['condition']==s['condition']) and (s['kind']=='all' or r['kind']==s['kind'])]
        check(len(rr)==s['n']==s['available'] and s['unavailable']==0,'summary full denominator')
        for key in ['primary_seconds','cumulative_error_seconds','longest_error_seconds','fp_minutes','fn_minutes','peak_error_kw','mean_error_kw','post_rebound_fitted_error_kwh','seconds','flagged_count']:
            close(s[key],np.mean([r[key] for r in rr]),'summary '+key)
        for key in ['curve_mse_kw2','task_curve_mse_kw2']:
            close(s[key.replace('mse_kw2','rmse_kw')],np.sqrt(np.mean([r[key] for r in rr])),'summary '+key)
        for key in ['null_false_positive','threshold_positive','whole_miss','onset_status_disagreement','target_status_disagreement','recovery_status_disagreement']:
            check(s[key]==sum(r[key] for r in rr),'summary '+key)
        for key in ['onset_error_seconds','target_error_seconds','recovery_error_seconds']:
            v=[r[key] for r in rr if r[key] is not None]
            check(s[key+'_n']==len(v),'conditional time denominator')
            close(s[key],np.mean(v) if v else None,'conditional time mean')
    return {'inputs':len(facts),'metric_rows':len(recovered),'summary_groups':len(summary),'all_available':True,'summary':summary,
            'flag_counts':[{'method':k[0],'condition':k[1],'kind':k[2],'flags':v} for k,v in flag_counts.items()]}
def main():
    protocol=read('protocol.json');freeze=read('validation_freeze.json')
    for path,digest in freeze['source_sha256'].items():check(sha(ROOT/path)==digest,'frozen source unchanged')
    for path,digest in freeze['production_sha256'].items():check(sha(ROOT/path)==digest,'frozen production source unchanged')
    protected=read('protected_before.json');changed=[]
    for path,digest in protected.items():
        check((ROOT/path).is_file(),'protected input still exists')
        if path=='AGENTS.md':continue
        if sha(ROOT/path)!=digest:changed.append(path)
    check(not changed,'old protected science unchanged')
    val=audit_stage('validation')
    eligible=[s for s in val['summary'] if s['method'].startswith('candidate') and s['condition']==s['kind']=='all']
    selected=min(eligible,key=lambda r:(r['primary_seconds'],-int(r['method'][-1])))
    check(selected['method']==freeze['selected_method'],'candidate selected only on validation')
    close(selected['primary_seconds'],freeze['validation_primary_seconds'],'validation frozen score')
    check(freeze['test_not_generated_yet'] is True,'test generated after validation freeze declaration')
    check((HERE/'validation_freeze.json').stat().st_mtime<=(HERE/'facts/test.json').stat().st_mtime,'mtime supports freeze before test')
    test=audit_stage('test');index={(s['method'],s['condition'],s['kind']):s for s in test['summary']}
    cand=freeze['selected_method']
    def g(method,condition,kind='all'):return index[(method,condition,kind)]
    gates={'all_test_available':test['all_available'],
       'spike_primary_at_least10percent_better':g(cand,'gaussian_plus_spikes')['primary_seconds']<=.9*g('cpop','gaussian_plus_spikes')['primary_seconds'],
       'gaussian_primary_within5seconds':g(cand,'gaussian')['primary_seconds']<=g('cpop','gaussian')['primary_seconds']+5,
       'spike_curve_rmse_not_worse':g(cand,'gaussian_plus_spikes')['curve_rmse_kw']<=g('cpop','gaussian_plus_spikes')['curve_rmse_kw']}
    for kind in ['one_bin_response','one_bin_gap']:
        gates['gaussian_'+kind+'_primary_within15seconds']=g(cand,'gaussian',kind)['primary_seconds']<=g('cpop','gaussian',kind)['primary_seconds']+15
        gates['gaussian_'+kind+'_misses_within1']=g(cand,'gaussian',kind)['whole_miss']<=g('cpop','gaussian',kind)['whole_miss']+1
    for cond in ['gaussian','gaussian_plus_spikes']:
        gates[cond+'_null_false_within1']=g(cand,cond,'null')['null_false_positive']<=g('cpop',cond,'null')['null_false_positive']+1
    for path,digest in hashes.items():check(sha(ROOT/path)==digest,'all audited inputs unchanged during audit')
    output={'status':'passed','scope':'Independent read-only weighted CPOP input/certificate/metric/freeze audit; no model or estimator executed',
       'checks':dict(checks),'n_checks':sum(checks.values()),'maximum_abs_numeric_difference':maximum,
       'validation':val,'test':test,'selected_candidate':cand,'adoption_gates_recomputed':gates,
       'candidate_safe_to_adopt_by_protocol':all(gates.values()),'no_estimator_called':True,'no_new_selection':True,
       'old_scientific_protection_changed':changed,'input_sha256':hashes,
       'limits':['Weights are data-dependent adaptation of existing heteroscedastic CPOP, not a new robust DP objective',
          'Identical single-point observations cannot distinguish real action from sensor spike',
          'Known simulation reference does not validate unknown-baseline deployment',
          'Paired Gaussian/spike conditions are not independent extra subjects',
          'This audit does not check the real-data auxiliary experiment']}
    out=HERE/'audit'/'independent_synthetic.json'
    with out.open('x',encoding='utf-8') as f:json.dump(output,f,ensure_ascii=False,indent=2)
    print(json.dumps({'status':'passed','checks':sum(checks.values()),'validation_rows':val['metric_rows'],'test_rows':test['metric_rows'],
                     'gates':gates,'adopt':all(gates.values()),'max_difference':maximum},ensure_ascii=False))
if __name__=='__main__':main()
