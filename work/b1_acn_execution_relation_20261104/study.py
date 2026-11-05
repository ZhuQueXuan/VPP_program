"""One pre-specified ACN execution contrast, without treatment effect identification."""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ACN = ROOT / "data/ACN_real_user_benchmark_v1_20261102"
META = ROOT / "work/b1_real_training_data_20261102/source_documents/acn_official_Caltech_2020.json"
COLUMNS = ["Actual Pilot (A)", "Charging Current (A)", "Power (kW)"]
GROUPS = ("below", "above")
P = json.loads((HERE / "protocol.json").read_text(encoding="utf8"))


def read_json(path):
    return json.loads(path.read_text(encoding="utf8"))


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    with path.open("x", encoding="utf8") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def samples(times, values, t, low, high):
    start, end = t + low, t + high
    i = np.searchsorted(times, start, side="left")
    j = np.searchsorted(times, end, side="right")
    return times[i:j], values[i:j]


def data_problem(times, x, t, low, high):
    # Timestamp and channel failures remain distinct from a genuine no-follow result.
    if not np.isfinite(x).all():
        return "missing_channel"
    gaps = np.diff(times)
    if (gaps <= 0).any():
        return "duplicate_time"
    if len(times) < P["min_points_per_window"]:
        return "too_few_points"
    if max(times[0] - (t + low), t + high - times[-1], gaps.max()) > P["max_gap_s"]:
        return "irregular_gap"
    return None


def measure(t, post_t, post, baseline, last_pre_t, last_pre):
    current_drop = baseline[0] - post[:, 1]
    power_drop = baseline[1] - post[:, 2]
    current = current_drop >= P["drop_current_A"]
    power = power_drop >= P["drop_power_kW"]
    joint = current & power
    hits = np.flatnonzero(joint[:-1] & joint[1:])
    first = int(hits[0]) if len(hits) else None
    left_censored = first == 0 and bool(
        (baseline - last_pre >= [P["drop_current_A"], P["drop_power_kW"]]).all()
    )
    return {
        "joint": first is not None,
        "current": bool((current[:-1] & current[1:]).any()),
        "power": bool((power[:-1] & power[1:]).any()),
        "delay_range_s": (
            [None if left_censored else float((post_t[first - 1] if first else last_pre_t) - t),
             float(post_t[first] - t)]
            if first is not None else None
        ),
        "confirmation_s": float(post_t[first + 1] - t) if first is not None else None,
        "post_median_drop": [float(np.median(current_drop)), float(np.median(power_drop))],
    }


def window(times, values, index, disconnect, drop_index=None):
    t = times[index]
    group_low, group_high = P["group_window_s"]
    base_low, base_high = P["baseline_window_s"]
    post_low, post_high = P["post_window_s"]
    result = {}
    if t + group_low < times[0]:
        return result | {"status": "start_boundary"}
    if t + post_high >= disconnect:
        return result | {"status": "session_end_or_unplug"}
    if t + post_high > times[-1]:
        return result | {"status": "trace_end_before_post_window"}

    block_t, block = samples(times, values, t, group_low, post_high)
    error = data_problem(block_t, block, t, group_low, post_high)
    if error:
        return result | {"status": error}
    middle = np.searchsorted(block_t, t)
    if drop_index is not None:
        if times[drop_index] >= t or t - times[drop_index] > P["max_gap_s"]:
            return result | {"status": "pilot_edge_time_ambiguous"}
        old, new = values[drop_index, 0], values[index, 0]
    else:
        old = new = values[index, 0]
    if (np.max(np.abs(block[:middle, 0] - old)) > P["pilot_stability_A"]
            or np.max(np.abs(block[middle:, 0] - new)) > P["pilot_stability_A"]):
        return result | {"status": "overlapping_pilot_change"}

    intervals = [(group_low, group_high), (base_low, base_high), (post_low, post_high)]
    sections = [samples(times, values, t, a, b) for a, b in intervals]
    for (a, b), (stamps, x) in zip(intervals, sections):
        error = data_problem(stamps, x, t, a, b)
        if error:
            return result | {"status": error}
    (_, early), (_, baseline_points), (post_t, post) = sections
    pre = early[:, 1:]
    late = baseline_points[:, 1:]
    early_median = np.median(pre, axis=0)
    baseline = np.median(late, axis=0)
    pre_shift = baseline - early_median
    if (np.maximum(np.ptp(pre, axis=0), np.ptp(late, axis=0))
            > [P["pre_current_range_A"], P["pre_power_range_kW"]]).any():
        return result | {"status": "unstable_pre"}
    if (np.abs(pre_shift) > [P["pre_median_shift_max_A"], P["pre_median_shift_max_kW"]]).any():
        return result | {"status": "pre_trend_exceeds_limit"}
    if min(early_median[0], baseline[0]) < P["baseline_current_min_A"]:
        return result | {"status": "insufficient_pre_current"}

    result = {
        "status": "included", "early": early_median.tolist(), "baseline": baseline.tolist(),
        "pre_shift": pre_shift.tolist(), "old_pilot_A": float(old), "new_pilot_A": float(new),
    }
    if drop_index is not None:
        margins = np.array([early_median[0], baseline[0]]) - new
        # Use disjoint early points for grouping. The later window is only a stability check.
        if margins[0] >= P["group_margin_A"] and margins[1] > 0:
            group = "below"
        elif margins[0] <= -P["group_margin_A"] and margins[1] < 0:
            group = "above"
        else:
            return result | {"status": "boundary_margin"}
        result.update(group=group, pilot_edge_range_s=[float(times[drop_index] - t), 0.0])
    return result | measure(t, post_t, post, baseline, block_t[middle - 1], block[middle - 1, 1:])


