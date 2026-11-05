from common import *
from model import current_baseline,infer
from b1_algorithm.process import _known_duration as KD,_local_response as LR

def cache(stage):
    cases=read(stage+'/facts.json');curves={r['task_id']:r['results'] for r in read(stage+'/curves.json')};truth={}
    for f in curves.values():
        if 'retained' in f:f['duration_fusion']=f.pop('retained')
    for panel in ['minute','10s']:
        for name in ['truth.json','mixed_truth.json']:truth.update({r['task_id']:r for r in read(HERE/stage/panel/name)})
    folder=HERE/stage
    if (folder/'baseline.json').exists():
        b=read(stage+'/baseline.json');base=np.asarray(b['durations']);masks=[np.asarray(m,bool) for m in b['masks']];X=np.load(folder/'effective_X.npy')
    else:
        base,masks,X=current_baseline(cases,curves);write(stage+'/baseline.json',dict(durations=base,masks=masks));np.save(folder/'effective_X.npy',X)
    probabilities={leaves:expit(LR.fast_predict(read(f'verifier{leaves}.json'),X)) for leaves in read('protocol.json')['leaves']}
    return cases,curves,truth,base,masks,probabilities

def score(cached,config):
    cases,curves,truth,base,masks,probs=cached;rows=[]
    for i,c in enumerate(cases):
        s=np.asarray(c['starts_s']);task=(s>=0)&(s<1800);dt=c['ends_s'][0]-s[0];clean=np.asarray(truth[c['task_id']]['true_reduction_kw']);tm=clean[task]>=.15;actual=KD.durations(clean,s,dt);f=curves[c['task_id']]
        value,mask,reject=infer(c,base[i],masks[i],probs[config['leaves']][i],config['threshold'],config['duration_cap'])
        variants=dict(cpop=(KD.durations(f['cpop']['prediction'],s,dt),np.asarray(f['cpop']['prediction'])[task]>=.15),labs=(KD.durations(f['labs']['prediction'],s,dt),np.asarray(f['labs']['prediction'])[task]>=.15),retained=(base[i],masks[i][task]),candidate=(value,mask[task]))
        for method,(v,m) in variants.items():
            positive=v[0]>0;hit=positive and np.any(m&tm);short=bool(0<actual[0]<=60.+1e-8);genuine=short and c['kind'] in ['one_bin_response','one_minute_response','one_finebin_response']
            rows.append(dict(**{k:c[k] for k in ['task_id','base_task_id','panel','condition','seed','kind']},method=method,status='ok',
                primary_seconds=float((abs(v[0]-actual[0])+abs(v[1]-actual[1]))/2),cumulative_error_seconds=float(abs(v[0]-actual[0])),longest_error_seconds=float(abs(v[1]-actual[1])),
                true_cumulative_seconds=float(actual[0]),predicted_cumulative_seconds=float(v[0]),true_longest_seconds=float(actual[1]),predicted_longest_seconds=float(v[1]),
                positive_truth=bool(actual[0]>0),positive_prediction=bool(positive),null_false_positive=bool(actual[0]==0 and positive),whole_miss=bool(actual[0]>0 and not positive),localized_miss=bool(actual[0]>0 and not hit),
                short_n=short,short_local_miss=bool(short and not hit),genuine_short_n=bool(genuine),genuine_short_miss=bool(genuine and not hit),
                physical_no_action=bool(max(clean[task])<=.04),rejected=bool(reject) if method=='candidate' else False,
                rejected_positive_truth=bool(reject and actual[0]>0) if method=='candidate' else False,
                effective_score=float(probs[config['leaves']][i]) if method=='candidate' else None))
    return rows

def aggregate(rows,method):
    rr=[r for r in rows if r['method']==method];out=dict(n=len(rr))
    for key in ['primary_seconds','cumulative_error_seconds','longest_error_seconds']:
        out[key]=float(np.mean([np.mean([np.mean([r[key] for r in rr if r['panel']==p and r['condition']==c]) for c in sorted({r['condition'] for r in rr if r['panel']==p})]) for p in sorted({r['panel'] for r in rr})]))
    for key in ['positive_truth','null_false_positive','whole_miss','localized_miss','short_n','short_local_miss','genuine_short_n','genuine_short_miss','rejected','rejected_positive_truth']:out[key]=int(sum(r[key] for r in rr))
    out['task_accuracy']=1-(out['null_false_positive']+out['whole_miss'])/out['n']
    return out
def summary(rows):return {m:aggregate(rows,m) for m in ['cpop','labs','retained','candidate']}

def gates(main,weak):
    s=dict(main=summary(main),weak=summary(weak),pooled=summary(main+weak));checks={}
    checks['false_reduction10']=s['pooled']['candidate']['null_false_positive']<=.9*s['pooled']['retained']['null_false_positive']
    for label,rr in [('main',main),('weak',weak)]:
        old=s[label]['retained'];new=s[label]['candidate'];checks[label+'_false_nonincrease']=new['null_false_positive']<=old['null_false_positive']
        for k in ['whole_miss','localized_miss','short_local_miss','genuine_short_miss']:checks[label+'_'+k+'_nonincrease']=new[k]<=old[k]
        checks[label+'_no_true_task_rejected']=new['rejected_positive_truth']==0
        checks[label+'_duration_noninferiority2s']=new['primary_seconds']<=old['primary_seconds']+2
    return checks,s

def choose():
    cached=[cache(s) for s in ['main_validation','weak_validation']];results=[];valid=[]
    for leaves in read('protocol.json')['leaves']:
      for threshold in read('protocol.json')['thresholds']:
       for cap in read('protocol.json')['duration_caps_seconds']:
        cfg=dict(leaves=leaves,threshold=threshold,duration_cap=cap);checks,s=gates(*[score(c,cfg) for c in cached]);r=dict(config=cfg,checks=checks,summary=s);results.append(r)
        if all(checks.values()):valid.append(r)
    write('validation_grid.json',results);valid.sort(key=lambda r:r['summary']['pooled']['candidate']['null_false_positive']);write('eligible.json',valid)
    if not valid:print('No effective verifier passed validation',flush=True);return
    selected=valid[0];write('selected.json',selected);paths=list(HERE.glob('*.py'))+[HERE/'protocol.json',HERE/'selected.json']+list(HERE.glob('verifier*.json'))
    paths += [p for p in (ROOT/'B1算法').rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    write('freeze.json',dict(source_sha256={p.relative_to(ROOT).as_posix():sha(p) for p in paths},current_final_not_generated=True))
    print(json.dumps(native(dict(config=selected['config'],checks=selected['checks'],summary=selected['summary']['pooled']))),flush=True)

def final(stage):
    for p,h in read('freeze.json')['source_sha256'].items():assert sha(ROOT/p)==h,p
    rows=score(cache(stage),read('selected.json')['config']);write(stage+'/metrics.json',rows);write(stage+'/assessment.json',summary(rows));print(stage,json.dumps(native(summary(rows))),flush=True)
if __name__=='__main__':choose() if sys.argv[1]=='choose' else final(sys.argv[1])
