"""Independent artifact verification; no imports from fitted study modules."""
from pathlib import Path
import ast
import csv
import hashlib
import json
import math
import sys

import numpy as np

BASE=Path(__file__).resolve().parent
PROJECT=BASE.parent.parent
CHECKS=[]
MAXIMA={}


def check(name,ok,detail=None):
    CHECKS.append(dict(name=name,ok=bool(ok),detail=detail))


def discrepancy(name,a,b,tolerance=1e-10):
    err=float(np.max(np.abs(np.asarray(a)-np.asarray(b))))
    MAXIMA[name]=max(MAXIMA.get(name,0.),err)
    check(name,err<tolerance,err)


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    with np.load(path,allow_pickle=False) as f:return {k:f[k] for k in f.files}


def basis(d,mi):
    d=np.asarray(d)
    if mi==1:return np.stack([np.ones_like(d),d],axis=-1)
    if mi==2:return np.stack([np.ones_like(d),d,np.fmax(d-.8,0),np.fmax(d-1.6,0)],axis=-1)
    raise ValueError(mi)


def independent_mean(scene,d,group,nodes=48):
    """Tensor Gaussian quadrature in independent x,w,u, V/delay averaged."""
    z,weight=np.polynomial.legendre.leggauss(nodes)
    x=z if group==0 else (z-1)/2 if group==1 else (z+1)/2
    x=x[:,None,None];w=z[None,:,None];u=z[None,None,:]
    base=.12+.06*(x+1)+.06*w+.04*u
    if scene=='zero':
        eta=-.5+.7*x-.6*w+.8*u
        p=1/(1+np.exp(-eta))
    elif scene=='linear':p=base+.22*d/2.4
    elif scene=='hinge':p=base+.3*max(0,d-1.2)/1.2
    elif scene=='smooth':
        eta=-2.5+4*d/2.4+.7*x-.6*w+.8*u
        p=1/(1+np.exp(-eta))
    else:raise ValueError(scene)
    tensor=weight[:,None,None]*weight[None,:,None]*weight[None,None,:]/8
    opening=(.4+.2*(x+1))*(.8+.2*w*w)
    return np.array([np.sum(p*tensor),np.sum(p*opening*.975*tensor)])


def independent_crossing(curve,delta,doses):
    gain=np.asarray(curve)-curve[0]
    if not np.isfinite(curve).all():return ('unavailable',None,None)
    if max(gain)<delta:return ('not_reached',None,None)
    if min(np.diff(curve)) < -1e-10:return ('ambiguous_nonmonotone',None,None)
    k=next(j for j,g in enumerate(gain) if g>=delta)
    return ('bracket',float(doses[k-1]),float(doses[k]))


