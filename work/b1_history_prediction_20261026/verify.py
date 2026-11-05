"""Independent history-feature, train-only normal-equation and score checks.

No imports from study features/run/generator/evaluator. Persisted sklearn
objects are read as numerical model parameters, not refitted on test data.
"""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','2');os.environ.setdefault('OMP_NUM_THREADS','2')
from pathlib import Path
import json,csv,hashlib,math
import numpy as np
import joblib
BASE=Path(__file__).resolve().parent;ROOT=BASE.parents[1]
RAW=ROOT/'data/驱动因素解耦模拟数据集_B1_history_prediction_v1_20261026'
CHECKS=[];ERRORS={}
METHODS=['C0_current','C1_history_summary','C2_history_shape','C3_history_PCA']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def check(name,ok):CHECKS.append(dict(name=name,passed=bool(ok)))
def close(name,a,b,tol=1e-9):
    a,b=np.asarray(a),np.asarray(b);err=float(np.max(abs(a-b))) if a.size else 0.;ERRORS[name]=max(ERRORS.get(name,0),err)
    check(name,a.shape==b.shape and np.isfinite(a).all() and np.isfinite(b).all() and err<tol)

def features(conditions,power,indices):
    """Vectorized independent extraction of exactly three previous curves."""
    current=conditions[indices[:,0],indices[:,1]]
    hist=np.stack([power[u,j-3:j] for u,j in indices]).astype(float)
    pastcond=np.stack([conditions[u,j-3:j] for u,j in indices])
    red=3-hist;req=red[:,:,20:60];mask=req>=.15;has=mask.any(axis=2)
    first=np.argmax(mask,axis=2)*30;first=np.where(has,first,1200)
    runs=np.zeros(has.shape,int);longest=np.zeros_like(runs)
    for j in range(40):runs=np.where(mask[:,:,j],runs+1,0);longest=np.maximum(longest,runs)
    y=np.sum(req,axis=2)/60
    n=has.sum(axis=1);meanon=np.where(n>0,np.sum(first*has,axis=1)/np.maximum(1,n)/1200,1.)
    rebound=np.maximum(-red[:,:,60:],0).sum(axis=2)/60
    summary=np.column_stack([current,pastcond.mean(axis=1),y.mean(axis=1),y[:,-1],has.mean(axis=1),meanon,longest.mean(axis=1)/40,rebound.mean(axis=1)])
    times=np.arange(20)*30;times=times-times.mean()
    early=np.sum(req[:,:,:20]*times[None,None,:],axis=2).mean(axis=1)/np.dot(times,times)*800
    late=np.sum(req[:,:,20:]*times[None,None,:],axis=2).mean(axis=1)/np.dot(times,times)*800
    shape=np.column_stack([summary,req[:,:,:20].mean(axis=(1,2))/1.5,req[:,:,20:].mean(axis=(1,2))/1.5,early,late,(y[:,-1]-y[:,0])/2,(first[:,-1]-first[:,0])/2400])
    return current,summary,shape,red.reshape(len(indices),360)/1.5

def polynomial(x,powers):
    cols=[]
    for exps in powers:
        col=np.ones(len(x))
        for j in np.flatnonzero(exps):col*=x[:,j]**int(exps[j])
        cols.append(col)
    return np.column_stack(cols)

