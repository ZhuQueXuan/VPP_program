"""Independent read-only known-reference comparison audit; no estimator calls."""
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
from pathlib import Path
from collections import Counter,defaultdict
import json,hashlib,csv,time
import numpy as np

OUT=Path(__file__).resolve().parent;HERE=OUT.parent;ROOT=HERE.parents[1]
checks=Counter();hashes={};maxdiff=defaultdict(float)
METHODS=['raw_features','ride_original','ride_revised','tf_standard','tf_gls','cpop','labs_2026']
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):
    p=Path(p);hashes[p.relative_to(ROOT).as_posix()]=sha(p)
    return json.loads(p.read_text(encoding='utf8'))
def text(p):
    p=Path(p);hashes[p.relative_to(ROOT).as_posix()]=sha(p)
    return p.read_text(encoding='utf-8-sig')
def ck(name,v):
    if not bool(v):raise AssertionError(name)
    checks[name]+=1
def near(name,a,b,tol=1e-10):
    a=np.asarray(a,float);b=np.asarray(b,float)
    err=float(np.max(abs(a-b))) if a.size else 0.
    maxdiff[name]=max(maxdiff[name],err)
    ck(name,a.shape==b.shape and np.isfinite(a).all() and np.isfinite(b).all() and err<=tol)
def first(mask,indexes):
    return next((i for i in indexes if mask[i]),None)
def longest(mask):
    run=best=0
    for yes in mask:run=run+1 if yes else 0;best=max(best,run)
    return best
def features(pred):
    pred=np.array(pred,float);a=pred>=.15;ix=first(a,range(15,45));it=first(pred>=1.35,range(15,45))
    def interval(i):return None if i is None else [float(max(0,(i-16)*60)),float(max(0,(i-15)*60))]
    recover=first(abs(pred)<=.15,range(45,60)) if ix is not None else None
    return dict(cumulative_response_seconds=int(a[15:45].sum())*60.,longest_continuous_response_seconds=longest(a[15:45])*60.,
        onset_interval_s=interval(ix),target_interval_s=interval(it),
        power_recovery_time_s=(recover-15)*60. if recover is not None else None,
        Y=float(pred[15:45].sum()/45),request_net_kwh=float(pred[15:45].sum()/60),
        post_rebound_kwh=float(np.maximum(-pred[45:],0).sum()/60))
def check_feature(actual,expected):
    for k,v in expected.items():
        if v is None:ck('feature missing-state replay',actual[k] is None)
        else:near('independent native-bin features',actual[k],v,1e-9)
def summarize(rs):
    good=[r for r in rs if r['status']=='ok'];d=dict(total=len(rs),available=len(good),unavailable=len(rs)-len(good))
    if not good:return d
    for key in ('primary_seconds','cumulative_error_seconds','longest_error_seconds','fp_minutes','fn_minutes','peak_error_kw','mean_error_kw','post_rebound_fitted_error_kwh','seconds'):
        d[key]=float(np.mean([r[key] for r in good]))
    d['curve_rmse_kw']=float(np.sqrt(np.mean([r['curve_mse_kw2'] for r in good])))
    d['task_curve_rmse_kw']=float(np.sqrt(np.mean([r['task_curve_mse_kw2'] for r in good])))
    for key in ('null_false_positive','whole_miss','threshold_positive','onset_status_disagreement','target_status_disagreement','recovery_status_disagreement'):
        d[key]=sum(r[key] for r in good)
    for key in ('onset_error_seconds','target_error_seconds','recovery_error_seconds'):
        val=[r[key] for r in good if r[key] is not None];d[key]=float(np.mean(val)) if val else None;d[key+'_n']=len(val)
    return d

