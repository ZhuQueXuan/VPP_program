"""Independent standard-library audit of frozen arrays. Never imports a model."""
import csv
import hashlib
import json
import math
from pathlib import Path
from statistics import mean, median

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OLD = HERE.parent / "b1_ev_single_demo_20261104"


def load(p):
    return json.loads(p.read_text(encoding="utf-8"))


def mse(v):
    return mean(x*x for x in v)


def rms(v):
    return math.sqrt(mse(v))


def write_csv(name, rows):
    with (HERE / name).open("w", newline="", encoding="utf-8-sig") as fp:
        w = csv.DictWriter(fp, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def main():
    src = load(OLD / "confirmation.json")
    decision, selection, protocol = (load(OLD / p) for p in
                                     ("decision.json", "selection.json", "protocol.json"))
    names = ["incumbent", str(selection["alpha"])]
    assert names[1] == str(decision["selected_alpha"]) == "10.0"
    grid, rows = src["grid"], src["cohorts"]
    assert len(rows) == 24 and len(grid) == 17 and grid[0] == 0.4
    assert sorted({r["seed"] for r in rows}) == protocol["confirmation_seeds"]
    assert {r["mechanism"] for r in rows} == set(protocol["mechanisms"])
    inputs = [OLD / p for p in ("confirmation.json", "protocol.json", "decision.json",
                               "selection.json", "evaluate.py", "development.json")]
    inputs += [HERE.parent / d / "README.md" for d in (
        "b1_continuous_dml_pilot_20261103", "b1_curve_spline_pilot_20261103",
        "b1_curve_stability_20261103")]
    hashes = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in inputs}
    points, cohort = [], []
    for r in rows:
        assert r["events"] == 480 and r["users"] == 240
        out = {"seed": r["seed"], "mechanism": r["mechanism"], "events": r["events"],
               "users": r["users"], "low_events": r["group_counts"][1],
               "high_events": r["group_counts"][2]}
        for name in names:
            label = "dr" if name == "incumbent" else "or"
            curves, truth = r["scores"][name]["curves"], r["truth"]
            assert all(c is not None and len(c) == 17 for c in curves + truth)
            errs = [[a-b for a, b in zip(c, t)] for c, t in zip(curves, truth)]
            gaperr = [b-a for a, b in zip(errs[1], errs[2])]
            curve_rmse, gap_rmse = rms(errs[0]), rms(gaperr)
            assert math.isclose(curve_rmse, r["scores"][name]["curve_rmse"], abs_tol=1e-9)
            assert math.isclose(gap_rmse, r["scores"][name]["subgroup_rmse"], abs_tol=1e-9)
            assert all(abs(c[0]) < 1e-9 for c in curves + truth)
            w = r["group_counts"][1] / r["events"]
            consistency = [c-w*l-(1-w)*h for c,l,h in zip(*curves)]
            truth_consistency = [c-w*l-(1-w)*h for c,l,h in zip(*truth)]
            assert rms(truth_consistency) < 1e-9
            cov = mean(a*b for a,b in zip(errs[1], errs[2]))
            assert math.isclose(gap_rmse**2, mse(errs[1])+mse(errs[2])-2*cov, abs_tol=1e-7)
            out.update({
                label+"_contrast_rmse_s": curve_rmse,
                label+"_group_difference_rmse_s": gap_rmse,
                label+"_low_contrast_rmse_s": rms(errs[1]),
                label+"_high_contrast_rmse_s": rms(errs[2]),
                label+"_contrast_mean_error_s": mean(errs[0]),
                label+"_contrast_centered_mse_s2": mean((v-mean(errs[0]))**2 for v in errs[0]),
                label+"_group_error_crossmoment_s2": cov,
                label+"_group_mixture_discrepancy_rmse_s": rms(consistency),
                label+"_contrast_error_at_1_2_s": errs[0][8],
                label+"_contrast_error_at_2_s": errs[0][-1],
                label+"_last4_mse_fraction": sum(v*v for v in errs[0][-4:])/sum(v*v for v in errs[0]),
                label+"_first4_nonref_mse_fraction": sum(v*v for v in errs[0][1:5])/sum(v*v for v in errs[0])
            })
            assert math.isclose(mean(errs[0])**2+out[label+"_contrast_centered_mse_s2"],
                                curve_rmse**2, abs_tol=1e-7)
            for k, amount in enumerate(grid):
                points.append(dict(seed=r["seed"], mechanism=r["mechanism"], method=label,
                    amount=amount, truth_contrast=truth[0][k], estimate_contrast=curves[0][k],
                    error_s=errs[0][k], low_error_s=errs[1][k], high_error_s=errs[2][k],
                    group_difference_error_s=gaperr[k]))
        out["contrast_delta_s"] = out["or_contrast_rmse_s"]-out["dr_contrast_rmse_s"]
        out["group_difference_delta_s"] = out["or_group_difference_rmse_s"]-out["dr_group_difference_rmse_s"]
        cohort.append(out)
    def summarize(group):
        out = {"cohorts": len(group)}
        for target in ("contrast", "group_difference"):
            a, b = [mean(r[f"{m}_{target}_rmse_s"] for r in group) for m in ("dr","or")]
            out.update({target+"_dr_mean_rmse_s": a, target+"_or_mean_rmse_s": b,
                        target+"_delta_s": b-a, target+"_reduction_pct":100*(1-b/a),
                        target+"_winning_cohorts":sum(r[f"{target}_delta_s"]<0 for r in group)})
        return out
    blocks = [dict(seed=seed, **summarize([r for r in cohort if r["seed"]==seed]))
              for seed in protocol["confirmation_seeds"]]
    mechanisms = [dict(mechanism=k, **summarize([r for r in cohort if r["mechanism"]==k]))
                  for k in protocol["mechanisms"]]
    loo = [dict(omitted_seed=seed, **summarize([r for r in cohort if r["seed"]!=seed]))
           for seed in protocol["confirmation_seeds"]]
    total = summarize(cohort)
    total["contrast_winning_blocks"] = sum(b["contrast_delta_s"]<0 for b in blocks)
    total["group_difference_winning_blocks"] = sum(b["group_difference_delta_s"]<0 for b in blocks)
    total["contrast_block_delta_median_s"] = median(b["contrast_delta_s"] for b in blocks)
    total["contrast_cohort_delta_median_s"] = median(r["contrast_delta_s"] for r in cohort)
    total["contrast_mean_cohort_relative_reduction_pct"] = mean(
        100*(1-r["or_contrast_rmse_s"]/r["dr_contrast_rmse_s"]) for r in cohort)
    for key, target in (("curve_rmse","contrast"), ("subgroup_rmse","group_difference")):
        expected = src["comparisons"]["10.0"][key]
        assert expected["outputs"] == [24,24]
        assert math.isclose(total[target+"_dr_mean_rmse_s"], expected["paired_means"][0],abs_tol=1e-9)
        assert math.isclose(total[target+"_or_mean_rmse_s"], expected["paired_means"][1],abs_tol=1e-9)
        assert math.isclose(total[target+"_or_mean_rmse_s"]/total[target+"_dr_mean_rmse_s"],
                            decision["ratios"][key],abs_tol=1e-12)
    assert total["contrast_winning_blocks"]==2 and not decision["use_candidate"]
    write_csv("cohort_diagnosis.csv",cohort)
    write_csv("block_summary.csv",blocks)
    write_csv("mechanism_summary.csv",mechanisms)
    write_csv("leave_one_block.csv",loo)
    write_csv("point_errors.csv",points)
    conclusion = {
        "date":"2026-11-05", "old_confirmation_role":"consumed_diagnostic_only",
        "new_model_fits":0, "new_confirmatory_claim":False,
        "input_sha256":hashes, "summary":total, "blocks":blocks, "mechanisms":mechanisms,
        "leave_one_block":loo,
        "level_identifiability":{
            "absolute_level_saved":False, "reference_level_error_saved":False,
            "reason":"All 24 rows retain only contrasts theta(a)-theta(0.4). Adding arbitrary constants to saved model and truth levels leaves every retained contrast unchanged. No absolute-level RMSE, reference bias or nuisance/noise decomposition can be recovered from these arrays.",
            "error_decomposition":"mean contrast error squared plus centered contrast error MSE is descriptive only. It is not a decomposition into reference error versus shape error."
        },
        "comparison_limits":{
            "incumbent":"Overall and each slack group separately refit nuisances and local-linear DR.",
            "pooled_or":"One full-cohort outcome model standardized within each pre-offer group, no DR residual correction.",
            "attribution":"Sharing samples, outcome fit/regularization, removal of residual correction and smoothing all differ; saved errors do not isolate these causes."
        }
    }
    (HERE/"diagnosis.json").write_text(json.dumps(conclusion,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(total,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
