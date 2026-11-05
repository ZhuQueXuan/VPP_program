"""Verify saved scores and inspect two raw counterexamples without rescanning a cohort."""

import csv
import gzip
import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from statistics import mean, median


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def load(name):
    return json.loads((HERE / name).read_text(encoding="utf8"))


def digest(name):
    return hashlib.sha256((HERE / name).read_bytes()).hexdigest()


def check_counterexample(result, session_id, line):
    session = next(row for row in result["sessions"] if row["session"] == session_id)
    row = next(r for r in result["windows"] if (r["session"], r["edge_line"]) == (session_id, line))
    t = datetime.fromisoformat(row["edge_utc"])
    fields = ("Actual Pilot (A)", "Charging Current (A)", "Power (kW)")
    points = []
    with gzip.open(ROOT / session["source"], "rt", encoding="utf8", newline="") as stream:
        for number, point in enumerate(csv.DictReader(stream), 2):
            delta = (datetime.fromisoformat(point[""]) - t).total_seconds()
            if -60 <= delta <= 30:
                points.append((number, delta, *(float(point[field]) for field in fields)))
    edges = [point[2] for point in points if point[0] in {row["previous_pilot_line"], line}]
    assert edges == row["anchor_pilot_A"]
    early = [point[3:] for point in points if -60 <= point[1] <= -35]
    reference = [point[3:] for point in points if -28 <= point[1] <= -5]
    assert all(math.isclose(median(column), expected, abs_tol=1e-12)
               for column, expected in zip(zip(*early), row["early"]))
    baseline = [median(column) for column in zip(*reference)]
    assert all(math.isclose(value, expected, abs_tol=1e-12)
               for value, expected in zip(baseline, row["baseline"]))
    post = [point for point in points if 0 <= point[1] <= 30]
    flags = [baseline[0] - point[3] >= 1 and baseline[1] - point[4] >= .2 for point in post]
    first = next((i for i in range(len(flags) - 1) if flags[i] and flags[i + 1]), None)
    assert (first is not None) == row["joint"]
    if first is not None:
        assert post[first][1] == row["delay_range_s"][1]
        assert post[first + 1][1] == row["confirmation_s"]
    return {"session": session_id, "edge_line": line, "raw_points_verified": len(points)}


def verify():
    freeze = load("freeze.json")
    assert freeze["hashes"] == {key: digest(key) for key in freeze["hashes"]}
    assert freeze["training_output_sha256"] == digest("training.json")
    roles = {}
    details = {}
    for role in ("training", "validation"):
        data = load(f"{role}.json")
        roles[role] = data
        assert data["role"] == role and data["hashes"] == freeze["hashes"]
        rows, summary = data["windows"], data["summary"]
        assert len({(row["session"], row["edge_line"]) for row in rows}) == len(rows)
        counts = Counter(row["status"] for row in rows)
        assert counts == {key: value["windows"] for key, value in summary["status"].items()}
        assert Counter(row["session"] for row in rows) == Counter({
            s["session"]: s["candidate_windows"] for s in data["sessions"] if s["candidate_windows"]
        })
        included = [row for row in rows if row["status"] == "included"]
        rates = []
        for group in ("below", "above"):
            selected = [row for row in included if row["group"] == group]
            out = summary["groups"][group]
            assert out["windows"] == len(selected)
            assert out["users"] == len({r["user"] for r in selected})
            assert out["sessions"] == len({r["session"] for r in selected})
            for field in ("joint", "current", "power"):
                assert out[f"{field}_hits"] == sum(row[field] for row in selected)
            assert out["placebo_status_counts"] == Counter(r["placebo"]["status"] for r in selected)
            assert out["placebo_joint_hits"] == sum(
                row["placebo"]["joint"] for row in selected if row["placebo"]["status"] == "included"
            )
            rates.append(mean(row["joint"] for row in selected))
        assert math.isclose(rates[0] - rates[1], summary["primary_contrast"]["difference"])
        for key in ("session", "user"):
            pairs = defaultdict(lambda: defaultdict(list))
            for row in included:
                pairs[row[key]][row["group"]].append(row["joint"])
            deltas = [mean(v["below"]) - mean(v["above"]) for v in pairs.values() if len(v) == 2]
            assert len(deltas) == summary[f"within_{key}"]["groups"]
            assert math.isclose(mean(deltas), summary[f"within_{key}"]["mean_difference"])
        details[role] = {"windows_checked": len(rows), "summary_rates_recomputed": rates,
                         "sessions": len(data["sessions"]), "output_sha256": digest(f"{role}.json")}
    assert not ({r["user"] for r in roles["training"]["sessions"]}
                & {r["user"] for r in roles["validation"]["sessions"]})
    gate = roles["validation"]["summary"]["primary_contrast"]
    group_sizes = roles["validation"]["summary"]["groups"]
    protocol = load("protocol.json")
    assert gate["gate"] == (
        min(r["users"] for r in group_sizes.values()) >= protocol["validation_gate_min_users_per_group"]
        and gate["difference"] >= protocol["validation_gate_min_difference"]
        and gate["user_cluster_percentiles"][0] > 0
    )
    examples = [
        check_counterexample(roles["training"], "2_39_126_560_2020-01-27 16:37:04.852939", 3116),
        check_counterexample(roles["validation"], "2_39_124_22_2020-01-28 17:18:06.961681", 529),
    ]
    return {"status": "passed", "frozen_inputs_verified": True, "no_user_overlap": True,
            "roles": details, "counterexamples": examples, "validation_gate_verified": gate["gate"]}


if __name__ == "__main__":
    print(json.dumps(verify(), indent=2))
