from common import *
from candidate import state_features
from task_model import features as event_features

GEN=load(OLD/'generation.py','known_generator')

def run(stage):
    if stage in ['test','stress_test']:
        for p,h in read('freeze.json')['source_sha256'].items():assert sha(ROOT/p)==h,p
    spec=read('protocol.json');stress='stress' in stage;cases=[]
    for panel in ['minute','10s']:
        prefix=stage+'/'+panel;block=(GEN.generate_stress if stress else GEN.generate)(panel,spec[stage+'_seeds'],spec[stage+'_per_kind'],prefix)
        for c in block:c['regime']='known'
        truth=read(prefix+'/truth.json');by={r['task_id']:r for r in truth};extra=[];extra_truth=[]
        # Preserve existing conditions; add variable-count faults to ordinary
        # records only, without consulting any response or latent label.
        for c in block:
            if c['condition']!='gaussian':continue
            seed=int.from_bytes(__import__('hashlib').sha256(c['task_id'].encode()).digest()[:4],'little');rng=np.random.default_rng(seed)
            s=np.array(c['starts_s']);inside=np.flatnonzero((s>=0)&(s<1800));addition=np.zeros(len(s))
            for _ in range(int(rng.integers(1,4))):
                width=int(rng.choice([1,2,4]));start=int(rng.choice(inside[:-4]));addition[start:start+width]+=float(rng.choice([-1.,1.])*rng.uniform(.25,1.0))
            x=dict(c,task_id=c['task_id']+'-mixed',condition='mixed_anomalies',power_kw=np.array(c['power_kw'])-addition)
            extra.append(x);t=dict(by[c['task_id']],task_id=x['task_id'],injected_indices=np.flatnonzero(addition),injected_residual_additions_kw=addition[addition!=0]);extra_truth.append(t)
        write(prefix+'/mixed_facts.json',extra);write(prefix+'/mixed_truth.json',extra_truth);cases+=block+extra
    write(stage+'/facts.json',cases)
    for name in ['cpop','labs']:(HERE/stage/'native'/name).mkdir(parents=True,exist_ok=True)
    cp,labs,_=GEN.baseline_batches(cases,stage+'/native');old=preserved_curves(cases,[cp[i] for i in range(len(cases))]);curves=[];Xs=[];slices=[];offset=0;event=[]
    for i,c in enumerate(cases):
        x=state_features(c,cp[i]['prediction']);Xs.append(x);slices.append([offset,offset+len(x)]);offset+=len(x)
        event.append(event_features(c,cp[i]['prediction'],old[i]['prediction']));curves.append(dict(task_id=c['task_id'],results=dict(cpop=cp[i],labs=labs[i],retained=old[i])))
    write(stage+'/curves.json',curves);write(stage+'/slices.json',slices);np.save(HERE/stage/'state_X.npy',np.vstack(Xs));np.save(HERE/stage/'event_X.npy',np.vstack(event))
    print(stage,'complete',len(cases),flush=True)
if __name__=='__main__':run(sys.argv[1])
