"""One fixed R candidate; development only under the current release."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import sys
import time

for key in ("OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS"):
    os.environ[key]="1"
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/"B1算法"))
import numpy as np
import scipy
import sklearn
from b1_algorithm.effects.core import group_folds
from b1_algorithm.effects.continuous import local_linear_weights
import continuous_r as cr
import baselines

PLAN=json.loads((HERE/"protocol.json").read_text(encoding="utf-8"))
GRID=np.asarray(PLAN["target"]["grid"])
GENERATOR=ROOT/"work/b1_point4_stability_design_20261105/new_data.py"
spec=importlib.util.spec_from_file_location("r_pilot_declared_generator",GENERATOR)
data=importlib.util.module_from_spec(spec)
spec.loader.exec_module(data)


def plain(x):
    if isinstance(x,np.ndarray):return x.tolist()
    if isinstance(x,np.generic):return x.item()
    if isinstance(x,dict):return {k:plain(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [plain(v) for v in x]
    return x


def save(p,obj):
    with p.open("x",encoding="utf-8") as fp:
        json.dump(plain(obj),fp,ensure_ascii=False,indent=2,allow_nan=False)
        fp.write("\n")


def sources():
    # Audit subdirectories are excluded explicitly; all training code/dependencies are listed.
    paths=sorted(HERE.glob("*.py"))+[HERE/"protocol.json",GENERATOR,
        ROOT/"work/b1_curve_spline_pilot_20261103/smoothers.py"]
    paths+=sorted((ROOT/"B1算法/b1_algorithm").rglob("*.py"))
    return {p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def rmse(x):
    return float(np.sqrt(np.mean(np.asarray(x)**2)))


def scores(predicted,truths):
    out={}
    true=[t-t[0] for t in truths]
    for method,pops in predicted.items():
        row=dict(full_group_output=all(r["status"]=="ok" for r in pops[1:]),
                 group_difference_rmse=None,output_points=[
                     len(GRID) if r["status"]=="ok" else 0 for r in pops])
        for j,(p,t) in enumerate(zip(pops,true)):
            if p["status"]=="ok":
                row[f"increment_rmse_{j}"]=rmse(np.asarray(p["contrast"])-t)
                if p.get("level") is not None:
                    row[f"level_rmse_{j}"]=rmse(np.asarray(p["level"])-truths[j])
        if row["full_group_output"]:
            error=(np.asarray(pops[2]["contrast"])-np.asarray(pops[1]["contrast"]))-(true[2]-true[1])
            row["group_difference_rmse"]=rmse(error)
            row["group_difference_nonreference_rmse"]=rmse(error[1:])
        out[method]=row
    return out


def decision(rows,stage):
    spec=PLAN["data"][stage]
    expected={(s,k) for s in spec["seeds"] for k in spec["mechanisms"]}
    actual=[(r["seed"],r["mechanism"]) for r in rows]
    designed=len(expected)
    full=lambda r,m:r["scores"][m]["full_group_output"]
    gates=dict(exact_cohort_set=set(actual)==expected and len(actual)==designed,
        common_output=all(sum(full(r,m) for r in rows)==designed for m in ("B0","OR10","R")),
        zero_reference=all(r["reference_exact_zero"] for r in rows),
        overall_unchanged=all(r["overall_equals_B0"] for r in rows))
    comparisons={}
    for ref in ("B0","OR10"):
        paired=[r for r in rows if full(r,"R") and full(r,ref)]
        a=float(np.mean([r["scores"][ref]["group_difference_rmse"] for r in paired])) if paired else None
        b=float(np.mean([r["scores"]["R"]["group_difference_rmse"] for r in paired])) if paired else None
        gates["gain_"+ref]=a is not None and a>0 and b<=.95*a
        deltas=[]
        for seed in spec["seeds"]:
            block=[r for r in paired if r["seed"]==seed]
            delta=(float(np.mean([r["scores"]["R"]["group_difference_rmse"]-
                                  r["scores"][ref]["group_difference_rmse"] for r in block]))
                   if {r["mechanism"] for r in block}==set(spec["mechanisms"]) and
                   len(block)==len(spec["mechanisms"]) else None)
            deltas.append(dict(seed=seed,delta=delta))
        gates["mechanisms_"+ref]=True
        for kind in spec["mechanisms"]:
            sub=[r for r in paired if r["mechanism"]==kind]
            gates["mechanisms_"+ref] &= len(sub)==len(spec["seeds"]) and (
                np.mean([r["scores"]["R"]["group_difference_rmse"] for r in sub])<=
                np.mean([r["scores"][ref]["group_difference_rmse"] for r in sub]))
        gates["single_group_noninferior_"+ref]=len(paired)==designed and all(
            np.mean([r["scores"]["R"][f"increment_rmse_{g}"] for r in paired])<=
            np.mean([r["scores"][ref][f"increment_rmse_{g}"] for r in paired])+2 for g in (1,2))
        comparisons[ref]=dict(paired=len(paired),baseline=a,candidate=b,blocks=deltas,
                              seed_wins=sum(v["delta"] is not None and v["delta"]<0 for v in deltas))
    joint=sum(all(comparisons[m]["blocks"][i]["delta"] is not None and
                  comparisons[m]["blocks"][i]["delta"]<0 for m in ("B0","OR10"))
              for i in range(len(spec["seeds"])))
    gates["joint_seed_wins"]=joint>=(4 if stage=="development" else 15)
    if stage=="confirmation":
        for ref in ("B0","OR10"):
            blocks=comparisons[ref]["blocks"]
            gates["seed_wins_"+ref]=comparisons[ref]["seed_wins"]>=15
            gates["leave_one_"+ref]=all(v["delta"] is not None for v in blocks) and all(
                np.mean([v["delta"] for v in blocks if v["seed"]!=b["seed"]])<=0 for b in blocks)
            zeros=[r for r in rows if r["mechanism"]=="zero_effect" and full(r,"R") and full(r,ref)]
            gates["zero_effect_"+ref]=len(zeros)==len(spec["seeds"]) and all(
                np.mean([r["scores"]["R"][key] for r in zeros])<=np.mean(
                    [r["scores"][ref][key] for r in zeros])
                for key in ("group_difference_rmse","increment_rmse_1","increment_rmse_2"))
    return dict(stage=stage,gates=gates,pass_all=all(gates.values()),comparisons=comparisons,
                joint_winning_blocks=joint,designed=designed,observed=len(rows))


def synthetic_preflight():
    # Score-ledger examples only. No generator or estimator called.
    def fake():
        rows=[]
        for seed in PLAN["data"]["development"]["seeds"]:
            for kind in PLAN["data"]["development"]["mechanisms"]:
                sc={m:dict(full_group_output=True,group_difference_rmse=v,
                           increment_rmse_1=v,increment_rmse_2=v)
                    for m,v in (("B0",100.),("OR10",100.),("R",40.))}
                rows.append(dict(seed=seed,mechanism=kind,scores=sc,
                                 reference_exact_zero=True,overall_equals_B0=True))
        return rows
    positive=decision(fake(),"development")
    assert positive["pass_all"]
    split=fake()
    for r in split:
        i=PLAN["data"]["development"]["seeds"].index(r["seed"])
        r["scores"]["R"].update(group_difference_rmse=60.,increment_rmse_1=1.,increment_rmse_2=1.)
        r["scores"]["B0"]["group_difference_rmse"]=100. if i<4 else 50.
        r["scores"]["OR10"]["group_difference_rmse"]=100. if i>=2 else 50.
    split_result=decision(split,"development")
    assert split_result["comparisons"]["B0"]["seed_wins"]==4
    assert split_result["comparisons"]["OR10"]["seed_wins"]==4
    assert split_result["joint_winning_blocks"]==2 and not split_result["pass_all"]
    missing=decision(fake()[:-1],"development")
    assert not missing["gates"]["exact_cohort_set"] and not missing["pass_all"]
    weak=fake()
    for r in weak:r["scores"]["OR10"]["group_difference_rmse"]=30.
    weak_result=decision(weak,"development")
    assert not weak_result["gates"]["gain_OR10"] and not weak_result["pass_all"]
    unsupported=fake();unsupported[0]["scores"]["R"]["full_group_output"]=False
    unsupported_result=decision(unsupported,"development")
    assert not unsupported_result["gates"]["common_output"] and not unsupported_result["pass_all"]
    return dict(passed=True,research_fits=0,research_cohorts_generated=0,
                positive=positive,split_wins=split_result,missing=missing,
                strong_OR=weak_result,unsupported=unsupported_result)


def cohort(d,seed,kind):
    x,a,y,u=[d[k] for k in ("X","dose","outcome","users")]
    masks=[np.ones(len(a),bool),x[:,0]<0,x[:,0]>=0]
    b0=baselines.fit_b0(d,seed,GRID)
    common=[p["status"]=="ok" for p in b0]
    or_state=baselines.fit_or(d,common)
    or_pops=[]
    for j,mask in enumerate(masks):
        if common[j]:
            level=baselines.query_or(or_state,x[mask],GRID)
            or_pops.append(dict(status="ok",level=level,contrast=level-level[0]))
        else:or_pops.append(dict(status="unsupported",reason="common B0 support"))
    smooth=baselines.retained_smoothers()
    s_pops=[]
    for j,mask in enumerate(masks):
        if not common[j]:
            s_pops.append(dict(status="unsupported",reason="common B0 support"))
            continue
        try:
            st=smooth.spline_state(a[mask],b0[j]["xi"],1e-4)
            level=smooth.spline_query(st,GRID)
            s_pops.append(dict(status="ok",level=level,contrast=level-level[0],spline_state=st))
        except (ValueError,np.linalg.LinAlgError) as exc:
            s_pops.append(dict(status="unsupported",reason=str(exc)))
    folds=group_folds(u,3,seed)
    rmodel=None
    try:
        rmodel=cr.fit_increment_surface(x,a,y,u,folds,known_uniform=kind=="randomized")
        rmodel["group_support"]={str(j):b0[j].get("support") for j in (1,2)}
        rmodel["common_group_eligible"]={str(j):common[j] for j in (1,2)}
        rpops=[b0[0]]
        for j,mask in enumerate(masks[1:],1):
            if not common[j]:
                rpops.append(dict(status="unsupported",reason="common B0 support",level=None))
                continue
            try:
                increment=cr.query_group(rmodel,x[mask],GRID)
                rpops.append(dict(status="ok",level=None,contrast=increment))
            except (ValueError,np.linalg.LinAlgError) as exc:
                rpops.append(dict(status="unsupported",reason=str(exc),level=None))
    except (ValueError,np.linalg.LinAlgError) as exc:
        rpops=[b0[0],dict(status="unsupported",reason=str(exc),level=None),
               dict(status="unsupported",reason=str(exc),level=None)]
    truths=[data.truth(x[mask],kind,GRID) for mask in masks]
    truth61=[data.truth(x[mask],kind,GRID,nodes=61) for mask in masks]
    truth_diff=max(float(np.max(abs(v-w))) for v,w in zip(truths,truth61))
    if truth_diff>1e-6:raise ValueError("Declared quadrature tolerance failed.")
    methods=dict(B0=b0,OR10=or_pops,S=s_pops,R=rpops)
    row=dict(seed=seed,mechanism=kind,scores=scores(methods,truths),
        reference_exact_zero=all(p["status"]!="ok" or np.all(np.asarray(p["contrast"])[0]==0)
                                 for p in rpops[1:]),
        overall_equals_B0=rpops[0] is b0[0])
    return dict(facts=d,truth_levels=truths,truth_quadrature_max_diff=truth_diff,
                populations=methods,R_model=rmodel,OR_model=or_state,score=row)


def run(stage):
    if stage!="development":
        raise ValueError("Only development is authorized in this run.")
    folder=HERE/stage
    if folder.exists():raise FileExistsError("No rerun/overwrite of consumed development.")
    preflight=synthetic_preflight()
    freeze=sources()
    environment=dict(python=sys.version,executable=sys.executable,platform=platform.platform(),
        numpy=np.__version__,scipy=scipy.__version__,sklearn=sklearn.__version__,
        threads={k:os.environ[k] for k in ("OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS")})
    folder.mkdir(exist_ok=False)
    save(folder/"gate_preflight.json",preflight)
    save(folder/"source_freeze.json",freeze)
    save(folder/"environment.json",environment)
    save(folder/"freeze_rule.json",dict(training_sources="All top-level py, protocol, explicit generator/smoother and B1 py; audit subdirectories excluded.",
        first_research_generation_after_freeze=True,stage=stage,confirmation_authorized=False))
    rows=[]
    start=time.perf_counter()
    for seed in PLAN["data"][stage]["seeds"]:
        for kind in PLAN["data"][stage]["mechanisms"]:
            if sources()!=freeze:raise ValueError("Training source changed during run; stop.")
            d=data.generate(seed,kind,PLAN["data"]["users_per_cohort"],PLAN["data"]["events_per_user"])
            value=cohort(d,seed,kind)
            if sources()!=freeze:raise ValueError("Training source changed during cohort; stop.")
            save(folder/f"{seed}-{kind}.json",value)
            rows.append(value["score"])
            print(stage,seed,kind,"saved",flush=True)
    result=decision(rows,stage)
    save(HERE/f"{stage}_receipt.json",dict(stage=stage,source_sha256=freeze,environment=environment,
        rows=rows,decision=result,elapsed_seconds=time.perf_counter()-start,
        actual_research_fitting_completed=True,data_kind="new known-truth simulation",confirmation_generated=False))
    print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--stage",choices=["development"],required=True)
    args=parser.parse_args()
    run(args.stage)
