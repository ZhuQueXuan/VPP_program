"""Print native-point evidence for checking the blind images, without assigning labels."""
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd


PACK = Path(__file__).resolve().parents[1] / "blind_pack"
MARKS = json.loads((PACK / "control_marks.json").read_text(encoding="utf-8"))


def groups(x, valid, max_gap):
    spans = []
    first = None
    for j, ok in enumerate(valid):
        connected = j > 0 and 0 < x[j] - x[j-1] <= max_gap
        if first is not None and (not ok or not connected):
            spans.append((first, j - 1))
            first = None
        if ok and first is None:
            first = j
    if first is not None:
        spans.append((first, len(x) - 1))
    return spans


def review(case, meta):
    df = pd.read_csv(PACK / "points" / f"{case}.csv")
    x = df.relative_s.to_numpy()
    heat = case.startswith("HP")
    y = df["hp_p" if heat else "power_kW"].to_numpy()
    gap, count, span, low, on, delta = (450, 2, 240, 50, 300, 200) if heat else (12, 3, 6, .15, .5, .3)
    end = meta["end_s"]
    stop = end if end is not None else 1800

    def ranges(mask):
        return [(f"{x[a]:g}..{x[b]:g}", int(b-a+1))
                for a, b in groups(x, mask, gap) if b-a+1 >= count and x[b]-x[a] >= span]

    def stats(a, b, last=False):
        use = (x >= a) & ((x <= b) if last else (x < b))
        t, p = x[use], y[use]
        if not len(t):
            return "empty"
        gaps = np.diff(t)
        return dict(n=len(t), bounds=(float(t[0]), float(t[-1])),
                    min_med_max=[round(float(v), 3) for v in np.nanpercentile(p, [0, 50, 100])],
                    missing=int(np.isnan(p).sum()),
                    gaps=[(float(t[j]), float(t[j+1])) for j in np.where((gaps <= 0) | (gaps > gap))[0]])

    core = (x >= 0) & (x < stop)
    print(case, "end", end, "coverage", stats(0, stop), "other", meta.get("other_intervention_start_s"),
          "session_end", meta.get("session_end_s_if_in_window"))
    print("  thirds", [stats(stop*k/3, stop*(k+1)/3) for k in range(3)])
    print("  low", ranges(core & (y <= low)), "on", ranges(core & (y >= on)))
    if not heat:
        limits = df.limit_A.to_numpy()
        changes = np.where(np.abs(np.diff(limits)) > .25)[0]
        print("  controls", [(float(x[j+1]), float(limits[j]), float(limits[j+1])) for j in changes])
    if end is not None and end > 0:
        start = max(0, end-(1800 if heat else 30))
        later = end+(21600 if heat else 300)
        reference = y[(x >= start) & (x < end)]
        median = np.nanmedian(reference) if len(reference) else np.nan
        post = (x > end if heat else x >= end) & (x <= later)
        print("  pre", stats(start, end), "post", stats(end, later, True),
              "  above", ranges(post & (y >= median+delta)))


for case in sys.argv[1:]:
    review(case, MARKS[case])
