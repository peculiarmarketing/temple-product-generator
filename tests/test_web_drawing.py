"""Offline tests for the pen-drawing tracer. No network.

Run: ./.venv.nosync/bin/python tests/test_web_drawing.py
Takes about 15 seconds: it traces the real Logan art twice.
"""

import gzip
import io
import json
import math
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
