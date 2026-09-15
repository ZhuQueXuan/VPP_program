#!/usr/bin/env python3
"""Evaluate the rule-gated shortest-board method on a reproducible benchmark.

The benchmark validates deterministic rule logic and failure handling. It is
not a substitute for external validation on Shandong dispatch-response data.
"""

from __future__ import annotations

import csv
import json
import math
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "market_rule_parameters.csv"
OUTPUT = ROOT / "results" / "algorithm_evaluation_v1"

RESOURCES = [
    (1, "分布式光伏", "forecast_or_green_eligibility"),
    (2, "蓄热锅炉", "thermal_supply_constraint"),
    (3, "冷水机组", "temperature_and_rebound_constraint"),
    (4, "冷库", "product_temperature_constraint"),
    (5, "辅助泵类", "liquid_level_or_process_constraint"),
    (6, "高压电机泵", "vfd_or_restart_constraint"),
    (7, "空调", "comfort_and_rebound_constraint"),
    (8, "充电桩（充电站）", "connection_authorization_and_target_soc"),
    (9, "水泥（球磨机）", "inventory_and_minimum_on_off_constraint"),
    (10, "中频电炉", "batch_stage_and_quality_constraint"),
    (11, "电窑炉", "thermal_process_and_quality_constraint"),
    (12, "储能", "soc_and_energy_constraint"),
    (13, "算力", "sla_and_task_deadline_constraint"),
    (14, "搅拌机", "batch_interruptibility_constraint"),
    (15, "烘干机（热泵）", "moisture_and_deadline_constraint"),
    (16, "压机（液压/油压/水压）", "cycle_stage_and_interlock_constraint"),
]

MARKET_METRICS = {
    "spot_fit": ["power", "energy", "duration"],
    "frequency_fit": ["bidirectional_power", "bidirectional_energy", "response", "ramp", "tracking"],
    "ramping_fit": ["power", "energy", "response", "ramp"],
    "green_supply_fit": ["eligible_green_energy"],
    "green_consumption_fit": ["shift_power", "shift_energy"],
}


def applicable_outputs(resource_id: int) -> list[str]:
    outputs = ["spot_fit", "frequency_fit", "reserve_readiness", "ramping_fit"]
    if resource_id == 1:
        outputs.append("green_supply_fit")
    else:
        outputs.append("green_consumption_fit")
    return outputs


def make_cases() -> list[dict]:
    rows: list[dict] = []
    case_id = 0
    for resource_id, resource_name, constraint_name in RESOURCES:
        for output_name in applicable_outputs(resource_id):
            if output_name == "reserve_readiness":
                case_id += 1
                rows.append({
                    "case_id": f"C{case_id:04d}", "resource_id": resource_id,
                    "resource_name": resource_name, "output_name": output_name,
                    "case_type": "market_not_open", "specific_constraint": constraint_name,
                    "gate_evidence": "complete", "specific_constraint_pass": True,
                    "metric_ratios": "1.15", "expected_status": "not_open",
                    "expected_feasible": "not_computable", "expected_bottleneck": "market_status",
                    "evidence_type": "constructed_rule_benchmark",
                })
                continue

            metrics = MARKET_METRICS[output_name]
            variants = [
                ("fully_capable", [1.15] * len(metrics), "complete", True, "pass", 1),
                ("primary_capability_shortfall", [0.65] + [1.15] * (len(metrics) - 1), "complete", True, "pass", 0),
                ("secondary_constraint_shortfall", [1.15] * max(1, len(metrics) - 1) + ([0.65] if len(metrics) > 1 else []), "complete", True, "pass", 0),
                ("resource_specific_constraint_failure", [1.15] * len(metrics), "complete", False, "fail", 0),
                ("missing_required_evidence", [1.15] * len(metrics), "missing", True, "pending_evidence", "not_computable"),
            ]
            for case_type, ratios, evidence, constraint_pass, expected_status, expected_feasible in variants:
                case_id += 1
                # One-metric markets cannot have a different secondary metric.
                if case_type == "secondary_constraint_shortfall" and len(metrics) == 1:
                    ratios = [0.65]
                expected_bottleneck = (
                    constraint_name if expected_status == "fail"
                    else "missing_evidence" if expected_status == "pending_evidence"
                    else metrics[min(range(len(ratios)), key=ratios.__getitem__)]
                )
                rows.append({
                    "case_id": f"C{case_id:04d}", "resource_id": resource_id,
                    "resource_name": resource_name, "output_name": output_name,
                    "case_type": case_type, "specific_constraint": constraint_name,
                    "gate_evidence": evidence, "specific_constraint_pass": constraint_pass,
                    "metric_ratios": "|".join(f"{x:.2f}" for x in ratios),
                    "metric_names": "|".join(metrics), "expected_status": expected_status,
                    "expected_feasible": expected_feasible, "expected_bottleneck": expected_bottleneck,
                    "evidence_type": "constructed_rule_benchmark",
                })
    return rows


