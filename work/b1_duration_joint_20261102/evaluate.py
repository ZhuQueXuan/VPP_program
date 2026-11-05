from common import *
from model import adopted,features,refine,true_durations
from b1_algorithm.process import _known_duration as KD,_local_response as LR

def cache(stage):
    cases=read(stage+'/facts.json');curves={r['task_id']:r['results'] for r in read(stage+'/curves.json')};truth={}
    for panel in ['minute','10s']:
        for name in ['truth.json','mixed_truth.json']:truth.update({r['task_id']:r for r in read(HERE/stage/panel/name)})
    folder=HERE/stage
    if (folder/'current_baseline.json').exists():
        old=read(folder/'current_baseline.json');base=np.asarray(old['durations']);masks=[np.asarray(m,bool) for m in old['masks']];X=np.load(folder/'joint_X.npy')
    else:
        base,oldX,masks=adopted(cases,curves,True);X=[]
        for i,c in enumerate(cases):
            f=curves[c['task_id']];X.append(features(c,f['cpop']['prediction'],f['retained' if 'retained' in f else 'duration_fusion']['prediction'],base[i],oldX[i]))
        X=np.vstack(X);write(stage+'/current_baseline.json',dict(durations=base,masks=masks));np.save(folder/'joint_X.npy',X)
    predictions={}
    for leaves in read('protocol.json')['leaves']:
        predictions[leaves]={label:LR.fast_predict(read(f'{label}{leaves}.json'),X) for label in ['cumulative','fraction','absolute']}
    return cases,curves,truth,base,masks,predictions

def score(cached,config):
    cases,curves,truth,base,masks,pred=cached;rr=[]
    for i,c in enumerate(cases):
        s=np.asarray(c['starts_s']);task=(s>=0)&(s<1800);dt=c['ends_s'][0]-s[0];clean=np.asarray(truth[c['task_id']]['true_reduction_kw']);actual=true_durations(clean,s,dt);tm=clean[task]>=.15;f=curves[c['task_id']]
        prediction=[pred[config['leaves']]['cumulative'][i],pred[config['leaves']][config['head']][i]];new=refine(c,base[i],prediction,config['mix'],config['head'])
        variants=dict(cpop=(KD.durations(f['cpop']['prediction'],s,dt),np.asarray(f['cpop']['prediction'])[task]>=.15),labs=(KD.durations(f['labs']['prediction'],s,dt),np.asarray(f['labs']['prediction'])[task]>=.15),retained=(base[i],masks[i][task]),candidate=(new,masks[i][task]))
        for m,(v,mask) in variants.items():
            positive=v[0]>0;hit=bool(positive and np.any(mask&tm));short=bool(0<actual[0]<=60.+1e-8);genuine=short and c['kind'] in ['one_bin_response','one_minute_response','one_finebin_response']
            rr.append(dict(**{k:c[k] for k in ['task_id','base_task_id','panel','condition','seed','kind']},method=m,status='ok',
                primary_seconds=float((abs(v[0]-actual[0])+abs(v[1]-actual[1]))/2),cumulative_error_seconds=float(abs(v[0]-actual[0])),longest_error_seconds=float(abs(v[1]-actual[1])),
                true_cumulative_seconds=float(actual[0]),predicted_cumulative_seconds=float(v[0]),true_longest_seconds=float(actual[1]),predicted_longest_seconds=float(v[1]),
                positive_truth=bool(actual[0]>0),positive_prediction=bool(positive),null_false_positive=bool(actual[0]==0 and positive),whole_miss=bool(actual[0]>0 and not positive),localized_miss=bool(actual[0]>0 and not hit),
                short_n=short,short_local_miss=bool(short and not hit),genuine_short_n=genuine,genuine_short_miss=bool(genuine and not hit),
                long_effective=bool(actual[0]>60),no_effective=bool(actual[0]==0),explicit_gap=c['kind'] in ['interrupted','one_bin_gap','one_minute_gap','one_finebin_gap']))
    return rr

