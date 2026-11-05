"""Read-only diagnosis of the already-seen final EV panel; no fit or threshold search.

Native CPOP input.csv stores y=Bhat-P and is bound to each saved output by
backend.artifact_dir and case_id. Truth is evaluator-only. The script never calls
an event/process/reference fitter and writes only to its own diagnosis directory.
"""
from pathlib import Path
import hashlib
import itertools
import json
import math
import sys

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OLD = ROOT / "work/b1_finish_ev_20261030/final_chain"
FACTS = ROOT / "data/B1_finish_chain_v1_20261030"
METHODS = ("ride_revised", "cpop", "ride_template")


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)


def longest(mask):
    best = run = 0
    for yes in mask:
        run = run + 1 if yes else 0
        best = max(best, run)
    return best


def moments(values):
    x = np.asarray(values, dtype=float).ravel()
    if not x.size:
        return {"n": 0}
    return dict(n=int(x.size), mean=float(x.mean()), rms=float(np.sqrt(np.mean(x*x))),
                sd_population=float(x.std()), min=float(x.min()), max=float(x.max()),
                quantiles={str(p):float(np.quantile(x,p)) for p in (.01,.05,.25,.5,.75,.95,.99)})


def corr(a, b):
    a = np.asarray(a, float); b = np.asarray(b, float)
    if len(a)<2 or a.std()==0 or b.std()==0:
        return None
    return float(np.corrcoef(a,b)[0,1])


def lag_correlation(x):
    # Pool within-event centered neighboring bins. Common event offsets are
    # removed here and separately measured as between-event mean bias.
    x = np.asarray(x, float)
    centered = x-x.mean(axis=1,keepdims=True)
    return corr(centered[:,:-1].ravel(),centered[:,1:].ravel())


def group_metrics(frame, keys):
    out=[]
    for key,group in frame.groupby(keys, observed=True, dropna=False):
        key=(key,) if not isinstance(key,tuple) else key
        row={name:(str(value) if not isinstance(value,(str,int,float)) else value) for name,value in zip(keys,key)}
        no=group[group.no_action==1]
        row.update(variants=int(len(group)),no_action=int(len(no)),responses=int(group.response.sum()),
                   reference_task_bias_mean_kw=float(group.reference_task_bias_mean_kw.mean()),
                   no_action_reference_task_bias_mean_kw=None if not len(no) else float(no.reference_task_bias_mean_kw.mean()),
                   no_action_reference_task_rmse_kw=None if not len(no) else float(no.reference_task_rmse_kw.mean()),
                   no_action_raw_detection_count=int(no.raw_detection.sum()),
                   no_action_raw_detection_rate=None if not len(no) else float(no.raw_detection.mean()))
        for method in METHODS:
            row[method+"_false_detection"]=int(no[method+"_detection"].sum())
            row[method+"_false_detection_rate"]=None if not len(no) else float(no[method+"_detection"].mean())
            row[method+"_miss"]=int(((group.response==1)&(group[method+"_detection"]==0)).sum())
        out.append(row)
    return out


