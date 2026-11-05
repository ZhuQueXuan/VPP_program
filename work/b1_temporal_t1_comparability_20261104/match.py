"""Freeze T1 comparability ledgers from local development data."""
from collections import Counter, defaultdict
import csv
from hashlib import sha256
from itertools import combinations
import json
from pathlib import Path
from zipfile import ZipFile

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
WORK = HERE.parent
T0 = WORK / "b1_temporal_t0_blind_20261104/provenance"
ACN = WORK / "b1_temporal_t0_20261104/acn_control_ledger.json"
HEAT = WORK / "b1_response_factors_20261104/raw/heat.zip"
RULES_SHA = "a9aaa4a0a4085d1bd9d99d3c58c5cba95f192b3e80c66c7bc211d0f9feda8504"
THERMAL = ["t_in", "t_out", "t_dhw", "t_set"]
CONTROL = ["hs_index", "decoupled", "notif_0", "intervention_indicator", "t_threshold_0"]


def digest(value):
    return sha256(value).hexdigest()


def rank(seed, *items):
    return digest("|".join([seed, *items]).encode())


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def window_stats(frame, left, right, channels):
    t = frame.relative_s.to_numpy()
    issues = []
    if len(t) < 2:
        issues.append("too_few_points")
    if len(t) and (t[0]-left > 300 or right-t[-1] > 300):
        issues.append("edge_over_300s")
    if (np.diff(t) <= 0).any():
        issues.append("duplicate_or_unordered")
    if (np.diff(t) > 450).any():
        issues.append("gap_over_450s")
    for key in channels:
        if not np.isfinite(frame[key].to_numpy()).all():
            issues.append("missing_" + key)
    result = {"points": len(t), "issues": issues}
    if len(t):
        result["edge_extension_s"] = [int(t[0]-left), int(right-t[-1])]
    if not issues:
        p = frame.hp_p.to_numpy(dtype=float)
        extension = ((t[0]-left)*p[0] + (right-t[-1])*p[-1]) / 3600000
        result["edge_energy_kWh"] = float(extension)
        result["energy_kWh"] = float(np.trapezoid(p, t) / 3600000 + extension)
        result.update({key: float(frame[key].median()) for key in channels if key != "hp_p"})
    return result


def heat_events(ledger):
    with ZipFile(HEAT) as archive, archive.open("experiment_data.dta") as stream:
        source = pd.read_stata(stream, convert_categoricals=False, columns=[
            "hh_id", "unique_index", "time_full", "hp_p", "intervention_dummy",
            "elapsed_time_inter", "reason_stop", *THERMAL, *CONTROL])
    source["source_row"] = np.arange(1, len(source)+1)
    source["utc"] = pd.to_datetime(source.time_full, format="mixed", utc=True)
    groups = {int(h): f.sort_values(["utc", "source_row"]).set_index("utc", drop=False)
              for h, f in source.groupby("hh_id")}
    old = read(T0 / "source_mapping_and_heat_selection.json")
    seen_t0 = {(r["household"], r["event"]) for key, r in old.items() if key.startswith("HP")}
    rows, curves = {}, {}
    for original in ledger:
        hh, event = original["household"], original["event"]
        key = f"{hh}:{event}"
        start = pd.Timestamp(original["start_utc"])
        stop = pd.Timestamp(original["stop_utc"])
        start_row = source.iloc[original["start_source_row"] - 1]
        stop_row = source.iloc[original["stop_source_row"] - 1]
        assert start_row.hh_id == stop_row.hh_id == hh and start_row.unique_index == stop_row.unique_index == event
        assert start_row.elapsed_time_inter == 0 and start_row.intervention_dummy == 1
        assert start_row.utc == start and stop_row.utc == stop and stop_row.reason_stop != 0
        hh_records = groups[hh]
        pre = hh_records.loc[start - pd.Timedelta(hours=1):start].copy()
        pre = pre[pre.utc < start]
        pre["relative_s"] = (pre.utc - start).dt.total_seconds()
        post = hh_records.loc[stop:stop + pd.Timedelta(hours=6)].copy()
        post = post[post.utc > stop]
        post["relative_s"] = (post.utc - stop).dt.total_seconds()
        before = window_stats(pre, -3600, 0, ["hp_p", *THERMAL])
        after = window_stats(post, 0, 21600, ["hp_p"])
        issues = ["before_" + i for i in before["issues"]] + ["after_" + i for i in after["issues"]]
        if original["zero_duration"]:
            issues.append("zero_duration")
        if original["other_post_events"]:
            issues.append("other_post_intervention")
        if any(e["start_relative_s"] < 0 for e in original["other_events"]):
            issues.append("other_pre_intervention")
        metadata = {k: float(start_row[k]) if pd.notna(start_row[k]) else None for k in CONTROL}
        if any(v is None for v in metadata.values()):
            issues.append("missing_control_metadata")
        local = pd.Timestamp(start_row.time_full)
        rows[key] = {
            "household": hh, "event": event, "start_source_row": original["start_source_row"],
            "stop_source_row": original["stop_source_row"], "start_utc": start.isoformat(),
            "stop_utc": stop.isoformat(), "local_date": local.date().isoformat(),
            "local_start_hour": local.hour + local.minute / 60 + local.second / 3600,
            "duration_s": original["duration_s"], "duration_source_minus_utc_s": original["duration_source_minus_utc_s"],
            "stop_code": round(float(stop_row.reason_stop), 1), "seen_t0_pack": (hh, event) in seen_t0,
            **metadata, "before": before, "after": after, "eligible": not issues, "issues": issues,
        }
        curves[key] = post[["source_row", "time_full", "utc", "relative_s", "hp_p", "intervention_dummy"]]
    return rows, curves


