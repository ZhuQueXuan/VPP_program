from common import *
from candidate import decode,tree_predict
from train import truth_for

def cache(stage,state_model):
    cases=read(stage+'/facts.json');curves={r['task_id']:r for r in read(stage+'/curves.json')};truth=truth_for(stage)
    X=np.load(HERE/stage/'state_X.npy');slices=read(stage+'/slices.json');p=expit(tree_predict(read(state_model),X));gate=expit(tree_predict(read('event_model.json'),np.load(HERE/stage/'event_X.npy')))
    # Original calibrated median remains frozen. Its first42 input features are
    # shared exactly; only the new threshold-state inference changes.
    _,models,_=DF._artifacts();q=DF._tree_predict(models['quantile.json'],X[:,:42])*.05
    return cases,curves,truth,slices,p,q,gate

def metrics(case,truth,pred,method,extra=None):
    t=np.array(truth['true_reduction_kw']);s=np.array(case['starts_s']);step=case['ends_s'][0]-s[0];use=(s>=0)&(s<1800);d=measure(pred,t,s,step);peak=float(np.max(t[use]));mask=np.asarray(pred)[use]>=.15;tm=t[use]>=.15
    edges=np.diff(np.r_[False,~tm,False].astype(int));gaps=list(zip(np.flatnonzero(edges==1),np.flatnonzero(edges==-1)))
    filled=any(a>0 and b<len(tm) and np.all(mask[a:b]) for a,b in gaps)
    short=d['positive_truth'] and d['true_cumulative_seconds']<=60.+1e-8
    return dict(**{k:case[k] for k in ['task_id','base_task_id','seed','kind','condition','panel']},method=method,status='ok',weak=bool(.08<=peak<=.30),short_n=short,short_local_miss=short and d['localized_miss'],true_gap_filled=bool(filled),
        explicit_gap_fill=bool(filled and case['kind'] in ['one_bin_gap','one_finebin_gap','one_minute_gap']),**d,**(extra or {}))

def aggregate(rows,method,weak=False):
    rr=[r for r in rows if r['method']==method and (not weak or r['weak'])];out=dict(method=method,n=len(rr))
    for key in ['primary_seconds','cumulative_error_seconds','longest_error_seconds']:
        out[key]=float(np.mean([np.mean([np.mean([r[key] for r in rr if r['panel']==p and r['condition']==c]) for c in sorted({r['condition'] for r in rr if r['panel']==p})]) for p in sorted({r['panel'] for r in rr})]))
    for key in ['null_false_positive','whole_miss','localized_miss','short_local_miss','short_n','true_gap_filled','explicit_gap_fill']:out[key]=int(sum(r[key] for r in rr))
    return out

def evaluate(cache_value,configuration):
    cases,curves,truth,slices,p,q,gate=cache_value;rows=[]
    for i,(c,(a,b)) in enumerate(zip(cases,slices)):
        fits=curves[c['task_id']]['results'];cp=np.array(fits['cpop']['prediction']);pred=decode(c,cp,p[a:b],q[a:b],configuration['state_threshold'],configuration['switch_penalty']);accepted=bool(gate[i]>=configuration['event_threshold'])
        if not accepted:pred=np.zeros(len(pred))
        for method,fit in fits.items():rows.append(metrics(c,truth[c['task_id']],fit['prediction'],method))
        rows.append(metrics(c,truth[c['task_id']],pred,'candidate',dict(accepted=accepted,event_score=float(gate[i]))))
    return rows

def choose():
    spec=read('protocol.json');records=[];eligible=[]
    for name in read('training_receipt.json')['models']:
        caches={stage:cache(stage,name) for stage in ['validation','stress_validation']}
        for threshold in spec['state_thresholds']:
          for penalty in spec['switch_penalties']:
           for event_threshold in spec['event_thresholds']:
            config=dict(state_model=name,state_threshold=threshold,switch_penalty=penalty,event_threshold=event_threshold,event_model='event_model.json')
            rows={stage:evaluate(c,config) for stage,c in caches.items()};ss={stage:{m:aggregate(rr,m) for m in ['cpop','labs','retained','candidate']} for stage,rr in rows.items()}
            weak={m:aggregate(rows['stress_validation'],m,True) for m in ['cpop','labs','retained','candidate']};checks={}
            checks['weak_gain10percent']=weak['candidate']['primary_seconds']<=.9*weak['retained']['primary_seconds']
            checks['main_noninferiority2s']=ss['validation']['candidate']['primary_seconds']<=ss['validation']['retained']['primary_seconds']+2.
            checks['fewer_false_positives']=ss['validation']['candidate']['null_false_positive']<ss['validation']['retained']['null_false_positive']
            for stage in ss:
                for k in ['short_local_miss','whole_miss','explicit_gap_fill']:checks[stage+'_'+k]=ss[stage]['candidate'][k]<=ss[stage]['retained'][k]
            item=dict(config=config,checks=checks,main=ss['validation'],stress=ss['stress_validation'],weak=weak);records.append(item)
            if all(checks.values()):
                item['score']=weak['candidate']['primary_seconds']/max(1.,weak['retained']['primary_seconds'])+ss['validation']['candidate']['null_false_positive']/max(1,ss['validation']['retained']['null_false_positive'])
                eligible.append(item)
    write('validation_grid.json',records);eligible.sort(key=lambda r:r['score']);write('eligible.json',eligible)
    if not eligible:print('NO candidate passed validation',flush=True);return
    selected=eligible[0];write('selected.json',selected)
    paths=list(HERE.glob('*.py'))+[HERE/'protocol.json',HERE/'selected.json',HERE/selected['config']['state_model'],HERE/'event_model.json']
    paths += [p for p in (ROOT/'B1算法').rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    write('freeze.json',dict(source_sha256={p.relative_to(ROOT).as_posix():sha(p) for p in paths},test_not_generated=True))
    print(json.dumps(native(selected)),flush=True)

def final(stage):
    for p,h in read('freeze.json')['source_sha256'].items():assert sha(ROOT/p)==h,p
    config=read('selected.json')['config'];rows=evaluate(cache(stage,config['state_model']),config);write(stage+'/metrics.json',rows)
    ss={m:aggregate(rows,m) for m in ['cpop','labs','retained','candidate']};weak={m:aggregate(rows,m,True) for m in ss};write(stage+'/assessment.json',dict(all=ss,weak=weak));print(stage,json.dumps(native(dict(all=ss,weak=weak))),flush=True)
if __name__=='__main__':choose() if sys.argv[1]=='choose' else final(sys.argv[1])
