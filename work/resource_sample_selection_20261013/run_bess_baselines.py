"""Run the frozen retrospective B0/B1 conversion comparison; no test refit."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import re
import sys

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent
PROJECT = BASE.parent.parent


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def fit_parameters(samples, config, units):
    fit = samples.loc[samples.test_id.eq(config["fit_test_id"]) & samples.partition.eq("fit")]
    parameters, failures = [], []
    for unit in units:
        for direction in ["charge", "discharge"]:
            cell = fit.loc[fit.unit_id.eq(unit) & fit.direction.eq(direction)]
            row = {"unit_id": unit, "direction": direction, "fit_test_id": config["fit_test_id"],
                   "fit_window_count": len(cell), "status": "ok", "eta": None}
            if len(cell) < config["minimum_fit_windows_per_unit_direction"]:
                row["status"] = "insufficient_fit_windows"
            else:
                ac_sum = float(cell.ac_mean_kw.sum())
                dc_sum = float(cell.dc_reference_mean_kw.sum())
                denominator = ac_sum if direction == "charge" else dc_sum
                eta = (dc_sum if direction == "charge" else ac_sum) / denominator if denominator else float("nan")
                row.update({"ac_mean_sum_kw": ac_sum, "dc_mean_sum_kw": dc_sum,
                            "fit_min_abs_ac_kw": float(cell.ac_mean_kw.abs().min()),
                            "fit_max_abs_ac_kw": float(cell.ac_mean_kw.abs().max())})
                if not np.isfinite(eta) or not 0 < eta <= 1:
                    row["status"] = "invalid_efficiency_no_clipping"
                    row["invalid_eta_description"] = str(eta)
                else:
                    row["eta"] = float(eta)
            parameters.append(row)
            if row["status"] != "ok":
                failures.append(row.copy())
    return parameters, failures


def predict(inputs, parameters):
    # Passing references or diagnostics here is an error, not a silent extra feature.
    require(list(inputs.columns) == ["unit_id", "direction", "ac_mean_kw"], "Prediction input whitelist violated")
    lookup = {(x["unit_id"], x["direction"]): x for x in parameters}
    b0, b1, statuses, outside_support = [], [], [], []
    for row in inputs.itertuples(index=False):
        b0.append(float(row.ac_mean_kw))
        parameter = lookup[(row.unit_id, row.direction)]
        statuses.append(parameter["status"])
        if parameter["status"] != "ok":
            b1.append(float("nan")); outside_support.append(None)
        else:
            eta = parameter["eta"]
            b1.append(row.ac_mean_kw * eta if row.direction == "charge" else row.ac_mean_kw / eta)
            outside_support.append(not parameter["fit_min_abs_ac_kw"] <= abs(row.ac_mean_kw) <= parameter["fit_max_abs_ac_kw"])
    return np.asarray(b0), np.asarray(b1), statuses, outside_support


def contract_checks(config):
    fixture = pd.DataFrame({"test_id": ["test_1", "test_1", "test_1", "test_1", "test_2"],
                            "partition": ["fit", "fit", "fit", "fit", "evaluation"],
                            "unit_id": ["lmo1"] * 5,
                            "direction": ["charge", "charge", "discharge", "discharge", "charge"],
                            "ac_mean_kw": [-100., -100., 100., 100., -100.],
                            "dc_reference_mean_kw": [-95., -95., 105., 105., -50.]})
    pars, fails = fit_parameters(fixture, config, ["lmo1"])
    require(not fails, "Known physical fixture failed")
    changed = fixture.copy(); changed.loc[4, "dc_reference_mean_kw"] = -10000.
    require(pars == fit_parameters(changed, config, ["lmo1"])[0], "Test2 target influenced parameters")
    b0, b1, _, _ = predict(fixture.loc[:3, config["input_columns"]], pars)
    require(np.allclose(b1, fixture.loc[:3, "dc_reference_mean_kw"], atol=1e-12, rtol=0), "Charge/discharge formula or sign failed")
    require(np.array_equal(b0, fixture.loc[:3, "ac_mean_kw"]), "B0 formula changed")
    invalid = fixture.copy(); invalid.loc[:1, "dc_reference_mean_kw"] = -110.
    invalid_pars, invalid_failures = fit_parameters(invalid, config, ["lmo1"])
    require(invalid_failures[0]["status"] == "invalid_efficiency_no_clipping", "Invalid eta was clipped")
    _, invalid_prediction, _, _ = predict(invalid.loc[:1, config["input_columns"]], invalid_pars)
    require(np.isnan(invalid_prediction).all(), "Invalid parameter not retained as failure")
    try:
        predict(fixture[config["input_columns"] + ["dc_reference_mean_kw"]], pars)
    except ValueError:
        pass
    else:
        raise ValueError("DC target accepted as model input")
    return ["Test2_target_cannot_change_fit", "signed_conversion_formulas", "B0_identity",
            "invalid_eta_no_clipping", "failed_prediction_retained", "target_input_rejected"]


def score_rows(predictions, group_fields):
    rows = []
    for key, group in predictions.groupby(group_fields, sort=True):
        if not isinstance(key, tuple):
            key = (key,)
        paired = np.isfinite(group.b0_dc_hat_kw) & np.isfinite(group.b1_dc_hat_kw)
        for method in ["B0", "B1"]:
            error = group.loc[paired, method.lower() + "_error_kw"]
            record = dict(zip(group_fields, key))
            record.update({"method": method, "windows_total": len(group), "paired_scored_windows": len(error),
                           "pair_failure_windows": int((~paired).sum()),
                           "mae_kw": float(error.abs().mean()) if len(error) else None,
                           "bias_kw": float(error.mean()) if len(error) else None,
                           "b1_outside_fit_power_support_windows": int(group.outside_fit_power_support.eq(True).sum())})
            rows.append(record)
    return pd.DataFrame(rows)


def run(run_id):
    require(bool(re.fullmatch(r"[A-Za-z0-9_-]+", run_id)), "Invalid run ID")
    run_dir = BASE / "baseline_runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    try:
        config_path = BASE / "baseline_protocol_v1.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        checks = contract_checks(config)
        source_run = BASE / "sample_runs" / config["sample_run_id"]
        sample_protocol = json.loads((source_run / "protocol_snapshot.json").read_text(encoding="utf-8"))
        sample_receipt = json.loads((source_run / "validation_receipt.json").read_text(encoding="utf-8"))
        sample_path = source_run / "samples.csv"
        require(digest(sample_path) == config["samples_sha256"] == sample_receipt["file_sha256"]["samples.csv"], "Sample fingerprint mismatch")
        require(digest(PROJECT / sample_protocol["zip_path_from_project_root"]) == config["source_sha256"], "Raw source fingerprint mismatch")
        require(sample_protocol["protocol_id"] == config["sample_protocol_id"] and sample_protocol["split_id"] == config["split_id"], "Sample protocol/split mismatch")
        samples = pd.read_csv(sample_path)
        require(samples.sample_id.is_unique, "Duplicate samples")
        require(set(samples.test_id) == {"test_1", "test_2"}, "Unexpected trial")
        require(samples.loc[samples.test_id.eq("test_1"), "partition"].eq("fit").all() and
                samples.loc[samples.test_id.eq("test_2"), "partition"].eq("evaluation").all(), "Invalid trial split")
        require(np.isfinite(samples[["ac_mean_kw", "dc_reference_mean_kw"]]).all().all(), "Nonfinite input/reference")
        require(((samples.direction.eq("charge") & samples.ac_mean_kw.lt(0)) |
                 (samples.direction.eq("discharge") & samples.ac_mean_kw.gt(0))).all(), "Direction/sign mismatch")
        parameters, failures = fit_parameters(samples, config, sample_protocol["units"])
        b0, b1, status, outside = predict(samples[config["input_columns"]], parameters)
        predictions = samples[["sample_id", "test_id", "unit_id", "direction", "partition",
                               "elapsed_window_start_s", "raw_window_start", "ac_mean_kw", "dc_reference_mean_kw"]].copy()
        predictions["b0_dc_hat_kw"], predictions["b1_dc_hat_kw"] = b0, b1
        predictions["b1_status"] = status
        predictions["outside_fit_power_support"] = outside
        predictions["b0_error_kw"] = b0 - predictions.dc_reference_mean_kw
        predictions["b1_error_kw"] = b1 - predictions.dc_reference_mean_kw
        by_unit = score_rows(predictions, ["test_id", "partition", "unit_id"])
        by_direction = score_rows(predictions, ["test_id", "partition", "unit_id", "direction"])
        metrics = {"primary_definition": config["primary_metric"], "by_trial": {}, "parameter_failures": len(failures)}
        for test, group in predictions.groupby("test_id", sort=True):
            paired = group.b1_dc_hat_kw.notna() & group.b0_dc_hat_kw.notna()
            summary = {"windows_total": len(group), "paired_windows": int(paired.sum()),
                       "coverage_of_candidate_unit_windows_percent": 100 * len(group) / (4320 * 4),
                       "role": "fit diagnostic" if test == "test_1" else "retrospective evaluation",
                       "b1_outside_fit_power_support_windows": int(group.outside_fit_power_support.eq(True).sum())}
            for method in ["B0", "B1"]:
                unit_scores = by_unit.loc[by_unit.test_id.eq(test) & by_unit.method.eq(method)]
                error = group.loc[paired, method.lower() + "_error_kw"]
                summary[method] = {"macro_unit_mae_kw": float(unit_scores.mae_kw.mean()),
                                   "macro_unit_bias_kw": float(unit_scores.bias_kw.mean()),
                                   "pooled_paired_mae_kw": float(error.abs().mean()),
                                   "units_scored": int(unit_scores.mae_kw.notna().sum())}
            summary["B0_all_available_mae_kw"] = float(group.b0_error_kw.abs().mean())
            summary["relative_macro_mae_reduction_percent"] = 100 * (1 - summary["B1"]["macro_unit_mae_kw"] / summary["B0"]["macro_unit_mae_kw"])
            metrics["by_trial"][test] = summary
        predictions.to_csv(run_dir / "predictions.csv", index=False, float_format="%.15g")
        by_unit.to_csv(run_dir / "metrics_by_unit.csv", index=False, float_format="%.15g")
        by_direction.to_csv(run_dir / "metrics_by_unit_direction.csv", index=False, float_format="%.15g")
        evaluation = predictions.loc[predictions.test_id.eq("test_2")]
        worst = evaluation.assign(abs_b1_error_kw=evaluation.b1_error_kw.abs()).sort_values("abs_b1_error_kw", ascending=False).head(10)
        worst.to_csv(run_dir / "worst_evaluation_windows.csv", index=False, float_format="%.15g")
        for name, value in [("parameters.json", parameters), ("failures.json", failures),
                            ("metrics.json", metrics), ("protocol_snapshot.json", config)]:
            (run_dir / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        output_names = ["predictions.csv", "metrics_by_unit.csv", "metrics_by_unit_direction.csv",
                        "worst_evaluation_windows.csv", "parameters.json", "failures.json", "metrics.json", "protocol_snapshot.json"]
        receipt = {"run_id": run_id, "status": "completed", "experiment_id": config["experiment_id"],
                   "input_data_card_version": config["input_data_card_version"], "sample_run_id": config["sample_run_id"],
                   "samples_sha256": digest(sample_path), "source_sha256": config["source_sha256"],
                   "code_sha256": digest(Path(__file__)), "protocol_sha256": digest(config_path),
                   "sample_protocol_sha256": digest(source_run / "protocol_snapshot.json"),
                   "environment": {"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__},
                   "contract_checks_passed": checks, "fit_test_id": "test_1", "evaluation_test_id": "test_2",
                   "fit_windows": int(samples.test_id.eq("test_1").sum()), "evaluation_windows": len(evaluation),
                   "fit_evaluation_sample_overlap": 0, "parameter_failures": len(failures),
                   "fit_sample_ids_sha256": hashlib.sha256("\n".join(samples.loc[samples.test_id.eq("test_1"), "sample_id"]).encode()).hexdigest(),
                   "file_sha256": {name: digest(run_dir / name) for name in output_names},
                   "scope": config["scope"], "gate_status": "await independent verification and reproduction"}
        (run_dir / "run_receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"run": str(run_dir), "evaluation": metrics["by_trial"]["test_2"], "parameter_failures": failures}, ensure_ascii=False, indent=2))
        return run_dir
    except Exception as error:
        (run_dir / "failure.json").write_text(json.dumps({"run_id": run_id, "status": "failed", "error": str(error)}, ensure_ascii=False, indent=2), encoding="utf-8")
        raise


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", default="BL_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
    run(parser.parse_args().run_id)
