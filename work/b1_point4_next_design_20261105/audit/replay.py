"""Independent saved-state audit; never fits models or regenerates research draws."""
import csv
import hashlib
import json
from pathlib import Path
import sys
from statistics import mean
import numpy as np
from scipy.interpolate import BSpline
from scipy.special import logit
from scipy.stats import norm

HERE=Path(__file__).resolve().parent
STUDY=HERE.parent
ROOT=STUDY.parents[1]
GRID=np.array([.4+.1*i for i in range(17)])


def load(p):return json.loads(p.read_text(encoding="utf-8"))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def state(x):
    a,b,c=np.asarray(x).T
    return np.column_stack([np.ones(len(a)),a,b,c,a*a,a*b,a*c,b*b,b*c,c*c])
def design(x,b):return np.column_stack([x,b,(x[:,:,None]*b[:,None,:]).reshape(len(x),-1)])
def linear(reg,x):return np.asarray(x)@np.asarray(reg["coef"]).T+reg["intercept"]
def ll(d,xi,h,amounts):
    z=d[None,:]-np.asarray(amounts)[:,None]
    k=np.exp(-.5*(z/h)**2)
    v0=k.sum(1);v1=(k*z).sum(1);v2=(k*z*z).sum(1)
    return (v2*(k*xi).sum(1)-v1*(k*z*xi).sum(1))/(v0*v2-v1*v1)
def rms(a):return float(np.sqrt(np.mean(np.asarray(a)**2)))