def main():
    p=json.loads((BASE/'protocol.json').read_text(encoding='utf-8'))
    with np.load(RAW/'observations.npz') as z:obs={k:z[k] for k in z.files}
    pred=np.load(BASE/'predictions.npz');models=joblib.load(BASE/'models.joblib')
    receipt=json.loads((BASE/'fit_receipt.json').read_text(encoding='utf-8'))
    for f,k,folder in [('observations.npz','raw_sha256',RAW),('models.joblib','models_sha256',BASE),('predictions.npz','predictions_sha256',BASE)]:check('persisted '+f,sha(folder/f)==receipt[k])
    check('raw public keys',set(obs)=={'power_obs_kw','conditions','Y','A','user_split','event_start_s'})
    check('fixed complete curve shape',obs['power_obs_kw'].shape==(20,3,400,12,120) and np.isfinite(obs['power_obs_kw']).all())
    check('prediction shapes',pred['test'].shape==(20,3,4,240) and pred['validation'].shape==(20,3,4,160))
    observed_y=np.sum((3-obs['power_obs_kw'][:,:,:,:,20:60].astype(float))*30,axis=-1)/1800
    close('all288000 original curve integrals',obs['Y'],observed_y,1e-12)
    dose6=obs['conditions'][:,:,:,0]*6
    check('random doses valid',np.all(abs(dose6-np.rint(dose6))<1e-12) and np.all((np.rint(dose6)>=0)&(np.rint(dose6)<=6)))
    recomputed={'validation':[],'test':[]};train_diagnostics=[]
    for r in range(20):
        split=obs['user_split'][r];groups=[np.flatnonzero(split==k) for k in range(3)]
        check('240/80/80 disjoint users',list(map(len,groups))==[240,80,80] and not any(set(groups[i])&set(groups[j]) for i,j in [(0,1),(0,2),(1,2)]))
        trainix=np.array([(u,j) for u in groups[0] for j in [3,4,5,6]])
        indices={'train':trainix,'validation':np.array([(u,j) for u in groups[1] for j in [7,8]]),'test':np.array([(u,j) for u in groups[2] for j in [9,10,11]])}
        for splitname in ('validation','test'):check('persisted '+splitname+' target indexes',np.array_equal(indices[splitname],pred[splitname+'_indices'][r]))
        for stage,ix in indices.items():
            past_ends=(ix[:,1,None]+np.array([-3,-2,-1]))*86400+3600
            calls=ix[:,1,None]*86400+600
            check('history complete strictly before '+stage+' calls',np.all(past_ends<calls))
        rval=[];rtest=[]
        for s,scene in enumerate(p['scenarios']):
            feats={name:features(obs['conditions'][r],obs['power_obs_kw'][r,s],ix) for name,ix in indices.items()}
            pack=models[r][s];pca=pack['pca'];train=feats['train']
            close('PCA mean from train histories only',pca.mean_,train[3].mean(axis=0),1e-10)
            close('PCA orthonormality',pca.components_@pca.components_.T,np.eye(6),1e-9)
            encoded={name:(feat[3]-pca.mean_)@pca.components_.T for name,feat in feats.items()}
            matrices={name:[feat[0],feat[1],feat[2],np.column_stack([feat[1],encoded[name]])] for name,feat in feats.items()}
            # Verify each fitted model against training-only centered normal equations.
            yy=obs['Y'][r,s,trainix[:,0],trainix[:,1]];yc=yy-yy.mean()
            pp={'validation':[],'test':[]}
            for mi,model in enumerate(pack['predictors']):
                scaler=model.named_steps['standardscaler'];poly=model.named_steps['polynomialfeatures'];ridge=model.named_steps['ridge']
                x=matrices['train'][mi];mu=x.mean(axis=0);variance=np.mean((x-mu)**2,axis=0)
                close('scaler means train only',scaler.mean_,mu,1e-10);close('scaler variances train only',scaler.var_,variance,1e-10)
                check('fixed Ridge alpha and polynomial degree',ridge.alpha==10 and poly.degree==2 and not poly.include_bias)
                z=polynomial((x-mu)/scaler.scale_,poly.powers_);zc=z-z.mean(axis=0)
                coef=np.linalg.solve(zc.T@zc+10*np.eye(z.shape[1]),zc.T@yc)
                intercept=yy.mean()-z.mean(axis=0)@coef
                close('independent centered ridge coefficients',ridge.coef_,coef,2e-9);close('independent intercept',np.array(ridge.intercept_),np.array(intercept),2e-9)
                train_diagnostics.append(dict(seed=p['seed_start']+r,scenario=scene,method=METHODS[mi],train_rows=len(yy),raw_feature_dimensions=x.shape[1],expanded_dimensions=z.shape[1],train_mse=float(np.mean((z@coef+intercept-yy)**2))))
                for name in ('validation','test'):
                    xx=matrices[name][mi];zz=polynomial((xx-mu)/scaler.scale_,poly.powers_);own=zz@coef+intercept
                    close('independent '+name+' predictions',pred[name][r,s,mi],own,2e-9)
                    close('reloaded model '+name+' predictions',pred[name][r,s,mi],model.predict(xx),2e-9)
                    pp[name].append(own)
            rval.append(pp['validation']);rtest.append(pp['test'])
        recomputed['validation'].append(rval);recomputed['test'].append(rtest)
        if (r+1)%5==0:print('verify train-only models',r+1,flush=True)
    verify_metrics(p,obs,pred)
    (BASE/'fit_generalization_diagnostics.json').write_text(json.dumps(train_diagnostics,indent=2),encoding='utf-8')
    frozen=json.loads((BASE/'source_freeze.json').read_text(encoding='utf-8'))
    for k,h in frozen['source'].items():check('frozen source '+k,sha(BASE/k)==h)
    for k,h in frozen['protected'].items():check('protected prior/model '+k,sha(ROOT/k)==h)
    source=(BASE/'features.py').read_text(encoding='utf-8')
    check('features import no evaluator/generator/traits',not any(t in source for t in ('import generate','import evaluate','hidden_traits')))
    # Direct inspection of assembly contract: permitted historical exclusive end.
    check('feature API restricts history slice',"power[u,j-3:j]" in source and "conditions[u,j-3:j]" in source)
    report=dict(status='passed' if all(v['passed'] for v in CHECKS) else 'failed',checks_passed=sum(v['passed'] for v in CHECKS),checks_failed=sum(not v['passed'] for v in CHECKS),maximum_errors=ERRORS,failures=[v for v in CHECKS if not v['passed']],verifier_sha256=sha(Path(__file__)),limits='independent numeric implementation and isolation checks only, not real data validation or independent research sample counts')
    (BASE/'independent_verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report));return 0 if report['status']=='passed' else 1

def verify_metrics(p,obs,pred):
    with (BASE/'metrics.csv').open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
    expected=[]
    for r in range(20):
        for s,scene in enumerate(p['scenarios']):
            for split in ('validation','test'):
                ix=pred[split+'_indices'][r];yy=obs['Y'][r,s,ix[:,0],ix[:,1]];xx=obs['conditions'][r,ix[:,0],ix[:,1],1]
                masks=[('all',np.ones(len(ix),bool)),('x_low',xx<0),('x_high',xx>=0)]
                if split=='test':masks +=[(f'event_{j}',ix[:,1]==j) for j in (9,10,11)]
                for group,mask in masks:
                    for mi,method in enumerate(METHODS):
                        pp=pred[split][r,s,mi,mask];er=pp-yy[mask]
                        expected.append(dict(seed=p['seed_start']+r,scenario=scene,split=split,group=group,method=method,rows=int(sum(mask)),users=len(set(ix[mask,0])),
                            mse=math.fsum(float(v)**2 for v in er)/len(er),rmse=math.sqrt(math.fsum(float(v)**2 for v in er)/len(er)),mae=math.fsum(abs(float(v)) for v in er)/len(er),bias=math.fsum(er)/len(er),out_of_unit_interval_count=int(sum((pp<0)|(pp>1)))))
    check('2160 metric records retained',len(rows)==len(expected)==2160)
    for a,b in zip(rows,expected):
        for k,v in b.items():
            if isinstance(v,float):close('independent score '+k,np.array(float(a[k])),np.array(v),1e-10)
            elif isinstance(v,int):check('metric '+k,int(a[k])==v)
            else:check('metric '+k,a[k]==v)
    ev=json.loads((BASE/'evaluation.json').read_text(encoding='utf-8'))
    for a in ev['summary']:
        rr=[v for v in expected if all(v[k]==a[k] for k in ('scenario','split','group','method'))]
        check('summary20 independent repetitions',a['repetitions']==len(rr)==20)
        check('summary target count',a['total_target_rows']==sum(v['rows'] for v in rr))
        close('summary pooled RMSE',a['pooled_rmse'],np.sqrt(np.mean([v['mse'] for v in rr])))
        close('summary mean MAE',a['mean_mae'],np.mean([v['mae'] for v in rr]));close('summary mean bias',a['mean_bias'],np.mean([v['bias'] for v in rr]))
        check('summary no clipping count',a['out_of_unit_interval_count']==sum(v['out_of_unit_interval_count'] for v in rr))
    for a in ev['paired']:
        rr=[v for v in expected if all(v[k]==a[k] for k in ('scenario','split','group'))]
        before=[v for v in rr if v['method']==a['baseline']];after=[v for v in rr if v['method']==a['candidate']]
        delta=np.array([b['mse']-c['mse'] for c,b in zip(before,after)])
        close('all20 paired MSE differences',a['differences'],delta)
        close('paired mean',a['candidate_minus_baseline_mse'],delta.mean());close('paired MCSE',a['mcse'],delta.std(ddof=1)/np.sqrt(20))
        check('paired denominator and better count',a['repetitions']==20 and a['candidate_better_count']==int(sum(delta<0)))

if __name__=='__main__':raise SystemExit(main())
