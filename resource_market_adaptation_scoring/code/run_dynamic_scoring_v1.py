#!/usr/bin/env python3
"""First unified dynamic scoring engine for PV, storage and EV resources.

The bundled examples are constructed assumptions. Diagnostic and benchmark
indices from those examples are not formal Shandong market scores.
"""

from __future__ import annotations

import csv
import copy
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config"
EXAMPLES = ROOT / "examples"
OUTPUT = ROOT / "results" / "dynamic_scoring_v1"
ENGINE_VERSION = "dynamic-scoring-v1.0"
CALCULATED_AT = "2026-09-15T10:05:00+08:00"

MARKET_STATUS_IDS = {
    "spot_fit": "market.spot.status",
    "frequency_fit": "market.frequency.status",
    "reserve_readiness": "market.reserve.status",
    "ramping_fit": "market.ramping.status",
    "green_supply_fit": "market.green_supply.status",
    "green_consumption_fit": "market.green_consumption.status",
}

QUALIFICATION_FIELDS = {
    "spot_fit": ["registered", "metering"],
    "frequency_fit": ["registered", "metering", "communication", "direct_control", "performance_test"],
    "reserve_readiness": ["registered", "metering", "communication", "direct_control"],
    "ramping_fit": ["registered", "metering", "communication", "direct_control"],
    "green_supply_fit": ["green_project_eligible", "traceable"],
    "green_consumption_fit": ["consumer_relation", "green_contract", "consumer_metered"],
}

MODEL_REQUIRED = {
    "分布式光伏": ["current_power_mw", "forecast_p10_mw", "forecast_horizon_h", "reserved_headroom_mw", "curtailable_power_mw", "grid_connection_limit_mw", "green_eligible"],
    "储能": ["energy_capacity_mwh", "soc", "soc_min", "soc_max", "soh", "charge_efficiency", "discharge_efficiency", "max_charge_power_mw", "max_discharge_power_mw"],
    "充电桩（充电站）": ["connected_power_mw", "current_power_mw", "min_power_mw", "max_power_mw", "flexible_energy_mwh", "earliest_departure_at", "target_energy_remaining_mwh", "user_authorized", "v2g_enabled", "v2g_power_mw"],
}

THERMAL_TYPES = {"蓄热锅炉", "冷水机组", "冷库", "空调", "烘干机（热泵）"}
THERMAL_REQUIRED = ["current_power_mw", "min_power_mw", "max_power_mw", "thermal_buffer_up_mwh", "thermal_buffer_down_mwh", "max_control_window_h", "rebound_energy_ratio", "process_state_name", "process_state_value", "process_state_min", "process_state_max", "process_margin_pct", "control_mode", "control_authorized"]
for thermal_type in THERMAL_TYPES:
    MODEL_REQUIRED[thermal_type] = THERMAL_REQUIRED

PUMP_TYPES = {"辅助泵类", "高压电机泵"}
PUMP_REQUIRED = ["current_power_mw", "min_stable_power_mw", "max_power_mw", "process_buffer_up_mwh", "process_buffer_down_mwh", "max_control_window_h", "vfd_enabled", "discrete_shutdown_allowed", "parallel_spare_power_mw", "liquid_level_pct", "liquid_level_min_pct", "liquid_level_max_pct", "flow_value", "minimum_flow_value", "pressure_value", "pressure_min", "pressure_max", "interlock_clear", "control_authorized"]
for pump_type in PUMP_TYPES:
    MODEL_REQUIRED[pump_type] = PUMP_REQUIRED

BATCH_TYPES = {"水泥（球磨机）", "中频电炉", "电窑炉", "搅拌机", "压机（液压/油压/水压）"}
BATCH_REQUIRED = ["unit_power_mw", "active_units", "interruptible_units", "schedulable_units", "production_buffer_up_mwh", "production_buffer_down_mwh", "max_control_window_h", "current_stage", "flexible_stages", "inventory_level_pct", "inventory_min_pct", "inventory_max_pct", "deadline_slack_h", "minimum_deadline_slack_h", "minimum_on_time_min", "minimum_off_time_min", "quality_risk_clear", "safety_interlock_clear", "control_authorized", "continuous_control"]
for batch_type in BATCH_TYPES:
    MODEL_REQUIRED[batch_type] = BATCH_REQUIRED

COMPUTE_TYPES = {"算力"}
COMPUTE_REQUIRED = ["facility_power_mw", "it_power_mw", "pue", "deferrable_workload_share", "upward_absorption_share", "deferrable_energy_mwh", "additional_schedulable_energy_mwh", "max_deferral_window_h", "deadline_slack_h", "minimum_deadline_slack_h", "sla_headroom_pct", "minimum_sla_headroom_pct", "migration_required", "migration_bandwidth_ok", "control_authorized", "real_time_workload_share"]
MODEL_REQUIRED["算力"] = COMPUTE_REQUIRED

COMMON_REQUIRED = ["rated_power_mw", "availability_pct", "response_time_s", "ramp_rate_mw_per_min", "tracking_error_pct", "specific_constraint_pass"]


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8-sig") as handle:
        return json.load(handle)


def write_json(path: Path, value: object) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def load_rules() -> dict[str, dict]:
    rows = {}
    with (CONFIG / "market_rule_parameters.csv").open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            rows[row["parameter_id"]] = row
    return rows


def market_statuses(rules: dict[str, dict]) -> dict[str, str]:
    return {output: rules[parameter_id]["value"] for output, parameter_id in MARKET_STATUS_IDS.items()}


def apply_operator(value: float, operator: str, threshold: float) -> bool:
    operations = {"<": value < threshold, "<=": value <= threshold, ">=": value >= threshold, "=": value == threshold}
    return operations[operator]


def blank_capability() -> dict:
    return {
        "available_up_power_mw": None,
        "available_down_power_mw": None,
        "available_up_energy_mwh": None,
        "available_down_energy_mwh": None,
        "duration_h": None,
        "response_time_s": None,
        "ramp_rate_mw_per_min": None,
        "tracking_error_pct": None,
        "eligible_green_energy_mwh": None,
        "shiftable_load_power_mw": None,
        "shiftable_load_energy_mwh": None,
    }


def common_capability(entity: dict) -> dict:
    result = blank_capability()
    for field in ["response_time_s", "ramp_rate_mw_per_min", "tracking_error_pct"]:
        result[field] = entity.get(field)
    return result


