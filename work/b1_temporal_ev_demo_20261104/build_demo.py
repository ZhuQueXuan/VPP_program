"""Build the offline ACN demo from exactly three frozen development point packs."""
import csv
import gzip
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from hashlib import sha256
from html import escape
import json
from pathlib import Path
from statistics import median
from urllib.parse import quote


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
T0 = HERE.parent / "b1_temporal_t0_blind_20261104"
ACN = HERE.parent / "b1_temporal_t0_20261104"
CASES = ("EV16", "EV23", "EV02")
WINDOW = (-60, 1800)
COLS = ("source_row", "time_utc", "relative_s", "limit_A", "current_A", "power_kW")


@dataclass(frozen=True)
class Point:
    row: int
    utc: str
    t: float
    limit: str
    current: str
    power: str


@dataclass(frozen=True)
class Mark:
    t: int
    channel: str
    text: str
    label_x: int
    label_y: int
    reason: str


STORIES = {
    "EV16": {
        "tag": "01 / 可见回升",
        "title": "限额先恢复，功率随后分步上升",
        "lead": "40 秒的限额已回到 32 A，功率仍约 1.77 kW。43 秒升到 3.80 kW，59 秒已到 6.94 kW。",
        "detail": "锚点 0 秒已收到 8 A 限额，当点功率仍为 6.927 kW，4 秒观测降到 1.950 kW。40 秒以后可见多个上升台阶，具体变化时刻受相邻采样点约束。",
        "zoom": (-12, 78), "ticks": [-10, 0, 10, 20, 30, 40, 50, 60, 70],
        "marks": (
            Mark(0, "limit", "0 s · 32 → 8 A", 255, 28, "首次看到限额降为 8 A"),
            Mark(40, "limit", "40 s · 8 → 32 A", 650, 28, "首次看到限额恢复至 32 A"),
            Mark(40, "power", "40 s · 1.77 kW", 474, 164, "回限同点的实测功率"),
            Mark(43, "power", "43 s · 3.80 kW", 620, 190, "回限后下一原点"),
            Mark(59, "power", "59 s · 6.94 kW", 758, 164, "上升至约 6.94 kW 的原点"),
        ),
        "extras": {-4: "上一个较高限额点", 4: "首次降限后的低功率点", 35: "回限前最后一个 8 A 原点"},
        "band": None, "skip_power": set(),
    },
    "EV23": {
        "tag": "02 / 原因未知",
        "title": "限额仍为 8 A，实测功率从约 1.6 kW 变为零",
        "lead": "降限后近一分钟约为 1.6 kW。59 秒仍有 1.581 kW，63 秒观测为零，此时限额仍为 8 A。",
        "detail": "59–63 秒之间的具体下降时刻和原因未知。63 秒之后，窗口内其余原点的功率均为零，记录到的限额仍为 8 A。",
        "zoom": (-12, 100), "ticks": [-10, 0, 20, 40, 60, 80, 100],
        "marks": (
            Mark(0, "limit", "0 s · 31 → 8 A", 242, 28, "首次看到限额降为 8 A"),
            Mark(63, "limit", "63 s · 仍是 8 A", 735, 28, "观测为零时，限额仍是 8 A"),
            Mark(59, "power", "59 s · 1.581 kW", 535, 164, "最后一个非零功率点"),
            Mark(63, "power", "63 s · 0 kW", 701, 190, "第一个观测为零的功率点"),
        ),
        "extras": {-4: "上一个较高限额点", 5: "降限后的近 1.6 kW 平台原点", 1797: "全窗末个原点"},
        "band": (59, 63, "59–63 s · 具体下降时刻与原因未知", 697, 406),
        "skip_power": {(59, 63)},
    },
    "EV02": {
        "tag": "03 / 完整过程不可判",
        "title": "4 秒就回限，受限阶段只有一个点",
        "lead": "0 秒限额由 32 A 降到 8 A，4 秒回到 32 A。此后功率上升可见，受限段仅有 0 秒的一个功率点。",
        "detail": "4、8、12 秒分别观测到 3.218、5.463、6.866 kW。受限段内缺少足够原点来建立末段参考，按冻结规则记完整回升过程不可判。",
        "zoom": (-12, 36), "ticks": [-12, -8, -4, 0, 4, 8, 12, 20, 28, 36],
        "marks": (
            Mark(0, "limit", "0 s · 32 → 8 A", 220, 28, "降限并记录到受限段唯一功率点"),
            Mark(4, "limit", "4 s · 8 → 32 A", 490, 28, "首次看到回限，受限段结束"),
            Mark(0, "power", "0 s · 1.675 kW", 237, 164, "受限段唯一功率点"),
            Mark(4, "power", "4 s · 3.218 kW", 436, 190, "回限同点已见功率上升"),
            Mark(12, "power", "12 s · 6.866 kW", 638, 164, "回限后的上升原点"),
        ),
        "extras": {-2: "紧邻降限前的 32 A 原点", 8: "回限后的下一上升点"},
        "band": (0, 4, "[0, 4) s · 完整过程不可判", 385, 406),
        "skip_power": {(0, 4)},
    },
}


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")


