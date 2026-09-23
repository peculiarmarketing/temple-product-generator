# Pen-drawn Temples Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Animate the stored temple line art on peculiarpeopleco.com: a homepage showcase that draws six temples in turn, and a band on every product page that draws that product's temple.

**Architecture:** A Python tracer (`web_drawing.py`) turns each temple's white SVG into pen-order centre-line strokes plus a finished-art WebP. `scripts/web_drawings.py` builds those for every temple folder and uploads them, together with four hand-written theme files kept in `theme/`, to the live Shopify theme as `pp-`-prefixed assets. `scripts/pen_templates.py` wires the two new sections into preview-only page layouts first and, after Evan approves, into the real homepage and product page layouts, with backups and a one-command revert. In the browser, `pp-pen-draw.js` uses the strokes as an SVG mask over the finished art, so shoppers always end on the exact stored drawing.

**Tech Stack:** Python 3.12 (`.venv.nosync`), numpy, Pillow, resvg_py (all already in `requirements.txt`); Shopify Admin GraphQL `2025-07` via `shopify_client.ShopifyClient` (`themeFilesUpsert`, `themes.files`); Shopify Liquid sections for shrine-theme-pro; plain browser JavaScript and CSS, no build step.

**Spec:** `docs/superpowers/specs/2026-09-23-pen-drawn-temples-design.md`. Read it before starting. The plan argues from it.

## Global Constraints

- Background `#001A58`; the only lift is a radial gradient to `#0a2873` at the centre. Nothing darker than `#001A58`.
- Pen tip colour `#F58000`. Button background `#F58000`, text `#ffffff`.
- Draw time 8500 ms per temple. Hold 3000 ms after the city line has finished appearing. Showcase cross-fade 700 ms. Exact-art fade-in 600 ms. Letters 45 ms apart.
- Homepage temples, in order: `salt-lake, kirtland, nauvoo, logan, mexico-city, rome`.
- Homepage wording is copied from the live slideshow `hero_slide` word for word: heading `Made to start the conversation`, text `Premium apparel for Latter-day Saints, printed to order in the United States.`, button `Find your temple`. No new customer-facing copy.
- Button link, until the Shop collection is live with the hoodie: `shopify://collections/temple-tees`. After: `shopify://collections/shop`.
- Drawing files: `assets/pp-temple-<slug>.json` and `assets/pp-temple-<slug>.webp`, where `<slug>` is the product's `temple:` tag value.
- City line = the temple manifest's `location_line` (for example `KENSINGTON, MARYLAND` for Washington DC), never the `temple_city` metafield.
- Every new theme file starts with `pp-`. No existing theme file is edited except `templates/index.json` and `templates/product.json` at go-live.
- Gates per drawing: at most 1.0% of art pixels left uncovered by the pen; gzipped strokes plus image at most 250,000 bytes.
- Phone breakpoint `max-width: 749px`. Tap targets at least 44 px. Reduced motion shows the finished drawing with no pen animation.
- House rules: no em dashes in any Evan-facing text; any live store write needs Evan's go for that step; never print or commit the token in `.env`.
- Don't run `pen_templates.py golive` or `revert` while the theme editor is open on the live theme.

## Review Focus

1. **A product whose temple has no uploaded drawing yet** (a new temple published before `push`). Expect: no empty navy box, and the band removes itself. Tested in Task 3 (harness `band-missing`).
2. **The longest city line on a 375 px phone** (`SARATOGA SPRINGS, UTAH`). Expect: one line, no horizontal scroll. Tested in Task 3 (harness at 375 px).
3. **Shoppers with reduced motion turned on.** Expect: finished drawing and city line shown at once, no pen, no endless loop on the product band. Tested in Task 3 (harness `?reduced=1`).
4. **A homepage temple list with a typo or unbuilt slug.** Expect: that entry is skipped, the dots count only real temples, and the rest keep cycling. Tested in Task 3 (harness showcase includes `not-a-temple`).
5. **Scrolling away mid-drawing and back.** Expect: exactly one loop resumes, with no doubled pen and no frozen half-drawing. Tested in Task 3 (harness scroll test).

---

## File Structure

| File | Responsibility |
|---|---|
| `web_drawing.py` (create) | Pure tracer: SVG text + city line -> `{data, image, stats}`. No network, no file IO. |
| `scripts/web_drawings.py` (create) | CLI `build` / `push` / `check`: folder discovery, slugs, file output, theme uploads with read-back. Also exports `upsert_theme_files` and `main_theme_id` for reuse. |
| `scripts/pen_templates.py` (create) | CLI `preview` / `golive` / `revert`: pure JSON transforms of the two page layouts, verification that nothing else moved, backups. |
| `scripts/shop_collection.py` (create) | CLI: create and publish the Shop collection, tag the Temple Art File `listing:standalone`. |
| `theme/assets/pp-pen-draw.js` (create) | Browser drawing engine and the two section controllers. |
| `theme/assets/pp-pen-draw.css` (create) | Styles for both sections, desktop and phone. |
| `theme/sections/pp-temple-showcase.liquid` (create) | Homepage section markup and editor settings. |
| `theme/sections/pp-temple-drawing.liquid` (create) | Product band markup; finds the `temple:` tag. |
| `theme/dev/harness.html` (create) | Local test page that mirrors both sections' rendered markup. |
| `tests/test_web_drawing.py` (create) | Tracer tests on synthetic shapes and real Logan art. |
| `tests/test_web_drawings_cli.py` (create) | Slug mapping, folder discovery, upload planning. |
| `tests/test_pen_templates.py` (create) | Layout transforms against real template fixtures. |
| `tests/fixtures/theme/index.json`, `tests/fixtures/theme/product.json` (create) | Snapshots of the live layouts, taken in Task 6. |
| `.gitignore` (modify) | Ignore `artifacts/web_drawings/` and `artifacts/pen_templates/`. |
| `README.md`, `../.claude/skills/temple-product-generator/SKILL.md`, `docs/decisions.md`, `HANDOFF.md`, `../project-sync/pipeline-and-tools.md` (modify) | Docs, in Task 9. |

Tests follow the repo's existing style: plain Python files that run top to bottom, `assert` with a message, and print `ok` at the end. Run each with `./.venv.nosync/bin/python tests/<file>.py`. There is no pytest.

---

### Task 1: The tracer module

**Files:**
- Create: `web_drawing.py`
- Test: `tests/test_web_drawing.py`

**Interfaces:**
- Consumes: `layout.TEMPLES_DIR` (tests only).
- Produces:
  - `web_drawing.build(svg_text: str, location_line: str, trace_width: int = 1024, art_max_px: int = 840) -> dict` returning `{"data": dict, "image": bytes, "stats": dict}`.
    - `data` = `{"version": 1, "box": [x, y, w, h], "penWidth": float, "city": str, "strokes": [str, ...], "lens": [float, ...]}`. All coordinates are in the SVG's viewBox units, and `strokes[i]` is an SVG path `d` string like `"M10 20 L30 40"` with at least two points.
    - `image` = lossless WebP bytes: white art on transparent, covering exactly `box`.
    - `stats` = `{"strokes": int, "uncovered_pct": float, "json_gz_bytes": int, "image_bytes": int}`.
  - `web_drawing.limit_problems(stats: dict) -> list[str]`: empty when the drawing is within both gates.
  - `web_drawing.thin(mask)`, `web_drawing.trace(mask) -> list[list[tuple[int,int]]]` (points as `(y, x)`), `web_drawing.rdp(points, eps)`, `web_drawing.polyline_length(points)`.
  - Constants `UNCOVERED_LIMIT_PCT = 1.0`, `BUDGET_BYTES = 250_000`.
  - Exception `web_drawing.DrawingError`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_web_drawing.py`:

```python
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

try:
    wd.build('<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"></svg>', "X")
    raise AssertionError("an SVG with no viewBox should be refused")
except wd.DrawingError:
    pass

print("ok")
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `./.venv.nosync/bin/python tests/test_web_drawing.py`
Expected: `ModuleNotFoundError: No module named 'web_drawing'`

- [ ] **Step 3: Write the module**

Create `web_drawing.py`:

