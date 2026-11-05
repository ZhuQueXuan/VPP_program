from common import *
from features_source import state_features
GEN=load(OLD/'generation.py','local_rescue_generator')

def balanced(panel,seeds,per_kind,prefix):
    cases=GEN.generate(panel,seeds,per_kind,prefix+'_unscaled');truth=read(prefix+'_unscaled/truth.json');peaks=read('protocol.json')['balanced_peaks_kw'];mapping={}
    for seed in seeds:
        kinds=sorted({c['kind'] for c in cases if c['seed']==seed})
        for kind in kinds:
            ids=sorted({c['base_task_id'] for c in cases if c['seed']==seed and c['kind']==kind})
            rng=np.random.default_rng(int.from_bytes(hashlib.sha256((panel+str(seed)+kind).encode()).digest()[:8],'little'))
            assigned=rng.permutation(peaks);assert len(ids)==len(assigned)
            mapping.update(dict(zip(ids,assigned)))
    recipes=[]
    for c,t in zip(cases,truth):
        clean=np.asarray(t['true_reduction_kw']);s=np.asarray(c['starts_s']);inside=(s>=0)&(s<1800);peak=clean[inside].max();scale=mapping[c['base_task_id']]/peak if peak>0 else 1.;latent=clean*scale
        observed=np.asarray(c['reference_kw'])-np.asarray(c['power_kw']);c['power_kw']=np.asarray(c['reference_kw'])-(observed-clean+latent);t['true_reduction_kw']=latent
        recipes.append(dict(task_id=c['task_id'],scale=scale,requested_peak=mapping[c['base_task_id']]))
    write(prefix+'/facts.json',cases);write(prefix+'/truth.json',truth);write(prefix+'/generation_recipe.json',recipes)
    return cases

def run(stage):
    if stage.endswith('test'):
        for p,h in read('freeze.json')['source_sha256'].items():assert sha(ROOT/p)==h,p
    spec=read('protocol.json');cases=[]
    for panel in ['minute','10s']:
        prefix=stage+'/'+panel;block=(GEN.generate if stage=='main_test' else balanced)(panel,spec[stage+'_seeds'],spec[stage+'_per_kind'],prefix)
        truth={r['task_id']:r for r in read(prefix+'/truth.json')};extra=[];xt=[]
        for c in block:
            c['regime']='known'
            if c['condition']!='gaussian':continue
            rng=np.random.default_rng(int.from_bytes(hashlib.sha256(c['task_id'].encode()).digest()[:4],'little'));s=np.array(c['starts_s']);inside=np.flatnonzero((s>=0)&(s<1800));addition=np.zeros(len(s))
            for _ in range(int(rng.integers(1,4))):
                width=int(rng.choice([1,2,4]));start=int(rng.choice(inside[:-4]));addition[start:start+width]+=float(rng.choice([-1.,1.])*rng.uniform(.25,1.0))
            x=dict(c,task_id=c['task_id']+'-mixed',condition='mixed_anomalies',power_kw=np.asarray(c['power_kw'])-addition);extra.append(x)
            xt.append(dict(truth[c['task_id']],task_id=x['task_id'],injected_indices=np.flatnonzero(addition),injected_residual_additions_kw=addition[addition!=0]))
        write(prefix+'/mixed_facts.json',extra);write(prefix+'/mixed_truth.json',xt);cases+=block+extra
    write(stage+'/facts.json',cases)
    if stage=='training':
        print('training facts complete',len(cases),flush=True)
        return
    for name in ['cpop','labs']:(HERE/stage/'native'/name).mkdir(parents=True,exist_ok=True)
    cp,labs,timing=GEN.baseline_batches(cases,stage+'/native');old=preserved_curves(cases,[cp[i] for i in range(len(cases))]);curves=[];Xs=[];slices=[];offset=0
    for i,c in enumerate(cases):
        x=state_features(c,cp[i]['prediction']);Xs.append(x);slices.append([offset,offset+len(x)]);offset+=len(x)
        curves.append(dict(task_id=c['task_id'],results=dict(cpop=cp[i],labs=labs[i],duration_fusion=old[i])))
    write(stage+'/curves.json',curves);write(stage+'/slices.json',slices);write(stage+'/timing.json',timing);np.save(HERE/stage/'state_X.npy',np.vstack(Xs))
    print(stage,'complete',len(cases),flush=True)
if __name__=='__main__':run(sys.argv[1])