def safe_number(value):
    d = Decimal(value) if value else None
    return d if d is not None and d.is_finite() else None


def read_points(source):
    with source.open(encoding="utf-8", newline="") as stream:
        records = csv.DictReader(stream)
        assert tuple(records.fieldnames) == COLS
        return [Point(int(r["source_row"]), r["time_utc"], float(r["relative_s"]), r["limit_A"],
                      r["current_A"], r["power_kW"]) for r in records]


def audit_native(points, source, role):
    assert role in {"training", "validation"}
    anchor = next(p for p in points if p.t == 0)
    zero = datetime.fromisoformat(anchor.utc)
    originals = {}
    with gzip.open(source, "rt", encoding="utf-8-sig", newline="") as stream:
        for row, raw in enumerate(csv.DictReader(stream), 2):
            time = datetime.fromisoformat(raw[""])
            elapsed = (time-zero).total_seconds()
            if WINDOW[0] <= elapsed <= WINDOW[1]:
                originals[row] = (time, elapsed, [safe_number(raw[c]) for c in
                                  ("Actual Pilot (A)", "Charging Current (A)", "Power (kW)")])
    assert list(originals) == [p.row for p in points]
    max_delta = Decimal(0)
    for p in points:
        time, elapsed, raw = originals[p.row]
        assert datetime.fromisoformat(p.utc) == time and p.t == elapsed
        for a, b in zip((safe_number(p.limit), safe_number(p.current), safe_number(p.power)), raw):
            assert (a is None) == (b is None)
            if a is not None:
                max_delta = max(max_delta, abs(a-b))
    assert max_delta <= Decimal("0.000000000001")
    return {"anchor_utc": anchor.utc, "source_row_start": points[0].row,
            "source_row_end": points[-1].row, "window_points_verified": len(points),
            "max_abs_numeric_difference": str(max_delta)}


def shown(value):
    d = safe_number(value)
    if d is None:
        return "缺测"
    return f"{d:.12f}".rstrip("0").rstrip(".") if d else "0"


def point_id(case, point):
    return f"{case.lower()}-r{point.row}"


def coords(point, channel, x, y):
    value = safe_number(getattr(point, channel))
    return (x(point.t), y(float(value))) if value is not None else None


def trace(points, channel, x, y, breaks, detailed, case):
    path, dots, previous = [], [], None
    for p in points:
        loc = coords(p, channel, x, y)
        if loc is None:
            previous = None
            continue
        px, py = loc
        linked = previous is not None and 0 < p.t-previous.t <= 12 and (previous.t,p.t) not in breaks
        if linked:
            if channel == "limit":
                path.append(f"H{px:.2f} V{py:.2f}")
            else:
                path.append(f"L{px:.2f},{py:.2f}")
        else:
            path.append(f"M{px:.2f},{py:.2f}")
        radius = "3.1" if detailed else "1.25"
        tip = escape(f"{p.t:g} s · 原行 {p.row} · {p.utc} · {shown(p.limit)} A · {shown(p.power)} kW")
        dots.append(f'<circle data-src="{p.row}" cx="{px:.2f}" cy="{py:.2f}" r="{radius}"><title>{tip}</title></circle>')
        previous = p
    return (f'<path class="{channel} line" d="{" ".join(path)}"/>'
            f'<g class="{channel} dots" data-case="{case}" data-channel="{channel}">{"".join(dots)}</g>')