```python
"""Pen drawings for the storefront: centre-line strokes in pen order, plus the finished art.

The temple SVGs are VTracer output, so every line in the art is a thin FILLED shape,
not a stroke. Animating those outlines looks like a scanner crawling both edges of
every line. This module finds the centre of each line instead (Zhang-Suen thinning),
joins the thinning's staircase scraps back into continuous strokes (dropping them is
what left gaps on arches and domes in the first mockup), orders the strokes the way a
hand would draw, and checks the result against the real art, adding patch strokes
wherever the pen would leave art hidden.

The browser uses the strokes only as a MASK over the finished-art image, so what a
shopper ends up seeing is the stored drawing. The strokes decide only the order it
appears in. The last 600 ms of the animation fades the unmasked image in, which covers
the hairline edge pixels the pen does not reach.

Design and measurements: docs/superpowers/specs/2026-09-23-pen-drawn-temples-design.md
"""

import gzip
import io
import json
import re

import numpy as np
import resvg_py
from PIL import Image, ImageDraw, ImageFilter

UNCOVERED_LIMIT_PCT = 1.0   # at most this share of art pixels left for the final fade
BUDGET_BYTES = 250_000      # gzipped strokes + image, per temple
PEN_WIDTH_FACTOR = 2.4      # pen width as a multiple of the average line width
PATCH_GROW_PX = 2           # misses this close to the pen are soft edge pixels
PAD_FRACTION = 0.03         # breathing room around the art, as a share of its width
ALPHA_CUTOFF = 100
N8 = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]


class DrawingError(Exception):
    pass


def view_box(svg_text):
    m = re.search(r'viewBox="([^"]+)"', svg_text)
    if not m:
        raise DrawingError("the SVG has no viewBox")
    return [float(v) for v in m.group(1).replace(",", " ").split()]


def render(svg_text, width):
    png = bytes(resvg_py.svg_to_bytes(svg_string=svg_text, width=int(width)))
    return Image.open(io.BytesIO(png)).convert("RGBA")


def thin(mask):
    """Zhang-Suen thinning: a boolean mask reduced to one-pixel centre lines."""
    b = np.pad(mask.astype(np.uint8), 1)
    while True:
        changed = False
        for step in (0, 1):
            n = [np.roll(np.roll(b, dy, 0), dx, 1) for dy, dx in
                 [(1, 0), (1, -1), (0, -1), (-1, -1), (-1, 0), (-1, 1), (0, 1), (1, 1)]]
            p2, p3, p4, p5, p6, p7, p8, p9 = n
            count = sum(n)
            seq = n + [p2]
            transitions = sum(((seq[i] == 0) & (seq[i + 1] == 1)).astype(np.uint8) for i in range(8))
            if step == 0:
                cond = (p2 * p4 * p6 == 0) & (p4 * p6 * p8 == 0)
            else:
                cond = (p2 * p4 * p8 == 0) & (p2 * p6 * p8 == 0)
            kill = (b == 1) & (count >= 2) & (count <= 6) & (transitions == 1) & cond
            if kill.any():
                b = b.copy()
                b[kill] = 0
                changed = True
        if not changed:
            return b[1:-1, 1:-1].astype(bool)


def trace(mask):
    """Boolean mask -> centre-line polylines of (y, x) pixels. Keeps every piece, however short."""
    ys, xs = np.nonzero(thin(mask))
    pix = set(zip(ys.tolist(), xs.tolist()))
    nbrs = {p: [(p[0] + dy, p[1] + dx) for dy, dx in N8 if (p[0] + dy, p[1] + dx) in pix]
            for p in sorted(pix)}
    nodes = {p for p, n in nbrs.items() if len(n) != 2}
    seen, pieces = set(), []

    def key(p, q):
        return (p, q) if p < q else (q, p)

    def walk(start, nxt):
        line = [start, nxt]
        seen.add(key(start, nxt))
        prev, cur = start, nxt
        while cur not in nodes:
            step = [q for q in nbrs[cur] if q != prev and key(cur, q) not in seen]
            if not step:
                break
            prev, cur = cur, step[0]
            seen.add(key(prev, cur))
            line.append(cur)
        return line

    for group in (sorted(nodes), list(nbrs)):  # junction runs first, then pure loops
        for p in group:
            for q in nbrs[p]:
                if key(p, q) not in seen:
                    pieces.append(walk(p, q))
    pieces += [[p, p] for p, n in nbrs.items() if not n]  # isolated dots
    return chain(pieces)


def chain(pieces):
    """Join pieces whose ends touch (same or adjacent pixel) into long strokes,
    preferring the continuation that keeps the current direction."""
    ends = {}
    for i, s in enumerate(pieces):
        ends.setdefault(s[0], []).append(i)
        ends.setdefault(s[-1], []).append(i)
    used = [False] * len(pieces)

    def best_next(line):
        tip, back = line[-1], line[max(0, len(line) - 6)]
        dy, dx = tip[0] - back[0], tip[1] - back[1]
        best, best_score = None, None
        for oy in (-1, 0, 1):
            for ox in (-1, 0, 1):
                at = (tip[0] + oy, tip[1] + ox)
                for j in ends.get(at, ()):
                    if used[j]:
                        continue
                    s = pieces[j] if pieces[j][0] == at else pieces[j][::-1]
                    far = s[min(len(s) - 1, 5)]
                    score = dy * (far[0] - tip[0]) + dx * (far[1] - tip[1])
                    if best_score is None or score > best_score:
                        best, best_score = (j, s), score
        return best

    out = []
    for i in sorted(range(len(pieces)), key=lambda i: (-len(pieces[i]), i)):
        if used[i]:
            continue
        used[i] = True
        line = list(pieces[i])
        for _ in range(2):  # grow forward, then flip and grow the other end
            while (nxt := best_next(line)):
                used[nxt[0]] = True
                line += nxt[1][1:] if nxt[1][0] == line[-1] else nxt[1]
            line.reverse()
        out.append(line)
    return out


def rdp(points, eps):
    """Ramer-Douglas-Peucker simplification, iterative so long strokes cannot overflow the stack."""
    if len(points) < 3:
        return list(points)
    arr = np.array(points, float)
    keep = np.zeros(len(points), bool)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        a, b = stack.pop()
        if b - a < 2:
            continue
        d = arr[b] - arr[a]
        span = np.hypot(*d) or 1.0
        seg = arr[a + 1:b]
        dist = np.abs(d[0] * (seg[:, 1] - arr[a][1]) - d[1] * (seg[:, 0] - arr[a][0])) / span
        i = int(dist.argmax())
        if dist[i] > eps:
            m = a + 1 + i
            keep[m] = True
            stack += [(a, m), (m, b)]
    return [points[i] for i in np.nonzero(keep)[0]]


def polyline_length(points):
    if len(points) < 2:
        return 0.0
    return float(np.sum(np.hypot(*np.diff(np.array(points, float), axis=0).T)))


def paint(strokes, size, width, grow=0):
    """Where a round pen of this width covers, as a boolean mask. Points are (x, y)."""
    im = Image.new("L", size, 0)
    d = ImageDraw.Draw(im)
    r = width / 2
    for s in strokes:
        if len(s) > 1:
            d.line(s, fill=255, width=max(1, round(width)), joint="curve")
        for x, y in s:  # round caps and joins
            d.ellipse([x - r, y - r, x + r, y + r], fill=255)
    if grow:
        im = im.filter(ImageFilter.MaxFilter(2 * grow + 1))
    return np.array(im) > 0


def pen_order(strokes, height):
    """Long structural strokes first, then details. Within each pass, hop to the nearest
    unused stroke end, starting at the bottom-left, the way a hand works across a page."""
    def order(group, start):
        left, res, cur = list(group), [], start
        while left:
            ends = np.array([[s[0][0], s[0][1], s[-1][0], s[-1][1]] for s in left], float)
            d0 = (ends[:, 0] - cur[0]) ** 2 + (ends[:, 1] - cur[1]) ** 2
            d1 = (ends[:, 2] - cur[0]) ** 2 + (ends[:, 3] - cur[1]) ** 2
            i0, i1 = int(d0.argmin()), int(d1.argmin())
            i, rev = (i1, True) if d1[i1] < d0[i0] else (i0, False)
            s = left.pop(i)
            s = s[::-1] if rev else s
            res.append(s)
            cur = s[-1]
        return res

    big = [s for s in strokes if polyline_length(s) >= 40]
    small = [s for s in strokes if polyline_length(s) < 40]
    first = order(big, (0, height))
    return first + order(small, first[-1][-1] if first else (0, height))


def build(svg_text, location_line, trace_width=1024, art_max_px=840):
    vb = view_box(svg_text)
    img = render(svg_text, trace_width)
    scale = vb[2] / img.width  # viewBox units per pixel
    art = np.array(img)[:, :, 3] > ALPHA_CUTOFF
    if not art.any():
        raise DrawingError("the SVG renders empty")

    skeleton = thin(art)
    pen_px = float(art.sum()) / max(1, int(skeleton.sum())) * PEN_WIDTH_FACTOR

    def simplified(pieces):
        return [[(x, y) for y, x in rdp(s, 0.6)] for s in pieces]

    strokes = simplified(trace(art))
    for _ in range(3):  # patch whatever the pen would still leave hidden
        miss = art & ~paint(strokes, img.size, pen_px, grow=PATCH_GROW_PX)
        if not miss.any():
            break
        strokes += simplified(trace(miss))
    uncovered = int((art & ~paint(strokes, img.size, pen_px)).sum())

    ordered = pen_order(strokes, img.height)
    to_vb = [[(round(vb[0] + x * scale), round(vb[1] + y * scale)) for x, y in s] for s in ordered]
    to_vb = [s if len(s) > 1 else s * 2 for s in to_vb]

    ys, xs = np.nonzero(art)
    x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    pad = (x1 - x0) * PAD_FRACTION
    box_px = (x0 - pad, y0 - pad, (x1 - x0) + 2 * pad, (y1 - y0) + 2 * pad)
    box = [round(vb[0] + box_px[0] * scale, 1), round(vb[1] + box_px[1] * scale, 1),
           round(box_px[2] * scale, 1), round(box_px[3] * scale, 1)]

    data = {
        "version": 1,
        "box": box,
        "penWidth": round(pen_px * scale, 1),
        "city": location_line,
        "strokes": ["M" + " L".join(f"{x} {y}" for x, y in s) for s in to_vb],
        "lens": [round(polyline_length(s), 1) for s in to_vb],
    }

    # Finished art, rendered at twice the trace width and cropped to exactly the box.
    k = 2
    big = render(svg_text, trace_width * k)
    crop = big.crop(tuple(round(v * k) for v in
                          (box_px[0], box_px[1], box_px[0] + box_px[2], box_px[1] + box_px[3])))
    crop.thumbnail((art_max_px, art_max_px), Image.LANCZOS)
    alpha = crop.split()[3]
    white = Image.new("L", crop.size, 255)
    out = io.BytesIO()
    Image.merge("RGBA", (white, white, white, alpha)).save(out, "WEBP", lossless=True, method=6)
    image = out.getvalue()

    payload = json.dumps(data, separators=(",", ":")).encode()
    stats = {
        "strokes": len(data["strokes"]),
        "uncovered_pct": round(100 * uncovered / int(art.sum()), 3),
        "json_gz_bytes": len(gzip.compress(payload, 9)),
        "image_bytes": len(image),
    }
    return {"data": data, "image": image, "stats": stats}


def limit_problems(stats):
    problems = []
    if stats["uncovered_pct"] > UNCOVERED_LIMIT_PCT:
        problems.append(f"{stats['uncovered_pct']}% of the art is left uncovered "
                        f"(limit {UNCOVERED_LIMIT_PCT}%)")
    total = stats["json_gz_bytes"] + stats["image_bytes"]
    if total > BUDGET_BYTES:
        problems.append(f"{total:,} bytes over the {BUDGET_BYTES:,} byte budget")
    return problems
```

`crop.thumbnail` only shrinks. If the box crop comes out smaller than `art_max_px`, the `max(img.size) == 840` assertion fails. At `trace_width * 2 = 2048` every temple's box is well over 840 px, so this holds. If it ever fails, raise `k`; don't change the test.

- [ ] **Step 4: Run the tests and confirm they pass**

Run: `./.venv.nosync/bin/python tests/test_web_drawing.py`
Expected: `ok`. If the Logan gates fail, print `r["stats"]` and compare against the mockup numbers: 0.374% uncovered, about 2,800 strokes. A big difference means a port error in `trace`/`chain`, not a reason to loosen a gate.

- [ ] **Step 5: Commit**

```bash
git add web_drawing.py tests/test_web_drawing.py
git commit -m "Pen-drawing tracer: centre-line strokes plus finished art

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: `web_drawings.py build`

**Files:**
- Create: `scripts/web_drawings.py`
- Modify: `.gitignore` (append two ignore lines at the end)
- Test: `tests/test_web_drawings_cli.py`

**Interfaces:**
- Consumes: `web_drawing.build`, `web_drawing.limit_problems`, `web_drawing.DrawingError`; `layout.TEMPLES_DIR`; `layout.working_path(temple_folder, "manifest.json")`.
- Produces (used by Tasks 4 and 6):
  - `slug_for(folder: str) -> str`
  - `temple_folders() -> dict[str, str]`, mapping slug to folder name, for every folder with a manifest and white art.
  - `OUT_DIR: Path` = `artifacts/web_drawings`
  - `drawing_files(slug) -> tuple[str, str]` = `("assets/pp-temple-<slug>.json", "assets/pp-temple-<slug>.webp")`
  - `ATTEMPTS`: the retry ladder for the gates.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_web_drawings_cli.py`:

