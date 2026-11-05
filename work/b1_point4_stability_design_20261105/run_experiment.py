"""Staged proposed comparison. Default preflight performs ZERO model fits.

Development/confirmation are intentionally not run in the design round.
"""
import argparse
from dataclasses import asdict
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys

for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[key] = "1"
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT/"B1算法"))

import numpy as np
from scipy.special import logit
from scipy.stats import norm
from sklearn.linear_model import Ridge
from sklearn.preprocessing import PolynomialFeatures, StandardScaler, SplineTransformer
from b1_algorithm.effects.continuous import (
    ContinuousEffectConfig, _crossfit, _design, _local_support,
    _marginal_logit_density, _marginal_prediction, local_linear_weights)
from b1_algorithm.effects.core import group_folds
import new_data

PLAN = json.loads((HERE/"experiment_plan.json").read_text(encoding="utf-8"))
GRID = np.array(PLAN["estimands"]["grid"])
LAMBDA = .1/320


def plain(x):
    if isinstance(x, np.ndarray):
        return x.tolist()
    if isinstance(x, np.generic):
        return x.item()
    if isinstance(x, dict):
        return {k:plain(v) for k,v in x.items()}
    if isinstance(x, (list,tuple)):
        return [plain(v) for v in x]
    return x


def save(p, obj):
    with p.open("x", encoding="utf-8") as fp:
        json.dump(plain(obj), fp, ensure_ascii=False, indent=2, allow_nan=False)
        fp.write("\n")


