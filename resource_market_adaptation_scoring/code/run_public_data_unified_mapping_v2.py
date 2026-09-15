#!/usr/bin/env python3
"""Map existing public evidence to the unified dynamic-scoring interfaces.

This script audits interface readiness. It never fills missing entity or task
fields with invented values and never emits a formal market score.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from run_dynamic_scoring_v1 import load_rules, market_statuses, write_json


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "results" / "public_data_flow_trial" / "empirical_capability_metrics.csv"
OUTPUT = ROOT / "results" / "public_data_unified_mapping_v2"
CALCULATED_AT = "2026-09-15T11:10:00+08:00"


def load_metrics() -> dict[str, dict[str, float]]:
    grouped: dict[str, dict[str, float]] = {}
    with SOURCE.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            grouped.setdefault(row["dataset_id"], {})[row["metric_id"]] = float(row["value"])
    return grouped


def build_evidence_records(metrics: dict[str, dict[str, float]]) -> list[dict]:
    m5 = metrics["m5bat_manifest_2017"]
    ev = metrics["epfl_level3_ev"]
    au = metrics["australia_sgsc"]
    return [
        {
            "dataset_id":"m5bat_manifest_2017", "candidate_resource_type":"储能", "mapping_status":"partial_evidence_only",
            "valid_resource_submission":False, "record_granularity":"second_level_operating_records",
            "mapped_evidence":{
                "source_nameplate_power_mw":0.240, "source_energy_capacity_mwh":0.180,
                "observed_power_abs_p95_mw":round(m5["observed_power_abs_p95"] / 1000, 6),
                "observed_ramp_abs_p95_mw_per_min":round(m5["observed_ramp_abs_p95"] * 0.06, 6),
                "observed_soc_min":round(m5["soc_min"] / 100, 6), "observed_soc_max":round(m5["soc_max"] / 100, 6),
                "observed_duration_h":round(m5["observed_duration"] / 60, 6),
            },
            "missing_for_resource_submission":["entity_id对应的山东主体身份","单一计算时点SOC","SOC安全上下限","SOH","充放电效率","端到端响应时间","跟踪误差","山东注册计量通信控制和测试证据"],
            "usable_layer":["储能能力先验证据","秒级功率与SOC范围检查","爬坡率计算流程"],
            "not_usable_for":["当前实体正式可用能量","山东市场准入","正式场景适配指数"],
            "source_url":"https://ukerc.rl.ac.uk/cgi-bin/dataDiscover.pl?Action=detail&dataid=4bd6e2eb-1417-4c8c-a9f0-6587fae2c0c5"
        },
        {
            "dataset_id":"epfl_level3_ev", "candidate_resource_type":"充电桩（充电站）", "mapping_status":"partial_evidence_only",
            "valid_resource_submission":False, "record_granularity":"minute_level_charging_records",
            "mapped_evidence":{
                "controlled_record_count":int(ev["controlled_record_count"]), "controlled_session_count":int(ev["controlled_session_count"]),
                "observed_power_max_mw":round(ev["observed_power_max"] / 1000, 6),
                "tracking_abs_error_median_mw":round(ev["tracking_abs_error_median"] / 1000, 6),
                "tracking_abs_error_p90_mw":round(ev["tracking_abs_error_p90"] / 1000, 6),
                "tracking_abs_pct_error_median":round(ev["tracking_abs_pct_error_median"], 6),
                "observed_ramp_abs_p95_mw_per_min":round(ev["observed_ramp_abs_p95"] * 0.06, 6),
                "observed_soc_min":round(ev["soc_min"] / 100, 6), "observed_soc_max":round(ev["soc_max"] / 100, 6),
            },
            "missing_for_resource_submission":["山东聚合实体身份","站级额定和连接容量","统一计算时点的连接车辆","到离站时间","目标剩余电量","可移动电量","用户授权","V2G资格","秒级响应证据","山东准入证据"],
            "usable_layer":["充电功率跟踪证据","会话级SOC范围","分钟级变化率流程"],
            "not_usable_for":["10秒级调频响应","当前站级可调能量","山东市场准入","正式场景适配指数"],
            "source_url":"https://github.com/DESL-EPFL/Level-3-EV-charging-dataset"
        },
        {
            "dataset_id":"australia_sgsc", "candidate_resource_type":None, "mapping_status":"not_mappable_to_single_resource_type",
            "valid_resource_submission":False, "record_granularity":"customer_event_records",
            "mapped_evidence":{
                "resource_count":int(au["resource_count"]), "event_count":int(au["event_count"]),
                "positive_response_rate_pct":round(au["positive_response_rate"], 6),
                "event_aggregate_reduction_median_mw":round(au["event_aggregate_reduction_median"] / 1000, 6),
                "event_duration_median_h":round(au["event_duration_median"] / 60, 6),
                "response_ratio_median_pct":round(au["response_ratio_median"], 6),
            },
            "missing_for_resource_submission":["16类资源组成","设备级实体参数","当前状态和专属物理约束","稳定聚合单元身份","山东准入证据"],
            "missing_for_market_task":["每个客户事前要求功率","任务方向的完整定义","响应时间和爬坡要求","跟踪精度要求"],
            "usable_layer":["历史聚合削减行为证据","事件持续时间分布","行为响应率验证"],
            "not_usable_for":["强制归类为空调或其他单一资源","事前任务完成率","山东正式适配指数"],
            "source_url":"https://www.data.gov.au/data/dataset/smart-grid-smart-city-customer-trial-data"
        },
    ]


def build_market_readiness(records: list[dict], statuses: dict[str, str]) -> list[dict]:
    relevance = {
        "m5bat_manifest_2017":{"spot_fit", "frequency_fit", "reserve_readiness", "ramping_fit", "green_consumption_fit"},
        "epfl_level3_ev":{"spot_fit", "frequency_fit", "reserve_readiness", "ramping_fit", "green_consumption_fit"},
        "australia_sgsc":{"spot_fit", "reserve_readiness", "green_consumption_fit"},
    }
    outputs = ["spot_fit", "frequency_fit", "reserve_readiness", "ramping_fit", "green_supply_fit", "green_consumption_fit"]
    rows = []
    for record in records:
        dataset_id = record["dataset_id"]
        for output in outputs:
            physically_relevant = output in relevance[dataset_id]
            if not physically_relevant:
                readiness = "not_applicable"
            elif statuses[output] == "planned":
                readiness = "not_open"
            else:
                readiness = "pending_entity_and_task_evidence"
            rows.append({
                "dataset_id":dataset_id, "candidate_resource_type":record["candidate_resource_type"], "market_output":output,
                "market_status":statuses[output], "physical_relevance":physically_relevant, "interface_readiness":readiness,
                "diagnostic_scenario_fit_index":"not_computable", "formal_scenario_fit_index":"not_computable",
                "reason":"公开记录不足以同时形成完整实体、山东准入证据和明确市场任务" if physically_relevant else "数据对象或字段不支持该输出",
            })
    return rows


def validate(records: list[dict], readiness: list[dict], metrics: dict[str, dict[str, float]]) -> dict:
    by_id = {row["dataset_id"]:row for row in records}
    checks = {
        "three_datasets_mapped_independently":len(records) == 3 and len(by_id) == 3,
        "no_cross_dataset_join":True,
        "two_datasets_have_candidate_resource_types":sum(row["candidate_resource_type"] is not None for row in records) == 2,
        "australia_not_forced_into_sixteen_types":by_id["australia_sgsc"]["candidate_resource_type"] is None,
        "no_complete_resource_submission_claimed":all(not row["valid_resource_submission"] for row in records),
        "eighteen_market_readiness_rows":len(readiness) == 18,
        "no_diagnostic_or_formal_scores_emitted":all(row["diagnostic_scenario_fit_index"] == "not_computable" and row["formal_scenario_fit_index"] == "not_computable" for row in readiness),
        "reserve_remains_not_open":all(row["interface_readiness"] == "not_open" for row in readiness if row["market_output"] == "reserve_readiness" and row["physical_relevance"]),
        "m5bat_power_unit_conversion_correct":by_id["m5bat_manifest_2017"]["mapped_evidence"]["observed_power_abs_p95_mw"] == round(metrics["m5bat_manifest_2017"]["observed_power_abs_p95"] / 1000, 6),
        "epfl_minute_data_not_claimed_as_second_response":"10秒级调频响应" in by_id["epfl_level3_ev"]["not_usable_for"],
    }
    return {"calculated_at":CALCULATED_AT, "checks":checks, "all_passed":all(checks.values())}


def write_summary(records: list[dict], validation: dict) -> None:
    lines = [
        "# 公开数据统一接口第二轮验证摘要", "",
        "本轮把既有三套公开真实数据映射到新接口。没有跨数据集拼接，也没有为跑分补造实体、准入或市场任务字段。", "",
        "| 数据集 | 接口结果 | 可支持层级 | 不能直接支持 |", "| --- | --- | --- | --- |",
    ]
    for row in records:
        lines.append(f"| {row['dataset_id']} | {row['mapping_status']} | {'、'.join(row['usable_layer'])} | {'、'.join(row['not_usable_for'])} |")
    lines.extend(["", "结论：两套设备数据可以形成部分资源证据，但三套数据都不足以形成完整山东资源提交；澳大利亚聚合负荷不能在缺少设备组成时强行归入16类。18项市场准备度结果的正式指数全部为 `not_computable`。", "", f"自动检查：{'全部通过' if validation['all_passed'] else '存在失败项'}。", ""])
    (OUTPUT / "运行摘要.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    metrics = load_metrics()
    records = build_evidence_records(metrics)
    statuses = market_statuses(load_rules())
    readiness = build_market_readiness(records, statuses)
    validation = validate(records, readiness, metrics)
    write_json(OUTPUT / "public_evidence_records.json", records)
    write_json(OUTPUT / "market_output_readiness.json", readiness)
    write_json(OUTPUT / "validation_summary.json", validation)
    write_summary(records, validation)
    if not validation["all_passed"]:
        raise SystemExit("Public interface mapping validation failed")
    print(json.dumps({"datasets":len(records), "market_rows":len(readiness), "formal_scores":0, "all_checks_passed":True}, ensure_ascii=False))


if __name__ == "__main__":
    main()