def pv_capability(entity: dict) -> dict:
    p = entity["model_parameters"]
    result = common_capability(entity)
    headroom = max(0.0, min(
        p["reserved_headroom_mw"],
        p["forecast_p10_mw"] - p["current_power_mw"],
        p["grid_connection_limit_mw"] - p["current_power_mw"],
    ))
    down = max(0.0, min(p["curtailable_power_mw"], p["current_power_mw"]))
    horizon = p["forecast_horizon_h"]
    result.update({
        "available_up_power_mw": round(headroom, 6),
        "available_down_power_mw": round(down, 6),
        "available_up_energy_mwh": round(headroom * horizon, 6),
        "available_down_energy_mwh": round(down * horizon, 6),
        "duration_h": horizon,
        "eligible_green_energy_mwh": round(p["forecast_p10_mw"] * horizon, 6) if p["green_eligible"] else 0.0,
    })
    return result


def storage_capability(entity: dict) -> dict:
    p = entity["model_parameters"]
    result = common_capability(entity)
    effective_energy = p["energy_capacity_mwh"] * p["soh"]
    up_energy = max(0.0, (p["soc"] - p["soc_min"]) * effective_energy * p["discharge_efficiency"])
    down_energy = max(0.0, (p["soc_max"] - p["soc"]) * effective_energy / p["charge_efficiency"])
    up_power = min(entity["rated_power_mw"], p["max_discharge_power_mw"])
    down_power = min(entity["rated_power_mw"], p["max_charge_power_mw"])
    durations = [up_energy / up_power if up_power else 0.0, down_energy / down_power if down_power else 0.0]
    result.update({
        "available_up_power_mw": round(up_power, 6),
        "available_down_power_mw": round(down_power, 6),
        "available_up_energy_mwh": round(up_energy, 6),
        "available_down_energy_mwh": round(down_energy, 6),
        "duration_h": round(min(durations), 6),
        "shiftable_load_power_mw": round(min(up_power, down_power), 6),
        "shiftable_load_energy_mwh": round(min(up_energy, down_energy), 6),
    })
    return result


def ev_capability(entity: dict) -> dict:
    p = entity["model_parameters"]
    result = common_capability(entity)
    if not p["user_authorized"]:
        up_power = down_power = up_energy = down_energy = 0.0
    else:
        v2g = p["v2g_power_mw"] if p["v2g_enabled"] else 0.0
        up_power = max(0.0, p["current_power_mw"] - p["min_power_mw"]) + v2g
        down_power = max(0.0, min(p["connected_power_mw"], p["max_power_mw"]) - p["current_power_mw"])
        up_energy = p["flexible_energy_mwh"]
        down_energy = p["flexible_energy_mwh"]
    durations = [up_energy / up_power if up_power else 0.0, down_energy / down_power if down_power else 0.0]
    result.update({
        "available_up_power_mw": round(up_power, 6),
        "available_down_power_mw": round(down_power, 6),
        "available_up_energy_mwh": round(up_energy, 6),
        "available_down_energy_mwh": round(down_energy, 6),
        "duration_h": round(min(durations), 6),
        "shiftable_load_power_mw": round(min(up_power, down_power), 6),
        "shiftable_load_energy_mwh": round(min(up_energy, down_energy), 6),
    })
    return result


def thermal_capability(entity: dict) -> dict:
    p = entity["model_parameters"]
    result = common_capability(entity)
    up_power = max(0.0, p["current_power_mw"] - p["min_power_mw"])
    down_power = max(0.0, p["max_power_mw"] - p["current_power_mw"])
    up_energy = min(p["thermal_buffer_up_mwh"], up_power * p["max_control_window_h"])
    down_energy = min(p["thermal_buffer_down_mwh"], down_power * p["max_control_window_h"])
    up_duration = up_energy / up_power if up_power else 0.0
    down_duration = down_energy / down_power if down_power else 0.0
    rebound_factor = 1.0 + p["rebound_energy_ratio"]
    result.update({
        "available_up_power_mw": round(up_power, 6),
        "available_down_power_mw": round(down_power, 6),
        "available_up_energy_mwh": round(up_energy, 6),
        "available_down_energy_mwh": round(down_energy, 6),
        "duration_h": round(min(up_duration, down_duration), 6),
        "shiftable_load_power_mw": round(min(up_power, down_power), 6),
        "shiftable_load_energy_mwh": round(min(up_energy, down_energy / rebound_factor), 6),
    })
    return result


def pump_capability(entity: dict) -> dict:
    p = entity["model_parameters"]
    result = common_capability(entity)
    if p["vfd_enabled"]:
        up_power = max(0.0, p["current_power_mw"] - p["min_stable_power_mw"])
        down_power = max(0.0, p["max_power_mw"] - p["current_power_mw"])
    else:
        up_power = p["current_power_mw"] if p["discrete_shutdown_allowed"] else 0.0
        down_power = max(0.0, p["parallel_spare_power_mw"])
    up_energy = min(p["process_buffer_up_mwh"], up_power * p["max_control_window_h"])
    down_energy = min(p["process_buffer_down_mwh"], down_power * p["max_control_window_h"])
    up_duration = up_energy / up_power if up_power else 0.0
    down_duration = down_energy / down_power if down_power else 0.0
    result.update({
        "available_up_power_mw": round(up_power, 6),
        "available_down_power_mw": round(down_power, 6),
        "available_up_energy_mwh": round(up_energy, 6),
        "available_down_energy_mwh": round(down_energy, 6),
        "duration_h": round(min(up_duration, down_duration), 6),
        "shiftable_load_power_mw": round(min(up_power, down_power), 6),
        "shiftable_load_energy_mwh": round(min(up_energy, down_energy), 6),
    })
    return result


def batch_capability(entity: dict) -> dict:
    p = entity["model_parameters"]
    result = common_capability(entity)
    stage_flexible = p["current_stage"] in p["flexible_stages"]
    if stage_flexible:
        up_power = max(0.0, p["interruptible_units"] * p["unit_power_mw"])
        down_power = max(0.0, p["schedulable_units"] * p["unit_power_mw"])
    else:
        up_power = down_power = 0.0
    up_energy = min(p["production_buffer_up_mwh"], up_power * p["max_control_window_h"])
    down_energy = min(p["production_buffer_down_mwh"], down_power * p["max_control_window_h"])
    up_duration = up_energy / up_power if up_power else 0.0
    down_duration = down_energy / down_power if down_power else 0.0
    result.update({
        "available_up_power_mw": round(up_power, 6),
        "available_down_power_mw": round(down_power, 6),
        "available_up_energy_mwh": round(up_energy, 6),
        "available_down_energy_mwh": round(down_energy, 6),
        "duration_h": round(min(up_duration, down_duration), 6),
        "shiftable_load_power_mw": round(min(up_power, down_power), 6),
        "shiftable_load_energy_mwh": round(min(up_energy, down_energy), 6),
    })
    return result


