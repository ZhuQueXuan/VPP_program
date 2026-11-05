"""Recompute T1 eligibility, pair masks, native exports and frozen hashes."""
from collections import Counter
import csv
from datetime import datetime
from hashlib import sha256
from itertools import combinations
import json
from pathlib import Path
from zipfile import ZipFile

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
PROV = HERE / "provenance"
T0 = HERE.parent / "b1_temporal_t0_blind_20261104"
ACN = HERE.parent / "b1_temporal_t0_20261104/acn_control_ledger.json"
HEAT = HERE.parent / "b1_response_factors_20261104/raw/heat.zip"
TEMP = ("t_in", "t_out", "t_dhw", "t_set")
META = ("hs_index", "decoupled", "notif_0", "intervention_indicator", "t_threshold_0")


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def validate_sources(events, selected):
    with ZipFile(HEAT) as archive, archive.open("experiment_data.dta") as member:
        raw = pd.read_stata(member, convert_categoricals=False, columns=[
            "hh_id", "unique_index", "time_full", "hp_p", "intervention_dummy",
            "elapsed_time_inter", "reason_stop", *TEMP, *META])
    time = pd.to_datetime(raw.time_full, utc=True)
    ntime = time.astype("int64").to_numpy() // 1_000_000_000
    households = raw.hh_id.to_numpy()
    back = load(T0 / "provenance/heat_event_ledger.json")
    cross = {(r["household"], r["event"]): r for r in back}
    assert len(events) == len(cross) == 287
    post_points = {}
    checked_areas = 0
    for key, row in events.items():
        i, j = row["start_source_row"]-1, row["stop_source_row"]-1
        hh, ev = row["household"], row["event"]
        assert (hh, ev) == (int(raw.hh_id.iat[i]), int(raw.unique_index.iat[i]))
        assert (hh, ev) == (int(raw.hh_id.iat[j]), int(raw.unique_index.iat[j]))
        assert raw.intervention_dummy.iat[i] == 1 and raw.elapsed_time_inter.iat[i] == 0
        assert abs(raw.reason_stop.iat[j] - row["stop_code"]) < 1e-6
        assert ntime[j]-ntime[i] == row["duration_s"]
        assert all(raw[k].iat[i] == row[k] for k in META)
        dt = datetime.fromisoformat(raw.time_full.iat[i])
        assert row["local_date"] == dt.date().isoformat()
        assert abs(row["local_start_hour"]-(dt.hour*3600+dt.minute*60+dt.second)/3600) < 1e-12
        bad = []
        for phase, anchor, left, right, keys in (
            ("before", i, -3600, 0, ("hp_p", *TEMP)), ("after", j, 0, 21600, ("hp_p",))
        ):
            offset = ntime-ntime[anchor]
            in_time = ((offset >= left) & (offset < right)) if phase == "before" else ((offset > left) & (offset <= right))
            indices = np.flatnonzero(in_time & (households == hh))
            indices = indices[np.argsort(offset[indices], kind="stable")]
            t = offset[indices]
            value = row[phase]
            assert len(t) == value["points"]
            p = raw.hp_p.to_numpy()[indices].astype("float64")
            width = t[1:] - t[:-1]
            missing = [k for k in keys if not np.isfinite(raw[k].to_numpy()[indices]).all()]
            unsafe = len(t) < 2 or bool(missing) or np.any((width <= 0) | (width > 450))
            if len(t):
                extension = [int(t[0]-left), int(right-t[-1])]
                assert extension == value["edge_extension_s"]
                unsafe = unsafe or max(extension) > 300
            assert bool(unsafe) == bool(value["issues"])
            bad.append(bool(unsafe))
            if not unsafe:
                edge = (p[0]*extension[0] + p[-1]*extension[1]) / 3600000
                total = sum(w*(a+b)/2 for w, a, b in zip(width, p[:-1], p[1:]))/3600000 + edge
                assert abs(edge-value["edge_energy_kWh"]) < 1e-12
                assert abs(total-value["energy_kWh"]) < 1e-12
                assert all(float(np.median(raw[k].to_numpy()[indices])) == value[k] for k in keys[1:])
                checked_areas += 1
            if phase == "after" and key in selected:
                post_points[key] = (indices, t)
        earlier = cross[(hh, ev)]
        expected = row["duration_s"] > 0 and not any(bad) and not earlier["other_post_events"] and not any(
            v["start_relative_s"] < 0 for v in earlier["other_events"])
        assert row["eligible"] == expected
    return raw, time, post_points, checked_areas