def candidate_predict(row: dict) -> dict:
    if row["output_name"] == "reserve_readiness":
        return {"status": "not_open", "feasible": "not_computable", "score": "not_computable", "bottleneck": "market_status"}
    if row["gate_evidence"] != "complete":
        return {"status": "pending_evidence", "feasible": "not_computable", "score": "not_computable", "bottleneck": "missing_evidence"}
    if not row["specific_constraint_pass"]:
        return {"status": "fail", "feasible": 0, "score": 0.0, "bottleneck": row["specific_constraint"]}
    ratios = [float(x) for x in row["metric_ratios"].split("|")]
    names = row.get("metric_names", "power").split("|")
    idx = min(range(len(ratios)), key=ratios.__getitem__)
    return {"status": "pass", "feasible": int(min(ratios) >= 1.0), "score": round(min(ratios) * 100, 2), "bottleneck": names[idx]}


def baseline_predict(row: dict, method: str) -> dict:
    if row["output_name"] == "reserve_readiness":
        return {"status": "not_open", "feasible": "not_computable", "score": "not_computable", "bottleneck": "market_status"}
    ratios = [float(x) for x in row["metric_ratios"].split("|")]
    if method == "capacity_only":
        score = ratios[0] * 100
        bottleneck = row.get("metric_names", "power").split("|")[0]
    elif method == "equal_weight_average":
        score = sum(ratios) / len(ratios) * 100
        bottleneck = "average_score"
    else:
        raise ValueError(method)
    # Baselines intentionally do not model missing evidence or resource-specific hard gates.
    return {"status": "pass", "feasible": int(score >= 100), "score": round(score, 2), "bottleneck": bottleneck}


def classification_metrics(pairs: list[tuple[int, int]]) -> dict[str, float]:
    tp = sum(y == 1 and p == 1 for y, p in pairs)
    tn = sum(y == 0 and p == 0 for y, p in pairs)
    fp = sum(y == 0 and p == 1 for y, p in pairs)
    fn = sum(y == 1 and p == 0 for y, p in pairs)
    n = len(pairs)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "evaluated_cases": n, "tp": tp, "tn": tn, "fp": fp, "fn": fn,
        "accuracy": (tp + tn) / n if n else math.nan,
        "precision": precision, "recall": recall, "f1": f1,
        "false_commitment_rate": fp / (tp + fp) if tp + fp else 0.0,
        "missed_opportunity_rate": fn / (tp + fn) if tp + fn else 0.0,
    }


def compare_methods(cases: list[dict]) -> tuple[list[dict], list[dict]]:
    detailed: list[dict] = []
    summary: list[dict] = []
    methods = ["capacity_only", "equal_weight_average", "rule_gated_shortest_board"]
    for method in methods:
        labeled_pairs: list[tuple[int, int]] = []
        status_correct = 0
        status_total = 0
        bottleneck_correct = 0
        bottleneck_total = 0
        for row in cases:
            pred = candidate_predict(row) if method == "rule_gated_shortest_board" else baseline_predict(row, method)
            expected = row["expected_feasible"]
            if expected != "not_computable":
                labeled_pairs.append((int(expected), int(pred["feasible"])))
            status_total += 1
            status_correct += pred["status"] == row["expected_status"]
            if method == "rule_gated_shortest_board" and expected != "not_computable" and int(expected) == 0:
                bottleneck_total += 1
                bottleneck_correct += pred["bottleneck"] == row["expected_bottleneck"]
            detailed.append({
                **row, "method": method, "predicted_status": pred["status"],
                "predicted_feasible": pred["feasible"], "predicted_score": pred["score"],
                "predicted_bottleneck": pred["bottleneck"],
                "status_correct": pred["status"] == row["expected_status"],
                "feasibility_correct": "not_evaluated" if expected == "not_computable" else int(pred["feasible"]) == int(expected),
            })
        metrics = classification_metrics(labeled_pairs)
        metrics.update({
            "method": method,
            "status_accuracy": status_correct / status_total,
            "bottleneck_accuracy": (bottleneck_correct / bottleneck_total) if bottleneck_total else "not_evaluated",
            "evaluation_scope": "constructed_rule_benchmark",
        })
        summary.append(metrics)
    return detailed, summary


def load_config() -> dict[str, dict]:
    with CONFIG.open(encoding="utf-8-sig", newline="") as handle:
        return {row["parameter_id"]: row for row in csv.DictReader(handle)}


def apply_operator(value: float, operator: str, threshold: float) -> bool:
    return {"<": value < threshold, "<=": value <= threshold, ">=": value >= threshold, "=": value == threshold}[operator]