def compute_capability(entity: dict) -> dict:
    p = entity["model_parameters"]
    result = common_capability(entity)
    up_power = max(0.0, p["facility_power_mw"] * p["deferrable_workload_share"])
    down_power = max(0.0, min(entity["rated_power_mw"] - p["facility_power_mw"], p["facility_power_mw"] * p["upward_absorption_share"]))
    up_energy = min(p["deferrable_energy_mwh"], up_power * p["max_deferral_window_h"])
    down_energy = min(p["additional_schedulable_energy_mwh"], down_power * p["max_deferral_window_h"])
    up_duration = up_energy / up_power if up_power else 0.0
    down_duration = down_energy / down_power if down_power else 0.0
    result.update({
        "available_up_power_mw": round(up_power, 6),
        "available_down_power_mw": round(down_power, 6),
        "available_up_energy_mwh": round(up_energy, 6),
        "available_down_energy_mwh": round(down_energy, 6),
        "duration_h": round(min(up_duration, down_duration), 6),
        "shiftable_load_power_mw": round(min(up_power, down_power), 6),
        "shiftable_load_energy_mwh": round(min(up_energy, down_energy), 6),
    })
    return result


ADAPTERS = {"分布式光伏": pv_capability, "储能": storage_capability, "充电桩（充电站）": ev_capability}
ADAPTERS.update({resource_type: thermal_capability for resource_type in THERMAL_TYPES})
ADAPTERS.update({resource_type: pump_capability for resource_type in PUMP_TYPES})
ADAPTERS.update({resource_type: batch_capability for resource_type in BATCH_TYPES})
ADAPTERS["算力"] = compute_capability


def missing_input_fields(entity: dict) -> list[str]:
    missing = [field for field in COMMON_REQUIRED if entity.get(field) is None]
    params = entity.get("model_parameters", {})
    missing.extend(f"model_parameters.{field}" for field in MODEL_REQUIRED.get(entity.get("resource_type"), []) if params.get(field) is None)
    return missing


def applicability(resource_type: str, output: str) -> bool:
    if output == "green_supply_fit":
        return resource_type == "分布式光伏"
    if output == "green_consumption_fit":
        return resource_type in {"储能", "充电桩（充电站）"} | THERMAL_TYPES | PUMP_TYPES | BATCH_TYPES | COMPUTE_TYPES
    return True


def resource_constraint_status(entity: dict) -> tuple[str, list[str]]:
    submitted = entity.get("specific_constraint_pass")
    if submitted is None:
        return "pending_evidence", ["resource_constraint.submitted_status"]
    if submitted is False:
        return "fail", ["resource_constraint.submitted_status"]
    if entity["resource_type"] not in THERMAL_TYPES | PUMP_TYPES | BATCH_TYPES | COMPUTE_TYPES:
        return "pass", []
    p = entity["model_parameters"]
    failures = []
    if not p["control_authorized"]:
        failures.append("resource_constraint.control_authorized")
    if entity["resource_type"] in THERMAL_TYPES:
        if not p["process_state_min"] <= p["process_state_value"] <= p["process_state_max"]:
            failures.append("resource_constraint.process_state_boundary")
        if p["process_margin_pct"] <= 0:
            failures.append("resource_constraint.process_margin")
        if not p["min_power_mw"] <= p["current_power_mw"] <= p["max_power_mw"]:
            failures.append("resource_constraint.power_boundary")
    elif entity["resource_type"] in PUMP_TYPES:
        if not p["liquid_level_min_pct"] <= p["liquid_level_pct"] <= p["liquid_level_max_pct"]:
            failures.append("resource_constraint.liquid_level_boundary")
        if p["flow_value"] < p["minimum_flow_value"]:
            failures.append("resource_constraint.minimum_flow")
        if not p["pressure_min"] <= p["pressure_value"] <= p["pressure_max"]:
            failures.append("resource_constraint.pressure_boundary")
        if not p["interlock_clear"]:
            failures.append("resource_constraint.process_interlock")
        if not p["min_stable_power_mw"] <= p["current_power_mw"] <= p["max_power_mw"]:
            failures.append("resource_constraint.power_boundary")
    elif entity["resource_type"] in BATCH_TYPES:
        if not p["inventory_min_pct"] <= p["inventory_level_pct"] <= p["inventory_max_pct"]:
            failures.append("resource_constraint.inventory_boundary")
        if p["deadline_slack_h"] < p["minimum_deadline_slack_h"]:
            failures.append("resource_constraint.deadline_slack")
        if not p["quality_risk_clear"]:
            failures.append("resource_constraint.quality_risk")
        if not p["safety_interlock_clear"]:
            failures.append("resource_constraint.safety_interlock")
        if p["interruptible_units"] > p["active_units"]:
            failures.append("resource_constraint.interruptible_unit_count")
    else:
        if p["deadline_slack_h"] < p["minimum_deadline_slack_h"]:
            failures.append("resource_constraint.deadline_slack")
        if p["sla_headroom_pct"] < p["minimum_sla_headroom_pct"]:
            failures.append("resource_constraint.sla_headroom")
        if p["migration_required"] and not p["migration_bandwidth_ok"]:
            failures.append("resource_constraint.migration_bandwidth")
        if not 0 <= p["real_time_workload_share"] <= 1:
            failures.append("resource_constraint.real_time_workload_share")
        if p["it_power_mw"] * p["pue"] > p["facility_power_mw"] * 1.05:
            failures.append("resource_constraint.pue_power_consistency")
    return ("fail", failures) if failures else ("pass", [])


def admission(entity: dict, output: str) -> tuple[str, list[str]]:
    qualification = entity["market_qualification"]
    failed = []
    pending = []
    for field in QUALIFICATION_FIELDS[output]:
        value = qualification.get(field)
        if value is False:
            failed.append(f"qualification.{field}")
        elif value is None:
            pending.append(f"qualification.{field}")
    if failed:
        return "fail", failed
    if pending:
        return "pending_evidence", pending
    return "pass", []


def official_gate_specs(entity: dict, cap: dict, output: str) -> list[tuple[str, float | None]]:
    """Map official rule IDs to observable entity or derived capability values."""
    resource_type = entity["resource_type"]
    rated = entity["rated_power_mw"]
    params = entity["model_parameters"]
    specs: list[tuple[str, float | None]] = []
    if resource_type == "分布式光伏" and output in {"spot_fit", "green_supply_fit"}:
        specs.append(("vpp.distributed_generation.min_aggregate_capacity", rated))
    elif resource_type == "储能":
        rated_duration = params["energy_capacity_mwh"] * params["soh"] / rated if rated else None
        if output in {"spot_fit", "frequency_fit"}:
            specs.append(("vpp.storage.min_aggregate_capacity", rated))
        if output == "spot_fit":
            specs.append(("vpp.storage.spot.min_continuous_duration", rated_duration))
        if output in {"frequency_fit", "ramping_fit"}:
            specs.append(("vpp.storage.aux.min_continuous_duration", rated_duration * 60 if rated_duration is not None else None))
    elif resource_type in ({"充电桩（充电站）"} | THERMAL_TYPES | PUMP_TYPES | BATCH_TYPES | COMPUTE_TYPES) and output == "spot_fit":
        up_power = cap["available_up_power_mw"]
        up_energy = cap["available_up_energy_mwh"]
        up_duration = up_energy / up_power if up_power else None
        specs.extend([
            ("vpp.adjustable_load.min_adjustable_capacity", up_power),
            ("vpp.adjustable_load.min_continuous_duration", up_duration),
        ])
    return specs