def run():
    tick=time.perf_counter();protocol=read(HERE/'protocol.json');freeze=read(HERE/'validation_freeze.json');before=read(HERE/'protected_before.json')
    for p,h in freeze['source_sha256'].items():ck('frozen study source unchanged',sha(HERE/p)==h)
    for p,h in freeze['production_sha256'].items():ck('frozen production source unchanged',sha(ROOT/p)==h)
    unchanged_protected=0;changed=[]
    for p,h in before.items():
        if p=='AGENTS.md':continue
        ck('protected scientific source/data exists',(ROOT/p).is_file())
        if sha(ROOT/p)!=h:changed.append(p)
        unchanged_protected+=1
    ck('all protected scientific files unchanged',not changed)
    receipt=read(HERE/'vendor/LABS/download_receipt.json')
    ck('author fixed commit agrees with protocol',receipt['commit']==protocol['settings']['labs_2026']['commit'])
    for name,d in receipt['downloads'].items():ck('author source/license/citation SHA',sha(HERE/'vendor/LABS'/name)==d['sha256'])
    ck('author MIT license present','MIT License' in text(HERE/'vendor/LABS/LICENSE'))
    source=text(HERE/'run_synthetic.py');simulation=text(HERE/'simulation.py')
    ck('truth opened after complete curves saved',source.index("write(f'outputs/{stage}_curves.json'")<source.index("truths=read(f'evaluator/{stage}.json')"))
    ck('generator contains independent dynamics not fitted candidates','state+=' in simulation and 'velocity+=' in simulation and 'reshape(60,60).mean' in simulation)
    ck('known baseline not command passed to methods',"case['reference_kw']" in source and "case['command_kw']" not in source)
    ck('test generation checks frozen source first',simulation.index("for name,value in freeze['source_sha256'].items()")<simulation.index('c,t=generate(stage)'))
    noise=read(HERE/'noise_development.json');z=np.asarray(noise['residuals'])
    ck('independent development128x60',z.shape==(128,60))
    near('noise development scalar variance',noise['scalar_variance'],np.mean(z*z),1e-15)
    covariance=np.asarray(noise['covariance']);ck('noise covariance positive definite',covariance.shape==(60,60) and np.linalg.eigvalsh(covariance).min()>0)
    allrows={};case_data={};subsets={};stage_summaries={};stage_users={};stage_seeds={};nativecases=0
    D=np.zeros((58,60));j=np.arange(58);D[j,j]=1.;D[j,j+1]=-2.;D[j,j+2]=1.
    for stage,expected_count in [('validation',64),('test',192)]:
        cases=read(HERE/f'facts/{stage}.json');truths=read(HERE/f'evaluator/{stage}.json')
        curves=read(HERE/f'outputs/{stage}_curves.json');metrics=read(HERE/f'outputs/{stage}_metrics.json');summaries=read(HERE/f'outputs/{stage}_summary.json')
        ck('complete stage cases and metrics',len(cases)==len(truths)==len(curves)==expected_count and len(metrics)==7*expected_count)
        ck('unique original users and tasks',len({c['task']['user_id'] for c in cases})==len({c['task']['task_id'] for c in cases})==expected_count)
        stage_users[stage]={c['task']['user_id'] for c in cases};stage_seeds[stage]={c['seed'] for c in cases}
        ck('prespecified seeds/kind balance',stage_seeds[stage]==set(protocol['simulation'][stage]['seeds']) and set(Counter(c['kind'] for c in cases).values())=={expected_count//8})
        index={(r['task_id'],r['method']):r for r in metrics};ck('all method keys retained',len(index)==len(metrics))
        rows=[];bounds={};physical_range=[float('inf'),-float('inf')]
        for c,t,o in zip(cases,truths,curves):
            task=c['task']['task_id'];ck('case evaluator curve task binding',task==t['task_id']==o['task_id'] and set(o['results'])==set(METHODS))
            near('shared minute grid',c['starts'],np.arange(-15,45),0.);near('shared minute ends',c['ends'],np.arange(-14,46),0.)
            ck('common task and known baseline',c['task']['request_kw']==1.5 and c['task']['end_min']==30 and c['sigma']==.05 and len(set(c['reference_kw']))==1)
            clean=np.array(t['true_reduction_kw']);raw=np.array(c['reference_kw'])-c['power_kw'];actual=features(clean)
            baseline=float(c['reference_kw'][0]);physical_range[0]=min(physical_range[0],baseline-t['fine_signal_max']);physical_range[1]=max(physical_range[1],baseline-t['fine_signal_min'])
            ck('declared clean fine-grid physical bounds',baseline-t['fine_signal_max']>=0 and baseline-t['fine_signal_min']<=7.2)
            ck('observed finite complete vector',clean.shape==raw.shape==(60,) and np.isfinite(raw).all())
            bounds[task]=dict(post_peak_rebound_kw=float(max(0,-clean[45:].min())),full_peak_rebound_kw=float(max(0,-clean.min())),fine_full_peak_rebound_kw=float(max(0,-t['fine_signal_min'])),
                post_within_original_bound=bool(clean[45:].min()>=-1.5-1e-12),full_within_original_bound=bool(clean.min()>=-1.5-1e-12))
            case_data[(stage,task)]=dict(kind=c['kind'],seed=c['seed'],**bounds[task])
            etas=[]
            for method in METHODS:
                result=o['results'][method];m=index[(task,method)];ck('all finite native60 outputs',result['status']==m['status']=='ok' and len(result['prediction'])==60 and np.isfinite(result['prediction']).all())
                pred=np.array(result['prediction']);f=features(pred);check_feature(m['features'],f);check_feature(m['true_features'],actual)
                a=clean[15:45]>=.15;b=pred[15:45]>=.15
                dc=abs(f['cumulative_response_seconds']-actual['cumulative_response_seconds']);dl=abs(f['longest_continuous_response_seconds']-actual['longest_continuous_response_seconds'])
                r=dict(task_id=task,method=method,kind=c['kind'],seed=c['seed'],status='ok',seconds=result.get('seconds',0.),primary_seconds=.5*(dc+dl),
                    cumulative_error_seconds=dc,longest_error_seconds=dl,fp_minutes=int(np.sum(b&~a)),fn_minutes=int(np.sum(a&~b)),
                    null_false_positive=c['kind']=='null' and bool(b.any()),threshold_positive=bool(a.any()),whole_miss=bool(a.any() and not b.any()),
                    curve_mse_kw2=float(np.mean((pred-clean)**2)),task_curve_mse_kw2=float(np.mean((pred[15:45]-clean[15:45])**2)),
                    peak_error_kw=float(abs(pred[15:45].max()-clean[15:45].max())),mean_error_kw=float(abs(pred[15:45].mean()-clean[15:45].mean())),
                    post_rebound_fitted_error_kwh=float(abs(np.maximum(-pred[45:],0).sum()-np.maximum(-clean[45:],0).sum())/60),raw_eta=float(raw[15:45].sum()/45))
                for name in ('onset','target'):
                    p=f[name+'_interval_s'];v=actual[name+'_interval_s'];both=p is not None and v is not None
                    r[name+'_status_disagreement']=(p is None)!=(v is None);r[name+'_both_present']=both;r[name+'_error_seconds']=abs(p[0]-v[0]) if both else None
                p=f['power_recovery_time_s'];v=actual['power_recovery_time_s'];r['recovery_status_disagreement']=(p is None)!=(v is None);r['recovery_error_seconds']=abs(p-v) if p is not None and v is not None else None
                for k,v in r.items():
                    if isinstance(v,(bool,str)) or v is None:ck('all metric identities/categories',m[k]==v)
                    else:near('all metric numeric recomputation',m[k],v,1e-9)
                etas.append(m['raw_eta']);rows.append(r)
                if method=='raw_features':near('raw extractor receives identical input',pred,raw,0.)
                if method in ('tf_standard','tf_gls'):
                    cov=noise['scalar_variance']*np.eye(60) if method=='tf_standard' else covariance;lam=4 if method=='tf_standard' else 2
                    ck('TF fixed penalty and success',result['penalty']==lam and result['success'] is True and result['raw_fallback'] is False)
                    near('TF primal from saved dual fixed covariance',pred,raw-cov@D.T@np.array(result['dual_solution']),1e-11)
            near('all7 raw eta identical',etas,np.repeat(raw[15:45].sum()/45,7),1e-14)
        for s in summaries:
            rs=[r for r in rows if r['method']==s['method'] and (s['kind']=='all' or r['kind']==s['kind'])];expected=summarize(rs)
            for k,v in expected.items():
                if v is None:ck('summary missing conditional time',s[k] is None)
                else:near('all pooled and kind summaries recomputed',s[k],v,1e-9)
        ck('complete63 pooled-kind summary groups',len(summaries)==63)
        allrows[stage]=rows;stage_summaries[stage]=[dict(method=m,**summarize([r for r in rows if r['method']==m])) for m in METHODS]
        sub=[]
        for label,condition in [('full_rebound_within1q',lambda v:v['full_within_original_bound']),('full_rebound_exceeds1q',lambda v:not v['full_within_original_bound']),
            ('post_rebound_within1q',lambda v:v['post_within_original_bound']),('post_rebound_exceeds1q',lambda v:not v['post_within_original_bound'])]:
            ids={k for k,v in bounds.items() if condition(v)}
            sub.append(dict(subset=label,n=len(ids),by_kind=dict(Counter(c['kind'] for c in cases if c['task']['task_id'] in ids)),
                methods=[dict(method=m,**summarize([r for r in rows if r['task_id'] in ids and r['method']==m])) for m in METHODS]))
        subsets[stage]=sub
        # Author LABS CSVs: verify the actual provided y and every returned point.
        li=list(csv.DictReader(text(HERE/f'labs/{stage}/input.csv').splitlines()));lo=list(csv.DictReader(text(HERE/f'labs/{stage}/output.csv').splitlines()))
        gin=defaultdict(list);gout=defaultdict(list)
        for r in li:gin[int(r['case_id'])].append(r)
        for r in lo:gout[int(r['case_id'])].append(r)
        ck('all LABS native case IDs',set(gin)==set(gout)==set(range(expected_count)))
        for i,c in enumerate(cases):
            near('LABS same raw input',[float(r['y']) for r in gin[i]],np.array(c['reference_kw'])-c['power_kw'],0.)
            ck('LABS complete index order',list(map(lambda r:int(r['index']),gout[i]))==list(range(1,61)))
            near('author LABS saved prediction exact',[float(r['fitted']) for r in gout[i]],curves[i]['results']['labs_2026']['prediction'],0.)
        nativecases+=expected_count
    ck('validation/test users and seeds isolated',not stage_users['validation']&stage_users['test'] and not stage_seeds['validation']&stage_seeds['test'])
    val=stage_summaries['validation'];candidates=[v for v in val if v['method'] not in ('raw_features','cpop') and v['available']==64]
    chosen=min(candidates,key=lambda r:(r['primary_seconds'],r['seconds']))
    ck('frozen selection from validation only',chosen['method']==freeze['selected_candidate']=='labs_2026' and chosen['primary_seconds']==freeze['validation_primary_seconds'])
    sorted_scores=sorted(v['primary_seconds'] for v in candidates);ck('no approximate tie issue',sorted_scores[1]-sorted_scores[0]>1e-9)
    ck('test not generated in freeze record',freeze['test_not_generated_yet'] is True)
    ck('filesystem freeze precedes new test creation',(HERE/'validation_freeze.json').stat().st_mtime_ns<(HERE/'facts/test.json').stat().st_mtime_ns)
    test={r['method']:r for r in stage_summaries['test']};selected=test[chosen['method']];old=test['ride_revised']
    reduction=1-selected['primary_seconds']/old['primary_seconds']
    gate=dict(all_available=selected['available']==192,primary_at_least10percent=reduction>=.10,
        full_curve_RMSE_not_increase=selected['curve_rmse_kw']<=old['curve_rmse_kw'],null_false_not_more_than_old_plus1=selected['null_false_positive']<=old['null_false_positive']+1,
        fractional_primary_improvement=reduction)
    gate['passed']=all(gate[k] for k in ('all_available','primary_at_least10percent','full_curve_RMSE_not_increase','null_false_not_more_than_old_plus1'))
    for p,h in hashes.items():ck('audit inputs unchanged',sha(ROOT/p)==h)
    result=dict(status='passed',scope='Independent read-only synthetic metrics/provenance audit; no fitting, generation or parameter changes',n_checks=sum(checks.values()),checks=dict(checks),
        max_numeric_residual=dict(maxdiff),stage_summaries=stage_summaries,original_bound_subsets=subsets,
        validation_selected=chosen['method'],recommendation_gate=gate,noise_shrinkage=noise['shrinkage'],
        cases_checked=256,method_rows_checked=1792,validation_rows=448,test_rows=1344,LABS_native_cases_checked=nativecases,
        protected_scientific_files_unchanged=unchanged_protected,source_sha256=freeze['source_sha256'],input_sha256=hashes,
        no_estimator_execution=True,limits=['Known baseline; no unknown-reference deployment claim.','No clean-session energy-debt/departure guarantee.',
            'Old RIDE1q rebound cap differs from revised declared headroom; subset comparison does not make their shape constraints identical.',
            'Within-run hashes and mtimes support record consistency, not external trusted chronology.','All seven methods retained; no test selection.'],seconds=time.perf_counter()-tick)
    with (OUT/'synthetic_audit.json').open('x',encoding='utf8') as h:json.dump(result,h,ensure_ascii=False,indent=2,allow_nan=False)
    print(json.dumps(dict(status='passed',checks=sum(checks.values()),gate=gate,all_test=stage_summaries['test'],bounds={stage:[{'subset':v['subset'],'n':v['n']} for v in a] for stage,a in subsets.items()}),ensure_ascii=False))
if __name__=='__main__':run()
