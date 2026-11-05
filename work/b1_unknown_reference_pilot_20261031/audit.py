"""Independent read-only pilot audit. No fitting, optimization or generation."""
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[key]='1'
import sys
sys.dont_write_bytecode=True
from pathlib import Path
import json,csv,hashlib,math
from collections import defaultdict,Counter
import numpy as np
import lightgbm as lgb

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
FACTS=ROOT/'data/B1_unknown_reference_pilot_v1_20261031'
hashes={};checks=Counter()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def pairs(items):
    result={}
    for k,v in items:
        assert k not in result,('duplicate JSON',k)
        result[k]=v
    return result
def read(p):
    p=Path(p);hashes[p.relative_to(ROOT).as_posix()]=sha(p)
    return json.loads(p.read_text(encoding='utf8'),object_pairs_hook=pairs,parse_constant=lambda x:(_ for _ in ()).throw(ValueError(x)))
def ck(name,condition):
    assert bool(condition),name
    checks[name]+=1
def near(name,a,b,atol=1e-10):
    ck(name,np.allclose(a,b,atol=atol,rtol=1e-10))
def feature_map(f):
    w=f['reference_window'];p=np.asarray(w['pre_power_kw'],float)
    s=np.asarray(w['pre_starts_min']);e=np.asarray(w['pre_ends_min'])
    keep=(s>=w['notice_min']-60-1e-9)&(e<=w['notice_min']+1e-9)
    p=p[keep];ck('60 legal pre-notice prefix',len(p)==60)
    offset=float(p.mean());center=p.reshape(4,15).mean(1)-offset
    prior=np.asarray(w['prior_mean_kw'],float);prior=prior-prior.mean()
    h=np.arange(60)+.5;clock=w['clock_hour']+(h-15)/60
    x=np.column_stack([np.repeat(center[None,:],60,axis=0),prior,h/60,np.sin(2*np.pi*clock/24),np.cos(2*np.pi*clock/24),np.full(60,np.sin(2*np.pi*w['weekday']/7)),np.full(60,np.cos(2*np.pi*w['weekday']/7)),np.full(60,w['temperature_c'])])
    return x,offset

