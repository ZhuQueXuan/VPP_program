"""Independent, no-fit replay of all 24 completed continuous-R pilot cohorts."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
sys.dont_write_bytecode=True
import numpy as np
from scipy.interpolate import BSpline
from scipy.special import logit
from scipy.stats import norm
from sklearn.linear_model import Ridge

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
DESIGN=ROOT/'work/b1_point4_next_design_20261105'
sys.path.insert(0,str(HERE.parent))
from audit_stage import Audit,sha,read,plain,truth61,local_line,support,rmse


def no_fit(*a,**k):
    raise AssertionError('No fit permitted during root audit')
Ridge.fit=no_fit
spec=importlib.util.spec_from_file_location('loaded_R_query_only',DESIGN/'continuous_r.py')
cr=importlib.util.module_from_spec(spec)
spec.loader.exec_module(cr)


def state(x):
    a,b,c=np.asarray(x).T
    return np.column_stack([np.ones(len(x)),a,b,c,a*a,a*b,a*c,b*b,b*c,c*c])


def design(xs,b):
    return np.concatenate([xs,b,(xs[:,:,None]*b[:,None,:]).reshape(len(xs),-1)],axis=1)


def spline(model,a):
    s=model['spline']
    return BSpline(s['t'],s['c'],s['k'],extrapolate=False)(a)[:,:-1]


def predict(coef,intercept,x):
    return x@np.asarray(coef).T+np.asarray(intercept)


def basis(model,a):
    return BSpline.design_matrix(np.asarray(a),model['dose_knots'],model['dose_degree'],extrapolate=False).toarray()


def independent_R_query(model,x,amounts):
    sx=state(x)
    delta=basis(model,amounts)-basis(model,[model['reference']])[0]
    v=(sx[:,None,:,None]*delta[None,:,None,:]).reshape(len(x),len(amounts),80)
    kept=np.asarray(model['q_kept_basis'])
    lost=np.linalg.norm(v-(v@kept)@kept.T,axis=2)/(1+np.linalg.norm(v,axis=2))
    reject=float(lost.max())>model['null_query_tolerance']
    result=(v@np.asarray(model['phi']))*(1+model['rho'])*model['outcome_scale']
    return result,reject,float(lost.max())


def replay_b0(p,facts,mask,grid,ck,tag):
    x,a,y,u=[np.asarray(facts[k]) for k in ('X','dose','outcome','users')]
    idx=np.flatnonzero(mask)
    ck.check(p['event_index']==idx.tolist(),tag+':indices')
    if 'xi' not in p:
        return
    ck.close(p['bandwidth'],1.06*np.std(a[idx])*len(set(u[idx]))**(-.2),tag+':h')
    fold=np.asarray(p['folds'])
    mu=np.zeros(len(idx)); pdf=mu.copy(); mg=mu.copy(); md=mu.copy()
    sx=state(x)[:,1:]
    for z in p['auxiliary_models']:
        k=z['fold']; tr=np.asarray(z['train_event_index']); te=np.asarray(z['test_event_index'])
        ck.check(tr.tolist()==idx[fold!=k].tolist() and te.tolist()==idx[fold==k].tolist(),tag+':scope')
        ck.check(not set(u[tr])&set(u[te]),tag+':user_scope')
        sc=z['scaler'];mean=np.asarray(sc['mean']);sd=np.asarray(sc['scale'])
        ck.close(mean,sx[tr].mean(0),tag+':scaler_mean')
        ck.close(sd,sx[tr].std(0),tag+':scaler_sd')
        xt,xe=(sx[tr]-mean)/sd,(sx[te]-mean)/sd
        om=z['outcome_model'];be=spline(z,a[te]);which=fold==k
        mu[which]=predict(om['coef'],om['intercept'],design(xe,be))
        ck.close(z['mean_state'],xt.mean(0),tag+':mean_state')
        mg[which]=predict(om['coef'],om['intercept'],design(np.broadcast_to(xt.mean(0),xe.shape),be))
        if z['known_uniform']:
            pdf[which]=md[which]=1/2.4
        else:
            inner=np.asarray(z['density_inner_fold'])
            ck.check(len(inner)==len(tr),tag+':inner_scope')
            for user in set(u[tr]):
                ck.check(len(set(inner[u[tr]==user]))==1,tag+':inner_user')
            residual=np.zeros(len(tr))
            for j,reg in enumerate(z['density_inner_models']):
                m=inner==j
                residual[m]=logit(a[tr][m]/2.4)-predict(reg['coef'],reg['intercept'],xt[m])
            sd_gps=float(np.sqrt(np.mean(residual**2)))
            ck.close(z['density_sd'],sd_gps,tag+':gps_sd')
            dm=z['density_final_model']
            means=predict(dm['coef'],dm['intercept'],xt)
            testmean=predict(dm['coef'],dm['intercept'],xe)
            scaled=a[te]/2.4;jac=2.4*scaled*(1-scaled)
            pdf[which]=norm.pdf(logit(scaled),testmean,sd_gps)/jac
            md[which]=norm.pdf(logit(scaled)[:,None],means[None,:],sd_gps).mean(1)/jac
    weights=md/pdf;xi=(y[idx]-mu)*weights+mg
    for key,v in [('mu_observed',mu),('conditional_density',pdf),('marginal_mu',mg),('marginal_density',md),('weights',weights),('xi',xi)]:
        ck.close(p[key],v,tag+':'+key)
    ds,failed=support(x[idx],a[idx],u[idx],grid,p['bandwidth'],weights)
    ck.tree(ds,p['support'],tag+':support')
    ck.tree(failed,p['failed_doses'],tag+':unsupported')
    ck.check((not failed)==(p['status']=='ok'),tag+':support_status')
    if p['status']=='ok':
        ck.close(p['level'],local_line(a[idx],xi,grid,p['bandwidth']),tag+':level_replay')


def replay_R(model,facts,grid,ck,tag):
    x,a,y,u=[np.asarray(facts[k]) for k in ('X','dose','outcome','users')]
    sx=state(x);ba=basis(model,a);psi=(sx[:,:,None]*ba[:,None,:]).reshape(len(a),80)
    folds=np.asarray(model['fold_by_event']);m=np.zeros(len(a));mom=np.zeros((len(a),8))
    for z in model['auxiliary_models']:
        k=z['fold'];tr=np.asarray(z['train_event_index']);te=np.asarray(z['test_event_index'])
        ck.check(tr.tolist()==np.flatnonzero(folds!=k).tolist() and te.tolist()==np.flatnonzero(folds==k).tolist(),tag+':scope')
        ck.check(not set(u[tr])&set(u[te]),tag+':user_scope')
        mean,sd=np.asarray(z['scaler_mean']),np.asarray(z['scaler_scale'])
        ck.close(mean,sx[tr,1:].mean(0),tag+':scaler_mean')
        ck.close(sd,sx[tr,1:].std(0),tag+':scaler_sd')
        xe=(sx[te,1:]-mean)/sd
        m[te]=predict(z['m_coef'],z['m_intercept'],xe)
        if z['gamma_mode']=='known_uniform_integral':
            ck.check(facts['known_density'] is not None,tag+':uniform_declaration')
            mom[te]=BSpline(model['dose_knots'],np.eye(8),3).integrate(0,2.4)/2.4
        else:
            ck.check(facts['known_density'] is None,tag+':observation_declaration')
            mom[te,:7]=predict(z['gamma_coef'],z['gamma_intercept'],xe)
            mom[te,7]=1-mom[te,:7].sum(1)
    gamma=(sx[:,:,None]*mom[:,None,:]).reshape(len(a),80)
    z=psi-gamma;q=psi.T@psi/len(a);r=z.T@z/len(a);rhs=z.T@(y/1800-m)/len(a)
    for key,v in [('m_oof',m),('dose_moments_oof',mom),('Gamma_oof',gamma),('function_Gram',q),('residual_Gram',r),('right_hand_side',rhs)]:
        ck.close(model[key],v,tag+':'+key)
    ck.close(mom.sum(1),np.ones(len(a)),tag+':partition')
    ck.check(model['rho']==.05 and model['reference']==.4 and model['absolute_level_available'] is False,tag+':fixed_contract')
    ck.check(model['negative_moment_entries']==int((mom<0).sum()) and model['moments_clipped'] is False,tag+':moments_not_clipped')
    eig,vec=np.linalg.eigh((q+q.T)/2);keep=eig>eig[-1]*1e-10
    ck.close(model['q_eigenvalues'],eig,tag+':q_eigen')
    ck.check(model['q_rank']==int(keep.sum()) and model['q_dimension']==80,tag+':q_rank')
    kept=np.asarray(model['q_kept_basis'])
    ck.close(kept@kept.T,vec[:,keep]@vec[:,keep].T,tag+':q_subspace')
    ck.close((r+.05*q)@np.asarray(model['phi']),rhs,tag+':normal_equation')
    # Independent algebra vs the loaded query-only implementation; no fits.
    amounts=np.array([.4,.73,.85,1.17,2.0])
    independent,reject,lost=independent_R_query(model,x,amounts)
    try:
        loaded=cr.query_conditional(model,x,amounts)
        ck.check(not reject,tag+':query_acceptance')
        ck.close(loaded,independent,tag+':query_loaded')
    except ValueError:
        ck.check(reject,tag+':query_reject')
    ck.close(independent[:,0],np.zeros(len(x)),tag+':reference_zero',tol=0)
    return dict(rank=model['q_rank'],continuous_query_rejected=reject,max_lost_query_fraction=lost,
                inserted_amounts=amounts.tolist(),inserted_overall_increment=independent.mean(0).tolist())


def score(pops,truths,grid):
    out={}
    for method,rows in pops.items():
        r=dict(full_group_output=all(p['status']=='ok' for p in rows[1:]),group_difference_rmse=None,
               output_points=[len(grid) if p['status']=='ok' else 0 for p in rows])
        true=[t-t[0] for t in truths]
        for j,p in enumerate(rows):
            if p['status']=='ok':
                r[f'increment_rmse_{j}']=rmse(np.asarray(p['contrast'])-true[j])
                if p.get('level') is not None:r[f'level_rmse_{j}']=rmse(np.asarray(p['level'])-truths[j])
        if r['full_group_output']:
            e=np.asarray(rows[2]['contrast'])-rows[1]['contrast']-(true[2]-true[1])
            r['group_difference_rmse']=rmse(e);r['group_difference_nonreference_rmse']=rmse(e[1:])
        out[method]=r
    return out


def decide(rows,plan):
    spec=plan['data']['development'];expected={(s,k) for s in spec['seeds'] for k in spec['mechanisms']};n=len(expected)
    actual=[(r['seed'],r['mechanism']) for r in rows]
    full=lambda r,m:r['scores'][m]['full_group_output']
    gates=dict(exact_cohort_set=set(actual)==expected and len(actual)==n,
        common_output=all(sum(full(r,m) for r in rows)==n for m in ('B0','OR10','R')),
        zero_reference=all(r['reference_exact_zero'] for r in rows),overall_unchanged=all(r['overall_equals_B0'] for r in rows))
    comp={}
    av=lambda rs,m,k:float(np.mean([r['scores'][m][k] for r in rs]))
    for ref in ('B0','OR10'):
        paired=[r for r in rows if full(r,'R') and full(r,ref)]
        a=av(paired,ref,'group_difference_rmse') if paired else None;b=av(paired,'R','group_difference_rmse') if paired else None
        gates['gain_'+ref]=a is not None and a>0 and b<=.95*a
        blocks=[]
        for seed in spec['seeds']:
            sub=[r for r in paired if r['seed']==seed]
            d=av(sub,'R','group_difference_rmse')-av(sub,ref,'group_difference_rmse') if len(sub)==len(spec['mechanisms']) and {r['mechanism'] for r in sub}==set(spec['mechanisms']) else None
            blocks.append(dict(seed=seed,delta=d))
        gates['mechanisms_'+ref]=all(len(sub:=[r for r in paired if r['mechanism']==k])==len(spec['seeds']) and av(sub,'R','group_difference_rmse')<=av(sub,ref,'group_difference_rmse') for k in spec['mechanisms'])
        gates['single_group_noninferior_'+ref]=len(paired)==n and all(av(paired,'R',f'increment_rmse_{g}')<=av(paired,ref,f'increment_rmse_{g}')+2 for g in (1,2))
        comp[ref]=dict(paired=len(paired),baseline=a,candidate=b,blocks=blocks,seed_wins=sum(z['delta'] is not None and z['delta']<0 for z in blocks))
    joint=sum(all(comp[m]['blocks'][i]['delta'] is not None and comp[m]['blocks'][i]['delta']<0 for m in ('B0','OR10')) for i in range(6))
    gates['joint_seed_wins']=joint>=4
    return plain(dict(stage='development',gates=gates,pass_all=all(gates.values()),comparisons=comp,joint_winning_blocks=joint,designed=n,observed=len(rows)))


def main():
    plan=read(DESIGN/'protocol.json');grid=np.asarray(plan['target']['grid']);receipt=read(DESIGN/'development_receipt.json')
    ck=Audit();freeze=read(DESIGN/'development/source_freeze.json');ck.check(freeze==receipt['source_sha256'],'receipt_freeze')
    for path,digest in freeze.items():ck.check(sha(ROOT/path)==digest,'hash:'+path)
    rows=[];failure_ledger=[];queries=[];hashes={}
    expected=[(s,k) for s in plan['data']['development']['seeds'] for k in plan['data']['development']['mechanisms']]
    ck.check([(r['seed'],r['mechanism']) for r in receipt['rows']]==expected,'24_exact_receipt_rows')
    for seed,kind in expected:
        path=DESIGN/'development'/f'{seed}-{kind}.json';obj=read(path);hashes[path.name]=sha(path)
        facts,pops=obj['facts'],obj['populations'];x,a,y,u=[np.asarray(facts[k]) for k in ('X','dose','outcome','users')]
        masks=[np.ones(len(a),bool),x[:,0]<0,x[:,0]>=0];tag=f'{seed}/{kind}'
        ck.check(x.shape==(480,3) and len(a)==len(y)==len(u)==480 and len(set(u))==240,tag+':facts')
        truths=[np.asarray(t) for t in obj['truth_levels']]
        for j,mask in enumerate(masks):
            ck.close(truths[j],truth61(x[mask],kind,grid),tag+f':truth_{j}',tol=1e-6)
            replay_b0(pops['B0'][j],facts,mask,grid,ck,tag+f':B0:{j}')
        om=obj['OR_model'];ck.check(om['alpha']==10,tag+':OR_fixed')
        for j,mask in enumerate(masks):
            xs=(state(x[mask])[:,1:]-np.asarray(om['scaler_mean']))/np.asarray(om['scaler_scale'])
            level=predict(om['coef'],om['intercept'],design(np.broadcast_to(xs.mean(0),(len(grid),9)),spline(om,grid)))
            ck.check((pops['OR10'][j]['status']=='ok')==(pops['B0'][j]['status']=='ok'),tag+f':OR_support_{j}')
            if pops['OR10'][j]['status']=='ok':ck.close(pops['OR10'][j]['level'],level,tag+':OR_level')
        ck.close(om['scaler_mean'],state(x)[:,1:].mean(0),tag+':OR_scale_mean')
        ck.close(om['scaler_scale'],state(x)[:,1:].std(0),tag+':OR_scale_sd')
        model=obj['R_model'];ck.check(model is not None,tag+':R_model_saved')
        if model is not None:
            q=replay_R(model,facts,grid,ck,tag+':R');queries.append(dict(seed=seed,mechanism=kind,**q))
            for j in (1,2):
                independent,reject,lost=independent_R_query(model,x[masks[j]],grid)
                eligible=pops['B0'][j]['status']=='ok'
                ck.check(model['common_group_eligible'][str(j)]==eligible,tag+':eligibility')
                ck.check((pops['R'][j]['status']=='ok')==(eligible and not reject),tag+':R_status')
                if pops['R'][j]['status']=='ok':ck.close(pops['R'][j]['contrast'],independent.mean(0),tag+':R_increment')
                if not eligible:ck.check(pops['R'][j]['reason']=='common B0 support',tag+':R_support_reason')
        for method,zs in pops.items():
            for j,p in enumerate(zs):
                if p['status']!='ok':failure_ledger.append(dict(seed=seed,mechanism=kind,method=method,population=j,
                    reason=p.get('reason'),failed_doses=p.get('failed_doses'),R_q_rank=None if model is None else model['q_rank']))
                elif p.get('level') is not None:ck.close(p['contrast'],np.asarray(p['level'])-p['level'][0],tag+':contrast')
        for field in ('level','contrast'):ck.close(pops['R'][0][field],pops['B0'][0][field],tag+':overall_'+field,tol=0)
        row=dict(seed=seed,mechanism=kind,scores=score(pops,truths,grid),
                 reference_exact_zero=all(p['status']!='ok' or p['contrast'][0]==0 for p in pops['R'][1:]),
                 overall_equals_B0=all(np.array_equal(pops['R'][0][k],pops['B0'][0][k]) for k in ('level','contrast')))
        ck.tree(row,obj['score'],tag+':score');rows.append(row)
    ck.tree(rows,receipt['rows'],'receipt_rows');result=decide(rows,plan);ck.tree(result,receipt['decision'],'decision')
    counts={m:sum(r['scores'][m]['full_group_output'] for r in rows) for m in ('B0','OR10','R','S')}
    report=plain(dict(passed=not ck.failures,checks=ck.checks,failures=ck.failures,all_cohorts_read=len(rows),
        independent_seed_blocks=6,full_group_output=counts,decision=result,max_abs_differences=ck.max_abs,
        failure_ledger=failure_ledger,continuous_queries=queries,recomputed_rows=rows,cohort_sha256=hashes,
        receipt_sha256=sha(DESIGN/'development_receipt.json'),audit_script_sha256=sha(Path(__file__)),
        new_fits=0,new_cohorts=0,confirmation_opened=False,
        console_serialization_note='Receipt and all 24 cohort files exist and recompute. A later console json.dumps NumPy-bool error does not erase those saved results; no cohort rerun required.',
        limitations=['No refit or causal-identification proof; numerical replay verifies saved model computations, not provenance through perturbation experiments.',
                     'S scores/contrasts checked but saved spline fit not independently re-solved; S is not an adoption control.',
                     'All R Grams are full rank in this run; rejected-null queries are implemented and algebraically reviewed, but no empirical rank rejection occurs.',
                     '18 paired score means are conditional on common support; six other designed cohorts remain in the failure ledger and force common-output failure.']))
    out=HERE/'development_audit.json'
    with out.open('x',encoding='utf-8') as f:json.dump(report,f,ensure_ascii=False,indent=2,allow_nan=False)
    print(json.dumps(dict(passed=report['passed'],checks=ck.checks,failures=len(ck.failures),candidate_pass=result['pass_all'],
        designed=24,full_group_output=counts,joint_wins=result['joint_winning_blocks'],output=str(out)),ensure_ascii=False))
    return 0 if report['passed'] else 1


if __name__=='__main__':sys.exit(main())
