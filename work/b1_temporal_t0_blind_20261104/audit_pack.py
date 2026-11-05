"""Check the frozen blind pack and all heat ledger windows against source records."""
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile

import numpy as np
import pandas as pd
from PIL import Image


HERE = Path(__file__).resolve().parent
PACK = HERE / "blind_pack"
PROVENANCE = HERE / "provenance"
WORK = HERE.parent
ACN = WORK / "b1_temporal_t0_20261104"
ZIP = WORK / "b1_response_factors_20261104/raw/heat.zip"
CHANNELS = ["hp_p", "t_in", "t_out", "t_dhw", "t_set", "intervention_dummy"]


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit_heat(ledger, mapping, marks, freeze):
    assert digest(ZIP) == freeze["source_heat_zip_sha256"]
    with ZipFile(ZIP) as archive:
        assert hashlib.sha256(archive.read("experiment_data.dta")).hexdigest() == freeze["source_heat_dta_sha256"]
        with archive.open("experiment_data.dta") as member:
            source = pd.read_stata(member, convert_categoricals=False, columns=[
                "time_full", "hh_id", "unique_index", "reason_stop",
                "elapsed_time_inter", "total_duration_int", *CHANNELS])
    utc = pd.to_datetime(source.time_full, utc=True)
    assert len(source) == freeze["source_heat_rows"] == 659782
    starts, stops = {}, {}
    for i in np.flatnonzero((source.intervention_dummy == 1) & (source.elapsed_time_inter == 0)):
        k = (int(source.hh_id.iat[i]), int(source.unique_index.iat[i]))
        assert k not in starts
        starts[k] = int(i)
    for i in np.flatnonzero(source.reason_stop.notna() & (source.reason_stop != 0)):
        k = (int(source.hh_id.iat[i]), int(source.unique_index.iat[i]))
        assert k not in stops
        stops[k] = int(i)
    assert set(starts) == set(stops) == {(r["household"], r["event"]) for r in ledger}
    assert len(ledger) == 287
    selected = {(m["household"], m["event"]): c for c, m in mapping.items() if c.startswith("HP")}
    rows_checked = 0
    for row in ledger:
        hh, event = k = (row["household"], row["event"])
        i, j = starts[k], stops[k]
        duration = int((utc.iat[j] - utc.iat[i]).total_seconds())
        assert (i+1, j+1, duration) == (row["start_source_row"], row["stop_source_row"], row["duration_s"])
        assert row["duration_s_source"] == source.total_duration_int.iat[j]
        assert row["duration_source_minus_utc_s"] == source.total_duration_int.iat[j] - duration
        assert row["stop_reason_raw"] == source.reason_stop.iat[j]
        household = source.index[source.hh_id == hh]
        seconds = (utc.loc[household] - utc.iat[i]).dt.total_seconds()
        order = seconds.sort_values(kind="stable")
        bounds = {"before": (-3600, 0), "during": (0, duration),
                  "after": (duration, duration+21600), "entire": (-3600, duration+21600)}
        for stage, (left, right) in bounds.items():
            included = order.between(left, right, inclusive={"before": "left", "after": "right"}.get(stage, "both"))
            t = order[included]
            stats = row["phases"][stage]
            assert stats["expected_s"] == [left, right]
            assert len(t) == stats["points"]
            assert stats["source_left_censored"] == (order.iloc[0] > left)
            assert stats["source_right_censored"] == (order.iloc[-1] < right)
            assert stats["left_edge_undercovered"] == (not len(t) or t.iloc[0] > left+450)
            assert stats["right_edge_undercovered"] == (not len(t) or t.iloc[-1] < right-450)
            assert (t.index[t.duplicated(keep=False)] + 1).tolist() == stats["duplicate_source_rows"]
            gaps = [(int(a), int(b)) for a, b in zip(t.iloc[:-1], t.iloc[1:]) if b-a > 450]
            assert [list(gap) for gap in gaps] == stats["long_gaps"]
            assert source.loc[t.index, CHANNELS].isna().sum().to_dict() == stats["missing_by_channel"]
        assert len(t) == row["phases"]["entire"]["points"]
        entire = row["phases"]["entire"]
        assert row["timing_issue"] == any(entire[field] for field in (
            "left_edge_undercovered", "right_edge_undercovered", "source_left_censored",
            "source_right_censored", "duplicate_source_rows", "long_gaps"))
        others = []
        for other in (key for key in starts if key[0] == hh and key != k):
            a = (utc.iat[starts[other]] - utc.iat[i]).total_seconds()
            b = (utc.iat[stops[other]] - utc.iat[i]).total_seconds()
            if a <= duration+21600 and b >= -3600:
                others.append((other[1], a, b))
        assert sorted(others) == sorted((o["event"], o["start_relative_s"], o["stop_relative_s"])
                                         for o in row["other_events"])
        assert sorted(o[0] for o in others if o[2] > duration) == sorted(
            o["event"] for o in row["other_post_events"])
        if k not in selected:
            continue
        case = selected[k]
        f = pd.read_csv(PACK / "points" / f"{case}.csv")
        assert np.array_equal(f.source_row, t.index + 1)
        assert np.array_equal(f.relative_s, t)
        assert np.array_equal(f.relative_stop_s, t-duration)
        assert np.array_equal(pd.to_datetime(f.utc, utc=True), utc.loc[t.index])
        assert f.time_full.tolist() == source.loc[t.index, "time_full"].tolist()
        for channel in CHANNELS:
            # Pandas emits the shortest decimal that round-trips to the native Stata dtype.
            native = source.loc[t.index, channel].to_numpy()
            restored = f[channel].to_numpy().astype(native.dtype)
            np.testing.assert_array_equal(restored, native)
        assert marks[case]["end_s"] == duration and marks[case]["stop_source_row"] == j+1
        rows_checked += len(f)
    assert rows_checked == freeze["heat_native_points"]
    return rows_checked, int(source.duplicated(subset=["hh_id", "time_full"]).sum())


