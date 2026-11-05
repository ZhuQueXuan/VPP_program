from common import *
from generation import generate,generate_stress,baseline_batches
from candidates import fit_segments
from learned import features,predict_model

def run(stage):
    f=read('selection_freeze.json')
    for p,h in f['source_sha256'].items():assert sha(ROOT/p)==h,p
    spec=read('evaluation_protocol.json');seeds=spec[stage+'_seeds'];per=spec['per_kind_'+stage];cases=[]
    for panel in spec['panels']:cases+=(generate_stress if stage=='stress' else generate)(panel,seeds,per,stage+'/'+panel)
    tic=time.perf_counter();original,labs,meta=baseline_batches(cases,stage+'/native')
    cfg=f['settings'];payload=read(cfg['model']);base=[];Xs=[];offset=0;times=[];slices=[]
    for c in cases:
        y=np.asarray(c['reference_kw'])-np.asarray(c['power_kw']);delta=float(c['ends_s'][0]-c['starts_s'][0]);t0=time.perf_counter()
        fit=fit_segments(y,c['sigma'],cfg['beta'],0.);X=features(y,fit['prediction'],c['sigma'],delta)
        base.append(fit);Xs.append(X);times.append(time.perf_counter()-t0);slices.append((offset,offset+len(y)));offset+=len(y)
    t0=time.perf_counter();learned=predict_model(payload,np.vstack(Xs));learn_seconds=time.perf_counter()-t0
    curves=[]
    for i,c in enumerate(cases):
        a,b=slices[i];pred=np.asarray(base[i]['prediction']);correction=learned[a:b]*c['sigma'];use=pred<=.15+cfg['band_sigma']*c['sigma']
        chosen=dict(status='ok',prediction=np.where(use,(1-cfg['weight'])*pred+cfg['weight']*correction,pred),seconds=times[i]+learn_seconds/len(cases),segments=base[i]['segments'])
        curves.append(dict(task_id=c['task_id'],results=dict(cpop=original[i],labs=labs[i],segment_boost=chosen)))
    write(stage+'/curves.json',curves)
    # Fits complete before evaluator is read.
    truths={}
    for panel in spec['panels']:truths.update({t['task_id']:t for t in read(stage+'/'+panel+'/truth.json')})
    rows=[]
    for c,r in zip(cases,curves):
        truth=np.asarray(truths[c['task_id']]['true_reduction_kw']);s=np.asarray(c['starts_s']);step=float(c['ends_s'][0]-c['starts_s'][0]);use=(s>=0)&(s<1800)
        eta=float(np.sum((np.asarray(c['reference_kw'])-np.asarray(c['power_kw']))[use])*step/(1.5*1800))
        for method,fit in r['results'].items():
            d={k:c[k] for k in ['task_id','base_task_id','panel','seed','kind','condition']};d.update(method=method,status=fit['status'],seconds=fit.get('seconds',0.),eta_raw=eta)
            if fit['status']=='ok':
                m=measure(fit['prediction'],truth,s,step);m['short_local_miss'] &= c['kind'] in ['one_bin_response','one_finebin_response','one_minute_response'];m['true_gap_filled'] &= c['kind'] in ['one_bin_gap','one_finebin_gap','one_minute_gap'];d.update(m)
                d['curve_mse_kw2']=float(np.mean((np.asarray(fit['prediction'])[use]-truth[use])**2))
            rows.append(d)
    write(stage+'/metrics.json',rows);ss=summary([r for r in rows if r['status']=='ok']);write(stage+'/summary.json',ss)
    write(stage+'/runtime.json',dict(baselines=meta,wall_seconds=time.perf_counter()-tic,learned_batch_seconds=learn_seconds,
        learned_allocated_per_case_seconds=learn_seconds/len(cases),parallel_batch_not_exclusive_latency=True))
    print(json.dumps([r for r in ss if r['panel']=='all']),flush=True)
if __name__=='__main__':run(sys.argv[1])