def aggregate(rows,method,subset=None):
    rr=[r for r in rows if r['method']==method and (subset is None or r[subset])];out=dict(n=len(rr))
    for key in ['primary_seconds','cumulative_error_seconds','longest_error_seconds']:
        out[key]=float(np.mean([np.mean([np.mean([r[key] for r in rr if r['panel']==p and r['condition']==c]) for c in sorted({r['condition'] for r in rr if r['panel']==p})]) for p in sorted({r['panel'] for r in rr})])) if rr else None
    for key in ['null_false_positive','whole_miss','localized_miss','short_n','short_local_miss','genuine_short_n','genuine_short_miss']:out[key]=sum(r[key] for r in rr)
    return out
def summary(rows):return {s or 'all':{m:aggregate(rows,m,s) for m in ['cpop','labs','retained','candidate']} for s in [None,'long_effective','no_effective','short_n','genuine_short_n','explicit_gap']}

def gates(main,weak):
    sa,sb,all_rows=summary(main),summary(weak),main+weak;pooled=summary(all_rows);checks={}
    checks['pooled_gain10']=pooled['all']['candidate']['primary_seconds']<=.9*pooled['all']['retained']['primary_seconds']
    checks['weak_gain10']=sb['all']['candidate']['primary_seconds']<=.9*sb['all']['retained']['primary_seconds']
    checks['long_positive_gain10']=pooled['long_effective']['candidate']['primary_seconds']<=.9*pooled['long_effective']['retained']['primary_seconds']
    checks['main_noninferiority2s']=sa['all']['candidate']['primary_seconds']<=sa['all']['retained']['primary_seconds']+2
    for label,v,rows in [('main',sa,main),('weak',sb,weak)]:
        old={r['task_id']:r for r in rows if r['method']=='retained'}
        checks[label+'_task_and_local_decisions_identical']=all(all(r[k]==old[r['task_id']][k] for k in ['positive_prediction','null_false_positive','whole_miss','localized_miss']) for r in rows if r['method']=='candidate')
        checks[label+'_short_time_noninferiority5s']=v['short_n']['candidate']['primary_seconds']<=v['short_n']['retained']['primary_seconds']+5
        checks[label+'_gap_longest_noninferiority5s']=v['explicit_gap']['candidate']['longest_error_seconds']<=v['explicit_gap']['retained']['longest_error_seconds']+5
    return checks,dict(main=sa,weak=sb,pooled=pooled)

def choose():
    caches=[cache(s) for s in ['main_validation','weak_validation']];results=[];valid=[]
    for leaves in read('protocol.json')['leaves']:
      for head in read('protocol.json')['heads']:
       for mix in read('protocol.json')['mix']:
        cfg=dict(leaves=leaves,head=head,mix=mix);rows=[score(v,cfg) for v in caches];checks,summaries=gates(*rows);r=dict(config=cfg,checks=checks,summary=summaries);results.append(r)
        if all(checks.values()):valid.append(r)
    write('validation_grid.json',results);valid.sort(key=lambda r:r['summary']['pooled']['all']['candidate']['primary_seconds']);write('eligible.json',valid)
    if not valid:print('No joint-duration configuration passed validation',flush=True);return
    selected=valid[0];write('selected.json',selected)
    paths=list(HERE.glob('*.py'))+[HERE/'protocol.json',HERE/'selected.json']+list(HERE.glob('*31.json'))+list(HERE.glob('*63.json'))
    paths += [p for p in (ROOT/'B1算法').rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    write('freeze.json',dict(source_sha256={p.relative_to(ROOT).as_posix():sha(p) for p in paths},new_final_not_generated=True))
    print(json.dumps(native(dict(config=selected['config'],checks=selected['checks'],pooled=selected['summary']['pooled']['all']))),flush=True)

def final(stage):
    for p,h in read('freeze.json')['source_sha256'].items():assert sha(ROOT/p)==h,p
    rows=score(cache(stage),read('selected.json')['config']);write(stage+'/metrics.json',rows);write(stage+'/assessment.json',summary(rows));print(stage,json.dumps(native(summary(rows)['all'])),flush=True)
if __name__=='__main__':choose() if sys.argv[1]=='choose' else final(sys.argv[1])
