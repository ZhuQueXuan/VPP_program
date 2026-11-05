"""Read-only numerical audit of fitted outputs. No estimator imports or fitting."""
import csv
import hashlib
import json
from pathlib import Path
from statistics import mean
import sys
import numpy as np
from scipy.interpolate import BSpline

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
STUDY=HERE.parent/"b1_point4_stability_design_20261105"
GRID=np.array([.4+.1*i for i in range(17)])


def load(p):
    return json.loads(p.read_text(encoding="utf-8"))


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def ll(d,y,h,query):
    # Independent local-polynomial normal-equation arithmetic in physical dose units.
    z=d[None,:]-np.asarray(query)[:,None]
    k=np.exp(-.5*(z/h)**2)
    s0=np.sum(k,axis=1)
    s1=np.sum(k*z,axis=1)
    s2=np.sum(k*z*z,axis=1)
    t0=np.sum(k*y,axis=1)
    t1=np.sum(k*z*y,axis=1)
    return (s2*t0-s1*t1)/(s0*s2-s1*s1)


def support(x,d,u,h,w,a):
    kernel=np.exp(-.5*((d-a)/h)**2)*w
    ess=kernel.sum()**2/np.sum(kernel**2)
    smd=np.max(abs(np.average(x,axis=0,weights=kernel)-x.mean(0))/np.maximum(x.std(0),1e-8))
    local=abs(d-a)<=h
    n,g=int(local.sum()),len(set(u[local]))
    return n,g,float(ess),float(smd),n>=25 and g>=15 and ess>=20 and smd<=.5


def true_levels(x,kind,grid,nodes):
    z,w=np.polynomial.legendre.leggauss(nodes)
    l=x[:,0,None]
    urgency=x[:,1,None]
    h=.6*z[None,:]
    out=[]
    for a in grid:
        signal=0 if kind=="zero_effect" else np.sin(np.pi*a/2.4) if kind=="nonmonotone" else a
        p=1/(1+np.exp(-(-1.5+1.25*signal*(1+.35*l)+.5*l-.45*urgency+.35*h)))
        mu=1/(1+np.exp(-(-.6+.8*signal+.3*l-.2*urgency+.15*h)))
        full=1/(1+np.exp(-(-3+.7*signal)))
        out.append(1800*np.mean((p*(full+(1-full)*mu)) @ (w/2)))
    return np.array(out)


