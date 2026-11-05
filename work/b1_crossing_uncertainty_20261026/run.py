"""Frozen experiment driver: public observations -> observed-only bands."""
from pathlib import Path
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','2')
os.environ.setdefault('OMP_NUM_THREADS','2')
import json,hashlib,time,sys
import numpy as np
import inference
BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[1]
RAW=ROOT/'data/驱动因素解耦模拟数据集_B1_crossing_uncertainty_v1_20261026'
P=json.loads((BASE/'protocol.json').read_text(encoding='utf-8'))

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def dump(name,value): (BASE/name).write_text(json.dumps(value,indent=2,ensure_ascii=False),encoding='utf-8')

def micro():
    checks=0
    def ck(v):
        nonlocal checks
        assert v;checks+=1
    from inference import invert,naive_first,old_strict
    for arr in ([0,0,0,0,.12,.2,.3],[0,.02,.18,.02,.16,0,.18],[0,0,0,0,0,0,0]):
        a=np.array(arr);v=invert(a,a,.1);n=naive_first(a,.1)
        ck((v['candidates']==[n[1]]) if n[0]=='bracket' else (not v['candidates'] and v['no_cross_possible']))
        ck(v['unique']==(n[0]=='bracket'))
    a=np.array([0,0,0,.1,.1,.1,.1]);ck(invert(a,a,.1)['candidates']==[3])
    lo=np.array([0,0,0,0,0,0,.08]);hi=np.array([0,0,0,0,0,0,.12])
    v=invert(lo,hi,.1);ck(v['candidates']==[6] and v['no_cross_possible'] and not v['unique'])
    ck(invert(np.zeros(7),np.full(7,.02)*np.array([0,1,1,1,1,1,1]),.1)['status']=='supported_not_reached')
    ck(old_strict(np.array([0,.001,0,0,.12,.2,.3]),.1)[0]=='ambiguous_nonmonotone')
    # Exhaustive rectangular-band inversion against Cartesian witnesses, including equality.
    from itertools import product
    rng=np.random.default_rng(921)
    for _ in range(100):
        lo=np.r_[0,rng.choice([0,.05,.1,.15],6)];hi=lo+np.r_[0,rng.choice([0,.05,.1],6)]
        witness=set()
        for vals in product(*[sorted(set([lo[k],hi[k]])) for k in range(1,7)]):
            witness.add(naive_first(np.r_[0,vals],.1)[1])
        v=invert(lo,hi,.1)
        ck(set(v['candidates'])|({-1} if v['no_cross_possible'] else set())==witness)
    # Cluster sufficient-statistic bootstrap agrees with explicit user copies.
    us=np.repeat(np.arange(4),14);di=np.tile(np.arange(7),8);x=np.tile([-1.,1.],28)
    y=np.array([np.arange(56)/100]);ct,sm=inference.aggregate(us,di,x,y,4)
    ids=np.array([0,0,2,3]);ww=np.bincount(ids,minlength=4)[None,:]
    out=inference.estimate(ct,sm,ww,minimum=1)
    selected=np.concatenate([np.flatnonzero(us==i) for i in ids])
    for g,mask in enumerate((np.ones(56,bool),x<0,x>=0)):
        for k in range(7):
            ix=selected[mask[selected]&(di[selected]==k)]
            ck(abs((ww@sm[0,g])[0,k]/(ww@ct[g])[0,k]-y[0,ix].mean())<1e-12)
    ct[1,:,1]=0
    out=inference.estimate(ct,sm,ww,minimum=1)
    ck(not out['available'][0,1] and np.isnan(out['q'][0,1]))
    return dict(passed=checks,failed=0)

def freeze():
    names=['protocol.json','inference.py','generate.py','run.py','evaluate.py','plot_results.py']
    identity={n:sha(BASE/n) for n in names}
    old=ROOT/'work/b1_multidose_20261026'
    protected={str(f.relative_to(ROOT)):sha(f) for f in old.iterdir() if f.is_file() and f.suffix!='.pyc'}
    live={str(f.relative_to(ROOT)):sha(f) for f in (ROOT/'资源能力模型').rglob('*') if f.is_file()}
    dump('source_freeze.json',dict(source=identity,protected_d109=protected,live_models=live))

def main():
    if '--freeze' in sys.argv:
        if (BASE/'source_freeze.json').exists():raise RuntimeError('freeze already exists; do not silently replace frozen identity')
        freeze();dump('micro_checks.json',micro());print('frozen, micro passed');return
    f=json.loads((BASE/'source_freeze.json').read_text(encoding='utf-8'))
    assert all(sha(BASE/n)==v for n,v in f['source'].items())
    if '--generate' in sys.argv:
        if (RAW/'observations.npz').exists() or (BASE/'bands.npz').exists() or (BASE/'evaluation.json').exists():raise RuntimeError('observations or revealed results already exist; no overwrite')
        import generate
        t=time.perf_counter();v=generate.main(P,RAW,BASE);v['elapsed_s']=time.perf_counter()-t;dump('generation_receipt.json',v);print(v);return
    if (BASE/'bands.npz').exists() or (BASE/'evaluation.json').exists():raise RuntimeError('inference results or truth already exist; no overwrite')
    t=time.perf_counter();obs=np.load(RAW/'observations.npz');results=[];weight_hash=[]
    for r in range(P['repetitions']):
        counts,sums=inference.aggregate(obs['user'],obs['dose'][r],obs['x'][r],obs['Y'][r],P['users'])
        rng=np.random.default_rng(P['seed_start']+r+P['bootstrap_seed_offset'])
        weights=rng.multinomial(P['users'],np.full(P['users'],1/P['users']),size=P['bootstrap_draws'])
        weight_hash.append(hashlib.sha256(weights.astype('<i8').tobytes()).hexdigest())
        results.append(inference.estimate(counts,sums,weights,P['minimum_original_group_dose_count'],P['confidence']))
        if (r+1)%20==0:print('infer',r+1,flush=True)
    np.savez_compressed(BASE/'bands.npz',**{k:np.array([v[k] for v in results]) for k in results[0]})
    dump('inference_receipt.json',dict(elapsed_s=time.perf_counter()-t,observations_sha256=sha(RAW/'observations.npz'),bands_sha256=sha(BASE/'bands.npz'),bootstrap_weight_sha256=weight_hash,unavailable_cells=int(sum((~v['available']).sum() for v in results))))
    print('inference saved',time.perf_counter()-t)

if __name__=='__main__':main()
