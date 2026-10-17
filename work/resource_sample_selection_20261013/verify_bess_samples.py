"""Independently recompute M5BAT samples and compare two preparation runs."""

import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import sys
import zipfile

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent
PROJECT = BASE.parent.parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(first_run, repeat_run, verification_id):
    for name in [first_run, repeat_run, verification_id]:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", name):
            raise ValueError("IDs must use letters, digits, underscores or hyphens")
    p = json.loads((BASE / "sample_protocol_v1.json").read_text(encoding="utf-8"))
    first = BASE / "sample_runs" / first_run
    repeat = BASE / "sample_runs" / repeat_run
    target = BASE / "sample_runs" / (verification_id + ".json")
    if target.exists():
        raise FileExistsError("Refuse to overwrite verification receipt")
    source = PROJECT / p["zip_path_from_project_root"]
    if digest(source) != p["zip_sha256"]:
        raise ValueError("Source fingerprint mismatch")
    for run in [first, repeat]:
        saved = json.loads((run / "protocol_snapshot.json").read_text(encoding="utf-8"))
        if saved != p:
            raise ValueError("Run protocol snapshot differs from current protocol")
    samples = pd.read_csv(first / "samples.csv")
    candidates = pd.read_csv(first / "candidate_windows.csv")
    manifest = pd.read_csv(first / "split_manifest.csv")
    if not samples.sample_id.is_unique or not manifest.sample_id.equals(samples.sample_id):
        raise ValueError("Duplicate sample IDs or misaligned manifest")
    for col in manifest.columns:
        if not manifest[col].equals(samples[col]):
            raise ValueError("Manifest column mismatch: " + col)
    totals, details = {}, {}
    tolerance = 1e-8
    with zipfile.ZipFile(source) as archive:
        for test, spec in p["tests"].items():
            content = archive.read(spec["member"])
            if hashlib.sha256(content).hexdigest() != spec["member_sha256"]:
                raise ValueError("CSV fingerprint mismatch")
            f = pd.read_csv(io.BytesIO(content))
            clock = pd.to_datetime(f.timestamp)
            if (len(f) != spec["rows"] or not clock.is_unique or
                    not clock.diff().iloc[1:].eq(pd.Timedelta(seconds=1)).all()):
                raise ValueError("Raw clock/coverage invalid")
            totals[test] = 0
            for unit in p["units"]:
                width = p["window_seconds"]
                ac = f[f"{unit}_power_ac"].to_numpy()[:-1].reshape(-1, width)
                dc = f[f"{unit}_power_dc"].to_numpy()[:-1].reshape(-1, width)
                minimum = p["strict_ac_min_abs_kw"]
                eligible = (((ac > minimum).all(axis=1)) | ((ac < -minimum).all(axis=1)))
                eligible &= np.ptp(ac, axis=1) < p["strict_ac_max_range_kw"]
                eligible &= np.isfinite(ac).all(axis=1) & np.isfinite(dc).all(axis=1)
                s = samples[samples.test_id.eq(test) & samples.unit_id.eq(unit)]
                c = candidates[candidates.test_id.eq(test) & candidates.unit_id.eq(unit)]
                starts = np.flatnonzero(eligible) * width
                valid = (
                    len(s) == spec["expected_eligible_by_unit"][unit]
                    and np.array_equal(s.elapsed_window_start_s.to_numpy(), starts)
                    and np.array_equal(c.eligible.to_numpy(), eligible)
                    and np.allclose(s.ac_mean_kw, ac.mean(axis=1)[eligible], atol=tolerance, rtol=0)
                    and np.allclose(s.dc_reference_mean_kw, dc.mean(axis=1)[eligible], atol=tolerance, rtol=0)
                    and s.raw_window_start.tolist() == f.timestamp.iloc[starts].tolist()
                    and s.raw_window_end_exclusive.tolist() == f.timestamp.iloc[starts + width].tolist()
                    and s.input_available_at_raw_protocol_bound.equals(s.raw_window_end_exclusive)
                    and s.partition.eq(spec["partition"]).all()
                    and s.source_sha256.eq(p["zip_sha256"]).all()
                    and c.exclusion_reason.fillna("").eq("").equals(c.eligible)
                )
                if not valid:
                    raise ValueError("Independent sample comparison failed: " + test + "/" + unit)
                totals[test] += len(s)
                details[test + "/" + unit] = {"eligible": len(s), "excluded": int((~eligible).sum())}
    if len(samples) != sum(totals.values()) or len(candidates) != 34560:
        raise ValueError("Extra/missing samples or candidate rows")
    repeat_hashes = {}
    for name in ["samples.csv", "candidate_windows.csv", "split_manifest.csv", "protocol_snapshot.json"]:
        first_hash = digest(first / name)
        if first_hash != digest(repeat / name):
            raise ValueError("Reproduction mismatch: " + name)
        repeat_hashes[name] = first_hash
    receipt = {
        "verification_id": verification_id, "status": "passed",
        "method": "NumPy reshape/mask from source ZIP; no import of preparation code",
        "first_run": first_run, "repeat_run": repeat_run,
        "code_sha256": digest(Path(__file__)), "protocol_sha256": digest(BASE / "sample_protocol_v1.json"),
        "source_sha256": p["zip_sha256"], "mean_absolute_tolerance_kw": tolerance,
        "eligible_by_test": totals, "units": details, "repeat_file_sha256": repeat_hashes,
        "availability_policy": "protocol bound, not actual receipt time",
        "model_fit_or_scores": "not performed",
    }
    target.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "passed", "eligible_by_test": totals, "receipt": str(target)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--first-run", required=True)
    parser.add_argument("--repeat-run", required=True)
    parser.add_argument("--verification-id", required=True)
    args = parser.parse_args()
    verify(args.first_run, args.repeat_run, args.verification_id)
