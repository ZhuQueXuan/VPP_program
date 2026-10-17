"""Prepare and validate the frozen M5BAT component samples. No model fitting."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import platform
import re
import sys
import zipfile

import numpy as np
import pandas as pd


BASE = Path(__file__).resolve().parent
PROJECT = BASE.parent.parent


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def check_clock(frame: pd.DataFrame) -> pd.Series:
    clock = pd.to_datetime(frame["timestamp"], errors="raise")
    require(not clock.isna().any(), "Missing timestamp")
    require(clock.is_unique, "Duplicate timestamp")
    require(clock.diff().iloc[1:].eq(pd.Timedelta(seconds=1)).all(),
            "Measurement must be consecutive one-second records; no ordinal gap filling")
    return clock


def unit_windows(frame: pd.DataFrame, unit: str, protocol: dict) -> pd.DataFrame:
    """Window qualification uses AC only, apart from paired finite completeness."""
    seconds = protocol["window_seconds"]
    require((len(frame) - 1) % seconds == 0, "Incomplete window at terminal boundary")
    check_clock(frame)
    ac = frame[f"{unit}_power_ac"].iloc[:-1].to_numpy(dtype=float)
    dc = frame[f"{unit}_power_dc"].iloc[:-1].to_numpy(dtype=float)
    grouped = pd.DataFrame({"ac": ac, "dc": dc}).groupby(np.arange(len(ac)) // seconds)
    out = grouped.agg(
        record_count=("ac", "size"), ac_count=("ac", "count"), dc_count=("dc", "count"),
        ac_min_kw=("ac", "min"), ac_max_kw=("ac", "max"),
        ac_mean_kw=("ac", "mean"), dc_reference_mean_kw=("dc", "mean"),
    )
    finite = pd.DataFrame({"finite": np.isfinite(ac) & np.isfinite(dc)}).groupby(
        np.arange(len(ac)) // seconds)["finite"].all()
    complete = out.record_count.eq(seconds) & out.ac_count.eq(seconds) & out.dc_count.eq(seconds) & finite
    same_active_direction = ((out.ac_min_kw > protocol["strict_ac_min_abs_kw"]) |
                             (out.ac_max_kw < -protocol["strict_ac_min_abs_kw"]))
    stable = (out.ac_max_kw - out.ac_min_kw) < protocol["strict_ac_max_range_kw"]
    out["eligible"] = complete & same_active_direction & stable
    # A single primary reason per window makes exclusion counts reconcile exactly.
    out["exclusion_reason"] = np.select(
        [~complete, ~same_active_direction, ~stable],
        ["incomplete_or_nonfinite_pair", "inactive_or_direction_change", "ac_range_at_least_10kw"],
        default="",
    )
    out["direction"] = np.where(out.ac_mean_kw > 0, "discharge", "charge")
    out["paired_loss_mean_kw"] = out.dc_reference_mean_kw - out.ac_mean_kw
    out["negative_loss_flag"] = out.paired_loss_mean_kw < 0
    out["dc_sign_mismatch_flag"] = (out.ac_mean_kw * out.dc_reference_mean_kw) < 0
    out["elapsed_window_start_s"] = out.index * seconds
    out["elapsed_window_end_s"] = (out.index + 1) * seconds
    starts = out.elapsed_window_start_s.to_numpy()
    ends = out.elapsed_window_end_s.to_numpy()
    out["raw_window_start"] = frame.timestamp.iloc[starts].to_numpy()
    out["raw_window_end_exclusive"] = frame.timestamp.iloc[ends].to_numpy()
    out["input_available_at_raw_protocol_bound"] = out.raw_window_end_exclusive
    return out.reset_index(drop=True)


def contract_checks(protocol: dict) -> list[str]:
    """Check scientific failure modes, independent of the real dataset counts."""
    clock = pd.date_range("2023-01-01", periods=61, freq="s").astype(str)
    fixture = pd.DataFrame({"timestamp": clock, "lmo1_power_ac": 100., "lmo1_power_dc": 105.})
    good = unit_windows(fixture, "lmo1", protocol)
    require(len(good) == 1 and bool(good.eligible.iloc[0]), "Half-open 60-second window failed")
    changed = fixture.copy()
    changed.loc[60, "lmo1_power_ac"] = 0
    require(unit_windows(changed, "lmo1", protocol).eligible.equals(good.eligible), "Endpoint reused")
    changed.loc[:59, "lmo1_power_dc"] = -200
    alt = unit_windows(changed, "lmo1", protocol)
    require(alt.eligible.equals(good.eligible) and bool(alt.dc_sign_mismatch_flag.iloc[0]),
            "Reference anomaly changed eligibility or disappeared")
    changed = fixture.copy()
    changed.loc[:59, "lmo1_power_ac"] = 50
    require(not bool(unit_windows(changed, "lmo1", protocol).eligible.iloc[0]), "Strict 50kW boundary failed")
    changed = fixture.copy()
    changed.loc[0, "lmo1_power_ac"] = 110
    require(not bool(unit_windows(changed, "lmo1", protocol).eligible.iloc[0]), "Strict 10kW range failed")
    changed = fixture.copy()
    changed.loc[0, "lmo1_power_ac"] = -100
    require(not bool(unit_windows(changed, "lmo1", protocol).eligible.iloc[0]), "Direction transition accepted")
    changed = fixture.copy()
    changed.loc[0, "lmo1_power_dc"] = np.nan
    require(not bool(unit_windows(changed, "lmo1", protocol).eligible.iloc[0]), "Missing reference accepted")
    changed = fixture.copy()
    changed.loc[1, "timestamp"] = changed.loc[0, "timestamp"]
    try:
        unit_windows(changed, "lmo1", protocol)
    except ValueError:
        pass
    else:
        raise ValueError("Duplicate/gapped clock accepted")
    return ["half_open_endpoint", "DC_anomaly_retained", "strict_50kW", "strict_10kW",
            "direction_transition", "missing_reference_rejected", "bad_clock_rejected"]


def prepare(protocol_path: Path, run_id: str) -> Path:
    require(bool(re.fullmatch(r"[A-Za-z0-9_-]+", run_id)), "Run ID must use letters, digits, underscore or hyphen")
    run = BASE / "sample_runs" / run_id
    run.mkdir(parents=True, exist_ok=False)  # Never overwrite a previous run.
    try:
        protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
        checks = contract_checks(protocol)
        require(protocol["tests"]["test_1"]["partition"] == "fit", "Test1 partition changed")
        require(protocol["tests"]["test_2"]["partition"] == "evaluation", "Test2 partition changed")
        source = (PROJECT / protocol["zip_path_from_project_root"]).resolve()
        require(source.is_relative_to(PROJECT), "Source path outside project")
        require(sha256(source) == protocol["zip_sha256"], "Source ZIP fingerprint differs from frozen protocol")
        frames, summaries = [], {}
        with zipfile.ZipFile(source) as archive:
            require(archive.testzip() is None, "ZIP CRC failed")
            for test_id, specification in protocol["tests"].items():
                content = archive.read(specification["member"])
                require(hashlib.sha256(content).hexdigest() == specification["member_sha256"], "CSV fingerprint mismatch")
                frame = pd.read_csv(io.BytesIO(content))
                check_clock(frame)
                require(len(frame) == specification["rows"], "Measurement row count changed")
                require(frame.timestamp.iloc[0] == specification["start_raw"] and
                        frame.timestamp.iloc[-1] == specification["end_raw"], "Raw time coverage changed")
                summaries[test_id] = {}
                for unit in protocol["units"]:
                    windows = unit_windows(frame, unit, protocol)
                    windows.insert(0, "unit_id", unit)
                    windows.insert(0, "test_id", test_id)
                    windows.insert(0, "source_sha256", protocol["zip_sha256"])
                    windows["source_member"] = specification["member"]
                    windows["partition"] = specification["partition"]
                    windows["protocol_id"] = protocol["protocol_id"]
                    windows["split_id"] = protocol["split_id"]
                    windows["measurement_timezone_declared"] = "UTC+2"
                    windows["timezone_alignment_status"] = "unverified; no schedule join"
                    windows["sample_id"] = (test_id + "_" + unit + "_" +
                                             windows.elapsed_window_start_s.astype(str).str.zfill(6))
                    selected = windows[windows.eligible]
                    require(len(selected) == specification["expected_eligible_by_unit"][unit],
                            f"Eligible count mismatch: {test_id}/{unit}")
                    excluded = windows.loc[~windows.eligible, "exclusion_reason"].value_counts().to_dict()
                    require(len(windows) == len(selected) + sum(excluded.values()), "Exclusions do not reconcile")
                    summaries[test_id][unit] = {
                        "candidate_windows": len(windows), "eligible_windows": len(selected),
                        "charge_windows": int(selected.direction.eq("charge").sum()),
                        "discharge_windows": int(selected.direction.eq("discharge").sum()),
                        "coverage_percent": 100 * len(selected) / len(windows),
                        "excluded_primary_reasons": excluded,
                        "negative_loss_flags_retained": int(selected.negative_loss_flag.sum()),
                        "dc_sign_mismatch_flags_retained": int(selected.dc_sign_mismatch_flag.sum()),
                    }
                    frames.append(windows)
        candidates = pd.concat(frames, ignore_index=True)
        require(not candidates.sample_id.duplicated().any(), "Duplicate sample key")
        samples = candidates[candidates.eligible].copy()
        require(samples.groupby("test_id").partition.nunique().eq(1).all(), "Trial leaked across partitions")
        fit = set(samples.loc[samples.partition.eq("fit"), "sample_id"])
        evaluation = set(samples.loc[samples.partition.eq("evaluation"), "sample_id"])
        require(fit.isdisjoint(evaluation), "Fit/evaluation sample overlap")
        candidates.to_csv(run / "candidate_windows.csv", index=False, float_format="%.12g")
        samples.to_csv(run / "samples.csv", index=False, float_format="%.12g")
        samples[["sample_id", "source_sha256", "test_id", "unit_id", "elapsed_window_start_s",
                 "elapsed_window_end_s", "partition", "split_id"]].to_csv(run / "split_manifest.csv", index=False)
        (run / "protocol_snapshot.json").write_text(json.dumps(protocol, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        receipt = {
            "run_id": run_id, "status": "sample_preparation_complete_not_model_experiment",
            "protocol_id": protocol["protocol_id"], "split_id": protocol["split_id"],
            "data_card_version": protocol["data_card_version"], "source_sha256": protocol["zip_sha256"],
            "code_sha256": sha256(Path(__file__)), "protocol_sha256": sha256(protocol_path),
            "environment": {"python": platform.python_version(), "pandas": pd.__version__, "numpy": np.__version__},
            "contract_checks_passed": checks, "trials": summaries,
            "candidate_unit_windows": len(candidates), "eligible_unit_windows": len(samples),
            "fit_windows": len(fit), "evaluation_windows": len(evaluation),
            "fit_evaluation_overlap": 0, "terminal_boundary_rows_not_used": 2,
            "file_sha256": {name: sha256(run / name) for name in
                            ["samples.csv", "candidate_windows.csv", "split_manifest.csv", "protocol_snapshot.json"]},
            "limitations": ["one site; four correlated units", "retrospective paired measurements",
                            "limited stable-window coverage", "test2 quality already inspected",
                            "no model fit, prediction, score or G1 acceptance"],
        }
        (run / "validation_receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"run": str(run), "candidate_windows": len(candidates),
                          "fit_windows": len(fit), "evaluation_windows": len(evaluation),
                          "contract_checks": checks}, ensure_ascii=False, indent=2))
        return run
    except Exception as error:
        (run / "failure.json").write_text(json.dumps({"run_id": run_id, "status": "failed",
                                                     "error": str(error)}, ensure_ascii=False, indent=2), encoding="utf-8")
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", default="PREP_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
    args = parser.parse_args()
    prepare(BASE / "sample_protocol_v1.json", args.run_id)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