def pair_mask(events):
    ordered = [(k, r) for k, r in sorted(events.items()) if r["eligible"]]
    index = {k: i for i, (k, _) in enumerate(ordered)}
    rr = [r for _, r in ordered]
    col = lambda k: np.array([r[k] for r in rr])
    pre = lambda k: np.array([r["before"][k] for r in rr])
    delta = lambda a: np.abs(a[:, None] - a[None, :])
    both_mean = lambda a: (a[:, None] + a[None, :]) / 2
    duration = col("duration_s")
    day = col("local_date").astype("datetime64[D]")
    years = day.astype("datetime64[Y]")
    clock = delta(col("local_start_hour"))
    pre_power = pre("energy_kWh") * 1000
    energy = np.array([r["after"]["energy_kWh"] for r in rr])
    failure = {
        key: col(key)[:, None] != col(key)[None, :]
        for key in ("hs_index", "decoupled", "notif_0", "stop_code")
    }
    failure.update({
        "date": (years[:, None] != years[None, :]) | (delta(day).astype(int) > 60),
        "start_clock": np.minimum(clock, 24-clock) > 3,
        "actual_duration": (delta(duration) > 10800) |
                           (np.maximum.outer(duration, duration) > 1.5*np.minimum.outer(duration, duration)),
        "threshold": delta(col("t_threshold_0")) > 1,
        "before_power": delta(pre_power) > np.maximum(250, .35*both_mean(pre_power)),
        "post_energy": delta(energy) > np.maximum(.35, .20*both_mean(energy)),
        **{k: delta(pre(k)) > limit for k, limit in zip(TEMP, (1.5, 4, 8, 1.5))}
    })
    seen, matches = set(), set()
    with (PROV / "heat_cross_house_pair_ledger.csv").open(encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            a, b = row["event_a"], row["event_b"]
            i, j = index[a], index[b]
            assert i < j and rr[i]["household"] != rr[j]["household"] and (a, b) not in seen
            seen.add((a, b))
            actual = {key for key, flags in failure.items() if flags[i, j]}
            assert actual == (set(row["mismatch_reasons"].split("|")) if row["mismatch_reasons"] else set())
            assert int(row["matched"]) == (not actual)
            same_round = rr[i]["hs_index"] == rr[j]["hs_index"] and rr[i]["intervention_indicator"] == rr[j]["intervention_indicator"]
            assert bool(int(row["same_source_round"])) == same_round
            if not actual:
                matches.add((a, b))
    assert len(seen) == sum(a["household"] != b["household"] for a, b in combinations(rr, 2))
    return seen, matches


def validate_ev():
    ledger = load(ACN)
    matches = set()
    with (PROV / "acn_control_matches.csv").open(encoding="utf-8") as stream:
        for r in csv.DictReader(stream):
            matches.add((r["role"], r["session_a"], r["session_b"]))
    independently_matched = set()
    for role in ("training", "validation"):
        by_shape = {}
        for r in ledger:
            if r["role"] != role or not r.get("core") or r["core"]["issues"]:
                continue
            steps = [(r["old_limit_A"], r["new_limit_A"])]
            steps.extend((s["old_A"], s["new_A"]) for s in r["subsequent_changes"])
            t = np.array([0, *(s["relative_s"] for s in r["subsequent_changes"]), 1800])
            levels = np.array(steps)
            change = levels[:, 1]-levels[:, 0]
            signature = (len(steps), tuple(np.sign(change)), bool(r["release"]))
            by_shape.setdefault(signature, []).append((r, t, levels, change))
        for group in by_shape.values():
            for (a, ta, la, da), (b, tb, lb, db) in combinations(group, 2):
                if a["user"] == b["user"]:
                    continue
                if np.any(np.abs(la-lb) > 1) or np.any(np.abs(da-db) > 1):
                    continue
                if np.any(np.abs(ta-tb) > 30) or np.any(np.abs(np.diff(ta)-np.diff(tb)) > 45):
                    continue
                if a["release"] and abs(a["release"]["relative_s"]-b["release"]["relative_s"]) > 30:
                    continue
                independently_matched.add((role, a["session"], b["session"]))
    assert independently_matched == matches
    return Counter(role for role, _, _ in matches)


def main():
    freeze = load(PROV / "pre_review_freeze.json")
    assert digest(HERE / "T1_RULES.md") == freeze["rules_sha256"]
    assert digest(HERE / "match.py") == freeze["builder_sha256"]
    assert all(digest(HERE.parent / p) == checksum for p, checksum in freeze["input_sha256"].items())
    assert all(digest(HERE / p) == checksum for p, checksum in freeze["frozen_outputs_sha256"].items())
    old = load(T0 / "provenance/pack_freeze.json")
    assert all(digest(T0 / "blind_pack" / p) == checksum for p, checksum in old["blind_pack_sha256"].items())
    events = load(PROV / "heat_events.json")
    graphs = load(PROV / "heat_accepted_pairs_and_triples.json")
    seen, matches = pair_mask(events)
    assert matches == set(map(tuple, graphs["edges"]))
    involved = {k for edge in matches for k in edge}
    triples = [v for v in combinations(sorted(involved), 3) if all(e in matches for e in combinations(v, 2))]
    assert set(triples) == {tuple(sorted((r["query"], r["candidate_a"], r["candidate_b"]))) for r in graphs["triples"]}
    review = graphs["review_mapping"]
    assert set(map(tuple, review.values())) == matches
    raw, time, points, areas = validate_sources(events, involved)
    exported = 0
    for case, pair in review.items():
        for label, key in zip("AB", pair):
            csv_path = HERE / "blind_pairs" / f"{case}_{label}.csv"
            trace = pd.read_csv(csv_path)
            indices, offset = points[key]
            assert np.array_equal(trace.source_row, indices+1) and np.array_equal(trace.relative_s, offset)
            assert np.array_equal(pd.to_datetime(trace.utc, utc=True), time.iloc[indices])
            assert trace.time_full.tolist() == raw.time_full.iloc[indices].tolist()
            for k in ("hp_p", "intervention_dummy"):
                source = raw[k].to_numpy()[indices]
                np.testing.assert_array_equal(trace[k].to_numpy().astype(source.dtype), source)
            exported += len(trace)
    ev = validate_ev()
    with (HERE / "review_first.psv").open(encoding="utf-8") as stream:
        judgments = list(csv.DictReader(stream, delimiter="|"))
    assert {r["case"] for r in judgments} == set(review)
    result = {
        "source_sha256": digest(Path(__file__)), "pre_review_freeze_sha256": digest(PROV / "pre_review_freeze.json"),
        "frozen_files_checked": len(freeze["frozen_outputs_sha256"]), "old_blind_files_checked": len(old["blind_pack_sha256"]),
        "heat_events_checked": len(events), "valid_integrals_recomputed": areas, "exported_points_checked": exported,
        "heat_pair_flags_checked": len(seen), "heat_pairs": len(matches), "heat_triples": len(triples),
        "ev_pairs_recomputed_by_role": ev, "review_first_sha256": digest(HERE / "review_first.psv"),
        "single_review_counts": Counter(r["judgment"] for r in judgments),
        "t2_draft_sha256": digest(HERE / "T2_DRAFT.md"), "models_fitted": 0,
    }
    (PROV / "verification.json").write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(f"Checked {len(seen)} heat pair flags, {exported} exported points, and {sum(ev.values())} ACN matches.")


if __name__ == "__main__":
    main()
