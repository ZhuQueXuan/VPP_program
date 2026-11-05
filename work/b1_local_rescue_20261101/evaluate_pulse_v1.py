from common import *
from local_model import adopted,rescue,durations
from b1_algorithm.process import _known_duration as KD
from raw_features import RAW_INDICES

OLD_LOCAL=ROOT/'work/b1_known_weak_20261101'
SEEN_MAIN=ROOT/'work/b1_known_functional_20261101'

def fast_predict(payload,X):
    X=np.asarray(X,np.float64);out=np.full(len(X),payload['baseline'],float)
    for tree in payload['trees']:
        node=np.zeros(len(X),int);active=np.arange(len(X))
        leaf=np.array([v['is_leaf'] for v in tree],bool);value=np.array([v['value'] for v in tree]);feature=np.array([v['feature_idx'] for v in tree]);threshold=np.array([v['num_threshold'] for v in tree]);left=np.array([v['left'] for v in tree]);right=np.array([v['right'] for v in tree]);missing=np.array([v['missing_go_to_left'] for v in tree],bool)
        while len(active):
            n=node[active];done=leaf[n];out[active[done]]+=value[n[done]];active=active[~done];n=n[~done]
            v=X[active,feature[n]];go=(v<=threshold[n])|(np.isnan(v)&missing[n]);node[active]=np.where(go,left[n],right[n])
    return out

