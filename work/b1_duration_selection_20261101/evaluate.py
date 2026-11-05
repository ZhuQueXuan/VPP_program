from common import *
from generation import generate,generate_stress,baseline_batches
from candidates import fit_segments
from learned import features,predict_model
from fusion import reconcile
from scipy.special import expit
from b1_algorithm.process.api import _features
from b1_algorithm.resources.ev import EVAnalysisConfig

def main(stage):
    freeze=read('selection_freeze.json')
    for p,h in freeze['source_sha256'].items():assert sha(ROOT/p)==h,p
    cfg=freeze['configuration'];spec=read('evaluation_protocol.json');cases=[]
    for panel in spec['panels']:cases+=(generate_stress if stage=='stress' else generate)(panel,spec[stage+'_seeds'],spec['per_kind_'+stage],stage+'/'+panel)
    tic=time.perf_counter();original,labs,meta=baseline_batches(cases,stage+'/native');Xs=[];offset=0;slices=[];fit_times=[]
    for c in cases:
        y=np.asarray(c['reference_kw'])-np.asarray(c['power_kw']);delta=float(c['ends_s'][0]-c['starts_s'][0]);now=time.perf_counter();base=fit_segments(y,c['sigma'],3.,0.);X=features(y,base['prediction'],c['sigma'],delta)
        Xs.append(X);fit_times.append(time.perf_counter()-now);slices.append((offset,offset+len(y)));offset+=len(y)
    X=np.vstack(Xs);now=time.perf_counter();q=predict_model(read(cfg['quantile_model']),X);p=expit(predict_model(read(cfg['state_model']),X));ml_seconds=time.perf_counter()-now
    curves=[]
    for i,c in enumerate(cases):
        a,b=slices[i];pred,info=reconcile(original[i]['prediction'],q[a:b]*c['sigma'],p[a:b],c['starts_s'],c['sigma'],cfg['threshold'],cfg['band_sigma'],cfg['change_cap'],cfg['preserve_gaps'])
        fit=dict(status='ok',prediction=pred,decision=info,seconds=original[i].get('seconds',0)+fit_times[i]+ml_seconds/len(cases))
        curves.append(dict(task_id=c['task_id'],results=dict(cpop=original[i],labs=labs[i],duration_fusion=fit)))
    write(stage+'/curves.json',curves)
    truth={}
    for panel in spec['panels']:truth.update({t['task_id']:t for t in read(stage+'/'+panel+'/truth.json')})
    rows=[]
    for c,r in zip(cases,curves):
        t=np.asarray(truth[c['task_id']]['true_reduction_kw']);s=np.asarray(c['starts_s']);e=np.asarray(c['ends_s']);step=float(e[0]-s[0]);raw=np.asarray(c['reference_kw'])-np.asarray(c['power_kw']);use=(s>=0)&(s<1800)
        data=dict(starts=s/60,ends=e/60,delta=step/60,profile=EVAnalysisConfig(),q=1.5,W=30.,reference=np.asarray(c['reference_kw']),y=raw)
        truefeatures=_features(data,t)['selected_curve'];eta=float(np.sum(raw[use])*step/2700.)
        for method,fit in r['results'].items():
            d={k:c[k] for k in ['task_id','base_task_id','panel','seed','kind','condition']};d.update(method=method,status=fit['status'],eta_raw=eta,seconds=fit.get('seconds',0.))
            if fit['status']=='ok':
                metric=measure(fit['prediction'],t,s,step);metric['short_local_miss'] &= c['kind'] in ['one_bin_response','one_finebin_response','one_minute_response'];metric['true_gap_filled'] &= c['kind'] in ['one_bin_gap','one_finebin_gap','one_minute_gap'];d.update(metric)
                f=_features(data,np.asarray(fit['prediction']));d.update(features=f,true_features=truefeatures,
                    curve_mse_kw2=float(np.mean((np.asarray(fit['prediction'])[use]-t[use])**2)))
            rows.append(d)
    write(stage+'/metrics.json',rows);ss=summary([r for r in rows if r['status']=='ok']);write(stage+'/summary.json',ss)
    write(stage+'/runtime.json',dict(wall_seconds=time.perf_counter()-tic,native=meta,models_batch_seconds=ml_seconds,timing_not_selection_gate=True))
    print(json.dumps([r for r in ss if r['panel']=='all']),flush=True)
if __name__=='__main__':main(sys.argv[1])