def chart(case, points, story, detailed):
    lo, hi = story["zoom"] if detailed else WINDOW
    ticks = story["ticks"] if detailed else [-60, 0, 300, 600, 900, 1200, 1500, 1800]
    width, left, right = 900, 82, 876
    limit_box, power_box = ((53, 133), (221, 344)) if detailed else ((25, 89), (116, 205))
    height = 426 if detailed and story["band"] else (394 if detailed else 247)
    observed = [p for p in points if lo <= p.t <= hi]
    point_lookup = {p.t: p for p in observed}
    x = lambda t: left + (right-left)*(t-lo)/(hi-lo)
    yl = lambda v: limit_box[1] - (limit_box[1]-limit_box[0])*(v+.75)/35.5
    yp = lambda v: power_box[1] - (power_box[1]-power_box[0])*(v+.26)/7.65
    token = case.lower() + ("-detail" if detailed else "-full")
    label = f"{case} {'局部细节' if detailed else '全观察窗'}，限额和实测功率使用共同时间轴"
    parts = [
        f'<svg class="scope" viewBox="0 0 {width} {height}" role="img" aria-labelledby="{token}-title">',
        f'<title id="{token}-title">{label}</title>',
        f'<defs><pattern id="{token}-pattern" width="7" height="7" patternUnits="userSpaceOnUse" '
        'patternTransform="rotate(35)"><rect width="7" height="7" fill="#f3ecf7"/>'
        '<line x1="0" y1="0" x2="0" y2="7" stroke="#dac8e5" stroke-width="2"/></pattern></defs>',
    ]
    for label, box, scale, values in (
        ("限额 · A", limit_box, yl, [0, 8, 16, 24, 32]),
        ("功率 · kW", power_box, yp, [0, 2, 4, 6]),
    ):
        top, bottom = box
        parts.append(f'<rect class="track" x="{left}" y="{top}" width="{right-left}" height="{bottom-top}" rx="6"/>')
        for a, b in [(lo, min(hi, points[0].t)), (max(lo, points[-1].t), hi)]:
            if b > a:
                parts.append(f'<rect class="unobserved" x="{x(a):.2f}" y="{top}" width="{x(b)-x(a):.2f}" height="{bottom-top}"/>')
        if detailed and story["band"]:
            a, b, *_ = story["band"]
            parts.append(f'<rect data-uncertain="{a},{b}" fill="url(#{token}-pattern)" x="{x(a):.2f}" y="{top}" '
                         f'width="{x(b)-x(a):.2f}" height="{bottom-top}"/>')
        for v in values:
            y = scale(v)
            parts.append(f'<line class="grid" x1="{left}" x2="{right}" y1="{y:.2f}" y2="{y:.2f}"/>'
                         f'<text class="tick" text-anchor="end" x="{left-9}" y="{y+4:.2f}">{v}</text>')
        for t in ticks:
            parts.append(f'<line class="grid" x1="{x(t):.2f}" x2="{x(t):.2f}" y1="{top}" y2="{bottom}"/>')
        parts.append(f'<line class="anchor" x1="{x(0):.2f}" x2="{x(0):.2f}" y1="{top}" y2="{bottom}"/>'
                     f'<text class="axis-label" x="5" y="{top-6}">{label}</text>')
    for t in ticks:
        align = "start" if t == lo else "end" if t == hi else "middle"
        parts.append(f'<text class="tick" text-anchor="{align}" x="{x(t):.2f}" y="{power_box[1]+20}">{t}</text>')
    parts.append(f'<text class="axis-label" text-anchor="end" x="{right}" y="{power_box[1]+40}">距降限锚点 · 秒</text>')
    parts.append(trace(observed, "limit", x, yl, set(), detailed, case))
    parts.append(trace(observed, "power", x, yp, story["skip_power"], detailed, case))

    # The open amber rings identify every bracketed change on the full trace.
    if not detailed:
        for a, b in zip(observed, observed[1:]):
            aa, bb = safe_number(a.limit), safe_number(b.limit)
            if aa is not None and bb is not None and aa != bb and 0 < b.t-a.t <= 12:
                parts.append(f'<circle class="changed" cx="{x(b.t):.2f}" cy="{yl(float(bb)):.2f}" r="3">'
                             f'<title>{b.t:g} s · {aa:g} → {bb:g} A · 原行 {b.row}</title></circle>')
    if detailed:
        for mark in story["marks"]:
            p = point_lookup[mark.t]
            channel = mark.channel
            px, py = coords(p, channel, x, yl if channel == "limit" else yp)
            lx, ly = mark.label_x, mark.label_y
            parts.append(
                f'<a class="call {channel}" href="#{point_id(case,p)}">'
                f'<line x1="{px:.2f}" x2="{lx}" y1="{py:.2f}" y2="{ly+5}"/>'
                f'<circle cx="{px:.2f}" cy="{py:.2f}" r="5.2"/>'
                f'<text text-anchor="middle" x="{lx}" y="{ly}">{escape(mark.text)}</text></a>')
        if story["band"]:
            a, b, phrase, lx, ly = story["band"]
            parts.append(f'<line class="uncertain-guide" x1="{x((a+b)/2):.2f}" x2="{lx}" '
                         f'y1="{power_box[1]}" y2="{ly-14}"/><text class="uncertain-note" text-anchor="middle" '
                         f'x="{lx}" y="{ly}">{escape(phrase)}</text>')
    return "".join(parts) + "</svg>"