def heat_mismatch(a, b):
    flags = [k for k in ("hs_index", "decoupled", "notif_0", "stop_code") if a[k] != b[k]]
    da, db = pd.Timestamp(a["local_date"]), pd.Timestamp(b["local_date"])
    clock = abs(a["local_start_hour"] - b["local_start_hour"])
    length = abs(a["duration_s"] - b["duration_s"])
    checks = {
        "date": da.year != db.year or abs((da-db).days) > 60,
        "start_clock": min(clock, 24-clock) > 3,
        "actual_duration": length > 10800 or max(a["duration_s"], b["duration_s"]) > 1.5*min(a["duration_s"], b["duration_s"]),
        "threshold": abs(a["t_threshold_0"]-b["t_threshold_0"]) > 1,
    }
    before_a, before_b = a["before"], b["before"]
    for key, limit in zip(THERMAL, (1.5, 4, 8, 1.5)):
        checks[key] = abs(before_a[key]-before_b[key]) > limit
    pa, pb = before_a["energy_kWh"]*1000, before_b["energy_kWh"]*1000
    checks["before_power"] = abs(pa-pb) > max(250, .35*(pa+pb)/2)
    ea, eb = a["after"]["energy_kWh"], b["after"]["energy_kWh"]
    checks["post_energy"] = abs(ea-eb) > max(.35, .20*(ea+eb)/2)
    return flags + [k for k, fail in checks.items() if fail]


def heat_graph(rows, out):
    eligible = sorted(k for k, r in rows.items() if r["eligible"])
    edges, flags, count = [], Counter(), 0
    with (out / "heat_cross_house_pair_ledger.csv").open("x", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["event_a", "event_b", "matched", "mismatch_reasons", "same_source_round"])
        for left, right in combinations(eligible, 2):
            a, b = rows[left], rows[right]
            if a["household"] == b["household"]:
                continue
            count += 1
            reasons = heat_mismatch(a, b)
            same_round = a["hs_index"] == b["hs_index"] and a["intervention_indicator"] == b["intervention_indicator"]
            writer.writerow([left, right, int(not reasons), "|".join(reasons), int(same_round)])
            flags.update(reasons)
            if not reasons:
                edges.append((left, right))
    return eligible, edges, {"eligible_cross_house_pairs": count, "nonexclusive_pair_mismatch_counts": dict(flags)}


def review_pairs(rows, edges):
    ordered = sorted(edges, key=lambda edge: rank("t1-heat-pair-v1", *edge))
    picked, covered, per_event = [], set(), Counter()
    while len(picked) < 12:
        available = [edge for edge in ordered if edge not in picked and all(per_event[k] < 2 for k in edge)]
        if not available:
            break
        edge = max(available, key=lambda e: len({rows[k]["household"] for k in e} - covered))
        picked.append(edge)
        covered.update(rows[k]["household"] for k in edge)
        per_event.update(edge)
    return picked


