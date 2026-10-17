"""Independently recompute fitted efficiencies, predictions, metrics and repetition."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(first_id, repeat_id, audit_id):
    for value in [first_id, repeat_id, audit_id]:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", value):
            raise ValueError("Invalid run/verification ID")
    config_path = BASE / "baseline_protocol_v1.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    first = BASE / "baseline_runs" / first_id
    repeat = BASE / "baseline_runs" / repeat_id
    output = BASE / "baseline_runs" / (audit_id + ".json")
    if output.exists():
        raise FileExistsError("Refuse to overwrite verification receipt")
    sample_path = BASE / "sample_runs" / config["sample_run_id"] / "samples.csv"
    if digest(sample_path) != config["samples_sha256"]:
        raise ValueError("Sample fingerprint mismatch")
    samples = pd.read_csv(sample_path)
    pred = pd.read_csv(first / "predictions.csv")
    if not pred.sample_id.equals(samples.sample_id):
        raise ValueError("Prediction/sample order or ID mismatch")
    for name in ["test_id", "unit_id", "direction", "partition", "elapsed_window_start_s", "raw_window_start"]:
        if not pred[name].equals(samples[name]):
            raise ValueError("Metadata mismatch: " + name)
    tolerances = config["reproduction_tolerances"]
    tol = tolerances["prediction_absolute_kw"]
    parameters = json.loads((first / "parameters.json").read_text(encoding="utf-8"))
    lookup = {(x["unit_id"], x["direction"]): x for x in parameters}
    if set(lookup) != {(u, d) for u in ["lmo1", "lmo2", "lmo3", "lmo4"] for d in ["charge", "discharge"]}:
        raise ValueError("Missing or duplicate parameter group")
    reconstructed = np.empty(len(samples))
    parameter_checks = {}
    for (unit, direction), fitted in lookup.items():
        fit_mask = samples.test_id.eq("test_1") & samples.partition.eq("fit") & samples.unit_id.eq(unit) & samples.direction.eq(direction)
        ac = samples.loc[fit_mask, "ac_mean_kw"].to_numpy()
        dc = samples.loc[fit_mask, "dc_reference_mean_kw"].to_numpy()
        eta = dc.sum() / ac.sum() if direction == "charge" else ac.sum() / dc.sum()
        if (fitted["status"] != "ok" or fitted["fit_test_id"] != "test_1" or fitted["fit_window_count"] != len(ac) or
                not 0 < eta <= 1 or not np.isclose(eta, fitted["eta"], atol=tolerances["eta_absolute"], rtol=0)):
            raise ValueError("Test1-only parameter reconstruction failed")
        mask = samples.unit_id.eq(unit) & samples.direction.eq(direction)
        x = samples.loc[mask, "ac_mean_kw"].to_numpy()
        reconstructed[mask] = x * eta if direction == "charge" else x / eta
        expected_support = (np.abs(x) < np.abs(ac).min()) | (np.abs(x) > np.abs(ac).max())
        if not np.array_equal(pred.loc[mask, "outside_fit_power_support"].to_numpy(), expected_support):
            raise ValueError("Input power support flag mismatch")
        parameter_checks[unit + "/" + direction] = {"fit_windows": len(ac), "eta": float(eta)}
    y = samples.dc_reference_mean_kw.to_numpy()
    ac = samples.ac_mean_kw.to_numpy()
    for name, expected in {"ac_mean_kw": ac, "dc_reference_mean_kw": y, "b0_dc_hat_kw": ac,
                           "b1_dc_hat_kw": reconstructed, "b0_error_kw": ac - y,
                           "b1_error_kw": reconstructed - y}.items():
        if not np.allclose(pred[name], expected, atol=tol, rtol=0):
            raise ValueError("Prediction/reference/error reconstruction failed: " + name)
    metric_tol = tolerances["metric_absolute_kw"]
    for filename, fields in [("metrics_by_unit.csv", ["test_id", "partition", "unit_id"]),
                             ("metrics_by_unit_direction.csv", ["test_id", "partition", "unit_id", "direction"])]:
        metrics = pd.read_csv(first / filename)
        for row in metrics.to_dict("records"):
            mask = np.ones(len(samples), dtype=bool)
            for field in fields:
                mask &= samples[field].eq(row[field]).to_numpy()
            error = (ac - y if row["method"] == "B0" else reconstructed - y)[mask]
            if (row["paired_scored_windows"] != len(error) or row["pair_failure_windows"] != 0 or
                    not np.isclose(row["mae_kw"], np.abs(error).mean(), atol=metric_tol, rtol=0) or
                    not np.isclose(row["bias_kw"], error.mean(), atol=metric_tol, rtol=0)):
                raise ValueError("Metric reconstruction failed")
    summary = json.loads((first / "metrics.json").read_text(encoding="utf-8"))
    for test, trial_summary in summary["by_trial"].items():
        test_mask = samples.test_id.eq(test).to_numpy()
        for method, prediction in [("B0", ac), ("B1", reconstructed)]:
            error = prediction - y
            per_unit_mae, per_unit_bias = [], []
            for unit in ["lmo1", "lmo2", "lmo3", "lmo4"]:
                values = error[test_mask & samples.unit_id.eq(unit).to_numpy()]
                per_unit_mae.append(np.abs(values).mean()); per_unit_bias.append(values.mean())
            expected = {"macro_unit_mae_kw": np.mean(per_unit_mae), "macro_unit_bias_kw": np.mean(per_unit_bias),
                        "pooled_paired_mae_kw": np.abs(error[test_mask]).mean()}
            for name, value in expected.items():
                if not np.isclose(trial_summary[method][name], value, atol=metric_tol, rtol=0):
                    raise ValueError("Summary metric reconstruction failed")
    if json.loads((first / "failures.json").read_text(encoding="utf-8")) != []:
        raise ValueError("Parameter failure requires separate gate review")
    repeated = {}
    for run in [first, repeat]:
        receipt = json.loads((run / "run_receipt.json").read_text(encoding="utf-8"))
        if (receipt["protocol_sha256"] != digest(config_path) or receipt["samples_sha256"] != digest(sample_path)
                or receipt["code_sha256"] != digest(BASE / "run_bess_baselines.py")):
            raise ValueError("Input/code/protocol fingerprint mismatch")
        for name, expected_hash in receipt["file_sha256"].items():
            if digest(run / name) != expected_hash:
                raise ValueError("Output fingerprint mismatch")
            if run == first:
                repeated[name] = expected_hash
            elif repeated[name] != expected_hash:
                raise ValueError("Repeat run differs: " + name)
    audit = {"verification_id": audit_id, "status": "passed", "first_run": first_id, "repeat_run": repeat_id,
             "method": "NumPy reconstruction on fixed samples; no import of baseline runner",
             "code_sha256": digest(Path(__file__)), "protocol_sha256": digest(config_path),
             "registered_tolerances": tolerances, "parameter_reconstruction": parameter_checks,
             "all_2911_predictions_and_errors_match": True, "all_group_and_summary_metrics_match": True,
             "repeat_output_sha256": repeated, "fit_test_id": "test_1", "evaluation_test_id": "test_2",
             "limits": ["retrospective same-site steady conversion", "not whole-capacity/SOC/task validation"]}
    output.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "passed", "receipt": str(output), "evaluation": summary["by_trial"]["test_2"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--first-run", required=True)
    parser.add_argument("--repeat-run", required=True)
    parser.add_argument("--verification-id", required=True)
    args = parser.parse_args()
    verify(args.first_run, args.repeat_run, args.verification_id)