def row_html(case, p, reason=None):
    rowid = f' id="{point_id(case,p)}"' if reason is not None else ""
    reason_cell = f"<td>{escape(reason)}</td>" if reason is not None else f"<td>{escape(shown(p.current))}</td>"
    return (f'<tr{rowid}><td>{p.t:g}</td><td>{shown(p.limit)}</td><td>{shown(p.power)}</td>'
            f'<td>{p.row}</td><td><time>{escape(p.utc)}</time></td>{reason_cell}</tr>')


def table(case, points, reasons=None):
    end = "判读依据" if reasons is not None else "实测电流 A"
    return ('<div class="table-scroll"><table><thead><tr><th scope="col">相对秒</th>'
            '<th scope="col">限额 A</th><th scope="col">功率 kW</th><th scope="col">压缩源行号</th>'
            f'<th scope="col">UTC</th><th scope="col">{end}</th></tr></thead><tbody>'
            + "".join(row_html(case, p, reasons[p.t] if reasons is not None else None) for p in points)
            + "</tbody></table></div>")


def section(case, points, source_path, source_sha):
    story = STORIES[case]
    reasons = dict(story["extras"])
    for mark in story["marks"]:
        if mark.t in reasons and mark.reason not in reasons[mark.t]:
            reasons[mark.t] += "。"+mark.reason
        else:
            reasons[mark.t] = mark.reason
    key_points = [p for p in points if p.t in reasons]
    assert len(key_points) == len(reasons)
    measured = ""
    if case == "EV23":
        slices = [median(safe_number(p.power) for p in points if a <= p.t < b)
                  for a, b in [(0,600), (600,1200), (1200,1800)]]
        assert slices == [0, 0, 0]
        measured = ('<p class="note"><b>为什么要看过程。</b> 把 0–1800 秒等分成三段，原点功率中位数均为 '
                    '0 kW。前段不到一分钟的约 1.6 kW 平台在这三个数里看不出来。</p>')
    link = quote("../../"+source_path, safe="/")
    return (
        f'<section class="case" id="{case.lower()}"><header><p class="eyebrow">{case} <span>{story["tag"]}</span></p>'
        f'<h2>{story["title"]}</h2><p class="case-lead">{story["lead"]}</p></header>'
        '<div class="chart-card"><div class="chart-heading"><h3>关键时段</h3>'
        '<span>点击标注可跳到对应原点</span></div>'
        f'<div class="chart-scroll">{chart(case, points, story, True)}</div></div>'
        f'<p class="observation">{story["detail"]}</p>{measured}'
        '<div class="chart-card full"><div class="chart-heading"><h3>全观察窗</h3>'
        f'<span>−60 至 1800 秒 · {len(points)} 个原点</span></div>'
        f'<div class="chart-scroll">{chart(case, points, story, False)}</div></div>'
        f'<p class="range">首末原点 {points[0].t:g} 至 {points[-1].t:g} 秒，曲线只绘到原记录范围。</p>'
        f'<h3 class="evidence-heading">关键原点</h3>{table(case,key_points,reasons)}'
        f'<details class="all-points" id="{case.lower()}-points"><summary>打开全部原点表 <span>{len(points)} 行</span></summary>'
        f'<p><a href="points/{case}.csv">打开冻结原点 CSV</a></p>{table(case,points)}</details>'
        '<details class="source"><summary>回查本地压缩源</summary>'
        f'<p><a href="{link}">打开对应冻结压缩源</a></p><code>{escape(source_path)}</code>'
        f'<p>压缩源 SHA256</p><code>{source_sha}</code>'
        '<p>原行号从压缩内 CSV 的表头第 1 行起算。路径在本项目内可用。</p></details></section>'
    ), key_points