```python
"""Offline tests for scripts/web_drawings.py. No network.

Run: ./.venv.nosync/bin/python tests/test_web_drawings_cli.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.web_drawings import drawing_files, slug_for, temple_folders  # noqa: E402

# Every `temple:` tag on the live store, read 23 Sep 2026. Folder names must map onto
# exactly these, or a product page would look for a drawing file that is never built.
LIVE_TAGS = {
    "albuquerque", "billings", "boise", "bountiful", "brigham-city", "burley", "cedar-city",
    "cody", "deseret-peak", "draper", "ephraim", "heber-valley", "jordan-river", "kirtland",
    "layton", "lehi", "lindon", "logan", "manhattan", "manti", "mexico-city", "monticello",
    "mount-timpanogos", "nauvoo", "oakland", "ogden", "ogden-original", "orem",
    "provo-city-center", "provo-rock-canyon", "provo", "red-cliffs", "rome", "salt-lake",
    "san-antonio", "san-diego", "saratoga-springs", "smithfield", "spanish-fork", "st-george",
    "syracuse", "taylorsville", "vernal", "washington-d-c", "west-jordan",
}

assert slug_for("Salt Lake") == "salt-lake"
assert slug_for("St. George") == "st-george"
assert slug_for("Heber Valley*") == "heber-valley"
assert slug_for("Ogden (original)") == "ogden-original"
assert slug_for("Washington DC") == "washington-d-c"

folders = temple_folders()
assert set(folders) == LIVE_TAGS, (
    f"missing: {sorted(LIVE_TAGS - set(folders))}  extra: {sorted(set(folders) - LIVE_TAGS)}")
assert folders["washington-d-c"] == "Washington DC"

assert drawing_files("logan") == ("assets/pp-temple-logan.json", "assets/pp-temple-logan.webp")

print("ok")
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `./.venv.nosync/bin/python tests/test_web_drawings_cli.py`
Expected: `ModuleNotFoundError: No module named 'scripts.web_drawings'`

- [ ] **Step 3: Write the build half of the CLI**

Create `scripts/web_drawings.py`:

```python
#!/usr/bin/env python
"""Pen-drawn temples for the storefront: build, upload and check each temple's drawing.

  python scripts/web_drawings.py build --all              # every temple, about 5 s each
  python scripts/web_drawings.py build --temple Logan     # one folder name (repeatable)
  python scripts/web_drawings.py push --dry-run           # what would change in the live theme
  python scripts/web_drawings.py push                     # upload changed drawings and theme code
  python scripts/web_drawings.py check                    # every live temple has its drawing

WHAT IT MAKES. Each temple gets two theme assets, named from the product's `temple:`
tag: pp-temple-<slug>.json (pen strokes in draw order, their lengths, the pen width,
the art box and the city line) and pp-temple-<slug>.webp (the finished art). The
product band and homepage showcase (theme/sections/) find them by that name. The city
line is the manifest's location_line, the same line printed on the garment, so
Washington DC reads KENSINGTON, MARYLAND.

GATES. A drawing is written only if the pen leaves at most 1% of the art for the final
fade and the two files together are at most 250 KB compressed. A temple that misses a
gate is retried with a finer trace, then a smaller image, and reported if it still
fails. Nothing that fails a gate can reach the theme, because push only uploads what
build wrote.

WRITING THE THEME. push uploads only files whose checksum differs from the live
theme's copy, then reads every checksum back. It adds and replaces pp- files only. It
never touches an existing theme file. The page layouts are scripts/pen_templates.py's
job.
"""

import argparse
import base64
import hashlib
import json
import re
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import web_drawing  # noqa: E402
from layout import TEMPLES_DIR, working_path  # noqa: E402

OUT_DIR = PROJECT_ROOT / "artifacts/web_drawings"
THEME_DIR = PROJECT_ROOT / "theme"
THEME_CODE = [
    "assets/pp-pen-draw.js",
    "assets/pp-pen-draw.css",
    "sections/pp-temple-showcase.liquid",
    "sections/pp-temple-drawing.liquid",
]
# Folder names that the generic rule would not turn into their live tag.
SLUG_OVERRIDES = {"Washington DC": "washington-d-c"}
# (trace_width, art_max_px), tried in order until a drawing passes both gates.
ATTEMPTS = [(1024, 840), (1536, 840), (1536, 720)]


def slug_for(folder):
    if folder in SLUG_OVERRIDES:
        return SLUG_OVERRIDES[folder]
    return re.sub(r"[^a-z0-9]+", "-", folder.rstrip("*").lower()).strip("-")


def temple_folders():
    """{slug: folder} for every temple folder with a manifest and white art."""
    found = {}
    for folder in sorted(p.name for p in TEMPLES_DIR.iterdir() if p.is_dir()):
        manifest = working_path(folder, "manifest.json")
        if not manifest.exists():
            continue
        art = json.loads(manifest.read_text()).get("art", {}).get("white")
        if art and (TEMPLES_DIR / folder / art).exists():
            found[slug_for(folder)] = folder
    return found


def drawing_files(slug):
    return (f"assets/pp-temple-{slug}.json", f"assets/pp-temple-{slug}.webp")


def build_one(folder):
    manifest = json.loads(working_path(folder, "manifest.json").read_text())
    svg = (TEMPLES_DIR / folder / manifest["art"]["white"]).read_text()
    for trace_width, art_px in ATTEMPTS:
        result = web_drawing.build(svg, manifest["location_line"], trace_width, art_px)
        problems = web_drawing.limit_problems(result["stats"])
        if not problems:
            return result, [], (trace_width, art_px)
    return result, problems, (trace_width, art_px)


def cmd_build(args):
    folders = temple_folders()
    if args.all:
        chosen = folders
    else:
        by_folder = {f: s for s, f in folders.items()}
        missing = [t for t in args.temple if t not in by_folder]
        if missing:
            raise SystemExit(f"no temple folder with a manifest and white art: {missing}")
        chosen = {by_folder[t]: t for t in args.temple}

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = OUT_DIR / "build-report.json"
    report = json.loads(report_path.read_text()) if report_path.exists() else {}
    failed = []
    for slug, folder in sorted(chosen.items()):
        t0 = time.time()
        result, problems, used = build_one(folder)
        st = result["stats"]
        line = (f"{folder:22} {st['strokes']:5} strokes  {st['uncovered_pct']:.2f}% left  "
                f"{(st['json_gz_bytes'] + st['image_bytes']) // 1024:4} KB  {time.time() - t0:4.1f}s")
        if problems:
            failed.append(folder)
            print(f"{line}  FAILED: {'; '.join(problems)}")
            continue
        json_name, webp_name = drawing_files(slug)
        (OUT_DIR / Path(json_name).name).write_text(
            json.dumps(result["data"], separators=(",", ":")))
        (OUT_DIR / Path(webp_name).name).write_bytes(result["image"])
        report[slug] = {"folder": folder, **st, "trace_width": used[0], "art_px": used[1]}
        print(line + ("" if used == ATTEMPTS[0] else f"  (needed {used})"))
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    if failed:
        print(f"\n{len(failed)} temple(s) not written: {failed}. They get no band until fixed.")
        return 1
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    g = b.add_mutually_exclusive_group(required=True)
    g.add_argument("--all", action="store_true")
    g.add_argument("--temple", action="append", help="temple folder name, e.g. 'Salt Lake'")
    args = ap.parse_args(argv)
    return {"build": cmd_build}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
```

Append to `.gitignore`:

```
# Pen-drawing theme assets, rebuilt from ../Temples/ by scripts/web_drawings.py build
# in about four minutes. The live theme holds the published copy. build-report.json
# is small and records the per-temple numbers, but it lives with the files it describes.
artifacts/web_drawings/

# Page-layout backups written by scripts/pen_templates.py golive, the revert path.
artifacts/pen_templates/
```

- [ ] **Step 4: Run the tests and confirm they pass**

Run: `./.venv.nosync/bin/python tests/test_web_drawings_cli.py`
Expected: `ok`. If the folder set differs, don't edit `LIVE_TAGS`. Add the folder to `SLUG_OVERRIDES` if its tag doesn't follow the generic rule, or report the mismatch to Evan if a folder genuinely has no live product.

- [ ] **Step 5: Build every temple**

Run: `./.venv.nosync/bin/python scripts/web_drawings.py build --all`
Expected: 45 lines, none `FAILED`, exit code 0, and 90 files plus `build-report.json` in `artifacts/web_drawings/`. Paste the summary into the commit message body.

- [ ] **Step 6: Commit**

```bash
git add scripts/web_drawings.py tests/test_web_drawings_cli.py .gitignore
git commit -m "web_drawings.py build: a pen drawing per temple, named by temple tag

<paste the 45-line build summary here>

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: The browser engine, styles and local harness

**Files:**
- Create: `theme/assets/pp-pen-draw.js`
- Create: `theme/assets/pp-pen-draw.css`
- Create: `theme/dev/harness.html`

**Interfaces:**
- Consumes: the `data` JSON shape from Task 1, and the files in `artifacts/web_drawings/` from Task 2.
- Produces the DOM contract that Task 4's Liquid must render exactly:
  - Product band: `<section class="pp-band" data-pp-pen-band data-json="URL" data-img="URL">` containing `.pp-band__inner > [h2.pp-band__name] + .pp-pen[role=img] > .pp-pen__art + .pp-pen__city[aria-hidden]`.
  - Showcase: `<section class="pp-showcase" data-pp-pen-showcase>` containing `.pp-showcase__inner > .pp-showcase__stage > (.pp-pen > .pp-pen__art + .pp-pen__city) + .pp-showcase__dots + span[data-pp-pen-item][data-json][data-img]...`, then `.pp-showcase__copy`.
  - `window.PPPen.init(root)`.

- [ ] **Step 1: Write the harness page (the test)**

Create `theme/dev/harness.html`. It mirrors the rendered markup of both sections and points at the local build output. Serve it from the repo root, so `/artifacts/...` resolves.

```html
<!DOCTYPE html>
<!-- Local test page for assets/pp-pen-draw.js. Mirrors the markup the two Liquid
     sections render. Serve from the repo root:
       ./.venv.nosync/bin/python -m http.server 8765
     then open http://localhost:8765/theme/dev/harness.html (add ?reduced=1 to
     simulate a phone set to reduce motion). -->
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>pp-pen harness</title>
<script>
  if (new URLSearchParams(location.search).has('reduced')) {
    const real = window.matchMedia.bind(window);
    window.matchMedia = (q) => q.includes('prefers-reduced-motion') ? { matches: true, media: q, addEventListener() {}, removeEventListener() {} } : real(q);
  }
</script>
<link rel="stylesheet" href="../assets/pp-pen-draw.css">
<style>body { margin: 0; font-family: Arial, sans-serif; } .gap { height: 120vh; display: grid; place-items: center; color: #999; }</style>
</head>
<body>
<section class="pp-showcase" data-pp-pen-showcase id="showcase">
  <div class="pp-showcase__inner">
    <div class="pp-showcase__stage">
      <div class="pp-pen" role="img" aria-label="Line drawings of temples, drawn one after another">
        <div class="pp-pen__art"></div>
        <div class="pp-pen__city" aria-hidden="true"></div>
      </div>
      <div class="pp-showcase__dots" aria-hidden="true"></div>
      <span hidden data-pp-pen-item data-json="/artifacts/web_drawings/pp-temple-salt-lake.json" data-img="/artifacts/web_drawings/pp-temple-salt-lake.webp"></span>
      <span hidden data-pp-pen-item data-json="/artifacts/web_drawings/pp-temple-not-a-temple.json" data-img="/artifacts/web_drawings/pp-temple-not-a-temple.webp"></span>
      <span hidden data-pp-pen-item data-json="/artifacts/web_drawings/pp-temple-kirtland.json" data-img="/artifacts/web_drawings/pp-temple-kirtland.webp"></span>
      <span hidden data-pp-pen-item data-json="/artifacts/web_drawings/pp-temple-nauvoo.json" data-img="/artifacts/web_drawings/pp-temple-nauvoo.webp"></span>
      <span hidden data-pp-pen-item data-json="/artifacts/web_drawings/pp-temple-logan.json" data-img="/artifacts/web_drawings/pp-temple-logan.webp"></span>
      <span hidden data-pp-pen-item data-json="/artifacts/web_drawings/pp-temple-mexico-city.json" data-img="/artifacts/web_drawings/pp-temple-mexico-city.webp"></span>
      <span hidden data-pp-pen-item data-json="/artifacts/web_drawings/pp-temple-rome.json" data-img="/artifacts/web_drawings/pp-temple-rome.webp"></span>
    </div>
    <div class="pp-showcase__copy">
      <h1 class="pp-showcase__heading">Made to start the conversation</h1>
      <p class="pp-showcase__text">Premium apparel for Latter-day Saints, printed to order in the United States.</p>
      <a class="pp-showcase__btn" href="#">Find your temple</a>
    </div>
  </div>
</section>

<div class="gap">scroll</div>

<section class="pp-band" data-pp-pen-band id="band-saratoga"
  data-json="/artifacts/web_drawings/pp-temple-saratoga-springs.json"
  data-img="/artifacts/web_drawings/pp-temple-saratoga-springs.webp">
  <div class="pp-band__inner">
    <h2 class="pp-band__name">Saratoga Springs Utah Temple</h2>
    <div class="pp-pen" role="img" aria-label="Saratoga Springs Utah Temple">
      <div class="pp-pen__art"></div>
      <div class="pp-pen__city" aria-hidden="true"></div>
    </div>
  </div>
</section>

<div class="gap">scroll</div>

<section class="pp-band" data-pp-pen-band id="band-missing"
  data-json="/artifacts/web_drawings/pp-temple-brand-new.json"
  data-img="/artifacts/web_drawings/pp-temple-brand-new.webp">
  <div class="pp-band__inner">
    <h2 class="pp-band__name">A temple with no drawing yet</h2>
    <div class="pp-pen" role="img" aria-label="A temple with no drawing yet">
      <div class="pp-pen__art"></div>
      <div class="pp-pen__city" aria-hidden="true"></div>
    </div>
  </div>
</section>

<div class="gap">end</div>
<script src="../assets/pp-pen-draw.js" defer></script>
</body>
</html>
```

