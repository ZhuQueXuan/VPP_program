"""Independent read-back verification of B1-SIM-EV-v1 artifacts.

Does not import the implementation, estimators, or simulator. Only the frozen
protocol, persisted factual observations/predictions, and evaluator truth are
read. This is numerical/contract verification, not real-world validation.
"""
from pathlib import Path
import ast
import csv
import hashlib
import json
import math
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
BASE = Path(__file__).resolve().parent
RAW = ROOT / 'data' / '驱动因素解耦模拟数据集_B1_v1_20261021'
CHECKS = []


def require(name, condition, detail=None):
    CHECKS.append({'name': name, 'ok': bool(condition), 'detail': detail})


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_npz(path):
    with np.load(path, allow_pickle=False) as data:
        return {key: data[key] for key in data.files}


def maxerr(a, b):
    return float(np.max(np.abs(np.asarray(a) - np.asarray(b))))


def conditional_effect(xw, beta, nodes):
    """Integrate the declared acceptance SCM, averaging hidden U and V.

    GL weights sum to 2 on [-1,1], hence multiply by 1/2 for Uniform U.
    Mean delay 30 s follows directly from discrete {0,10,...,60}.
    """
    u, weight = np.polynomial.legendre.leggauss(nodes)
    x = xw[..., 0]
    w = xw[..., 1]
    logits = (-0.5 + 0.7*x - 0.6*w)[..., None] + 0.8*u
    p0 = 1/(1 + np.exp(-logits))
    p1 = 1/(1 + np.exp(-(logits + beta)))
    opening = (0.4 + 0.2*(x + 1))*(0.8 + 0.2*w*w)
    return opening * (1 - 30/1200) * ((p1-p0) @ weight / 2)