def main():
    p=json.loads((BASE/'protocol.json').read_text(encoding='utf-8-sig'))
    rawdir=PROJECT/p['raw_root'];raw=load(rawdir/'observations.npz')
    pred=load(BASE/'predictions.npz');truth=load(BASE/'evaluation_truth.npz')
    doses=np.asarray(p['doses_yuan_per_kwh']);scenes=p['scenarios'];groups=p['groups']
    methods=list(p['methods']);outcomes=p['outcomes']
    check('observed-only raw keys',set(raw)=={'X','dose','user','split','A','Y'},list(raw))
    check('frozen observation shapes',raw['X'].shape==(20,8400,2)
          and all(raw[k].shape==(20,8400) for k in ('dose','user','split'))
          and all(raw[k].shape==(20,4,8400) for k in ('A','Y')))
    check('valid observed domains',np.isfinite(raw['X']).all() and np.isfinite(raw['Y']).all()
          and (abs(raw['X'])<=1).all() and np.isin(raw['A'],[0,1]).all()
          and np.isin(raw['dose'],np.arange(7)).all() and np.isin(raw['split'],[0,1,2]).all())
    check('prediction array shapes',pred['curve'].shape==(20,4,2,3,3,7)
          and pred['test_factual'].shape==(20,4,2,3,1680))
    rebuilt=np.empty_like(pred['curve']);losses=[];support=[]
    for r in range(20):
        x,di,users,split=[raw[k][r] for k in ('X','dose','user','split')]
        uu,cc=np.unique(users,return_counts=True)
        check(f'{r}: 600 users each 14 events',np.array_equal(uu,np.arange(600)) and (cc==14).all())
        sets=[set(users[split==j]) for j in range(3)]
        check(f'{r}: 360/120/120 user isolation',[len(z) for z in sets]==[360,120,120]
              and not(sets[0]&sets[1] or sets[0]&sets[2] or sets[1]&sets[2]))
        masks=[np.ones(len(di),bool),x[:,0]<0,x[:,0]>=0]
        for s,scene in enumerate(scenes):
            observed=np.stack([raw['A'][r,s],raw['Y'][r,s]],axis=1)
            for g,group in enumerate(groups):
                tr=(split==0)&masks[g]; counts=np.bincount(di[tr],minlength=7)
                support.append(dict(seed=p['seeds'][r],scenario=scene,group=group,
                                    train_dose_counts=counts.tolist()))
                check(f'{r}/{s}/{g}: training dose supports',(counts>=50).all(),counts.tolist())
                fitted=[]
                means=np.array([observed[tr & (di==k)].mean(axis=0) for k in range(7)])
                fitted.append(means)
                # Main uses lstsq. Here solve full-rank normal equations,
                # then separately validate residual normal-equation score.
                coefficients={}
                for m in (1,2):
                    b=basis(doses[di[tr]],m);target=observed[tr]
                    coef=np.linalg.solve(b.T@b,b.T@target);coefficients[m]=coef
                    check(f'{r}/{s}/{g}/{m}: normal equation rank',np.linalg.matrix_rank(b)==b.shape[1])
                    score=np.max(abs(b.T@(target-b@coef)))/len(b)
                    check(f'{r}/{s}/{g}/{m}: least-squares score',score<1e-10,float(score))
                    fitted.append(basis(doses,m)@coef)
                for m,method in enumerate(methods):
                    rebuilt[r,s,:,g,m]=fitted[m].T
                    for o,outcome in enumerate(outcomes):
                        row=dict(seed=p['seeds'][r],scenario=scene,group=group,method=method,outcome=outcome)
                        for part,partname in [(1,'validation'),(2,'test')]:
                            mask=(split==part)&masks[g]
                            values=means[di[mask],o] if m==0 else (basis(doses[di[mask]],m)@coefficients[m])[:,o]
                            row[partname+'_mse']=math.fsum((float(v)-float(y))**2 for v,y in zip(values,observed[mask,o]))/len(values)
                            if g==0 and part==2:discrepancy('persisted factual predictions',values,pred['test_factual'][r,s,o,m])
                        row['negative_steps']=int(np.sum(np.diff(fitted[m][:,o]) < -1e-10))
                        row['probability_out_of_bounds']=int(np.sum((fitted[m][:,o]<0)|(fitted[m][:,o]>1))) if o==0 else None
                        losses.append(row)
    discrepancy('all dose curve estimates independently rebuilt',rebuilt,pred['curve'])
    published_losses=json.loads((BASE/'losses.json').read_text())
    check('all fixed losses retained',len(published_losses)==len(losses)==1440)
    lookup={(z['seed'],z['scenario'],z['group'],z['method'],z['outcome']):z for z in losses}
    for row in published_losses:
        rec=lookup[tuple(row[k] for k in ('seed','scenario','group','method','outcome'))]
        for key in ('validation_mse','test_mse'):discrepancy('factual losses independent recomputation',row[key],rec[key])
        check('negative steps and acceptance bound flags',all(row[k]==rec[k] for k in ('negative_steps','probability_out_of_bounds')))
    recorded_support=json.loads((BASE/'fit_diagnostics.json').read_text())
    check('all training supports independently reproduced',recorded_support==support)
    owntruth=np.empty((4,2,3,7))
    for s,scene in enumerate(scenes):
        for g in range(3):
            for k,d in enumerate(doses):owntruth[s,:,g,k]=independent_mean(scene,d,g)
        discrepancy('population all equals half low plus half high',owntruth[s,:,0],owntruth[s,:,1:].mean(axis=1),1e-12)
    discrepancy('population truth by independent 48-node integral',owntruth,truth['curve'],1e-10)
    verify_metrics(p,pred,owntruth,truth)
    verify_panel(rawdir,raw)
    verify_sources(p,rawdir)
    report=dict(status='passed' if all(z['ok'] for z in CHECKS) else 'failed',
                identity='independent_simulation_numerical_and_contract_verification_only',
                checks_passed=sum(z['ok'] for z in CHECKS),checks_failed=sum(not z['ok'] for z in CHECKS),
                maxima=MAXIMA,checks=CHECKS,verifier_sha256=sha(Path(__file__)),
                input_hashes={str(z.relative_to(PROJECT)):sha(z) for z in [rawdir/'observations.npz',
                    BASE/'predictions.npz',BASE/'evaluation_truth.npz',BASE/'protocol.json']})
    (BASE/'independent_verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('status','checks_passed','checks_failed','maxima')}))
    return 0 if report['status']=='passed' else 1


def verify_metrics(p,pred,owntruth,truth):
    doses=np.asarray(p['doses_yuan_per_kwh']);methods=list(p['methods']);scenes=p['scenarios']
    groups=p['groups'];outcomes=p['outcomes'];curve=pred['curve']
    lookup={};crosslookup={};root_values=np.full((4,3,2),np.nan)
    for s,scene in enumerate(scenes):
        for g,group in enumerate(groups):
            for ei,delta in enumerate((.1,.05)):
                baseline=owntruth[s,1,g,0]
                if owntruth[s,1,g,-1]-baseline>=delta:
                    lo,hi=0.,2.4
                    # A different quadrature resolution and pure bisection
                    # independently check evaluator brentq continuous roots.
                    for _ in range(46):
                        middle=(lo+hi)/2
                        if independent_mean(scene,middle,g,24)[1]-baseline>=delta:hi=middle
                        else:lo=middle
                    root_values[s,g,ei]=(lo+hi)/2
    check('continuous root availability matches',np.array_equal(np.isfinite(root_values),np.isfinite(truth['continuous_roots'])))
    finite=np.isfinite(root_values)
    discrepancy('continuous roots independent bisection',root_values[finite],truth['continuous_roots'][finite],1e-10)
    for r,seed in enumerate(p['seeds']):
        for s,scene in enumerate(scenes):
            for o,outcome in enumerate(outcomes):
                for g,group in enumerate(groups):
                    target=owntruth[s,o,g]
                    for m,method in enumerate(methods):
                        c=curve[r,s,o,g,m]
                        err=[float(a-b) for a,b in zip(c,target)]
                        changes=[((float(c[k+1])-float(c[k]))-(float(target[k+1])-float(target[k])))/.4 for k in range(6)]
                        rec=dict(seed=seed,scenario=scene,outcome=outcome,group=group,method=method,
                            curve_rmse=math.sqrt(math.fsum(z*z for z in err)/7),
                            sensitivity_rmse=math.sqrt(math.fsum(z*z for z in changes)/6),
                            endpoint_gain_error=float(c[-1]-c[0]-target[-1]+target[0]),
                            negative_steps=sum(c[k+1]-c[k]<-1e-10 for k in range(6)))
                        lookup[(seed,scene,outcome,group,method)]=rec
                        if o!=1:continue
                        for ei,delta in enumerate((.1,.05)):
                            result=independent_crossing(c,delta,doses)
                            expected=independent_crossing(target,delta,doses)
                            root=root_values[s,g,ei]
                            correct=result==expected
                            contained=(result[0]=='bracket' and np.isfinite(root)
                                       and result[1]-1e-10<=root<=result[2]+1e-10)
                            crosslookup[(seed,scene,group,method,delta)]=dict(
                                seed=seed,scenario=scene,group=group,method=method,delta=delta,
                                status=result[0],lower=result[1],upper=result[2],
                                true_status=expected[0],true_lower=expected[1],true_upper=expected[2],
                                continuous_root=float(root) if np.isfinite(root) else None,
                                state_and_grid_correct=correct,continuous_root_contained=contained,
                                spurious_bracket=expected[0]=='not_reached' and result[0]=='bracket')
    for name,lookupdata,keys in [('metrics.csv',lookup,('seed','scenario','outcome','group','method')),
                                ('crossings.csv',crosslookup,('seed','scenario','group','method','delta'))]:
        with (BASE/name).open(encoding='utf-8-sig',newline='') as stream:published=list(csv.DictReader(stream))
        check('1440 unique rows retained: '+name,len(published)==len(lookupdata)==1440)
        seen=set()
        for row in published:
            key=tuple(int(row[k]) if k=='seed' else float(row[k]) if k=='delta' else row[k] for k in keys)
            check('unique '+name+' '+str(key),key not in seen);seen.add(key)
            expected=lookupdata[key]
            for k,v in expected.items():
                if k in keys:continue
                if v is None:check('not applicable field '+k,row[k]=='')
                elif isinstance(v,(bool,np.bool_)):check('crossing bool '+k,row[k].lower()==str(bool(v)).lower())
                elif isinstance(v,str):check('crossing state '+k,row[k]==v)
                else:discrepancy('recomputed '+name+' '+k,float(row[k]),v,1e-10)
        filename=BASE/('verification_recomputed_'+name)
        with filename.open('w',encoding='utf-8',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(next(iter(lookupdata.values()))))
            writer.writeheader();writer.writerows(lookupdata.values())
    report=json.loads((BASE/'evaluation.json').read_text())
    for row in report['summary']:
        matching=[z for z in lookup.values() if all(z[k]==row[k] for k in ('scenario','outcome','group','method'))]
        rmses=[z['curve_rmse'] for z in matching];mean=math.fsum(rmses)/20
        expected=dict(pooled_curve_rmse=math.sqrt(math.fsum(z*z for z in rmses)/20),mean_curve_rmse=mean,
            rmse_mcse=math.sqrt(math.fsum((z-mean)**2 for z in rmses)/19/20),
            pooled_sensitivity_rmse=math.sqrt(math.fsum(z['sensitivity_rmse']**2 for z in matching)/20),
            nonmonotonic_repetitions=sum(z['negative_steps']>0 for z in matching))
        for k,v in expected.items():discrepancy('summary '+k,row[k],v)
        if row['outcome']=='delivery':
            thresholds=[z for z in crosslookup.values() if z['delta']==.1
                and all(z[k]==row[k] for k in ('scenario','group','method'))]
            expected_counts={
                'correct_grid_count':sum(z['state_and_grid_correct'] for z in thresholds),
                'bracket_count':sum(z['status']=='bracket' for z in thresholds),
                'ambiguous_count':sum(z['status']=='ambiguous_nonmonotone' for z in thresholds),
                'not_reached_count':sum(z['status']=='not_reached' for z in thresholds),
                'root_contained_count':sum(z['continuous_root_contained'] for z in thresholds),
                'spurious_bracket_count':sum(z['spurious_bracket'] for z in thresholds)}
            check('summary threshold denominators and counts',all(row[k]==v for k,v in expected_counts.items()))
    for row in report['paired']:
        key=(row['scenario'],row['outcome'],row['group'])
        bymethod={method:[z for z in lookup.values() if (z['scenario'],z['outcome'],z['group'])==key and z['method']==method]
                  for method in methods[1:]}
        delta=[b['curve_rmse']**2-a['curve_rmse']**2 for a,b in zip(bymethod[methods[1]],bymethod[methods[2]])]
        mean=math.fsum(delta)/20
        discrepancy('paired MSE difference',row['spline_minus_linear_mse'],mean)
        discrepancy('paired MCSE',row['delta_mcse'],math.sqrt(math.fsum((z-mean)**2 for z in delta)/19/20))
        check('paired wins',row['spline_better_count']==sum(z<0 for z in delta))


def verify_panel(rawdir,raw):
    panel=load(rawdir/'request_panel.npz');hidden=load(BASE/'panel_evaluator.npz')
    check('public request panel observed-only fields',set(panel)=={'time_edges_s','reference_kw','power_obs_kw','indices'})
    check('84 representative request curves',panel['power_obs_kw'].shape==(84,120))
    t=panel['time_edges_s'];reference=panel['reference_kw']
    check('declared request time boundaries',np.array_equal(t,np.arange(600.,1801.,10.)) and np.array_equal(reference,np.full(120,3.)))
    for i,(scene,event,x,w,a,delay,opening,y) in enumerate(hidden['meta']):
        scene,event=int(scene),int(event)
        integral=math.fsum((float(reference[j])-float(panel['power_obs_kw'][i,j]))*float(t[j+1]-t[j]) for j in range(120))/1800
        discrepancy('public curve integral equals factual Y',integral,raw['Y'][0,scene,event],1e-12)
        discrepancy('evaluator meta factual Y',integral,y,1e-12)
        discrepancy('opening matches declared mechanism',opening,(.4+.2*(x+1))*(.8+.2*w*w),1e-12)
        check(f'panel {i}: action labels internally valid',a in (0,1) and delay in range(0,61,10)
              and a==raw['A'][0,scene,event] and np.array_equal(panel['indices'][i],[scene,event]))
    x=raw['X'][...,0];w=raw['X'][...,1]
    opening=(.4+.2*(x+1))*(.8+.2*w*w)
    horizon=3600+1800*(x+1);pmax=3.5+.75*(x+1)
    recovery=(pmax-3)*(horizon-1800)-1.5*opening*1200
    check('all 168000 base conditions bound request power and worst recovery',
          (3-1.5*opening>=0).all() and (recovery>=0).all(),
          {'minimum_recovery_margin_kws':float(recovery.min())})


def verify_sources(p,rawdir):
    frozen=json.loads((BASE/'source_freeze.json').read_text())
    for name,value in frozen.items():check('frozen scientific source '+name,sha(BASE/name)==value)
    receipt=json.loads((BASE/'fit_receipt.json').read_text())
    check('fit source raw and prediction identity',receipt['raw_sha256']==sha(rawdir/'observations.npz')
          and receipt['prediction_sha256']==sha(BASE/'predictions.npz') and not receipt['truth_existed_before_fit'])
    check('240 group model packages and reload',receipt['persisted_group_model_packages']==240 and receipt['reload_exact'])
    tree=ast.parse((BASE/'run.py').read_text(encoding='utf-8-sig'))
    fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='fit_all')
    text=ast.unparse(fn)
    check('fit only factual A/Y with predecision dose groups',"raw['A']" in text and "raw['Y']" in text
          and not any(z in text for z in ('panel_evaluator','probability(',"raw['u']","raw['v']",'truth[')))
    model_text=(BASE/'models.py').read_text(encoding='utf-8-sig')
    model_ast=ast.parse(model_text)
    imports=[ast.unparse(n) for n in ast.walk(model_ast) if isinstance(n,(ast.Import,ast.ImportFrom))]
    check('models do not import generation/evaluation',not any('generate' in z or 'evaluate' in z for z in imports))
    check('models have no clipping or adaptive knots','clip(' not in model_text and 'max(0,d-1.2)' not in model_text)


if __name__=='__main__':raise SystemExit(main())
