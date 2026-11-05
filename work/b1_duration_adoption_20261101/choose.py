"""Calibrate observable safeguards on broad seen development, then freeze anew."""
from common import *
from candidates import fit_segments
from learned import features,predict_model
from fusion import reconcile
from scipy.special import expit

def main():
    specs=[('minute',ROOT/'work/b1_cpop_jump_v2_20261031','old','main'),('10s',ROOT/'work/b1_cpop_fine_v3_20261031','old','main')]
    specs += [(p,ROOT/'work/b1_fast_selection_20261101/validation','new','main') for p in ['minute','10s']]
    specs += [(p,ROOT/'work/b1_duration_selection_20261101/validation','new','main') for p in ['minute','10s']]
    specs += [(p,ROOT/'work/b1_duration_selection_20261101/stress','new','stress') for p in ['minute','10s']]
    items=[];xx=[];offset=0;rows=[]
    for panel,path,style,cohort in specs:
        if style=='old':cases=read(path/'facts/test.json');truth={r['task_id']:r for r in read(path/'evaluator/test.json')};old={r['task_id']:r for r in read(path/'outputs/test_curves.json')}
        else:cases=read(path/panel/'facts.json');truth={r['task_id']:r for r in read(path/panel/'truth.json')};old={r['task_id']:r for r in read(path/'curves.json')}
        for c in cases:
            tid=c.get('task_id',c.get('task',{}).get('task_id'));s=np.asarray(c['starts_s'] if 'starts_s' in c else c['starts'])*(1 if 'starts_s' in c else 60.);step=float(s[1]-s[0]);y=np.array(c['reference_kw'])-np.array(c['power_kw']);t=np.array(truth[tid]['true_reduction_kw']);fit=fit_segments(y,c['sigma'],3.,0.);X=features(y,fit['prediction'],c['sigma'],step)
            items.append(dict(task_id=tid,panel=panel,cohort=cohort,kind=c['kind'],s=s,step=step,sigma=c['sigma'],truth=t,cpop=old[tid]['results']['cpop']['prediction'],start=offset,end=offset+len(y)));xx.append(X);offset+=len(y)
            for method in ['cpop','labs']:
                d=measure(old[tid]['results'][method]['prediction'],t,s,step);d.update(method=method,panel=panel,cohort=cohort,task_id=tid,seconds=0.);d['short_local_miss'] &= c['kind'] in ['one_bin_response','one_finebin_response','one_minute_response'];d['true_gap_filled'] &= c['kind'] in ['one_bin_gap','one_finebin_gap','one_minute_gap'];rows.append(d)
    X=np.vstack(xx);prob=expit(predict_model(read('model_classifier.json'),X));quantile=predict_model(read('model_q50.json'),X)
    settings={}
    for threshold in [.4,.5,.6,.7,.8,.9]:
      for cap in [.05,.1,.2,1.]:
        name=f't{threshold:g}_cap{cap:g}';settings[name]=dict(threshold=threshold,change_cap=cap,preserve_gaps=True,band_sigma=2.,quantile_model='model_q50.json',state_model='model_classifier.json')
        for c in items:
            a,b=c['start'],c['end'];pred,info=reconcile(c['cpop'],quantile[a:b]*c['sigma'],prob[a:b],c['s'],c['sigma'],threshold,2.,cap,True)
            d=measure(pred,c['truth'],c['s'],c['step']);d.update(method=name,panel=c['panel'],cohort=c['cohort'],task_id=c['task_id'],seconds=0.,curve_mse=float(np.mean((pred-c['truth'])**2)),decision_reason=info['reason']);d['short_local_miss'] &= c['kind'] in ['one_bin_response','one_finebin_response','one_minute_response'];d['true_gap_filled'] &= c['kind'] in ['one_bin_gap','one_finebin_gap','one_minute_gap'];rows.append(d)
    def group(method,cohort):
        rr=[r for r in rows if r['method']==method and r['cohort']==cohort]
        d=dict(method=method,cohort=cohort,n=len(rr))
        for k in ['primary_seconds','cumulative_error_seconds','longest_error_seconds','curve_mse']:d[k]=float(np.mean([r.get(k,0.) for r in rr]))
        for k in ['short_local_miss','true_gap_filled','whole_miss','null_false_positive']:d[k]=int(sum(r[k] for r in rr))
        return d
    summaries=[group(m,c) for m in ['cpop','labs']+list(settings) for c in ['main','stress']];safe=[];base=group('cpop','main');stress=group('cpop','stress')
    for name,cfg in settings.items():
        a,b=group(name,'main'),group(name,'stress')
        if a['primary_seconds']<=.9*base['primary_seconds'] and b['primary_seconds']<=stress['primary_seconds']+5 and all(a[k]<=base[k] for k in ['short_local_miss','true_gap_filled','whole_miss','null_false_positive']) and a['cumulative_error_seconds']<=base['cumulative_error_seconds']:
            safe.append(dict(method=name,score=.5*(a['primary_seconds']/base['primary_seconds']+b['primary_seconds']/stress['primary_seconds']),main=a,stress=b,config=cfg))
    safe=[r for r in safe if all(r['stress'][k]<=stress[k] for k in ['short_local_miss','true_gap_filled'])]
    write('guarded_development_metrics.json',rows);write('guarded_development_summary.json',summaries);write('guarded_rank.json',sorted(safe,key=lambda r:r['score']))
    print(json.dumps(sorted(safe,key=lambda r:r['score'])[:5]),flush=True)
if __name__=='__main__':main()
