#!/usr/bin/env python3
"""Validate simultaneous multi-market commitments for a resource portfolio."""

from __future__ import annotations

import copy
import json
from pathlib import Path

from run_dynamic_scoring_v1 import (
    ADAPTERS,
    EXAMPLES,
    admission,
    evaluate_official_gates,
    load_json,
    load_rules,
    market_statuses,
    resource_constraint_status,
    write_json,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "results" / "portfolio_allocation_v1"
CALCULATED_AT = "2026-09-15T10:50:00+08:00"
ENGINE_VERSION = "portfolio-allocation-v1.0"


def load_all_submissions() -> list[dict]:
    files = [
        "first_batch_resource_submissions.json",
        "thermal_resource_submissions.json",
        "pump_resource_submissions.json",
        "batch_resource_submissions.json",
        "compute_resource_submission.json",
    ]
    submissions = []
    for name in files:
        submissions.extend(load_json(EXAMPLES / name)["submissions"])
    return submissions


def merge_overrides(base: list[dict], overrides: list[dict]) -> list[dict]:
    rows = copy.deepcopy(base)
    by_key = {(row["task_id"], row["entity_id"]): row for row in rows}
    for override in overrides:
        key = (override["task_id"], override["entity_id"])
        if key not in by_key:
            rows.append(copy.deepcopy(override))
        else:
            by_key[key].update(override)
    return rows


def validate_allocation(portfolio: dict, submissions: list[dict], assignments: list[dict], scenario_id: str) -> dict:
    rules = load_rules()
    statuses = market_statuses(rules)
    tasks = {task["task_id"]: task for task in portfolio["tasks"]}
    entities = {item["entity"]["entity_id"]: item["entity"] for item in submissions}
    capabilities = {entity_id: ADAPTERS[entity["resource_type"]](entity) for entity_id, entity in entities.items()}

    task_results = []
    for task_id, task in tasks.items():
        task_rows = [row for row in assignments if row["task_id"] == task_id]
        assigned_up = sum(row["committed_up_power_mw"] for row in task_rows)
        assigned_down = sum(row["committed_down_power_mw"] for row in task_rows)
        direction = task["direction"]
        up_required = direction in {"up", "bidirectional"}
        down_required = direction in {"down", "bidirectional"}
        up_met = not up_required or assigned_up >= task["required_power_mw"]
        down_met = not down_required or assigned_down >= task["required_power_mw"]
        task_results.append({
            "task_id":task_id, "market_output":task["market_output"], "direction":direction,
            "required_power_mw":task["required_power_mw"], "assigned_up_power_mw":round(assigned_up, 6),
            "assigned_down_power_mw":round(assigned_down, 6), "up_requirement_met":up_met,
            "down_requirement_met":down_met, "task_requirement_met":up_met and down_met,
        })

    entity_results = []
    for entity_id in sorted({row["entity_id"] for row in assignments}):
        entity = entities[entity_id]
        cap = capabilities[entity_id]
        entity_rows = [row for row in assignments if row["entity_id"] == entity_id]
        committed_up_power = sum(row["committed_up_power_mw"] for row in entity_rows)
        committed_down_power = sum(row["committed_down_power_mw"] for row in entity_rows)
        committed_up_energy = sum(row["committed_up_power_mw"] * tasks[row["task_id"]]["duration_h"] for row in entity_rows)
        committed_down_energy = sum(row["committed_down_power_mw"] * tasks[row["task_id"]]["duration_h"] for row in entity_rows)
        constraint_status, constraint_failures = resource_constraint_status(entity)
        conflicts = list(constraint_failures)
        evaluated_rule_ids = []
        for row in entity_rows:
            output = tasks[row["task_id"]]["market_output"]
            qualification_status, qualification_failures = admission(entity, output)
            official_status, evaluated, official_failures = evaluate_official_gates(entity, cap, output, rules)
            evaluated_rule_ids.extend(evaluated)
            if statuses[output] != "operational":
                conflicts.append(f"portfolio_gate.{row['task_id']}.market_not_operational")
            if qualification_status != "pass":
                conflicts.extend(f"portfolio_gate.{row['task_id']}.{item}" for item in qualification_failures)
            if official_status != "pass":
                conflicts.extend(f"portfolio_gate.{row['task_id']}.{item}" for item in official_failures)
        if committed_up_power > (cap["available_up_power_mw"] or 0) + 1e-9:
            conflicts.append("portfolio_conflict.up_power_double_commitment")
        if committed_down_power > (cap["available_down_power_mw"] or 0) + 1e-9:
            conflicts.append("portfolio_conflict.down_power_double_commitment")
        if committed_up_energy > (cap["available_up_energy_mwh"] or 0) + 1e-9:
            conflicts.append("portfolio_conflict.up_energy_shortfall")
        if committed_down_energy > (cap["available_down_energy_mwh"] or 0) + 1e-9:
            conflicts.append("portfolio_conflict.down_energy_shortfall")
        entity_results.append({
            "entity_id":entity_id, "resource_type":entity["resource_type"],
            "available_up_power_mw":cap["available_up_power_mw"], "committed_up_power_mw":round(committed_up_power, 6),
            "available_down_power_mw":cap["available_down_power_mw"], "committed_down_power_mw":round(committed_down_power, 6),
            "available_up_energy_mwh":cap["available_up_energy_mwh"], "committed_up_energy_mwh":round(committed_up_energy, 6),
            "available_down_energy_mwh":cap["available_down_energy_mwh"], "committed_down_energy_mwh":round(committed_down_energy, 6),
            "specific_constraint_status":constraint_status, "conflicts":conflicts, "entity_allocation_feasible":not conflicts,
            "evaluated_rule_ids":sorted(set(evaluated_rule_ids)),
        })

    unknown_entities = sorted({row["entity_id"] for row in assignments} - set(entities))
    unknown_tasks = sorted({row["task_id"] for row in assignments} - set(tasks))
    negative_commitments = [row for row in assignments if row["committed_up_power_mw"] < 0 or row["committed_down_power_mw"] < 0]
    portfolio_feasible = (
        all(row["task_requirement_met"] for row in task_results)
        and all(row["entity_allocation_feasible"] for row in entity_results)
        and not unknown_entities and not unknown_tasks and not negative_commitments
    )
    return {
        "schema_version":"1.0", "scenario_id":scenario_id, "portfolio_id":portfolio["portfolio_id"],
        "calculated_at":CALCULATED_AT, "engine_version":ENGINE_VERSION, "evidence_status":portfolio["evidence_status"],
        "portfolio_feasible":portfolio_feasible, "task_results":task_results, "entity_results":entity_results,
        "unknown_entities":unknown_entities, "unknown_tasks":unknown_tasks, "negative_commitments":negative_commitments,
    }


def low_soc_submissions(submissions: list[dict]) -> list[dict]:
    changed = copy.deepcopy(submissions)
    for submission in changed:
        if submission["entity"]["entity_id"] == "BESS-DEMO-01":
            submission["entity"]["model_parameters"]["soc"] = 0.20
    return changed


def validation_summary(base: dict, overload: dict, low_soc: dict) -> dict:
    overload_bess = next(row for row in overload["entity_results"] if row["entity_id"] == "BESS-DEMO-01")
    low_soc_bess = next(row for row in low_soc["entity_results"] if row["entity_id"] == "BESS-DEMO-01")
    checks = {
        "base_plan_is_feasible": base["portfolio_feasible"],
        "base_tasks_are_all_fulfilled": all(row["task_requirement_met"] for row in base["task_results"]),
        "base_entities_have_no_conflicts": all(row["entity_allocation_feasible"] for row in base["entity_results"]),
        "overloaded_plan_is_rejected": not overload["portfolio_feasible"],
        "overloaded_bess_has_power_conflict": "portfolio_conflict.up_power_double_commitment" in overload_bess["conflicts"],
        "low_soc_plan_is_rejected": not low_soc["portfolio_feasible"],
        "low_soc_bess_has_energy_conflict": "portfolio_conflict.up_energy_shortfall" in low_soc_bess["conflicts"],
        "no_unknown_ids_in_base": not base["unknown_entities"] and not base["unknown_tasks"],
        "no_negative_commitments_in_base": not base["negative_commitments"],
    }
    return {"checks":checks, "all_passed":all(checks.values())}


def write_summary(base: dict, overload: dict, low_soc: dict, validation: dict) -> None:
    lines = [
        "# 多资源聚合与多市场容量冲突试算", "",
        "本次使用构造任务和构造实体，验证同一资源的功率与能量不能在现货、调频和爬坡任务中重复承诺。结果不是正式调度方案。", "",
        "| 场景 | 组合是否可行 | 主要结果 |", "| --- | --- | --- |",
        f"| 基准分配 | {base['portfolio_feasible']} | 三项任务满足，三个实体均未超出功率或能量能力 |",
        f"| 储能过度分配 | {overload['portfolio_feasible']} | 储能上调功率被重复承诺 |",
        f"| 储能SOC降至0.20 | {low_soc['portfolio_feasible']} | 原分配方案超出储能上调可用能量 |", "",
        f"自动检查：{'全部通过' if validation['all_passed'] else '存在失败项'}。", "",
        "系统没有自行决定哪个市场优先，而是校验提交的分配方案。后续如需自动优化，必须由用户或正式规则明确目标函数和优先级。", "",
    ]
    (OUTPUT / "运行摘要.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    portfolio = load_json(EXAMPLES / "portfolio_allocation_demo.json")
    submissions = load_all_submissions()
    base = validate_allocation(portfolio, submissions, portfolio["base_assignments"], "base_feasible_plan")
    overload_assignments = merge_overrides(portfolio["base_assignments"], portfolio["conflict_overrides"])
    overload = validate_allocation(portfolio, submissions, overload_assignments, "bess_overcommitted_plan")
    low_soc = validate_allocation(portfolio, low_soc_submissions(submissions), portfolio["base_assignments"], "same_plan_with_low_bess_soc")
    validation = validation_summary(base, overload, low_soc)
    write_json(OUTPUT / "base_allocation_result.json", base)
    write_json(OUTPUT / "overcommitted_allocation_result.json", overload)
    write_json(OUTPUT / "low_soc_allocation_result.json", low_soc)
    write_json(OUTPUT / "validation_summary.json", validation)
    write_summary(base, overload, low_soc, validation)
    if not validation["all_passed"]:
        raise SystemExit("Portfolio allocation validation failed")
    print(json.dumps({"base_feasible":True, "overload_rejected":True, "low_soc_rejected":True, "all_checks_passed":True}, ensure_ascii=False))


if __name__ == "__main__":
    main()