- [ ] **Step 2: Serve it and confirm it fails**

Run in the background: `./.venv.nosync/bin/python -m http.server 8765` from the repo root.
Open `http://localhost:8765/theme/dev/harness.html` in the Browser pane, which must be visible, because hidden pages don't run animations.
Expected: the unstyled page, and a console 404 for `pp-pen-draw.js` and `.css`.

- [ ] **Step 3: Write the stylesheet**

Create `theme/assets/pp-pen-draw.css`:

```css
/* Peculiar People: pen-drawn temples. Styles for sections/pp-temple-showcase.liquid
   and sections/pp-temple-drawing.liquid. Behaviour lives in pp-pen-draw.js. */

.pp-showcase,
.pp-band {
  --pp-navy: #001A58;
  --pp-lift: #0a2873;
  --pp-orange: #F58000;
  background: radial-gradient(90% 80% at 50% 38%, var(--pp-lift) 0%, var(--pp-navy) 75%);
  color: #fff;
}

.pp-pen { display: flex; flex-direction: column; align-items: center; transition: opacity .7s ease; }
.pp-pen.is-faded { opacity: 0; }
.pp-pen__art { width: 100%; aspect-ratio: 1 / 1; }
.pp-pen__art svg { width: 100%; height: 100%; display: block; overflow: visible; }
.pp-pen__exact { opacity: 0; transition: opacity .6s ease; }
.pp-pen__exact.is-on { opacity: 1; }
.pp-pen__exact.is-instant { transition: none; }
.pp-pen__tip { transition: opacity .5s ease; }
.pp-pen__tip.is-off { opacity: 0; }
.pp-pen__city {
  margin-top: 14px;
  min-height: 1.4em;
  font-family: var(--font-heading-family, Montserrat), Arial, sans-serif;
  font-weight: 700;
  font-size: 15px;
  letter-spacing: .18em;
  white-space: nowrap;
  text-align: center;
}
.pp-pen__city span { opacity: 0; transition: opacity .25s ease; }
.pp-pen__city span.is-on { opacity: 1; }

/* Homepage showcase */
.pp-showcase__inner {
  display: grid;
  grid-template-columns: 1fr 1.1fr;
  align-items: center;
  gap: 24px;
  max-width: 1200px;
  min-height: 520px;
  margin: 0 auto;
  padding: 48px 40px;
}
.pp-showcase__stage { order: 2; display: flex; flex-direction: column; align-items: center; }
.pp-showcase__stage .pp-pen__art { width: min(420px, 100%); }
.pp-showcase__copy { order: 1; }
.pp-showcase__heading { margin: 0 0 14px; color: #fff; font-size: clamp(28px, 4vw, 42px); line-height: 1.1; }
.pp-showcase__text { margin: 0 0 22px; max-width: 440px; color: rgba(255, 255, 255, .8); line-height: 1.5; }
.pp-showcase__btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 48px;
  padding: 0 26px;
  border-radius: 4px;
  background: var(--pp-orange);
  color: #fff;
  font-weight: 700;
  letter-spacing: .03em;
  text-decoration: none;
}
.pp-showcase__btn:focus-visible { outline: 2px solid #fff; outline-offset: 3px; }
.pp-showcase__dots { display: flex; gap: 8px; min-height: 8px; margin-top: 14px; }
.pp-showcase__dots span { width: 8px; height: 8px; border-radius: 50%; background: rgba(255, 255, 255, .3); transition: background .3s; }
.pp-showcase__dots span.is-on { background: var(--pp-orange); }

/* Product band */
.pp-band__inner { display: flex; flex-direction: column; align-items: center; max-width: 1200px; margin: 0 auto; padding: 48px 24px; }
.pp-band__name { margin: 0 0 18px; color: #fff; font-size: 20px; text-align: center; }
.pp-band .pp-pen__art { width: min(440px, 100%); }
.pp-band:not(.is-ready) .pp-pen { visibility: hidden; }

@media (max-width: 749px) {
  .pp-showcase__inner { grid-template-columns: 1fr; min-height: 0; gap: 10px; padding: 24px 20px 32px; }
  .pp-showcase__stage { order: 1; }
  .pp-showcase__copy { order: 2; margin-top: 8px; }
  .pp-showcase__stage .pp-pen__art { width: auto; height: min(42vh, 300px); max-width: 100%; }
  .pp-showcase__btn { display: flex; width: 100%; }
  .pp-band__inner { padding: 32px 20px; }
  .pp-pen__city { font-size: 12.5px; letter-spacing: .14em; }
}
```

- [ ] **Step 4: Write the engine**

Create `theme/assets/pp-pen-draw.js`:

```js
/* Peculiar People: pen-drawn temples.
   Drives sections/pp-temple-showcase.liquid (homepage) and
   sections/pp-temple-drawing.liquid (product page). Data files come from
   scripts/web_drawings.py: pp-temple-<slug>.json (pen strokes in draw order,
   their lengths, pen width, art box, city line) and pp-temple-<slug>.webp (the
   finished art). The strokes are a MASK over the finished art, so a shopper
   always ends up looking at the stored drawing; the last 600 ms fades the
   unmasked art in to cover hairline edges the pen does not reach. */
(() => {
  if (window.PPPen) return;

  const NS = 'http://www.w3.org/2000/svg';
  const DRAW_MS = 8500;   // pen down to pen up, one temple
  const HOLD_MS = 3000;   // finished drawing stays up once the city line is complete
  const FADE_MS = 700;    // showcase cross-fade between temples
  const EXACT_MS = 600;   // unmasked art fades in at the end
  const LETTER_MS = 45;
  const REDUCED = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const ease = (t) => -(Math.cos(Math.PI * t) - 1) / 2;
  const cache = new Map();
  let uid = 0;

  // JSON and image together; a missing file rejects, and the rejection is cached.
  function load(item) {
    if (!cache.has(item.json)) {
      cache.set(item.json, Promise.all([
        fetch(item.json).then((r) => {
          if (!r.ok) throw new Error(`pp-pen: ${r.status} ${item.json}`);
          return r.json();
        }),
        new Promise((resolve, reject) => {
          const img = new Image();
          img.onload = resolve;
          img.onerror = () => reject(new Error(`pp-pen: image failed ${item.img}`));
          img.src = item.img;
        }),
      ]).then(([data]) => data));
    }
    return cache.get(item.json);
  }

  function svgEl(name, attrs) {
    const node = document.createElementNS(NS, name);
    for (const k in attrs) node.setAttribute(k, attrs[k]);
    return node;
  }

  function mount(artEl, data, imgUrl) {
    const [x, y, w, h] = data.box;
    const id = `pp-pen-mask-${++uid}`;
    const svg = svgEl('svg', { viewBox: `${x} ${y} ${w} ${h}`, 'aria-hidden': 'true', focusable: 'false' });
    const mask = svgEl('mask', { id, maskUnits: 'userSpaceOnUse', x, y, width: w, height: h });
    const pen = svgEl('g', { fill: 'none', stroke: '#fff', 'stroke-width': data.penWidth,
      'stroke-linecap': 'round', 'stroke-linejoin': 'round' });
    const paths = data.strokes.map((d) => pen.appendChild(svgEl('path', { d })));
    mask.appendChild(pen);
    const defs = svgEl('defs', {});
    defs.appendChild(mask);
    const image = (extra) => svgEl('image', { href: imgUrl, x, y, width: w, height: h,
      preserveAspectRatio: 'none', ...extra });
    const drawn = image({ mask: `url(#${id})` });
    const exact = image({ class: 'pp-pen__exact' });
    const tip = svgEl('g', { class: 'pp-pen__tip' });
    tip.appendChild(svgEl('circle', { r: data.penWidth * 1.6, fill: '#F58000', opacity: '0.25' }));
    tip.appendChild(svgEl('circle', { r: data.penWidth * 0.55, fill: '#F58000' }));
    svg.append(defs, drawn, exact, tip);
    artEl.replaceChildren(svg);
    return { paths, exact, tip };
  }

  // Resolves once the last letter has faded in.
  function typeCity(cityEl, text, live) {
    const letters = [...text].map((c) => {
      const s = document.createElement('span');
      s.textContent = c === ' ' ? '\u00a0' : c;
      return s;
    });
    cityEl.replaceChildren(...letters);
    if (REDUCED) {
      letters.forEach((s) => s.classList.add('is-on'));
      return Promise.resolve();
    }
    letters.forEach((s, i) => setTimeout(() => live() && s.classList.add('is-on'), i * LETTER_MS));
    return wait(letters.length * LETTER_MS + 250);
  }

  async function draw(stage, data, imgUrl, live) {
    const cityEl = stage.querySelector('.pp-pen__city');
    cityEl.replaceChildren();
    const { paths, exact, tip } = mount(stage.querySelector('.pp-pen__art'), data, imgUrl);
    if (REDUCED) {
      tip.remove();
      exact.classList.add('is-instant', 'is-on');
      await typeCity(cityEl, data.city, live);
      return;
    }
    const lens = data.lens;
    const cum = [0];
    for (const l of lens) cum.push(cum[cum.length - 1] + l);
    const total = cum[cum.length - 1];
    // Hidden until the pen reaches it: a zero-length stroke would otherwise show
    // its round cap as a stray dot from the first frame.
    paths.forEach((p, i) => {
      p.style.visibility = 'hidden';
      p.style.strokeDasharray = `${lens[i]} ${lens[i] + 1}`;
      p.style.strokeDashoffset = lens[i];
    });
    let i = 0;
    const t0 = performance.now();
    await new Promise((done) => {
      const frame = (now) => {
        if (!live()) return done();
        const progress = Math.min(1, (now - t0) / DRAW_MS);
        const target = ease(progress) * total;
        while (i < paths.length && cum[i + 1] <= target) {
          paths[i].style.visibility = 'visible';
          paths[i].style.strokeDashoffset = 0;
          i++;
        }
        if (i < paths.length) {
          const along = target - cum[i];
          if (along > 0) {
            paths[i].style.visibility = 'visible';
            paths[i].style.strokeDashoffset = lens[i] - along;
            const pt = paths[i].getPointAtLength(along);
            tip.setAttribute('transform', `translate(${pt.x} ${pt.y})`);
          }
        }
        if (progress < 1) requestAnimationFrame(frame); else done();
      };
      requestAnimationFrame(frame);
    });
    if (!live()) return;
    tip.classList.add('is-off');
    exact.classList.add('is-on');
    await wait(EXACT_MS);
    if (live()) await typeCity(cityEl, data.city, live);
  }

  function whenVisible(target, onChange) {
    new IntersectionObserver((entries) => entries.forEach((e) => onChange(e.isIntersecting)),
      { rootMargin: '200px 0px' }).observe(target);
  }

  // Product band: draw, hold, redraw while on screen. No drawing file: remove the band.
  function initBand(section) {
    const stage = section.querySelector('.pp-pen');
    const item = { json: section.dataset.json, img: section.dataset.img };
    let visible = false;
    let run = 0;
    let running = false;
    let finished = false;
    const start = async () => {
      if (running || finished) return;
      running = true;
      const mine = ++run;
      const live = () => visible && run === mine;
      try {
        const data = await load(item);
        section.classList.add('is-ready');
        while (live()) {
          await draw(stage, data, item.img, live);
          if (REDUCED) { finished = true; break; }
          if (live()) await wait(HOLD_MS);
        }
      } catch (err) {
        finished = true;
        section.remove();
        console.warn(err);
      } finally {
        running = false;
        if (visible && !finished) start();
      }
    };
    whenVisible(section, (v) => { visible = v; if (v) start(); else run++; });
  }

  // Homepage showcase: each temple in turn. Entries whose files are missing are dropped.
  function initShowcase(section) {
    const stage = section.querySelector('.pp-pen');
    const dotsEl = section.querySelector('.pp-showcase__dots');
    const items = [...section.querySelectorAll('[data-pp-pen-item]')]
      .map((n) => ({ json: n.dataset.json, img: n.dataset.img }));
    const renderDots = (active) => dotsEl.replaceChildren(...items.map((_, j) => {
      const dot = document.createElement('span');
      if (j === active) dot.className = 'is-on';
      return dot;
    }));
    let idx = 0;
    let visible = false;
    let run = 0;
    let running = false;
    if (items.length) load(items[0]).catch(() => {});  // above the fold: fetch now
    const start = async () => {
      if (running) return;
      running = true;
      const mine = ++run;
      const live = () => visible && run === mine;
      try {
        while (live() && items.length) {
          idx %= items.length;
          const item = items[idx];
          let data;
          try {
            data = await load(item);
          } catch (err) {
            console.warn(err);
            items.splice(idx, 1);
            continue;
          }
          if (!live()) break;
          renderDots(idx);
          stage.classList.remove('is-faded');
          if (items.length > 1) load(items[(idx + 1) % items.length]).catch(() => {});
          await draw(stage, data, item.img, live);
          if (!live()) break;
          await wait(HOLD_MS);
          if (!live() || items.length < 2) break;  // a single temple just stays drawn
          stage.classList.add('is-faded');
          await wait(FADE_MS);
          idx++;
        }
        if (!items.length) section.querySelector('.pp-showcase__stage').hidden = true;
      } finally {
        running = false;
        if (visible && items.length > 1) start();
      }
    };
    whenVisible(section, (v) => { visible = v; if (v) start(); else run++; });
  }

  function init(root = document) {
    root.querySelectorAll('[data-pp-pen-band]:not([data-pp-pen-init])').forEach((s) => {
      s.dataset.ppPenInit = '1';
      initBand(s);
    });
    root.querySelectorAll('[data-pp-pen-showcase]:not([data-pp-pen-init])').forEach((s) => {
      s.dataset.ppPenInit = '1';
      initShowcase(s);
    });
  }

  window.PPPen = { init };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => init());
  else init();
  document.addEventListener('shopify:section:load', (e) => init(e.target));
})();
```

- [ ] **Step 5: Verify in the harness (the Review Focus tests)**

With the Browser pane visible, reload `http://localhost:8765/theme/dev/harness.html` and run each check with `javascript_tool`. Every expected value must match.

