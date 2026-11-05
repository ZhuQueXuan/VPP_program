"""Stages are separate so truth is calculated only after predictions exist."""
import os
os.environ.setdefault('OMP_NUM_THREADS','2')
os.environ.setdefault('OPENBLAS_NUM_THREADS','2')
from pathlib import Path
import sys,json,time,hashlib,csv,platform
import numpy as np
import joblib
from simulation import curve,generate
from estimators import EffectStudy,aipw

ROOT=Path(__file__).resolve().parent
PROJECT=ROOT.parent.parent
P=json.loads((ROOT/'protocol.json').read_text(encoding='utf-8'))
RAW=PROJECT/P['raw_root']

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def micro():
    rows=[]
    for x in (-1.,0.,1.):
        for w in (-1.,0.,1.):
            for a in (False,True):
                for delay in (0,30,60):
                    c=curve(x,w,a,delay,np.random.default_rng(1))
                    opening=(.4+.2*(x+1))*(.8+.2*w*w)
                    y_star=1.5*opening*a*(1200-delay)/1800
                    dt=np.diff(c['edges'])
                    mask=(c['edges'][:-1]>=600)&(c['edges'][:-1]<1800)
                    calc=np.sum((c['reference']-c['power'])[mask]*dt[mask])/1800
                    assert abs(calc-y_star)<1e-12
                    assert abs(np.dot(c['power'],dt)/3600-c['demand'])<1e-12
                    assert c['remaining']<1e-9
                    rows.append(dict(x=x,w=w,accept=a,delay=delay,ystar=y_star))
    r=dict(stage='micro',identity=P['identity'],cases=len(rows),passed=True,
           protocol_sha256=digest(ROOT/'protocol.json'),python=platform.python_version())
    (ROOT/'micro_checks.json').write_text(json.dumps(r,indent=2),encoding='utf-8')
    print(json.dumps(r))

def gen():
    assert json.loads((ROOT/'micro_checks.json').read_text())['passed']
    started=time.time()
    r=generate(P,RAW,ROOT)
    r.update(stage='generation',seconds=time.time()-started,
             protocol_sha256=digest(ROOT/'protocol.json'))
    (ROOT/'generation_checks.json').write_text(json.dumps(r,indent=2),encoding='utf-8')
    print(json.dumps(r))

def fit():
    start=time.time()
    truth_existed=(ROOT/'truth.npz').exists()
    if truth_existed:
        raise RuntimeError('main fit refuses previously revealed truth; use a new frozen study')
    observed=np.load(RAW/'main_observations.npz')
    shape=observed['Y'].shape[:2]+(384,)
    predictions={k:np.empty(shape) for k in ('mu0','mu1','e','ridge_effect')}
    diagnostics=[]
    (ROOT/'models').mkdir(exist_ok=True)
    for ri,seed in enumerate(P['replicate_seeds']):
        for si,name in enumerate(P['scenarios']):
            x,d,y,user,split=[observed[k][ri,si] for k in ('X','D','Y','user','split')]
            tr,va,te=split==0,split==1,split==2
            assert len(set(user[tr])&set(user[te]))==0
            m=EffectStudy().fit(x[tr],d[tr],y[tr],user[tr],not name.startswith('observed'))
            pred=m.predict_observed(x[te])
            # Evaluate diagnostics only on validation, no hyperparameter search.
            pv=m.predict_observed(x[va])
            avalid=aipw(y[va],d[va],pv['mu0'],pv['mu1'],pv['e'])
            for key in predictions:
                predictions[key][ri,si]=pred[key]
            path=ROOT/'models'/f'{seed}_{name}.joblib'
            joblib.dump(m,path,compress=3)
            reloaded=joblib.load(path)
            assert np.array_equal(reloaded.effect(x[te][:7]),m.effect(x[te][:7]))
            assert np.allclose(m.effect(x[te][:7]),pred['mu1'][:7]-pred['mu0'][:7])
            diagnostics.append(dict(seed=seed,scenario=name,folds=m.folds,
                oof_rows=len(m.oof),oof_finite=bool(np.isfinite(m.oof).all()),
                validation_e_min=float(pv['e'].min()),validation_e_max=float(pv['e'].max()),
                test_e_min=float(pred['e'].min()),test_e_max=float(pred['e'].max()),
                validation_score_mean=float(avalid.mean()),reload_exact=True))
        print(f'fit replicate {ri+1}/{len(P["replicate_seeds"])}',flush=True)
    np.savez_compressed(ROOT/'predictions.npz',**predictions)
    (ROOT/'fit_diagnostics.json').write_text(json.dumps(diagnostics,indent=2),encoding='utf-8')
    r=dict(stage='fit',seconds=time.time()-start,protocol_sha256=digest(ROOT/'protocol.json'),
           predictions_sha256=digest(ROOT/'predictions.npz'),truth_existed_at_fit_start=truth_existed,
           persisted_models=len(diagnostics),python=platform.python_version(),
           raw_sha256=digest(RAW/'main_observations.npz'))
    (ROOT/'fit_receipt.json').write_text(json.dumps(r,indent=2),encoding='utf-8')
    print(json.dumps(r))

if __name__=='__main__':
    {'micro':micro,'generate':gen,'fit':fit}[sys.argv[1]]()
