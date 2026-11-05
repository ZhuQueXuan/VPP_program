"""Check the release tables and meter samples without estimating response."""
import bisect
import csv
import hashlib
import io
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path


HERE = Path(__file__).resolve().parent


def read_json(name):
    return json.loads((HERE / name).read_text(encoding="utf-8"))


def timestamp(value):
    try:
        stamp = datetime.fromisoformat(value)
    except ValueError:
        try:
            stamp = datetime.strptime(value, "%m/%d/%Y %H:%M:%S %z")
        except ValueError:
            return None
    return stamp if stamp.tzinfo is not None else None


def csv_rows(data, header=None):
    rows = csv.DictReader(io.StringIO(data.decode("utf-8-sig")), fieldnames=header)
    result = list(rows)
    assert all(None not in row and None not in row.values() for row in result)
    return rows.fieldnames, result


def file_bytes(entry):
    data = (HERE / entry["file"]).read_bytes()
    assert len(data) == entry["stored_bytes"]
    assert hashlib.sha256(data).hexdigest() == entry["sha256"]
    if entry["range"]:
        start, stop = map(int, entry["range"].removeprefix("bytes=").split("-"))
        assert len(data) == stop - start + 1
    else:
        assert len(data) == entry["source_bytes"]
    return data


def table_result(entry, product):
    header, rows = csv_rows(file_bytes(entry))
    counts = Counter()
    candidate = []
    start_keys = Counter()
    durations = Counter()
    end_formats = Counter()
    for line, row in enumerate(rows, start=2):
        depot = row["depot_id"]
        start = timestamp(row["start_time"])
        counts["missing_or_invalid_start"] += start is None
        if product == "A":
            end = start + timedelta(minutes=int(row["run_time"])) if start else None
        else:
            end_formats["slash" if "/" in row["end_time"] else "iso_like"] += 1
            end = timestamp(row["end_time"])
        counts["missing_or_invalid_end"] += end is None
        if start:
            start_keys[(depot, start)] += 1
        counts["zero_reported_turndown_kw"] += float(row["flexibility_turndown_kw"]) == 0
        if product == "B":
            counts["zero_final_turndown_kw"] += float(row["final_turndown_kw"]) == 0
        if not start or not end:
            continue
        seconds = int((end - start).total_seconds())
        durations[seconds] += 1
        if seconds > 0 and (product == "A" or seconds == 1800):
            candidate.append((product, depot, start, end, line, row["flexibility_turndown_kw"],
                              row.get("final_turndown_kw")))
    unique = [event for event in candidate if start_keys[event[1:3]] == 1]
    return {
        "source_csv": entry["file"],
        "fields": header,
        "row_count": len(rows),
        "depots": sorted({row["depot_id"] for row in rows}),
        "duplicate_identical_excess": len(rows) - len({tuple(row.values()) for row in rows}),
        "duplicate_start_keys": sum(count > 1 for count in start_keys.values()),
        "end_format_counts": end_formats,
        "duration_counts_seconds": dict(sorted(durations.items())),
        "unique_candidate_windows": len(unique),
        "field_checks": counts,
        "earliest_start": min(stamp for _, stamp in start_keys).isoformat(),
        "latest_start": max(stamp for _, stamp in start_keys).isoformat(),
    }, unique


def meter_result(entries):
    sample_checks = []
    measured = defaultdict(dict)
    ambiguous = set()
    header = None
    for index, entry in enumerate(entries):
        data = file_bytes(entry)
        # Ranges need not start or end on a CSV record boundary.
        data = data[:data.rindex(b"\n") + 1]
        if index:
            data = data[data.index(b"\n") + 1:]
            _, rows = csv_rows(data, header)
        else:
            header, rows = csv_rows(data)
        counts = Counter()
        stamps = []
        key_values = defaultdict(set)
        for row in rows:
            stamp = timestamp(row["ev_load_timestamp"])
            load = row["ev_load"]
            counts["no_verified_time"] += stamp is None
            counts["no_value"] += not load
            if load and float(load) == 0:
                counts["explicit_zero_with_time" if stamp else "zero_without_time"] += 1
            if not stamp or not load:
                continue
            depot = row["depot_id"]
            stamps.append(stamp)
            value = float(load)
            key = (depot, stamp)
            key_values[key].add(value)
            previous = measured[depot].get(stamp)
            if previous is not None and previous != value:
                ambiguous.add(key)
            measured[depot][stamp] = value
        sample_checks.append({
            "file": entry["file"], "range": entry["range"], "complete_rows": len(rows),
            "duplicate_identical_excess": len(rows) - len({tuple(row.values()) for row in rows}),
            "repeated_valid_time_depot_excess": len(stamps) - len(key_values),
            "conflicting_power_keys": sum(len(values) > 1 for values in key_values.values()),
            "depots": sorted({row["depot_id"] for row in rows}),
            "time_min": min(stamps).isoformat() if stamps else None,
            "time_max": max(stamps).isoformat() if stamps else None,
            "checks": counts,
        })
    for depot, stamp in ambiguous:
        del measured[depot][stamp]
    return header, sample_checks, measured


