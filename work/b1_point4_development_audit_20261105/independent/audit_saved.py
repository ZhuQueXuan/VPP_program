"""Read-only independent audit of the executed development; no fit or generation."""
import csv
import hashlib
import json
from pathlib import Path
import math
from statistics import mean
import numpy as np
from scipy.interpolate import BSpline

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
STUDY=ROOT/'work/b1_point4_stability_design_20261105'


def load(path):
    return json.loads(path.read_text(encoding='utf8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def folds(users,n,seed):
    unique=sorted(set(users))
    perm=np.random.default_rng(seed).permutation(len(unique))
    assigned=np.empty(len(unique),int)
    assigned[perm]=np.arange(len(unique))%n
    lookup={u:int(f) for u,f in zip(unique,assigned)}
    return np.array([lookup[u] for u in users])


def level_at(a,xi,q,h):
    z=(a[None,:]-q[:,None])/h
    kernel=np.exp(-z*z/2)
    s0=kernel.sum(1);s1=(kernel*z).sum(1);s2=(kernel*z*z).sum(1)
    weights=kernel*(s2[:,None]-s1[:,None]*z)/(s0*s2-s1*s1)[:,None]
    return weights@xi


def expected(x,kind,q):
    nodes,w=np.polynomial.legendre.leggauss(61)
    slack=x[:,0,None];demand=x[:,1,None];h=.6*nodes[None,:]
    out=[]
    logistic=lambda z:1/(1+np.exp(-z))
    for a in q:
        signal=0 if kind=='zero_effect' else np.sin(np.pi*a/2.4) if kind=='nonmonotone' else a
        p=logistic(-1.5+1.25*signal*(1+.35*slack)+.5*slack-.45*demand+.35*h)
        mu=logistic(-.6+.8*signal+.3*slack-.2*demand+.15*h)
        full=logistic(-3+.7*signal)
        out.append(float(1800*np.mean((p*(full+(1-full)*mu))@(w/2))))
    return np.array(out)


def main():
    checks=0
    maxdiff={k:0. for k in ['truth','pseudo','local_linear','spline','score','support','overall']}
    def ck(ok,label):
        nonlocal checks
        if not ok:
            raise AssertionError(label)
        checks+=1
    def close(a,b,label,key,tol=1e-8):
        a,b=np.asarray(a,float),np.asarray(b,float)
        ck(a.shape==b.shape,label+' shape')
        error=float(np.max(abs(a-b))) if a.size else 0.
        maxdiff[key]=max(maxdiff[key],error)
        ck(np.isfinite(a).all() and np.isfinite(b).all() and error<=tol,label)
    plan=load(STUDY/'experiment_plan.json')
    receipt=load(STUDY/'development_receipt.json')
    freeze=load(STUDY/'development/source_freeze.json')
    amended=load(STUDY/'ROOT_PREFLIGHT.json')
    for path,h in freeze.items():
        ck(sha(ROOT/path)==h,'frozen source '+path)
    ck(freeze==receipt['source_sha256']==amended['all_training_sources'],'same reviewed freeze')
    ck(sha(STUDY/'run_experiment.py')==amended['amended_runner_sha256'],'amended gate runner')
    ck(not (STUDY/'confirmation').exists(),'confirmation not opened')
    ck(not (STUDY/'confirmation_receipt.json').exists(),'confirmation receipt absent')
    q=np.array(plan['estimands']['grid'])
    files=sorted((STUDY/'development').glob('[0-9]*.json'))
    expected_keys={(s,k) for s in plan['development']['seeds'] for k in plan['development']['mechanisms']}
    ck(len(files)==24,'24 files')
    rows=[];scopes_seen=0;cross_users=0;replay=[]
    artifact_hashes={}
    for file in files:
        artifact_hashes[file.name]=sha(file)
        j=load(file)
        savedscore=j['score'];seed=savedscore['seed'];kind=savedscore['mechanism']
        ck((seed,kind) in expected_keys,'expected key')
        expected_keys.remove((seed,kind))
        d=j['facts'];x=np.array(d['X']);a=np.array(d['dose']);y=np.array(d['outcome']);users=np.array(d['users'])
        ck(len(x)==len(a)==len(y)==len(users)==480,'480 facts')
        ck(len(set(users))==240 and all(sum(users==u)==2 for u in set(users)),'240 two-event users')
        ck(x.shape==(480,3) and np.isfinite(x).all(),'X shape')
        ck(np.isfinite(a).all() and min(a)>0 and max(a)<2.4,'continuous dose domain')
        ck(np.isfinite(y).all() and min(y)>=0 and max(y)<=1800,'Y domain')
        high=x[:,0]>=0;g=high.astype(int)
        masks=[np.ones(480,bool),~high,high]
        global_folds=folds(users,3,seed)
        cross_users+=sum(set(g[users==u])=={0,1} for u in set(users))
        truths=[np.array(t) for t in j['truth_levels']]
        for mask,t in zip(masks,truths):
            close(expected(x[mask],kind,q),t,'truth61', 'truth',1e-6)
        methods=j['models'];own={}
        for method,pops in methods.items():
            ck(len(pops)==3,'3 populations')
            score=dict(full_group_output=all(r['status']=='ok' for r in pops[1:]),group_difference_rmse=None)
            ck(savedscore['scores'][method]['full_group_output']==score['full_group_output'],'output count')
            for pop,(mask,r,t) in enumerate(zip(masks,pops,truths)):
                ck(savedscore['scores'][method]['output_points'][pop]==(17 if r['status']=='ok' else 0),'point output')
                if r['status']!='ok':
                    continue
                lev=np.array(r['level']);cont=np.array(r['contrast'])
                close(cont,lev-lev[0],'contrast from level','score')
                for metric,error in [('level_rmse',lev-t),('contrast_rmse',cont-(t-t[0])),
                                     ('contrast_nonreference_rmse',cont[1:]-(t[1:]-t[0]))]:
                    value=float(np.sqrt(np.mean(error**2)))
                    score[f'{metric}_{pop}']=value
                    close(value,savedscore['scores'][method][f'{metric}_{pop}'],'score '+metric,'score')
                if method in ('B0','C0','C'):
                    idx=np.array(r['event_index']);u=users[idx];aa=a[idx]
                    ck(np.array_equal(idx,np.flatnonzero(mask)),'group event index')
                    f=np.array(r['folds'])
                    expected_f=folds(u,3,seed) if method=='B0' or pop==0 else global_folds[mask]
                    ck(np.array_equal(f,expected_f),'fold labels')
                    for fold in set(f):
                        ck(not set(u[f==fold]).intersection(u[f!=fold]),'user fold isolation')
                    xi,w,mu,pi,mg,vg=(np.array(r[k]) for k in ('xi','weights','mu_observed','conditional_density','marginal_mu','marginal_density'))
                    ck(np.isfinite(xi).all() and np.isfinite(w).all() and max(w)<=30 and min(pi)>0,'finite pseudo/density weights')
                    close(w,vg/pi,'marginal over conditional density','pseudo')
                    close(xi,(y[idx]-mu)*w+mg,'pseudo arithmetic','pseudo')
                    h=1.06*float(np.std(aa))*len(set(u))**(-.2)
                    close(h,r['bandwidth'],'bandwidth','support')
                    close(level_at(aa,xi,q,h),lev,'saved xi level replay','local_linear')
                    for info,amount in zip(r['support'],q):
                        local=abs(aa-amount)<=h
                        kernel=np.exp(-.5*((aa-amount)/h)**2)*w
                        ess=float(kernel.sum()**2/(kernel@kernel))
                        sd=np.maximum(x[idx].std(0),1e-8)
                        smd=float(np.max(abs(np.average(x[idx],axis=0,weights=kernel)-x[idx].mean(0))/sd))
                        ck(info['local_events']==int(local.sum()),'local events')
                        ck(info['local_users']==len(set(u[local])),'local users')
                        close(ess,info['effective_events'],'ESS','support')
                        close(smd,info['max_weighted_smd'],'SMD','support')
                        ck(info['local_events']>=25 and info['local_users']>=15 and ess>=20 and smd<=.5,'support gates')
                    if file.name=='915051101-randomized.json':
                        queries=np.array([.73,1.17])
                        direct=level_at(aa,xi,queries,h)
                        reference=level_at(aa,xi,np.array([.4]),h)[0]
                        replay.append(dict(method=method,population=pop,amounts=queries.tolist(),levels=direct.tolist(),
                                           contrasts=(direct-reference).tolist(),new_fits=0))
                elif method=='S':
                    state=r['spline_state']
                    spline=BSpline(state['knots'],state['coefficients'],state['degree'],extrapolate=False)
                    close(spline(q/state['x_scale'])*state['y_scale'],lev,'saved spline replay','spline')
            if score['full_group_output']:
                predicted=np.array(pops[2]['contrast'])-np.array(pops[1]['contrast'])
                target=(truths[2]-truths[2][0])-(truths[1]-truths[1][0])
                value=float(np.sqrt(np.mean((predicted-target)**2)))
                score['group_difference_rmse']=value
                close(value,savedscore['scores'][method]['group_difference_rmse'],'group score','score')
                close(float(np.sqrt(np.mean((predicted[1:]-target[1:])**2))),
                      savedscore['scores'][method]['group_difference_nonreference_rmse'],'16-point group score','score')
            own[method]=score
        for method in ('C0','C'):
            for key in ('level','contrast'):
                close(methods[method][0][key],methods['B0'][0][key],'overall invariant','overall',1e-9)
            scopes=j['scopes'][method]
            ck(len(scopes)==6,'6 fold/group scopes')
            for scope in scopes:
                scopes_seen+=1
                fold,group=scope['fold'],scope['group']
                ti=np.flatnonzero(global_folds!=fold)
                train=np.array(scope['train_event_index']);test=np.array(scope['test_event_index']);marg=np.array(scope['marginal_event_index'])
                expected_train=ti if method=='C' else ti[g[ti]==group]
                expected_test=np.flatnonzero((global_folds==fold)&(g==group))
                expected_marg=ti[g[ti]==group]
                ck(np.array_equal(train,expected_train),'exact conditional train population')
                ck(np.array_equal(test,expected_test),'exact heldout group population')
                ck(np.array_equal(marg,expected_marg),'exact marginal target population')
                ck(not set(users[train]).intersection(users[test]),'cross-group heldout users excluded')
                ck(scope['pooled']==(method=='C'),'scope pooled flag')
                close(scope['ridge_alpha'],(.1/320)*len(train),'mean-loss alpha','support')
                inner=np.array(scope['inner_fold_by_train_event'])
                ck(np.array_equal(inner,folds(users[ti],2,seed+fold+130)),'expected inner folds')
                for innerfold in (0,1):
                    ck(not set(users[ti][inner==innerfold]).intersection(users[ti][inner!=innerfold]),'inner user isolation')
                other=next(v for v in j['scopes']['C' if method=='C0' else 'C0'] if v['fold']==fold and v['group']==group)
                ck(scope['inner_fold_by_train_event']==other['inner_fold_by_train_event'],'C/C0 shared inner folds')
                ck(scope['marginal_event_index']==other['marginal_event_index'],'C/C0 same target marginal population')
        rows.append(dict(seed=seed,mechanism=kind,scores=own))
    ck(not expected_keys,'all expected cohorts present')
    gates=dict(overall_identical=True,coverage=all(r['scores'][m]['full_group_output'] for r in rows for m in ('B0','C0','C')))
    comparisons={}
    blocks=[]
    for seed in plan['development']['seeds']:
        block=[r for r in rows if r['seed']==seed]
        b=dict(seed=seed)
        for m in ('B0','C0','C'):
            b[m]=mean(r['scores'][m]['group_difference_rmse'] for r in block)
        b['win_B0']=b['C']<b['B0'];b['win_C0']=b['C']<b['C0'];b['joint_win']=b['win_B0'] and b['win_C0']
        blocks.append(b)
    for m in ('B0','C0'):
        a=mean(r['scores'][m]['group_difference_rmse'] for r in rows)
        b=mean(r['scores']['C']['group_difference_rmse'] for r in rows)
        wins=sum(v['win_'+m] for v in blocks)
        gates['gain_'+m]=b<=.95*a;gates['wins_'+m]=wins>=4
        comparisons[m]=dict(baseline=a,candidate=b,gain_pct=100*(1-b/a),wins=wins)
        close(a,receipt['decision']['comparisons'][m]['baseline'],'receipt baseline','score')
        close(b,receipt['decision']['comparisons'][m]['candidate'],'receipt candidate','score')
    joint=sum(b['joint_win'] for b in blocks)
    gates['joint_block_wins']=joint>=4
    ck(gates==receipt['decision']['gates'],'all gate booleans')
    ck(joint==receipt['decision']['joint_block_wins']==3,'joint wins')
    ck(all(gates.values())==receipt['decision']['pass_all']==False,'failure decision')
    ck(not (STUDY/'confirmation').exists(),'confirmation still unopened')
    with (HERE/'independent_blocks.csv').open('w',encoding='utf-8-sig',newline='') as fp:
        w=csv.DictWriter(fp,fieldnames=list(blocks[0]));w.writeheader();w.writerows(blocks)
    output=dict(date='2026-11-05',passed=True,checks=checks,new_fits=0,new_research_data_generated=0,
        cohorts=24,independent_blocks=6,scopes_checked=scopes_seen,
        cross_group_user_occurrences_across_cohorts=cross_users,
        pairing='Same-seed mechanisms repeat users and exogenous states; cross-group user occurrences are audit row occurrences, not independent subjects.',
        comparisons=comparisons,blocks=blocks,gates=gates,joint_block_wins=joint,
        candidate_passes=False,maximum_numeric_differences=maxdiff,
        loaded_xi_offgrid_replay=replay,
        replay_scope='Stored xi and bandwidth support direct final-stage local-linear querying without nuisance refits; no saved Ridge/scaler parameters to replay arbitrary conditional auxiliary predictions. OR retains grid predictions only; S retains spline state.',
        preprocessing_evidence='Frozen code creates poly/scaler on identical global training X for C/C0; stored scopes and alpha confirm training/marginal partitions. Scaler coefficients are not saved, so no independent empirical perturbation/refit proof is claimed.',
        source_freeze_sha256=sha(STUDY/'development/source_freeze.json'),
        artifact_sha256=artifact_hashes)
    (HERE/'independent_audit.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({k:output[k] for k in ('checks','comparisons','joint_block_wins','candidate_passes','maximum_numeric_differences')},ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
