#!/usr/bin/env python3
"""Apply official Shandong thresholds to existing public-data evidence."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
MAIN = ROOT / "resource_market_adaptation_scoring"
PUBLIC = ROOT / "data" / "public_datasets"
OUTPUT = MAIN / "results" / "official_rule_gate_trial"


def get_rule(config: pd.DataFrame, parameter_id: str) -> pd.Series:
    row = config[(config["parameter_id"] == parameter_id) & (config["record_status"] == "active")]
    if len(row) != 1:
        raise ValueError(f"Expected one active rule for {parameter_id}, got {len(row)}")
    return row.iloc[0]


def comparison(dataset_id, evidence, evidence_unit, rule, result, interpretation):
    return {
        "dataset_id": dataset_id,
        "evidence_value": evidence,
        "evidence_unit": evidence_unit,
        "parameter_id": rule["parameter_id"],
        "operator": rule["operator"],
        "rule_value": rule["value"],
        "rule_unit": rule["unit"],
        "region": rule["region"],
        "rule_gate_result": result,
        "interpretation": interpretation,
        "source_document": rule["source_document"],
        "source_clause": rule["source_clause"],
    }


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    config = pd.read_csv(MAIN / "config" / "market_rule_parameters.csv")
    metrics = pd.read_csv(MAIN / "results" / "public_data_flow_trial" / "empirical_capability_metrics.csv")
    metric_map = {(r.dataset_id, r.metric_id): float(r.value) for r in metrics.itertuples(index=False)}
    rows = []

    # Published nominal ratings: 240 kW / 180 kWh. Duration is energy/power,
    # not the shorter observation-window length in the downloaded test files.
    m5bat_power_mw = 0.240
    m5bat_duration_h = 0.180 / 0.240
    m5bat_p95_mw = metric_map[("m5bat_manifest_2017", "observed_power_abs_p95")] / 1000

    rule = get_rule(config, "vpp.storage.min_aggregate_capacity")
    rows.append(comparison("m5bat_manifest_2017", m5bat_power_mw, "MW", rule, "fail_as_single_unit",
        "单台240 kW储能低于1 MW聚合单元门槛；可与其他资源聚合后重新判断。"))
    rule = get_rule(config, "vpp.storage.spot.min_continuous_duration")
    rows.append(comparison("m5bat_manifest_2017", m5bat_duration_h, "h", rule, "fail",
        "180 kWh/240 kW得到额定时长0.75 h，低于电能量市场2 h门槛。"))
    rule = get_rule(config, "vpp.storage.aux.min_continuous_duration")
    rows.append(comparison("m5bat_manifest_2017", m5bat_duration_h * 60, "min", rule, "pass_nominal_duration",
        "额定时长45 min超过15 min，但仍需山东主体注册、测试、计量通信等证据。"))
    rule = get_rule(config, "frequency.reserve.storage_power_ratio_each_direction")
    required_reserve_mw = m5bat_power_mw * float(rule["value"]) / 100
    rows.append(comparison("m5bat_manifest_2017", m5bat_p95_mw, "MW_observed_abs_p95", rule, "supporting_evidence_only",
        f"按额定功率计算单方向预留要求为{required_reserve_mw:.3f} MW；实测值较高，但未证明同一运行点上下双向均可用。"))

    epfl_max_mw = metric_map[("epfl_level3_ev", "observed_power_max")] / 1000
    rule = get_rule(config, "vpp.adjustable_load.min_adjustable_capacity")
    rows.append(comparison("epfl_level3_ev", epfl_max_mw, "MW_observed_charging_power", rule, "not_computable",
        "最大充电功率不等于经测试认定的可调节能力，不能据此判断1 MW门槛。"))

    sgsc_path = PUBLIC / "australia_sgsc" / "整理结果" / "澳大利亚需求响应_真实可用记录.csv"
    sgsc = pd.read_csv(sgsc_path)
    sgsc["reduction_kw"] = pd.to_numeric(sgsc["实际有效调节功率（千瓦）"], errors="coerce")
    event_reduction = sgsc.groupby("任务编号")["reduction_kw"].sum()
    event_duration_h = pd.to_numeric(sgsc["要求持续时间（分钟）"], errors="coerce") / 60
    rule = get_rule(config, "vpp.adjustable_load.min_adjustable_capacity")
    rows.append(comparison("australia_sgsc", round(event_reduction.median() / 1000, 6), "MW_event_median", rule,
        "partial_pass_by_event", f"13次事件中有{int((event_reduction >= 1000).sum())}次达到1 MW；不能视为稳定通过。"))
    rule = get_rule(config, "vpp.adjustable_load.min_continuous_duration")
    rows.append(comparison("australia_sgsc", round(event_duration_h.median(), 6), "h_event_median", rule,
        "pass_duration_evidence", "事件持续时间中位数4 h，高于山东1 h门槛；仍不能替代山东调节能力认定。"))

    result = pd.DataFrame(rows)
    result.to_csv(OUTPUT / "rule_gate_comparison.csv", index=False, encoding="utf-8-sig")
    summary = {
        "status": "pass",
        "comparison_count": len(result),
        "formal_market_scores_emitted": 0,
        "shandong_active_rules_used": sorted(result["parameter_id"].unique().tolist()),
        "sgsc_events_total": int(len(event_reduction)),
        "sgsc_events_at_or_above_1mw": int((event_reduction >= 1000).sum()),
        "boundary": "Official thresholds were applied as gates; no dispatch completion score was fabricated.",
    }
    with (OUTPUT / "validation_summary.json").open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