P=read(HERE/'protocol.json');F=read(HERE/'freeze.json')
for p,h in F['source_identity'].items():ck('frozen source SHA',sha(ROOT/p)==h)
for p,h in F['artifact_sha256'].items():ck('frozen artifact SHA',sha(ROOT/p)==h)
allfacts={};stage_users={};stage_times={}
for phase,d in P['stages'].items():
    receipt=read(HERE/'data_receipts'/f'{phase}.json')
    for row in receipt['rows']:
        for p,h in row['sha256'].items():ck('fresh fact/truth/metadata SHA',sha(ROOT/p)==h)
    group=set();first=[];last=[]
    seeds=d.get('seeds',[d.get('seed')])
    ck('whole-week shift',d['shift_min']%10080==0)
    for seed in seeds:
        paired=None
        for variant in d['variants']:
            fs=read(FACTS/phase/f'{seed}_{variant}_facts.json')
            allfacts[(phase,seed,variant)]=fs
            users=Counter(f['task']['user_id'] for f in fs)
            ck('two events per user',set(users.values())=={2})
            ck('phase size',len(users)==d.get('users',d.get('users_per_block')))
            ids=[f['task']['task_id'] for f in fs]
            ck('unique task IDs within variant',len(ids)==len(set(ids)))
            if paired is None:paired=fs;group.update(users)
            else:
                ck('paired task identity',[f['task'] for f in fs]==[f['task'] for f in paired])
                ck('paired legal reference_window',[f['reference_window'] for f in fs]==[f['reference_window'] for f in paired])
            for f in fs:
                t=f['task'];w=f['reference_window'];notice=t['notice_min'];start=t['start_min']
                ck('reference identity/time/task binding',all(w[k]==t[k] for k in ('task_id','user_id','meter_id','notice_min')) and w['task_start_min']==start and w['task_end_min']==t['end_min'] and w['request_kw']==t['request_kw'])
                ck('task signature',t['end_min']-start==30 and t['request_kw']==1.5 and start-notice==15)
                near('native complete minute grid',np.asarray(f['starts_min'])-start,np.arange(-15.,45.))
                near('native interval ends',np.asarray(f['ends_min'])-start,np.arange(-14.,46.))
                ck('legal feature availability',max(w[k] for k in ('pre_available_min','prior_available_min','calendar_available_min','temperature_available_min'))<=notice)
                ck('prefix ends before notice',max(w['pre_ends_min'])<=notice)
                ck('observed label completion',f['availability']['power_records_available_at_min']>=max(f['ends_min']))
                ck('calendar preservation',w['clock_hour']==(start%1440)/60 and w['weekday']==int(start//1440)%7)
                hs={h['source_id']:h for h in f['historical_non_event']}
                ck('history source ledger',len(w['prior_source_ids'])==w['prior_source_count'] and len(set(w['prior_source_ids']))==len(w['prior_source_ids']))
                selected=[hs[k] for k in w['prior_source_ids']]
                for h in selected:ck('history before notice and same entity',h['non_event'] is True and h['available_at_min']<notice and h['user_id']==t['user_id'] and h['meter_id']==t['meter_id'])
                near('prior mean from declared real history',w['prior_mean_kw'],np.mean([h['power_kw'][-60:] for h in selected],axis=0))
                ck('non-event flags' if variant=='non_event' else 'announced event flags',f['non_event']==(variant=='non_event') and f['task_dispatched']==(variant!='non_event') and f['incentive_signal_announced']==(variant!='non_event'))
                first.append(notice);last.append(f['availability']['power_records_available_at_min'])
    stage_users[phase]=group;stage_times[phase]=(min(first),max(last))
phases=list(P['stages'])
for i,a in enumerate(phases):
    for b in phases[i+1:]:ck('users disjoint across stages',not stage_users[a]&stage_users[b])
for a,b in zip(phases,phases[1:]):ck('strict complete-label stage chronology',stage_times[a][1]<stage_times[b][0])

sel=read(HERE/'reference_selection.json');refval=allfacts[('reference_validation',P['stages']['reference_validation']['seed'],'non_event')]
train=allfacts[('train',P['stages']['train']['seed'],'non_event')]
horiz=np.array(P['reference']['training_horizons'])
trainmap=[feature_map(f) for f in train]
X=np.concatenate([x[horiz] for x,o in trainmap]);Y=np.concatenate([(np.asarray(f['power_kw'])-o)[horiz] for f,(x,o) in zip(train,trainmap)])
ck('same 1024 actual training rows',X.shape==(1024,11) and len(Y)==1024)
models={};scores=[]
for row in sel['rows']:
    path=ROOT/row['artifact'];env=read(path)
    ck('model envelope SHA',hashlib.sha256(env['payload_json'].encode()).hexdigest()==env['sha256'])
    model=json.loads(env['payload_json'],object_pairs_hook=pairs);m=model['metadata'];ident=m['spec']['id']
    models[ident]=model
    ck('model ledger exact users/tasks',m['training_users']==sorted(stage_users['train']) and m['training_task_ids']==sorted(f['task']['task_id'] for f in train))
    ck('train cutoff legal',m['fit_cutoff_min']==stage_times['train'][1] and m['fit_cutoff_min']<stage_times['reference_validation'][0])
    near('scaler mean training-only',model['scaler_mean'],X.mean(0))
    expected_scale=np.sqrt(np.mean((X-X.mean(0))**2,axis=0));expected_scale[expected_scale==0]=1
    near('scaler scale training-only',model['scaler_scale'],expected_scale)
    if m['spec']['family']=='lightgbm':
        ck('native tree SHA',sha(path.parent/model['tree_file'])==model['tree_sha256'])
        model['_booster']=lgb.Booster(model_file=str(path.parent/model['tree_file']))
    else:
        ck('fixed GP optimizer/noise',m['engine_params']['optimizer'] is None and m['engine_params']['white_noise_variance']==.0025 and m['engine_params']['amplitude']==.04)
        Z=(X-np.asarray(model['scaler_mean']))/model['scaler_scale'];near('GP same transformed training rows',Z,model['gp_train_x'])
        delta=Z[:,None,:]-Z[None,:,:]
        K=.04*np.exp(-.5*np.sum(delta*delta,axis=2)/m['spec']['length_scale']**2)+.0025*np.eye(1024)
        near('saved GP weights solve declared kernel equations',K@np.asarray(model['gp_alpha']),Y,1e-8)
def predict(model,fs):
    xo=[feature_map(f) for f in fs];raw=np.concatenate([x for x,o in xo]);z=(raw-model['scaler_mean'])/model['scaler_scale']
    m=model['metadata']
    if m['spec']['family']=='lightgbm':out=model['_booster'].predict(z,num_threads=1)
    else:
        # Chunked kernel arithmetic only: no fitting or hyperparameter search.
        trainx=np.asarray(model['gp_train_x']);alpha=np.asarray(model['gp_alpha']);parts=[]
        for lo in range(0,len(z),128):
            delta=z[lo:lo+128,None,:]-trainx[None,:,:]
            parts.append(.04*np.exp(-.5*np.sum(delta*delta,axis=2)/m['spec']['length_scale']**2)@alpha)
        out=np.concatenate(parts)
    return out.reshape(len(fs),60)+np.asarray([o for x,o in xo])[:,None]
for row in sel['rows']:
    ident=row['spec']['id'];pred=predict(models[ident],refval)
    saved=read(HERE/'reference_validation_predictions'/f'{ident}.json')
    near('independent model prediction replay',pred,saved['prediction'],1e-10)
    mse=float(np.mean((pred-np.asarray([f['power_kw'] for f in refval]))**2));near('reference validation observed-power score',mse,row['mse']);scores.append(mse)
ck('reference selection fixed minimum MSE',sel['selected']==sel['rows'][int(np.argmin(scores))]['spec']['id'])
selected=models[sel['selected']]
dev=allfacts[('process_development',P['stages']['process_development']['seed'],'non_event')]
devref=predict(selected,dev);res=devref-np.asarray([f['power_kw'] for f in dev])
error=read(HERE/'development_error_model.json');near('saved development residuals',res,error['residuals'])
near('common effective variance',max(.05**2,float(np.mean(res**2))),error['scalar_variance'])
near('common effective sigma',error['sigma_effective']**2,error['scalar_variance'])
# Independent closed-form Ledoit-Wolf arithmetic; no covariance estimator fit.
A=res-res.mean(0);n,p=A.shape;emp=A.T@A/n;mu=np.trace(emp)/p
delta=(np.sum(emp**2)-2*mu*np.trace(emp)+p*mu**2)/p
beta=(np.sum(np.sum(A*A,axis=1)**2)/n-np.sum(emp**2))/(p*n)
shrink=min(beta,delta)/delta if delta>0 else 0
cov=(1-shrink)*emp+shrink*mu*np.eye(p)+1e-8*np.eye(p)
near('independent LedoitWolf shrinkage',shrink,error['shrinkage']);near('independent LedoitWolf covariance',cov,error['covariance'])
D=np.diff(np.eye(60),n=2,axis=0)
selection=read(HERE/'process_selection.json')
def check_tf(y,pred,solver,C,penalty):
    ck('TF no raw fallback',solver['raw_fallback'] is False)
    if pred is None:ck('explicit unavailable TF',solver['status']=='unavailable');return
    x=np.asarray(pred);u=np.asarray(solver['dual_solution']);S=np.eye(60)*C if np.ndim(C)==0 else C
    near('TF primal-dual stationarity',x,y-S@D.T@u,1e-9)
    primal=.5*(x-y)@np.linalg.solve(S,x-y)+penalty*np.sum(np.abs(D@x))
    dual=u@(D@y)-.5*u@(D@S@D.T@u)
    near('TF independently recomputed primal',primal,solver['primal'],1e-8)
    near('TF independently recomputed dual',dual,solver['dual'],1e-8)
    ck('TF actual dual feasibility',np.max(np.abs(u))<=penalty+1e-10*max(1,penalty))
    ck('TF actual primal-dual gap',abs(primal-dual)<=solver['gap_tolerance']+1e-9)
for method,C in [('tf_standard',error['scalar_variance']),('tf_gls',cov)]:
    grid=[]
    for pen in P['process']['penalties']:
        fs=read(HERE/'development_solver'/f'{method}_{pen}.json');false=defaultdict(bool)
        for f,y,fit in zip(dev,res,fs):
            check_tf(y,fit['prediction'],fit,C,pen)
            false[f['task']['user_id']] |= fit['prediction'] is not None and bool(np.any(np.asarray(fit['prediction'])[15:45]>=.15))
        count=sum(false.values());saved=[x for x in selection['grid'][method] if x['penalty']==pen][0]
        ck('development raw user error count',count==saved['false_users'] and len(false)==32)
        grid.append((pen,count/32,saved['unavailable']))
    valid=[g for g in grid if g[2]==0];passing=[g for g in valid if g[1]<=.05]
    chosen=min(passing,key=lambda x:x[0]) if passing else min(valid,key=lambda x:(x[1],x[0]))
    ck('process selection frozen rule',selection['chosen'][method]['penalty']==chosen[0] and selection['chosen'][method]['development_target_met']==bool(passing))

def simple_features(pred):
    x=np.asarray(pred);task=x[15:45];mask=task>=.15
    best=run=0
    for flag in mask:run=run+1 if flag else 0;best=max(best,run)
    return dict(cumulative_response_seconds=float(mask.sum()*60),longest_continuous_response_seconds=float(best*60),mean_reduction_kw=float(task.mean()),peak_reduction_kw=float(task.max()),post_rebound_kwh=float(np.maximum(-x[45:],0).sum()/60))
def scan(x):
    x=np.asarray(x)[15:45];prefix=np.r_[0.,np.cumsum(x)]
    return max(float(np.max(prefix[k:]-prefix[:-k])/np.sqrt(k)) for k in P['event_evidence']['scan_lengths'])
def native_check(rows,fs,refs,sigma=None):
    if any(r['status']!='ok' for r in rows):return
    directory=Path(rows[0]['solver']['backend']['artifact_dir'])
    with (directory/'input.csv').open(encoding='utf-8-sig',newline='') as h:inputs=list(csv.DictReader(h))
    with (directory/'segments.csv').open(encoding='utf-8-sig',newline='') as h:segments=list(csv.DictReader(h))
    ins=defaultdict(list);segs=defaultdict(list)
    for v in inputs:ins[int(v['case_id'])].append(v)
    for v in segments:segs[int(v['case_id'])].append(v)
    ck('native original CP one case per event',len(ins)==len(rows))
    for i,(row,f,ref) in enumerate(zip(rows,fs,refs)):
        inp=ins[i*10];sg=[s for s in segs[i*10] if float(s['x1'])>float(s['x0'])]
        near('native CP same residual input',[float(v['y']) for v in inp],np.asarray(ref)-f['power_kw'])
        near('native CP correct frozen sigma',[float(v['sigma']) for v in inp],error['sigma_effective'] if sigma is None else sigma)
        ck('native CP full grid no hidden subsample',len(inp)==60 and all(v['train']=='1' for v in inp))
        xx=np.array([float(v['x']) for v in inp]);near('native CP midpoint lattice',xx,np.arange(-15,45)+.5)
        reconstructed=np.full(60,np.nan)
        for j,s in enumerate(sg):
            a,b=float(s['x0']),float(s['x1']);use=(xx>=a-1e-9)&(xx<=b+1e-9)
            if j==0:use|=xx<a
            if j==len(sg)-1:use|=xx>b
            reconstructed[use]=float(s['gradient'])*xx[use]+float(s['intercept'])
        near('native CP saved original segment replay',reconstructed,row['prediction'],1e-11)

cal=read(HERE/'event_calibration.json');calfacts=allfacts[('calibration',P['stages']['calibration']['seed'],'non_event')]
calrefs=read(HERE/'references'/'calibration.json')['prediction'];near('calibration reference replay',calrefs,predict(selected,calfacts))
for method in P['process']['methods']:
    outs=read(HERE/'calibration_outputs'/f'{method}.json');maxima=defaultdict(lambda:-np.inf)
    for f,ref,o in zip(calfacts,calrefs,outs):
        ck('calibration identity and availability',o['task_id']==f['task']['task_id'] and o['prediction'] is not None)
        near('common scan statistic',scan(o['prediction']),o['scan_score']);maxima[o['user_id']]=max(maxima[o['user_id']],o['scan_score'])
    ck('48 calibration user blocks',len(maxima)==48)
    ck('calibration maxima exact',dict(maxima)==cal[method]['user_maxima'])
    if method=='cpop':native_check(outs,calfacts,calrefs)

summaries=[]
for phase in ('validation','test'):
    ck('evaluation phase completed',bool(read(HERE/f'{phase}_completed.json')))
    assess=read(HERE/f'{phase}_assessment.json');metrics=read(HERE/f'{phase}_metrics.json');metricmap={(r['seed'],r['variant'],r['method'],r['task_id']):r for r in metrics}
    groups=defaultdict(list);d=P['stages'][phase]
    for seed in d.get('seeds',[d.get('seed')]):
        refs=read(HERE/'references'/f'{phase}_{seed}.json')['prediction']
        near('evaluation reference facts-only replay',refs,predict(selected,allfacts[(phase,seed,'strong')]))
        for variant in d['variants']:
            fs=allfacts[(phase,seed,variant)];ts=read(HERE/'evaluator'/phase/f'{seed}_{variant}_truth.json');etas=defaultdict(list)
            for method in P['process']['methods']:
                outs=read(HERE/'outputs'/phase/f'{seed}_{variant}_{method}.json')
                ck('all output rows preserved',len(outs)==len(fs))
                if method=='cpop':native_check(outs,fs,refs)
                for f,t,ref,o in zip(fs,ts,refs,outs):
                    ck('factual/truth/output task binding',f['task']['task_id']==t['task_id']==o['task_id'])
                    near('physical factual generation equation',f['power_kw'],np.asarray(t['true_reference_kw'])-t['true_reduction_kw']+np.asarray(t['measurement_error_kw']))
                    y=np.asarray(ref)-np.asarray(f['power_kw']);raweta=float(y[15:45].sum()/45);near('same raw eta',raweta,o['eta_raw']);etas[o['task_id']].append(o['eta_raw'])
                    m=metricmap[(seed,variant,method,o['task_id'])]
                    if o['prediction'] is None:
                        ck('unavailable remains explicit',o['status']!='ok' and o['features'] is None and o['evidence_p'] is None);continue
                    if method!='cpop':check_tf(y,o['prediction'],o['solver'],error['scalar_variance'] if method=='tf_standard' else cov,selection['chosen'][method]['penalty'])
                    feat=simple_features(o['prediction'])
                    for k,v in feat.items():near('independent selected feature '+k,v,o['features'][k],1e-9)
                    truthfeat=simple_features(t['true_reduction_kw']);near('truth duration arithmetic',truthfeat['cumulative_response_seconds'],t['cumulative_response_seconds'])
                    near('duration metric arithmetic',abs(feat['cumulative_response_seconds']-t['cumulative_response_seconds']),m['duration_error_seconds'])
                    near('longest metric arithmetic',abs(feat['longest_continuous_response_seconds']-t['longest_continuous_response_seconds']),m['longest_error_seconds'])
                    near('raw energy metric arithmetic',abs(raweta-t['eta']),m['eta_error'])
                    near('common scan statistic',scan(o['prediction']),o['scan_score'])
                    pvalue=(1+sum(v>=o['scan_score'] for v in cal[method]['user_maxima'].values()))/49
                    near('rank pvalue exact',pvalue,o['evidence_p'])
                    ck('rank decision exact',o['evidence_status']==('evidence' if pvalue<=.05 else 'inconclusive'))
                    groups[(variant,method)].append((t,feat,o))
            ck('eta equals all three process methods',all(len(v)==3 and max(v)-min(v)<1e-12 for v in etas.values()))
    for (variant,method),group in groups.items():
        a=[x for x in assess['groups'] if x['variant']==variant and x['method']==method][0]
        duration=np.array([abs(f['cumulative_response_seconds']-t['cumulative_response_seconds']) for t,f,o in group])
        near('assessment duration MAE',duration.mean(),a['duration_mae_seconds'])
        no=[(t,f,o) for t,f,o in group if not t['physical_action']];positive=[(t,f,o) for t,f,o in group if t['threshold_positive']]
        fp=sum(f['cumulative_response_seconds']>0 for t,f,o in no);miss=sum(f['cumulative_response_seconds']==0 for t,f,o in positive)
        ck('assessment no-action complete count',len(no)==a['no_action'])
        ck('assessment raw FP count',fp==a['false_positive_duration'])
        ck('assessment positive complete count',len(positive)==a['threshold_positive'])
        ck('assessment missed positive count',miss==a['missed_positive_duration'])
        ck('assessment false evidence count',sum(o['evidence_status']=='evidence' for t,f,o in no)==a['no_action_false_evidence'])
        ck('assessment inconclusive count',sum(o['evidence_status']=='inconclusive' for t,f,o in positive)==a['positive_inconclusive'])
        summaries.append(dict(phase=phase,variant=variant,method=method,n=len(group),duration_mae_seconds=float(duration.mean()),no_action=len(no),false_positive=fp,positive=len(positive),miss=miss))
    ck('assessment row count and full methods',len(metrics)==assess['rows'] and len(groups)==9)
supplement=[]
if (HERE/'supplement_freeze.json').exists():
    sf=read(HERE/'supplement_freeze.json');sp=read(HERE/'supplement_protocol.json');sc=read(HERE/'sensitivity_calibration.json')
    ck('supplement script/protocol/calibration/main freeze unchanged',sf['script_sha256']==sha(HERE/'cpop_sensitivity.py') and sf['protocol_sha256']==sha(HERE/'supplement_protocol.json') and sf['calibration_sha256']==sha(HERE/'sensitivity_calibration.json') and sf['main_freeze_sha256']==sha(HERE/'freeze.json'))
    ck('supplement honest validation-seen timing',sf['validation_seen'] is True and sf['test_generated'] is False and sp['timing']=='Added after response-validation results were seen, before test facts generation')
    testfiles=[FACTS/'test'/f'{seed}_{v}_facts.json' for seed in P['stages']['test']['seeds'] for v in P['stages']['test']['variants']]
    ck('supplement filesystem freeze precedes new test facts',all((HERE/'supplement_freeze.json').stat().st_mtime_ns<p.stat().st_mtime_ns for p in testfiles))
    ck('supplement fixed declared meter sigma',sc['sigma']==.05 and sc['alpha']==.05)
    def supplement_native(rows,label,fs,refs):
        original=read(HERE/'sensitivity_native_outputs'/f'{label}.json')
        bound=[]
        for row,o in zip(rows,original):
            ck('supplement uses actual native CPOP output',o['process']['method']=='CPOP' and o['status']=='ok')
            near('supplement native prediction exact',row['prediction'],o['process']['reduction_interval_kw'])
            bound.append(dict(row,solver=dict(backend=o['process']['backend'])))
        native_check(bound,fs,refs,.05)
    scouts=read(HERE/'sensitivity_calibration_outputs.json');smax=defaultdict(lambda:-np.inf)
    supplement_native(scouts,'calibration',calfacts,calrefs)
    for o in scouts:
        near('supplement same scan statistic',scan(o['prediction']),o['scan_score'])
        smax[o['user_id']]=max(smax[o['user_id']],o['scan_score'])
    ck('supplement same 48 calibration users',set(smax)==set(cal['cpop']['user_maxima']))
    ck('supplement own max-user calibration exact',dict(smax)==sc['maxima'])
    for phase in ('validation','test'):
        ck('supplement evaluation complete',bool(read(HERE/f'sensitivity_{phase}_completed.json')))
        d=P['stages'][phase];sgroups=defaultdict(list)
        for seed in d.get('seeds',[d.get('seed')]):
            refs=read(HERE/'references'/f'{phase}_{seed}.json')['prediction']
            for variant in d['variants']:
                fs=allfacts[(phase,seed,variant)];ts=read(HERE/'evaluator'/phase/f'{seed}_{variant}_truth.json')
                outs=read(HERE/'sensitivity_outputs'/phase/f'{seed}_{variant}.json')
                ck('supplement same full event cohort',len(outs)==len(fs))
                supplement_native(outs,f'{phase}_{seed}_{variant}',fs,refs)
                for f,t,ref,o in zip(fs,ts,refs,outs):
                    ck('supplement identity exact',o['task_id']==f['task']['task_id']==t['task_id'])
                    near('supplement shared raw eta',(np.asarray(ref)[15:45]-np.asarray(f['power_kw'])[15:45]).sum()/45,o['eta_raw'])
                    feat=simple_features(o['prediction'])
                    for k,v in feat.items():near('supplement selected feature '+k,v,o['features'][k],1e-9)
                    near('supplement same scan statistic',scan(o['prediction']),o['scan_score'])
                    pv=(1+sum(v>=o['scan_score'] for v in sc['maxima'].values()))/49
                    near('supplement independent max-user rank',pv,o['evidence_p'])
                    ck('supplement rank decision exact',o['evidence_status']==('evidence' if pv<=.05 else 'inconclusive'))
                    sgroups[variant].append((t,feat,o))
        for variant,group in sgroups.items():
            no=[(t,f,o) for t,f,o in group if not t['physical_action']];pos=[(t,f,o) for t,f,o in group if t['threshold_positive']]
            supplement.append(dict(phase=phase,variant=variant,method='cpop_meter_sigma',n=len(group),duration_mae_seconds=float(np.mean([abs(f['cumulative_response_seconds']-t['cumulative_response_seconds']) for t,f,o in group])),no_action=len(no),false_positive=sum(f['cumulative_response_seconds']>0 for t,f,o in no),positive=len(pos),miss=sum(f['cumulative_response_seconds']==0 for t,f,o in pos),false_evidence=sum(o['evidence_status']=='evidence' for t,f,o in no),positive_inconclusive=sum(o['evidence_status']=='inconclusive' for t,f,o in pos)))
for p,h in F['source_identity'].items():ck('source unchanged after audit',sha(ROOT/p)==h)
ck('all read inputs unchanged after audit',all(sha(ROOT/p)==h for p,h in hashes.items()))
receipt=dict(status='passed',scope='Independent read-only numerical and provenance audit; no fitting, optimization, generation, tuning, native-R rerun or source mutation',checks=dict(checks),n_checks=sum(checks.values()),input_files=len(hashes),source_files=len(F['source_identity']),users_by_stage={k:len(v) for k,v in stage_users.items()},time_bounds=stage_times,selected_reference=sel['selected'],selected_penalties=selection['chosen'],independent_summary=summaries,supplement_summary=supplement,limitations=['Same finite simulated mechanism as the pilot, not field validation.','Native CPOP engine is verified by saved R input/segments and frozen source, not rerun.','Advanced recovery-status/onset metrics are source-reviewed; primary durations, energies, selected-curve features, scores, ranks and counts independently recomputed.','Primary CP effective-sigma versus TF raw-FPR tuning remains configuration-specific; supplement added after validation is transparently separate, not a pre-validation design.','Filesystem timestamps support within-run supplement-before-test ordering and are not external trusted timestamps.'],sha256=hashes)
out=HERE/'independent_audit.json'
with out.open('x',encoding='utf8') as h:json.dump(receipt,h,ensure_ascii=False,indent=2,allow_nan=False)
print(json.dumps({k:v for k,v in receipt.items() if k not in ('checks','sha256','independent_summary')},ensure_ascii=False,indent=2))