def main():
    checks=0
    errors={}
    def ck(ok,label):
        nonlocal checks
        if not ok:raise AssertionError(label)
        checks+=1
    def close(a,b,tol,label):
        diff=float(np.max(abs(np.asarray(a)-np.asarray(b))))
        errors[label]=max(errors.get(label,0.),diff)
        ck(diff<=tol,label)
    plan=load(STUDY/"protocol.json")
    receipt=load(STUDY/"development_receipt.json")
    frozen=load(STUDY/"development/source_freeze.json")
    ck(frozen==receipt["source_sha256"],"freeze receipt")
    for name,value in frozen.items():ck(sha(ROOT/name)==value,name)
    ck(not (STUDY/"confirmation").exists(),"new confirmation unopened")
    ck(not (ROOT/"work/b1_point4_stability_design_20261105/confirmation").exists(),"old confirmation unopened")
    spec=plan["data"]["development"]
    expected={(s,k) for s in spec["seeds"] for k in spec["mechanisms"]}
    actual_files=list((STUDY/"development").glob("925*.json"))
    ck(len(actual_files)==24,"all 24 files")
    metrics=[];rows=[];queries=[];support_failures=[];ranks=[]
    gamma_modes={};ridge_fit_count=0
    for seed in spec["seeds"]:
        for kind in spec["mechanisms"]:
            value=load(STUDY/"development"/f"{seed}-{kind}.json")
            x=np.array(value["facts"]["X"]);a=np.array(value["facts"]["dose"])
            y=np.array(value["facts"]["outcome"]);u=np.array(value["facts"]["users"])
            ck(len(a)==480 and len(set(u))==240,"counts")
            ck(np.all((a>0)&(a<2.4)) and np.all((y>=0)&(y<=1800)),"declared range")
            masks=[np.ones(len(a),bool),x[:,0]<0,x[:,0]>=0]
            m=value["R_model"]
            ck(m is not None and m["rho"]==.05 and m["q_dimension"]==80,"fixed R")
            ck(m["absolute_level_available"] is False,"no fabricated candidate level")
            ranks.append(m["q_rank"])
            knots=np.array(m["dose_knots"])
            dose=lambda q:BSpline.design_matrix(np.asarray(q),knots,3,extrapolate=False).toarray()
            sx=state(x);b=dose(a);psi=(sx[:,:,None]*b[:,None,:]).reshape(len(a),80)
            folds=np.array(m["fold_by_event"])
            for user in set(u):ck(len(set(folds[u==user]))==1,"whole-user R folds")
            moof=np.empty(480);mom=np.empty((480,8));seen=[]
            for scope in m["auxiliary_models"]:
                ti=np.array(scope["train_event_index"]);vi=np.array(scope["test_event_index"])
                ck(not set(u[ti]).intersection(u[vi]),"cross-group user excluded")
                ck(set(ti)==set(np.flatnonzero(folds!=scope["fold"])) and
                   set(vi)==set(np.flatnonzero(folds==scope["fold"])),"exact scope")
                mu0=sx[ti,1:].mean(0);sd0=sx[ti,1:].std(0);sd0=np.where(sd0==0,1.,sd0)
                close(mu0,scope["scaler_mean"],1e-12,"R training-only scaler mean")
                close(sd0,scope["scaler_scale"],1e-12,"R training-only scaler scale")
                xv=(sx[vi,1:]-mu0)/sd0
                moof[vi]=xv@np.asarray(scope["m_coef"])+scope["m_intercept"]
                ck(np.shape(scope["m_coef"])==(9,),"m uses only X")
                mode=scope["gamma_mode"]
                gamma_modes[mode]=gamma_modes.get(mode,0)+1
                if kind=="randomized":
                    ck(mode=="known_uniform_integral" and scope["gamma_coef"] is None,"design knowledge only randomized")
                    mom[vi]=BSpline(knots,np.eye(8),3).integrate(0,2.4)/2.4
                else:
                    ck(mode=="train-only basis conditional regression" and scope["gamma_coef"] is not None,"observed Gamma estimated")
                    pred=xv@np.asarray(scope["gamma_coef"]).T+np.asarray(scope["gamma_intercept"])
                    mom[vi,:7]=pred;mom[vi,7]=1-pred.sum(1)
                seen.extend(vi.tolist())
            ck(sorted(seen)==list(range(480)),"OOF once per event")
            close(moof,m["m_oof"],1e-12,"loaded m OOF")
            close(mom,m["dose_moments_oof"],1e-12,"loaded moment OOF")
            gamma=(sx[:,:,None]*mom[:,None,:]).reshape(480,80)
            close(gamma,m["Gamma_oof"],1e-12,"Gamma tensor")
            close(mom.sum(1),np.ones(480),1e-12,"moment partition")
            z=psi-gamma;q=psi.T@psi/480;r=z.T@z/480;rhs=z.T@(y/1800-moof)/480
            close(q,m["function_Gram"],1e-12,"Q function penalty")
            close(r,m["residual_Gram"],1e-12,"R residual gram")
            close(rhs,m["right_hand_side"],1e-12,"right hand side")
            phi=np.array(m["phi"])
            close((r+.05*q)@phi,rhs,1e-9,"normal equation rhoQ")
            eig,vec=np.linalg.eigh((q+q.T)/2)
            close(eig,m["q_eigenvalues"],1e-12,"Q spectrum")
            ck(int((eig>eig[-1]*1e-10).sum())==m["q_rank"],"fixed rank cutoff")
            kept=np.array(m["q_kept_basis"])
            ck(m["q_relative_cutoff"]==1e-10 and m["null_query_tolerance"]==1e-8,"fixed numerical rule")
            # Rebuild all original B0 nuisance predictions from stored coefficients.
            for pop,p in enumerate(value["populations"]["B0"]):
                idx=np.array(p["event_index"])
                ck(np.array_equal(idx,np.flatnonzero(masks[pop])),"B0 same population")
                f=np.array(p["folds"]);ridge_fit_count+=p["actual_ridge_fits"]
                mu=np.empty(len(idx));mg=np.empty(len(idx));pdf=np.empty(len(idx));md=np.empty(len(idx))
                for scope in p["auxiliary_models"]:
                    ti=np.array(scope["train_event_index"]);vi=np.array(scope["test_event_index"])
                    ck(not set(u[ti]).intersection(u[vi]),"B0 user isolation")
                    scale=scope["scaler"];xt=(state(x[ti])[:,1:]-scale["mean"])/scale["scale"]
                    xv=(state(x[vi])[:,1:]-scale["mean"])/scale["scale"]
                    sp=scope["spline"];sb=BSpline(sp["t"],sp["c"],sp["k"],extrapolate=False)
                    bv=sb(a[vi])[:,:-1]
                    local=np.searchsorted(idx,vi)
                    mu[local]=linear(scope["outcome_model"],design(xv,bv))
                    mg[local]=linear(scope["outcome_model"],design(np.broadcast_to(xt.mean(0),xv.shape),bv))
                    if scope["known_uniform"]:
                        pdf[local]=md[local]=1/2.4
                    else:
                        inner=np.array(scope["density_inner_fold"]);res=np.empty(len(ti))
                        for k in (0,1):
                            res[inner==k]=logit(a[ti][inner==k]/2.4)-linear(scope["density_inner_models"][k],xt[inner==k])
                        sd=float(np.sqrt(np.mean(res**2)))
                        close(sd,scope["density_sd"],1e-12,"B0 loaded density scale")
                        cond_mean=linear(scope["density_final_model"],xv)
                        train_mean=linear(scope["density_final_model"],xt)
                        prop=a[vi]/2.4
                        pdf[local]=norm.pdf(logit(prop),cond_mean,sd)/(2.4*prop*(1-prop))
                        md[local]=norm.pdf(logit(prop[:,None]),train_mean[None,:],sd).mean(1)/(2.4*prop*(1-prop))
                close(mu,p["mu_observed"],1e-9,"B0 loaded outcome predictions")
                close(mg,p["marginal_mu"],1e-9,"B0 independently loaded marginal outcomes")
                close(pdf,p["conditional_density"],1e-12,"B0 loaded conditional density")
                close(md,p["marginal_density"],1e-12,"B0 independently loaded marginal density")
                xi=(y[idx]-mu)*md/pdf+mg
                close(xi,p["xi"],1e-8,"B0 loaded DR values")
                ck(np.isfinite(xi).all(),"finite B0")
                h=p["bandwidth"]
                weights=np.array(p["weights"])
                for amount,st in zip(GRID,p["support"]):
                    kern=np.exp(-.5*((a[idx]-amount)/h)**2)*weights
                    local=abs(a[idx]-amount)<=h
                    ess=kern.sum()**2/(kern@kern)
                    smd=float(np.max(abs(np.average(x[idx],axis=0,weights=kern)-x[idx].mean(0))/
                                      np.maximum(x[idx].std(0),1e-8)))
                    n,g=int(local.sum()),len(set(u[idx][local]))
                    close([ess,smd],[st["effective_events"],st["max_weighted_smd"]],1e-9,"support replay")
                    ck(n==st["local_events"] and g==st["local_users"],"support counts")
                    bad=[]
                    if n<25:bad.append("local_events")
                    if g<15:bad.append("local_users")
                    if ess<20:bad.append("ESS")
                    if smd>.5:bad.append("weighted_SMD")
                    if bad:support_failures.append(dict(seed=seed,mechanism=kind,population=pop,amount=amount,
                        reason="+".join(bad),events=n,users=g,ess=ess,smd=smd))
                if p["status"]=="ok":
                    close(ll(a[idx],np.array(p["xi"]),h,GRID),p["level"],1e-9,"B0 LL replay")
            # Rebuild the fixed OR using the complete saved state.
            ormod=value["OR_model"]
            ridge_fit_count+=1
            sp=ormod["spline"];sb=BSpline(sp["t"],sp["c"],sp["k"],extrapolate=False)
            for method,pops in value["populations"].items():
                sc=dict(full_group_output=all(p["status"]=="ok" for p in pops[1:]))
                deltas=[]
                for pop,(p,mask,t) in enumerate(zip(pops,masks,value["truth_levels"])):
                    if p["status"]!="ok":
                        deltas.append(None);continue
                    delta=np.array(p["contrast"]);truth=np.array(t);td=truth-truth[0]
                    if method=="OR10":
                        xs=(state(x[mask])[:,1:]-ormod["scaler_mean"])/ormod["scaler_scale"]
                        bs=sb(GRID)[:,:-1]
                        level=design(np.broadcast_to(xs.mean(0),(17,9)),bs)@ormod["coef"]+ormod["intercept"]
                        close(level,p["level"],1e-9,"loaded OR10 query")
                    elif method=="S":
                        st=p["spline_state"]
                        level=BSpline(st["knots"],st["coefficients"],st["degree"])(GRID/st["x_scale"])*st["y_scale"]
                        close(level,p["level"],1e-9,"loaded S query")
                    elif method=="R" and pop>0:
                        allv=(state(x[mask])[:,None,:,None]*(dose(GRID)[None,:,None,:]-dose([.4])[None,None,0,None,:])).reshape(mask.sum(),17,80)
                        projection=(allv@kept)@kept.T
                        ck(np.max(np.linalg.norm(allv-projection,axis=2)/(1+np.linalg.norm(allv,axis=2)))<=1e-8,"identifiable requested contrasts")
                        own=1.05*(allv@phi).mean(0)*1800
                        close(own,delta,1e-8,"loaded R query")
                        ck(np.array_equal(delta[:1],[0.]),"exact R reference")
                        ck(p["level"] is None,"R level absent")
                        for amount in (.4,.73,1.17,1.2,2.):
                            v=(state(x[mask])[:,:,None]*(dose([amount])[0]-dose([.4])[0])[None,None,:]).reshape(mask.sum(),80)
                            pred=float(1800*1.05*np.mean(v@phi))
                            queries.append(dict(seed=seed,mechanism=kind,group=pop,amount=amount,increment_seconds=pred))
                    elif method=="R":
                        ck(p==value["populations"]["B0"][0],"overall retained")
                    close(rms(delta-td),value["score"]["scores"][method][f"increment_rmse_{pop}"],1e-8,"increment score")
                    deltas.append(delta)
                sc["group_difference_rmse"]=None
                if sc["full_group_output"]:
                    true=np.array(value["truth_levels"])
                    dif=(deltas[2]-deltas[1])-((true[2]-true[2,0])-(true[1]-true[1,0]))
                    sc["group_difference_rmse"]=rms(dif)
                    close(sc["group_difference_rmse"],value["score"]["scores"][method]["group_difference_rmse"],1e-8,"group score")
                for pop in (1,2):
                    if deltas[pop] is not None:sc[f"increment_rmse_{pop}"]=value["score"]["scores"][method][f"increment_rmse_{pop}"]
                metrics.append(dict(seed=seed,mechanism=kind,method=method,
                    full_group_output=sc["full_group_output"],group_difference_rmse=sc["group_difference_rmse"]))
            rows.append(value["score"])
    # Separate gate reconstruction; all unavailable rows remain in the denominator.
    ck({(r["seed"],r["mechanism"]) for r in rows}==expected and len(rows)==24,"exact cohort set")
    comp={};gate=dict(exact_cohort_set=True,common_output=all(sum(
        r["scores"][m]["full_group_output"] for r in rows)==24 for m in ("B0","OR10","R")),
        zero_reference=all(r["reference_exact_zero"] for r in rows),
        overall_unchanged=all(r["overall_equals_B0"] for r in rows))
    for ref in ("B0","OR10"):
        paired=[r for r in rows if all(r["scores"][m]["full_group_output"] for m in ("R",ref))]
        base=mean(r["scores"][ref]["group_difference_rmse"] for r in paired)
        cand=mean(r["scores"]["R"]["group_difference_rmse"] for r in paired)
        gate["gain_"+ref]=cand<=.95*base
        gate["mechanisms_"+ref]=all(len(sub:=[r for r in paired if r["mechanism"]==kind])==6 and
            mean(r["scores"]["R"]["group_difference_rmse"] for r in sub)<=
            mean(r["scores"][ref]["group_difference_rmse"] for r in sub) for kind in spec["mechanisms"])
        gate["single_group_noninferior_"+ref]=len(paired)==24 and all(
            mean(r["scores"]["R"][f"increment_rmse_{g}"] for r in paired)<=
            mean(r["scores"][ref][f"increment_rmse_{g}"] for r in paired)+2 for g in (1,2))
        blocks=[]
        for seed in spec["seeds"]:
            sub=[r for r in paired if r["seed"]==seed]
            blocks.append(dict(seed=seed,delta=mean(r["scores"]["R"]["group_difference_rmse"]-
                r["scores"][ref]["group_difference_rmse"] for r in sub) if len(sub)==4 else None))
        comp[ref]=dict(paired=len(paired),baseline=base,candidate=cand,blocks=blocks)
    wins=sum(all(comp[m]["blocks"][i]["delta"] is not None and comp[m]["blocks"][i]["delta"]<0
                 for m in ("B0","OR10")) for i in range(6))
    gate["joint_seed_wins"]=wins>=4
    ck(gate==receipt["decision"]["gates"],"all independent gates")
    ck(wins==receipt["decision"]["joint_winning_blocks"]==0,"joint winners")
    ck(not all(gate.values()) and receipt["decision"]["pass_all"] is False,"stop development")
    for name,values in (("cohort_metrics.csv",metrics),("support_failures.csv",support_failures),
                        ("loaded_queries.csv",queries)):
        with (HERE/name).open("w",encoding="utf-8-sig",newline="") as fp:
            w=csv.DictWriter(fp,fieldnames=list(values[0]));w.writeheader();w.writerows(values)
    out=dict(passed=True,checks=checks,new_audit_model_fits=0,actual_training_cohorts=24,
        independent_seed_blocks=6,gates=gate,comparisons=comp,joint_winning_blocks=wins,
        errors=errors,R_ranks=ranks,Gamma_modes=gamma_modes,explicit_B0_OR_ridge_fits=ridge_fit_count,
        R_auxiliary_ridge_fits=6*3+18*6,R_surface_solves=24,
        loaded_query_count=len(queries),support_failures=support_failures,confirmation_opened=False,
        stage_process_exit_code=1,
        process_note="All 24 fits, source checks and receipt saves completed; only final console json.dumps(np.bool_) failed. No rerun or source modification.",
        source_sha256=frozen,
        development_receipt_sha256=sha(STUDY/"development_receipt.json"))
    (HERE/"replay_verification.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"{checks} independent saved-state checks passed; common outputs 18/24; joint wins 0/6; zero audit fits.")


if __name__=="__main__":main()