def evaluate_official_gates(entity: dict, cap: dict, output: str, rules: dict[str, dict]) -> tuple[str, list[str], list[str]]:
    evaluated, failed, pending = [], [], []
    for rule_id, observed in official_gate_specs(entity, cap, output):
        evaluated.append(rule_id)
        rule = rules.get(rule_id)
        if rule is None or rule.get("value", "") == "" or observed is None:
            pending.append(rule_id)
            continue
        if not apply_operator(float(observed), rule["operator"], float(rule["value"])):
            failed.append(rule_id)
    if failed:
        return "fail", evaluated, failed
    if pending:
        return "pending_evidence", evaluated, pending
    return "pass", evaluated, []


def positive_ratio(available: float | None, required: float | None) -> float | None:
    if available is None or required is None:
        return None
    if required == 0:
        return 1.0
    return available / required


def inverse_ratio(limit_value: float | None, actual_value: float | None) -> float | None:
    if limit_value is None or actual_value is None:
        return None
    if actual_value == 0:
        return 1.0
    return limit_value / actual_value


def resolve_requirements(entity: dict, task: dict) -> dict:
    req = dict(task["requirements"])
    rated = entity["rated_power_mw"]
    if req.get("required_power_mw") is None and req.get("required_power_ratio") is not None:
        req["required_power_mw"] = req["required_power_ratio"] * rated
    if req.get("required_ramp_mw_per_min") is None and req.get("required_ramp_ratio_per_min") is not None:
        req["required_ramp_mw_per_min"] = req["required_ramp_ratio_per_min"] * rated
    if req.get("required_energy_mwh") is None and req.get("required_power_mw") is not None and req.get("required_duration_h") is not None:
        req["required_energy_mwh"] = req["required_power_mw"] * req["required_duration_h"]
    if req.get("required_energy_mwh") is None and req.get("required_energy_ratio") is not None:
        req["required_energy_mwh"] = req["required_energy_ratio"] * rated * (req.get("required_duration_h") or 1.0)
    return req


def metric_ratios(cap: dict, req: dict, output: str) -> dict[str, float | None]:
    direction = req["direction"]
    up_power, down_power = cap["available_up_power_mw"], cap["available_down_power_mw"]
    up_energy, down_energy = cap["available_up_energy_mwh"], cap["available_down_energy_mwh"]
    required_power, required_energy = req.get("required_power_mw"), req.get("required_energy_mwh")
    if direction == "up":
        power, energy = up_power, up_energy
    elif direction == "down":
        power, energy = down_power, down_energy
    else:
        power = min(up_power, down_power) if up_power is not None and down_power is not None else None
        energy = min(up_energy, down_energy) if up_energy is not None and down_energy is not None else None

    if output == "spot_fit":
        directional_duration = energy / power if energy is not None and power else 0.0
        return {"power": positive_ratio(power, required_power), "energy": positive_ratio(energy, required_energy), "duration": positive_ratio(directional_duration, req.get("required_duration_h"))}
    if output == "frequency_fit":
        return {"bidirectional_power": positive_ratio(power, required_power), "bidirectional_energy": positive_ratio(energy, required_energy), "response": inverse_ratio(req.get("max_response_time_s"), cap["response_time_s"]), "ramp": positive_ratio(cap["ramp_rate_mw_per_min"], req.get("required_ramp_mw_per_min")), "tracking": inverse_ratio(req.get("max_tracking_error_pct"), cap["tracking_error_pct"])}
    if output == "reserve_readiness":
        return {"power": positive_ratio(power, required_power), "energy": positive_ratio(energy, required_energy), "response": inverse_ratio(req.get("max_response_time_s"), cap["response_time_s"])}
    if output == "ramping_fit":
        return {"bidirectional_power": positive_ratio(power, required_power), "bidirectional_energy": positive_ratio(energy, required_energy), "response": inverse_ratio(req.get("max_response_time_s"), cap["response_time_s"]), "ramp": positive_ratio(cap["ramp_rate_mw_per_min"], req.get("required_ramp_mw_per_min"))}
    if output == "green_supply_fit":
        return {"eligible_green_energy": positive_ratio(cap["eligible_green_energy_mwh"], required_energy)}
    if output == "green_consumption_fit":
        return {"shift_power": positive_ratio(cap["shiftable_load_power_mw"], required_power), "shift_energy": positive_ratio(cap["shiftable_load_energy_mwh"], required_energy)}
    raise ValueError(output)


