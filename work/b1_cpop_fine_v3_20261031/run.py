from common import *
from candidate import refine,features
from simulation import generate

def summarize(rows):
    out=[]
    for method in sorted({r['method'] for r in rows}):
      for condition in ['all']+read('protocol.json')['simulation']['conditions']:
       for kind in ['all']+read('protocol.json')['simulation']['kinds']:
        rr=[r for r in rows if r['method']==method and (condition=='all' or r['condition']==condition) and (kind=='all' or r['kind']==kind)]
        if not rr:continue
        good=[r for r in rr if r['status']=='ok'];d=dict(method=method,condition=condition,kind=kind,n=len(rr),available=len(good))
        if good:
            for key in ['primary_seconds','cumulative_error_seconds','longest_error_seconds','fp_bins','fn_bins','seconds']:
                d[key]=float(np.mean([r[key] for r in good]))
            for key in ['whole_miss','null_false_positive']:d[key]=sum(r[key] for r in good)
            d['curve_rmse_kw']=float(np.sqrt(np.mean([r['curve_mse_kw2'] for r in good])))
        out.append(d)
    return out

def main(stage):
    if stage=='test':
        freeze=read('validation_freeze.json')
        for name,h in freeze['source_sha256'].items():assert sha(ROOT/name)==h,name
        kappas=[freeze['kappa']]
    else:kappas=read('protocol.json')['active_kappas']
    cases=generate(stage);cp=[];prep={};lookup={};index=0
    for i,c in enumerate(cases):
        y=np.array(c['reference_kw'])-np.array(c['power_kw']);s=np.array(c['starts_s']);e=np.array(c['ends_s'])
        cp.append(dict(case_id=index,starts=s,ends=e,y=y,sigma=c['sigma'],train=np.ones(len(y),bool)));lookup[i,'cpop']=index;index+=1
        for k in kappas:
            tic=time.perf_counter();z,info=refine(y,s,c['command_kw'],c['sigma'],k);info['seconds']=time.perf_counter()-tic
            method=f'fine_{int(k)}';prep[i,method]=info;lookup[i,method]=index
            cp.append(dict(case_id=index,starts=s,ends=e,y=z,sigma=c['sigma'],train=np.ones(len(y),bool)));index+=1
    fitted,meta=cp_batch(cp,f'native/{stage}');labs,lmeta=labs_batch([np.array(c['reference_kw'])-np.array(c['power_kw']) for c in cases],f'labs/{stage}')
    saved=[]
    for i,c in enumerate(cases):
        results={m:fitted[ix] for (j,m),ix in lookup.items() if j==i};results['labs']=labs[i]
        for k in kappas:
            m=f'fine_{int(k)}';results[m]['fine_evidence']=prep[i,m];results[m]['seconds']+=prep[i,m]['seconds']
        saved.append(dict(task_id=c['task_id'],results=results))
    write(f'outputs/{stage}_curves.json',saved)
    # Evaluator is opened only after all fits have been saved.
    truth={t['task_id']:t for t in read(f'evaluator/{stage}.json')};rows=[]
    for c,r in zip(cases,saved):
        s=np.array(c['starts_s']);use=(s>=0)&(s<1800);clean=np.array(truth[c['task_id']]['true_reduction_kw']);tf=features(clean,s,1800,.15)
        raw=(np.array(c['reference_kw'])-np.array(c['power_kw']))[use];eta=float(raw.sum()*10/3600/(1.5*.5))
        for method,fit in r['results'].items():
            d={key:c[key] for key in ['task_id','base_task_id','seed','kind','condition']};d.update(method=method,status=fit['status'],seconds=fit.get('seconds',0.),raw_eta=eta)
            if fit['status']=='ok':
                pred=np.array(fit['prediction']);f=features(pred,s,1800,.15)
                ce=abs(f['cumulative_seconds']-tf['cumulative_seconds']);le=abs(f['longest_seconds']-tf['longest_seconds'])
                d.update(features=f,true_features=tf,cumulative_error_seconds=ce,longest_error_seconds=le,primary_seconds=.5*(ce+le),
                    whole_miss=tf['threshold_positive'] and not f['threshold_positive'],null_false_positive=not tf['threshold_positive'] and f['threshold_positive'],
                    fp_bins=int(np.sum((pred[use]>=.15)&(clean[use]<.15))),fn_bins=int(np.sum((pred[use]<.15)&(clean[use]>=.15))),
                    curve_mse_kw2=float(np.mean((pred[use]-clean[use])**2)))
            rows.append(d)
    summaries=summarize(rows);write(f'outputs/{stage}_metrics.json',rows);write(f'outputs/{stage}_summary.json',summaries)
    write(f'outputs/{stage}_runtime.json',dict(native=meta,labs=lmeta,workers=4,not_exclusive_latency=True))
    if stage=='validation':
        candidates=[r for r in summaries if r['kind']==r['condition']=='all' and r['method'].startswith('fine_') and r['available']==r['n']]
        minimum=min(r['primary_seconds'] for r in candidates);best=max((r for r in candidates if r['primary_seconds']<=minimum+1e-9),key=lambda r:r['method'])
        files=[p for p in HERE.glob('*.py')]+[HERE/'protocol.json',OLD/'vendor/LABS/LABS_functions.R',OLD/'labs_batch.R']
        files += [ROOT/name for name in read('protected_before.json') if name.startswith('B1算法/')]
        write('validation_freeze.json',dict(kappa=float(best['method'].split('_')[1]),method=best['method'],validation_primary=best['primary_seconds'],
            source_sha256={p.relative_to(ROOT).as_posix():sha(p) for p in files}))
    print(json.dumps([r for r in summaries if r['kind']=='all'],ensure_ascii=False),flush=True)
if __name__=='__main__':main(sys.argv[1])