def triples_and_folds(rows, edges):
    adjacency = defaultdict(set)
    for a, b in edges:
        adjacency[a].add(b)
        adjacency[b].add(a)
    triples, by_fold = [], defaultdict(list)
    for a, b in edges:
        for c in sorted(k for k in adjacency[a] & adjacency[b] if k > b):
            events = (a, b, c)
            homes = tuple(sorted(rows[k]["household"] for k in events))
            assert len(set(homes)) == 3
            order = sorted(events, key=lambda k: rank("t1-heat-query-v1", k))
            triple = {"households": homes, "query": order[0], "candidate_a": order[1], "candidate_b": order[2]}
            triples.append(triple)
            by_fold[homes].append(triple)
    info = []
    for homes, group in sorted(by_fold.items()):
        distinct = len({r["query"] for r in group})
        info.append({"households": homes, "triples": len(group), "queries": distinct,
                     "meets_per_fold_gate": len(group) >= 4 and distinct >= 4})
    partitions = [()]
    for count in range(1, 4):
        for partition in combinations(info, count):
            if len(set(h for f in partition for h in f["households"])) == 3*count:
                partitions.append(partition)
    best = min(partitions, key=lambda folds: (-sum(f["meets_per_fold_gate"] for f in folds),
                                             -sum(f["triples"] for f in folds),
                                             tuple(f["households"] for f in folds)))
    return triples, info, list(best)


def acn_mismatch(a, b):
    x, y = a["subsequent_changes"], b["subsequent_changes"]
    if len(x) != len(y):
        return "different_stage_count"
    if bool(a["release"]) != bool(b["release"]):
        return "different_return_presence"
    if a["release"] and abs(a["release"]["relative_s"]-b["release"]["relative_s"]) > 30:
        return "return_time"
    if abs(a["old_limit_A"]-b["old_limit_A"]) > 1 or abs(a["new_limit_A"]-b["new_limit_A"]) > 1:
        return "anchor_levels"
    da = a["new_limit_A"]-a["old_limit_A"]
    db = b["new_limit_A"]-b["old_limit_A"]
    if abs(da-db) > 1:
        return "anchor_amplitude"
    ax = [0, *(e["relative_s"] for e in x), 1800]
    bx = [0, *(e["relative_s"] for e in y), 1800]
    for i, (u, v) in enumerate(zip(x, y), 1):
        au, bv = u["new_A"]-u["old_A"], v["new_A"]-v["old_A"]
        if au*bv <= 0 or abs(au-bv) > 1:
            return "later_direction_or_amplitude"
        if abs(u["old_A"]-v["old_A"]) > 1 or abs(u["new_A"]-v["new_A"]) > 1:
            return "later_levels"
        if abs(ax[i]-bx[i]) > 30:
            return "later_time"
    if any(abs((a1-a0)-(b1-b0)) > 45 for a0, a1, b0, b1 in zip(ax, ax[1:], bx, bx[1:])):
        return "stage_length"
    return None


def acn_graph(out, ledger):
    results, unmatched = {}, {}
    with (out / "acn_control_matches.csv").open("x", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["role", "session_a", "session_b", "user_a", "user_b", "later_changes", "has_return"])
        for role in ("training", "validation"):
            assigned = [r for r in ledger if r["role"] == role]
            core = [r for r in assigned if r.get("core") and not r["core"]["issues"]]
            sessions, users, later_users, reasons = set(), set(), set(), Counter()
            match_count, multistep, cross = 0, 0, 0
            for a, b in combinations(core, 2):
                if a["user"] == b["user"]:
                    continue
                cross += 1
                failed = acn_mismatch(a, b)
                if failed:
                    reasons[failed] += 1
                    continue
                count = len(a["subsequent_changes"])
                writer.writerow([role, a["session"], b["session"], a["user"], b["user"], count, int(bool(a["release"]))])
                sessions.update([a["session"], b["session"]])
                users.update([a["user"], b["user"]])
                match_count += 1
                if count:
                    multistep += 1
                    later_users.update([a["user"], b["user"]])
            unmatched[role] = [{"session": r["session"], "user": r["user"]} for r in core
                               if r["session"] not in sessions]
            results[role] = {
                "all_sessions": len(assigned), "all_users": len({r["user"] for r in assigned}),
                "complete_core_sessions": len(core), "complete_core_users": len({r["user"] for r in core}),
                "cross_user_pairs_screened": cross, "matched_pairs": match_count,
                "matched_sessions": len(sessions), "matched_users": len(users),
                "unmatched_complete_sessions": len(core)-len(sessions),
                "unmatched_complete_users": len({r["user"] for r in core}-users),
                "matched_multistep_pairs": multistep, "matched_multistep_users": len(later_users),
                "first_failure_counts": reasons,
                "meets_backup_gate": match_count >= 10 and len(users) >= 10 and multistep >= 3,
            }
    save(out / "acn_unmatched_complete.json", unmatched)
    return results


