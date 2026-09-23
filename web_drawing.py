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
THICK_PERCENTILE = 97       # ...and at least wide enough for all but the thickest 3% of line
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


def half_widths(mask, skeleton):
    """Half the line width at each skeleton pixel: how many 3x3 erosions it survives."""
    depth = np.zeros(mask.shape, np.int32)
    cur = mask.copy()
    while cur.any():
        depth += cur
        p = np.pad(cur, 1)
        cur = np.logical_and.reduce([p[1 + dy:p.shape[0] - 1 + dy, 1 + dx:p.shape[1] - 1 + dx]
                                     for dy in (-1, 0, 1) for dx in (-1, 0, 1)])
    return depth[skeleton]


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
    # Sized from the average line, the pen leaves a sliver along the thickest lines of
    # temples whose line weight varies (Cody left 2%). Cover those too.
    mean_pen = float(art.sum()) / max(1, int(skeleton.sum())) * PEN_WIDTH_FACTOR
    thick_pen = 2 * float(np.percentile(half_widths(art, skeleton), THICK_PERCENTILE)) + 2
    pen_px = max(mean_pen, thick_pen)

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
    box = [round(float(vb[0] + box_px[0] * scale), 1), round(float(vb[1] + box_px[1] * scale), 1),
           round(float(box_px[2] * scale), 1), round(float(box_px[3] * scale), 1)]

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
