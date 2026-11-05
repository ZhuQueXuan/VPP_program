"""Check the finished offline page against its point copies and compressed sources."""
import csv
from datetime import datetime
from decimal import Decimal
import gzip
from hashlib import sha256
from html.parser import HTMLParser
import json
from pathlib import Path
from urllib.parse import unquote

from build_demo import CASES, HERE, ROOT, STORIES, Point, trace


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.links = []
        self.charts = []
        self.channel = None

    def handle_starttag(self, tag, attrs):
        attr = dict(attrs)
        if "id" in attr:
            self.ids.append(attr["id"])
        for key in ("href", "src"):
            if key in attr:
                self.links.append(attr[key])
        if tag == "svg":
            self.charts.append({"label": attr["aria-labelledby"], "limit": [], "power": []})
        if tag == "g" and "data-channel" in attr:
            self.channel = attr["data-channel"]
        if tag == "circle" and self.channel and "data-src" in attr:
            self.charts[-1][self.channel].append(int(attr["data-src"]))

    def handle_endtag(self, tag):
        if tag == "g":
            self.channel = None


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def rows(path, compressed=False):
    opener = gzip.open if compressed else Path.open
    with opener(path, "rt", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def main():
    manifest = json.loads((HERE / "source_map.json").read_text("utf-8"))
    source_audit = json.loads((HERE / "source_verification.json").read_text("utf-8"))
    html_path = HERE / "index.html"
    html = html_path.read_text("utf-8")
    page = Page()
    page.feed(html)
    assert tuple(manifest) == CASES and len(page.charts) == 6
    assert digest(html_path) == source_audit["page_sha256"]
    assert len(page.ids) == len(set(page.ids))
    for link in page.links:
        if link.startswith("#"):
            assert link[1:] in page.ids
        else:
            assert ":" not in link and (HERE / unquote(link)).is_file()
    assert "acn_user_" not in html
    max_difference = Decimal(0)
    for case in CASES:
        meta = manifest[case]
        stored = HERE / f"points/{case}.csv"
        original = ROOT / meta["compressed_source"]
        assert digest(stored) == digest(ROOT / meta["frozen_anonymous_points"]) == meta["frozen_points_sha256"]
        assert digest(original) == meta["compressed_source_sha256"]
        source = rows(original, compressed=True)
        packed = rows(stored)
        for index, raw in enumerate(packed):
            line = int(raw["source_row"])
            assert line == meta["source_row_span"][0]+index
            orig = source[line-2]
            assert raw["time_utc"] == orig[""]
            for a,b in (("limit_A","Actual Pilot (A)"), ("current_A","Charging Current (A)"), ("power_kW","Power (kW)")):
                delta = abs(Decimal(raw[a])-Decimal(orig[b]))
                max_difference = max(max_difference, delta)
            relative = (datetime.fromisoformat(orig[""])-datetime.fromisoformat(meta["anchor_utc"])).total_seconds()
            assert float(raw["relative_s"]) == relative
        for label, (a,b) in (("detail", STORIES[case]["zoom"]), ("full", (-60,1800))):
            graph = next(c for c in page.charts if c["label"] == f"{case.lower()}-{label}-title")
            expected = [int(r["source_row"]) for r in packed if a <= float(r["relative_s"]) <= b]
            assert graph["power"] == graph["limit"] == expected
        for line in source_audit["cases"][case]["key_rows"]:
            assert f"{case.lower()}-r{line}" in page.ids
    assert max_difference <= Decimal("1e-12")
    # Test the drawing rule at 12 s, over 12 s, and through a missing reading.
    example = [Point(i, "", t, v, "", v) for i,t,v in
               [(1,0,"1"), (2,12,"2"), (3,25,"3"), (4,26,""), (5,28,"0")]]
    identity = lambda x: x
    power = trace(example, "power", identity, identity, set(), True, "rule")
    limit = trace(example, "limit", identity, identity, set(), True, "rule")
    assert 'd="M0.00,1.00 L12.00,2.00 M25.00,3.00 M28.00,0.00"' in power
    assert 'd="M0.00,1.00 H12.00 V2.00 M25.00,3.00 M28.00,0.00"' in limit
    assert 'data-src="4"' not in power and 'data-src="4"' not in limit
    proof = {
        "page_sha256": digest(html_path), "six_svg_views_verified": len(page.charts),
        "offline_local_or_internal_links_verified": len(page.links), "plot_point_count": source_audit["point_total"],
        "key_rows_verified": source_audit["key_row_total"], "raw_numeric_max_abs_difference": str(max_difference),
        "max_real_gap_s": max(c["max_gap_s"] for c in source_audit["cases"].values()),
        "drawing_rule_boundary_check": "12 seconds joined, >12 seconds and missing split, raw zero preserved",
        "exact_development_case_ids": list(CASES),
    }
    (HERE / "page_verification.json").write_text(json.dumps(proof,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(proof, indent=2))


if __name__ == "__main__":
    main()