def export_pairs(blind, picked, curves):
    case_ids = []
    for i, pair in enumerate(picked, 1):
        case = f"M{i:02d}"
        case_ids.append(case)
        fig, axes = plt.subplots(2, 1, sharex=True, sharey=True, figsize=(10.5, 4.8), layout="constrained")
        for ax, label, key in zip(axes, "AB", pair):
            frame = curves[key]
            frame.to_csv(blind / f"{case}_{label}.csv", index=False)
            t = frame.relative_s.to_numpy()
            p = frame.hp_p.to_numpy()
            assert len(t) >= 2 and np.isfinite(p).all() and np.all((np.diff(t) > 0) & (np.diff(t) <= 450))
            ax.plot(t/3600, p, "o-", ms=2.5, lw=1, color="#17679a")
            ax.set_ylabel(f"{label} (W)")
            ax.grid(alpha=.23)
        axes[-1].set(xlim=(0, 6), xlabel="Hours from recorded stop")
        fig.suptitle(f"{case}   |   Native heat-pump power")
        fig.savefig(blind / f"{case}.png", dpi=130)
        plt.close(fig)
    links = "\n".join(f'<h2>{c}</h2><a href="{c}_A.csv">A points</a> · <a href="{c}_B.csv">B points</a>'
                      f'<p><img src="{c}.png" style="max-width:100%" alt="{c}"></p>' for c in case_ids)
    (blind / "index.html").write_text(
        '<!doctype html><html lang="zh"><meta charset="utf-8"><title>T1 匹配后原点</title>'
        '<h1>T1 固定可比对 · 停止后6小时</h1>' + links + "</html>\n", encoding="utf-8")


def main():
    assert digest((HERE / "T1_RULES.md").read_bytes()) == RULES_SHA
    old_freeze = read(T0 / "pack_freeze.json")
    assert digest(HEAT.read_bytes()) == old_freeze["source_heat_zip_sha256"]
    assert digest(ACN.read_bytes()) == old_freeze["source_acn_ledger_sha256"]
    heat_input = T0 / "heat_event_ledger.json"
    provenance, blind = HERE / "provenance", HERE / "blind_pairs"
    provenance.mkdir(exist_ok=False)
    blind.mkdir(exist_ok=False)
    rows, curves = heat_events(read(heat_input))
    eligible, edges, audit = heat_graph(rows, provenance)
    picked = review_pairs(rows, edges)
    triples, folds, chosen = triples_and_folds(rows, edges)
    used = set(k for pair in edges for k in pair)
    pair_hh = lambda edges: len({rows[k]["household"] for edge in edges for k in edge})
    audit.update({
        "events": len(rows), "households": len({r["household"] for r in rows.values()}),
        "eligible_events": len(eligible), "eligible_households": len({rows[k]["household"] for k in eligible}),
        "ineligibility_reasons": Counter(i for r in rows.values() for i in r["issues"]),
        "all_matches": len(edges), "matched_households": pair_hh(edges), "matched_events": len(used),
        "same_source_round_matches": sum(rows[a]["hs_index"] == rows[b]["hs_index"] and
                                         rows[a]["intervention_indicator"] == rows[b]["intervention_indicator"]
                                         for a, b in edges),
        "unmatched_eligible": sorted(set(eligible)-used),
        "review_pairs": len(picked), "review_households": pair_hh(picked),
        "review_events": len({k for pair in picked for k in pair}),
        "review_events_seen_t0": sorted({k for pair in picked for k in pair if rows[k]["seen_t0_pack"]}),
        "triples": len(triples), "three_household_groups": folds, "best_disjoint_folds": chosen,
        "meets_pair_support": len(picked) >= 8 and pair_hh(picked) >= 6,
        "meets_fold_support": sum(f["meets_per_fold_gate"] for f in chosen) >= 2 and
                              sum(f["triples"] for f in chosen if f["meets_per_fold_gate"]) >= 12,
    })
    save(provenance / "heat_events.json", rows)
    save(provenance / "heat_accepted_pairs_and_triples.json", {
        "edges": edges, "review_mapping": {f"M{i:02d}": pair for i, pair in enumerate(picked, 1)},
        "triples": triples})
    save(provenance / "matching_summary.json", {"heat": audit, "acn": acn_graph(provenance, read(ACN))})
    export_pairs(blind, picked, curves)
    save(provenance / "pre_review_freeze.json", {
        "rules_sha256": RULES_SHA, "builder_sha256": digest(Path(__file__).read_bytes()),
        "input_sha256": {p.relative_to(WORK).as_posix(): digest(p.read_bytes()) for p in (HEAT, heat_input, ACN)},
        "frozen_outputs_sha256": {p.relative_to(HERE).as_posix(): digest(p.read_bytes())
                                  for d in (blind, provenance) for p in sorted(d.iterdir()) if p.is_file()},
        "models_fitted": 0, "used_old_confirmation": False,
    })
    print(f"Frozen {len(picked)} heat review pairs and {len(triples)} available triples.")


if __name__ == "__main__":
    main()
