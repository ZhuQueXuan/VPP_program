"""Recompute source joins and descriptive checks. Writes JSON to stdout."""

import csv
import gzip
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from email.utils import parsedate_to_datetime
from pathlib import Path
from statistics import mean
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "work"
ACN = ROOT / "data/ACN_real_user_benchmark_v1_20261102"
METADATA = WORK / "b1_real_training_data_20261102/source_documents/acn_official_Caltech_2020.json"
STORE = WORK / "b1_response_factors_20261104/raw/ev.csv"
HARVARD = WORK / "b1_real_response_data_20261103/ev_review/workplace_original.csv"
PILOT = "Actual Pilot (A)"
POWER = "Power (kW)"
CURRENT = "Charging Current (A)"
ENERGY = "Energy Delivered (kWh)"


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def acn_point(row):
    return {
        "csv_line": row["line"],
        "utc": row["time"].isoformat(),
        "pilot_A": row[PILOT],
        "current_A": row[CURRENT],
        "power_kW": row[POWER],
        "energy_kWh": row[ENERGY],
    }


def inspect_acn_trace(entry, session, anchor, prior):
    path = ROOT / entry["local"]
    with gzip.open(path, "rt", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        columns = reader.fieldnames
        rows = []
        for line, raw in enumerate(reader, 2):
            stamp = datetime.fromisoformat(raw[""])
            assert stamp.utcoffset() == timedelta(0)
            rows.append({"line": line, "time": stamp, **{
                name: float(raw[name]) if raw[name] else None
                for name in (PILOT, POWER, CURRENT, ENERGY)
            }})
    pref = [row for row in rows if row["time"] < anchor and row[ENERGY] is not None]
    meter = max(pref, key=lambda row: row["time"], default=None)
    disconnect = parsedate_to_datetime(session["disconnectTime"])
    # Inspect a downward edge plus a subsequent up-edge in the same raw trace.
    # The timing rule is illustrative, not a task or a recovery label.
    down, up = None, None
    for before, after in zip(rows, rows[1:]):
        if not timedelta(0) < after["time"] - before["time"] <= timedelta(seconds=15):
            continue
        if before[PILOT] is None or after[PILOT] is None:
            continue
        step = after[PILOT] - before[PILOT]
        if down is None and after["time"] >= anchor and step <= -2:
            down = [acn_point(before), acn_point(after)]
        elif down and step >= 2:
            if after["time"] - datetime.fromisoformat(down[1]["utc"]) <= timedelta(minutes=15):
                up = [acn_point(before), acn_point(after)]
            break
    return {
        "source": entry["local"], "sha256": sha256(path),
        "session_id": entry["session_id"], "station_id": session["stationID"],
        "site_id": session["siteID"], "site_timezone": session["timezone"],
        "metadata_connection_utc": parsedate_to_datetime(session["connectionTime"]).isoformat(),
        "metadata_disconnect_utc": disconnect.isoformat(),
        "connected_at_research_anchor": anchor < disconnect,
        "first_meter_row": acn_point(rows[0]), "meter_columns": columns,
        "meter_rows": len(rows), "research_anchor_utc": anchor.isoformat(),
        "prior_revision": {key: prior[key] for key in (
            "modifiedAt", "kWhRequested", "requestedDeparture", "paymentRequired"
        )} if prior else None,
        "after_or_at_anchor_revisions": sum(
            parsedate_to_datetime(item["modifiedAt"]) >= anchor
            for item in session["userInputs"] or [] if item["modifiedAt"]
        ),
        "last_pre_anchor_energy_row": acn_point(meter) if meter else None,
        "last_pre_anchor_energy_age_s": (anchor - meter["time"]).total_seconds() if meter else None,
        "planned_minutes_remaining": (
            (parsedate_to_datetime(prior["requestedDeparture"]) - anchor).total_seconds() / 60
            if prior and prior["requestedDeparture"] else None
        ),
        "requested_minus_meter_kWh": (
            prior["kWhRequested"] - meter[ENERGY]
            if prior and prior["kWhRequested"] is not None and meter and anchor < disconnect else None
        ),
        "first_post_anchor_pilot_drop_at_least_2A": down,
        "next_pilot_increase_at_least_2A_within_15min": up,
    }


def audit_acn():
    manifest_path = ACN / "training_sessions.json"
    manifest = read_json(manifest_path)
    records = read_json(METADATA)["_items"]
    by_id = {item["sessionID"]: item for item in records}
    assert len(by_id) == len(records)
    assert len({row["session_id"] for row in manifest}) == len(manifest)
    counts = Counter()
    revisions_fields = set()
    examples = []
    stations = set()
    for index, entry in enumerate(manifest):
        session = by_id[entry["session_id"]]
        filename_key = session["sessionID"].split("_", 4)
        station = "-".join(filename_key[:4])
        assert station == session["stationID"] == entry["station_group"].split("/")[-1]
        suffix = filename_key[4].replace(" ", "T").replace(":", "-").replace(".", "-")
        assert Path(entry["local"]).name == f"{station}-{suffix}.csv.gz"
        assert (METADATA.name == Path(entry["metadata_source"]).name)
        anchor = parsedate_to_datetime(session["connectionTime"]) + timedelta(minutes=30)
        revisions = session["userInputs"] or []
        revisions_fields.update(key for row in revisions for key in row)
        timed = [(parsedate_to_datetime(row["modifiedAt"]), row) for row in revisions if row["modifiedAt"]]
        before = [(stamp, row) for stamp, row in timed if stamp < anchor]
        prior = max(before, key=lambda pair: pair[0])[1] if before else None
        counts["with_input_revisions"] += bool(revisions)
        counts["with_timed_pre_anchor_revision"] += bool(prior)
        counts["with_revision_at_or_after_anchor"] += any(stamp >= anchor for stamp, _ in timed)
        counts["with_pre_anchor_requested_kWh"] += bool(prior and prior["kWhRequested"] is not None)
        counts["with_pre_anchor_planned_departure"] += bool(prior and prior["requestedDeparture"])
        counts["with_pre_anchor_payment_required_true"] += bool(prior and prior["paymentRequired"])
        counts["connected_at_anchor_from_session_bounds"] += anchor < parsedate_to_datetime(session["disconnectTime"])
        if index < 4 or (station not in stations and len(stations) < 6):
            examples.append(inspect_acn_trace(entry, session, anchor, prior))
        stations.add(station)
    return {
        "training_manifest_sha256": sha256(manifest_path), "metadata_sha256": sha256(METADATA),
        "training_sessions_joined": len(manifest), "training_users": len({x["user_group"] for x in manifest}),
        "official_metadata_rows": len(records), "metadata_columns": sorted({key for row in records for key in row}),
        "user_input_fields": sorted(revisions_fields), "counts": counts,
        "trace_examples": examples,
    }


def store_point(row):
    return {key: value for key, value in row.items() if key not in {"local", "utc"}} | {
        "local": row["local"].isoformat(), "utc": row["utc"].isoformat(),
    }


def audit_store():
    with STORE.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        columns = reader.fieldnames
        rows = []
        for line, row in enumerate(reader, 2):
            utc = datetime.fromisoformat(row.pop(""))
            assert utc.utcoffset() == timedelta(0)
            rows.append(row | {"line": line, "utc": utc, "local": utc.astimezone(ZoneInfo("Europe/Lisbon"))})
    assert all(b["utc"] - a["utc"] == timedelta(hours=1) for a, b in zip(rows, rows[1:]))
    by_utc = {row["utc"]: row for row in rows}
    local_keys = Counter(row["local"].replace(tzinfo=None).isoformat() for row in rows)
    repeated_local = [store_point(row) for row in rows if local_keys[row["local"].replace(tzinfo=None).isoformat()] > 1]
    # Fixed single local clock hour, then stratify by weekday/weekend. Descriptive only.
    groups = defaultdict(list)
    for row in rows:
        if (row["local"].hour == 13 and row["availability_service"] == "1"
                and row["availability_discounts"] == "1" and row["holiday"] == "0"):
            day_type = "weekend" if row["local"].weekday() >= 5 else "weekday"
            groups[(day_type, Decimal(row["discount"]))].append(row)
    descriptions = []
    for (kind, discount), group in sorted(groups.items()):
        meter = [Decimal(row["consumption_total"]) for row in group if row["consumption_total"]]
        price = [Decimal(row["market_price"]) for row in group if row["market_price"]]
        descriptions.append({
            "day_type": kind, "discount_fraction": str(discount), "hours": len(group),
            "meter_nonmissing": len(meter),
            "average_meter_kW": float(mean(meter)) if meter else None,
            "market_price_nonmissing": len(price),
            "average_market_price_csv_units": float(mean(price)) if price else None,
        })
    first_offers = [next(row for row in rows if Decimal(row["discount"]) == d)
                    for d in sorted({Decimal(row["discount"]) for row in rows})]
    lag_example = next(row for row in rows if Decimal(row["discount"]) > 0
                       and (lag := by_utc.get(row["utc"] - timedelta(hours=48)))
                       and lag["consumption_total"])
    # The earlier completed hour is a research proxy. Individual publication times are missing.
    for row in first_offers + [lag_example]:
        lag = by_utc.get(row["utc"] - timedelta(hours=48))
        row["lag48h_csv_line"] = lag["line"] if lag else None
        row["lag48h_meter_kW"] = lag["consumption_total"] if lag else None
    return {
        "sha256": sha256(STORE), "git_blob_sha1": hashlib.sha1(
            f"blob {STORE.stat().st_size}\0".encode() + STORE.read_bytes()
        ).hexdigest(),
        "columns": columns, "rows": len(rows), "unique_utc_keys": len(by_utc),
        "utc_first": rows[0]["utc"].isoformat(), "utc_last": rows[-1]["utc"].isoformat(),
        "missing_counts": {key: sum(not row[key] for row in rows) for key in columns if key},
        "discount_counts": dict(Counter(row["discount"] for row in rows)),
        "zero_meter_hours": sum(bool(row["consumption_total"]) and Decimal(row["consumption_total"]) == 0 for row in rows),
        "raw_hour_matches_utc": sum(int(row["hour"]) == row["utc"].hour for row in rows),
        "raw_hour_matches_local": sum(int(row["hour"]) == row["local"].hour for row in rows),
        "repeated_local_clock_examples": repeated_local,
        "first_raw_row_per_discount": [store_point(row) for row in first_offers],
        "first_positive_discount_with_48h_history": store_point(lag_example),
        "descriptive_13_local": descriptions,
    }


def audit_harvard():
    with HARVARD.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        rows = list(reader)
        columns = reader.fieldnames
    return {"sha256": sha256(HARVARD), "columns": columns, "sessions": len(rows),
            "unique_session_ids": len({row["sessionId"] for row in rows}),
            "users": len({row["userId"] for row in rows}),
            "positive_payment_sessions": sum(Decimal(row["dollars"]) > 0 for row in rows)}


if __name__ == "__main__":
    print(json.dumps({"acn": audit_acn(), "supermarket": audit_store(), "harvard": audit_harvard()},
                     ensure_ascii=False, indent=2, allow_nan=False))