def candidates_with_meter_rows(events, measured):
    depot_times = {depot: sorted(values) for depot, values in measured.items()}
    joined = []
    for product, depot, start, end, line, reported_turndown, final_turndown in events:
        times = depot_times.get(depot, [])
        left = bisect.bisect_left(times, start)
        right = bisect.bisect_left(times, end)
        if left == right:
            continue
        stamps = times[left:right]
        joined.append({
            "product": product, "depot_id": depot, "event_csv_line": line,
            "start": start.isoformat(), "end": end.isoformat(),
            "source_flexibility_turndown_kw": reported_turndown,
            "source_final_turndown_kw": final_turndown,
            "meter_rows_with_unique_timestamp": len(stamps),
            "earliest_meter": stamps[0].isoformat(), "latest_meter": stamps[-1].isoformat(),
            "first_minus_start_seconds": (stamps[0] - start).total_seconds(),
            "end_minus_last_seconds": (end - stamps[-1]).total_seconds(),
            "maximum_interior_gap_seconds": max(
                ((b - a).total_seconds() for a, b in zip(stamps, stamps[1:])), default=None
            ),
            "explicit_zero_values": sum(measured[depot][stamp] == 0 for stamp in stamps),
        })
    return joined


def main():
    originals = {item["file"]: item for item in read_json("source_bytes.json")}
    a, events_a = table_result(originals["table_30.csv"], "A")
    b, events_b = table_result(originals["table_31.csv"], "B")
    entries = [originals["table_27_head.csv.part"]] + read_json("meter_window_bytes.json")
    meter_fields, meter_chunks, measured = meter_result(entries)
    joined = candidates_with_meter_rows(events_a + events_b, measured)
    with (HERE / "technical_matches.csv").open("w", newline="", encoding="utf-8") as file:
        keys = ["product", "depot_id", "event_csv_line", "start", "end",
                "source_flexibility_turndown_kw", "source_final_turndown_kw",
                "meter_rows_with_unique_timestamp", "earliest_meter", "latest_meter",
                "first_minus_start_seconds", "end_minus_last_seconds",
                "maximum_interior_gap_seconds", "explicit_zero_values"]
        writer = csv.DictWriter(file, fieldnames=keys)
        writer.writeheader()
        writer.writerows(joined)
    result = {
        "event_summaries": {"A": a, "B": b}, "meter_fields": meter_fields,
        "meter_chunks": meter_chunks, "complete_meter_sample_rows": sum(chunk["complete_rows"] for chunk in meter_chunks),
        "technical_intersections": {product: sum(row["product"] == product for row in joined) for product in ("A", "B")},
        "positive_source_turndown_among_intersections": {
            product: sum(row["product"] == product and float(row["source_flexibility_turndown_kw"]) > 0
                         for row in joined) for product in ("A", "B")
        },
        "intersection_rule": "Same depot, unique event start key, parsed offsets, event half-open window and exact observed timestamp. A uses recorded runtime; B requires exactly 30 minutes. Counts are matching observations, not full coverage or a claim the whole schedule interval was an active turndown.",
        "monetary_offer_column_matches": [
            field for field in a["fields"] + b["fields"]
            if any(token in field.casefold() for token in ("price", "payment", "currency", "reward", "compensation"))
        ],
        "admitted_incentive_events": 0,
    }
    (HERE / "sample_checks.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"A": a, "B": b, "meter_rows": result["complete_meter_sample_rows"],
                      "technical_intersections": result["technical_intersections"]}, indent=2))


if __name__ == "__main__":
    main()