def main():
    count=0
    max_level_replay=0.
    max_truth_diff=0.
    min_support=dict(events=10**9,users=10**9,ess=1e99)
    maximum_smd=0.
    maximum_weight=0.
    ck_history=[]
    def ck(ok,label):
        nonlocal count
        if not ok:
            raise AssertionError(label)
        count+=1
    receipt=load(STUDY/"development_receipt.json")
    plan=load(STUDY/"experiment_plan.json")
    root=load(STUDY/"ROOT_PREFLIGHT.json")
    ck(receipt["source_sha256"]==root["all_training_sources"],"reviewed training freeze")
    for name,digest in receipt["source_sha256"].items():
        ck(sha(ROOT/name)==digest,name)
    frozen=load(STUDY/"development/source_freeze.json")
    ck(frozen==receipt["source_sha256"],"stage freeze")
    ck(not (STUDY/"confirmation").exists(),"confirmation not opened")
    outputs=list((STUDY/"development").glob("*.json"))
    outputs=[p for p in outputs if p.name!="source_freeze.json"]
    ck(len(outputs)==24,"24 saved cohorts")
    table=[]
    queries=[]
    cohorts=[]
    for seed in plan["development"]["seeds"]:
        for kind in plan["development"]["mechanisms"]:
            path=STUDY/"development"/f"{seed}-{kind}.json"
            obj=load(path)
            x=np.array(obj["facts"]["X"]);d=np.array(obj["facts"]["dose"])
            y=np.array(obj["facts"]["outcome"]);u=np.array(obj["facts"]["users"])
            ck(len(y)==480 and len(set(u))==240,"event/user counts")
            ck(all(np.sum(u==v)==2 for v in set(u)),"two events per user")
            ck(np.isfinite(y).all() and min(y)>=0 and max(y)<=1800,"bounded observed response")
            ck(np.all((d>0)&(d<2.4)),"continuous interior")
            truths=[np.array(t) for t in obj["truth_levels"]]
            masks=[np.ones(480,bool),x[:,0]<0,x[:,0]>=0]
            for mask,t in zip(masks,truths):
                own=true_levels(x[mask],kind,GRID,61)
                err=float(np.max(abs(own-t)))
                max_truth_diff=max(max_truth_diff,err)
                ck(err<1e-6,"independent integral truth")
            w=float(np.mean(masks[1]))
            ck(np.max(abs(truths[0]-w*truths[1]-(1-w)*truths[2]))<1e-9,"target population")
            recomputed={}
            for name,pops in obj["models"].items():
                ck(all(p["status"]=="ok" for p in pops),"all populations output")
                out=[]
                for pop,(p,t) in enumerate(zip(pops,truths)):
                    level=np.array(p["level"]);delta=np.array(p["contrast"])
                    ck(len(level)==17 and len(delta)==17,"17-point arrays")
                    ck(np.max(abs(delta-(level-level[0])))<1e-9,"saved reference subtraction")
                    for label,v in (("level_rmse",level-t),("contrast_rmse",delta-(t-t[0])),
                                    ("contrast_nonreference_rmse",(delta-(t-t[0]))[1:])):
                        rmse=float(np.sqrt(np.mean(v*v)))
                        ck(abs(rmse-obj["score"]["scores"][name][f"{label}_{pop}"])<1e-9,"score replay")
                    if name in ("B0","C0","C"):
                        idx=np.array(p["event_index"])
                        ck(np.array_equal(idx,np.flatnonzero(masks[pop])),"population binding")
                        a=d[idx];xi=np.array(p["xi"]);weights=np.array(p["weights"])
                        mu=np.array(p["mu_observed"]);pi=np.array(p["conditional_density"])
                        mg=np.array(p["marginal_mu"]);vg=np.array(p["marginal_density"])
                        ck(np.max(abs(xi-((y[idx]-mu)*vg/pi+mg)))<1e-9,"DR xi")
                        ck(np.max(abs(weights-vg/pi))<1e-12,"stabilized weights")
                        ck(np.isfinite(xi).all() and min(pi)>0 and max(weights)<=30,"finite xi and GPS")
                        maximum_weight=max(maximum_weight,float(max(weights)))
                        h=p["bandwidth"]
                        ck(abs(h-1.06*np.std(a)*len(set(u[idx]))**(-.2))<1e-12,"fixed bandwidth")
                        own=ll(a,xi,h,GRID)
                        replay=float(np.max(abs(own-level)))
                        max_level_replay=max(max_level_replay,replay)
                        ck(replay<1e-9,"independent LL replay")
                        for q,stored in zip(GRID,p["support"]):
                            n,g,ess,smd,good=support(x[idx],a,u[idx],h,weights,q)
                            ck(good,"support passed")
                            ck(n==stored["local_events"] and g==stored["local_users"],"support counts")
                            ck(abs(ess-stored["effective_events"])<1e-9 and abs(smd-stored["max_weighted_smd"])<1e-10,"ESS and balance")
                            min_support["events"]=min(min_support["events"],n)
                            min_support["users"]=min(min_support["users"],g)
                            min_support["ess"]=min(min_support["ess"],ess)
                            maximum_smd=max(maximum_smd,smd)
                        for q in (.4,.73,1.17,1.2,2.):
                            prediction=float(ll(a,xi,h,[q])[0])
                            nested=float(ll(a,xi,h,[.4,q,2.])[1])
                            ck(abs(prediction-nested)<1e-9,"query set invariance")
                            supported=support(x[idx],a,u[idx],h,weights,q)[-1]
                            queries.append(dict(seed=seed,mechanism=kind,method=name,population=pop,
                                                amount=q,level=prediction,contrast=prediction-float(ll(a,xi,h,[.4])[0]),
                                                supported=supported))
                    elif name=="S":
                        state=p["spline_state"]
                        f=BSpline(state["knots"],state["coefficients"],state["degree"],extrapolate=False)
                        own=f(GRID/state["x_scale"])*state["y_scale"]
                        ck(np.max(abs(own-level))<1e-9,"loaded spline state")
                    out.append(delta)
                diff=(out[2]-out[1])-((truths[2]-truths[2][0])-(truths[1]-truths[1][0]))
                primary=float(np.sqrt(np.mean(diff*diff)))
                ck(abs(primary-obj["score"]["scores"][name]["group_difference_rmse"])<1e-9,"group difference error")
                discrepancy=float(np.sqrt(np.mean((out[0]-w*out[1]-(1-w)*out[2])**2)))
                ck(abs(discrepancy-obj["score"]["scores"][name]["group_mixture_discrepancy_rmse"])<1e-9,"group mixture")
                ck(obj["score"]["scores"][name]["output_points"]==[17,17,17],"output accounting")
                recomputed[name]=primary
                table.append(dict(seed=seed,mechanism=kind,method=name,group_difference_rmse=primary,
                                  **{k:obj["score"]["scores"][name][k] for k in
                                     ("level_rmse_0","level_rmse_1","level_rmse_2",
                                      "contrast_rmse_0","contrast_rmse_1","contrast_rmse_2")}))
            for method in ("C0","C"):
                for key in ("level","contrast"):
                    ck(np.array_equal(obj["models"][method][0][key],obj["models"]["B0"][0][key]),"overall exact copy")
            cohorts.append(dict(seed=seed,mechanism=kind,errors=recomputed))
    blocks=[]
    for seed in plan["development"]["seeds"]:
        row=dict(seed=seed)
        for m in ("B0","C0","C","OR","S"):
            row[m]=mean(r["errors"][m] for r in cohorts if r["seed"]==seed)
        row.update(C_minus_B0=row["C"]-row["B0"],C_minus_C0=row["C"]-row["C0"])
        row["joint_win"]=row["C_minus_B0"]<0 and row["C_minus_C0"]<0
        blocks.append(row)
    means={m:mean(r["errors"][m] for r in cohorts) for m in ("B0","C0","C","OR","S")}
    gates=dict(overall_identical=True,coverage=True)
    for ref in ("B0","C0"):
        wins=sum(b["C"]<b[ref] for b in blocks)
        gates["gain_"+ref]=means["C"]<=.95*means[ref]
        gates["wins_"+ref]=wins>=4
    joint=sum(b["joint_win"] for b in blocks)
    gates["joint_block_wins"]=joint>=4
    ck(gates==receipt["decision"]["gates"],"all predeclared gates")
    ck(all(gates.values())==receipt["decision"]["pass_all"] is False,"stop")
    ck(joint==receipt["decision"]["joint_block_wins"]==3,"joint winners")
    for name,data in (("cohort_metrics.csv",table),("block_metrics.csv",blocks),("queries_replayed.csv",queries)):
        with (HERE/name).open("w",encoding="utf-8-sig",newline="") as fp:
            w=csv.DictWriter(fp,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
    out=dict(date="2026-11-05",passed=True,checks=count,extra_model_fits=0,
        actual_development_cohorts=24,independent_seed_blocks=6,
        loaded_LL_population_curves=216,loaded_S_population_curves=72,
        replayed_query_outputs=len(queries),maximum_LL_saved_error_seconds=max_level_replay,
        maximum_independent_truth_error_seconds=max_truth_diff,
        minimum_support=min_support,maximum_weighted_smd=maximum_smd,maximum_stabilized_weight=maximum_weight,
        group_difference_mean_rmse=means,blocks=blocks,gates=gates,adopt_or_confirm=False,
        confirmation_opened=False,real_training_data=False,
        limitations="OR grid predictions scored but no coefficients were saved for OR arbitrary-query replay; nuisance coefficients/scalers not retained. LL frozen-xi replay and S loaded basis replay need no new fit.",
        source_sha256=receipt["source_sha256"],development_receipt_sha256=sha(STUDY/"development_receipt.json"))
    (HERE/"replay_verification.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in out.items() if k not in ("source_sha256","blocks")},ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