def evaluate(submission: dict, task: dict, statuses: dict[str, str], rules: dict[str, dict]) -> dict:
    entity = submission["entity"]
    output = task["market_output"]
    result_id = f"{submission['submission_id']}::{task['task_id']}"
    missing = missing_input_fields(entity)
    constraint_status, constraint_failures = resource_constraint_status(entity)

    if not applicability(entity["resource_type"], output):
        return {
            "schema_version":"1.0", "result_id":result_id, "calculated_at":CALCULATED_AT, "engine_version":ENGINE_VERSION,
            "submission_id":submission["submission_id"], "entity_id":entity["entity_id"], "resource_type":entity["resource_type"], "aggregation_id":entity.get("aggregation_id"),
            "task_id":task["task_id"], "calculation_mode":task["calculation_mode"], "market_output":output, "region":task["region"], "capability":blank_capability(),
            "market_status":statuses[output], "admission_status":"not_applicable", "specific_constraint_status":constraint_status, "metric_ratios":{}, "bottleneck_metric":None,
            "feasibility":"not_applicable", "diagnostic_scenario_fit_index":"not_applicable", "benchmark_fit_index":"not_applicable", "formal_scenario_fit_index":"not_applicable",
            "evidence_status":submission["evidence_status"], "data_completeness_pct":round(100 * (len(COMMON_REQUIRED) - len([x for x in missing if not x.startswith('model_parameters.')])) / len(COMMON_REQUIRED), 2),
            "missing_fields":missing, "evaluated_rule_ids":[], "failed_rule_ids":[], "explanation":"该市场输出不适用于当前资源角色。"
        }

    cap = blank_capability() if missing else ADAPTERS[entity["resource_type"]](entity)
    qualification_status, qualification_fields = admission(entity, output)
    official_status, evaluated_rules, official_failures = evaluate_official_gates(entity, cap, output, rules)
    if "fail" in {qualification_status, official_status}:
        admission_status = "fail"
    elif "pending_evidence" in {qualification_status, official_status}:
        admission_status = "pending_evidence"
    else:
        admission_status = "pass"
    req = resolve_requirements(entity, task)
    ratios = metric_ratios(cap, req, output) if not missing else {}
    usable = [value for value in ratios.values() if value is not None]
    ratios_complete = bool(ratios) and len(usable) == len(ratios)
    bottleneck = min(ratios, key=lambda key: ratios[key]) if ratios_complete else None
    raw_score = round(min(100.0, min(usable) * 100.0), 2) if ratios_complete else "not_computable"

    market_status = statuses[output]
    formal_evidence = submission["evidence_status"] == "verified_entity_data" and task["evidence_status"] in {"official_rule", "verified_market_task"}
    gate_pass = market_status == "operational" and admission_status == "pass" and constraint_status == "pass"
    if gate_pass and ratios_complete:
        feasibility = "feasible" if min(usable) >= 1.0 else "not_feasible"
    else:
        feasibility = "not_computable"
    diagnostic = raw_score if constraint_status == "pass" else "not_computable"
    benchmark = diagnostic if task["calculation_mode"] == "standard_benchmark" else "not_applicable"
    formal = diagnostic if task["calculation_mode"] == "specific_task" and gate_pass and formal_evidence else "not_computable"

    total_required = len(COMMON_REQUIRED) + len(MODEL_REQUIRED[entity["resource_type"]])
    completeness = round(100 * (total_required - len(missing)) / total_required, 2)
    failed_rules = [f"qualification.{field.split('.')[-1]}" for field in qualification_fields] + official_failures
    if market_status != "operational":
        failed_rules = [f"market_status.{output}"] + failed_rules
    if constraint_status != "pass":
        failed_rules.extend(constraint_failures)

    reasons = []
    if market_status != "operational": reasons.append(f"市场状态为{market_status}")
    if admission_status != "pass": reasons.append(f"准入状态为{admission_status}")
    if constraint_status != "pass": reasons.append(f"资源专属约束为{constraint_status}")
    if missing: reasons.append("存在必填字段缺失")
    if bottleneck: reasons.append(f"当前最短板为{bottleneck}")
    if not formal_evidence: reasons.append("当前证据只支持调试或比较结果，不支持正式指数")

    return {
        "schema_version":"1.0", "result_id":result_id, "calculated_at":CALCULATED_AT, "engine_version":ENGINE_VERSION,
        "submission_id":submission["submission_id"], "entity_id":entity["entity_id"], "resource_type":entity["resource_type"], "aggregation_id":entity.get("aggregation_id"),
        "task_id":task["task_id"], "calculation_mode":task["calculation_mode"], "market_output":output, "region":task["region"], "capability":cap,
        "market_status":market_status, "admission_status":admission_status, "specific_constraint_status":constraint_status,
        "metric_ratios":{key: (round(value, 6) if value is not None else None) for key, value in ratios.items()}, "bottleneck_metric":bottleneck,
        "feasibility":feasibility, "diagnostic_scenario_fit_index":diagnostic, "benchmark_fit_index":benchmark, "formal_scenario_fit_index":formal,
        "evidence_status":"mixed_evidence" if submission["evidence_status"] != task["evidence_status"] else submission["evidence_status"],
        "data_completeness_pct":completeness, "missing_fields":missing, "evaluated_rule_ids":evaluated_rules, "failed_rule_ids":failed_rules, "explanation":"；".join(reasons) + "。"
    }


def validate_rule_boundaries(rules: dict[str, dict]) -> dict:
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
    details = []
    for rule_id, values, expected_values in specs:
        rule = rules[rule_id]
        for observed, expected in zip(values, expected_values):
            actual = apply_operator(observed, rule["operator"], float(rule["value"]))
            details.append({"rule_id":rule_id, "observed":observed, "expected_pass":expected, "actual_pass":actual, "correct":actual == expected})
    return {"case_count":len(details), "all_passed":all(row["correct"] for row in details), "details":details}


def validate_gate_integration(submission_set: dict, scenario_set: dict, statuses: dict, rules: dict) -> dict:
    by_type = {item["entity"]["resource_type"]: item for item in submission_set["submissions"]}
    by_output = {item["market_output"]: item for item in scenario_set["tasks"]}

    pv = copy.deepcopy(by_type["分布式光伏"])
    pv["submission_id"] = "TEST-PV-BELOW-CAPACITY"
    pv["entity"]["rated_power_mw"] = 0.8
    pv["entity"]["model_parameters"].update({"current_power_mw":0.2, "forecast_p10_mw":0.4, "reserved_headroom_mw":0.2, "curtailable_power_mw":0.2, "grid_connection_limit_mw":0.8})
    pv_result = evaluate(pv, by_output["spot_fit"], statuses, rules)

    storage = copy.deepcopy(by_type["储能"])
    storage["submission_id"] = "TEST-STORAGE-BELOW-DURATION"
    storage["entity"]["model_parameters"]["energy_capacity_mwh"] = 3.0
    storage_result = evaluate(storage, by_output["spot_fit"], statuses, rules)

    ev = copy.deepcopy(by_type["充电桩（充电站）"])
    ev["submission_id"] = "TEST-EV-BELOW-ADJUSTABLE-CAPACITY"
    ev["entity"]["model_parameters"].update({"current_power_mw":0.8, "min_power_mw":0.3, "flexible_energy_mwh":0.3})
    ev_result = evaluate(ev, by_output["spot_fit"], statuses, rules)

    cases = [
        {"case":"pv_below_1mw", "expected_rule":"vpp.distributed_generation.min_aggregate_capacity", "result":pv_result},
        {"case":"storage_below_2h", "expected_rule":"vpp.storage.spot.min_continuous_duration", "result":storage_result},
        {"case":"ev_below_1mw", "expected_rule":"vpp.adjustable_load.min_adjustable_capacity", "result":ev_result},
    ]
    details = [{
        "case":item["case"], "expected_rule":item["expected_rule"],
        "admission_status":item["result"]["admission_status"],
        "failed_rule_ids":item["result"]["failed_rule_ids"],
        "correct":item["result"]["admission_status"] == "fail" and item["expected_rule"] in item["result"]["failed_rule_ids"],
    } for item in cases]
    return {"case_count":len(details), "all_passed":all(item["correct"] for item in details), "details":details}


