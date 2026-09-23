"""Offline tests for the pen-drawing tracer. No network.

Run: ./.venv.nosync/bin/python tests/test_web_drawing.py
Takes about 15 seconds: it traces the real Logan art twice.
"""

import gzip
import io
import json
import math
import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import web_drawing as wd  # noqa: E402
from layout import TEMPLES_DIR  # noqa: E402


def mask_from(draw_fn, size=(200, 200)):
    im = Image.new("L", size, 0)
    draw_fn(ImageDraw.Draw(im))
    return np.array(im) > 0


# thin: a 6 px thick bar becomes a 1 px line
bar = mask_from(lambda d: d.rectangle([20, 97, 180, 102], fill=255))
sk = wd.thin(bar)
assert sk.sum() > 140, f"skeleton lost the bar: {sk.sum()} px"
assert sk.sum(axis=0).max() <= 2, "skeleton is more than one pixel thick"

# trace + chain: a quarter arc comes back as ONE continuous stroke, not scraps.
# This is the curve-gap bug from the mockup (scraps under 5 px were dropped).
arc = mask_from(lambda d: d.arc([20, 20, 180, 180], 180, 270, fill=255, width=6))
strokes = wd.trace(arc)
longest = max(wd.polyline_length(s) for s in strokes)
expected = math.pi * 77 / 2  # quarter circle at the arc's centre radius
assert longest > 0.9 * expected, f"arc split into scraps: longest {longest:.0f} of {expected:.0f}"

# rdp keeps the end points and a real corner, and drops collinear points
pts = [(0, 0), (0, 5), (0, 10), (5, 10), (10, 10)]
assert wd.rdp(pts, 0.6) == [(0, 0), (0, 10), (10, 10)], wd.rdp(pts, 0.6)
long_line = [(0, i) for i in range(5000)]  # must not hit the recursion limit
assert wd.rdp(long_line, 0.6) == [(0, 0), (0, 4999)]

# the real thing: Logan
logan = (TEMPLES_DIR / "Logan" / "Logan white.svg").read_text()
r = wd.build(logan, "LOGAN, UTAH")
d, st = r["data"], r["stats"]
assert wd.limit_problems(st) == [], wd.limit_problems(st)
assert st["uncovered_pct"] < wd.UNCOVERED_LIMIT_PCT, st
assert d["city"] == "LOGAN, UTAH"
assert d["version"] == 1
assert len(d["strokes"]) == len(d["lens"]) == st["strokes"] > 100, st
assert all(s.startswith("M") and " L" in s for s in d["strokes"]), "a stroke has fewer than two points"
x, y, w, h = d["box"]
img = Image.open(io.BytesIO(r["image"]))
assert img.format == "WEBP" and img.mode == "RGBA", (img.format, img.mode)
assert max(img.size) == 840, img.size
assert abs(img.size[0] / img.size[1] - w / h) < 0.01, "image does not match the box shape"
assert st["json_gz_bytes"] == len(gzip.compress(json.dumps(d, separators=(",", ":")).encode(), 9))

# same input, same output: rebuilding must not churn the theme on every push
r2 = wd.build(logan, "LOGAN, UTAH")
assert r2["data"] == d and r2["image"] == r["image"], "tracer output is not deterministic"

# The browser (theme/assets/pp-pen-draw.js) reads exactly these keys: penWidth sets the
# mask's stroke-width and the pen tip, lens drives each stroke's dash, box is the viewBox.
assert set(d) == {"version", "box", "penWidth", "city", "strokes", "lens"}, set(d)
assert 0 < d["penWidth"] < w, d["penWidth"]
for s, ln in zip(d["strokes"], d["lens"]):
    pts = [(float(a), float(b)) for a, b in re.findall(r"[ML](-?[\d.]+) (-?[\d.]+)", s)]
    assert abs(wd.polyline_length(pts) - ln) < 0.1, (s[:40], ln)
    assert all(x <= px <= x + w and y <= py <= y + h for px, py in pts), "stroke outside box"

# pen order: long structural strokes before short details, even when a detail is nearer
# the bottom-left start; a long horizontal line is drawn left to right.
order = wd.pen_order([[(150, 390), (160, 390)], [(10, 20), (200, 20)]], 400)
assert order[0] == [(10, 20), (200, 20)], order
assert order[1] == [(150, 390), (160, 390)] or order[1] == [(160, 390), (150, 390)], order
lengths = [wd.polyline_length([(float(a), float(b)) for a, b in re.findall(r"[ML](-?[\d.]+) (-?[\d.]+)", s)])
           for s in d["strokes"]]
first_short = next(i for i, ln in enumerate(lengths) if ln < 160)
assert all(ln < 160 + 8 for ln in lengths[first_short:]), "a long stroke comes after the details began"

# a non-zero viewBox origin must carry through to the box and the strokes
off = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="100 200 400 400">'
       '<rect x="150" y="300" width="300" height="12" fill="#fff"/></svg>')
od = wd.build(off, "X", trace_width=400, art_max_px=200)["data"]
ox, oy, ow, oh = od["box"]
assert 100 < ox < 160 and 250 < oy < 310, od["box"]
opts = [(float(a), float(b)) for s in od["strokes"] for a, b in re.findall(r"[ML](-?[\d.]+) (-?[\d.]+)", s)]
assert all(140 <= px <= 460 and 290 <= py <= 320 for px, py in opts), opts[:4]

# the gates reject what they should
ok_stats = {"strokes": 1, "uncovered_pct": 0.5, "json_gz_bytes": 100_000, "image_bytes": 100_000}
assert wd.limit_problems(ok_stats) == []
assert len(wd.limit_problems({**ok_stats, "uncovered_pct": 1.01})) == 1
assert len(wd.limit_problems({**ok_stats, "json_gz_bytes": 150_001})) == 1

# Temples whose line weights vary: the thickest lines must still be covered by the pen.
# Cody failed the gate at 1.85% when the pen was sized from the mean line width alone.
cody = (TEMPLES_DIR / "Cody" / "Cody Wyoming Temple white.svg").read_text()
cst = wd.build(cody, "CODY, WYOMING")["stats"]
assert cst["uncovered_pct"] < wd.UNCOVERED_LIMIT_PCT, cst

try:
    wd.build('<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"></svg>', "X")
    raise AssertionError("an SVG with no viewBox should be refused")
except wd.DrawingError:
    pass

print("ok")
