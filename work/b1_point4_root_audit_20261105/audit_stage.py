"""Read-only numerical audit of one already completed stage; no fitting/generation.

Usage: python audit_stage.py --stage development [--output report.json]
No estimator or data-generator module is imported. Reports live in this directory.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DESIGN = HERE.parent / "b1_point4_stability_design_20261105"
TOL = 1e-7


def read(p):
    return json.loads(p.read_text(encoding="utf-8"))


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def plain(x):
    if isinstance(x, np.ndarray):
        return x.tolist()
    if isinstance(x, np.generic):
        return x.item()
    if isinstance(x, dict):
        return {k: plain(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [plain(v) for v in x]
    return x


class Audit:
    def __init__(self):
        self.checks = 0
        self.failures = []
        self.max_abs = {}

    def check(self, ok, name):
        self.checks += 1
        if not bool(ok):
            self.failures.append(name)

    def close(self, a, b, name, tol=TOL):
        aa, bb = np.asarray(a), np.asarray(b)
        if aa.shape != bb.shape:
            self.check(False, name + ":shape")
            return
        delta = float(np.max(np.abs(aa - bb))) if aa.size else 0.0
        self.max_abs[name.split(":")[-1]] = max(self.max_abs.get(name.split(":")[-1], 0.0), delta)
        self.check(np.isfinite(aa).all() and np.isfinite(bb).all() and delta <= tol, name)

    def tree(self, expected, actual, name):
        if isinstance(expected, dict):
            self.check(set(expected) == set(actual), name + ":keys")
            for k in expected.keys() & actual.keys():
                self.tree(expected[k], actual[k], name + ":" + k)
        elif isinstance(expected, list):
            self.check(len(expected) == len(actual), name + ":length")
            for i, (a, b) in enumerate(zip(expected, actual)):
                self.tree(a, b, name + ":" + str(i))
        elif isinstance(expected, (float, np.floating)):
            self.close(expected, actual, name)
        else:
            self.check(expected == actual, name)


def rmse(x):
    return float(np.sqrt(np.mean(np.square(x))))


def truth61(x, mechanism, grid):
    # Independent expectation, not a call to new_data.response/truth or generate.
    nodes, weights = np.polynomial.legendre.leggauss(61)
    h = .6 * nodes[None, :]
    slack, demand = x[:, 0, None], x[:, 1, None]
    logistic = lambda z: 1. / (1. + np.exp(-z))
    out = []
    for a in grid:
        signal = 0. if mechanism == "zero_effect" else np.sin(np.pi * a / 2.4) if mechanism == "nonmonotone" else a
        ep = 1.2 * (slack >= 0) * np.sin(2*np.pi*a/2.4) if mechanism == "conditional_shape_shift" else 0.
        em = .7 * (slack >= 0) * np.cos(2*np.pi*a/2.4) if mechanism == "conditional_shape_shift" else 0.
        p = logistic(-1.5+1.25*signal*(1+.35*slack)+.5*slack-.45*demand+.35*h+ep)
        mu = logistic(-.6+.8*signal+.3*slack-.2*demand+.15*h+em)
        full = logistic(-3+.7*signal)
        out.append(float(np.mean((1800*p*(full+(1-full)*mu)) @ (weights/2))))
    return np.asarray(out)


def local_line(a, xi, grid, h):
    values = []
    for q in grid:
        z = a-q
        w = np.exp(-.5*(z/h)**2)
        s0, s1, s2 = w.sum(), np.dot(w,z), np.dot(w,z*z)
        t0, t1 = np.dot(w,xi), np.dot(w*z,xi)
        values.append((s2*t0-s1*t1)/(s0*s2-s1*s1))
    return np.asarray(values)


def support(x, a, users, grid, h, weights):
    rows, failed = [], []
    for q in grid:
        local = np.abs(a-q) <= h
        w = np.exp(-.5*((a-q)/h)**2)*weights
        ess = float(w.sum()**2/np.dot(w,w))
        smd = float(np.max(np.abs(np.average(x,axis=0,weights=w)-x.mean(0))/np.maximum(x.std(0),1e-8)))
        r = dict(dose=float(q), local_events=int(local.sum()), local_users=len(set(users[local])),
                 effective_events=ess,max_weighted_smd=smd)
        rows.append(r)
        if r["local_events"]<25 or r["local_users"]<15 or ess<20 or smd>.5:
            failed.append(float(q))
    return rows, failed


def score_all(models, truths, low_fraction, grid):
    scores = {}
    for name, rows in models.items():
        r = dict(full_group_output=all(z["status"]=="ok" for z in rows[1:]),group_difference_rmse=None,
                 output_points=[len(grid) if z["status"]=="ok" else 0 for z in rows],
                 support_points=[sum(s["dose"] not in z.get("failed_doses",[]) for s in z["support"])
                                 if "support" in z else len(grid) if z["status"]=="ok" else None for z in rows])
        for j, (z,t) in enumerate(zip(rows,truths)):
            if z["status"]=="ok":
                level = np.asarray(z["level"])
                contrast = level-level[0]
                error = contrast-(t-t[0])
                r[f"level_rmse_{j}"] = rmse(level-t)
                r[f"contrast_rmse_{j}"] = rmse(error)
                r[f"contrast_nonreference_rmse_{j}"] = rmse(error[1:])
        if r["full_group_output"]:
            low, high = [np.asarray(z["level"])-z["level"][0] for z in rows[1:]]
            e = high-low-((truths[2]-truths[2][0])-(truths[1]-truths[1][0]))
            r["group_difference_rmse"] = rmse(e)
            r["group_difference_nonreference_rmse"] = rmse(e[1:])
        if all(z["status"]=="ok" for z in rows):
            contrasts = [np.asarray(z["level"])-z["level"][0] for z in rows]
            r["group_mixture_discrepancy_rmse"] = rmse(contrasts[0]-low_fraction*contrasts[1]-(1-low_fraction)*contrasts[2])
        scores[name] = r
    return scores


def audit_cohort(obj, seed, mechanism, grid, audit):
    tag = f"{seed}/{mechanism}"
    facts, models = obj["facts"], obj["models"]
    x,a,y,u = [np.asarray(facts[k]) for k in ("X","dose","outcome","users")]
    masks = [np.ones(len(y),bool),x[:,0]<0,x[:,0]>=0]
    audit.check(x.shape==(480,3) and len(a)==len(y)==len(u)==480,tag+":fact_shapes")
    audit.check(len(set(u))==240 and set(Counter(u).values())=={2},tag+":user_counts")
    audit.check(np.isfinite(x).all() and np.isfinite(a).all() and np.isfinite(y).all() and
                (a>0).all() and (a<2.4).all() and (y>=0).all() and (y<=1800).all(),tag+":fact_domain")
    truth = [np.asarray(t) for t in obj["truth_levels"]]
    for j,mask in enumerate(masks):
        audit.close(truth[j],truth61(x[mask],mechanism,grid),tag+f":truth_{j}",tol=1e-6)
    failures = []
    for method, rows in models.items():
        audit.check(len(rows)==3,tag+":"+method+":populations")
        for j,r in enumerate(rows):
            label=tag+f":{method}:{j}"
            if r["status"]!="ok":
                failures.append(dict(method=method,population=j,reason=r.get("reason"),failed_doses=r.get("failed_doses")))
            if r["status"]=="ok":
                audit.check(len(r["level"])==len(grid),label+":level_length")
                audit.close(r["contrast"],np.asarray(r["level"])-r["level"][0],label+":contrast")
            if "xi" not in r:
                continue
            idx=np.flatnonzero(masks[j])
            audit.check(r["event_index"]==idx.tolist(),label+":event_index")
            xi,w,mu,pdf,mg,md = [np.asarray(r[k]) for k in ("xi","weights","mu_observed","conditional_density","marginal_mu","marginal_density")]
            audit.check(all(v.shape==idx.shape for v in (xi,w,mu,pdf,mg,md)),label+":auxiliary_shapes")
            audit.check((pdf>0).all() and np.isfinite(pdf).all() and np.isfinite(w).all() and (w<=30).all(),label+":density_valid")
            audit.close(w,md/pdf,label+":density_ratio")
            audit.close(xi,(y[idx]-mu)*w+mg,label+":pseudo_outcome")
            if facts["known_density"] is not None:
                audit.close(w,np.ones(len(idx)),label+":known_uniform_weights")
                audit.close(pdf,np.full(len(idx),1/2.4),label+":known_uniform_pdf")
            folds=np.asarray(r["folds"])
            for user in set(u[idx]):
                audit.check(len(set(folds[u[idx]==user]))==1,label+":whole_user_fold")
            h=1.06*np.std(a[idx])*len(set(u[idx]))**(-.2)
            audit.close(r["bandwidth"],h,label+":bandwidth")
            diagnostics, failed=support(x[idx],a[idx],u[idx],grid,h,w)
            audit.tree(diagnostics,r["support"],label+":support")
            audit.tree(failed,r["failed_doses"],label+":failed_doses")
            audit.check((not failed)==(r["status"]=="ok"),label+":support_status")
            if not failed:
                audit.close(r["level"],local_line(a[idx],xi,grid,h),label+":local_linear")
    for method in ("C0","C"):
        if method not in obj["scopes"]:
            audit.check(all(r["status"]!="ok" for r in models[method][1:]),tag+":"+method+":missing_scope_is_failure")
            continue
        allfolds=np.full(len(y),-1)
        for j in (1,2):
            allfolds[masks[j]]=models[method][j]["folds"]
        scope_test=[]
        for scope in obj["scopes"][method]:
            f,g=scope["fold"],scope["group"]
            outer=np.flatnonzero(allfolds!=f)
            expected_test=np.flatnonzero((allfolds==f)&masks[g+1])
            expected_marginal=np.flatnonzero((allfolds!=f)&masks[g+1])
            train=np.asarray(scope["train_event_index"],dtype=int)
            test=np.asarray(scope["test_event_index"],dtype=int)
            marginal=np.asarray(scope["marginal_event_index"],dtype=int)
            label=tag+f":{method}:scope{f}-{g}"
            audit.check(test.tolist()==expected_test.tolist(),label+":test_population")
            audit.check(marginal.tolist()==expected_marginal.tolist(),label+":marginal_population")
            audit.check(train.tolist()==(outer if method=="C" else expected_marginal).tolist(),label+":train_population")
            audit.check(not set(u[train])&set(u[test]) and not set(u[marginal])&set(u[test]),label+":user_isolation")
            audit.check(scope["pooled"]==(method=="C"),label+":pooling")
            audit.close(scope["ridge_alpha"],.1/320*len(train),label+":mean_loss_penalty")
            inner=np.asarray(scope["inner_fold_by_train_event"])
            audit.check(len(inner)==len(outer) and set(inner)=={0,1},label+":inner_shape")
            for user in set(u[outer]):
                audit.check(len(set(inner[u[outer]==user]))==1,label+":inner_user_isolation")
            scope_test.extend(test.tolist())
        audit.check(sorted(scope_test)==list(range(len(y))),tag+":"+method+":scope_complete_once")
    for j in (1,2):
        c0,c=models["C0"][j],models["C"][j]
        if "folds" in c0 and "folds" in c:
            audit.check(c0["folds"]==c["folds"],tag+f":same_folds_{j}")
    delta=[]
    for method in ("C0","C"):
        if models["B0"][0]["status"]=="ok":
            for field in ("level","contrast"):
                audit.close(models[method][0][field],models["B0"][0][field],tag+":"+method+":overall_"+field,tol=1e-9)
            delta.append(float(np.max(np.abs(np.asarray(models[method][0]["level"])-models["B0"][0]["level"]))))
    scores=score_all(models,truth,float(masks[1].mean()),grid)
    row=dict(seed=seed,mechanism=mechanism,scores=scores,overall_status=models["B0"][0]["status"],overall_max_abs_delta=max(delta) if delta else None)
    audit.tree(row,obj["score"],tag+":saved_scores")
    return row, failures


def decision(rows, stage):
    full=lambda r,m:r["scores"][m]["full_group_output"]
    seeds=sorted({r["seed"] for r in rows})
    gates=dict(overall_identical=all(r["overall_status"]=="ok" and r["overall_max_abs_delta"] is not None and r["overall_max_abs_delta"]<=1e-9 for r in rows),
               coverage=all(all(full(r,m) for r in rows) for m in ("B0","C0","C")))
    comparisons={}
    for baseline in ("B0","C0"):
        pairs=[r for r in rows if full(r,baseline) and full(r,"C")]
        av=lambda rs,m,k:float(np.mean([r["scores"][m][k] for r in rs]))
        a=av(pairs,baseline,"group_difference_rmse") if pairs else None
        b=av(pairs,"C","group_difference_rmse") if pairs else None
        blocks=[]
        for seed in seeds:
            rs=[r for r in rows if r["seed"]==seed]
            d=av(rs,"C","group_difference_rmse")-av(rs,baseline,"group_difference_rmse") if all(full(r,baseline) and full(r,"C") for r in rs) else None
            blocks.append(dict(seed=seed,delta=d))
        wins=sum(z["delta"] is not None and z["delta"]<0 for z in blocks)
        gates["gain_"+baseline]=a is not None and a>0 and b<=.95*a
        gates["wins_"+baseline]=wins>=(4 if stage=="development" else 15)
        if stage=="confirmation":
            gates["loo_"+baseline]=all(z["delta"] is not None for z in blocks) and all(np.mean([q["delta"] for q in blocks if q["seed"]!=z["seed"]])<=0 for z in blocks)
            gates["mechanism_"+baseline]=all(len(rs:=[r for r in rows if r["mechanism"]==kind and full(r,baseline) and full(r,"C")])==len(seeds) and av(rs,"C","group_difference_rmse")<=av(rs,baseline,"group_difference_rmse") for kind in {r["mechanism"] for r in rows})
            zero=[r for r in rows if r["mechanism"]=="zero_effect" and full(r,baseline) and full(r,"C")]
            gates["zero_"+baseline]=len(zero)==len(seeds) and all(av(zero,"C",key)<=av(zero,baseline,key) for key in ("group_difference_rmse","contrast_rmse_1","contrast_rmse_2"))
        comparisons[baseline]=dict(paired=len(pairs),baseline=a,candidate=b,wins=wins,blocks=blocks)
    joint=sum(all(comparisons[m]["blocks"][i]["delta"] is not None and comparisons[m]["blocks"][i]["delta"]<0 for m in ("B0","C0")) for i in range(len(seeds)))
    if stage=="development":
        gates["joint_block_wins"]=joint>=4
    else:
        pairs=[r for r in rows if full(r,"C0") and full(r,"C")]
        gates["single_group_noninferiority"]=bool(pairs) and all(av(pairs,"C",k)<=av(pairs,"C0",k)+2 for k in ("level_rmse_1","level_rmse_2","contrast_rmse_1","contrast_rmse_2"))
    return plain(dict(stage=stage,gates=gates,pass_all=all(gates.values()),comparisons=comparisons,joint_block_wins=joint,
                      output_cohorts=sum(full(r,"C") for r in rows),designed_cohorts=len(rows),independent_seed_blocks=len(seeds)))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage",choices=("development","confirmation"),default="development")
    parser.add_argument("--output",default=None)
    args=parser.parse_args()
    receipt_path=DESIGN/f"{args.stage}_receipt.json"
    if not receipt_path.is_file():
        print(f"No completed {args.stage} receipt; no data opened and no report written.")
        return 2
    audit=Audit()
    plan,receipt=read(DESIGN/"experiment_plan.json"),read(receipt_path)
    spec,grid=plan[args.stage],np.asarray(plan["estimands"]["grid"])
    freeze=read(DESIGN/args.stage/"source_freeze.json")
    audit.check(freeze==receipt["source_sha256"],"receipt_source_freeze")
    for name,digest in freeze.items():
        audit.check(sha(ROOT/name)==digest,"source_hash:"+name)
    expected=[(s,k) for s in spec["seeds"] for k in spec["mechanisms"]]
    audit.check([(r["seed"],r["mechanism"]) for r in receipt["rows"]]==expected,"expected_receipt_keys")
    rows,failed,files=[],[],{}
    for seed,kind in expected:
        p=DESIGN/args.stage/f"{seed}-{kind}.json"
        obj=read(p)
        row,f=audit_cohort(obj,seed,kind,grid,audit)
        rows.append(row)
        failed.extend(dict(seed=seed,mechanism=kind,**z) for z in f)
        files[p.name]=sha(p)
    audit.tree(rows,receipt["rows"],"receipt_rows")
    independent=decision(rows,args.stage)
    audit.tree(independent,receipt["decision"],"receipt_decision")
    report=plain(dict(stage=args.stage,passed=not audit.failures,checks=audit.checks,failures=audit.failures,
        receipt_sha256=sha(receipt_path),audit_script_sha256=sha(Path(__file__)),cohort_sha256=files,
        max_abs_differences=audit.max_abs,decision=independent,failure_ledger=failed,recomputed_rows=rows,
        new_fits=0,research_data_generated=False,
        limitations=["No model refit or saved-model prediction replay. Conditional model coefficients were not saved; numerical mu/marginal predictions cannot be independently reconstructed.",
                     "B0 marginal_mu and marginal_density were algebraically recovered by the runner; their identity checks are not independent evidence for original marginalization.",
                     "Saved scopes verify index and user separation. They do not prove an implementation never read excluded data; no perturbation/refit leakage experiment was run.",
                     "Truth is independently integrated over saved X only; no new random cohort is generated and no other stage is opened."]))
    out=HERE/(args.output or f"{args.stage}_audit.json")
    with out.open("x",encoding="utf-8") as fp:
        json.dump(report,fp,ensure_ascii=False,indent=2,allow_nan=False)
        fp.write("\n")
    print(json.dumps(dict(passed=report["passed"],checks=audit.checks,failures=len(audit.failures),stage=args.stage,
                          candidate_pass=independent["pass_all"],output=str(out)),ensure_ascii=False))
    return 0 if report["passed"] else 1


if __name__=="__main__":
    sys.exit(main())