def validate_thermal_models(submission_set: dict, scenario_set: dict, statuses: dict, rules: dict) -> dict:
    by_output = {item["market_output"]: item for item in scenario_set["tasks"]}
    thermal_submissions = [item for item in submission_set["submissions"] if item["entity"]["resource_type"] in THERMAL_TYPES]
    details = []
    for original in thermal_submissions:
        baseline = evaluate(original, by_output["spot_fit"], statuses, rules)

        low_buffer = copy.deepcopy(original)
        low_buffer["submission_id"] += "-LOW-BUFFER"
        low_buffer["entity"]["model_parameters"]["thermal_buffer_up_mwh"] = 0.10
        low_result = evaluate(low_buffer, by_output["spot_fit"], statuses, rules)
        details.append({
            "resource_type":original["entity"]["resource_type"], "test":"reduced_thermal_buffer",
            "baseline_index":baseline["diagnostic_scenario_fit_index"], "changed_index":low_result["diagnostic_scenario_fit_index"],
            "correct":isinstance(low_result["diagnostic_scenario_fit_index"], (int, float)) and low_result["diagnostic_scenario_fit_index"] < baseline["diagnostic_scenario_fit_index"],
        })

        boundary_failure = copy.deepcopy(original)
        boundary_failure["submission_id"] += "-STATE-OUTSIDE"
        p = boundary_failure["entity"]["model_parameters"]
        p["process_state_value"] = p["process_state_max"] + 1.0
        failure_result = evaluate(boundary_failure, by_output["spot_fit"], statuses, rules)
        details.append({
            "resource_type":original["entity"]["resource_type"], "test":"process_state_outside_boundary",
            "constraint_status":failure_result["specific_constraint_status"], "diagnostic_index":failure_result["diagnostic_scenario_fit_index"],
            "failed_rule_ids":failure_result["failed_rule_ids"],
            "correct":failure_result["specific_constraint_status"] == "fail" and failure_result["diagnostic_scenario_fit_index"] == "not_computable" and "resource_constraint.process_state_boundary" in failure_result["failed_rule_ids"],
        })
    return {"case_count":len(details), "all_passed":bool(details) and all(item["correct"] for item in details), "details":details}


def validate_pump_models(submission_set: dict, scenario_set: dict, statuses: dict, rules: dict) -> dict:
    by_output = {item["market_output"]: item for item in scenario_set["tasks"]}
    pump_submissions = [item for item in submission_set["submissions"] if item["entity"]["resource_type"] in PUMP_TYPES]
    details = []
    for original in pump_submissions:
        baseline = evaluate(original, by_output["spot_fit"], statuses, rules)

        low_buffer = copy.deepcopy(original)
        low_buffer["submission_id"] += "-LOW-BUFFER"
        low_buffer["entity"]["model_parameters"]["process_buffer_up_mwh"] = 0.10
        low_result = evaluate(low_buffer, by_output["spot_fit"], statuses, rules)
        details.append({
            "resource_type":original["entity"]["resource_type"], "test":"reduced_process_buffer",
            "baseline_index":baseline["diagnostic_scenario_fit_index"], "changed_index":low_result["diagnostic_scenario_fit_index"],
            "correct":isinstance(low_result["diagnostic_scenario_fit_index"], (int, float)) and low_result["diagnostic_scenario_fit_index"] < baseline["diagnostic_scenario_fit_index"],
        })

        level_failure = copy.deepcopy(original)
        level_failure["submission_id"] += "-LEVEL-OUTSIDE"
        p = level_failure["entity"]["model_parameters"]
        p["liquid_level_pct"] = p["liquid_level_min_pct"] - 1.0
        failure_result = evaluate(level_failure, by_output["spot_fit"], statuses, rules)
        details.append({
            "resource_type":original["entity"]["resource_type"], "test":"liquid_level_outside_boundary",
            "constraint_status":failure_result["specific_constraint_status"], "diagnostic_index":failure_result["diagnostic_scenario_fit_index"],
            "failed_rule_ids":failure_result["failed_rule_ids"],
            "correct":failure_result["specific_constraint_status"] == "fail" and "resource_constraint.liquid_level_boundary" in failure_result["failed_rule_ids"],
        })

    high_voltage = next(item for item in pump_submissions if item["entity"]["resource_type"] == "高压电机泵")
    no_discrete = copy.deepcopy(high_voltage)
    no_discrete["submission_id"] += "-NO-DISCRETE"
    no_discrete["entity"]["model_parameters"].update({"discrete_shutdown_allowed":False, "parallel_spare_power_mw":0.0})
    no_discrete_result = evaluate(no_discrete, by_output["spot_fit"], statuses, rules)
    details.append({
        "resource_type":"高压电机泵", "test":"remove_discrete_shutdown_and_spare_unit",
        "available_up_power_mw":no_discrete_result["capability"]["available_up_power_mw"],
        "admission_status":no_discrete_result["admission_status"],
        "correct":no_discrete_result["capability"]["available_up_power_mw"] == 0 and "vpp.adjustable_load.min_adjustable_capacity" in no_discrete_result["failed_rule_ids"],
    })
    return {"case_count":len(details), "all_passed":bool(details) and all(item["correct"] for item in details), "details":details}


def validate_batch_models(submission_set: dict, scenario_set: dict, statuses: dict, rules: dict) -> dict:
    by_output = {item["market_output"]: item for item in scenario_set["tasks"]}
    batch_submissions = [item for item in submission_set["submissions"] if item["entity"]["resource_type"] in BATCH_TYPES]
    details = []
    for original in batch_submissions:
        baseline = evaluate(original, by_output["spot_fit"], statuses, rules)

        low_buffer = copy.deepcopy(original)
        low_buffer["submission_id"] += "-LOW-BUFFER"
        low_buffer["entity"]["model_parameters"]["production_buffer_up_mwh"] = 0.10
        low_result = evaluate(low_buffer, by_output["spot_fit"], statuses, rules)
        details.append({
            "resource_type":original["entity"]["resource_type"], "test":"reduced_production_buffer",
            "baseline_index":baseline["diagnostic_scenario_fit_index"], "changed_index":low_result["diagnostic_scenario_fit_index"],
            "correct":isinstance(low_result["diagnostic_scenario_fit_index"], (int, float)) and low_result["diagnostic_scenario_fit_index"] < baseline["diagnostic_scenario_fit_index"],
        })

        quality_failure = copy.deepcopy(original)
        quality_failure["submission_id"] += "-QUALITY-RISK"
        quality_failure["entity"]["model_parameters"]["quality_risk_clear"] = False
        failure_result = evaluate(quality_failure, by_output["spot_fit"], statuses, rules)
        details.append({
            "resource_type":original["entity"]["resource_type"], "test":"quality_risk_not_clear",
            "constraint_status":failure_result["specific_constraint_status"], "diagnostic_index":failure_result["diagnostic_scenario_fit_index"],
            "failed_rule_ids":failure_result["failed_rule_ids"],
            "correct":failure_result["specific_constraint_status"] == "fail" and "resource_constraint.quality_risk" in failure_result["failed_rule_ids"],
        })

    furnace = next(item for item in batch_submissions if item["entity"]["resource_type"] == "中频电炉")
    unsafe_stage = copy.deepcopy(furnace)
    unsafe_stage["submission_id"] += "-POURING-STAGE"
    unsafe_stage["entity"]["model_parameters"]["current_stage"] = "pouring"
    stage_result = evaluate(unsafe_stage, by_output["spot_fit"], statuses, rules)
    details.append({
        "resource_type":"中频电炉", "test":"non_flexible_pouring_stage",
        "available_up_power_mw":stage_result["capability"]["available_up_power_mw"],
        "admission_status":stage_result["admission_status"],
        "correct":stage_result["capability"]["available_up_power_mw"] == 0 and "vpp.adjustable_load.min_adjustable_capacity" in stage_result["failed_rule_ids"],
    })
    return {"case_count":len(details), "all_passed":bool(details) and all(item["correct"] for item in details), "details":details}


