from common import *
from candidate import tree_predict
from model import input_features,durations,refine
DEV=ROOT/'work/b1_known_weak_20261101'

def truth_for(directory,stage):
    t={}
    for panel in ['minute','10s']:
        for name in ['truth.json','mixed_truth.json']:t.update({r['task_id']:r for r in read(directory/stage/panel/name)})
    return t

def dataset(stage,directory=DEV):
    cases=read(directory/stage/'facts.json');curves={r['task_id']:r for r in read(directory/stage/'curves.json')};truth=truth_for(directory,stage);X=[]
    for c in cases:
        r=curves[c['task_id']]['results'];X.append(input_features(c,r['cpop']['prediction'],r['retained']['prediction']))
    X=np.vstack(X);event=expit(tree_predict(read('physical_event_model.json'),X));delta={}
    for leaves in read('protocol.json')['duration_leaves']:
        delta[leaves]=np.column_stack([tree_predict(read(f'{label}_leaves{leaves}.json'),X) for label in ['cumulative','longest']])
    return cases,curves,truth,event,delta

def score(dataset_value,config):
    cases,curves,truth,event,delta=dataset_value;rows=[]
    for i,c in enumerate(cases):
        f=curves[c['task_id']]['results'];s=np.array(c['starts_s']);use=(s>=0)&(s<1800);step=c['ends_s'][0]-s[0];t=np.array(truth[c['task_id']]['true_reduction_kw']);true=durations(t,s,step);tm=t[use]>=.15
        accepted=event[i]>=config['event_threshold'];est=refine(c,f['cpop']['prediction'],f['retained']['prediction'],delta[config['leaves']][i],accepted,config['shrink'])
        estimates={m:durations(r['prediction'],s,step) for m,r in f.items()};estimates['candidate']=est
        for method,value in estimates.items():
            curve=np.asarray(f['retained' if method=='candidate' else method]['prediction']);mask=curve[use]>=.15
            if method=='candidate' and not accepted:mask=np.zeros(len(mask),bool)
            positive=bool(value[0]>0);short=bool(0<true[0]<=60.+1e-8);ce=abs(value[0]-true[0]);le=abs(value[1]-true[1])
            rows.append(dict(**{k:c[k] for k in ['task_id','base_task_id','panel','condition','seed','kind']},method=method,status='ok',
                primary_seconds=float(.5*(ce+le)),cumulative_error_seconds=float(ce),longest_error_seconds=float(le),
                positive_truth=bool(true[0]>0),positive_prediction=positive,null_false_positive=bool(true[0]==0 and positive),whole_miss=bool(true[0]>0 and not positive),
                localized_miss=bool(true[0]>0 and (not positive or not np.any(tm&mask))),short_n=short,short_local_miss=bool(short and (not positive or not np.any(tm&mask))),
                weak=bool(.08<=max(t[use])<=.3),explicit_gap=bool(c['kind'] in ['one_bin_gap','one_finebin_gap','one_minute_gap']),
                true_cumulative_seconds=float(true[0]),true_longest_seconds=float(true[1]),predicted_cumulative_seconds=float(value[0]),predicted_longest_seconds=float(value[1]),
                event_score=float(event[i]) if method=='candidate' else None))
    return rows

def aggregate(rows,method,subset=None):
    rr=[r for r in rows if r['method']==method and (subset is None or r[subset])];d=dict(n=len(rr))
    for k in ['primary_seconds','cumulative_error_seconds','longest_error_seconds']:
        d[k]=float(np.mean([np.mean([np.mean([r[k] for r in rr if r['panel']==p and r['condition']==c]) for c in sorted({r['condition'] for r in rr if r['panel']==p})]) for p in sorted({r['panel'] for r in rr})]))
    for k in ['null_false_positive','whole_miss','localized_miss','short_local_miss','short_n']:d[k]=int(sum(r[k] for r in rr))
    return d

def choose():
    caches={stage:dataset(stage) for stage in ['validation','stress_validation']};all_results=[];eligible=[]
    for leaves in read('protocol.json')['duration_leaves']:
      for shrink in read('protocol.json')['duration_shrink']:
       for threshold in read('protocol.json')['event_thresholds']:
        config=dict(leaves=leaves,shrink=shrink,event_threshold=threshold);rows={p:score(v,config) for p,v in caches.items()};ss={p:{m:aggregate(rr,m) for m in ['cpop','labs','retained','candidate']} for p,rr in rows.items()};weak={m:aggregate(rows['stress_validation'],m,'weak') for m in ss['validation']};checks={}
        checks['weak10percent_gain']=weak['candidate']['primary_seconds']<=.9*weak['retained']['primary_seconds']
        checks['main_noninferiority2s']=ss['validation']['candidate']['primary_seconds']<=ss['validation']['retained']['primary_seconds']+2
        checks['main_fewer_false']=ss['validation']['candidate']['null_false_positive']<ss['validation']['retained']['null_false_positive']
        for p,rr in rows.items():
            for key in ['short_local_miss','whole_miss']:checks[p+'_'+key]=ss[p]['candidate'][key]<=ss[p]['retained'][key]
            checks[p+'_gap_duration_noninferiority5s']=aggregate(rr,'candidate','explicit_gap')['longest_error_seconds']<=aggregate(rr,'retained','explicit_gap')['longest_error_seconds']+5
            checks[p+'_short_duration_noninferiority5s']=aggregate(rr,'candidate','short_n')['primary_seconds']<=aggregate(rr,'retained','short_n')['primary_seconds']+5
        result=dict(config=config,checks=checks,main=ss['validation'],stress=ss['stress_validation'],weak=weak);all_results.append(result)
        if all(checks.values()):
            result['score']=weak['candidate']['primary_seconds']/weak['retained']['primary_seconds']+ss['validation']['candidate']['null_false_positive']/max(1,ss['validation']['retained']['null_false_positive']);eligible.append(result)
    write('validation_grid_extended.json',all_results);eligible.sort(key=lambda r:r['score']);write('eligible_extended.json',eligible)
    if not eligible:print('NO functional candidate passed validation',flush=True);return
    selected=eligible[0];write('selected.json',selected);paths=list(HERE.glob('*.py'))+[HERE/'protocol.json',HERE/'selected.json',HERE/'physical_event_model.json']+list(HERE.glob('*_leaves*.json'))
    paths += [p for p in (ROOT/'B1算法').rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    write('freeze.json',dict(source_sha256={p.relative_to(ROOT).as_posix():sha(p) for p in paths},final_test_not_generated=True,existing_duration_curve_is_not_relabelled_as_calibrated_duration_mask=True))
    print(json.dumps(native(selected)),flush=True)

def final(stage):
    for p,h in read('freeze.json')['source_sha256'].items():assert sha(ROOT/p)==h,p
    rows=score(dataset(stage,HERE),read('selected.json')['config']);write(stage+'/metrics.json',rows)
    write(stage+'/assessment.json',{subset or 'all':{m:aggregate(rows,m,subset) for m in ['cpop','labs','retained','candidate']} for subset in [None,'weak','explicit_gap']})
    print(stage,json.dumps(read(stage+'/assessment.json')),flush=True)
if __name__=='__main__':choose() if sys.argv[1]=='choose' else final(sys.argv[1])
