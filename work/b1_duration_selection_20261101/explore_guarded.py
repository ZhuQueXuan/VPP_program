from common import *
from candidates import fit_segments
from learned import features,predict_model
from scipy.special import expit
from fusion import reconcile

def main():
    items=[];xx=[];offset=0;rows=[]
    specs=[('minute',ROOT/'work/b1_cpop_jump_v2_20261031','old'),('10s',ROOT/'work/b1_cpop_fine_v3_20261031','old'),('minute',ROOT/'work/b1_fast_selection_20261101/validation','new'),('10s',ROOT/'work/b1_fast_selection_20261101/validation','new')]
    for panel,p,style in specs:
        if style=='old':cases=read(p/'facts/test.json');truth={r['task_id']:r for r in read(p/'evaluator/test.json')};old={r['task_id']:r for r in read(p/'outputs/test_curves.json')}
        else:cases=read(p/panel/'facts.json');truth={r['task_id']:r for r in read(p/panel/'truth.json')};old={r['task_id']:r for r in read(p/'curves.json')}
        for c in cases:
            tid=c.get('task_id',c.get('task',{}).get('task_id'));s=np.asarray(c['starts_s'] if 'starts_s' in c else c['starts'])*(1 if 'starts_s' in c else 60.);step=float(s[1]-s[0]);y=np.array(c['reference_kw'])-np.array(c['power_kw']);t=np.array(truth[tid]['true_reduction_kw']);fit=fit_segments(y,c['sigma'],3.,0.);X=features(y,fit['prediction'],c['sigma'],step)
            items.append(dict(task_id=tid,panel=panel,kind=c['kind'],s=s,step=step,sigma=c['sigma'],truth=t,cpop=old[tid]['results']['cpop']['prediction'],start=offset,end=offset+len(y)));xx.append(X);offset+=len(y)
            for m in ['cpop','labs']:
                d=measure(old[tid]['results'][m]['prediction'],t,s,step);d.update(method=m,panel=panel,task_id=tid,seconds=0.);d['short_local_miss'] &= c['kind'] in ['one_bin_response','one_finebin_response','one_minute_response'];d['true_gap_filled'] &= c['kind'] in ['one_bin_gap','one_finebin_gap','one_minute_gap'];rows.append(d)
    X=np.vstack(xx);p=expit(predict_model(read('model_classifier.json'),X));q=predict_model(read('model_q50.json'),X)
    settings={}
    for threshold in [.2,.3,.4,.5,.6]:
      for cap in [.05,.1,.2,1.]:
       for keep_gaps in [False,True]:
        name=f'fusion_t{threshold:g}_cap{cap:g}_g{int(keep_gaps)}';settings[name]=dict(threshold=threshold,change_cap=cap,preserve_gaps=keep_gaps,band_sigma=2.,quantile_model='model_q50.json',state_model='model_classifier.json')
        for c in items:
            a,b=c['start'],c['end'];pred,info=reconcile(c['cpop'],q[a:b]*c['sigma'],p[a:b],c['s'],c['sigma'],threshold,2.,cap,keep_gaps)
            d=measure(pred,c['truth'],c['s'],c['step']);d.update(method=name,panel=c['panel'],task_id=c['task_id'],seconds=0.,curve_mse=float(np.mean((pred-c['truth'])**2)),decision_reason=info['reason']);d['short_local_miss'] &= c['kind'] in ['one_bin_response','one_finebin_response','one_minute_response'];d['true_gap_filled'] &= c['kind'] in ['one_bin_gap','one_finebin_gap','one_minute_gap'];rows.append(d)
    ss=summary(rows);write('guarded_metrics.json',rows);write('guarded_summary.json',ss);write('guarded_settings.json',settings)
    b=next(r for r in ss if r['method']=='cpop' and r['panel']=='all')
    safe=[r for r in ss if r['method'] in settings and r['panel']=='all' and r['short_local_miss']<=b['short_local_miss'] and r['true_gap_filled']<=b['true_gap_filled'] and r['null_false_positive']<=b['null_false_positive'] and r['whole_miss']<=b['whole_miss'] and r['cumulative_error_seconds']<=b['cumulative_error_seconds']]
    write('guarded_rank.json',sorted(safe,key=lambda r:r['primary_seconds']));print(json.dumps(sorted(safe,key=lambda r:r['primary_seconds'])[:8]),flush=True)
if __name__=='__main__':main()