def main():
    protocol = json.loads((BASE/'protocol.json').read_text(encoding='utf-8-sig'))
    observations = load_npz(RAW/'main_observations.npz')
    predictions = load_npz(BASE/'predictions.npz')
    truth = load_npz(BASE/'truth.npz')
    required = {'X', 'D', 'Y', 'user', 'split'}
    require('factual artifact required fields', required <= observations.keys(), list(observations))
    if not required <= observations.keys():
        raise ValueError('Factual artifact schema differs from agreed interface')
    require('factual artifact excludes hidden and potential values',
            not any(k.lower() in {'u','v','tau','truth','y0','y1','accept','delay','y_star'} for k in observations),
            list(observations))
    X,D,Y,user,split = (observations[k] for k in ('X','D','Y','user','split'))
    R,S,N = D.shape
    require('frozen experiment array shapes',
            R == 20 and S == 4 and N == 1920 and X.shape == (R,S,N,2)
            and Y.shape == D.shape and user.shape == D.shape and split.shape == D.shape)
    require('finite factual measurements and legal domains',
            np.isfinite(X).all() and np.isfinite(Y).all() and np.isin(D,[0,1]).all()
            and (np.abs(X)<=1).all() and np.isin(split,[0,1,2]).all())
    # Check the declared feasible region for every factual covariate, including
    # the worst allowed acceptance and zero-delay realization. This does not
    # pretend that unsaved high-frequency trajectories were read back.
    horizon=3600+1800*(X[...,0]+1)
    pmax=3.5+.75*(X[...,0]+1)
    opening=(.4+.2*(X[...,0]+1))*(.8+.2*X[...,1]**2)
    worst_debt=1.5*opening*1200
    recovery_room=(pmax-3)*(horizon-1800)
    require('all factual conditions have nonnegative request power and sufficient recovery room',
            (3-1.5*opening>=0).all() and (recovery_room>=worst_debt).all(),
            {'minimum_recovery_margin_kws':float((recovery_room-worst_debt).min())})
    beta = [1.2,0.,-1.2,1.2]
    recomputed_truth = []
    factual_test = []
    features_test = []
    treatment_test = []
    per_cell = []
    for r in range(R):
        truth_r, y_r, x_r, d_r = [], [], [], []
        for s in range(S):
            uu, counts = np.unique(user[r,s],return_counts=True)
            require(f'{r}/{s}: user identities and event counts',
                    np.array_equal(uu,np.arange(240)) and (counts==8).all())
            sets = [set(user[r,s][split[r,s]==part].tolist()) for part in range(3)]
            require(f'{r}/{s}: user partition sizes and no leakage',
                    [len(z) for z in sets] == [144,48,48]
                    and not (sets[0]&sets[1] or sets[0]&sets[2] or sets[1]&sets[2]))
            mask = split[r,s] == 2
            xx,dd,yy = X[r,s,mask], D[r,s,mask], Y[r,s,mask]
            t80 = conditional_effect(xx,beta[s],80)
            t160 = conditional_effect(xx,beta[s],160)
            require(f'{r}/{s}: 80 versus 160 node CATE stability',
                    maxerr(t80,t160) < 1e-12, maxerr(t80,t160))
            truth_r.append(t160); y_r.append(yy); x_r.append(xx); d_r.append(dd)
            for g, gm in [('all',np.ones(len(xx),dtype=bool)),('x_negative',xx[:,0]<0),('x_nonnegative',xx[:,0]>=0)]:
                n0 = int(np.sum((dd==0)&gm)); n1 = int(np.sum((dd==1)&gm))
                per_cell.append({'replicate':r,'scenario':s,'group':g,'n0':n0,'n1':n1,
                                 'support_ok':min(n0,n1)>=10})
        recomputed_truth.append(truth_r); factual_test.append(y_r)
        features_test.append(x_r); treatment_test.append(d_r)
    tau = np.asarray(recomputed_truth)
    yy, xx, dd = map(np.asarray,(factual_test,features_test,treatment_test))
    require('persisted truth shape',truth['tau'].shape == tau.shape,list(truth['tau'].shape))
    require('persisted truth independent recalculation',maxerr(truth['tau'],tau)<1e-12,maxerr(truth['tau'],tau))
    require('declared zero mechanism is exactly zero',np.max(np.abs(tau[:,1]))==0.)
    for key in ('mu0','mu1','e','ridge_effect'):
        require(f'prediction shape and finiteness: {key}',
                predictions[key].shape == tau.shape and np.isfinite(predictions[key]).all())
    e = predictions['e']
    require('RCT prediction propensity equals known 0.5',maxerr(e[:,:3],.5)==0.)
    require('propensity support without hidden clipping',((e>=.05)&(e<=.95)).all(),[float(e.min()),float(e.max())])
    require('frozen true observed propensity stays supported',
            ((1/(1+np.exp(-(1.2*xx[:,3,:,0]+.8*xx[:,3,:,1])))>.05)
             & (1/(1+np.exp(-(1.2*xx[:,3,:,0]+.8*xx[:,3,:,1])))<.95)).all())
    mu0,mu1 = predictions['mu0'],predictions['mu1']
    # Reconstruct score using factual holdout observations only.
    aipw = mu1-mu0 + dd*(yy-mu1)/e - (1-dd)*(yy-mu0)/(1-e)
    estimates=[]
    for r in range(R):
        for s in range(S):
            for g,gm in [('all',np.ones(xx.shape[2],bool)),('x_negative',xx[r,s,:,0]<0),('x_nonnegative',xx[r,s,:,0]>=0)]:
                values={
                    'G0':float(yy[r,s,gm & (dd[r,s]==1)].mean()-yy[r,s,gm & (dd[r,s]==0)].mean()),
                    'G1':float(predictions['ridge_effect'][r,s,gm].mean()),
                    'G1ML':float((mu1[r,s,gm]-mu0[r,s,gm]).mean()),
                    'G2':float(aipw[r,s,gm].mean()),
                }
                for method, value in values.items():
                    target=float(tau[r,s,gm].mean())
                    estimates.append({'replicate':r,'scenario':s,'group':g,'method':method,
                                      'estimate':value,'truth':target,'error':value-target})
    with (BASE/'verification_recomputed_metrics.csv').open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(estimates[0]))
        writer.writeheader();writer.writerows(estimates)
    # Detailed persisted metric schema is adapted below after implementation
    # artifacts exist, preserving all outcomes rather than changing thresholds.
    verify_persisted_metrics(estimates, protocol)
    verify_curves(observations)
    verify_folds(observations, protocol)
    verify_source()
    report={'identity':'independent_numerical_and_contract_verification_only',
            'checked_artifacts':{str(path.relative_to(ROOT)):sha(path) for path in [
                RAW/'main_observations.npz',BASE/'predictions.npz',BASE/'truth.npz',BASE/'protocol.json',
                BASE/'run_research.py',BASE/'simulation.py',BASE/'estimators.py',
                Path(__file__).resolve()] if path.exists()},
            'checks':CHECKS,'checks_passed':sum(z['ok'] for z in CHECKS),
            'checks_failed':sum(not z['ok'] for z in CHECKS),
            'holdout_cell_support':per_cell,
            'status':'passed' if all(z['ok'] for z in CHECKS) else 'failed'}
    (BASE/'independent_verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('status','checks_passed','checks_failed')},ensure_ascii=False))
    return 0 if report['status']=='passed' else 1


def verify_persisted_metrics(estimates, protocol):
    with (BASE/'metrics.csv').open(encoding='utf-8-sig',newline='') as stream:
        persisted=list(csv.DictReader(stream))
    lookup={(z['replicate'],z['scenario'],z['group'],z['method']):z for z in estimates}
    seeds=list(protocol['replicate_seeds']); scenarios=list(protocol['scenarios'])
    groups={'all':'all','x_low':'x_negative','x_high':'x_nonnegative'}
    require('all 960 expected persisted metric rows',len(persisted)==len(lookup)==960)
    differences=[]; seen=set()
    for row in persisted:
        key=(seeds.index(int(row['seed'])),scenarios.index(row['scenario']),groups[row['group']],row['method'])
        require('metric row unique: '+str(key),key not in seen)
        seen.add(key)
        for col in ('estimate','truth','error'):
            differences.append(abs(float(row[col])-lookup[key][col]))
        eligible=not (row['method']=='G0' and row['scenario'].startswith('observed'))
        require('G0 observational association labelled: '+str(key),
                row['causal_eligible'].lower()==str(eligible).lower())
    require('all persisted estimates/truth/errors independently reproduced',max(differences)<1e-12,max(differences))
    evaluation=json.loads((BASE/'evaluation.json').read_text(encoding='utf-8'))
    for row in evaluation['summary']:
        relevant=[z for z in estimates if z['scenario']==scenarios.index(row['scenario'])
                  and z['method']==row['method'] and z['group']==groups[row['group']]]
        errors=[z['error'] for z in relevant]; values=[z['estimate'] for z in relevant]
        mean=math.fsum(errors)/len(errors)
        rmse=math.sqrt(math.fsum(z*z for z in errors)/len(errors))
        mcse=math.sqrt(math.fsum((z-mean)**2 for z in errors)/(len(errors)-1)/len(errors))
        expected={'bias':mean,'rmse':rmse,'error_mcse':mcse,
                  'mean_estimate':math.fsum(values)/len(values),
                  'mean_truth':math.fsum(z['truth'] for z in relevant)/len(relevant),
                  'abs_estimate_gt_005':sum(abs(z)>.05 for z in values)/len(values)}
        err=max(abs(row[k]-v) for k,v in expected.items())
        require('summary independent scalar sums: '+str((row['scenario'],row['method'],row['group'])),err<1e-12,err)
    for row in evaluation['paired']:
        selected={method:[z for z in estimates if z['scenario']==scenarios.index(row['scenario'])
                  and z['method']==method and z['group']==groups[row['group']]] for method in ('G2',row['baseline'])}
        pairs=list(zip(selected['G2'],selected[row['baseline']]))
        delta=[a['error']**2-b['error']**2 for a,b in pairs]
        mean=math.fsum(delta)/len(delta)
        se=math.sqrt(math.fsum((z-mean)**2 for z in delta)/(len(delta)-1)/len(delta))
        wins=sum(abs(a['error'])<abs(b['error']) for a,b in pairs)
        require('paired comparison independently reproduced: '+str((row['scenario'],row['baseline'],row['group'])),
                abs(row['mse_delta']-mean)<1e-12 and abs(row['delta_mcse']-se)<1e-12
                and row['absolute_error_wins']==wins)
    receipt=json.loads((BASE/'run_receipt.json').read_text(encoding='utf-8'))
    fit_receipt=json.loads((BASE/'fit_receipt.json').read_text(encoding='utf-8'))
    require('prediction hash fixed before truth evaluation',
            receipt['predictions_sha256']==fit_receipt['predictions_sha256']==sha(BASE/'predictions.npz')
            and not fit_receipt['truth_existed_at_fit_start'] and receipt['truth_after_predictions'])
    require('protocol hash unchanged across generation fit evaluation',
            fit_receipt['protocol_sha256']==receipt['protocol_sha256']==sha(BASE/'protocol.json'))
    frozen=json.loads((BASE/'source_freeze_before_evaluation.json').read_text(encoding='utf-8'))
    for name,digest in frozen.items():
        require('pre-evaluation scientific source identity: '+name,sha(BASE/name)==digest)


def verify_curves(observations):
    panel=load_npz(BASE/'evaluator_curves.npz')
    public=load_npz(RAW/'observed_curve_panel.npz')
    require('public panel excludes hidden physical/action labels',
            set(public)=={'time_edges_s','reference_kw','power_obs_kw','indices'})
    require('48 declared representative curves persisted',len(panel['meta'])==48)
    worst_energy=worst_bound=worst_y=worst_power=0.
    for i,meta in enumerate(panel['meta']):
        scenario,event,x,w,accepted,delay,horizon,pmax,demand,y=meta
        scenario,event=int(scenario),int(event)
        edges=panel['time_edges_s'][i]; edges=edges[np.isfinite(edges)]
        n=len(edges)-1
        reference=panel['reference_kw'][i,:n]
        actual=panel['power_star_kw'][i,:n]
        measured=panel['power_obs_kw'][i,:n]
        duration=[float(edges[j+1]-edges[j]) for j in range(n)]
        require(f'curve {i}: legal clock and declared scalar parameters',
                (np.diff(edges)>0).all() and edges[0]==0 and edges[-1]==horizon
                and abs(horizon-(3600+1800*(x+1)))<1e-10
                and abs(pmax-(3.5+.75*(x+1)))<1e-12
                and abs(demand-3*horizon/3600)<1e-12)
        request_sum=math.fsum((float(reference[j])-float(measured[j]))
                    *max(0.,min(float(edges[j+1]),1800)-max(float(edges[j]),600)) for j in range(n))
        independent_y=request_sum/1800
        worst_y=max(worst_y,abs(independent_y-y),abs(independent_y-observations['Y'][0,scenario,event]))
        energy=math.fsum(float(actual[j])*duration[j] for j in range(n))/3600
        worst_energy=max(worst_energy,abs(energy-demand))
        worst_bound=max(worst_bound,max(0.,-float(actual.min()),float(actual.max())-pmax))
        opening=(.4+.2*(x+1))*(.8+.2*w*w)
        debt=1.5*opening*accepted*(1200-delay)
        expected=[]
        for j in range(n):
            left=float(edges[j]); power=3.
            if 600+delay<=left<1800:
                power-=1.5*opening*accepted
            elif left>=1800:
                cap=pmax-3
                power+=min(cap,max(0.,debt-cap*(left-1800))/duration[j])
            expected.append(power)
        worst_power=max(worst_power,maxerr(actual,expected))
        require(f'curve {i}: public observed panel identity',
                np.array_equal(public['time_edges_s'][i],panel['time_edges_s'][i],equal_nan=True)
                and np.array_equal(public['reference_kw'][i],panel['reference_kw'][i],equal_nan=True)
                and np.array_equal(public['power_obs_kw'][i],panel['power_obs_kw'][i],equal_nan=True)
                and np.array_equal(public['indices'][i],[scenario,event]))
    require('curve signed integral reproduces factual Y',worst_y<1e-12,worst_y)
    require('curve energy requirement independently balanced',worst_energy<1e-10,worst_energy)
    require('curve noiseless physical power respects bounds',worst_bound<1e-10,worst_bound)
    require('curve trajectory matches independent closed form',worst_power<1e-10,worst_power)


def verify_folds(observations,protocol):
    diagnostics=json.loads((BASE/'fit_diagnostics.json').read_text(encoding='utf-8'))
    require('80 fitted scenario diagnostics persisted',len(diagnostics)==80)
    for row in diagnostics:
        r=protocol['replicate_seeds'].index(row['seed'])
        s=list(protocol['scenarios']).index(row['scenario'])
        users=observations['user'][r,s]
        d=observations['D'][r,s]
        split=observations['split'][r,s]
        training=set(users[split==0]); seen={u:0 for u in training}
        for f,fold in enumerate(row['folds']):
            tr=set(fold['train_users']); va=set(fold['heldout_users'])
            counts=[int(np.sum(np.isin(users,list(tr))&(d==arm))) for arm in (0,1)]
            require(f'{r}/{s}/{f}: crossfit user isolation and factual arm support',
                    not tr&va and tr|va==training and min(counts)>=20 and counts==fold['arm_counts'])
            for u in va:
                seen[u]+=1
        require(f'{r}/{s}: each training user held out exactly once',all(v==1 for v in seen.values()))
        require(f'{r}/{s}: saved reload and factual OOF diagnostic',
                row['reload_exact'] and row['oof_rows']==1152 and row['oof_finite'])
    for key in ('X','user','split'):
        require('base scenario variants retain same '+key,
                all(np.array_equal(observations[key][:,0],observations[key][:,s]) for s in range(1,4)))


def verify_source():
    source=(BASE/'run_research.py').read_text(encoding='utf-8-sig')
    ast.parse(source)
    require('main implementation parses for read-only audit',True)
    tree=ast.parse(source)
    fit=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='fit')
    fit_text=ast.unparse(fit)
    require('fitting function reads factual artifact and no evaluator or latent labels',
            'main_observations.npz' in fit_text and 'observed[k]' in fit_text
            and 'u' not in {n.id for n in ast.walk(fit) if isinstance(n,ast.Name)}
            and 'conditional_truth' not in fit_text and 'curve(' not in fit_text
            and 'generate(' not in fit_text)
    estimator_source=(BASE/'estimators.py').read_text(encoding='utf-8-sig')
    et=ast.parse(estimator_source)
    imported=[ast.unparse(n) for n in ast.walk(et) if isinstance(n,(ast.Import,ast.ImportFrom))]
    require('estimator module imports no simulator/evaluator and opens no artifacts',
            not any('simulation' in z or 'evaluate' in z for z in imported)
            and not any(isinstance(n,ast.Call) and isinstance(n.func,ast.Name)
                        and n.func.id in {'open','load_npz'} for n in ast.walk(et)))
    fn=next(n for n in et.body if isinstance(n,ast.FunctionDef) and n.name=='fit_aux')
    require('auxiliary fit explicit observed-only argument contract',
            [a.arg for a in fn.args.args]==['x','d','y','randomized'])
    require('propensity no silent clipping in implementation','clip' not in estimator_source.replace('no clipping',''))


if __name__ == '__main__':
    raise SystemExit(main())
