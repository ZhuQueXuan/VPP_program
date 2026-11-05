"""Graph assumptions -> identification -> observed features -> train means."""
from pathlib import Path
import json,hashlib,time,sys
import numpy as np
from features import extract
from graph import assumed,adjustment,learn
from estimators import fit,predict
BASE=Path(__file__).resolve().parent;ROOT=BASE.parents[1]
RAW=ROOT/'data/驱动因素解耦模拟数据集_B1_ev_factor_chain_v1_20261026'
P=json.loads((BASE/'protocol.json').read_text(encoding='utf-8'))
METHODS=P['methods']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(name,v):(BASE/name).write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')

def micro():
    passed=0
    for random,expected in [(True,[]),(False,['X','W'])]:
        assert adjustment(assumed(random))['selected']==expected;passed+=1
    ref=np.full((3,360),3.);power=ref.copy();power[1,66:126]=1.5;power[1,180:240]=4.5
    power[2,60:90]=1.5;power[2,120:150]=1.5
    out=extract(ref,power)
    assert np.array_equal(out['cumulative_s'],[0,600,600]);passed+=1
    assert np.array_equal(out['longest_s'],[0,600,300]);passed+=1
    assert np.array_equal(out['S'],[0,1,1]);passed+=1
    assert abs(out['net_kwh'][1]-.25)<1e-12 and abs(out['debt_end_kwh'][1])<1e-12;passed+=2
    bad=power.copy();bad[0,60]=np.nan
    try:extract(ref,bad);raise AssertionError('missing accepted')
    except ValueError:passed+=1
    # Graph screening deterministic under row permutation; no oracle edges input.
    rng=np.random.default_rng(88231);data=rng.integers(0,2,(1000,5))
    g=learn(data);g2=learn(data[rng.permutation(1000)])
    assert g['edges']==g2['edges'];passed+=1
    for col in [[],['X','W'],['X','W','A']]:
        model=fit(data[:,0],data[:,1],data[:,2],data[:,3],data[:,[4,4]],col,1)
        pred=predict(model,data[:,0],data[:,1],data[:,3]);assert pred.shape==(1000,2,2) and np.isfinite(pred).all();passed+=1
    small=fit(np.zeros(3,int),np.zeros(3,int),np.zeros(3,int),np.zeros(3,int),np.zeros((3,2)),[],1)
    assert not small['available'] and np.isnan(predict(small,np.zeros(3),np.zeros(3))).all();passed+=1
    return dict(passed=passed,failed=0)

def main():
    cmd=sys.argv[1]
    if cmd=='freeze':
        if (BASE/'source_freeze.json').exists():raise RuntimeError('already frozen')
        names=['protocol.json','features.py','graph.py','estimators.py','generate.py','run.py','evaluate.py','plot_results.py']
        protected={}
        for folder in ['work/b1_research_20261021','work/b1_history_prediction_20261026','资源能力模型']:
            for f in (ROOT/folder).rglob('*'):
                if f.is_file() and '__pycache__' not in f.parts:protected[str(f.relative_to(ROOT))]=sha(f)
        dump('source_freeze.json',dict(source={n:sha(BASE/n) for n in names},protected=protected));dump('micro_checks.json',micro());print('frozen + micro passed');return
    identity=json.loads((BASE/'source_freeze.json').read_text(encoding='utf-8'));assert all(sha(BASE/k)==h for k,h in identity['source'].items())
    if cmd=='generate':
        if (RAW/'observations.npz').exists():raise RuntimeError('raw exists')
        import generate
        start=time.perf_counter();rec=generate.main(P,RAW,BASE);rec['elapsed_s']=time.perf_counter()-start;dump('generation_receipt.json',rec);print(rec);return
    if cmd!='fit':raise ValueError('freeze/generate/fit')
    if (BASE/'predictions.npz').exists() or (BASE/'evaluation.json').exists():raise RuntimeError('predictions/evaluation already exist')
    with np.load(RAW/'observations.npz') as z:obs={k:z[k] for k in z.files}
    start=time.perf_counter();allfeatures={k:[] for k in ('cumulative_s','S','longest_s','net_kwh','Y','debt_end_kwh')}
    models=[];graphs=[];preds={'validation':[],'test':[]};indices={'validation':[],'test':[]}
    for r in range(P['repetitions']):
        tr=obs['user_split'][r]==0;hold=[np.flatnonzero(obs['user_split'][r]==k) for k in (1,2)]
        for split,ix in zip(('validation','test'),hold):indices[split].append(ix)
        repfeatures={k:[] for k in allfeatures};repmodels=[];repgraphs=[];reppred={'validation':[],'test':[]}
        for s,scene in enumerate(P['scenarios']):
            f=extract(obs['reference_kw'][r],obs['power_obs_kw'][r,s]);outcomes=np.column_stack([f['cumulative_s'],f['S']])
            for k in allfeatures:repfeatures[k].append(f[k])
            x=obs['X'][r];w=obs['W'][r];d=obs['D'][r,s];a=obs['A'][r,s]
            prior=assumed(scene.startswith('randomized'));ident=adjustment(prior)
            learned=learn(np.column_stack([x[tr],w[tr],d[tr],a[tr],f['S'][tr]]))
            repgraphs.append(dict(seed=P['seed_start']+r,scenario=scene,assumed_edges=prior,identification=ident,learned=learned))
            fits=[fit(x[tr],w[tr],d[tr],a[tr],outcomes[tr],cols,minimum) for cols,minimum in [([],20),(ident['selected'],20),(['X','W','A'],5)]]
            repmodels.append(fits)
            for split,ix in zip(('validation','test'),hold):
                reppred[split].append(np.array([predict(m,x[ix],w[ix],a[ix] if i==2 else None) for i,m in enumerate(fits)]))
        for k in allfeatures:allfeatures[k].append(repfeatures[k])
        for split in preds:preds[split].append(reppred[split])
        models.append(repmodels);graphs.append(repgraphs)
        if (r+1)%5==0:print('feature/graph/fit',r+1,flush=True)
    np.savez_compressed(BASE/'observed_features.npz',**allfeatures)
    np.savez_compressed(BASE/'predictions.npz',**preds,**{split+'_indices':indices[split] for split in indices})
    dump('models.json',models);dump('graphs.json',graphs)
    dump('fit_receipt.json',dict(elapsed_s=time.perf_counter()-start,raw_sha256=sha(RAW/'observations.npz'),features_sha256=sha(BASE/'observed_features.npz'),predictions_sha256=sha(BASE/'predictions.npz'),graphs_sha256=sha(BASE/'graphs.json'),models_sha256=sha(BASE/'models.json')))
    print('saved',time.perf_counter()-start)

if __name__=='__main__':main()
