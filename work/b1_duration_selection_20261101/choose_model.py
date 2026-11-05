from common import *
from candidates import fit_segments
from learned import features,predict_model
from scipy.special import expit

def main():
    items=[];Xs=[];offset=0;rows=[]
    specs=[('minute',ROOT/'work/b1_cpop_jump_v2_20261031','old'),('10s',ROOT/'work/b1_cpop_fine_v3_20261031','old'),('minute',ROOT/'work/b1_fast_selection_20261101/validation','new'),('10s',ROOT/'work/b1_fast_selection_20261101/validation','new')]
    for panel,p,style in specs:
        if style=='old':
            cases=json.loads((p/'facts/test.json').read_text(encoding='utf-8'));tt={r['task_id']:r for r in json.loads((p/'evaluator/test.json').read_text(encoding='utf-8'))};oo={r['task_id']:r for r in json.loads((p/'outputs/test_curves.json').read_text(encoding='utf-8'))}
        else:
            cases=json.loads((p/panel/'facts.json').read_text(encoding='utf-8'));tt={r['task_id']:r for r in json.loads((p/panel/'truth.json').read_text(encoding='utf-8'))};oo={r['task_id']:r for r in json.loads((p/'curves.json').read_text(encoding='utf-8'))}
        for c in cases:
            tid=c.get('task_id',c.get('task',{}).get('task_id'));s=np.array(c['starts_s'] if 'starts_s' in c else c['starts'])*(1. if 'starts_s' in c else 60.);step=float(s[1]-s[0]);y=np.array(c['reference_kw'])-np.array(c['power_kw']);truth=np.array(tt[tid]['true_reduction_kw'])
            tic=time.perf_counter();fit=fit_segments(y,c['sigma'],3.,0.);X=features(y,fit['prediction'],c['sigma'],step);elapsed=time.perf_counter()-tic
            items.append(dict(panel=panel,task_id=tid,kind=c['kind'],truth=truth,s=s,step=step,sigma=c['sigma'],base=np.array(fit['prediction']),start=offset,end=offset+len(y),base_seconds=elapsed));Xs.append(X);offset+=len(y)
            for method in ['cpop','labs']:
                fit=oo[tid]['results'][method];d=measure(fit['prediction'],truth,s,step);d.update(panel=panel,method=method,task_id=tid,seconds=fit['seconds']);d['short_local_miss'] &= c['kind'] in ['one_bin_response','one_finebin_response','one_minute_response'];d['true_gap_filled'] &= c['kind'] in ['one_bin_gap','one_finebin_gap','one_minute_gap'];rows.append(d)
    X=np.vstack(Xs);predictions={};times={}
    for name in ['q40','q50','q60','classifier']:
        p=read('model_'+name+'.json');tic=time.perf_counter();predictions[name]=predict_model(p,X);times[name]=time.perf_counter()-tic
        print('inferred',name,flush=True)
    settings={}
    for model in ['q40','q50','q60']:
      for band in [1.,2.,3.]:
       for mix in [.5,1.]:
        for cls_threshold in [None,.4,.5,.6]:
            name=f'{model}_b{band:g}_m{mix:g}_c{cls_threshold}';settings[name]=dict(model='model_'+model+'.json',classifier='model_classifier.json' if cls_threshold is not None else None,class_threshold=cls_threshold,band_sigma=band,mix=mix,beta=3.)
            for c in items:
                a,b=c['start'],c['end'];rawpred=predictions[model][a:b]*c['sigma'];base=c['base'];use=base<=.15+band*c['sigma'];z=(1-mix)*base+mix*rawpred
                if cls_threshold is not None:
                    positive=expit(predictions['classifier'][a:b])>=cls_threshold
                    z=np.where(positive,np.maximum(z,.150001),np.minimum(z,.149999))
                pred=np.where(use,z,base);d=measure(pred,c['truth'],c['s'],c['step']);d.update(panel=c['panel'],method=name,task_id=c['task_id'],seconds=c['base_seconds']+(times[model]+(times['classifier'] if cls_threshold is not None else 0))/len(items));d['short_local_miss'] &= c['kind'] in ['one_bin_response','one_finebin_response','one_minute_response'];d['true_gap_filled'] &= c['kind'] in ['one_bin_gap','one_finebin_gap','one_minute_gap'];rows.append(d)
    ss=summary(rows);write('development_metrics.json',rows);write('development_summary.json',ss);write('settings.json',settings)
    base=next(r for r in ss if r['method']=='cpop' and r['panel']=='all')
    safe=[r for r in ss if r['panel']=='all' and r['method'] in settings and r['short_local_miss']<=base['short_local_miss'] and r['true_gap_filled']<=base['true_gap_filled'] and r['null_false_positive']<=base['null_false_positive'] and r['whole_miss']<=base['whole_miss']+1 and r['cumulative_error_seconds']<=base['cumulative_error_seconds']+5]
    ranked=sorted(safe,key=lambda r:(r['primary_seconds'],r['method']));write('rank.json',ranked)
    print('best all',json.dumps(sorted([r for r in ss if r['panel']=='all'],key=lambda r:r['primary_seconds'])[:5]),flush=True);print('best safe',json.dumps(ranked[:5]),flush=True)
if __name__=='__main__':main()