1. Showcase draws, then skips the bad slug (Review Focus 4). At 11 s after load:
   ```js
   ({ city: document.querySelector('#showcase .pp-pen__city').textContent.replace(/\u00a0/g, ' '),
      exact: document.querySelector('#showcase .pp-pen__exact').classList.contains('is-on') })
   ```
   Expected: `{ city: "SALT LAKE CITY, UTAH", exact: true }`. At 20 s, read
   `document.querySelectorAll('#showcase .pp-showcase__dots span').length`. Expected: `6`
   (seven entries, minus `not-a-temple`, which is dropped when the loop reaches it).
2. The showcase moves on after the hold. Poll `city` every 250 ms for 30 s. Expected: it becomes `KIRTLAND, OHIO`. The full city line stays up about 3000 ms, measured from the last letter to clearing, allowing ±400 ms.
3. Missing drawing (Review Focus 1). Scroll `#band-missing` into view, wait 2 s, then run `!!document.getElementById('band-missing')`. Expected: `false`.
4. Band and the longest city line on a phone (Review Focus 2). Run `resize_window` with preset `mobile` and reload. Scroll `#band-saratoga` into view and wait 12 s, then run:
   ```js
   ({ ready: document.getElementById('band-saratoga').classList.contains('is-ready'),
      city: document.querySelector('#band-saratoga .pp-pen__city').textContent.replace(/\u00a0/g, ' '),
      cityFits: document.querySelector('#band-saratoga .pp-pen__city').scrollWidth <= document.documentElement.clientWidth,
      noSideScroll: document.documentElement.scrollWidth <= document.documentElement.clientWidth })
   ```
   Expected: all true, and city `SARATOGA SPRINGS, UTAH`. Take a screenshot of the showcase at the top as well. The drawing sits above the heading and the full-width button is visible without scrolling. Reset with preset `desktop`.
5. Scroll away and back (Review Focus 5). Scroll `#band-saratoga` into view, wait 3 s, scroll to the top, wait 1 s, scroll back, and wait 3 s. Then count the tips: `document.querySelectorAll('#band-saratoga .pp-pen__tip').length`. Expected: `1`. Also confirm the tip's `transform` value changes between two reads 200 ms apart, which shows exactly one live pen.
6. Reduced motion (Review Focus 3). Open `harness.html?reduced=1`. After 1.5 s, `#showcase .pp-pen__exact` has `is-instant` and `is-on`, no `.pp-pen__tip` exists, and the city line is complete. Scroll to `#band-saratoga`. After 2 s the same holds, and 12 s later there's still one svg, with no redraw.
7. `read_console_messages` with `onlyErrors: true`. Expected: nothing except the two intentional 404s, for `not-a-temple` and `brand-new`.

If any check fails, fix `pp-pen-draw.js` or `.css` and rerun all seven. Stop the http.server when done.

- [ ] **Step 6: Commit**

```bash
git add theme/assets/pp-pen-draw.js theme/assets/pp-pen-draw.css theme/dev/harness.html
git commit -m "Pen-drawing engine, styles and local harness

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: The two Liquid sections, then `push` and `check`

**Files:**
- Create: `theme/sections/pp-temple-showcase.liquid`
- Create: `theme/sections/pp-temple-drawing.liquid`
- Modify: `scripts/web_drawings.py`, adding `push`, `check` and the shared theme helpers
- Modify: `tests/test_web_drawings_cli.py`, adding the upload-planning tests

**Interfaces:**
- Consumes: the Task 3 DOM contract; `ShopifyClient.gql`; `drawing_files`, `temple_folders`, `OUT_DIR`, `THEME_DIR`, `THEME_CODE` from Task 2.
- Produces (used by Task 6):
  - `main_theme_id(client) -> str` (theme gid)
  - `remote_checksums(client, theme_gid, patterns: list[str]) -> dict[str, str]`
  - `upsert_theme_files(client, theme_gid, files: dict[str, bytes]) -> None`, which raises `SystemExit` on user errors.
  - `plan_uploads(local: dict[str, bytes], remote: dict[str, str]) -> list[str]`
  - `md5(b: bytes) -> str`

- [ ] **Step 1: Write the showcase section**

Create `theme/sections/pp-temple-showcase.liquid`:

```liquid
{%- comment -%}
  Peculiar People homepage showcase: temples drawn by pen, one after another.
  Drawing files are built and uploaded by scripts/web_drawings.py as
  pp-temple-<slug>.json and .webp. "Temples" takes the temple tag names (the part
  after `temple:`), comma separated, in the order they draw. A name with no uploaded
  drawing is skipped.
{%- endcomment -%}
{{ 'pp-pen-draw.css' | asset_url | stylesheet_tag }}
<script src="{{ 'pp-pen-draw.js' | asset_url }}" defer></script>
{%- assign slugs = section.settings.temples | split: ',' -%}
<section class="pp-showcase" data-pp-pen-showcase>
  <div class="pp-showcase__inner">
    <div class="pp-showcase__stage">
      <div class="pp-pen" role="img" aria-label="{{ section.settings.drawing_label | escape }}">
        <div class="pp-pen__art"></div>
        <div class="pp-pen__city" aria-hidden="true"></div>
      </div>
      <div class="pp-showcase__dots" aria-hidden="true"></div>
      {%- for s in slugs -%}
        {%- assign slug = s | strip | downcase -%}
        {%- if slug != blank -%}
          <span hidden data-pp-pen-item
            data-json="{{ 'pp-temple-' | append: slug | append: '.json' | asset_url }}"
            data-img="{{ 'pp-temple-' | append: slug | append: '.webp' | asset_url }}"></span>
        {%- endif -%}
      {%- endfor -%}
    </div>
    <div class="pp-showcase__copy">
      {%- if section.settings.heading != blank -%}
        <h1 class="pp-showcase__heading">{{ section.settings.heading }}</h1>
      {%- endif -%}
      {%- if section.settings.subheading != blank -%}
        <p class="pp-showcase__text">{{ section.settings.subheading | escape }}</p>
      {%- endif -%}
      {%- if section.settings.button_label != blank and section.settings.link != blank -%}
        <a class="pp-showcase__btn" href="{{ section.settings.link }}">{{ section.settings.button_label | escape }}</a>
      {%- endif -%}
    </div>
  </div>
</section>

