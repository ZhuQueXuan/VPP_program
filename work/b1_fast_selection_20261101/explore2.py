from common import *
from candidates import fit_segments,shrink_segments
from scipy.ndimage import uniform_filter1d

def main():
    write('exploration2_plan.json',dict(families=['constant-only exact segmentation','slope-coefficient risk shrinkage on fixed DP segments','fixed penalty ensembles','local Wiener'],
        development_only=True,correction='Gap preservation now checks internal zero runs only, not the pre-onset nonresponse region. Initial development outputs retained, not used as final proof.'))
    rows=[]
    for panel,p in [('minute',ROOT/'work/b1_cpop_jump_v2_20261031'),('10s',ROOT/'work/b1_cpop_fine_v3_20261031')]:
        facts=json.loads((p/'facts/test.json').read_text(encoding='utf-8'));truth={r['task_id']:r for r in json.loads((p/'evaluator/test.json').read_text(encoding='utf-8'))};old={r['task_id']:r for r in json.loads((p/'outputs/test_curves.json').read_text(encoding='utf-8'))}
        for i,c in enumerate(facts):
            tid=c.get('task_id',c.get('task',{}).get('task_id'));s=np.array(c['starts_s'] if panel=='10s' else c['starts'])*(1. if panel=='10s' else 60.);step=float(s[1]-s[0]);y=np.array(c['reference_kw'])-np.array(c['power_kw']);t=np.array(truth[tid]['true_reduction_kw']);sigma=c['sigma']
            predictions={m:(old[tid]['results'][m]['prediction'],old[tid]['results'][m]['seconds']) for m in ['cpop','labs']}
            basefits={};costs={}
            for beta in [1.,2.,3.,4.]:
                tic=time.perf_counter();fit=fit_segments(y,sigma,beta,0.);costs[beta]=time.perf_counter()-tic;basefits[beta]=fit
                for strength in [.5,1.,2.,4.,8.]:
                    tic=time.perf_counter();pred=shrink_segments(y,fit,sigma,strength);predictions[f'shrink_b{beta:g}_k{strength:g}']=(pred,costs[beta]+time.perf_counter()-tic)
                tic=time.perf_counter();flat=fit_segments(y,sigma,beta,0.,False);predictions[f'flat_b{beta:g}']=(flat['prediction'],time.perf_counter()-tic)
            for name,bs in [('ens23',[2.,3.]),('ens234',[2.,3.,4.]),('ens1234',[1.,2.,3.,4.])]:
                aa=np.array([basefits[b]['prediction'] for b in bs]);predictions[name+'_mean']=(aa.mean(axis=0),sum(costs[b] for b in bs));predictions[name+'_median']=(np.median(aa,axis=0),sum(costs[b] for b in bs))
            for window in [3,5,9,17,31]:
                tic=time.perf_counter();mean=uniform_filter1d(y,size=window,mode='nearest');var=np.maximum(0.,uniform_filter1d(y*y,size=window,mode='nearest')-mean*mean)
                pred=mean+np.maximum(0.,1.-sigma*sigma/np.maximum(var,1e-30))*(y-mean);predictions[f'wiener{window}']=(pred,time.perf_counter()-tic)
            for method,(pred,elapsed) in predictions.items():
                d=measure(pred,t,s,step);d.update(panel=panel,method=method,task_id=tid,seconds=elapsed)
                d['short_local_miss'] &= c['kind'] in ['one_bin_response','one_finebin_response','one_minute_response'];d['true_gap_filled'] &= c['kind'] in ['one_bin_gap','one_finebin_gap','one_minute_gap'];rows.append(d)
            if (i+1)%120==0:print(panel,i+1,'/',len(facts),flush=True)
    ss=summary(rows);write('development2_metrics.json',rows);write('development2_summary.json',ss)
    print(json.dumps(sorted([r for r in ss if r['panel']=='all'],key=lambda r:r['primary_seconds'])[:14]),flush=True)
if __name__=='__main__':main()