def validate_compute_model(submission_set: dict, scenario_set: dict, statuses: dict, rules: dict) -> dict:
    by_output = {item["market_output"]: item for item in scenario_set["tasks"]}
    original = next(item for item in submission_set["submissions"] if item["entity"]["resource_type"] == "算力")
    baseline = evaluate(original, by_output["spot_fit"], statuses, rules)
    details = []

    low_share = copy.deepcopy(original)
    low_share["submission_id"] += "-LOW-DEFERRABLE"
    low_share["entity"]["model_parameters"]["deferrable_workload_share"] = 0.05
    low_result = evaluate(low_share, by_output["spot_fit"], statuses, rules)
    details.append({
        "test":"reduced_deferrable_workload_share", "baseline_up_power_mw":baseline["capability"]["available_up_power_mw"],
        "changed_up_power_mw":low_result["capability"]["available_up_power_mw"], "baseline_index":baseline["diagnostic_scenario_fit_index"],
        "changed_index":low_result["diagnostic_scenario_fit_index"],
        "correct":low_result["capability"]["available_up_power_mw"] < baseline["capability"]["available_up_power_mw"] and low_result["diagnostic_scenario_fit_index"] < baseline["diagnostic_scenario_fit_index"],
    })

    low_sla = copy.deepcopy(original)
    low_sla["submission_id"] += "-LOW-SLA"
    low_sla["entity"]["model_parameters"]["sla_headroom_pct"] = 5.0
    sla_result = evaluate(low_sla, by_output["spot_fit"], statuses, rules)
    details.append({
        "test":"sla_headroom_below_minimum", "constraint_status":sla_result["specific_constraint_status"],
        "failed_rule_ids":sla_result["failed_rule_ids"],
        "correct":sla_result["specific_constraint_status"] == "fail" and "resource_constraint.sla_headroom" in sla_result["failed_rule_ids"] and sla_result["diagnostic_scenario_fit_index"] == "not_computable",
    })

    deadline = copy.deepcopy(original)
    deadline["submission_id"] += "-SHORT-DEADLINE"
    deadline["entity"]["model_parameters"]["deadline_slack_h"] = 0.5
    deadline_result = evaluate(deadline, by_output["spot_fit"], statuses, rules)
    details.append({
        "test":"deadline_slack_below_minimum", "constraint_status":deadline_result["specific_constraint_status"],
        "failed_rule_ids":deadline_result["failed_rule_ids"],
        "correct":deadline_result["specific_constraint_status"] == "fail" and "resource_constraint.deadline_slack" in deadline_result["failed_rule_ids"],
    })
    return {"case_count":len(details), "all_passed":all(item["correct"] for item in details), "details":details}


def validate_overall_consistency(standard: list[dict]) -> dict:
    resource_types = sorted({row["resource_type"] for row in standard})
    market_outputs = {"spot_fit", "frequency_fit", "reserve_readiness", "ramping_fit", "green_supply_fit", "green_consumption_fit"}
    forbidden_total_fields = {"resource_total_score", "overall_resource_score", "fixed_category_score"}
    checks = {
        "sixteen_resource_types_present": len(resource_types) == 16,
        "six_market_outputs_present": {row["market_output"] for row in standard} == market_outputs,
        "six_rows_per_entity": all(sum(row["entity_id"] == entity_id for row in standard) == 6 for entity_id in {row["entity_id"] for row in standard}),
        "no_fixed_total_score_field": all(not forbidden_total_fields.intersection(row) for row in standard),
        "all_formal_indices_non_numeric_for_simulation": all(not isinstance(row["formal_scenario_fit_index"], (int, float)) for row in standard),
        "every_applicable_row_has_capability_or_missing_reason": all(row["feasibility"] == "not_applicable" or row["metric_ratios"] or row["missing_fields"] for row in standard),
    }
    return {"resource_types":resource_types, "resource_type_count":len(resource_types), "market_output_count":len(market_outputs), "checks":checks, "all_passed":all(checks.values())}


def validate_results(standard: list[dict], specific: list[dict], boundary: dict, integration: dict, thermal: dict, pump: dict, batch: dict, compute: dict, overall: dict) -> dict:
    checks = {
        "standard_result_count_is_96": len(standard) == 96,
        "each_standard_entity_has_six_outputs": all(sum(row["entity_id"] == entity for row in standard) == 6 for entity in {row["entity_id"] for row in standard}),
        "all_simulation_formal_indices_not_computable": all(row["formal_scenario_fit_index"] in {"not_computable", "not_applicable"} for row in standard + specific),
        "reserve_is_not_formal": all(row["market_status"] == "planned" and row["formal_scenario_fit_index"] == "not_computable" for row in standard if row["market_output"] == "reserve_readiness"),
        "not_applicable_outputs_are_explicit": sum(row["feasibility"] == "not_applicable" for row in standard) == 16,
        "specific_task_has_two_soc_states": len(specific) == 2,
        "lower_soc_reduces_diagnostic_index": specific[1]["diagnostic_scenario_fit_index"] < specific[0]["diagnostic_scenario_fit_index"],
        "lower_soc_bottleneck_is_energy": specific[1]["bottleneck_metric"] == "bidirectional_energy",
        "official_rules_are_traced": all("evaluated_rule_ids" in row for row in standard + specific),
        "expected_current_examples_official_gates_pass": all(row["admission_status"] == "pass" for row in standard if row["feasibility"] != "not_applicable"),
        "twenty_four_rule_boundary_cases_pass": boundary["case_count"] == 24 and boundary["all_passed"],
        "three_official_gate_integration_cases_pass": integration["case_count"] == 3 and integration["all_passed"],
        "ten_thermal_dynamic_and_constraint_cases_pass": thermal["case_count"] == 10 and thermal["all_passed"],
        "five_pump_dynamic_and_constraint_cases_pass": pump["case_count"] == 5 and pump["all_passed"],
        "eleven_batch_dynamic_and_constraint_cases_pass": batch["case_count"] == 11 and batch["all_passed"],
        "three_compute_dynamic_and_constraint_cases_pass": compute["case_count"] == 3 and compute["all_passed"],
        "sixteen_resource_overall_consistency_passes": overall["all_passed"],
    }
    return {"checks": checks, "all_passed": all(checks.values())}