def scan(entry, disconnect):
    path = ROOT / entry["local"]
    try:
        frame = pd.read_csv(path, usecols=["Unnamed: 0"] + COLUMNS)
    except (OSError, EOFError, ValueError) as error:
        return type(error).__name__, []
    utc = pd.to_datetime(frame["Unnamed: 0"], format="mixed", utc=True, errors="coerce")
    if utc.isna().any() or not utc.is_monotonic_increasing:
        return "invalid_or_nonmonotone_time", []
    times = utc.astype("int64").to_numpy() / 1e9
    values = frame[COLUMNS].apply(pd.to_numeric, errors="coerce").to_numpy()
    pilots = np.flatnonzero(np.isfinite(values[:, 0]))
    drops = np.flatnonzero(np.diff(values[pilots, 0]) <= -P["pilot_drop_A"])
    rows = []
    for drop in drops:
        before, edge = int(pilots[drop]), int(pilots[drop + 1])
        t = times[edge]
        record = {
            "session": entry["session_id"], "user": entry["user_group"], "station": entry["station_group"],
            "edge_utc": utc.iloc[edge].isoformat(), "edge_line": edge + 2, "previous_pilot_line": before + 2,
            "anchor_pilot_A": [float(values[before, 0]), float(values[edge, 0])],
        }
        result = window(times, values, edge, disconnect, before)
        if result["status"] == "included":
            target = t - P["placebo_shift_s"]
            offset = np.searchsorted(times, target, side="right") - 1
            if offset < 0 or target - times[offset] > P["max_gap_s"]:
                placebo = {"status": "no_nearby_placebo_anchor"}
            else:
                placebo = window(times, values, offset, disconnect)
                placebo["line"] = int(offset) + 2
            result["placebo"] = placebo
        rows.append(record | result)
    return "ok", rows


def counts(rows):
    return {"windows": len(rows), "sessions": len({row["session"] for row in rows}),
            "users": len({row["user"] for row in rows})}


def medians(rows, field):
    return np.median([row[field] for row in rows], axis=0).tolist() if rows else None


def paired(rows, key):
    data = pd.DataFrame(rows)
    if data.empty:
        return {"groups": 0, "mean_difference": None}
    rates = data.groupby([key, "group"])["joint"].mean().unstack().reindex(columns=GROUPS).dropna()
    return {"groups": len(rates),
            "mean_difference": float((rates.below - rates.above).mean()) if len(rates) else None}