{% schema %}
{
  "name": "PP temple showcase",
  "settings": [
    { "type": "inline_richtext", "id": "heading", "label": "Heading" },
    { "type": "text", "id": "subheading", "label": "Text" },
    { "type": "text", "id": "button_label", "label": "Button label" },
    { "type": "url", "id": "link", "label": "Button link" },
    {
      "type": "text",
      "id": "temples",
      "label": "Temples",
      "info": "Temple tag names (after temple:), comma separated, in the order they draw.",
      "default": "salt-lake, kirtland, nauvoo, logan, mexico-city, rome"
    },
    {
      "type": "text",
      "id": "drawing_label",
      "label": "Drawing description for screen readers",
      "default": "Line drawings of temples, drawn one after another"
    }
  ],
  "presets": [{ "name": "PP temple showcase" }]
}
{% endschema %}
```

The screen-reader description is the only new wording, and only screen readers read it. Show Evan the default at the Task 7 gate.

- [ ] **Step 2: Write the product band section**

Create `theme/sections/pp-temple-drawing.liquid`:

```liquid
{%- comment -%}
  Peculiar People product band: this product's temple, drawn by pen.
  Finds its drawing from the product's `temple:` tag. No tag (the Temple Art File):
  renders nothing. A tag whose drawing is not uploaded yet: pp-pen-draw.js removes
  the band, so a shopper never sees an empty box. Files come from
  scripts/web_drawings.py.
{%- endcomment -%}
{%- liquid
  assign slug = ''
  for tag in product.tags
    assign head = tag | slice: 0, 7
    if head == 'temple:'
      assign slug = tag | remove_first: 'temple:'
      break
    endif
  endfor
  assign temple_name = product.metafields.peculiar.temple_name.value
-%}
{%- if slug != blank -%}
  {{ 'pp-pen-draw.css' | asset_url | stylesheet_tag }}
  <script src="{{ 'pp-pen-draw.js' | asset_url }}" defer></script>
  <section class="pp-band" data-pp-pen-band
    data-json="{{ 'pp-temple-' | append: slug | append: '.json' | asset_url }}"
    data-img="{{ 'pp-temple-' | append: slug | append: '.webp' | asset_url }}">
    <div class="pp-band__inner">
      {%- if temple_name != blank -%}
        <h2 class="pp-band__name">{{ temple_name | escape }}</h2>
      {%- endif -%}
      <div class="pp-pen" role="img" aria-label="{{ temple_name | default: product.title | escape }}">
        <div class="pp-pen__art"></div>
        <div class="pp-pen__city" aria-hidden="true"></div>
      </div>
    </div>
  </section>
{%- endif -%}

{% schema %}
{
  "name": "PP temple drawing",
  "enabled_on": { "templates": ["product"] },
  "settings": [],
  "presets": [{ "name": "PP temple drawing" }]
}
{% endschema %}
```

- [ ] **Step 3: Write the failing tests for upload planning**

Insert before the final `print("ok")` in `tests/test_web_drawings_cli.py`:

```python
from scripts.web_drawings import md5, plan_uploads  # noqa: E402

local = {"assets/a.json": b"one", "assets/b.webp": b"two", "assets/c.js": b"three"}
remote = {"assets/a.json": md5(b"one"), "assets/b.webp": md5(b"old"), "assets/zzz.json": "x"}
assert plan_uploads(local, remote) == ["assets/b.webp", "assets/c.js"], plan_uploads(local, remote)
assert plan_uploads(local, {k: md5(v) for k, v in local.items()}) == []
```

Run: `./.venv.nosync/bin/python tests/test_web_drawings_cli.py`
Expected: `ImportError: cannot import name 'md5'`

- [ ] **Step 4: Add the theme helpers, `push` and `check`**

In `scripts/web_drawings.py`, add `from shopify_client import ShopifyClient  # noqa: E402` after the `layout` import. Then add the following above `def main`:

```python
def md5(b):
    return hashlib.md5(b).hexdigest()


def main_theme_id(client):
    nodes = client.gql("{ themes(first: 1, roles: [MAIN]) { nodes { id name } } }")["themes"]["nodes"]
    if not nodes:
        raise SystemExit("no published theme found.")
    return nodes[0]["id"]


def remote_checksums(client, theme_gid, patterns):
    """{filename: md5} for live theme files matching the patterns (Shopify wildcards)."""
    out, after = {}, None
    while True:
        theme = client.gql("""
          query($id: ID!, $f: [String!], $after: String) { theme(id: $id) {
            files(filenames: $f, first: 250, after: $after) {
              nodes { filename checksumMd5 }
              pageInfo { hasNextPage endCursor } } } }""",
            {"id": theme_gid, "f": patterns, "after": after})["theme"]
        page = theme["files"]
        out.update({n["filename"]: n["checksumMd5"] for n in page["nodes"]})
        if not page["pageInfo"]["hasNextPage"]:
            return out
        after = page["pageInfo"]["endCursor"]


def upsert_theme_files(client, theme_gid, files):
    """Write {filename: bytes} into the theme, 10 per call. Text as TEXT, images as BASE64."""
    names = sorted(files)
    for i in range(0, len(names), 10):
        batch = []
        for name in names[i:i + 10]:
            body = files[name]
            if name.endswith(".webp"):
                batch.append({"filename": name, "body": {"type": "BASE64",
                              "value": base64.b64encode(body).decode()}})
            else:
                batch.append({"filename": name, "body": {"type": "TEXT", "value": body.decode()}})
        result = client.gql("""
          mutation($themeId: ID!, $files: [OnlineStoreThemeFilesUpsertFileInput!]!) {
            themeFilesUpsert(themeId: $themeId, files: $files) {
              upsertedThemeFiles { filename }
              userErrors { filename code message } } }""",
            {"themeId": theme_gid, "files": batch})["themeFilesUpsert"]
        if result["userErrors"]:
            raise SystemExit(f"theme write refused: {result['userErrors']}")


def plan_uploads(local, remote):
    return sorted(n for n, b in local.items() if remote.get(n) != md5(b))


def local_theme_files(slugs=None):
    files = {name: (THEME_DIR / name).read_bytes() for name in THEME_CODE}
    for path in sorted(OUT_DIR.glob("pp-temple-*")):
        if path.suffix not in (".json", ".webp"):
            continue
        slug = path.stem[len("pp-temple-"):]
        if slugs is None or slug in slugs:
            files[f"assets/{path.name}"] = path.read_bytes()
    return files


PATTERNS = ["assets/pp-*", "sections/pp-*"]


def cmd_push(args):
    slugs = None
    if args.temple:
        folders = {f: s for s, f in temple_folders().items()}
        slugs = {folders[t] for t in args.temple}
    local = local_theme_files(slugs)
    client = ShopifyClient()
    theme_gid = main_theme_id(client)
    todo = plan_uploads(local, remote_checksums(client, theme_gid, PATTERNS))
    print(f"theme  : {theme_gid}")
    print(f"local  : {len(local)} files, {len(todo)} new or changed")
    for name in todo:
        print(f"  {name}  {len(local[name]) // 1024} KB")
    if not todo:
        print("the live theme already has all of these. Nothing to do.")
        return 0
    if args.dry_run:
        print("\nDRY RUN, nothing sent.")
        return 0
    upsert_theme_files(client, theme_gid, {n: local[n] for n in todo})
    after = remote_checksums(client, theme_gid, PATTERNS)
    wrong = [n for n in todo if after.get(n) != md5(local[n])]
    if wrong:
        raise SystemExit(f"read-back mismatch on {wrong}. Re-run push; if it persists, stop.")
    print(f"written and read back: {len(todo)} files.")
    return 0


def live_temple_slugs(client):
    slugs, after = set(), None
    while True:
        page = client.gql("""
          query($after: String) { products(first: 250, after: $after, query: "status:active") {
            nodes { tags } pageInfo { hasNextPage endCursor } } }""", {"after": after})["products"]
        for node in page["nodes"]:
            slugs |= {t[len("temple:"):] for t in node["tags"] if t.startswith("temple:")}
        if not page["pageInfo"]["hasNextPage"]:
            return slugs
        after = page["pageInfo"]["endCursor"]


def cmd_check(_args):
    client = ShopifyClient()
    theme_gid = main_theme_id(client)
    remote = remote_checksums(client, theme_gid, PATTERNS)
    slugs = live_temple_slugs(client)
    missing = sorted(s for s in slugs if not all(f in remote for f in drawing_files(s)))
    code_missing = [n for n in THEME_CODE if n not in remote]
    print(f"live temples: {len(slugs)}   with drawings in the theme: {len(slugs) - len(missing)}")
    if code_missing:
        print(f"theme code missing: {code_missing}")
    if missing:
        print(f"no drawing yet (their product band stays hidden): {missing}")
        print("fix: web_drawings.py build --temple '<folder>' && web_drawings.py push")
    return 1 if (missing or code_missing) else 0
```

In `main`, register the new commands:

```python
    p = sub.add_parser("push")
    p.add_argument("--temple", action="append", help="limit drawings to these folders")
    p.add_argument("--dry-run", action="store_true")
    sub.add_parser("check")
    args = ap.parse_args(argv)
    return {"build": cmd_build, "push": cmd_push, "check": cmd_check}[args.cmd](args)
```

`push` always includes the four theme code files, so a code change ships with any push.

- [ ] **Step 5: Run the tests and confirm they pass**

Run: `./.venv.nosync/bin/python tests/test_web_drawings_cli.py`
Expected: `ok`

- [ ] **Step 6: Dry run against the live theme (read-only)**

Run: `./.venv.nosync/bin/python scripts/web_drawings.py push --dry-run`
Expected: 94 new files (90 drawings plus 4 code files) and `DRY RUN, nothing sent.`

- [ ] **Step 7: Push (live, but invisible to customers)**

This writes new `pp-` files only; no page references them yet. Evan approved rollout step 1 in the spec. Tell Evan in one line that it's happening, then run:
`./.venv.nosync/bin/python scripts/web_drawings.py push`
Expected: `written and read back: 94 files.`
Then: `./.venv.nosync/bin/python scripts/web_drawings.py check`
Expected: `live temples: 45   with drawings in the theme: 45`, exit code 0.
Then open `https://peculiarpeopleco.com/` in the Browser pane and confirm the homepage is unchanged: the slideshow heading `Made to start the conversation` is present, and there's no `[data-pp-pen-showcase]`.

If Shopify rejects the `.liquid` files, the error names the line. Fix the file, rerun `push`, and don't touch anything else in the theme.

- [ ] **Step 8: Commit**

```bash
git add theme/sections scripts/web_drawings.py tests/test_web_drawings_cli.py
git commit -m "Theme sections plus web_drawings.py push/check; 94 pp- files live, unreferenced

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Page-layout transforms (`pen_templates.py`, offline)

**Files:**
- Create: `scripts/pen_templates.py`
- Create: `tests/fixtures/theme/index.json`, `tests/fixtures/theme/product.json`
- Test: `tests/test_pen_templates.py`

**Interfaces:**
- Consumes: `main_theme_id`, `upsert_theme_files` from `scripts.web_drawings`; `theme_file` from `scripts.swatches` (it reads any filename in the live theme).
- Produces:
  - `split_banner(content: str) -> tuple[str, dict]`
  - `add_showcase(index_doc: dict, link: str = INTERIM_LINK) -> dict`
  - `add_band(product_doc: dict) -> dict`
  - `changed_paths(a, b) -> set[tuple]`
  - `verify(before: dict, after: dict, expected: set[tuple]) -> None`, which raises `SystemExit` naming any unexpected path.
  - Constants `SHOWCASE_ID = "pp_temple_showcase"`, `BAND_ID = "pp_temple_drawing"`, `INTERIM_LINK = "shopify://collections/temple-tees"`, `HOME_TEMPLES = "salt-lake, kirtland, nauvoo, logan, mexico-city, rome"`.

- [ ] **Step 1: Save the live layouts as fixtures (read-only)**

Run:

```bash
./.venv.nosync/bin/python - <<'EOF'
import sys; sys.path.insert(0, ".")
from pathlib import Path
from shopify_client import ShopifyClient
from scripts.swatches import theme_file
c = ShopifyClient(); d = Path("tests/fixtures/theme"); d.mkdir(parents=True, exist_ok=True)
for name in ("index.json", "product.json"):
    (d / name).write_text(theme_file(c, f"templates/{name}")[1])
    print(name, len((d / name).read_text()))