def main():
    if len(sys.argv)>1:
        raise SystemExit("No tuning options are supported; rerun in a new directory with a copied script.")
    protocol=read(HERE.parent/"protocol.json")
    seeds=protocol["factor_diagnosis"]["blocks"]
    old_manifest=read(OLD/"scientific_files_final_sha256.json")
    used={HERE.parent/"protocol.json",HERE.parent/"source_freeze.json",OLD/"process.json",OLD/"assessment.json",
          OLD/"scientific_files_final_sha256.json",ROOT/"work/b1_ev_mainline_20261030/simulation.py",
          ROOT/"B1算法/b1_algorithm/api.py",ROOT/"B1算法/b1_algorithm/reference/ev_selection.py",
          ROOT/"B1算法/b1_algorithm/process/batch.py"}
    for seed in seeds:
        used.add(OLD/f"references/{seed}.json")
        for scenario in ("positive","zero"):
            used.update((FACTS/f"{seed}_{scenario}_facts.json",OLD/f"evaluator/{seed}_{scenario}_truth.json",
                         OLD/f"factor_inputs/{seed}_{scenario}.json"))
            for method in METHODS:
                used.add(OLD/f"events/{seed}_{scenario}_{method}.json")
            events=read(OLD/f"events/{seed}_{scenario}_cpop.json")
            native=Path(events[0]["process"]["backend"]["artifact_dir"])/"input.csv"
            if not native.resolve().is_relative_to(OLD.resolve()):
                raise AssertionError("native input path outside saved final panel")
            used.add(native)
    before={p.relative_to(ROOT).as_posix():sha(p) for p in sorted(used)}
    historical_manifest_matches={k:(old_manifest[k]==v) for k,v in before.items() if k in old_manifest}
    assert all(historical_manifest_matches.values())
    assert not (HERE/"summary.json").exists(),"Preserve previous outputs; use a fresh diagnosis directory"
    process={(r["seed"],r["scenario"],r["method"],r["task_id"]):r for r in read(OLD/"process.json")}
    rows=[]; task_bias=[];task_noise=[];task_raw=[]; pre_bias=[];post_bias=[]
    checks={"event_identity":0,"native_raw_eta":0,"raw_duration":0,"selected_duration":0,
            "saved_process_score":0,"paired_reference":0,"true_no_action_is_zero_curve":0,
            "pointwise_observation_identity":0,"reference_method":0}
    maxima={"native_eta_difference":0.,"pointwise_identity_difference":0.,"paired_reference_difference":0.}
    for seed in seeds:
        selections={s["task_id"]:s for s in read(OLD/f"references/{seed}.json")}
        previous={}
        for scenario in ("positive","zero"):
            facts=read(FACTS/f"{seed}_{scenario}_facts.json")
            truth=read(OLD/f"evaluator/{seed}_{scenario}_truth.json")
            indices=read(OLD/f"factor_inputs/{seed}_{scenario}.json")["target_indices"]
            outputs={method:read(OLD/f"events/{seed}_{scenario}_{method}.json") for method in METHODS}
            assert len(indices)==256 and all(len(o)==256 for o in outputs.values())
            native=Path(outputs["cpop"][0]["process"]["backend"]["artifact_dir"])/"input.csv"
            native_frame=pd.read_csv(native,float_precision="round_trip")
            assert list(native_frame.columns)==["case_id","x","y","sigma","train"]
            assert native_frame.case_id.nunique()==256
            for local_index,index in enumerate(indices):
                f=facts[index]; t=truth[index]; tid=t["task_id"]
                events={method:outputs[method][local_index] for method in METHODS}
                assert all(e["task"]["task_id"]==tid and e["status"]=="ok" for e in events.values())
                assert tid==f["task"]["task_id"] and t["user_id"]==f["task"]["user_id"]
                checks["event_identity"]+=1
                # batch.py uses base=i*10 so guarded CV IDs remain distinct.
                case=native_frame[native_frame.case_id==local_index*10]
                s=np.asarray(t["relative_starts_min"],float); use=(s>=0)&(s<t["W_min"])
                pre=s<0; post=s>=t["W_min"]
                assert np.array_equal(case.x.to_numpy(),s+.5) and len(case)==60 and use.sum()==30
                raw=case.y.to_numpy(); p=np.asarray(f["power_kw"],float)
                b=p+raw; bt=np.asarray(t["true_reference_kw"],float)
                true_r=np.asarray(t["true_reduction_kw"],float); eps=np.asarray(t["measurement_error_kw"],float)
                bias=b-bt; residual=raw-true_r
                pointdiff=float(np.max(np.abs(raw-(true_r+bias-eps))))
                assert pointdiff<3e-15
                maxima["pointwise_identity_difference"]=max(maxima["pointwise_identity_difference"],pointdiff)
                checks["pointwise_observation_identity"]+=1
                raw_eta=float(raw[use].sum()/(t["q_kw"]*t["W_min"]))
                etadiff=max(abs(e["outcome"]["value"]-raw_eta) for e in events.values())
                assert etadiff<1e-12
                checks["native_raw_eta"]+=1;maxima["native_eta_difference"]=max(maxima["native_eta_difference"],etadiff)
                threshold=.1*t["q_kw"]; rawmask=raw[use]>=threshold
                no_action=t["cumulative_response_seconds"]==0
                if no_action:
                    assert np.all(true_r==0)
                    checks["true_no_action_is_zero_curve"]+=1
                selection=selections[tid]
                assert all(e["reference"]["method"]==selection["method"] for e in events.values())
                checks["reference_method"]+=1
                row=dict(seed=seed,scenario=scenario,task_id=tid,user_id=t["user_id"],
                    event_index=int(tid.rsplit("-",1)[1]),shape=t["latent"]["shape"],
                    dose=f["offered_incentive"],L=f["deadline_slack"],U=f["demand_urgency"],
                    reference_method=selection["method"],history_validation_events=selection["validation_events"],
                    historical_gbdt_mae_kw=selection["mean_history_task_mae_kw"]["gbdt"],
                    historical_prev10_mae_kw=selection["mean_history_task_mae_kw"]["prev10"],
                    no_action=int(no_action),response=int(not no_action),observed_participation=int(f["observed_participation"]),
                    true_duration_seconds=t["cumulative_response_seconds"],threshold_kw=threshold,
                    meter_sigma_kw=f["noise_sigma_kw"],reference_task_bias_mean_kw=float(bias[use].mean()),
                    reference_task_rmse_kw=float(np.sqrt(np.mean(bias[use]**2))),
                    reference_task_bias_sd_kw=float(bias[use].std()),reference_task_bias_min_kw=float(bias[use].min()),
                    reference_task_bias_max_kw=float(bias[use].max()),reference_pre_task_bias_mean_kw=float(bias[pre].mean()),
                    reference_post_task_bias_mean_kw=float(bias[post].mean()),
                    reference_task_minus_pre_bias_kw=float(bias[use].mean()-bias[pre].mean()),
                    reference_post_minus_pre_bias_kw=float(bias[post].mean()-bias[pre].mean()),
                    meter_noise_task_mean_kw=float(eps[use].mean()),meter_noise_task_rms_kw=float(np.sqrt(np.mean(eps[use]**2))),
                    raw_residual_task_mean_kw=float(residual[use].mean()),raw_residual_task_rmse_kw=float(np.sqrt(np.mean(residual[use]**2))),
                    raw_task_max_kw=float(raw[use].max()),raw_duration_seconds=int(rawmask.sum())*60,
                    raw_longest_seconds=longest(rawmask)*60,raw_detection=int(rawmask.any()),
                    reference_bias_only_above_threshold_bins=int((bias[use]>=threshold).sum()),
                    raw_above_threshold_with_bias_below_threshold_bins=int((rawmask&(bias[use]<threshold)).sum()),
                    reference_bias_above_threshold_removed_by_noise_bins=int(((bias[use]>=threshold)&~rawmask).sum()),
                    noise_only_above_threshold_bins=int((-eps[use]>=threshold).sum()),
                    native_input_relative_path=native.relative_to(ROOT).as_posix(),native_case_id=local_index*10)
                # This is observable before notice: historical average minus the
                # observed [-75,-15) prefix. It is not the selected Bhat error.
                prefix_prior=np.mean([np.asarray(h["power_kw"],float)[:60] for h in f["historical_non_event"]],axis=0)
                prefix_meter=np.asarray(f["reference_window"]["pre_power_kw"],float)
                row["pre_notice_history_prior_minus_meter_mean_kw"]=float(np.mean(prefix_prior-prefix_meter))
                for method,e in events.items():
                    fit=np.asarray(e["process"]["reduction_interval_kw"],float)
                    duration=int((fit[use]>=threshold).sum())*60
                    saved=e["process"]["features"]["selected_curve"]["cumulative_response_seconds"]
                    assert duration==saved
                    checks["selected_duration"]+=1
                    saved_raw=e["process"]["features"]["raw_observed"]["cumulative_response_seconds"]
                    assert saved_raw==row["raw_duration_seconds"]
                    checks["raw_duration"]+=1
                    score=process[(seed,scenario,method,tid)]
                    assert score["duration"]==duration and score["no_action"]==int(no_action)
                    assert score["false_detection"]==int(no_action and duration>0)
                    checks["saved_process_score"]+=1
                    row[method+"_duration_seconds"]=duration
                    row[method+"_detection"]=int(duration>0)
                    row[method+"_max_kw"]=float(fit[use].max())
                    row[method+"_curve_rmse_kw"]=float(np.sqrt(np.mean((fit[use]-true_r[use])**2)))
                row["common_all_three_detection"]=int(all(row[m+"_detection"] for m in METHODS))
                row["common_revised_cpop_detection"]=int(row["ride_revised_detection"] and row["cpop_detection"])
                row["reference_bias_group"]=("below_minus_threshold" if row["reference_task_bias_mean_kw"]<-threshold else
                    "minus_threshold_to_zero" if row["reference_task_bias_mean_kw"]<0 else
                    "zero_to_threshold" if row["reference_task_bias_mean_kw"]<threshold else "at_or_above_threshold")
                if scenario=="positive":previous[tid]=b
                else:
                    d=float(np.max(np.abs(previous[tid]-b)))
                    assert d<2e-15
                    maxima["paired_reference_difference"]=max(maxima["paired_reference_difference"],d)
                    checks["paired_reference"]+=1
                rows.append(row);task_bias.append(bias[use]);task_noise.append(eps[use]);task_raw.append(raw[use]);pre_bias.append(bias[pre]);post_bias.append(bias[post])
            print("joined",seed,scenario,len(indices),flush=True)
    df=pd.DataFrame(rows)
    assert len(df)==4096 and int(df.no_action.sum())==1778 and int(df.response.sum())==2318
    df["dose_group"]=pd.cut(df.dose,[0.,.8,1.6,2.4],right=False,include_lowest=True).astype(str)
    df["L_group"]=np.where(df.L<0,"L<0","L>=0")
    df["U_group"]=np.where(df.U<0,"U<0","U>=0")
    df["pre_notice_prior_bias_sign"]=np.where(df.pre_notice_history_prior_minus_meter_mean_kw<0,"negative","nonnegative")
    no=df[df.no_action==1];yes=df[df.response==1]
    overlap=[]
    for a,b in itertools.combinations(METHODS,2):
        aa=no[a+"_detection"].astype(bool);bb=no[b+"_detection"].astype(bool)
        intersection=int((aa&bb).sum());union=int((aa|bb).sum())
        overlap.append(dict(method_a=a,method_b=b,intersection=intersection,union=union,
                            a_only=int((aa&~bb).sum()),b_only=int((bb&~aa).sum()),jaccard=intersection/union))
    diagnostic=[]
    for name,group in [("all_no_action",no),("all_response",yes),
                       ("common_revised_cpop_false_detection",no[no.common_revised_cpop_detection==1]),
                       ("common_all_three_false_detection",no[no.common_all_three_detection==1]),
                       ("no_method_detected",no[no[[m+"_detection" for m in METHODS]].sum(axis=1)==0])]:
        ix=group.index.to_numpy()
        diagnostic.append(dict(group=name,variants=int(len(group)),
            task_reference_bias_bin_kw=moments(np.asarray(task_bias)[ix]),
            task_meter_noise_bin_kw=moments(np.asarray(task_noise)[ix]),
            task_raw_bin_kw=moments(np.asarray(task_raw)[ix]),
            task_reference_bias_event_mean_kw=moments(group.reference_task_bias_mean_kw),
            raw_threshold_bins=moments(group.raw_duration_seconds/60),
            raw_longest_bins=moments(group.raw_longest_seconds/60),
            task_reference_bias_within_event_lag1=lag_correlation(np.asarray(task_bias)[ix]),
            task_meter_noise_within_event_lag1=lag_correlation(np.asarray(task_noise)[ix]),
            task_raw_within_event_lag1=lag_correlation(np.asarray(task_raw)[ix]),
            pre_task_bias_mean_kw=moments(group.reference_pre_task_bias_mean_kw),
            post_task_bias_mean_kw=moments(group.reference_post_task_bias_mean_kw),
            task_minus_pre_bias_kw=moments(group.reference_task_minus_pre_bias_kw),
            post_minus_pre_bias_kw=moments(group.reference_post_minus_pre_bias_kw),
            pre_notice_prior_mismatch_mean_kw=moments(group.pre_notice_history_prior_minus_meter_mean_kw),
            reference_bias_event_mean_ge_threshold=int((group.reference_task_bias_mean_kw>=.15).sum()),
            reference_bias_only_any_bin_ge_threshold=int((group.reference_bias_only_above_threshold_bins>0).sum()),
            raw_any_bin_ge_threshold=int(group.raw_detection.sum()),
            raw_persistent_ge2_bins=int((group.raw_longest_seconds>=120).sum()),
            raw_persistent_ge5_bins=int((group.raw_longest_seconds>=300).sum()),
            reference_bias_only_above_threshold_bins=int(group.reference_bias_only_above_threshold_bins.sum()),
            raw_above_threshold_with_bias_below_threshold_bins=int(group.raw_above_threshold_with_bias_below_threshold_bins.sum()),
            noise_only_threshold_bins=int(group.noise_only_above_threshold_bins.sum())))
    transitions=[]
    for method in METHODS:
        detected=no[method+"_detection"]==1;raw=no.raw_detection==1
        transitions.append(dict(method=method,false_detection=int(detected.sum()),denominator=len(no),rate=float(detected.mean()),
            raw_and_fit=int((raw&detected).sum()),raw_only=int((raw&~detected).sum()),fit_only=int((~raw&detected).sum()),
            neither=int((~raw&~detected).sum()),miss=int(((df.response==1)&(df[method+"_detection"]==0)).sum()),
            no_action_fit_duration_seconds=moments(no.loc[detected,method+"_duration_seconds"]),
            no_action_fitted_minus_raw_duration_seconds=moments(no[method+"_duration_seconds"]-no.raw_duration_seconds)))
    groups={"scenario":group_metrics(df,["scenario"]),"block":group_metrics(df,["seed"]),
            "reference_method":group_metrics(df,["reference_method"]),
            "reference_method_scenario":group_metrics(df,["reference_method","scenario"]),
            "shape":group_metrics(df,["shape"]),"dose_group":group_metrics(df,["dose_group"]),
            "L_group":group_metrics(df,["L_group"]),"U_group":group_metrics(df,["U_group"]),
            "L_U":group_metrics(df,["L_group","U_group"]),
            "reference_bias_group":group_metrics(df,["reference_bias_group"]),
            "pre_notice_prior_bias_sign":group_metrics(df,["pre_notice_prior_bias_sign"])}
    summary=dict(schema="b1.existing-panel.false-detection-diagnosis.v1",data_status="Already-seen paired simulation panel; no new independent test",
        definitions=dict(no_action="True cumulative duration is zero; all60 true reduction bins exactly zero in these1778 variants",
            zero_scenario="Dose intervention does not change response distribution; participation and actual response may remain nonzero",
            false_detection="True no-action and any of30 selected fitted task bins >=0.1q=0.15kW; cumulative duration>0",
            calibration="No5% event-level hypothesis-test calibration is encoded in this definition; not a causal I-type error or eta>.1 test",
            identity="P=Btrue-Rtrue+epsilon; raw=Bhat-P=Rtrue+(Bhat-Btrue)-epsilon",
            pre_task="[-15,0)min, after notice at-15min; not all available at assignment",
            pre_notice="[-75,-15)min observed input prefix; historical-prior-minus-meter is available before notice but is not selected Bhat error"),
        counts=dict(target_variants=len(df),no_action=len(no),response=len(yes),base_target_events=2048,
            no_action_false_detection_all_three=int(no.common_all_three_detection.sum()),
            no_action_any_method_detected=int((no[[m+"_detection" for m in METHODS]].sum(axis=1)>0).sum()),
            zero_scenario_actual_response=int(((df.scenario=="zero")&(df.response==1)).sum()),
            positive_scenario_no_action=int(((df.scenario=="positive")&(df.no_action==1)).sum())),
        method_detection=transitions,pairwise_false_detection_overlap=overlap,diagnostic_distributions=diagnostic,
        descriptive_groups=groups,
        correlations_no_action=dict(reference_task_bias_vs_pre_task_bias=corr(no.reference_task_bias_mean_kw,no.reference_pre_task_bias_mean_kw),
            reference_task_bias_vs_post_task_bias=corr(no.reference_task_bias_mean_kw,no.reference_post_task_bias_mean_kw),
            reference_task_bias_vs_pre_notice_prior_mismatch=corr(no.reference_task_bias_mean_kw,no.pre_notice_history_prior_minus_meter_mean_kw),
            reference_task_bias_vs_dose=corr(no.reference_task_bias_mean_kw,no.dose),
            reference_task_bias_vs_L=corr(no.reference_task_bias_mean_kw,no.L),
            reference_task_bias_vs_U=corr(no.reference_task_bias_mean_kw,no.U)),
        noise_bound=dict(generator_kind="independent bounded Uniform(-sqrt(3)*sigma,+sqrt(3)*sigma)",
            declared_sigma_kw=.05,absolute_bound_kw=math.sqrt(3)*.05,threshold_kw=.15,
            implication="With a true reference, raw no-action noise alone cannot cross0.15kW in this generator; fitted-process behavior needs separate oracle probe"),
        checks=checks,max_absolute_arithmetic_differences=maxima,
        interpretation_limits=["Reference-method and condition groups contain different selected cases; their rates are descriptive, not causal method effects.",
            "Paired scenarios and repeated users share reference/noise;4096variants and1778no-action rows are not4096or1778 independent trials.",
            "Bias/noise arithmetic and saved-fit overlap do not partition fitted false detections into causal percentages.",
            "No process/reference fit, threshold scan, calibration, correction or candidate/default selection was performed.",
            "The pre-notice observable mismatch suggests an investigation opportunity; this panel cannot authorize a correction selected for its scores."])
    df.to_csv(HERE/"event_join.csv",index=False,encoding="utf-8-sig")
    dump(HERE/"summary.json",summary)
    for name,values in groups.items():
        pd.DataFrame(values).to_csv(HERE/f"group_{name}.csv",index=False,encoding="utf-8-sig")
    after={p.relative_to(ROOT).as_posix():sha(p) for p in sorted(used)}
    assert before==after
    central=read(HERE.parent/"source_freeze.json")
    central_matches={k:sha(ROOT/k)==v for k,v in central.items()}
    assert all(central_matches.values())
    receipt=dict(schema="b1.detection-diagnosis.receipt.v1",script_sha256=sha(Path(__file__)),
        protocol_sha256=sha(HERE.parent/"protocol.json"),old_inputs_used=len(before),old_inputs_unchanged=before==after,
        historical_manifest_compared=len(historical_manifest_matches),historical_manifest_all_match=True,
        central_source_freeze_compared=len(central_matches),central_source_freeze_all_match=True,
        no_source_or_old_artifact_write=True,no_fitting=True,no_threshold_search=True,
        inputs_sha256=before,outputs_sha256={p.name:sha(p) for p in sorted(HERE.iterdir()) if p.is_file() and p.name!="receipt.json"},
        checks=checks,max_absolute_arithmetic_differences=maxima)
    dump(HERE/"receipt.json",receipt)
    print(json.dumps({k:summary[k] for k in ("counts","method_detection","pairwise_false_detection_overlap","correlations_no_action")},ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