def audit_selection(ledger, mapping):
    rank = lambda row: hashlib.sha256(
        f"t0-blind-heat-v1|{row['household']}|{row['event']}".encode()).hexdigest()
    for row in ledger:
        assert row["selection_sha256"] == rank(row)
    remaining = sorted(ledger, key=rank)
    picked = [next(r for r in remaining if r["household"] == hh and r["duration_s"] > 0)
              for hh in sorted({r["household"] for r in ledger})]
    counts = Counter(r["household"] for r in picked)
    for condition in (lambda r: r["duration_s"] == 0,
                      lambda r: r["duration_s"] > 0 and r["timing_issue"],
                      lambda r: r["duration_s"] > 0):
        item = next((r for r in remaining if counts[r["household"]] < 2 and r not in picked
                     and condition(r)), None)
        if item:
            picked.append(item)
            counts[item["household"]] += 1
    assert len(picked) == 12 and len(counts) == 9 and max(counts.values()) == 2
    assert [rank(r) for r in sorted(picked, key=rank)] == [
        m["selection_sha256"] for k, m in mapping.items() if k.startswith("HP")]


def main():
    freeze = read(PROVENANCE / "pack_freeze.json")
    mapping = read(PROVENANCE / "source_mapping_and_heat_selection.json")
    ledger = read(PROVENANCE / "heat_event_ledger.json")
    marks = read(PACK / "control_marks.json")
    paths = {p.relative_to(PACK).as_posix(): digest(p) for p in PACK.rglob("*") if p.is_file()}
    assert paths == freeze["blind_pack_sha256"]
    for field, filename in (("ledger", "acn_control_ledger.json"), ("registry", "acn_review_registry.json")):
        assert digest(ACN / filename) == freeze[f"source_acn_{field}_sha256"]
    assert digest(HERE / "build_pack.py") == freeze["builder_sha256"]
    acn_mapping = {c: m for c, m in mapping.items() if c.startswith("EV")}
    registry = read(ACN / "acn_review_registry.json")
    acn_keys = sorted(r["case"] for r in registry)
    assert acn_keys == sorted(m["case"] for m in acn_mapping.values())
    assert len(acn_keys) == len({m["user"] for m in acn_mapping.values()}) == 24
    expected = sorted(acn_keys, key=lambda c: hashlib.sha256(f"t0-blind-acn-v1|{c}".encode()).digest())
    assert expected == [m["case"] for m in acn_mapping.values()]
    for case, row in acn_mapping.items():
        original = ACN / "blind_source_points" / f"{row['case']}.csv"
        assert digest(original) == row["original_pack_sha256"] == digest(PACK / "points" / f"{case}.csv")
    audit_selection(ledger, mapping)
    heat_rows, source_duplicate_excess = audit_heat(ledger, mapping, marks, freeze)
    assert set(mapping) == set(marks)
    for case in mapping:
        with Image.open(PACK / "plots" / f"{case}.png") as chart:
            assert chart.height >= 500 and chart.width >= 700
            chart.verify()
    review = HERE / "review_private/first_read.psv"
    with review.open(encoding="utf-8", newline="") as stream:
        ratings = list(csv.DictReader(stream, delimiter="|"))
    assert sorted(r["case"] for r in ratings) == sorted(mapping)
    dimensions = ("interruption", "order", "rise")
    summaries = {}
    for kind, object_key in (("EV", "user"), ("HP", "household")):
        subset = [r for r in ratings if r["case"].startswith(kind)]
        summaries[kind] = {"cases": len(subset),
                           "objects": len({mapping[r["case"]][object_key] for r in subset})}
        for dim in dimensions:
            distinct = defaultdict(set)
            for r in subset:
                distinct[r[dim]].add(mapping[r["case"]][object_key])
            valid = [r for r in subset if r[dim] not in {"不可判", "不适用"}]
            summaries[kind][dim] = {"case_counts": Counter(r[dim] for r in subset),
                                    "objects_per_category": {k: len(v) for k, v in distinct.items()},
                                    "assessable_cases": len(valid),
                                    "assessable_objects": len({mapping[r["case"]][object_key] for r in valid})}
    heat_issues = Counter()
    for r in ledger:
        stages = r["phases"]
        heat_issues["zero_duration"] += r["zero_duration"]
        heat_issues["utc_duration_discrepancy"] += r["duration_source_minus_utc_s"] != 0
        heat_issues["other_intervention"] += bool(r["other_events"])
        heat_issues["other_post_intervention"] += bool(r["other_post_events"])
        for phase, s in stages.items():
            for flag in ("empty", "source_left_censored", "source_right_censored", "left_edge_undercovered",
                         "right_edge_undercovered", "duplicate_source_rows", "long_gaps"):
                heat_issues[f"{phase}.{flag}"] += bool(s[flag])
            for channel, count in s["missing_by_channel"].items():
                heat_issues[f"{phase}.missing.{channel}"] += count > 0

    def power_coverage(phase):
        return phase["points"] >= 2 and not any(phase[field] for field in (
            "source_left_censored", "source_right_censored", "left_edge_undercovered",
            "right_edge_undercovered", "duplicate_source_rows", "long_gaps")
        ) and phase["missing_by_channel"]["hp_p"] == 0

    candidates = defaultdict(list)
    for r in ledger:
        if r["zero_duration"]:
            continue
        if power_coverage(r["phases"]["entire"]):
            candidates["full_window"].append(r)
        if power_coverage(r["phases"]["before"]) and power_coverage(r["phases"]["during"]):
            candidates["before_and_during"].append(r)
        if power_coverage(r["phases"]["after"]) and not r["other_post_events"]:
            candidates["post_window_no_new_control"].append(r)
    coverage_counts = {
        key: {"events": len(rows), "households": len({r["household"] for r in rows})}
        for key, rows in candidates.items()
    }
    report = {
        "audit_source_sha256": digest(Path(__file__)), "blind_frozen_files": len(paths),
        "heat_stage_checks": len(ledger)*4, "heat_point_source_rows_checked": heat_rows,
        "heat_source_duplicate_hh_original_time_extra_rows": source_duplicate_excess,
        "acn_reused_csv_verified": len(acn_keys), "acn_reused_points": freeze["acn_native_points"],
        "heat_issue_case_counts": heat_issues, "heat_positive_metadata_coverage": coverage_counts,
        "first_review_sha256": digest(review),
        "first_review_summary": summaries, "independent_second_review_available": False,
        "models_fitted": 0, "prior_confirmation_opened": False,
    }
    path = PROVENANCE / "verification.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Verified {len(paths)} blind files, {len(acn_keys)} ACN packs, {heat_rows} heat points, {len(ratings)} first reviews.")


if __name__ == "__main__":
    main()
