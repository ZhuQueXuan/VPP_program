from common import *

KINDS_FINE=['smooth_strong','smooth_weak','brief_weak','interrupted','early_exit','oscillatory','delayed_rebound','null','one_minute_response','one_minute_gap','one_finebin_response','one_finebin_gap']
def generate(panel,seeds,per_kind,prefix):
    if panel=='minute':
        m=load_module(V1/'simulation.py','_fresh_minute_generator');cases=[];truth=[]
        for seed in seeds:
            a,b=m.block(seed,per_kind);cases+=a;truth+=b
    else:
        m=load_module(ROOT/'work/b1_cpop_fine_v3_20261031/simulation.py','_fresh_fine_generator')
        spec=dict(simulation=dict(kinds=KINDS_FINE,conditions=['gaussian','single_sample_spikes','persistent_bursts'],batch=dict(seeds=seeds,per_kind=per_kind)))
        saved={};m.read=lambda name:spec
        def capture(name,value):saved[name]=value
        m.write=capture;cases=m.generate('batch');truth=saved['evaluator/batch.json']
    normalized=[]
    for c,t in zip(cases,truth):
        if panel=='minute':
            tid=c['task']['task_id'];s=np.asarray(c['starts'],float)*60;e=np.asarray(c['ends'],float)*60
        else:tid=c['task_id'];s=np.asarray(c['starts_s'],float);e=np.asarray(c['ends_s'],float)
        normalized.append(dict(task_id=tid,base_task_id=c['base_task_id'],panel=panel,seed=c['seed'],kind=c['kind'],condition=c['condition'],
            starts_s=s,ends_s=e,reference_kw=c['reference_kw'],power_kw=c['power_kw'],command_kw=c['command_kw'],sigma=c['sigma']))
        assert tid==t['task_id']
    write(prefix+'/facts.json',normalized);write(prefix+'/truth.json',truth)
    return normalized

def baseline_batches(cases,directory):
    cp=[]
    for i,c in enumerate(cases):
        y=np.asarray(c['reference_kw'])-np.asarray(c['power_kw'])
        cp.append(dict(case_id=i,starts=np.asarray(c['starts_s'])/60,ends=np.asarray(c['ends_s'])/60,y=y,sigma=c['sigma'],train=np.ones(len(y),bool)))
    # Existing versioned batch helper is reused with its output root explicitly
    # rebound to this experiment; original files/source are unchanged.
    h=load_module(ROOT/'work/b1_cpop_fine_v3_20261031/common.py','_shared_native_batches')
    h.HERE=HERE;h.ROOT=ROOT;h.OLD=PREVIOUS
    original,cm=h.cp_batch(cp,directory+'/cpop')
    labs,lm=h.labs_batch([c['y'] for c in cp],directory+'/labs')
    return original,labs,dict(cpop=cm,labs=lm,workers=4)

def generate_stress(panel,seeds,per_kind,prefix):
    cases=generate(panel,seeds,per_kind,prefix+'_unscaled');truth=read(prefix+'_unscaled/truth.json')
    bases=sorted({c['base_task_id'] for c in cases});peaks=[.08,.13,.145,.155,.18,.25]
    mapping={b:peaks[i%len(peaks)] for i,b in enumerate(bases)};newtruth=[];recipe=[]
    for c,t in zip(cases,truth):
        clean=np.asarray(t['true_reduction_kw']);s=np.asarray(c['starts_s']);inside=(s>=0)&(s<1800);peak=float(np.max(clean[inside]));scale=mapping[c['base_task_id']]/peak if peak>0 else 1.
        newclean=clean*scale;observed=np.asarray(c['reference_kw'])-np.asarray(c['power_kw']);newobserved=observed-clean+newclean
        c['power_kw']=np.asarray(c['reference_kw'])-newobserved
        newtruth.append(dict(**t,true_reduction_kw_original=t['true_reduction_kw']))
        newtruth[-1]['true_reduction_kw']=newclean
        recipe.append(dict(task_id=c['task_id'],scale=scale,requested_peak=mapping[c['base_task_id']]))
    write(prefix+'/facts.json',cases);write(prefix+'/truth.json',newtruth);write(prefix+'/generation_recipe.json',recipe)
    return cases