def write_summary(standard: list[dict], specific: list[dict], validation: dict) -> None:
    by_entity = {}
    for row in standard:
        by_entity.setdefault(row["entity_id"], []).append(row)
    lines = [
        "# 动态评分运行摘要", "",
        "当前已接入全部16类资源。输入与任务均为构造假设，结果只用于验证系统接口和动态重算，不是山东正式市场评分。", "",
        "## 标准六项画像", "",
        "| 实体 | 资源类型 | 可计算比较结果 | 不适用结果 | 正式指数 |", "| --- | --- | --- | --- | --- |",
    ]
    for entity_id, rows in by_entity.items():
        numeric = [r for r in rows if isinstance(r["benchmark_fit_index"], (int, float))]
        not_applicable = [r["market_output"] for r in rows if r["feasibility"] == "not_applicable"]
        lines.append(f"| {entity_id} | {rows[0]['resource_type']} | {len(numeric)}/6 | {', '.join(not_applicable) if not_applicable else '无'} | 均为 not_computable |")
    lines.extend(["", "## SOC 动态重算", "", "| 实体 | SOC | 诊断场景指数 | 最短板 | 正式指数 |", "| --- | ---: | ---: | --- | --- |"])
    for row, soc in zip(specific, [0.55, 0.20]):
        lines.append(f"| {row['entity_id']} | {soc:.2f} | {row['diagnostic_scenario_fit_index']} | {row['bottleneck_metric']} | {row['formal_scenario_fit_index']} |")
    lines.extend(["", f"自动检查：{'全部通过' if validation['all_passed'] else '存在失败项'}。", "", "SOC 从 0.55 降至 0.20 后，在同一个 1 MW 双向、持续 1 h 的构造调频任务中，储能的双向可用能量成为最短板，诊断指数随之下降。这证明结果由实体状态和任务共同决定，并非储能类别固定分。", ""])
    (OUTPUT / "运行摘要.md").write_text("\n".join(lines), encoding="utf-8")


def write_standard_matrix(standard: list[dict]) -> None:
    order = ["spot_fit", "frequency_fit", "reserve_readiness", "ramping_fit", "green_supply_fit", "green_consumption_fit"]
    labels = {"spot_fit":"现货", "frequency_fit":"调频", "reserve_readiness":"备用准备度", "ramping_fit":"爬坡", "green_supply_fit":"绿电供给", "green_consumption_fit":"绿电消费"}
    grouped = {}
    for row in standard:
        grouped.setdefault((row["entity_id"], row["resource_type"]), {})[row["market_output"]] = row
    lines = [
        "# 16类资源标准场景动态画像快照", "",
        "本表来自构造实体和可更新标准比较场景，只用于查看统一程序输出。它不是16类资源固定评分表，不代表山东正式市场资格、交易评分或收益。实体参数或比较场景变化后，本表会重新计算。", "",
        "| 实体 | 资源类型 | " + " | ".join(labels[item] for item in order) + " |",
        "| --- | --- | " + " | ".join(["---:"] * len(order)) + " |",
    ]
    for (entity_id, resource_type), rows in grouped.items():
        cells = []
        for output in order:
            row = rows[output]
            value = row["benchmark_fit_index"]
            if value == "not_applicable":
                cells.append("不适用")
            elif output == "reserve_readiness":
                cells.append(f"{value}（计划状态）")
            else:
                cells.append(str(value))
        lines.append(f"| {entity_id} | {resource_type} | " + " | ".join(cells) + " |")
    lines.extend(["", "说明：数值为标准比较场景下的最短板指数快照；正式指数在本批模拟数据中均为 `not_computable`。", ""])
    (OUTPUT / "标准场景动态画像矩阵.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    rules = load_rules()
    statuses = market_statuses(rules)
    submission_set = load_json(EXAMPLES / "first_batch_resource_submissions.json")
    thermal_set = load_json(EXAMPLES / "thermal_resource_submissions.json")
    submission_set["submissions"].extend(thermal_set["submissions"])
    pump_set = load_json(EXAMPLES / "pump_resource_submissions.json")
    submission_set["submissions"].extend(pump_set["submissions"])
    batch_set = load_json(EXAMPLES / "batch_resource_submissions.json")
    submission_set["submissions"].extend(batch_set["submissions"])
    compute_set = load_json(EXAMPLES / "compute_resource_submission.json")
    submission_set["submissions"].extend(compute_set["submissions"])
    scenario_set = load_json(CONFIG / "standard_market_scenarios.json")
    standard = [evaluate(submission, task, statuses, rules) for submission in submission_set["submissions"] for task in scenario_set["tasks"]]

    specific_demo = load_json(EXAMPLES / "specific_frequency_task_demo.json")
    specific = [evaluate(submission, specific_demo["task"], statuses, rules) for submission in specific_demo["submissions"]]
    boundary = validate_rule_boundaries(rules)
    integration = validate_gate_integration(submission_set, scenario_set, statuses, rules)
    thermal = validate_thermal_models(submission_set, scenario_set, statuses, rules)
    pump = validate_pump_models(submission_set, scenario_set, statuses, rules)
    batch = validate_batch_models(submission_set, scenario_set, statuses, rules)
    compute = validate_compute_model(submission_set, scenario_set, statuses, rules)
    overall = validate_overall_consistency(standard)
    validation = validate_results(standard, specific, boundary, integration, thermal, pump, batch, compute, overall)

    write_json(OUTPUT / "standard_profile_results.json", standard)
    write_json(OUTPUT / "specific_task_results.json", specific)
    write_json(OUTPUT / "validation_summary.json", validation)
    write_json(OUTPUT / "official_rule_boundary_results.json", boundary)
    write_json(OUTPUT / "official_gate_integration_results.json", integration)
    write_json(OUTPUT / "thermal_model_test_results.json", thermal)
    write_json(OUTPUT / "pump_model_test_results.json", pump)
    write_json(OUTPUT / "batch_model_test_results.json", batch)
    write_json(OUTPUT / "compute_model_test_results.json", compute)
    write_json(OUTPUT / "sixteen_resource_consistency_results.json", overall)
    write_summary(standard, specific, validation)
    write_standard_matrix(standard)
    if not validation["all_passed"]:
        failed = [name for name, passed in validation["checks"].items() if not passed]
        raise SystemExit(f"Validation failed: {failed}")
    print(json.dumps({"standard_results": len(standard), "specific_results": len(specific), "all_checks_passed": True}, ensure_ascii=False))


if __name__ == "__main__":
    main()
