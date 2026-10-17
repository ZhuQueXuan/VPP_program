"""Inspect SOC steps against native power; no correction, state fit or capacity estimate."""

import argparse
import hashlib
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


def audit(run_id):
    if not re.fullmatch(r"[A-Za-z0-9_-]+", run_id):
        raise ValueError("Invalid run ID")
    target = BASE / "state_audit_runs" / run_id
    target.mkdir(parents=True, exist_ok=False)
    protocol = json.loads((BASE / "sample_protocol_v1.json").read_text(encoding="utf-8"))
    source = PROJECT / protocol["zip_path_from_project_root"]
    if digest(source) != protocol["zip_sha256"]:
        raise ValueError("Raw source fingerprint mismatch")
    jump_threshold_pp, return_band_pp, return_horizon_s = 1., .2, 5
    nominal_assumption_kwh = 774.14
    events, summaries = [], {}
    with zipfile.ZipFile(source) as archive:
        for test, specification in protocol["tests"].items():
            content = archive.read(specification["member"])
            if hashlib.sha256(content).hexdigest() != specification["member_sha256"]:
                raise ValueError("CSV fingerprint mismatch")
            f = pd.read_csv(archive.open(specification["member"]))
            t = pd.to_datetime(f.timestamp)
            if not t.is_unique or not t.diff().iloc[1:].eq(pd.Timedelta(seconds=1)).all():
                raise ValueError("Clock invalid")
            summaries[test] = {}
            for unit in protocol["units"]:
                soc = f[unit + "_soc"].to_numpy()
                ac = f[unit + "_power_ac"].to_numpy()
                dc = f[unit + "_power_dc"].to_numpy()
                positions = np.flatnonzero(np.abs(np.diff(soc)) > jump_threshold_pp + 1e-8) + 1
                returns, zeros, lows = 0, 0, 0
                for i in positions:
                    before = soc[i - 1]
                    jump = soc[i] - before
                    stop = min(i + return_horizon_s + 1, len(soc))
                    returned = bool(np.any(np.abs(soc[i + 1:stop] - before) <= return_band_pp + 1e-8))
                    zero_ac = bool(ac[i - 1] == 0 and ac[i] == 0)
                    low_dc = bool(max(abs(dc[i - 1]), abs(dc[i])) <= 15)
                    returns += int(returned); zeros += int(zero_ac); lows += int(low_dc)
                    events.append({
                        "test_id": test, "unit_id": unit, "elapsed_s": int(i), "raw_timestamp": f.timestamp.iloc[i],
                        "soc_before_percent": float(before), "soc_after_percent": float(soc[i]),
                        "soc_change_pp": float(jump), "ac_before_kw": float(ac[i - 1]), "ac_after_kw": float(ac[i]),
                        "dc_before_kw": float(dc[i - 1]), "dc_after_kw": float(dc[i]),
                        "returned_within_5s_0p2pp": returned, "two_endpoint_ac_zero": zero_ac,
                        "two_endpoint_dc_abs_le_15kw": low_dc,
                        "conditional_energy_if_soc_equals_soe_nominal_kwh": float(nominal_assumption_kwh * jump / 100),
                        "conditional_equivalent_charge_power_kw": float(nominal_assumption_kwh * jump / 100 * 3600),
                        "one_second_dc_endpoint_energy_envelope_kwh": float(max(abs(dc[i - 1]), abs(dc[i])) / 3600),
                        "conditional_status": "nominal-capacity/SOC=SOE assumption only, NOT real energy or capacity truth",
                    })
                summaries[test][unit] = {"soc_grid_0p1pp": bool(np.allclose(soc * 10, np.round(soc * 10), atol=1e-8)),
                                         "jumps_gt_1pp": len(positions), "max_abs_jump_pp": float(np.max(np.abs(np.diff(soc))[positions - 1])),
                                         "returned_within_5s_0p2pp": returns, "zero_ac_endpoint_jump_count": zeros,
                                         "dc_abs_le_15kw_endpoint_jump_count": lows}
    table = pd.DataFrame(events).sort_values(["test_id", "elapsed_s", "unit_id"]).reset_index(drop=True)
    table.to_csv(target / "soc_jump_events.csv", index=False, float_format="%.15g")
    selected = table.loc[table.soc_change_pp.abs().idxmax()].to_dict()
    literature_parameters = {
        "source": "https://publications.rwth-aachen.de/record/1024855/files/1024855.pdf",
        "section": "3.5 Table 2; 3.3.2 Eqs (12)-(14)", "scope": "author's Test2 model parameters, not our independent capacity measurements",
        "nominal_energy_kwh": nominal_assumption_kwh, "soh_percent": {"lmo1": 93.18, "lmo2": 93.39, "lmo3": 93.76, "lmo4": 93.73},
        "capacity_formula": "nominal_energy_kwh * SOH / 100; SOC window and rate limits apply separately",
        "health_scaled_energy_parameters_kwh": {u: nominal_assumption_kwh * h / 100 for u, h in
                                                 {"lmo1": 93.18, "lmo2": 93.39, "lmo3": 93.76, "lmo4": 93.73}.items()},
        "battery_one_way_efficiency": 0.9769,
        "boundary": "battery internal energy efficiency; distinct from inverter AC/DC baseline eta",
        "missing": ["routine capacity test raw files and exact dates", "Test1 matching SOH", "SOC/SOE calibration", "BMS correction logs"],
    }
    (target / "literature_parameters.json").write_text(json.dumps(literature_parameters, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    receipt = {"run_id": run_id, "status": "diagnostic_complete_no_state_model", "source_sha256": protocol["zip_sha256"],
               "code_sha256": digest(Path(__file__)), "jump_threshold_pp": jump_threshold_pp,
               "return_horizon_s": return_horizon_s, "return_band_pp": return_band_pp,
               "diagnostic_thresholds_not_sample_exclusion_rules": True,
               "groups": summaries, "jump_records_total": len(table), "max_jump_example": selected,
               "SOC_modified": False, "sample_or_baseline_protocol_changed": False,
               "not_established": ["exact BMS mechanism", "physical energy change from SOC steps", "current effective capacity", "SOC ground truth"],
               "file_sha256": {name: digest(target / name) for name in ["soc_jump_events.csv", "literature_parameters.json"]}}
    (target / "audit_receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"run": str(target), "jumps": len(table), "groups": summaries,
                      "max_jump_example": selected, "capacity_parameters": literature_parameters["health_scaled_energy_parameters_kwh"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    audit(parser.parse_args().run_id)
