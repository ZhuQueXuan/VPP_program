"""运行资源—市场适配最小模拟样例。

全部实体数值均为 simulation_assumption，只用于流程验证。
程序不会把模拟结果输出为正式市场适配指数或真实项目结论。
"""

from __future__ import annotations

import copy
import csv
import json
import math
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
INPUT_PATH = ROOT / "examples" / "pv_minimal_example.json"
OUTPUT_DIR = ROOT / "results" / "minimal_example"
SCORES_PATH = OUTPUT_DIR / "portfolio_market_results.csv"
MULTI_PATH = OUTPUT_DIR / "multi_market_feasibility.csv"
SENSITIVITY_PATH = OUTPUT_DIR / "sensitivity_soc.csv"
CLASSIFICATION_PATH = OUTPUT_DIR / "resource_classification.csv"
VALIDATION_PATH = OUTPUT_DIR / "validation_summary.json"


def clamp_ratio(value: float, required: float) -> float:
    if required <= 0:
        return 1.0
    return max(0.0, min(value / required, 1.0))


def inverse_ratio(value: float, limit: float) -> float:
    if value <= limit:
        return 1.0
    if not math.isfinite(value) or value <= 0:
        return 0.0
    return max(0.0, min(limit / value, 1.0))


def validate_payload(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    components = payload["components"]

    pv = components["pv_demo"]["parameters"]
    if not 0 <= pv["available_power_low_mw"] <= pv["available_power_high_mw"] <= pv["rated_power_mw"]:
        errors.append("光伏可用功率区间超出额定功率")

    battery = components["battery_demo"]["parameters"]
    if not battery["soc_min"] <= battery["soc"] <= battery["soc_max"]:
        errors.append("储能SOC不在安全边界内")
    if battery["rated_power_mw"] <= 0 or battery["rated_energy_mwh"] <= 0:
        errors.append("储能额定功率或能量非正")
    if not 0 < battery["one_way_efficiency"] <= 1:
        errors.append("储能效率不在(0,1]内")

    ev = components["ev_station_demo"]["parameters"]
    if not ev["minimum_power_per_charger_mw"] <= ev["current_power_per_charger_mw"] <= ev["power_per_charger_mw"]:
        errors.append("充电桩当前功率不在最小和额定功率之间")
    if ev["connected_chargers"] < 0:
        errors.append("在线充电桩数量为负")

    for scenario_name, scenario in payload["scenarios"].items():
        if scenario["scenario_source"] not in {
            "actual_market_order",
            "official_threshold",
            "verified_test_protocol",
            "research_case",
            "simulation_assumption",
        }:
            errors.append(f"{scenario_name} 的场景来源类型无效")
        if scenario["duration_h"] <= 0:
            errors.append(f"{scenario_name} 的持续时间非正")

    return errors


def select_response_metrics(
    contributors: list[dict[str, float]], required_power: float
) -> tuple[float, float, float]:
    """按响应时间优先选择贡献者，返回达到任务所需的响应、爬坡和功率加权跟踪误差。"""
    if required_power <= 0:
        return 0.0, math.inf, 0.0

    selected_power = 0.0
    response_time = 0.0
    ramp_rate = 0.0
    weighted_tracking = 0.0
    for contributor in sorted(contributors, key=lambda item: item["response_time_s"]):
        take = min(contributor["power_mw"], required_power - selected_power)
        if take <= 0:
            continue
        selected_power += take
        response_time = max(response_time, contributor["response_time_s"])
        ramp_rate += contributor["ramp_rate_mw_per_s"] * (
            take / contributor["power_mw"]
        )
        weighted_tracking += take * contributor["tracking_error_pct"]
        if selected_power + 1e-12 >= required_power:
            break

    if selected_power <= 0:
        return math.inf, 0.0, math.inf
    return response_time, ramp_rate, weighted_tracking / selected_power


def aggregate_capability(
    payload: dict[str, Any], portfolio: dict[str, Any], duration_h: float
) -> dict[str, Any]:
    caps: dict[str, Any] = {
        "delivery_power_low_mw": 0.0,
        "delivery_power_high_mw": 0.0,
        "delivery_energy_low_mwh": 0.0,
        "delivery_energy_high_mwh": 0.0,
        "up_power_low_mw": 0.0,
        "up_power_high_mw": 0.0,
        "down_power_low_mw": 0.0,
        "down_power_high_mw": 0.0,
        "up_energy_low_mwh": 0.0,
        "up_energy_high_mwh": 0.0,
        "down_energy_low_mwh": 0.0,
        "down_energy_high_mwh": 0.0,
        "eligible_green_energy_low_mwh": 0.0,
        "eligible_green_energy_high_mwh": 0.0,
        "absorption_power_low_mw": 0.0,
        "absorption_power_high_mw": 0.0,
        "absorption_energy_low_mwh": 0.0,
        "absorption_energy_high_mwh": 0.0,
        "up_contributors": [],
        "down_contributors": [],
    }

    for component_id in portfolio["components"]:
        component = payload["components"][component_id]
        params = component["parameters"]
        component_type = component["component_type"]

        if component_type == "pv":
            low = float(params["available_power_low_mw"])
            high = float(params["available_power_high_mw"])
            reserved = float(params["reserved_up_power_mw"])
            caps["delivery_power_low_mw"] += low
            caps["delivery_power_high_mw"] += high
            caps["delivery_energy_low_mwh"] += low * duration_h
            caps["delivery_energy_high_mwh"] += high * duration_h
            caps["up_power_low_mw"] += reserved
            caps["up_power_high_mw"] += reserved
            caps["up_energy_low_mwh"] += reserved * duration_h
            caps["up_energy_high_mwh"] += reserved * duration_h
            caps["down_power_low_mw"] += low
            caps["down_power_high_mw"] += high
            caps["down_energy_low_mwh"] += low * duration_h
            caps["down_energy_high_mwh"] += high * duration_h
            caps["eligible_green_energy_low_mwh"] += low * duration_h
            caps["eligible_green_energy_high_mwh"] += high * duration_h
            if reserved > 0:
                caps["up_contributors"].append(
                    {
                        "power_mw": reserved,
                        "response_time_s": float(params["response_time_s"]),
                        "ramp_rate_mw_per_s": float(params["ramp_rate_mw_per_s"]),
                        "tracking_error_pct": float(params["tracking_error_pct"]),
                    }
                )
            caps["down_contributors"].append(
                {
                    "power_mw": low,
                    "response_time_s": float(params["response_time_s"]),
                    "ramp_rate_mw_per_s": float(params["ramp_rate_mw_per_s"]),
                    "tracking_error_pct": float(params["tracking_error_pct"]),
                }
            )

        elif component_type == "battery":
            power = float(params["rated_power_mw"])
            energy = float(params["rated_energy_mwh"])
            efficiency = float(params["one_way_efficiency"])
            discharge_energy = max(0.0, (params["soc"] - params["soc_min"]) * energy * efficiency)
            charge_energy = max(0.0, (params["soc_max"] - params["soc"]) * energy / efficiency)
            up_power = min(power, discharge_energy / duration_h)
            down_power = min(power, charge_energy / duration_h)
            up_energy = min(discharge_energy, up_power * duration_h)
            down_energy = min(charge_energy, down_power * duration_h)

            for suffix in ("low", "high"):
                caps[f"delivery_power_{suffix}_mw"] += up_power
                caps[f"delivery_energy_{suffix}_mwh"] += up_energy
                caps[f"up_power_{suffix}_mw"] += up_power
                caps[f"up_energy_{suffix}_mwh"] += up_energy
                caps[f"down_power_{suffix}_mw"] += down_power
                caps[f"down_energy_{suffix}_mwh"] += down_energy
                caps[f"absorption_power_{suffix}_mw"] += down_power
                caps[f"absorption_energy_{suffix}_mwh"] += down_energy

            contributor = {
                "response_time_s": float(params["response_time_s"]),
                "ramp_rate_mw_per_s": float(params["ramp_rate_mw_per_s"]),
                "tracking_error_pct": float(params["tracking_error_pct"]),
            }
            caps["up_contributors"].append({"power_mw": up_power, **contributor})
            caps["down_contributors"].append({"power_mw": down_power, **contributor})

        elif component_type == "ev_station":
            count = float(params["connected_chargers"])
            maximum = count * float(params["power_per_charger_mw"])
            current = count * float(params["current_power_per_charger_mw"])
            minimum = count * float(params["minimum_power_per_charger_mw"])
            up_power = max(0.0, current - minimum)
            down_power = max(0.0, maximum - current)
            up_energy = min(float(params["flexible_reduction_energy_mwh"]), up_power * duration_h)
            down_energy = min(float(params["flexible_increase_energy_mwh"]), down_power * duration_h)

            for suffix in ("low", "high"):
                caps[f"delivery_power_{suffix}_mw"] += up_power
                caps[f"delivery_energy_{suffix}_mwh"] += up_energy
                caps[f"up_power_{suffix}_mw"] += up_power
                caps[f"up_energy_{suffix}_mwh"] += up_energy
                caps[f"down_power_{suffix}_mw"] += down_power
                caps[f"down_energy_{suffix}_mwh"] += down_energy
                caps[f"absorption_power_{suffix}_mw"] += down_power
                caps[f"absorption_energy_{suffix}_mwh"] += down_energy

            contributor = {
                "response_time_s": float(params["response_time_s"]),
                "ramp_rate_mw_per_s": float(params["ramp_rate_mw_per_s"]),
                "tracking_error_pct": float(params["tracking_error_pct"]),
            }
            caps["up_contributors"].append({"power_mw": up_power, **contributor})
            caps["down_contributors"].append({"power_mw": down_power, **contributor})
        else:
            raise ValueError(f"未知组件类型：{component_type}")

    return caps


def gate_status(payload: dict[str, Any], portfolio: dict[str, Any], market: str) -> tuple[str, str]:
    snapshot = payload["rule_snapshot"][market]
    if snapshot["market_status"] == "planned":
        return "not_open", "山东备用当前为探索开展，正式准入不计算"

    required_gates = payload["scenarios"][market]["required_gates"]
    missing = [gate for gate in required_gates if gate not in portfolio["gates"]]
    failed = [gate for gate in required_gates if portfolio["gates"].get(gate) is False]
    if missing:
        return "pending_evidence", "缺少证明字段：" + ", ".join(missing)
    if failed:
        return "fail", "明确不满足：" + ", ".join(failed)
    return "pass", "模拟条件下所列门控字段齐全且为真"


def score_from_ratios(ratios: list[tuple[str, float, float]]) -> tuple[float, float, str, str]:
    low_name, low_value, _ = min(ratios, key=lambda item: item[1])
    high_name, _, high_value = min(ratios, key=lambda item: item[2])
    return 100.0 * low_value, 100.0 * high_value, low_name, high_name


def evaluate_scenario(
    payload: dict[str, Any], portfolio: dict[str, Any], market: str
) -> dict[str, Any]:
    scenario = payload["scenarios"][market]
    req = scenario["requirements"]
    caps = aggregate_capability(payload, portfolio, float(scenario["duration_h"]))
    status, reason = gate_status(payload, portfolio, market)
    ratios: list[tuple[str, float, float]] = []
    capability_summary = ""
    transaction_status = ""

    if market == "spot":
        ratios = [
            (
                "delivery_power_mw",
                clamp_ratio(caps["delivery_power_low_mw"], req["delivery_power_mw"]),
                clamp_ratio(caps["delivery_power_high_mw"], req["delivery_power_mw"]),
            ),
            (
                "delivery_energy_mwh",
                clamp_ratio(caps["delivery_energy_low_mwh"], req["delivery_energy_mwh"]),
                clamp_ratio(caps["delivery_energy_high_mwh"], req["delivery_energy_mwh"]),
            ),
        ]
        capability_summary = (
            f"净交付功率{caps['delivery_power_low_mw']:.3f}—{caps['delivery_power_high_mw']:.3f} MW；"
            f"电量{caps['delivery_energy_low_mwh']:.3f}—{caps['delivery_energy_high_mwh']:.3f} MWh"
        )

    elif market == "frequency":
        required_power = float(req["bidirectional_power_mw"])
        up_response, up_ramp, up_tracking = select_response_metrics(caps["up_contributors"], required_power)
        down_response, down_ramp, down_tracking = select_response_metrics(caps["down_contributors"], required_power)
        bidirectional_power_low = min(caps["up_power_low_mw"], caps["down_power_low_mw"])
        bidirectional_power_high = min(caps["up_power_high_mw"], caps["down_power_high_mw"])
        bidirectional_energy_low = min(caps["up_energy_low_mwh"], caps["down_energy_low_mwh"])
        bidirectional_energy_high = min(caps["up_energy_high_mwh"], caps["down_energy_high_mwh"])
        response = max(up_response, down_response)
        ramp = min(up_ramp, down_ramp)
        tracking = max(up_tracking, down_tracking)
        ratios = [
            ("bidirectional_power_mw", clamp_ratio(bidirectional_power_low, required_power), clamp_ratio(bidirectional_power_high, required_power)),
            ("bidirectional_energy_mwh", clamp_ratio(bidirectional_energy_low, req["bidirectional_energy_mwh"]), clamp_ratio(bidirectional_energy_high, req["bidirectional_energy_mwh"])),
            ("response_time_s", inverse_ratio(response, req["response_time_s"]), inverse_ratio(response, req["response_time_s"])),
            ("ramp_rate_mw_per_s", clamp_ratio(ramp, req["ramp_rate_mw_per_s"]), clamp_ratio(ramp, req["ramp_rate_mw_per_s"])),
            ("tracking_error_pct", inverse_ratio(tracking, req["tracking_error_pct"]), inverse_ratio(tracking, req["tracking_error_pct"])),
        ]
        response_text = f"{response:.1f} s" if math.isfinite(response) else "不可达"
        capability_summary = (
            f"双向功率{bidirectional_power_low:.3f}—{bidirectional_power_high:.3f} MW；"
            f"双向电量{bidirectional_energy_low:.3f}—{bidirectional_energy_high:.3f} MWh；"
            f"可用容量响应时间{response_text}"
        )

    elif market in {"reserve", "ramping"}:
        required_power = float(req["up_power_mw"])
        response, ramp, _ = select_response_metrics(caps["up_contributors"], required_power)
        ratios = [
            ("up_power_mw", clamp_ratio(caps["up_power_low_mw"], required_power), clamp_ratio(caps["up_power_high_mw"], required_power)),
            ("up_energy_mwh", clamp_ratio(caps["up_energy_low_mwh"], req["up_energy_mwh"]), clamp_ratio(caps["up_energy_high_mwh"], req["up_energy_mwh"])),
            ("response_time_s", inverse_ratio(response, req["response_time_s"]), inverse_ratio(response, req["response_time_s"])),
            ("ramp_rate_mw_per_s", clamp_ratio(ramp, req["ramp_rate_mw_per_s"]), clamp_ratio(ramp, req["ramp_rate_mw_per_s"])),
        ]
        response_text = f"{response:.1f} s" if math.isfinite(response) else "不可达"
        capability_summary = (
            f"上调功率{caps['up_power_low_mw']:.3f}—{caps['up_power_high_mw']:.3f} MW；"
            f"上调电量{caps['up_energy_low_mwh']:.3f}—{caps['up_energy_high_mwh']:.3f} MWh；"
            f"可用容量响应时间{response_text}"
        )

    elif market == "green_supply":
        contract = float(req["green_contract_energy_mwh"])
        user_energy = float(req["linked_user_consumption_mwh"])
        settled_low = min(contract, caps["eligible_green_energy_low_mwh"], user_energy)
        settled_high = min(contract, caps["eligible_green_energy_high_mwh"], user_energy)
        ratios = [("settled_green_energy_mwh", clamp_ratio(settled_low, contract), clamp_ratio(settled_high, contract))]
        capability_summary = (
            f"合格绿电{caps['eligible_green_energy_low_mwh']:.3f}—{caps['eligible_green_energy_high_mwh']:.3f} MWh；"
            f"按三者取小试算结算量{settled_low:.3f}—{settled_high:.3f} MWh"
        )

    elif market == "green_consumption":
        ratios = [
            ("shift_increase_power_mw", clamp_ratio(caps["absorption_power_low_mw"], req["shift_increase_power_mw"]), clamp_ratio(caps["absorption_power_high_mw"], req["shift_increase_power_mw"])),
            ("shift_increase_energy_mwh", clamp_ratio(caps["absorption_energy_low_mwh"], req["shift_increase_energy_mwh"]), clamp_ratio(caps["absorption_energy_high_mwh"], req["shift_increase_energy_mwh"])),
        ]
        transaction_status = status
        capability_summary = (
            f"增负荷消纳功率{caps['absorption_power_low_mw']:.3f}—{caps['absorption_power_high_mw']:.3f} MW；"
            f"可移电量{caps['absorption_energy_low_mwh']:.3f}—{caps['absorption_energy_high_mwh']:.3f} MWh"
        )
    else:
        raise ValueError(f"未知市场：{market}")

    score_low, score_high, bottleneck_low, bottleneck_high = score_from_ratios(ratios)
    return {
        "portfolio_id": portfolio["portfolio_id"],
        "portfolio_name": portfolio["portfolio_name"],
        "market": market,
        "output_name": scenario["output_name"],
        "scenario_name": scenario["scenario_name"],
        "scenario_source": scenario["scenario_source"],
        "market_status": payload["rule_snapshot"][market]["market_status"],
        "gate_status": status,
        "gate_reason": reason,
        "formal_scenario_fit_index": "not_computable",
        "formal_index_reason": "实体和任务均为simulation_assumption；只输出模拟流程指数",
        "simulation_fit_index_low": round(score_low, 2),
        "simulation_fit_index_high": round(score_high, 2),
        "bottleneck_low": bottleneck_low,
        "bottleneck_high": bottleneck_high,
        "capability_summary": capability_summary,
        "transaction_compliance_status": transaction_status,
        "data_completeness_pct": 100.0,
        "evidence_status": "simulation_only",
        "resource_grade": "not_graded",
        "economic_result_status": payload["economic_result"]["status"],
    }


def classification_rows(payload: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for portfolio in payload["portfolios"]:
        types = {payload["components"][item]["component_type"] for item in portfolio["components"]}
        tags: list[str] = []
        constraints: list[str] = []
        if "pv" in types:
            tags.extend(["绿色电源", "连续限功率"])
        if "battery" in types:
            tags.extend(["储能", "连续双向调节", "组合履约协同"])
            constraints.append("能量/SOC约束")
        if "ev_station" in types:
            tags.extend(["柔性负荷", "时段平移", "绿电消纳协同"])
            constraints.append("用户行为/充电需求约束")
        rows.append(
            {
                "portfolio_id": portfolio["portfolio_id"],
                "portfolio_name": portfolio["portfolio_name"],
                "functional_tags": ";".join(dict.fromkeys(tags)),
                "main_constraints": ";".join(constraints) if constraints else "预测与可用出力约束",
                "grade": "not_graded",
                "evidence_status": "simulation_only",
            }
        )
    return rows


def multi_market_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    test = payload["multi_market_test"]
    portfolio = next(item for item in payload["portfolios"] if item["portfolio_id"] == test["portfolio_id"])
    duration_h = max(
        payload["scenarios"][market]["duration_h"]
        for market in test["same_time_up_regulation_requests_mw"]
    )
    caps = aggregate_capability(payload, portfolio, duration_h)
    requested = sum(float(value) for value in test["same_time_up_regulation_requests_mw"].values())
    available = float(caps["up_power_low_mw"])
    return [
        {
            "portfolio_id": portfolio["portfolio_id"],
            "portfolio_name": portfolio["portfolio_name"],
            "simultaneous_markets": "+".join(test["same_time_up_regulation_requests_mw"]),
            "requested_up_power_mw": round(requested, 3),
            "credible_up_power_low_mw": round(available, 3),
            "feasible": requested <= available + 1e-12,
            "shortfall_mw": round(max(0.0, requested - available), 3),
            "result": "可同时履约" if requested <= available + 1e-12 else "不可同时履约，存在容量重复占用",
            "reserve_treatment": test["reserve_excluded_reason"],
            "scenario_source": test["scenario_source"],
        }
    ]


def sensitivity_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    spec = payload["sensitivity_test"]
    rows: list[dict[str, Any]] = []
    for soc in spec["values"]:
        changed = copy.deepcopy(payload)
        changed["components"]["battery_demo"]["parameters"]["soc"] = float(soc)
        for portfolio in changed["portfolios"]:
            if "battery_demo" not in portfolio["components"]:
                continue
            for market in ("frequency", "reserve", "ramping"):
                result = evaluate_scenario(changed, portfolio, market)
                rows.append(
                    {
                        "portfolio_id": portfolio["portfolio_id"],
                        "portfolio_name": portfolio["portfolio_name"],
                        "changed_parameter": spec["parameter"],
                        "soc": soc,
                        "market": market,
                        "simulation_fit_index_low": result["simulation_fit_index_low"],
                        "simulation_fit_index_high": result["simulation_fit_index_high"],
                        "bottleneck_low": result["bottleneck_low"],
                        "gate_status": result["gate_status"],
                        "formal_index": "not_computable",
                        "perturbation_source": spec["scenario_source"],
                    }
                )
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"没有可写入的数据：{path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    payload = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
    errors = validate_payload(payload)
    if errors:
        raise ValueError("；".join(errors))

    score_rows = [
        evaluate_scenario(payload, portfolio, market)
        for portfolio in payload["portfolios"]
        for market in payload["scenarios"]
    ]
    multi_rows = multi_market_rows(payload)
    sensitivity = sensitivity_rows(payload)
    classifications = classification_rows(payload)

    all_scores_in_range = all(
        0.0 <= float(row[field]) <= 100.0
        for row in score_rows
        for field in ("simulation_fit_index_low", "simulation_fit_index_high")
    )
    interval_order_valid = all(
        float(row["simulation_fit_index_low"]) <= float(row["simulation_fit_index_high"])
        for row in score_rows
    )
    multi_market_conflict_detected = any(not bool(row["feasible"]) for row in multi_rows)
    pv_storage_reserve_scores = [
        float(row["simulation_fit_index_low"])
        for row in sensitivity
        if row["portfolio_id"] == "pv_storage_demo" and row["market"] == "reserve"
    ]
    sensitivity_detects_soc_effect = len(set(pv_storage_reserve_scores)) > 1
    if not all_scores_in_range or not interval_order_valid:
        raise ValueError("场景指数范围或区间顺序校验失败")
    if not multi_market_conflict_detected:
        raise ValueError("多市场容量冲突测试未检测到预期冲突")
    if not sensitivity_detects_soc_effect:
        raise ValueError("SOC敏感性测试未产生预期变化")

    write_csv(SCORES_PATH, score_rows)
    write_csv(MULTI_PATH, multi_rows)
    write_csv(SENSITIVITY_PATH, sensitivity)
    write_csv(CLASSIFICATION_PATH, classifications)

    summary = {
        "schema_version": payload["schema_version"],
        "validation_status": "pass",
        "input_validation_errors": [],
        "portfolio_count": len(payload["portfolios"]),
        "scenario_count": len(payload["scenarios"]),
        "score_row_count": len(score_rows),
        "all_formal_indices_not_computable": all(
            row["formal_scenario_fit_index"] == "not_computable" for row in score_rows
        ),
        "all_evidence_status_simulation_only": all(
            row["evidence_status"] == "simulation_only" for row in score_rows
        ),
        "reserve_all_not_open": all(
            row["gate_status"] == "not_open"
            for row in score_rows
            if row["market"] == "reserve"
        ),
        "all_simulation_scores_in_range": all_scores_in_range,
        "all_score_intervals_ordered": interval_order_valid,
        "multi_market_conflict_detected": multi_market_conflict_detected,
        "sensitivity_detects_soc_effect": sensitivity_detects_soc_effect,
        "economic_result_status": payload["economic_result"]["status"],
        "outputs": [
            str(SCORES_PATH.relative_to(ROOT)),
            str(MULTI_PATH.relative_to(ROOT)),
            str(SENSITIVITY_PATH.relative_to(ROOT)),
            str(CLASSIFICATION_PATH.relative_to(ROOT)),
        ],
    }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    VALIDATION_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
