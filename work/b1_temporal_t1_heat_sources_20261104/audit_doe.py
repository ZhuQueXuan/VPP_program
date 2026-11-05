"""Audit the two small public DOE tables without deriving event times from power."""
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path

import pandas as pd


HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"
SOURCE = ("438", "461")
NEEDED = ("alias", "timestamp", "local_time", "unique_hour", "curr_curtail_id",
          "curr_curtail_type", "curr_curtail_numeric", "curr_watts", "opt_out",
          "oper_state", "running", "comm_status")


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def audit_one(code):
    file = RAW / f"DOE_ORLa{code}_raw.csv"
    data = pd.read_csv(file)
    assert set(NEEDED) <= set(data) and data.alias.unique().tolist() == ["ORLa"+code]
    t = pd.to_datetime(data.local_time, format="%Y-%m-%d %H:%M:%S")
    h = pd.to_datetime(data.unique_hour, format="%Y-%m-%d %H")
    rel_numeric = data.timestamp - data.timestamp.iloc[0]
    rel_clock = (t - t.iloc[0]).dt.total_seconds()
    gaps = t.diff().dt.total_seconds()
    numeric_gaps = data.timestamp.diff()
    assert t.is_monotonic_increasing and not t.duplicated().any()
    assert data.timestamp.is_monotonic_increasing and not data.timestamp.duplicated().any()
    control = data.curr_curtail_type
    # 8 is described as End Shed/Run Normal in the related EcoPort study.
    # +100 with codes 1/11 marks a candidate curtailment in these tables.
    # This is a status-row transition bracket. It is not an independent command timestamp.
    prior_cut = control.shift().isin([1, 11]) & data.curr_curtail_numeric.shift().gt(0)
    changed_id = data.curr_curtail_id.ne(data.curr_curtail_id.shift())
    hit = prior_cut & control.eq(8) & changed_id
    ordinary = hit & gaps.between(1, 3660) & numeric_gaps.between(1, 3660)
    transitions = []
    for i in data.index[hit]:
        transitions.append({
            "last_cut_csv_line": int(i+1), "first_normal_csv_line": int(i+2),
            "last_cut_local_clock": data.local_time.iat[i-1],
            "first_normal_local_clock": data.local_time.iat[i],
            "last_cut_code": int(control.iat[i-1]), "normal_code": int(control.iat[i]),
            "cut_status_id": int(data.curr_curtail_id.iat[i-1]),
            "normal_status_id": int(data.curr_curtail_id.iat[i]),
            "local_bracket_seconds": float(gaps.iat[i]),
            "numeric_bracket_seconds": float(numeric_gaps.iat[i]),
            "ordinary_hourly_gap": bool(ordinary.iat[i]),
            "t1_eligible": False,
        })
    first = int(data.index[ordinary][0])
    anchor = t.iat[first]
    keep = t.between(anchor-pd.Timedelta(hours=5), anchor+pd.Timedelta(hours=6))
    extract = data.loc[keep, list(NEEDED)].copy()
    extract.insert(0, "source_csv_line", extract.index+2)
    local_clock = t.loc[keep]
    after_idx = t.index[(t >= anchor) & (t <= anchor+pd.Timedelta(hours=6))]
    post_deltas = t.loc[after_idx].diff().dt.total_seconds().dropna()
    result = {
        "alias": data.alias.iat[0], "rows": len(data), "columns": list(data.columns),
        "local_first": data.local_time.iat[0], "local_last": data.local_time.iat[-1],
        "local_clock_includes_utc_offset": False, "numeric_epoch_confirmed": False,
        "local_gap_min_s": float(gaps.min()), "local_gap_median_s": float(gaps.median()),
        "local_gap_max_s": float(gaps.max()), "numeric_gap_min_s": float(numeric_gaps.min()),
        "local_gaps_over_3660_s": int(gaps.gt(3660).sum()),
        "local_gaps_at_most_450_s": int(gaps.le(450).sum()),
        "max_absolute_elapsed_difference_numeric_vs_local_s": float((rel_numeric-rel_clock).abs().max()),
        "first_unique_hour_label": str(h.iat[0]), "unique_hour_duplicate_rows": int(h.duplicated().sum()),
        "power_zero_rows": int(data.curr_watts.eq(0).sum()),
        "power_missing_rows": int(data.curr_watts.isna().sum()),
        "rows_with_any_empty_cell": int(data.isna().any(axis=1).sum()),
        "power_min_W": float(data.curr_watts.min()), "power_max_W": float(data.curr_watts.max()),
        "control_row_counts": dict(Counter(map(int, control))),
        "ordinary_candidate_release_brackets": int(ordinary.sum()),
        "long_gap_candidate_release_brackets": int(hit.sum()-ordinary.sum()),
        "first_example": {
            "last_cut_csv_line": first+1, "first_normal_csv_line": first+2,
            "local_bracket_s": float(gaps.iat[first]),
            "following_6h_row_count_including_first_normal_row": len(after_idx),
            "max_following_gap_s": float(post_deltas.max()),
            "non_normal_following_rows_including_6h_endpoint": int(control.loc[after_idx].ne(8).sum()),
            "slice_rows": len(extract),
            "slice_clock_bounds": [str(local_clock.iloc[0]), str(local_clock.iloc[-1])],
        },
        "t1_eligible_events": 0,
    }
    return result, transitions, extract


def main():
    receipts = json.loads((RAW / "doe_fetch.json").read_text(encoding="utf-8"))
    assert all(digest(RAW / r["file"]) == r["sha256"] for r in receipts if "file" in r)
    review, slices, brackets = [], [], []
    for alias in SOURCE:
        row, transitions, trace = audit_one(alias)
        review.append(row)
        slices.append(trace)
        brackets.extend({"alias": row["alias"], **t} for t in transitions)
    a, b = [{r["normal_status_id"] for r in brackets
             if r["alias"] == row["alias"] and r["ordinary_hourly_gap"]} for row in review]
    pd.concat(slices).to_csv(HERE / "doe_first_control_transition_points.csv", index=False)
    pd.DataFrame(brackets).to_csv(HERE / "doe_status_transition_ledger.csv", index=False)
    out = {
        "audit_source_sha256": digest(Path(__file__)),
        "sample_selection": "first ordinary code 1/11 (+) to code 8 with different status ID, chronological per alias",
        "public_site_entries_sampled": len(review), "device_aliases": len(review),
        "ordinary_brackets_shared_normal_status_ids": len(a & b),
        "ordinary_brackets_distinct_normal_status_ids_union": len(a | b),
        "raw_power_rows": sum(r["rows"] for r in review),
        "t1_qualified_households": 0, "t1_qualified_events": 0,
        "cross_house_t1_pairs": 0, "cross_house_t1_triples": 0,
        "site_checks": review,
    }
    (HERE / "doe_sample_audit.json").write_text(json.dumps(out, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k != "site_checks"}, indent=2))


if __name__ == "__main__":
    main()
