"""Recreate the T0 ledger and blind pack from the two local development sources."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
import numpy as np
import pandas as pd


HERE = Path(__file__).resolve().parent
WORK = HERE.parent
ACN = WORK / "b1_temporal_t0_20261104"
HEAT = WORK / "b1_response_factors_20261104/raw/heat.zip"
RULES = HERE / "blind_pack/RULES.md"
CHANNELS = ["hp_p", "t_in", "t_out", "t_dhw", "t_set", "intervention_dummy"]
HEAT_COLUMNS = ["time_full", "hh_id", "unique_index", "elapsed_time_inter",
                "total_duration_int", "reason_stop", *CHANNELS]


def sha(value):
    return hashlib.sha256(value).hexdigest()


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
                    encoding="utf-8")


def stage_stats(frame, left, right, hh_min, hh_max):
    seconds = frame.relative_s.to_numpy()
    gaps = np.diff(seconds)
    return {
        "expected_s": [left, right],
        "points": len(frame),
        "first_relative_s": int(seconds[0]) if len(seconds) else None,
        "last_relative_s": int(seconds[-1]) if len(seconds) else None,
        "empty": not len(seconds),
        "source_left_censored": hh_min > left,
        "source_right_censored": hh_max < right,
        "left_edge_undercovered": not len(seconds) or int(seconds[0]) - left > 450,
        "right_edge_undercovered": not len(seconds) or right - int(seconds[-1]) > 450,
        "duplicate_source_rows": frame.loc[frame.relative_s.duplicated(keep=False), "source_row"].tolist(),
        "long_gaps": [[int(seconds[i]), int(seconds[i+1])] for i in np.flatnonzero(gaps > 450)],
        "missing_by_channel": frame[CHANNELS].isna().sum().to_dict(),
    }


def heat_ledger():
    with zipfile.ZipFile(HEAT) as archive:
        member_sha = sha(archive.read("experiment_data.dta"))
        with archive.open("experiment_data.dta") as stream:
            frame = pd.read_stata(stream, columns=HEAT_COLUMNS, convert_categoricals=False)
    frame["source_row"] = np.arange(1, len(frame) + 1)
    frame["utc"] = pd.to_datetime(frame.time_full, format="mixed", utc=True)
    assert frame.utc.notna().all()
    starts = frame[(frame.intervention_dummy == 1) & (frame.elapsed_time_inter == 0)]
    stops = frame[frame.reason_stop.notna() & (frame.reason_stop != 0)]
    keys = ["hh_id", "unique_index"]
    events = starts.merge(stops, on=keys, validate="one_to_one", suffixes=("_start", "_stop"))
    assert len(events) == len(starts) == len(stops) == 287
    groups = {int(hh): group.sort_values(["utc", "source_row"]).set_index("utc", drop=False)
              for hh, group in frame.groupby("hh_id")}
    entries, windows = [], {}
    for event in events.itertuples(index=False):
        hh, event_id = int(event.hh_id), int(event.unique_index)
        start, stop = event.utc_start, event.utc_stop
        duration = int((stop - start).total_seconds())
        raw_duration = int(event.total_duration_int_stop)
        assert duration >= 0 and raw_duration >= 0 and (duration == 0) == (raw_duration == 0)
        group = groups[hh]
        left = start - pd.Timedelta(hours=1)
        right = stop + pd.Timedelta(hours=6)
        local = group.loc[left:right].copy()
        local["relative_s"] = (local.utc - start).dt.total_seconds().astype(int)
        local["relative_stop_s"] = local.relative_s - duration
        hh_min = int((group.utc.iloc[0] - start).total_seconds())
        hh_max = int((group.utc.iloc[-1] - start).total_seconds())
        t = local.relative_s
        phases = {
            "before": stage_stats(local[t < 0], -3600, 0, hh_min, hh_max),
            "during": stage_stats(local[t.between(0, duration)], 0, duration, hh_min, hh_max),
            "after": stage_stats(local[t > duration], duration, duration + 21600, hh_min, hh_max),
            "entire": stage_stats(local, -3600, duration + 21600, hh_min, hh_max),
        }
        other_events = events[(events.hh_id == hh) & (events.unique_index != event_id)
                              & (events.utc_start <= right) & (events.utc_stop >= left)]
        other = [{"event": int(e.unique_index), "start_relative_s": int((e.utc_start - start).total_seconds()),
                  "stop_relative_s": int((e.utc_stop - start).total_seconds()),
                  "start_source_row": e.source_row_start, "stop_source_row": e.source_row_stop}
                 for e in other_events.itertuples(index=False)]
        post_events = [e for e in other if e["start_relative_s"] > duration or e["stop_relative_s"] > duration]
        entire = phases["entire"]
        timing_issue = bool(entire["left_edge_undercovered"] or entire["right_edge_undercovered"]
                            or entire["source_left_censored"] or entire["source_right_censored"]
                            or entire["duplicate_source_rows"] or entire["long_gaps"])
        key = sha(f"t0-blind-heat-v1|{hh}|{event_id}".encode())
        entries.append({
            "household": hh, "event": event_id, "selection_sha256": key,
            "start_source_row": event.source_row_start, "stop_source_row": event.source_row_stop,
            "start_utc": start.isoformat(), "stop_utc": stop.isoformat(),
            "duration_s": duration, "duration_s_source": raw_duration,
            "duration_source_minus_utc_s": raw_duration - duration,
            "zero_duration": duration == 0, "stop_reason_raw": event.reason_stop_stop,
            "other_events": other, "other_post_events": post_events, "timing_issue": timing_issue,
            "phases": phases,
        })
        windows[(hh, event_id)] = local
    entries.sort(key=lambda row: (row["household"], row["start_utc"], row["event"]))
    assert len(groups) == 9 and sum(row["zero_duration"] for row in entries) == 34
    return entries, windows, len(frame), member_sha


def select_heat(entries):
    selected, counts = [], Counter()
    ordered = sorted(entries, key=lambda row: row["selection_sha256"])

    def take(row, tier):
        selected.append({**row, "tier": tier})
        counts[row["household"]] += 1

    for hh in sorted({row["household"] for row in entries}):
        chosen = next((r for r in ordered if r["household"] == hh and not r["zero_duration"]), None)
        if chosen:
            take(chosen, "household_first")
    tiers = ("zero_duration", "positive_timing_issue", "positive_other")
    for tier in tiers:
        for row in ordered:
            if counts[row["household"]] >= 2 or any(
                r["selection_sha256"] == row["selection_sha256"] for r in selected
            ):
                continue
            matches = (row["zero_duration"] if tier == "zero_duration" else not row["zero_duration"]
                       and (tier == "positive_other" or row["timing_issue"]))
            if matches:
                take(row, tier)
                break
    return sorted(selected, key=lambda row: row["selection_sha256"])


def native_line(ax, times, values, gap, color, label, time_scale):
    """Draw only original points and valid adjacent pairs."""
    times = np.asarray(times)
    values = np.asarray(values)
    dt = np.diff(times)
    good = np.isfinite(values)
    pairs = good[:-1] & good[1:] & (dt > 0) & (dt <= gap)
    xy = np.column_stack((times / time_scale, values))
    segments = np.stack([xy[:-1][pairs], xy[1:][pairs]], axis=1)
    ax.add_collection(LineCollection(segments, colors=color, linewidths=0.85))
    ax.plot(xy[good, 0], xy[good, 1], ".", ms=2.2, color=color, label=label)
    missing = times[~good] / time_scale
    if len(missing):
        ax.plot(missing, np.full(len(missing), .04), "|", transform=ax.get_xaxis_transform(),
                color=color, alpha=.65)


def plot_case(path, case, frame, end, stop, heat, other, observed_end=None):
    scale, gap = (3600, 450) if heat else (1, 12)
    left = -3600 if heat else -60
    windows = [("Full window", left, stop)]
    if heat:
        windows.extend([("Start detail", -3600, min(stop, 7200)),
                        ("Stop detail", max(left, end - 7200), end + 21600)])
    elif end is not None:
        windows.append(("Return detail", max(left, end - 40), end + 300))
    columns = len(windows)
    fig, axes = plt.subplots(2, columns, figsize=(5.6 * columns, 4.15), squeeze=False,
                             layout="constrained", sharex="col", height_ratios=[2.2, 1])
    traces = (("hp_p", "Power (W)", "#17679a"), ("intervention_dummy", "Control flag", "#a64b08")) if heat else (
        ("power_kW", "Power (kW)", "#17679a"), ("current_A", "Current (A)", "#42762b"),
        ("limit_A", "Received limit (A)", "#a64b08"))
    for col, (title, a, b) in enumerate(windows):
        region = frame[frame.relative_s.between(a, b)]
        for index, (key, label, color) in enumerate(traces):
            axis = axes[0 if index == 0 else 1, col]
            native_line(axis, region.relative_s, region[key], gap, color, label, scale)
        for ax in axes[:, col]:
            ax.axvline(0, color="#6b7280", lw=.85, linestyle="--")
            if end is not None:
                ax.axvline(end / scale, color="#803879", lw=1.0, linestyle="--")
            if observed_end is not None and a < observed_end < b:
                ax.axvline(observed_end / scale, color="#4b5563", lw=.9, linestyle=":")
            for mark in other:
                ax.axvline(mark / scale, color="#d27118", lw=.9, linestyle=":")
            ax.set_xlim(a / scale, b / scale)
            ax.grid(alpha=.18)
            ax.legend(loc="upper right", fontsize=8)
        axes[0, col].set_title(title, fontsize=10)
        axes[1, col].set_xlabel("Hours from start" if heat else "Seconds from start")
    axes[0, 0].set_ylabel("W" if heat else "kW")
    axes[1, 0].set_ylabel("0 / 1" if heat else "A")
    fig.suptitle(case + "  |  Native points", fontsize=13)
    fig.savefig(path, dpi=125)
    plt.close(fig)


def build(output):
    pack = output / "blind_pack"
    private = output / "provenance"
    assert not (private / "pack_freeze.json").exists(), "Use a fresh --output for reproduction"
    for folder in (pack / "points", pack / "plots", private):
        folder.mkdir(parents=True, exist_ok=True)
    if output != HERE:
        shutil.copyfile(RULES, pack / "RULES.md")
    acn_registry = load_json(ACN / "acn_review_registry.json")
    acn_ledger = {row["session"]: row for row in load_json(ACN / "acn_control_ledger.json")}
    entries, windows, heat_rows, member_sha = heat_ledger()
    save_json(private / "heat_event_ledger.json", entries)
    sources, public = {}, {}
    for n, row in enumerate(sorted(acn_registry, key=lambda r: sha(f"t0-blind-acn-v1|{r['case']}".encode())), 1):
        case = f"EV{n:02d}"
        source = ACN / "blind_source_points" / f"{row['case']}.csv"
        path = pack / "points" / f"{case}.csv"
        shutil.copyfile(source, path)
        frame = pd.read_csv(path)
        event = acn_ledger[row["session"]]
        release = event["release"]
        end = release["relative_s"] if release else None
        right = max(1800, end + 300) if end is not None else 1800
        observed_end = event["disconnect_seconds"] - event["start_seconds"]
        if end is not None:
            edge_index = np.flatnonzero(frame.source_row == release["raw_row"])[0]
            assert frame.relative_s.iloc[edge_index] == end
            assert 0 < end - frame.relative_s.iloc[edge_index - 1] <= 12
            assert frame.limit_A.iloc[edge_index] - frame.limit_A.iloc[edge_index - 1] >= 2
            assert abs(frame.limit_A.iloc[edge_index] - event["old_limit_A"]) <= .25
        public[case] = {"unit": "seconds", "end_s": end, "window_s": [-60, right],
                        "session_end_s_if_in_window": observed_end if observed_end < right else None}
        sources[case] = {**row, "original_pack_sha256": sha(source.read_bytes()),
                         "source": event["source"], "points": len(frame)}
        plot_case(pack / "plots" / f"{case}.png", case, frame, end, right, False, [], observed_end)
    for n, row in enumerate(select_heat(entries), 1):
        case = f"HP{n:02d}"
        frame = windows[(row["household"], row["event"])]
        end = row["duration_s"]
        right = end + 21600
        other = [event["start_relative_s"] for event in row["other_events"]]
        public[case] = {"unit": "seconds", "end_s": end, "window_s": [-3600, right],
                        "other_intervention_start_s": other,
                        "stop_source_row": row["stop_source_row"]}
        sources[case] = {**row, "points": len(frame)}
        frame[["source_row", "time_full", "utc", "relative_s", "relative_stop_s", *CHANNELS]].to_csv(
            pack / "points" / f"{case}.csv", index=False)
        plot_case(pack / "plots" / f"{case}.png", case, frame, end, right, True, other)
    save_json(pack / "control_marks.json", public)
    save_json(private / "source_mapping_and_heat_selection.json", sources)
    links = []
    for case, meta in public.items():
        end = meta["end_s"]
        end_text = "none recorded" if end is None else f"{end:g} s"
        links.append(f'<section><h2>{case}</h2><p>Return / stop mark: {end_text} '
                     f'&middot; <a href="points/{case}.csv">Native CSV</a> '
                     f'&middot; <a href="plots/{case}.png">Open full image</a></p>'
                     f'<img loading="lazy" src="plots/{case}.png" alt="{case} native points"></section>')
    (pack / "index.html").write_text(
        '<!doctype html><html lang="zh"><meta charset="utf-8"><title>T0 blind review</title>'
        '<style>body{max-width:1400px;margin:2em auto;font:16px system-ui}img{width:100%}'
        'section{padding:1em 0;border-top:1px solid #ddd}</style><h1>T0 原曲线盲审</h1>'
        '<p><a href="RULES.md">判读规则</a> · <a href="control_marks.json">控制时间记录</a></p>'
        '<p>灰色虚线是起点，紫色虚线是回限或停止标记。橙色点线是热泵其他干预起点，'
        '深灰点线是 ACN 窗内交易结束。底部同色短竖线是缺失读数。相对秒和源行见 CSV。</p>'
        + "\n".join(links) + "</html>\n", encoding="utf-8")
    save_json(private / "pack_freeze.json", {
        "source_heat_zip_sha256": sha(HEAT.read_bytes()), "source_heat_dta_sha256": member_sha,
        "source_heat_rows": heat_rows, "heat_events": len(entries),
        "heat_households": len({row["household"] for row in entries}),
        "source_acn_ledger_sha256": sha((ACN / "acn_control_ledger.json").read_bytes()),
        "source_acn_registry_sha256": sha((ACN / "acn_review_registry.json").read_bytes()),
        "acn_native_points": sum(r["points"] for k, r in sources.items() if k.startswith("EV")),
        "heat_native_points": sum(r["points"] for k, r in sources.items() if k.startswith("HP")),
        "builder_sha256": sha(Path(__file__).read_bytes()),
        "blind_pack_sha256": {p.relative_to(pack).as_posix(): sha(p.read_bytes())
                              for p in sorted(pack.rglob("*")) if p.is_file()},
    })


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=HERE)
    build(parser.parse_args().output.resolve())
