"""Audit the nested, bounded plan and dispatch release files."""
import csv
import io
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, time

from audit_samples import HERE, file_bytes, read_json, timestamp


def parse_time(value):
    if not isinstance(value, str):
        return None
    value = value.strip()
    if value.endswith(" Z"):
        value = value.removesuffix(" Z") + " +00:00"
    value = re.sub(r"(\.)(\d+)(?=[+-]\d\d:\d\d$)",
                   lambda match: "." + match[2][:6].ljust(6, "0"), value)
    return timestamp(value)


def csv_messages(entry):
    rows = csv.DictReader(io.StringIO(file_bytes(entry).decode("utf-8-sig")), delimiter=";")
    for line, row in enumerate(rows, start=2):
        yield line, row, json.loads(row["message"])


def plan_entry(entry, plan_index):
    counts = Counter()
    products = defaultdict(Counter)
    fields = set()
    price_fields = set()
    for line, row, plan in csv_messages(entry):
        counts["message_rows"] += 1
        fields.update(plan)
        product = (plan.get("type") or "").removeprefix("Product ")
        if product not in {"A", "B"}:
            counts["other_or_missing_type"] += 1
            continue
        for event in plan.get("flexibilityEvents") or []:
            counts["nested_windows"] += 1
            price_fields.update(key for key in event if "price" in key.lower())
            products[product][str(event.get("utilisationPrice"))] += 1
            date = parse_time(plan["date"])
            created = parse_time(plan["timestamp"])
            if date is None or created is None:
                counts["unknown_plan_time"] += 1
                continue
            start = datetime.combine(date.date(), time.fromisoformat(event["startTime"]), tzinfo=date.tzinfo)
            plan_index[(product, str(plan["depotId"]), start)].append({
                "file": entry["file"], "line": line, "offset": row["offset"],
                "plan_id": plan["flexibilityId"], "event_id": event["flexibilityEventId"],
                "recorded_at": created.isoformat(), "operation": plan["operation"],
                "source_price_fields": {key: event[key] for key in event if "price" in key.lower()},
                "source_turndown_kw": event["flexibilityTurnDownKW"],
            })
            counts["planned_before_window"] += created < start
    return {"counts": counts, "plan_fields": sorted(fields), "nested_price_fields": sorted(price_fields),
            "utilisation_price_counts_by_product": products}


def dispatch_entry(entry, dispatch_index):
    counts = Counter()
    fields = set()
    for line, _, payload in csv_messages(entry):
        counts["message_rows"] += 1
        for message in payload["dispatches"]:
            counts["nested_dispatch_rows"] += 1
            fields.update(message)
            start = parse_time(message["dispatch_start_timestamp"])
            created = parse_time(message["created_timestamp"])
            end = parse_time(message["dispatch_end_timestamp"])
            counts["end_sentinel_year_1"] += end is not None and end.year == 1
            if start is None or created is None:
                counts["unknown_dispatch_time"] += 1
                continue
            depot, product = str(message["depot_id"]), message["product_type"]
            dispatch_index[(product, depot, start)].append({
                "file": entry["file"], "line": line, "created_at": created.isoformat(),
                "created_at_raw": message["created_timestamp"],
                "source_end": message["dispatch_end_timestamp"],
                "source_dispatch_kw": message["dispatch_power_kw"],
            })
    return {"counts": counts, "dispatch_fields": sorted(fields)}


def main():
    entries = read_json("trace_bytes.json")
    plans = defaultdict(list)
    dispatches = defaultdict(list)
    checks = {}
    for entry in entries:
        file = entry["file"]
        checks[file] = plan_entry(entry, plans) if file.startswith("table_25") else dispatch_entry(entry, dispatches)
    raw_matches = []
    with (HERE / "technical_matches.csv").open(encoding="utf-8", newline="") as file:
        for row in csv.DictReader(file):
            product, depot, start = row["product"], row["depot_id"], parse_time(row["start"])
            key = (product, depot, start)
            if key not in dispatches and key not in plans:
                continue
            prospective = [
                plan for plan in plans[key] if parse_time(plan["recorded_at"]) < start
            ]
            raw_matches.append({"summary_and_meter": row, "prospective_plan_messages": prospective,
                                "dispatch_messages_at_same_start": dispatches[key]})
    all_three = [
        match for match in raw_matches
        if match["dispatch_messages_at_same_start"] and any(
            (plan["source_price_fields"].get("utilisationPrice") or 0) > 0
            and plan["source_turndown_kw"] > 0
            and parse_time(plan["recorded_at"]) <= min(parse_time(item["created_at"])
                                                       for item in match["dispatch_messages_at_same_start"])
            for plan in match["prospective_plan_messages"]
        )
    ]
    result = {
        "files": checks,
        "method": "Join exact product/depot/UTC start from nested payloads to summary and metered timestamps. Keep all candidate plan versions before the window. Source clock interpretation uses the date's explicit UTC and nested time of day, checked by exact dispatch match. At least one positive recorded utilisation price and positive planned turndown before dispatch identifies only a linkage candidate, pending contract/assignment and full quality evidence.",
        "candidate_price_dispatch_meter_count": len(all_three),
        "raw_price_values_with_dispatch_and_meter": sorted({
            plan["source_price_fields"]["utilisationPrice"]
            for match in all_three for plan in match["prospective_plan_messages"]
            if (plan["source_price_fields"].get("utilisationPrice") or 0) > 0 and plan["source_turndown_kw"] > 0
        }),
        "price_dispatch_meter_candidates": all_three,
        "joined": raw_matches,
        "admitted_for_effect_estimation": 0,
    }
    (HERE / "trace_checks.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("files", "candidate_price_dispatch_meter_count",
                                                  "raw_price_values_with_dispatch_and_meter")}, indent=2))


if __name__ == "__main__":
    main()