EOF
```

Expected: two sizes printed. Open each and confirm there's no token or licence blob, only section settings.

- [ ] **Step 2: Write the failing tests**

Create `tests/test_pen_templates.py`:

```python
"""Offline tests for scripts/pen_templates.py against snapshots of the live layouts.

Run: ./.venv.nosync/bin/python tests/test_pen_templates.py
"""

import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.pen_templates import (  # noqa: E402
    BAND_ID, HOME_TEMPLES, INTERIM_LINK, SHOWCASE_ID,
    add_band, add_showcase, changed_paths, split_banner, verify,
)

FIX = Path(__file__).resolve().parent / "fixtures/theme"
_, index = split_banner((FIX / "index.json").read_text())
_, product = split_banner((FIX / "product.json").read_text())

# homepage: showcase first, hero switched off (not deleted), wording copied exactly
home = add_showcase(index)
slide = index["sections"]["hero"]["blocks"][index["sections"]["hero"]["block_order"][0]]["settings"]
show = home["sections"][SHOWCASE_ID]
assert home["order"][0] == SHOWCASE_ID and home["order"][1:] == index["order"]
assert home["sections"]["hero"]["disabled"] is True
assert show["type"] == "pp-temple-showcase"
assert show["settings"]["heading"] == slide["heading"] == "Made to start the conversation"
assert show["settings"]["subheading"] == slide["subheading"]
assert show["settings"]["button_label"] == slide["button_label"] == "Find your temple"
assert show["settings"]["link"] == INTERIM_LINK
assert show["settings"]["temples"] == HOME_TEMPLES
assert "hero" in home["sections"], "the old banner must be kept, only disabled"
verify(index, home, {("order",), ("sections", SHOWCASE_ID), ("sections", "hero", "disabled")})
assert index["order"][0] == "hero" and "disabled" not in index["sections"]["hero"], "input was mutated"
assert add_showcase(index, "shopify://collections/shop")["sections"][SHOWCASE_ID]["settings"]["link"] == "shopify://collections/shop"

# product: band right after main, nothing else moved
prod = add_band(product)
assert prod["order"][prod["order"].index("main") + 1] == BAND_ID
assert prod["sections"][BAND_ID] == {"type": "pp-temple-drawing", "settings": {}}
verify(product, prod, {("order",), ("sections", BAND_ID)})

# running twice is refused rather than doubling the section
for fn, doc in ((add_showcase, home), (add_band, prod)):
    try:
        fn(doc)
        raise AssertionError(f"{fn.__name__} ran twice")
    except ValueError:
        pass

# verify catches a stray change anywhere else
tampered = copy.deepcopy(prod)
tampered["sections"]["main"]["settings"]["x"] = 1
assert ("sections", "main", "settings", "x") in changed_paths(product, tampered)
try:
    verify(product, tampered, {("order",), ("sections", BAND_ID)})
    raise AssertionError("verify missed a stray change")
except SystemExit:
    pass

print("ok")
```

Run: `./.venv.nosync/bin/python tests/test_pen_templates.py`
Expected: `ModuleNotFoundError: No module named 'scripts.pen_templates'`

- [ ] **Step 3: Write the transforms and CLI**

Create `scripts/pen_templates.py`:

```python
#!/usr/bin/env python
"""Wire the pen-drawn temple sections into the live theme's page layouts.

  python scripts/pen_templates.py preview [--dry-run]   # preview-only layouts, ?view=pen-preview
  python scripts/pen_templates.py golive [--dry-run] [--link shopify://collections/shop]
  python scripts/pen_templates.py revert                # put back what the last golive replaced

preview writes templates/index.pen-preview.json and templates/product.pen-preview.json,
which Shopify serves only when an address carries ?view=pen-preview, so customers never
see them. golive makes the same two changes to the real templates/index.json and
templates/product.json, and only after Evan's go at the review gate: the showcase goes
first on the homepage with the old slideshow disabled (not deleted), and the drawing band
goes straight after the main product section.

Every write is checked first: the new layout is compared with the live one key by key,
and nothing is sent if anything beyond the intended change would move. golive saves both
live files to artifacts/pen_templates/<timestamp>/ before writing, and revert restores
the newest save. Unlike config/settings_data.json in swatches.py, these layouts are
re-serialised whole: adding a section is a structural edit, and the key-by-key check is
what guarantees nothing else changed. Do not run golive or revert with the theme editor
open on the live theme; the editor saves whole files and the last save wins.
"""

import argparse
import copy
import json
import re
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from shopify_client import ShopifyClient  # noqa: E402
from scripts.swatches import theme_file  # noqa: E402
from scripts.web_drawings import main_theme_id, upsert_theme_files  # noqa: E402

SHOWCASE_ID = "pp_temple_showcase"
BAND_ID = "pp_temple_drawing"
INTERIM_LINK = "shopify://collections/temple-tees"
HOME_TEMPLES = "salt-lake, kirtland, nauvoo, logan, mexico-city, rome"
BACKUP_DIR = PROJECT_ROOT / "artifacts/pen_templates"
BANNER = re.compile(r"^\s*/\*.*?\*/\s*", re.S)
EXPECTED_INDEX = {("order",), ("sections", SHOWCASE_ID), ("sections", "hero", "disabled")}
EXPECTED_PRODUCT = {("order",), ("sections", BAND_ID)}


def split_banner(content):
    m = BANNER.match(content)
    banner = m.group(0) if m else ""
    return banner, json.loads(content[len(banner):])


def join_banner(banner, doc):
    return banner + json.dumps(doc, indent=2, ensure_ascii=False) + "\n"


def add_showcase(index_doc, link=INTERIM_LINK):
    doc = copy.deepcopy(index_doc)
    if SHOWCASE_ID in doc["sections"]:
        raise ValueError("this homepage already has the showcase")
    hero = doc["sections"]["hero"]
    slide = hero["blocks"][hero["block_order"][0]]["settings"]
    doc["sections"][SHOWCASE_ID] = {
        "type": "pp-temple-showcase",
        "settings": {
            "heading": slide["heading"],
            "subheading": slide.get("subheading", ""),
            "button_label": slide.get("button_label", ""),
            "link": link,
            "temples": HOME_TEMPLES,
        },
    }
    doc["order"].insert(0, SHOWCASE_ID)
    hero["disabled"] = True
    return doc


def add_band(product_doc):
    doc = copy.deepcopy(product_doc)
    if BAND_ID in doc["sections"]:
        raise ValueError("this product layout already has the drawing band")
    doc["sections"][BAND_ID] = {"type": "pp-temple-drawing", "settings": {}}
    doc["order"].insert(doc["order"].index("main") + 1, BAND_ID)
    return doc


def changed_paths(a, b, prefix=()):
    if isinstance(a, dict) and isinstance(b, dict):
        out = set()
        for k in set(a) | set(b):
            if k not in a or k not in b:
                out.add(prefix + (k,))
            elif a[k] != b[k]:
                out |= changed_paths(a[k], b[k], prefix + (k,))
        return out
    return set() if a == b else {prefix}


def verify(before, after, expected):
    moved = changed_paths(before, after)
    if moved != expected:
        raise SystemExit(f"the edit would change {sorted(moved)}, expected exactly "
                         f"{sorted(expected)}. Nothing sent.")


def planned(client, link):
    """[(target filename, live banner, live doc, new doc, expected paths)] for both layouts."""
    out = []
    for name, fn, expected in (("templates/index.json", lambda d: add_showcase(d, link), EXPECTED_INDEX),
                               ("templates/product.json", add_band, EXPECTED_PRODUCT)):
        banner, doc = split_banner(theme_file(client, name)[1])
        new = fn(doc)
        verify(doc, new, expected)
        out.append((name, banner, doc, new))
    return out


def cmd_preview(args):
    client = ShopifyClient()
    theme_gid = main_theme_id(client)
    files = {}
    for name, _banner, _doc, new in planned(client, args.link):
        target = name.replace(".json", ".pen-preview.json")
        files[target] = join_banner("", new).encode()
        print(f"{target}: {len(new['order'])} sections, first {new['order'][:2]}")
    if args.dry_run:
        print("\nDRY RUN, nothing sent.")
        return 0
    upsert_theme_files(client, theme_gid, files)
    # Compare content, not bytes: Shopify may reformat a layout file when it saves it.
    wrong = [n for n in files if split_banner(theme_file(client, n)[1])[1] != json.loads(files[n])]
    if wrong:
        raise SystemExit(f"read-back mismatch on {wrong}")
    print("preview layouts written. Customers see nothing; add ?view=pen-preview to view.")
    return 0


def cmd_golive(args):
    client = ShopifyClient()
    theme_gid = main_theme_id(client)
    plans = planned(client, args.link)
    for name, _b, _d, new in plans:
        print(f"{name}: order becomes {new['order'][:3]} ...")
    if args.dry_run:
        print("\nDRY RUN, nothing sent.")
        return 0
    stamp = BACKUP_DIR / time.strftime("%Y%m%d-%H%M%S")
    stamp.mkdir(parents=True)
    files = {}
    for name, banner, doc, new in plans:
        (stamp / Path(name).name).write_text(theme_file(client, name)[1])
        files[name] = join_banner(banner, new).encode()
    print(f"live layouts saved to {stamp.relative_to(PROJECT_ROOT)}")
    upsert_theme_files(client, theme_gid, files)
    for name, _b, _d, new in plans:
        _, live = split_banner(theme_file(client, name)[1])
        if live != new:
            raise SystemExit(f"{name} read back different from what was sent. Run revert.")
    print("live. Undo with: scripts/pen_templates.py revert")
    return 0