def cache(stage,directory=HERE):
    source=directory/('test' if stage=='development_main' else stage);cases=read(source/'facts.json');raw=read(source/'curves.json');curves={r['task_id']:dict(r['results']) for r in raw};truth={}
    for f in curves.values():
        if 'retained' in f:f['duration_fusion']=f.pop('retained')
    for panel in ['minute','10s']:
        for name in ['truth.json','mixed_truth.json']:truth.update({r['task_id']:r for r in read(source/panel/name)})
    folder=HERE/stage;folder.mkdir(exist_ok=True);slices=read(source/'slices.json')
    if (folder/'adopted.json').exists():b=read(folder/'adopted.json');est=np.asarray(b['durations']);score=np.asarray(b['physical_score'])
    else:est,score=adopted(cases,curves);write(stage+'/adopted.json',dict(durations=est,physical_score=score))
    pp={}
    for model in read('protocol.json')['models']:
        target=folder/f'local_probability_{model}.npy'
        if not target.exists():
            X=np.load(source/'state_X.npy',mmap_mode='r')
            if isinstance(model,str):X=np.asarray(X[:,RAW_INDICES]);payload=read(f'{model}.json')
            else:payload=read(OLD_LOCAL/f'state_leaves{model}.json')
            check=np.asarray(X[::max(1,len(X)//800)])
            assert np.max(abs(fast_predict(payload,check)-KD.tree_predict(payload,check)))<1e-12
            p=expit(fast_predict(payload,X));np.save(target,p);print(stage,'local model',model,flush=True)
        pp[model]=np.load(target,mmap_mode='r')
    return cases,curves,truth,est,score,slices,pp

def score(cached,config):
    cases,curves,truth,baseline,physical,slices,probs=cached;rows=[]
    for i,c in enumerate(cases):
        s=np.asarray(c['starts_s']);task=(s>=0)&(s<1800);dt=c['ends_s'][0]-s[0];clean=np.asarray(truth[c['task_id']]['true_reduction_kw']);tm=clean[task]>=.15;actual=durations(tm,dt);f=curves[c['task_id']];a,b=slices[i]
        mask,value,added=rescue(c,f['duration_fusion']['prediction'],baseline[i],physical[i],probs[config['model']][a:b],config['threshold'],config.get('z_threshold',4.));base_mask=(np.asarray(f['duration_fusion']['prediction'])>=.15)&task
        if baseline[i,0]<=0:base_mask[:]=False
        variants=dict(cpop=((np.asarray(f['cpop']['prediction'])>=.15)&task,None),labs=((np.asarray(f['labs']['prediction'])>=.15)&task,None),retained=(base_mask,baseline[i]),candidate=(mask,value))
        for method,(m,estimate) in variants.items():
            m=m[task];estimate=durations(m,dt) if estimate is None else estimate;positive=estimate[0]>0;hit=positive and np.any(m&tm);short=bool(0<actual[0]<=60.+1e-8);genuine=c['kind'] in ['one_bin_response','one_minute_response','one_finebin_response'] and actual[0]>0;wrong=m&~tm
            row=dict(**{k:c[k] for k in ['task_id','base_task_id','seed','kind','condition','panel']},method=method,status='ok',
                primary_seconds=float((abs(estimate[0]-actual[0])+abs(estimate[1]-actual[1]))/2),cumulative_error_seconds=float(abs(estimate[0]-actual[0])),longest_error_seconds=float(abs(estimate[1]-actual[1])),
                true_cumulative_seconds=float(actual[0]),predicted_cumulative_seconds=float(estimate[0]),true_longest_seconds=float(actual[1]),predicted_longest_seconds=float(estimate[1]),
                positive_truth=bool(actual[0]>0),null_false_positive=bool(actual[0]==0 and positive),whole_miss=bool(actual[0]>0 and not positive),localized_miss=bool(actual[0]>0 and not hit),
                short_n=short,short_local_miss=bool(short and not hit),genuine_short_n=bool(genuine),genuine_short_miss=bool(genuine and not hit),
                false_positive_seconds=float(wrong.sum()*dt),localized_false_bins=int(wrong.sum()),new_bins=int(added[task].sum()) if method=='candidate' else 0,
                new_true_bins=int(sum(added[task]&tm)) if method=='candidate' else 0,
                weak=bool(.08-1e-9<=max(clean[task])<=.3),explicit_gap=c['kind'] in ['one_bin_gap','one_finebin_gap','one_minute_gap'])
            rows.append(row)
    return rows

def aggregate(rows,method,subset=None):
    rr=[r for r in rows if r['method']==method and (subset is None or r[subset])];d=dict(n=len(rr))
    for key in ['primary_seconds','cumulative_error_seconds','longest_error_seconds','false_positive_seconds']:
        d[key]=float(np.mean([np.mean([np.mean([r[key] for r in rr if r['panel']==p and r['condition']==c]) for c in sorted({r['condition'] for r in rr if r['panel']==p})]) for p in sorted({r['panel'] for r in rr})])) if rr else None
    for key in ['null_false_positive','whole_miss','localized_miss','short_n','short_local_miss','genuine_short_n','genuine_short_miss','new_bins','new_true_bins']:d[key]=int(sum(r[key] for r in rr))
    d['new_bin_precision']=d['new_true_bins']/d['new_bins'] if d['new_bins'] else 1.
    return d

def summarize(rows):return {subset or 'all':{m:aggregate(rows,m,subset) for m in ['cpop','labs','retained','candidate']} for subset in [None,'genuine_short_n','short_n','weak','explicit_gap']}

def gates(main,weak):
    a=summarize(main);b=summarize(weak);checks={};before=b['genuine_short_n']['retained'];after=b['genuine_short_n']['candidate']
    checks['weak_genuine_short_recovery10percent']=after['genuine_short_miss']<=.9*before['genuine_short_miss'] and before['genuine_short_miss']>0
    for label,v,margin in [('main',a,2.),('weak',b,5.)]:
        old=v['all']['retained'];new=v['all']['candidate']
        checks[label+'_false_tasks_nonincrease']=new['null_false_positive']<=old['null_false_positive']
        checks[label+'_short_misses_nonincrease']=new['short_local_miss']<=old['short_local_miss']
        checks[label+'_whole_misses_nonincrease']=new['whole_miss']<=old['whole_miss']
        checks[label+'_duration_noninferiority']=new['primary_seconds']<=old['primary_seconds']+margin
        checks[label+'_false_occupancy_noninferiority']=new['false_positive_seconds']<=old['false_positive_seconds']+.5
        checks[label+'_new_bin_precision75']=new['new_bin_precision']>=.75
    return checks,a,b

def choose():
    caches=[cache('development_main',SEEN_MAIN),cache('validation')];results=[];eligible=[]
    for model in read('protocol.json')['models']:
      for threshold in read('protocol.json')['thresholds']:
       for z_threshold in read('protocol.json')['z_thresholds']:
        cfg=dict(model=model,threshold=threshold,z_threshold=z_threshold);rr=[score(c,cfg) for c in caches];checks,a,b=gates(*rr);r=dict(config=cfg,checks=checks,main=a,weak=b);results.append(r)
        if all(checks.values()):eligible.append(r)
    write('validation_grid_pulse.json',results)
    eligible.sort(key=lambda r:(r['weak']['genuine_short_n']['candidate']['genuine_short_miss'],r['weak']['all']['candidate']['primary_seconds']))
    write('eligible_pulse.json',eligible)
    if not eligible:print('No local rescue candidate passed validation',flush=True);return
    write('selected.json',eligible[0]);paths=list(HERE.glob('*.py'))+[HERE/'protocol.json',HERE/'selected.json']+[HERE/f'{n}.json' for n in read('protocol.json')['models']]
    paths += [p for p in (ROOT/'B1算法').rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    write('freeze.json',dict(source_sha256={p.relative_to(ROOT).as_posix():sha(p) for p in paths},final_not_generated=True))
    print(json.dumps(native(dict(config=eligible[0]['config'],checks=eligible[0]['checks'],weak_short=eligible[0]['weak']['genuine_short_n']))),flush=True)

def final(stage):
    for p,h in read('freeze.json')['source_sha256'].items():assert sha(ROOT/p)==h,p
    rows=score(cache(stage),read('selected.json')['config']);write(stage+'/metrics.json',rows);write(stage+'/assessment.json',summarize(rows));print(stage,json.dumps(native(summarize(rows)['all'])),flush=True)

if __name__=='__main__':choose() if sys.argv[1]=='choose' else final(sys.argv[1])
