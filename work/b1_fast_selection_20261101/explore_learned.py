from common import *
from candidates import fit_segments
from learned import features,predict_model

def main():
    items=[];Xs=[];offset=0;baseline_rows=[]
    for panel,p in [('minute',ROOT/'work/b1_cpop_jump_v2_20261031'),('10s',ROOT/'work/b1_cpop_fine_v3_20261031')]:
        cases=json.loads((p/'facts/test.json').read_text(encoding='utf-8'));truth={r['task_id']:r for r in json.loads((p/'evaluator/test.json').read_text(encoding='utf-8'))};old={r['task_id']:r for r in json.loads((p/'outputs/test_curves.json').read_text(encoding='utf-8'))}
        for c in cases:
            tid=c.get('task_id',c.get('task',{}).get('task_id'));s=np.array(c['starts_s'] if panel=='10s' else c['starts'])*(1. if panel=='10s' else 60.);step=float(s[1]-s[0]);y=np.array(c['reference_kw'])-np.array(c['power_kw']);t=np.array(truth[tid]['true_reduction_kw'])
            tic=time.perf_counter();fit=fit_segments(y,c['sigma'],3.,0.);X=features(y,fit['prediction'],c['sigma'],step);elapsed=time.perf_counter()-tic
            item=dict(panel=panel,task_id=tid,kind=c['kind'],starts=s,step=step,sigma=c['sigma'],truth=t,base=np.array(fit['prediction']),start=offset,end=offset+len(y),base_seconds=elapsed);offset+=len(y);items.append(item);Xs.append(X)
            for m in ['cpop','labs']:
                d=measure(old[tid]['results'][m]['prediction'],t,s,step);d.update(panel=panel,method=m,task_id=tid,seconds=old[tid]['results'][m]['seconds']);d['short_local_miss'] &= c['kind'] in ['one_bin_response','one_finebin_response','one_minute_response'];d['true_gap_filled'] &= c['kind'] in ['one_bin_gap','one_finebin_gap','one_minute_gap'];baseline_rows.append(d)
    X=np.vstack(Xs);rows=baseline_rows.copy();settings={}
    for leaves in [15,31]:
        payload=read(f'model_l{leaves}.json');tic=time.perf_counter();allpred=predict_model(payload,X);elapsed=time.perf_counter()-tic;print('inference model',leaves,'seconds',elapsed,flush=True)
        for weight in [.25,.5,1.]:
          for band in [1.,2.,3.]:
           for zone in ['band','below']:
            method=f'learn_l{leaves}_w{weight:g}_{zone}{band:g}';settings[method]=dict(model=f'model_l{leaves}.json',weight=weight,band_sigma=band,zone=zone,beta=3.)
            for c in items:
                base=c['base'];learn=allpred[c['start']:c['end']]*c['sigma'];use=(abs(base-.15)<=band*c['sigma']) if zone=='band' else base<=.15+band*c['sigma']
                pred=np.where(use,(1-weight)*base+weight*learn,base);d=measure(pred,c['truth'],c['starts'],c['step'])
                d.update(method=method,panel=c['panel'],task_id=c['task_id'],seconds=c['base_seconds']+elapsed/len(items));d['short_local_miss'] &= c['kind'] in ['one_bin_response','one_finebin_response','one_minute_response'];d['true_gap_filled'] &= c['kind'] in ['one_bin_gap','one_finebin_gap','one_minute_gap'];rows.append(d)
    ss=summary(rows);write('development_learned_metrics.json',rows);write('development_learned_summary.json',ss);write('learned_settings.json',settings)
    base=next(r for r in ss if r['method']=='cpop' and r['panel']=='all')
    acceptable=[r for r in ss if r['panel']=='all' and r['method'] in settings and r['short_local_miss']<=base['short_local_miss'] and r['true_gap_filled']<=base['true_gap_filled'] and r['null_false_positive']<=base['null_false_positive']]
    write('development_acceptable_rank.json',sorted(acceptable,key=lambda r:r['primary_seconds']))
    print(json.dumps(sorted([r for r in ss if r['panel']=='all'],key=lambda r:r['primary_seconds'])[:8]),flush=True)
    print('safe',json.dumps(sorted(acceptable,key=lambda r:r['primary_seconds'])[:5]),flush=True)
if __name__=='__main__':main()
