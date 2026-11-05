from common import *
from error_tracking import forecasts,predict as track
from dataclasses import asdict

GEN=load(OLD/'generation.py','unchanged_batch_helper')

def generate(stage):
    spec=read('protocol.json')[stage];gen=load(ROOT/'work/b1_reliability_20261031/study/generator.py','source_generator');cases=[];truth=[];source=[]
    for cohort in ['main','short']:
      for seed in spec[cohort+'_seeds']:
        sets=gen.generate_reliability(seed,spec[cohort+'_users'],variants=tuple(['null'] if cohort=='short' else ['strong','weak','null']),clock_shift_min=spec['shift'])
        rng=np.random.default_rng(seed+290000);faults={};shorts={}
        for variant,(fs,ts,_) in sets.items():
          predicted=forecasts(fs)
          for f,t,pred in zip(fs,ts,predicted):
            identity=f['task']['task_id'];s=(np.array(f['starts_min'])-f['task']['start_min'])*60;e=s+60.
            if identity not in faults:
                ix=rng.choice(np.arange(15,45),2,replace=False);v=rng.choice([-1.,1.],2)*rng.uniform(.4,.9,2);a=np.zeros(60);a[ix]=v;faults[identity]=a
                clean=np.zeros(60);clean[int(rng.integers(18,42))]=float(rng.uniform(.45,1.5));shorts[identity]=clean
            for action in (['null','short'] if cohort=='short' else [variant]):
                addition=shorts[identity] if action=='short' else np.zeros(60);clean=np.array(t['true_reduction_kw'])+addition
                for condition in ['ordinary','spikes']:
                    tid=identity+'-'+action+'-'+cohort+'-'+condition;power=np.array(f['power_kw'])-addition-(faults[identity] if condition=='spikes' else 0.)
                    cases.append(dict(task_id=tid,base_task_id=identity+'-'+action+'-'+cohort,physical_task_id=identity,user_id=f['task']['user_id'],cohort=cohort,kind=action,seed=seed,panel='minute',regime='unknown',condition=condition,starts_s=s,ends_s=e,reference_kw=pred,power_kw=power,sigma=.05))
                    truth.append(dict(task_id=tid,true_reduction_kw=clean,true_reference_kw=t['true_reference_kw']))
            source.append(f)
    write(stage+'/facts.json',cases);write(stage+'/truth.json',truth);write(stage+'/source_facts.json',source);return cases

def dual_short(old_prediction,new_prediction,starts):
    old=np.asarray(old_prediction);out=np.asarray(new_prediction).copy();s=np.asarray(starts);task=(s>=0)&(s<1800);mask=(old>=.15)&task
    edges=np.diff(np.r_[False,mask,False].astype(int))
    for a,b in zip(np.flatnonzero(edges==1),np.flatnonzero(edges==-1)):
        if b-a<=1:out[a:b]=np.maximum(out[a:b],old[a:b])
    return out

def run(stage):
    if stage=='test':
        for p,h in read('freeze.json')['source_sha256'].items():assert sha(ROOT/p)==h,p
    cases=generate(stage);model=read(read('error_tracking/selection.json')['selected']['model']);raw=np.array([np.array(c['reference_kw'])-np.array(c['power_kw']) for c in cases]);bias=track(model,raw)
    tracked=[]
    for c,b in zip(cases,bias):
        x=dict(c,reference_kw=np.array(c['reference_kw'])-b);tracked.append(x)
    write(stage+'/bias_prediction.json',[dict(task_id=c['task_id'],conditional_error_kw=b) for c,b in zip(cases,bias)])
    combined=cases+tracked
    for name in ['cpop','labs']:(HERE/stage/'native'/name).mkdir(parents=True,exist_ok=True)
    cp,labs,_=GEN.baseline_batches(combined,stage+'/native');retained=preserved_curves(combined,[cp[i] for i in range(len(combined))]);n=len(cases);curves=[]
    for i,c in enumerate(cases):
        fits=dict(old_cpop=cp[i],old_labs=labs[i],old_retained=retained[i],tracked_cpop=cp[n+i],tracked_labs=labs[n+i],tracked_retained=retained[n+i])
        fits['dual_short']=dict(status='ok',prediction=dual_short(retained[i]['prediction'],retained[n+i]['prediction'],c['starts_s']))
        curves.append(dict(task_id=c['task_id'],results=fits))
    write(stage+'/curves.json',curves)
    truth={r['task_id']:r for r in read(stage+'/truth.json')};rows=[]
    for c,r in zip(cases,curves):
        for method,fit in r['results'].items():
            assert fit['status']=='ok';d=measure(fit['prediction'],truth[c['task_id']]['true_reduction_kw'],np.array(c['starts_s']),60.)
            short=d['positive_truth'] and d['true_cumulative_seconds']<=60.+1e-8
            rows.append(dict(**{k:c[k] for k in ['task_id','base_task_id','user_id','seed','cohort','kind','panel','regime','condition']},method=method,status='ok',short_n=short,short_local_miss=short and d['localized_miss'],**d))
    write(stage+'/metrics.json',rows);ss={cohort:summary([r for r in rows if r['cohort']==cohort]) for cohort in ['main','short']};write(stage+'/summary.json',ss)
    print(stage,json.dumps(native(ss)),flush=True)
if __name__=='__main__':run(sys.argv[1])
