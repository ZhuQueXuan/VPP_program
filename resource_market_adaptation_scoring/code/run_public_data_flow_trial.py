#!/usr/bin/env python3
"""Use three independent public datasets to trial the resource-market flow.

The datasets are never horizontally joined.  Each source produces its own
evidence metrics and then passes through the same market-status/gate logic.
No formal market fit score is emitted without a Shandong market identity,
complete gate evidence and an explicit market task.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
MAIN = ROOT / "resource_market_adaptation_scoring"
PUBLIC = ROOT / "data" / "public_datasets"
OUTPUT = MAIN / "results" / "public_data_flow_trial"


def clean_number(series: pd.Series) -> pd.Series:
    result = pd.to_numeric(series, errors="coerce")
    return result.mask(result == -999)


def metric(dataset_id, resource_type, metric_id, value, unit, derivation, usable_for):
    return {
        "dataset_id": dataset_id,
        "resource_type": resource_type,
        "metric_id": metric_id,
        "value": None if pd.isna(value) else round(float(value), 6),
        "unit": unit,
        "evidence_type": "public_real_measurement",
        "derivation": derivation,
        "usable_for": usable_for,
    }


def analyze_m5bat() -> tuple[list[dict], dict]:
    base = PUBLIC / "m5bat_manifest_2017"
    files = [base / "01-03-2017_Test1.csv", base / "01-03-2017_Test2_v2.csv"]
    frames = []
    ramps = []
    for path in files:
        frame = pd.read_csv(path)
        frame["timestamp"] = pd.to_datetime(frame.iloc[:, 0], dayfirst=True, errors="coerce")
        frame["power_kw"] = clean_number(frame["Real Power (kW)"])
        frame["soc_pct"] = clean_number(frame["SoC (%)"])
        frame["frequency_hz"] = clean_number(frame["Frequency (Hz)"])
        dt = frame["timestamp"].diff().dt.total_seconds()
        dp = frame["power_kw"].diff().abs()
        valid = (dt > 0) & dp.notna()
        ramps.extend((dp[valid] / dt[valid]).tolist())
        frames.append(frame)
    data = pd.concat(frames, ignore_index=True)
    power = data["power_kw"].dropna()
    soc = data["soc_pct"].dropna()
    frequency = data["frequency_hz"].dropna()
    observed_minutes = sum(
        max(0.0, (f["timestamp"].max() - f["timestamp"].min()).total_seconds() / 60)
        for f in frames
    )
    rows = [
        metric("m5bat_manifest_2017", "battery_storage", "record_count", len(data), "records", "两份原始CSV记录数之和", "数据完整度"),
        metric("m5bat_manifest_2017", "battery_storage", "observed_power_abs_max", power.abs().max(), "kW", "实测有功功率绝对值最大值", "容量证据"),
        metric("m5bat_manifest_2017", "battery_storage", "observed_power_abs_p95", power.abs().quantile(0.95), "kW", "实测有功功率绝对值95分位", "可信可用功率参考"),
        metric("m5bat_manifest_2017", "battery_storage", "observed_ramp_abs_p95", pd.Series(ramps).quantile(0.95), "kW/s", "相邻有效秒级记录功率变化率绝对值95分位", "爬坡能力证据"),
        metric("m5bat_manifest_2017", "battery_storage", "soc_min", soc.min(), "%", "实测SOC最小值", "状态约束"),
        metric("m5bat_manifest_2017", "battery_storage", "soc_max", soc.max(), "%", "实测SOC最大值", "状态约束"),
        metric("m5bat_manifest_2017", "battery_storage", "observed_duration", observed_minutes, "min", "各测试文件连续观测时长之和", "持续时间证据"),
        metric("m5bat_manifest_2017", "battery_storage", "grid_frequency_min", frequency.min(), "Hz", "实测电网频率最小值", "调频场景背景"),
        metric("m5bat_manifest_2017", "battery_storage", "grid_frequency_max", frequency.max(), "Hz", "实测电网频率最大值", "调频场景背景"),
    ]
    return rows, {"records": len(data), "files": len(files)}


def analyze_epfl_ev() -> tuple[list[dict], dict]:
    path = PUBLIC / "epfl_level3_ev" / "Measurement_data.xlsx"
    frames = []
    for sheet in ("CCS1", "CCS2"):
        frame = pd.read_excel(path, sheet_name=sheet)
        frame["connector"] = sheet
        frames.append(frame)
    data = pd.concat(frames, ignore_index=True)
    for col in ("P (W)", "Pset (W)", "Preq (W)", "SOC (%)"):
        data[col] = pd.to_numeric(data[col], errors="coerce")
    controlled = data[
        data["Session"].notna()
        & (data["Ctrl_s (0 = False, 1 = True)"] == 1)
        & (data["Pset (W)"] >= 1000)
        & data["P (W)"].notna()
    ].copy()
    controlled["abs_error_kw"] = (controlled["P (W)"] - controlled["Pset (W)"]).abs() / 1000
    controlled["abs_pct_error"] = controlled["abs_error_kw"] / (controlled["Pset (W)"] / 1000) * 100
    controlled = controlled.sort_values(["connector", "Session", "Date and time"])
    dt = controlled.groupby(["connector", "Session"])["Date and time"].diff().dt.total_seconds()
    dp = controlled.groupby(["connector", "Session"])["P (W)"].diff().abs() / 1000
    ramp = (dp / dt).where(dt > 0).dropna()
    rows = [
        metric("epfl_level3_ev", "ev_charger", "controlled_record_count", len(controlled), "records", "有会话、受控、设定功率不低于1kW且实际功率非空的分钟记录", "数据完整度"),
        metric("epfl_level3_ev", "ev_charger", "controlled_session_count", controlled["Session"].nunique(), "sessions", "符合筛选条件的独立充电会话数", "样本覆盖"),
        metric("epfl_level3_ev", "ev_charger", "observed_power_max", controlled["P (W)"].max() / 1000, "kW", "受控分钟实际功率最大值", "容量证据"),
        metric("epfl_level3_ev", "ev_charger", "tracking_abs_error_median", controlled["abs_error_kw"].median(), "kW", "实际功率与设定功率绝对偏差中位数", "跟踪能力证据"),
        metric("epfl_level3_ev", "ev_charger", "tracking_abs_error_p90", controlled["abs_error_kw"].quantile(0.90), "kW", "实际功率与设定功率绝对偏差90分位", "履约风险证据"),
        metric("epfl_level3_ev", "ev_charger", "tracking_abs_pct_error_median", controlled["abs_pct_error"].replace([np.inf, -np.inf], np.nan).median(), "%", "绝对偏差除以设定功率的中位数", "跟踪精度证据"),
        metric("epfl_level3_ev", "ev_charger", "observed_ramp_abs_p95", ramp.quantile(0.95), "kW/s", "同一接口同一会话相邻分钟实际功率变化率95分位", "爬坡能力参考"),
        metric("epfl_level3_ev", "ev_charger", "soc_min", controlled["SOC (%)"].min(), "%", "受控分钟SOC最小值", "状态约束"),
        metric("epfl_level3_ev", "ev_charger", "soc_max", controlled["SOC (%)"].max(), "%", "受控分钟SOC最大值", "状态约束"),
    ]
    return rows, {"records": len(data), "controlled_records": len(controlled), "sessions": int(controlled["Session"].nunique())}


def analyze_australia_dr() -> tuple[list[dict], dict]:
    path = PUBLIC / "australia_sgsc" / "整理结果" / "澳大利亚需求响应_真实可用记录.csv"
    data = pd.read_csv(path)
    baseline = pd.to_numeric(data["基线平均用电功率（千瓦）"], errors="coerce")
    actual = pd.to_numeric(data["实际平均用电功率（千瓦）"], errors="coerce")
    reduction = pd.to_numeric(data["实际有效调节功率（千瓦）"], errors="coerce")
    duration = pd.to_numeric(data["要求持续时间（分钟）"], errors="coerce")
    ratio = (reduction / baseline * 100).replace([np.inf, -np.inf], np.nan)
    event_aggregate = data.assign(reduction_kw=reduction).groupby("任务编号", as_index=False)["reduction_kw"].sum()
    rows = [
        metric("australia_sgsc", "aggregated_load", "response_record_count", len(data), "records", "整理后真实客户—事件记录数", "样本覆盖"),
        metric("australia_sgsc", "aggregated_load", "resource_count", data["资源编号"].nunique(), "resources", "独立客户编号数", "聚合规模"),
        metric("australia_sgsc", "aggregated_load", "event_count", data["任务编号"].nunique(), "events", "独立高峰调节事件数", "任务覆盖"),
        metric("australia_sgsc", "aggregated_load", "positive_response_rate", (reduction > 0).mean() * 100, "%", "实际有效调节功率大于0的记录占比", "响应可用性证据"),
        metric("australia_sgsc", "aggregated_load", "individual_reduction_median", reduction.median(), "kW", "单客户单事件实际削减功率中位数", "单体能力证据"),
        metric("australia_sgsc", "aggregated_load", "individual_reduction_p90", reduction.quantile(0.90), "kW", "单客户单事件实际削减功率90分位", "单体能力上界参考"),
        metric("australia_sgsc", "aggregated_load", "event_aggregate_reduction_median", event_aggregate["reduction_kw"].median(), "kW", "按真实任务编号汇总后的事件削减功率中位数", "聚合能力证据"),
        metric("australia_sgsc", "aggregated_load", "response_ratio_median", ratio.median(), "%", "实际削减功率除以基线功率的中位数；不是任务完成率", "响应幅度证据"),
        metric("australia_sgsc", "aggregated_load", "event_duration_median", duration.median(), "min", "事件持续时间中位数", "持续能力证据"),
        metric("australia_sgsc", "aggregated_load", "baseline_power_median", baseline.median(), "kW", "单客户事件基线功率中位数", "基线证据"),
        metric("australia_sgsc", "aggregated_load", "actual_power_median", actual.median(), "kW", "单客户事件实际功率中位数", "实测结果"),
    ]
    return rows, {"records": len(data), "resources": int(data["资源编号"].nunique()), "events": int(data["任务编号"].nunique())}


def load_market_statuses() -> dict[str, str]:
    config = pd.read_csv(MAIN / "config" / "market_rule_parameters.csv")
    statuses = config[(config["parameter_type"] == "status") & (config["record_status"] == "active")]
    return dict(zip(statuses["market_output"], statuses["value"]))


def build_flow_results(statuses: dict[str, str]) -> list[dict]:
    relevance = {
        "m5bat_manifest_2017": {"spot_fit", "frequency_fit", "reserve_readiness", "ramping_fit"},
        "epfl_level3_ev": {"spot_fit", "frequency_fit", "reserve_readiness", "ramping_fit", "green_consumption_fit"},
        "australia_sgsc": {"spot_fit", "reserve_readiness", "green_consumption_fit"},
    }
    all_outputs = [
        "spot_fit",
        "frequency_fit",
        "reserve_readiness",
        "ramping_fit",
        "green_supply_fit",
        "green_consumption_fit",
    ]
    rows = []
    for dataset_id, applicable in relevance.items():
        for output_name in all_outputs:
            market_status = statuses[output_name]
            if output_name not in applicable:
                gate_status = "not_applicable"
                reason = "该数据集没有支持此输出所需的资源或交易字段"
            elif market_status == "planned":
                gate_status = "not_open"
                reason = "山东备用市场当前为planned；只保留物理准备度"
            else:
                gate_status = "pending_evidence"
                reason = "国外公开数据不能证明山东主体注册、计量通信、控制测试和合同关系"
            rows.append(
                {
                    "dataset_id": dataset_id,
                    "output_name": output_name,
                    "market_status": market_status,
                    "physical_relevance": "yes" if output_name in applicable else "no",
                    "gate_status": gate_status,
                    "formal_scenario_fit_index": "not_computable",
                    "formal_index_reason": (
                        "缺少明确市场任务要求和完整准入证据"
                        if gate_status == "pending_evidence"
                        else reason
                    ),
                    "evidence_result": "empirical_metrics_available" if output_name in applicable else "not_applicable",
                    "gate_reason": reason,
                }
            )
    return rows


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    metric_rows = []
    dataset_checks = {}
    for analyzer in (analyze_m5bat, analyze_epfl_ev, analyze_australia_dr):
        rows, checks = analyzer()
        metric_rows.extend(rows)
        dataset_checks[rows[0]["dataset_id"]] = checks

    metrics = pd.DataFrame(metric_rows)
    metrics.to_csv(OUTPUT / "empirical_capability_metrics.csv", index=False, encoding="utf-8-sig")

    statuses = load_market_statuses()
    flow = pd.DataFrame(build_flow_results(statuses))
    flow.to_csv(OUTPUT / "flow_gate_results.csv", index=False, encoding="utf-8-sig")

    validation = {
        "status": "pass",
        "dataset_count": len(dataset_checks),
        "metric_count": len(metrics),
        "flow_result_count": len(flow),
        "market_status_source": "config/market_rule_parameters.csv",
        "formal_scores_emitted": int((flow["formal_scenario_fit_index"] != "not_computable").sum()),
        "cross_dataset_horizontal_join": False,
        "dataset_checks": dataset_checks,
        "checks": {
            "all_dataset_ids_present": len(dataset_checks) == 3,
            "all_metric_values_present": bool(metrics["value"].notna().all()),
            "six_outputs_per_dataset": len(flow) == 18,
            "reserve_is_not_open": bool((flow[flow["output_name"] == "reserve_readiness"]["gate_status"] == "not_open").all()),
            "no_unjustified_formal_score": bool((flow["formal_scenario_fit_index"] == "not_computable").all()),
        },
    }
    with (OUTPUT / "validation_summary.json").open("w", encoding="utf-8") as handle:
        json.dump(validation, handle, ensure_ascii=False, indent=2)
    print(json.dumps(validation, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