def summarize(rows):
    good = [row for row in rows if row["status"] == "included"]
    summary = {}
    for group in GROUPS:
        used = [row for row in good if row["group"] == group]
        hits = [row for row in used if row["joint"]]
        placebo = [row["placebo"] for row in used if row["placebo"]["status"] == "included"]
        summary[group] = counts(used) | {
            "joint_hits": len(hits), "joint_rate": len(hits) / len(used) if used else None,
            "current_hits": sum(row["current"] for row in used),
            "power_hits": sum(row["power"] for row in used),
            "median_pre_early_A_kW": medians(used, "early"),
            "median_pre_shift_A_kW": medians(used, "pre_shift"),
            "median_post_drop_A_kW": medians(used, "post_median_drop"),
            "left_censored_delay": sum(row["delay_range_s"][0] is None for row in hits),
            "median_delay_bounds_s": medians(
                [row for row in hits if row["delay_range_s"][0] is not None], "delay_range_s"
            ),
            "median_confirmation_s": medians(hits, "confirmation_s"),
            "placebo_eligible": len(placebo), "placebo_joint_hits": sum(row["joint"] for row in placebo),
            "placebo_status_counts": dict(Counter(row["placebo"]["status"] for row in used)),
        }
    contrast = None
    if all(summary[group]["windows"] for group in GROUPS):
        data = pd.DataFrame(good)
        cells = data.groupby(["user", "group"])["joint"].agg(["sum", "size"]).unstack(fill_value=0)
        users = cells.shape[0]
        rng = np.random.default_rng(P["bootstrap_seed"])
        draw = rng.multinomial(users, np.full(users, 1 / users), size=P["bootstrap_draws"])
        numer = draw @ cells["sum"].loc[:, list(GROUPS)].to_numpy(dtype=float)
        denom = draw @ cells["size"].loc[:, list(GROUPS)].to_numpy(dtype=float)
        complete = (denom > 0).all(axis=1)
        rates = numer[complete] / denom[complete]
        interval = np.quantile(rates[:, 0] - rates[:, 1], [0.025, 0.975]).tolist()
        difference = summary["below"]["joint_rate"] - summary["above"]["joint_rate"]
        gate = (
            min(summary[group]["users"] for group in GROUPS) >= P["validation_gate_min_users_per_group"]
            and difference >= P["validation_gate_min_difference"]
            and interval[0] > 0
        )
        contrast = {"difference": difference, "user_cluster_percentiles": interval,
                    "complete_bootstrap_draws": int(complete.sum()), "gate": gate}
    return {
        "candidate_windows": counts(rows),
        "status": {status: counts([r for r in rows if r["status"] == status])
                   for status in sorted({row["status"] for row in rows})},
        "included": counts(good), "groups": summary, "primary_contrast": contrast,
        "within_session": paired(good, "session"), "within_user": paired(good, "user"),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("role", choices=("training", "validation"))
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    target = args.output.resolve()
    if target.parent != HERE or target.exists():
        parser.error("Specify a new output file inside this study directory.")
    hashes = {name: sha256(HERE / name) for name in ("study.py", "protocol.json")}
    if args.role == "validation":
        if read_json(HERE / "freeze.json")["hashes"] != hashes:
            raise ValueError("Frozen protocol or script differs.")
    manifest_path = ACN / f"{args.role}_sessions.json"
    manifest = read_json(manifest_path)
    assert all(item["split"] == args.role and item["site"] == "caltech" for item in manifest)
    assert len({item["session_id"] for item in manifest}) == len(manifest)
    by_id = {row["sessionID"]: row for row in read_json(META)["_items"]}
    sessions = []
    rows = []
    for item in manifest:
        disconnect = pd.Timestamp(by_id[item["session_id"]]["disconnectTime"]).timestamp()
        status, candidate_rows = scan(item, disconnect)
        sessions.append({"session": item["session_id"], "user": item["user_group"],
                         "source": item["local"], "status": status, "candidate_windows": len(candidate_rows)})
        rows.extend(candidate_rows)
    summary = summarize(rows) | {
        "manifest_sessions": len(sessions), "manifest_users": len({row["user"] for row in sessions}),
        "session_status_counts": dict(Counter(row["status"] for row in sessions)),
        "readable_sessions_without_candidate": sum(
            row["status"] == "ok" and not row["candidate_windows"] for row in sessions
        ),
    }
    write_json(target, {"role": args.role, "hashes": hashes, "manifest_sha256": sha256(manifest_path),
                       "metadata_sha256": sha256(META), "summary": summary, "sessions": sessions,
                       "windows": rows})
    print(json.dumps(summary, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