def evaluate_rule_boundaries(config: dict[str, dict]) -> list[dict]:
    specs = [
        ("vpp.storage.min_aggregate_capacity", [0.99, 1.00, 1.01], [False, True, True]),
        ("vpp.storage.spot.min_continuous_duration", [1.99, 2.00, 2.01], [False, True, True]),
        ("vpp.storage.aux.min_continuous_duration", [14.9, 15.0, 15.1], [False, True, True]),
        ("vpp.adjustable_load.min_adjustable_capacity", [0.99, 1.00, 1.01], [False, True, True]),
        ("vpp.adjustable_load.min_continuous_duration", [0.99, 1.00, 1.01], [False, True, True]),
        ("frequency.agc.thermal_response_time", [59.9, 60.0, 60.1], [True, False, False]),
        ("frequency.agc.hydro_response_time", [19.9, 20.0, 20.1], [True, False, False]),
        ("frequency.agc.allowed_deviation_ratio", [0.99, 1.00, 1.01], [True, True, False]),
    ]
    rows = []
    for parameter_id, values, expected in specs:
        rule = config[parameter_id]
        threshold = float(rule["value"])
        for value, expected_pass in zip(values, expected):
            actual_pass = apply_operator(value, rule["operator"], threshold)
            rows.append({
                "parameter_id": parameter_id, "test_value": value, "unit": rule["unit"],
                "operator": rule["operator"], "threshold": threshold,
                "expected_pass": expected_pass, "actual_pass": actual_pass,
                "correct": expected_pass == actual_pass, "source_clause": rule["source_clause"],
            })
    return rows


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def create_chart(summary: list[dict]) -> None:
    method_labels = ["Capacity only", "Equal-weight average", "Rule gate + shortest board"]
    metric_specs = [("accuracy", "Accuracy", "#4C78A8"), ("f1", "F1", "#59A14F"),
                    ("false_commitment_rate", "False commitment", "#E15759")]
    width, height = 1040, 560
    plot_left, plot_top, plot_height = 90, 90, 360
    group_width, bar_width, gap = 290, 54, 12
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="520" y="38" text-anchor="middle" font-family="Arial" font-size="22" font-weight="bold">Constructed rule benchmark: method comparison</text>',
    ]
    for tick in range(0, 101, 20):
        y = plot_top + plot_height - tick / 100 * plot_height
        parts.append(f'<line x1="{plot_left}" y1="{y:.1f}" x2="1000" y2="{y:.1f}" stroke="#DDDDDD"/>')
        parts.append(f'<text x="75" y="{y+5:.1f}" text-anchor="end" font-family="Arial" font-size="12">{tick}</text>')
    for method_idx, (row, method_label) in enumerate(zip(summary, method_labels)):
        group_x = 135 + method_idx * group_width
        for metric_idx, (key, _, color) in enumerate(metric_specs):
            value = float(row[key]) * 100
            x = group_x + metric_idx * (bar_width + gap)
            bar_h = value / 100 * plot_height
            y = plot_top + plot_height - bar_h
            parts.append(f'<rect x="{x}" y="{y:.1f}" width="{bar_width}" height="{bar_h:.1f}" fill="{color}"/>')
            parts.append(f'<text x="{x+bar_width/2:.1f}" y="{max(78, y-7):.1f}" text-anchor="middle" font-family="Arial" font-size="11">{value:.1f}</text>')
        parts.append(f'<text x="{group_x+96}" y="480" text-anchor="middle" font-family="Arial" font-size="13">{method_label}</text>')
    for idx, (_, label, color) in enumerate(metric_specs):
        x = 300 + idx * 190
        parts.append(f'<rect x="{x}" y="515" width="16" height="16" fill="{color}"/>')
        parts.append(f'<text x="{x+23}" y="528" font-family="Arial" font-size="13">{label}</text>')
    parts.append('</svg>')
    (OUTPUT / "method_comparison.svg").write_text("\n".join(parts), encoding="utf-8")


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    cases = make_cases()
    detailed, summary = compare_methods(cases)
    boundary = evaluate_rule_boundaries(load_config())
    write_csv(OUTPUT / "benchmark_cases.csv", cases)
    write_csv(OUTPUT / "case_results.csv", detailed)
    write_csv(OUTPUT / "method_comparison.csv", summary)
    write_csv(OUTPUT / "rule_boundary_results.csv", boundary)
    create_chart(summary)

    candidate = next(x for x in summary if x["method"] == "rule_gated_shortest_board")
    baseline_best = max((x for x in summary if x["method"] != "rule_gated_shortest_board"), key=lambda x: x["f1"])
    result = {
        "status": "pass",
        "benchmark_type": "constructed_rule_benchmark",
        "resource_class_count": len(RESOURCES),
        "case_count": len(cases),
        "market_output_counts": dict(Counter(row["output_name"] for row in cases)),
        "rule_boundary_case_count": len(boundary),
        "rule_boundary_accuracy": sum(row["correct"] for row in boundary) / len(boundary),
        "candidate_metrics": candidate,
        "best_baseline_method": baseline_best["method"],
        "best_baseline_f1": baseline_best["f1"],
        "external_real_data_accuracy": "not_computable",
        "acceptance_90_percent_claim": "not_met_or_tested",
        "reason": "No Shandong dispatch-response ground truth is available; this run validates rule logic only.",
    }
    with (OUTPUT / "evaluation_summary.json").open("w", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