def main():
    mapping = read_json(T0 / "provenance/source_mapping_and_heat_selection.json")
    t0 = read_json(T0 / "provenance/pack_freeze.json")
    controls = read_json(T0 / "blind_pack/control_marks.json")
    previous = {r["session"]: r for r in read_json(ACN / "acn_control_ledger.json")}
    exports = HERE / "points"
    exports.mkdir(exist_ok=True)
    source_map, checks, content = {}, {}, []
    for case in CASES:
        meta = mapping[case]
        frozen = T0 / f"blind_pack/points/{case}.csv"
        assert digest(frozen) == t0["blind_pack_sha256"][f"points/{case}.csv"]
        assert controls[case]["window_s"] == list(WINDOW) and controls[case]["session_end_s_if_in_window"] is None
        source = ROOT / meta["source"]
        assert source.resolve().is_relative_to((ROOT / "data/ACN_real_user_benchmark_v1_20261102/raw/caltech").resolve())
        assert meta["source"] == previous[meta["session"]]["source"]
        rows = read_points(frozen)
        proof = audit_native(rows, source, meta["role"])
        assert proof["anchor_utc"] == previous[meta["session"]]["anchor_utc"]
        gaps = [b.t-a.t for a,b in zip(rows,rows[1:])]
        gz_hash = digest(source)
        html, key_points = section(case, rows, meta["source"], gz_hash)
        content.append(html)
        (exports / f"{case}.csv").write_bytes(frozen.read_bytes())
        source_map[case] = {
            "frozen_anonymous_points": frozen.relative_to(ROOT).as_posix(),
            "frozen_points_sha256": digest(frozen), "compressed_source": meta["source"],
            "compressed_source_sha256": gz_hash, "anchor_utc": proof["anchor_utc"],
            "source_row_span": [proof["source_row_start"], proof["source_row_end"]],
        }
        checks[case] = {**proof, "source_development_role": meta["role"],
                        "point_csv_is_frozen_copy": digest(exports / f"{case}.csv") == digest(frozen),
                        "max_gap_s": max(gaps), "gaps_over_12_s": sum(g>12 for g in gaps),
                        "key_rows": [p.row for p in key_points]}
    stylesheet = (HERE / "style.css").read_text(encoding="utf-8")
    template = (HERE / "template.html").read_text(encoding="utf-8")
    html = template.replace("<!-- INLINE STYLE -->", stylesheet).replace("<!-- CASES -->", "\n".join(content))
    (HERE / "index.html").write_text(html, encoding="utf-8")
    save_json(HERE / "source_map.json", source_map)
    save_json(HERE / "source_verification.json", {
        "cases": checks, "point_total": sum(r["window_points_verified"] for r in checks.values()),
        "key_row_total": sum(len(r["key_rows"]) for r in checks.values()),
        "page_sha256": digest(HERE / "index.html"), "source_map_sha256": digest(HERE / "source_map.json"),
        "t0_freeze_sha256": digest(T0 / "provenance/pack_freeze.json"),
        "native_values_tolerance": "1e-12",
        "read_old_confirmation": False, "fitted_models": 0,
    })


if __name__ == "__main__":
    main()
