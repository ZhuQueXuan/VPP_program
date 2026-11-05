"""Validate the decision ledger, evidence links, and locally retained source hashes."""
import csv
import hashlib
import json
import re
import zipfile
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from xml.etree import ElementTree

HERE = Path(__file__).resolve().parent
WORK = HERE.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(name):
    return json.loads((HERE / name).read_text(encoding="utf-8"))


def main():
    checks = 0

    def check(ok, label):
        nonlocal checks
        if not ok:
            raise AssertionError(label)
        checks += 1

    with (HERE / "admission.csv").open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        check(len(reader.fieldnames) == 15, "schema")
    ids = {r["source_id"] for r in rows}
    check(len(rows) == len(ids) == 13, "source rows and keys")
    check({r["source_id"] for r in rows if r["scope"] == "new"}
          == {"optimise_prime_ws2", "lcl_ev"}, "new source cap")
    for r in rows:
        check(None not in r and all(r.values()), r["source_id"])
        check(r["main_30min"] == r["continuous"] == "未放行", r["source_id"])
        check(r["fixed_arm_energy"] in {"未放行", "待合法原件"}, r["source_id"])
        check(r["evidence"].startswith("https://") or (HERE / r["evidence"]).is_file(), r["evidence"])
    protocol = load("comparison_protocol.json")
    check(protocol["status"] == "conditional_draft_not_released", "protocol status")
    check(protocol["selection_uses_effect_outcomes"] is False, "no outcome selection")
    for target in re.findall(r"\]\(([^)]+)\)", (HERE / "README.md").read_text(encoding="utf-8")):
        if not target.startswith("https://") and target != "verification.json":
            check((HERE / target).exists(), target)
    for name in ("lcl_members.json", "lcl_sample_access.json", "lcl_dictionary_access.json"):
        j = load(name)
        check(sum(x["bytes"] for x in j["ranges"]) <= j["network_byte_limit"], name)
        check(len(j["directory"]) == 4, name)
        check("error" not in j, name)
        for r in j["samples"]:
            p = HERE / r["path"]
            check(sha(p) == r["saved_sha256"] and p.stat().st_size == r["saved_bytes"], p.name)
    lcl = load("lcl_audit.json")
    sample = load("lcl_sample_access.json")
    check(sum(x["bytes"] for x in sample["ranges"]) == lcl["acquisition"]["sample_download_bytes"], "LCL bytes")
    counts = {k.split()[1].lower(): len(v) for k, v in sample["nested_directory"].items()}
    check(counts == lcl["acquisition"]["nested_entries_including_dirs"], "LCL nested directory")
    for i, expected in enumerate(lcl["sample_clock_and_keys"]["by_member"], 1):
        with (HERE / f"lcl_residential_sample_{i}.csv").open(encoding="ascii", newline="") as f:
            observed = list(csv.DictReader(f, skipinitialspace=True))
        keys = {(r["SerialNo"].strip(), r["ReadingDate"]) for r in observed}
        check(len(keys) == len(observed) == expected["rows"], "LCL unique key")
        check({x[0] for x in keys} == {expected["meter"]}, "LCL file-to-meter key")
        times = [datetime.strptime(r["ReadingDate"], "%d/%m/%Y %H:%M:%S") for r in observed]
        check({(b-a).total_seconds() for a, b in zip(times, times[1:])} == {600}, "LCL clock spacing")
        values = [r["Import Wh Total"].strip() for r in observed]
        check(sum(not x for x in values) == expected["import_wh_blank"], "LCL blanks")
        check(sum(x != "" and Decimal(x) == 0 for x in values) == expected["import_wh_zero"], "LCL zero")
    dictionary = load("lcl_dictionary_access.json")
    check(sum(x["bytes"] for x in dictionary["ranges"]) == lcl["acquisition"]["dictionary_download_bytes"],
          "LCL dictionary bytes")
    with zipfile.ZipFile(HERE / "lcl_sample_residential_crosswalk.xlsx") as xlsx:
        ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        shared = ["".join(x.itertext()) for x in ElementTree.fromstring(xlsx.read("xl/sharedStrings.xml"))]
        sheet = ElementTree.fromstring(xlsx.read("xl/worksheets/sheet1.xml"))
        cells = {}
        for c in sheet.findall(".//m:c", ns):
            v = c.findtext("m:v", default="", namespaces=ns)
            if v:
                cells[c.get("r")] = shared[int(v)] if c.get("t") == "s" else v
        check(len(sheet.findall(".//m:row", ns)) == 79, "LCL crosswalk rows")
        check([cells[k].strip() for k in ("A1", "B1", "C1")] == ["Recruited Cu. ID", "Token", "Cu No."],
              "LCL crosswalk headers")
        check(not {"212175499", "212175512"}.intersection(v.strip() for v in cells.values()),
              "LCL crosswalk literal meter keys")
        check(not any(re.search(r"eco\s*20|tariff|control group|\bTOU\b|price", v, re.I)
                      for v in cells.values()), "LCL crosswalk tariff labels")
    check(load("optimise_prime/source_audit.json")["decision"]["admitted_incentive_events"] == 0,
          "depot source decision")
    trace = load("optimise_prime/trace_checks.json")
    candidates = trace["price_dispatch_meter_candidates"]
    check(len(candidates) == trace["candidate_price_dispatch_meter_count"] == 6, "depot candidate count")
    check(trace["admitted_for_effect_estimation"] == 0, "depot inference gate")
    check({x["summary_and_meter"]["depot_id"] for x in candidates} == {"8"}, "one depot")
    check({x["summary_and_meter"]["start"][:10] for x in candidates} == {"2021-11-08"}, "one UTC date")
    check({p["plan_id"] for x in candidates for p in x["prospective_plan_messages"]} == {401}, "one day plan")
    for x in candidates:
        p = x["prospective_plan_messages"]
        d = x["dispatch_messages_at_same_start"]
        w = x["summary_and_meter"]
        check({(z["operation"], z["source_price_fields"]["utilisationPrice"]) for z in p}
              == {("Insert", 83.1), ("Update", 144.0)}, "plan revisions")
        check(len(d) == 1 and max(z["recorded_at"] for z in p) < d[0]["created_at"] < w["start"],
              "plan before dispatch before window")
        check(int(w["meter_rows_with_unique_timestamp"]) in {5, 6}, "bounded meter coverage")
    old = {
        "b1_real_response_data_20261103/ev_sources.json": "61c7dc9e874bd105fa71bb3b65f3a2f57e5470347a466bc7d482953d18fc0923",
        "b1_real_response_data_20261103/ev_review/workplace_original.csv": "5cefedfd1a1526f8f4868aec626a2bb6e8915e1c1d1a45ce3eb958eaeb80c31b",
        "b1_factor_r3a_price_admission_20261104/source_access.json": "d9d108cb71b55d60a5a6566b707a3312442611c42651769e643bd90d0e41557e"
    }
    for name, expected in old.items():
        check(sha(WORK / name) == expected, name)
    hashes = {p.relative_to(HERE).as_posix(): sha(p) for p in sorted(HERE.rglob("*"))
              if p.is_file() and p.name != "verification.json" and "__pycache__" not in p.parts}
    result = {
        "date": "2026-11-05", "passed": True, "checks": checks,
        "rows": len(rows), "new_sources": 2, "admitted_sources": 0,
        "admitted_vehicle_events": 0, "eligible_population_size": None,
        "old_hashes": old, "artifacts_sha256": hashes,
        "effect_estimates": 0, "models_fit": 0, "old_confirmation_reopened": False,
        "stage": "ready_for_root_review_estimation_not_released"
    }
    (HERE / "verification.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                                            encoding="utf-8")
    print(f"{checks} checks; {len(rows)} source rows; 0 admitted.")


if __name__ == "__main__":
    main()