def cmd_revert(_args):
    saves = sorted(p for p in BACKUP_DIR.glob("*") if p.is_dir()) if BACKUP_DIR.exists() else []
    if not saves:
        raise SystemExit("no golive backup found in artifacts/pen_templates/.")
    latest = saves[-1]
    files = {f"templates/{p.name}": p.read_bytes() for p in sorted(latest.glob("*.json"))}
    client = ShopifyClient()
    upsert_theme_files(client, main_theme_id(client), files)
    for name, body in files.items():  # content, not bytes: Shopify may reformat on save
        if split_banner(theme_file(client, name)[1])[1] != split_banner(body.decode())[1]:
            raise SystemExit(f"{name} did not read back as the saved copy. Check it by hand.")
    print(f"restored {sorted(files)} from {latest.relative_to(PROJECT_ROOT)}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for cmd in ("preview", "golive"):
        p = sub.add_parser(cmd)
        p.add_argument("--dry-run", action="store_true")
        p.add_argument("--link", default=INTERIM_LINK, help="the showcase button's link")
    sub.add_parser("revert")
    args = ap.parse_args(argv)
    return {"preview": cmd_preview, "golive": cmd_golive, "revert": cmd_revert}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the tests and confirm they pass**

Run: `./.venv.nosync/bin/python tests/test_pen_templates.py`
Expected: `ok`

- [ ] **Step 5: Commit**

```bash
git add scripts/pen_templates.py tests/test_pen_templates.py tests/fixtures/theme
git commit -m "pen_templates.py: preview, golive and revert for the two page layouts

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Preview layouts on the live store

**Files:** none changed. This task runs Task 5's `preview` and checks the result in a browser.

**Interfaces:**
- Consumes: `scripts/pen_templates.py preview`.
- Produces: two live preview-only layouts and a verified preview for Evan.

- [ ] **Step 1: Dry run**

Run: `./.venv.nosync/bin/python scripts/pen_templates.py preview --dry-run`
Expected: `templates/index.pen-preview.json: 11 sections, first ['pp_temple_showcase', 'hero']`, `templates/product.pen-preview.json: 10 sections, first ['main', 'pp_temple_drawing']`, then `DRY RUN`.

- [ ] **Step 2: Write the preview layouts (live, invisible to customers)**

Run: `./.venv.nosync/bin/python scripts/pen_templates.py preview`
Expected: `preview layouts written.`

- [ ] **Step 3: Confirm the homepage honours `?view=` (the spec's open check)**

Open `https://peculiarpeopleco.com/?view=pen-preview` in the Browser pane, which must be visible. Run:
`({ showcase: !!document.querySelector('[data-pp-pen-showcase]'), heading: document.querySelector('.pp-showcase__heading')?.textContent.trim() })`
Expected: `{ showcase: true, heading: "Made to start the conversation" }`.
Then open `https://peculiarpeopleco.com/` without the parameter and confirm `showcase: false`.

If the homepage ignores `?view=` and `showcase` is false with the parameter too, stop. Ask Evan to duplicate the live theme once in Shopify admin (Online Store > Themes > the three dots > Duplicate), then push the preview index layout into that copy as `templates/index.json`, and give him its `?preview_theme_id=` link. Don't change the live `index.json` to work around it.

- [ ] **Step 4: Check the product preview on the four review temples**

For each product address below, open it with `?view=pen-preview`, scroll the band into view, wait 13 s, and read `.pp-band .pp-pen__city`:
- the Salt Lake parent tee (`/products/` + the tee's handle; find it with `ShopifyClient().find_product_by_title("Essential Heavyweight Temple Tee")`). Expected city: `SALT LAKE CITY, UTAH`.
- Logan hoodie. Expected: `LOGAN, UTAH`.
- Washington DC tee. Expected: `KENSINGTON, MARYLAND`.
- Saratoga Springs sweatshirt. Expected: `SARATOGA SPRINGS, UTAH`, on one line at the `mobile` preset.

Also open `/products/temple-art-file?view=pen-preview`. Expected: no `.pp-band` element at all.
For each page, `read_console_messages` with `onlyErrors: true` should return nothing from `pp-pen`.

- [ ] **Step 5: Speed spot check**

On the Logan product page, compare `performance.getEntriesByType('largest-contentful-paint').at(-1).startTime` with and without `?view=pen-preview`, three loads each, at the `mobile` preset. Expected: the preview median is within 150 ms of the plain median. The band loads only near the viewport, so it shouldn't touch the photos. If it's worse, find what `pp-` loads before the band is visible and fix that before the gate.

---

### Task 7: Evan's review gate (stop here)

- [ ] **Step 1: Give Evan the preview addresses and wait**

Send Evan, in plain words, the four product links plus the homepage link, each ending in `?view=pen-preview`, and ask him to check them on his phone and his computer. Remind him customers can't see these. Also show him the screen-reader description, `Line drawings of temples, drawn one after another`, and the fact that the button goes to Temple Tees until the Shop collection is ready.

Don't go on to Task 8 until Evan explicitly says go. If he asks for changes, make them in `theme/`, rerun `web_drawings.py push` and `pen_templates.py preview`, and ask again.

---

### Task 8: Go live, and the Shop collection

**Files:**
- Create: `scripts/shop_collection.py`

**Interfaces:**
- Consumes: `pen_templates.py golive`; `ShopifyClient`.
- Produces: the real layouts updated; the `shop` collection (tags `listing:parent` OR `listing:standalone`); the Temple Art File tagged `listing:standalone`.

- [ ] **Step 1: Go live (only after Evan's go in Task 7)**

Check that nobody has the theme editor open on the live theme. Then:
`./.venv.nosync/bin/python scripts/pen_templates.py golive --dry-run`, then `./.venv.nosync/bin/python scripts/pen_templates.py golive`
Expected: `live layouts saved to artifacts/pen_templates/<stamp>` and `live.`
Open `https://peculiarpeopleco.com/` and one product page without `?view=` and confirm the showcase and band are there. Keep the revert command ready: `./.venv.nosync/bin/python scripts/pen_templates.py revert`.

- [ ] **Step 2: Write the Shop collection script**

Create `scripts/shop_collection.py`:

```python
#!/usr/bin/env python
"""The Shop collection behind the homepage button: one card per garment, plus designs
that are not a single temple's.

  python scripts/shop_collection.py            # dry run: what exists and what would change
  python scripts/shop_collection.py --apply    # create and publish it, tag the art file

Rules (any of): tag listing:parent (the Salt Lake tee, crew and, after the Easify
re-import, hoodie; their Temple dropdown reaches every other temple) or tag
listing:standalone (products with no dropdown: the Temple Art File now, future
non-temple designs later). The two tags stay separate so the planned parents-only All
Temples collection never picks up the art file.
"""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from shopify_client import ShopifyClient  # noqa: E402

HANDLE = "shop"
TITLE = "Shop"
STANDALONE = "listing:standalone"
STANDALONE_PRODUCTS = ["temple-art-file"]
RULES = [{"column": "TAG", "relation": "EQUALS", "condition": "listing:parent"},
         {"column": "TAG", "relation": "EQUALS", "condition": STANDALONE}]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args(argv)
    c = ShopifyClient()

    existing = c.gql("""query($h: String!) { collectionByHandle(handle: $h) { id title
        products(first: 50) { nodes { title } } } }""", {"h": HANDLE})["collectionByHandle"]
    todo_tags = []
    for handle in STANDALONE_PRODUCTS:
        p = c.gql("""query($h: String!) { productByHandle(handle: $h) { id tags } }""",
                  {"h": handle})["productByHandle"]
        if p is None:
            raise SystemExit(f"no product with handle {handle}")
        if STANDALONE not in p["tags"]:
            todo_tags.append((handle, p["id"]))

    print(f"collection {HANDLE}: {'exists' if existing else 'to create'}")
    print(f"tag {STANDALONE} to add on: {[h for h, _ in todo_tags] or 'nothing'}")
    if not args.apply:
        print("\nDRY RUN. Re-run with --apply after Evan's go.")
        return 0

    for handle, gid in todo_tags:
        errs = c.gql("""mutation($id: ID!, $t: [String!]!) { tagsAdd(id: $id, tags: $t) {
            userErrors { message } } }""", {"id": gid, "t": [STANDALONE]})["tagsAdd"]["userErrors"]
        if errs:
            raise SystemExit(f"tagging {handle} failed: {errs}")

    if not existing:
        res = c.gql("""mutation($input: CollectionInput!) { collectionCreate(input: $input) {
            collection { id } userErrors { field message } } }""",
            {"input": {"title": TITLE, "handle": HANDLE,
                       "ruleSet": {"appliedDisjunctively": True, "rules": RULES}}})["collectionCreate"]
        if res["userErrors"]:
            raise SystemExit(f"collectionCreate failed: {res['userErrors']}")
        cid = res["collection"]["id"]
        pubs = c.gql("{ publications(first: 20) { nodes { id name } } }")["publications"]["nodes"]
        store = [p["id"] for p in pubs if p["name"] == "Online Store"]
        try:
            errs = c.gql("""mutation($id: ID!, $p: [PublicationInput!]!) { publishablePublish(id: $id,
                input: $p) { userErrors { message } } }""",
                {"id": cid, "p": [{"publicationId": pid} for pid in store]})["publishablePublish"]["userErrors"]
        except Exception as exc:  # most likely a missing write_publications scope
            errs = [str(exc)]
        if errs or not store:
            print(f"created, but NOT published to the Online Store ({errs or 'no Online Store channel'}).")
            print("Evan: Shopify admin > Products > Collections > Shop > Sales channels > Online Store.")

    after = c.gql("""query($h: String!) { collectionByHandle(handle: $h) {
        products(first: 50) { nodes { title } } } }""", {"h": HANDLE})["collectionByHandle"]
    print("Shop now holds:", [n["title"] for n in after["products"]["nodes"]])
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3: Dry run, then apply after Evan's go**

Run: `./.venv.nosync/bin/python scripts/shop_collection.py`
Expected: `collection shop: to create` and `tag listing:standalone to add on: ['temple-art-file']`.
After Evan says go: `./.venv.nosync/bin/python scripts/shop_collection.py --apply`
Expected: `Shop now holds:` the Salt Lake tee, the Salt Lake sweatshirt and the Temple Art File (in any order). The hoodie arrives after the Easify step in HANDOFF.md.

- [ ] **Step 4: Point the button at Shop (only once the hoodie parent is tagged)**

When `cloud-temple-hoodie` carries `listing:parent`, change the showcase's "Button link" to the Shop collection in the theme editor. Evan can do it in one field, or ask Claude. Until then, leave it on Temple Tees.

- [ ] **Step 5: Commit**

```bash
git add scripts/shop_collection.py
git commit -m "shop_collection.py: one-of-each Shop collection for the homepage button

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Docs, handoff and project sync

**Files:**
- Modify: `README.md` (Tapstitch sequence block, after the `tapstitch_run.py --apply` line)
- Modify: `../.claude/skills/temple-product-generator/SKILL.md` (after the Easify paragraph, near line 112)
- Modify: `docs/decisions.md` (append a dated section)
- Modify: `HANDOFF.md` (top)
- Modify: `../project-sync/pipeline-and-tools.md` ("Current state", "Still open", date)

- [ ] **Step 1: README.** Add to the Tapstitch sequence code block:

```
scripts/web_drawings.py build --temple '<Folder>'  # pen drawing for a newly published temple
scripts/web_drawings.py push                       # upload it; its product band appears
scripts/web_drawings.py check                      # every live temple has a drawing
```

- [ ] **Step 2: SKILL.md.** Add a paragraph: after publishing a new temple, run `scripts/web_drawings.py build --temple '<Folder>'` then `push`, then `check`. Until then that temple's product page simply has no drawing band, and nothing breaks. The homepage list is edited in the theme editor, in the PP temple showcase's "Temples" field.

- [ ] **Step 3: decisions.md.** Add a `## 23 September 2026 (pen-drawn temples on the storefront)` section. Record: why centre lines plus a mask over the finished art (outline tracing looked like a scanner, and dropping thinning scraps left gaps on curves); the gates (1%, 250 KB) and the retry ladder; the naming by `temple:` tag; city line from the manifest; theme assets because the token has `write_themes` but not `write_files`; the 3 s hold and 8.5 s draw; whether `?view=` worked on the homepage (the Task 6 outcome); and the interim Temple Tees link.

- [ ] **Step 4: HANDOFF.md.** At the top: what's live, the revert command, the Shop collection state, and the one open step (switch the button to Shop after the Easify import and hoodie tag).

- [ ] **Step 5: Project sync.** Update `../project-sync/pipeline-and-tools.md`: the new tool and the two theme sections under "Current state", the button switch under "Still open", and today's date. Then push it to the claude.ai Project if a Projects tool is available. If not, tell Evan that `claude/pipeline-and-tools.md` is stale.

- [ ] **Step 6: Run every test once more**

Run:
```bash
for t in tests/test_web_drawing.py tests/test_web_drawings_cli.py tests/test_pen_templates.py; do ./.venv.nosync/bin/python "$t" || exit 1; done
./.venv.nosync/bin/python scripts/web_drawings.py check
```
Expected: `ok` three times, then `with drawings in the theme: 45`.

- [ ] **Step 7: Commit**

```bash
git add README.md docs/decisions.md HANDOFF.md
git commit -m "Docs: pen-drawn temples live, how to add a new temple's drawing

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

The SKILL.md and project-sync files sit outside this repo, in the parent `Claude Projects` folder. Commit them there if that folder is a git repo; otherwise they're saved on disk and that's enough.
