"""Freeze -> fresh longitudinal observations -> training-only fit -> predictions."""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','2');os.environ.setdefault('OMP_NUM_THREADS','2');os.environ.setdefault('MKL_NUM_THREADS','2')
from pathlib import Path
import json,hashlib,time,sys
import numpy as np
import joblib
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler,PolynomialFeatures
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from features import make,assemble
BASE=Path(__file__).resolve().parent;ROOT=BASE.parents[1]
RAW=ROOT/'data/驱动因素解耦模拟数据集_B1_history_prediction_v1_20261026'
P=json.loads((BASE/'protocol.json').read_text(encoding='utf-8'))
METHODS=('C0_current','C1_history_summary','C2_history_shape','C3_history_PCA')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(n,v):(BASE/n).write_text(json.dumps(v,indent=2,ensure_ascii=False,allow_nan=False),encoding='utf-8')

def micro():
    checks=0
    c=np.zeros((2,12,3));power=np.full((2,12,120),3.)
    f,ix=assemble(c,power,[0],[9]);base={k:v.copy() for k,v in f.items()}
    power[0,9:]=999;c[0,10:]=999;power[1]=888
    f,ix=assemble(c,power,[0],[9])
    for k in f:assert np.array_equal(f[k],base[k]);checks+=1
    power[0,8,20:60]=1.5
    f,ix=assemble(c,power,[0],[9]);assert f['summary'][0,7]==1.;checks+=1
    assert f['current'].shape==(1,3) and f['summary'].shape==(1,12) and f['shape'].shape==(1,18) and f['encoder_input'].shape==(1,360);checks+=4
    try:make(np.zeros(3),np.zeros((3,3)),np.full((3,120),np.nan));raise AssertionError('accepted missing')
    except ValueError:checks+=1
    return dict(passed=checks,failed=0)

def datasets(obs,r,s):
    result={};cond=obs['conditions'][r];power=obs['power_obs_kw'][r,s].astype(float)
    for split,events in [('train',P['train_target_events']),('validation',P['validation_target_events']),('test',P['test_target_events'])]:
        code={'train':0,'validation':1,'test':2}[split];users=np.flatnonzero(obs['user_split'][r]==code)
        feat,index=assemble(cond,power,users,events);result[split]=(feat,index)
    return result

def matrices(feat,pca):return [feat['current'],feat['summary'],feat['shape'],np.column_stack([feat['summary'],pca.transform(feat['encoder_input'])])]

def main():
    command=sys.argv[1]
    if command=='freeze':
        if (BASE/'source_freeze.json').exists():raise RuntimeError('already frozen')
        files=['protocol.json','features.py','generate.py','run.py','evaluate.py','plot_results.py']
        protected={}
        for folder in ['work/b1_fullcycle_features_20261026','work/b1_crossing_uncertainty_20261026','资源能力模型']:
            for f in (ROOT/folder).rglob('*'):
                if f.is_file() and '__pycache__' not in f.parts:protected[str(f.relative_to(ROOT))]=sha(f)
        dump('source_freeze.json',dict(source={n:sha(BASE/n) for n in files},protected=protected));dump('micro_checks.json',micro());print('freeze + micro passed');return
    frozen=json.loads((BASE/'source_freeze.json').read_text(encoding='utf-8'));assert all(sha(BASE/n)==h for n,h in frozen['source'].items())
    if command=='generate':
        if (RAW/'observations.npz').exists():raise RuntimeError('observations exist')
        import generate
        t=time.perf_counter();v=generate.main(P,RAW,BASE);v['elapsed_s']=time.perf_counter()-t;dump('generation_receipt.json',v);print(v);return
    if command!='fit':raise ValueError('freeze/generate/fit')
    if (BASE/'predictions.npz').exists() or (BASE/'evaluation.json').exists():raise RuntimeError('predictions/truth already exist')
    with np.load(RAW/'observations.npz') as z:obs={k:z[k] for k in z.files}
    t=time.perf_counter();models=[];val=[];test=[];diagnostics=[];indices=[]
    for r in range(P['repetitions']):
        rval=[];rtest=[];rmodels=[];rindices=[]
        for s,scene in enumerate(P['scenarios']):
            data=datasets(obs,r,s);train,ti=data['train']
            pca=PCA(n_components=6,svd_solver='randomized',iterated_power=3,random_state=18).fit(train['encoder_input'])
            xtrain=matrices(train,pca);ytrain=obs['Y'][r,s,ti[:,0],ti[:,1]]
            fitted=[make_pipeline(StandardScaler(),PolynomialFeatures(2,include_bias=False),Ridge(alpha=10,solver='cholesky')).fit(x,ytrain) for x in xtrain]
            pp={}
            for name in ('validation','test'):
                feat,index=data[name];xx=matrices(feat,pca);pp[name]=np.array([m.predict(x) for m,x in zip(fitted,xx)])
                if s==0:rindices.append(index)
            rval.append(pp['validation']);rtest.append(pp['test']);rmodels.append(dict(pca=pca,predictors=fitted))
            diagnostics.append(dict(seed=P['seed_start']+r,scenario=scene,train_rows=len(ti),validation_rows=len(data['validation'][1]),test_rows=len(data['test'][1]),pca_explained_variance_ratio=pca.explained_variance_ratio_.tolist(),feature_dims=[x.shape[1] for x in xtrain]))
        val.append(rval);test.append(rtest);models.append(rmodels);indices.append(rindices)
        if (r+1)%5==0:print('fit',r+1,flush=True)
    np.savez_compressed(BASE/'predictions.npz',validation=val,test=test,validation_indices=np.array([v[0] for v in indices]),test_indices=np.array([v[1] for v in indices]))
    joblib.dump(models,BASE/'models.joblib',compress=3);dump('fit_diagnostics.json',diagnostics)
    dump('fit_receipt.json',dict(elapsed_s=time.perf_counter()-t,predictions_sha256=sha(BASE/'predictions.npz'),models_sha256=sha(BASE/'models.joblib'),raw_sha256=sha(RAW/'observations.npz')))
    print('fitted, saved',time.perf_counter()-t)

if __name__=='__main__':main()
