"""micro -> generation -> observed fit/predict. Evaluation is separate."""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','2')
from pathlib import Path
import sys,json,time,hashlib
import numpy as np
import joblib
from models import fit,predict,group_masks,crossing,DOSES,METHODS
BASE=Path(__file__).resolve().parent;PROJECT=BASE.parent.parent
P=json.loads((BASE/'protocol.json').read_text(encoding='utf-8'))
RAW=PROJECT/P['raw_root']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(name,x):(BASE/name).write_text(json.dumps(x,indent=2),encoding='utf-8')

def micro():
    from generate import probability,request_observations
    checks=[]
    def check(name,ok):checks.append(dict(name=name,passed=bool(ok)));assert ok,name
    # Population formula and trajectory sum are distinct paths for development cases.
    for a in (0,1):
        for c in (.32,.52,.8):
            for delay in (0,30,60):
                power,y=request_observations(np.array([a]),np.array([c]),np.array([delay]),np.zeros((1,120)))
                check(f'integral {a}/{c}/{delay}',abs(y[0]-a*c*(1-delay/1200))<1e-12)
    mesh=np.array(np.meshgrid([-1.,1.],[-1.,1.],[-1.,1.],DOSES,indexing='ij')).reshape(4,-1)
    for name in P['scenarios']:
        pp=probability(name,mesh[3],mesh[0],mesh[1],mesh[2]);check('p bounds '+name,np.all((pp>=0)&(pp<=1)))
    di=np.repeat(np.arange(7),60);d=DOSES[di]
    y=np.c_[.2+.1*d,.1+.05*d+.08*np.maximum(0,d-.8)-.04*np.maximum(0,d-1.6)]
    ms,counts=fit(di,y)
    check('OLS exact linear',np.max(abs(predict(ms[1],DOSES)[:,0]-(.2+.1*DOSES)))<1e-12)
    check('fixed spline exact basis',np.max(abs(predict(ms[2],d)-y))<1e-12)
    check('flat no crossing',crossing(np.full(7,.3),.1)['status']=='not_reached')
    check('monotone bracket',crossing(np.array([0,.02,.04,.06,.08,.12,.14]),.1)=={'status':'bracket','lower':1.6,'upper':2.})
    check('nonmonotone ambiguity',crossing(np.array([0,.04,.02,.15,.1,.2,.1]),.1)['status']=='ambiguous_nonmonotone')
    for name,call in [('unsupported extrapolation',lambda:predict(ms[1],np.array([3.]))),('unobserved M0 point',lambda:predict(ms[0],np.array([.1]))),('arm support',lambda:fit(np.zeros(60,int),np.zeros(60)))]:
        try:call()
        except ValueError:check(name,True)
        else:check(name,False)
    save('micro_checks.json',dict(passed=True,checks=checks,protocol_sha256=sha(BASE/'protocol.json')))
    print('micro checks',len(checks),'passed')

def gen():
    assert json.loads((BASE/'micro_checks.json').read_text())['passed']
    if (RAW/'observations.npz').exists():raise RuntimeError('refuse overwrite generated raw')
    sources=['protocol.json','models.py','generate.py','run.py','evaluate.py']
    save('source_freeze.json',{s:sha(BASE/s) for s in sources})
    from generate import generate
    start=time.time();r=generate(P,RAW,BASE);r['seconds']=time.time()-start
    r['raw_sha256']=sha(RAW/'observations.npz');save('generation_receipt.json',r);print(json.dumps(r))

def fit_all():
    if (BASE/'evaluation_truth.npz').exists() or (BASE/'predictions.npz').exists():raise RuntimeError('previous predictions/truth present; freeze a new study')
    raw=np.load(RAW/'observations.npz');R,S,N=raw['Y'].shape
    curves=np.empty((R,S,2,3,3,7))
    test_predictions=np.empty((R,S,2,3,1680))
    losses=[];diagnostics=[];start=time.time();packs={}
    for ri,seed in enumerate(P['seeds']):
        x,di,split,users=[raw[k][ri] for k in ('X','dose','split','user')]
        masks=group_masks(x);tr=split==0;va=split==1;te=split==2
        assert not set(users[tr])&set(users[te]) and not set(users[tr])&set(users[va]) and not set(users[va])&set(users[te])
        for si,name in enumerate(P['scenarios']):
            observed=np.c_[raw['A'][ri,si],raw['Y'][ri,si]]
            for gi,gname in enumerate(P['groups']):
                train=tr&masks[gi];models,counts=fit(di[train],observed[train]);packs[(ri,si,gi)]=models
                diagnostics.append(dict(seed=seed,scenario=name,group=gname,train_dose_counts=counts.tolist()))
                for mi,m in enumerate(models):
                    curve=predict(m,DOSES)
                    curves[ri,si,:,gi,mi,:]=curve.T
                    if gi==0:test_predictions[ri,si,:,mi,:]=predict(m,DOSES[di[te]]).T
                    for oi,outcome in enumerate(P['outcomes']):
                        rec=dict(seed=seed,scenario=name,group=gname,method=METHODS[mi],outcome=outcome)
                        for splitname,sm in [('validation',va),('test',te)]:
                            mask=sm&masks[gi]
                            fitted=predict(m,DOSES[di[mask]])[:,oi]
                            rec[splitname+'_mse']=float(np.mean((observed[mask,oi]-fitted)**2))
                        rec['negative_steps']=int(np.sum(np.diff(curve[:,oi]) < -1e-10))
                        rec['probability_out_of_bounds']=int(np.sum((curve[:,oi]<0)|(curve[:,oi]>1))) if oi==0 else None
                        losses.append(rec)
        print(f'fit {ri+1}/{R}',flush=True)
    np.savez_compressed(BASE/'predictions.npz',curve=curves,test_factual=test_predictions)
    joblib.dump(packs,BASE/'models.joblib',compress=3)
    reloaded=joblib.load(BASE/'models.joblib')
    assert np.array_equal(predict(reloaded[(0,0,0)][2],DOSES),curves[0,0,:,0,2,:].T)
    save('losses.json',losses);save('fit_diagnostics.json',diagnostics)
    save('fit_receipt.json',dict(seconds=time.time()-start,protocol_sha256=sha(BASE/'protocol.json'),
        prediction_sha256=sha(BASE/'predictions.npz'),raw_sha256=sha(RAW/'observations.npz'),
        truth_existed_before_fit=False,persisted_group_model_packages=len(packs),reload_exact=True))
    print('fit saved',len(packs),'group model packages')

if __name__=='__main__':{'micro':micro,'generate':gen,'fit':fit_all}[sys.argv[1]]()