def sources():
    paths = sorted(HERE.glob("*.py"))+[HERE/"experiment_plan.json"]
    paths += sorted((ROOT/"B1算法"/"b1_algorithm").rglob("*.py"))
    paths += [ROOT/"work"/"b1_curve_spline_pilot_20261103"/"smoothers.py"]
    return {p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def load_smoothers():
    path = ROOT/"work"/"b1_curve_spline_pilot_20261103"/"smoothers.py"
    spec = importlib.util.spec_from_file_location("p4_retained_smoother", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def summary_output(x, a, users, xi, weight, cfg):
    h = 1.06*float(np.std(a))*len(set(users))**(-.2)
    diagnostics, failed = _local_support(x, a, users, GRID, h, weight, cfg)
    out = dict(status="unsupported" if failed else "ok", bandwidth=h,
               failed_doses=failed, support=diagnostics, xi=xi, weights=weight)
    if not failed:
        level = local_linear_weights(a, GRID, h) @ xi
        out.update(level=level, contrast=level-level[0])
    return out


def incumbent(d, seed):
    cfg = ContinuousEffectConfig(seed=seed, n_boot=99)
    x,a,y,u = [d[k] for k in ("X","dose","outcome","users")]
    masks = [np.ones(len(y),bool), x[:,0]<0, x[:,0]>=0]
    out = []
    for mask in masks:
        try:
            known = None if d["known_density"] is None else d["known_density"][mask]
            xi,w,folds,_,mu,pdf = _crossfit(x[mask],a[mask],y[mask],u[mask],cfg,[0.,2.4],known)
            row = summary_output(x[mask],a[mask],u[mask],xi,w,cfg)
            row.update(folds=folds, mu_observed=mu, conditional_density=pdf,
                       marginal_mu=xi-(y[mask]-mu)*w, marginal_density=w*pdf,
                       event_index=np.flatnonzero(mask))
        except (ValueError, np.linalg.LinAlgError) as exc:
            row = dict(status="unsupported",reason=str(exc),event_index=np.flatnonzero(mask))
        out.append(row)
    return out


def shared_auxiliary(d, seed, pooled):
    """C0 and C differ only in conditional model training population."""
    x,a,y,u = [d[k] for k in ("X","dose","outcome","users")]
    n = len(y)
    group = (x[:,0]>=0).astype(int)
    folds = group_folds(u,3,seed)
    xi,weights,mu_all,pdf_all,mm_all,md_all = [np.full(n,np.nan) for _ in range(6)]
    scopes = []
    for fold in np.unique(folds):
        train, test = folds!=fold, folds==fold
        ti = np.flatnonzero(train)
        assert not set(u[train]).intersection(u[test])
        poly = PolynomialFeatures(2,include_bias=False)
        scaler = StandardScaler().fit(poly.fit_transform(x[train]))
        xt,xe = scaler.transform(poly.transform(x[train])),scaler.transform(poly.transform(x[test]))
        test_index = np.flatnonzero(test)
        gt,ge = group[train],group[test]
        spline = SplineTransformer(knots=np.linspace(0,2.4,6)[:,None],degree=3,
            include_bias=False,extrapolation="error").fit(np.array([[0.],[2.4]]))
        bt,be = spline.transform(a[train,None]),spline.transform(a[test,None])
        inner = group_folds(u[train],2,seed+int(fold)+130)
        populations = [None] if pooled else [0,1]
        for pop in populations:
            fit = np.ones(train.sum(),bool) if pop is None else gt==pop
            if fit.sum()<50 or len(set(a[ti[fit]]))<20:
                raise ValueError("insufficient conditional training population")
            outcome = Ridge(alpha=LAMBDA*fit.sum()).fit(_design(xt[fit],bt[fit]),y[train][fit])
            mu = outcome.predict(_design(xe,be))
            density_model = None
            if d["known_density"] is None:
                z = logit(a[train]/2.4)
                residual = np.full(train.sum(),np.nan)
                for k in (0,1):
                    fit_inner = fit & (inner!=k)
                    val_inner = fit & (inner==k)
                    if fit_inner.sum()<20 or not val_inner.any():
                        raise ValueError("sparse inner user fold")
                    model = Ridge(alpha=LAMBDA*fit_inner.sum()).fit(xt[fit_inner],z[fit_inner])
                    residual[val_inner] = z[val_inner]-model.predict(xt[val_inner])
                sd = float(np.sqrt(np.mean(residual[fit]**2)))
                if not np.isfinite(sd) or sd<.05:
                    raise ValueError("assignment density unsupported")
                density_model = Ridge(alpha=LAMBDA*fit.sum()).fit(xt[fit],z[fit])
                conditional = norm.pdf(logit(a[test]/2.4),density_model.predict(xe),sd) / (
                    2.4*(a[test]/2.4)*(1-a[test]/2.4))
            else:
                conditional = d["known_density"][test].copy()
            for g in ([0,1] if pop is None else [pop]):
                held = ge==g
                marginal = gt==g
                idx = test_index[held]
                if not len(idx) or not marginal.any():
                    raise ValueError("empty group in fold")
                mg = _marginal_prediction(outcome,xt[marginal].mean(0),spline,a[idx])
                vg = (d["known_density"][idx].copy() if density_model is None else
                      _marginal_logit_density(a[idx],density_model.predict(xt[marginal]),sd,0.,2.4))
                pi = conditional[held]
                if np.any(pi<=0) or not np.isfinite(pi).all():
                    raise ValueError("invalid conditional density")
                w = vg/pi
                if not np.isfinite(w).all() or max(w)>30:
                    raise ValueError("extreme weights; no trimming")
                xi[idx]=(y[idx]-mu[held])*w+mg
                weights[idx],mu_all[idx],pdf_all[idx],mm_all[idx],md_all[idx] = w,mu[held],pi,mg,vg
                scopes.append(dict(fold=int(fold),group=g,
                    train_event_index=ti[fit],test_event_index=idx,
                    marginal_event_index=ti[marginal],inner_fold_by_train_event=inner,
                    ridge_alpha=LAMBDA*fit.sum(),pooled=pooled))
    assert np.isfinite(xi).all()
    cfg = ContinuousEffectConfig(seed=seed,n_boot=99)
    rows = []
    for g in (0,1):
        mask = group==g
        row = summary_output(x[mask],a[mask],u[mask],xi[mask],weights[mask],cfg)
        row.update(event_index=np.flatnonzero(mask),folds=folds[mask],
                   mu_observed=mu_all[mask],conditional_density=pdf_all[mask],
                   marginal_mu=mm_all[mask],marginal_density=md_all[mask])
        rows.append(row)
    return rows,scopes


def fixed_or(d, support):
    x,a,y = [d[k] for k in ("X","dose","outcome")]
    states = StandardScaler().fit_transform(PolynomialFeatures(2,include_bias=False).fit_transform(x))
    spline = SplineTransformer(knots=np.linspace(0,2.4,6)[:,None],degree=3,
        include_bias=False,extrapolation="error").fit(np.array([[0.],[2.4]]))
    reg = Ridge(alpha=10.).fit(_design(states,spline.transform(a[:,None])),y)
    result=[]
    for j,mask in enumerate([np.ones(len(y),bool),x[:,0]<0,x[:,0]>=0]):
        if not support[j]:
            result.append(dict(status="unsupported",reason="common comparator support"))
        else:
            level=_marginal_prediction(reg,states[mask].mean(0),spline,GRID)
            result.append(dict(status="ok",level=level,contrast=level-level[0]))
    return result


def fit_cohort(d, seed):
    b0 = incumbent(d,seed)
    methods={"B0":b0}
    audits={}
    for method,pooled in (("C0",False),("C",True)):
        try:
            rows,scope=shared_auxiliary(d,seed,pooled)
            methods[method]=[b0[0],*rows]
            audits[method]=scope
        except (ValueError,np.linalg.LinAlgError) as exc:
            methods[method]=[b0[0],dict(status="unsupported",reason=str(exc)),
                            dict(status="unsupported",reason=str(exc))]
    joint=[all(methods[m][j]["status"]=="ok" for m in ("B0","C")) for j in range(3)]
    methods["OR"]=fixed_or(d,joint)
    smoother=load_smoothers()
    spline_rows=[]
    for j,mask in enumerate([np.ones(len(d["dose"]),bool),d["X"][:,0]<0,d["X"][:,0]>=0]):
        if not joint[j]:
            spline_rows.append(dict(status="unsupported",reason="common comparator support"))
            continue
        try:
            state=smoother.spline_state(d["dose"][mask],b0[j]["xi"],1e-4)
            level=smoother.spline_query(state,GRID)
            spline_rows.append(dict(status="ok",level=level,contrast=level-level[0],spline_state=state))
        except ValueError as exc:
            spline_rows.append(dict(status="unsupported",reason=str(exc)))
    methods["S"]=spline_rows
    return methods,audits


def score(methods, truths, group_fraction):
    scores={}
    for name,rows in methods.items():
        o=dict(full_group_output=all(r["status"]=="ok" for r in rows[1:]),group_difference_rmse=None,
               output_points=[len(GRID) if r["status"]=="ok" else 0 for r in rows],
               support_points=[sum(x["dose"] not in r.get("failed_doses",[]) for x in r["support"])
                               if "support" in r else (len(GRID) if r["status"]=="ok" else None)
                               for r in rows])
        for j,(r,t) in enumerate(zip(rows,truths)):
            if r["status"]=="ok":
                o[f"level_rmse_{j}"]=float(np.sqrt(np.mean((r["level"]-t)**2)))
                o[f"contrast_rmse_{j}"]=float(np.sqrt(np.mean((r["contrast"]-(t-t[0]))**2)))
                o[f"contrast_nonreference_rmse_{j}"]=float(np.sqrt(np.mean(
                    (r["contrast"][1:]-(t[1:]-t[0]))**2)))
        if o["full_group_output"]:
            error=(rows[2]["contrast"]-rows[1]["contrast"])-(
                (truths[2]-truths[2][0])-(truths[1]-truths[1][0]))
            o["group_difference_rmse"]=float(np.sqrt(np.mean(error**2)))
            o["group_difference_nonreference_rmse"]=float(np.sqrt(np.mean(error[1:]**2)))
        if all(r["status"]=="ok" for r in rows):
            mixture=(group_fraction*rows[1]["contrast"]+(1-group_fraction)*rows[2]["contrast"])
            o["group_mixture_discrepancy_rmse"]=float(np.sqrt(np.mean((rows[0]["contrast"]-mixture)**2)))
        scores[name]=o
    return scores


def assess(rows, stage):
    c="C"
    reference_methods=("B0","C0")
    gates={}
    full=lambda r,m:r["scores"][m]["full_group_output"]
    complete=sum(full(r,c) for r in rows)
    nblocks=len({r["seed"] for r in rows})
    n=len(rows)
    gates["overall_identical"]=all(r["overall_status"]=="ok" and
        r["overall_max_abs_delta"] is not None and r["overall_max_abs_delta"]<=1e-9 for r in rows)
    # No dropped cohort changes the target mechanism weights or independent-block estimand.
    gates["coverage"]=all(sum(full(r,m) for r in rows)==n for m in ("B0","C0","C"))
    comparisons={}
    for m in reference_methods:
        paired=[r for r in rows if full(r,m) and full(r,c)]
        a=float(np.mean([r["scores"][m]["group_difference_rmse"] for r in paired])) if paired else None
        b=float(np.mean([r["scores"][c]["group_difference_rmse"] for r in paired])) if paired else None
        blocks=[]
        for seed in sorted({r["seed"] for r in rows}):
            block=[r for r in rows if r["seed"]==seed]
            usable=[r for r in block if full(r,m) and full(r,c)]
            delta=float(np.mean([r["scores"][c]["group_difference_rmse"]-
                                r["scores"][m]["group_difference_rmse"] for r in usable])) if len(usable)==len(block) else None
            blocks.append(dict(seed=seed,delta=delta))
        wins=sum(bk["delta"] is not None and bk["delta"]<0 for bk in blocks)
        gates["gain_"+m]=a is not None and a>0 and b<=.95*a
        gates["wins_"+m]=wins>=(4 if stage=="development" else 15)
        if stage=="confirmation":
            # Missing blocks cannot satisfy a leave-one-block stability claim.
            gates["loo_"+m]=all(bk["delta"] is not None for bk in blocks) and all(
                np.mean([v["delta"] for v in blocks if v["seed"]!=bk["seed"]])<=0 for bk in blocks)
            gates["mechanism_"+m]=True
            for kind in sorted({r["mechanism"] for r in rows}):
                sub=[r for r in rows if r["mechanism"]==kind and full(r,m) and full(r,c)]
                gates["mechanism_"+m] &= len(sub)==nblocks and (
                    np.mean([r["scores"][c]["group_difference_rmse"] for r in sub])<=
                    np.mean([r["scores"][m]["group_difference_rmse"] for r in sub]))
            zero=[r for r in rows if r["mechanism"]=="zero_effect" and full(r,m) and full(r,c)]
            keys=("group_difference_rmse","contrast_rmse_1","contrast_rmse_2")
            gates["zero_"+m]=len(zero)==nblocks and all(
                np.mean([r["scores"][c][k] for r in zero])<=np.mean([r["scores"][m][k] for r in zero])
                for k in keys)
        comparisons[m]=dict(paired=len(paired),baseline=a,candidate=b,wins=wins,blocks=blocks)
    joint_wins=sum(all(comparisons[m]["blocks"][i]["delta"] is not None and
                       comparisons[m]["blocks"][i]["delta"]<0 for m in reference_methods)
                   for i in range(nblocks))
    if stage=="development":
        gates["joint_block_wins"]=joint_wins>=4
    if stage=="confirmation":
        paired=[r for r in rows if full(r,"C0") and full(r,c)]
        gates["single_group_noninferiority"]=bool(paired) and all(
            np.mean([r["scores"][c][k] for r in paired])<=np.mean([r["scores"]["C0"][k] for r in paired])+2
            for k in ("level_rmse_1","level_rmse_2","contrast_rmse_1","contrast_rmse_2"))
    return dict(stage=stage,gates=gates,pass_all=all(gates.values()),comparisons=comparisons,
                joint_block_wins=joint_wins,
                output_cohorts=complete,designed_cohorts=n,independent_seed_blocks=nblocks)


def run_stage(stage):
    # Calling a fitting stage is a deliberate future action, after total-manager review.
    if stage=="confirmation":
        receipt=json.loads((HERE/"development_receipt.json").read_text(encoding="utf-8"))
        if not receipt["decision"]["pass_all"]:
            raise ValueError("Development failed; no confirmation or retuning.")
        if receipt["source_sha256"]!=sources():
            raise ValueError("Source changed after development freeze.")
    else:
        receipt=None
    folder=HERE/stage
    folder.mkdir(exist_ok=False)
    freeze=sources()
    save(folder/"source_freeze.json",freeze)
    spec=PLAN[stage]
    rows=[]
    for seed in spec["seeds"]:
        for kind in spec["mechanisms"]:
            d=new_data.generate(seed,kind,spec["users_per_cohort"],spec["events_per_user"])
            target_masks=[np.ones(len(d["dose"]),bool),d["X"][:,0]<0,d["X"][:,0]>=0]
            truths=[new_data.truth(d["X"][mask],kind,GRID) for mask in target_masks]
            truth61=[new_data.truth(d["X"][mask],kind,GRID,nodes=61) for mask in target_masks]
            if max(np.max(abs(a-b)) for a,b in zip(truths,truth61))>1e-6:
                raise ValueError("Truth quadrature tolerance failed; do not score.")
            methods,audit=fit_cohort(d,seed)
            differences=[]
            for name in ("C0","C"):
                if methods["B0"][0]["status"]=="ok":
                    differences.append(float(np.max(abs(methods[name][0]["level"]-methods["B0"][0]["level"]))))
            row=dict(seed=seed,mechanism=kind,
                     scores=score(methods,truths,float(np.mean(d["X"][:,0]<0))),
                     overall_status=methods["B0"][0]["status"],
                     overall_max_abs_delta=max(differences) if differences else None)
            save(folder/f"{seed}-{kind}.json",dict(facts=d,truth_levels=truths,models=methods,
                                                 scopes=audit,score=row))
            rows.append(row)
            print(stage,seed,kind,"saved",flush=True)
    decision=assess(rows,stage)
    save(HERE/f"{stage}_receipt.json",dict(source_sha256=freeze,rows=rows,decision=decision,
        real_effect_validation=False,no_point5=True))


def preflight():
    # Numerical and contract checks only; replace fit by a guard while checking imports.
    def forbidden_fit(*args, **kwargs):
        raise AssertionError("No model fitting permitted during design preflight.")
    Ridge.fit=forbidden_fit
    ast_paths=[HERE/"new_data.py",Path(__file__)]
    for p in ast_paths:
        compile(p.read_text(encoding="utf-8"),str(p),"exec")
    allseeds=PLAN["development"]["seeds"]+PLAN["confirmation"]["seeds"]
    assert len(allseeds)==len(set(allseeds))==26
    assert len(GRID)==17 and GRID[0]==.4
    users=np.array(["u0","u0","u1","u1","u2","u2","u3","u3","u4","u4","u5","u5"])
    groups=np.tile([0,1],6)
    folds=group_folds(users,3,17)
    for k in set(folds):
        assert not set(users[folds==k]).intersection(users[folds!=k])
        assert set(groups[folds==k])=={0,1}
    # Oracle group pseudo-outcomes: correct group marginalization is not overall xi.
    mu=np.array([10.,20.,30.,40.])
    pi=np.array([.1,.2,.3,.4])
    groups=np.array([0,0,1,1])
    y=mu.copy()
    xi=np.empty(4)
    for g in (0,1):
        mask=groups==g
        xi[mask]=(y[mask]-mu[mask])*pi[mask].mean()/pi[mask]+mu[mask].mean()
    assert np.array_equal(xi,np.array([15.,15.,35.,35.]))
    assert not np.array_equal(xi,np.full(4,mu.mean()))
    assert np.isclose(LAMBDA*320,.1) and np.isclose(LAMBDA*160,.05)
    assert np.isclose((LAMBDA*160)/160,(LAMBDA*320)/320)
    # Artificial score records test adoption logic, not estimator performance.
    fake=[]
    for seed in PLAN["confirmation"]["seeds"]:
        for kind in PLAN["confirmation"]["mechanisms"]:
            scores={}
            for name,value in (("B0",100.),("C0",100.),("C",90.)):
                scores[name]=dict(full_group_output=True,group_difference_rmse=value,
                    contrast_rmse_1=value,contrast_rmse_2=value,level_rmse_1=value,level_rmse_2=value)
            fake.append(dict(seed=seed,mechanism=kind,scores=scores,
                             overall_status="ok",overall_max_abs_delta=0.))
    assert assess(fake,"confirmation")["pass_all"]
    fake[0]["scores"]["C"]["full_group_output"]=False
    assert not assess(fake,"confirmation")["gates"]["coverage"]
    assert not assess(fake,"confirmation")["pass_all"]
    fake[0]["scores"]["C"]["full_group_output"]=True
    fake[0]["overall_status"]="unsupported"
    fake[0]["overall_max_abs_delta"]=None
    assert not assess(fake,"confirmation")["gates"]["overall_identical"]
    # No generate(), fit_cohort(), _crossfit(), Ridge.fit() calls in preflight.
    save(HERE/"preflight.json",dict(passed=True,new_model_fits=0,
        research_development_or_confirmation_data_generated=False,
        checks=["syntax","26 disjoint reserved seeds","grid/reference","whole-user cross-group folds",
                "oracle group marginalization","mean-loss penalty scale",
                "synthetic score gates including missing coverage and unsupported overall"],
        limitations="No trained candidate, end-to-end training or empirical performance checked.",
        source_sha256=sources()))
    print("Preflight passed; zero model fits; no research cohorts generated.")


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--stage",choices=["preflight","development","confirmation"],default="preflight")
    args=parser.parse_args()
    if args.stage=="preflight":
        preflight()
    else:
        run_stage(args.stage)
