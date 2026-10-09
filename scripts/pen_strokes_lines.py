"""Line-first pen strokes for the temple drawing animation.

The theme animation (assets/pp-pen-draw.js) reveals the finished art through a
mask of pen strokes listed in pp-temple-<slug>.json (version 2: box, penWidth,
city, strokes, lens, widths, tiers). scripts/pen_strokes.py builds that file by
tracing the skeleton of the art. A skeleton breaks every ruled line wherever
another line touches it, so even after joining, the animation read as squiggles
and floating bits. This script builds the same file the other way round: it
finds the ruled lines first, the way the sketch was made, and only then deals
with what is left.

Evan's rule (9 October 2026), for every temple: the drawing goes in the order a
person would draw it, one whole line at a time, never in fragments:
  1. The full outline of the temple.
  2. The major lines.
  3. The larger windows and doors.
  4. The fine details.
Where lines cross, the crossing appears when the later line is drawn whole over
the earlier one. A corner edge and its overshoot tail are one line.

How it works:
  1. Ruled lines (find_lines). Straight segments are found on the thinned ink
     (probabilistic Hough). Each, longest first, is followed along its own
     direction through the ink, across crossings and small pen-lift gaps
     (up to GAP art px), refitted to the ink it runs over, and kept if the ink
     along it is solid and its own centre runs on ink, not over paper. Segments lying on a line already found are the same
     line. Each full line is ONE straight stroke from end to end, at the ink
     width measured along it. The mask only reveals ink, so the stroke passing
     over a gap reveals nothing there.
  2. Classes (classify). The building is the ink closed by 2 art px with holes
     filled. A line is OUTLINE when most of it lies on the building's outer
     contour (roof, spire, parapet and wall edges, and overshoot tails and
     ground lines, which the contour wraps). A line that runs along the
     silhouette at one end and inside the building at the other (a spire edge
     running straight on down a tower) is cut in two there; a tail, with paper
     on both sides, is never cut off its line. Level lines on the roofline
     between the spires (parapets, battlements) are outline; a little under it,
     major. A line is MAJOR when it is long (MAJOR_LEN of the drawing), runs
     between two lines already outline or major (pilasters, courses), or, if
     level, spans most of its facade or of the building's width where it sits
     (cornices, spire ledges and caps). Shorter lines belong to features.
  3. Features. Ink not covered by outline and major strokes is grouped into
     connected pieces, pieces a few pixels apart joined (a window with its
     sill). A feature's straight lines are drawn first, then its curves (traced
     on the skeleton of what is left). Traced pieces on the silhouette join the
     outline walk. Groups of OPENING size or more are OPENINGS, smaller ones
     FINE DETAILS; then (refine_features):
       - round and quatrefoil windows are openings by the size of their box;
       - column shafts standing on the ground in a row of three or more are a
         colonnade, each column its own opening (Evan, 1 October 2026);
       - an upright major line running mostly beside openings (a stack of
         window sides the line follower joined) is cut back into pieces, each
         given to its window;
       - ladders of short level lines (quoins) are fine details, drawn last;
       - upright lines that are not the side of a narrow opening (tower body
         edges, pilasters) are major;
       - small groups inside an opening's box join that opening.
  4. Order. Outline: one walk clockwise round the building from its top, each
     line drawn in the walking direction. Major lines: the longest, which cross
     facades, first; then facade by facade (left to right), upright lines left
     to right, then level ones top down. Openings (a colonnade first, column by
     column), then fine details: facade by facade, top down, in rows that follow
     the wall's perspective slope, rows alternately left to right and right to
     left. Any line not on the outline is drawn top to bottom, or left to right.
  5. Widths and coverage. A straight stroke is as wide as its ink typically is
     plus 1 art px, so it shows its own ink and not its neighbours'. A detail
     stroke whose ink the outline and major strokes already show (a doubled
     line hugging a heavy edge), or half shown with only a crumb left, is
     dropped. Edge specks a stroke misses are
     taken in by widening the nearest opening or detail stroke. Any other ink
     no stroke reaches is traced on its skeleton at its own local width (never
     a round blob) and drawn right after the nearest opening or detail stroke,
     or with the fine details if none is near. A stroke whose centre runs
     mostly over paper is dropped first. No stroke is wider than MAX_WIDTH times
     the median pen: a heavier line becomes one stroke drawn along it and back
     in side-by-side passes.

Usage:
  python scripts/pen_strokes_lines.py ART.webp OLD.json OUT.json [--debug DEBUG.png]

OLD.json supplies the art box and the city line, which are kept unchanged.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from collections import defaultdict

import cv2
import numpy as np
from PIL import Image
from scipy import ndimage as ndi
from skimage.morphology import skeletonize

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pen_strokes import plen, resample, skeleton_graph  # noqa: E402

UP = 2               # work at twice the art's resolution
ALPHA_INK = 110      # alpha above which a pixel is ink
WIDTH_PCT = 50       # a straight stroke covers the ink's typical width across it...
WIDTH_PAD = 1.0      # ...plus this many art px, so it shows only its own ink
TOL = 1.5            # art px: a ruled line's centre stays this close to its ink
GAP = 1.0            # art px: widest gap of paper a line runs on across
MIN_LINE = 8.0       # art px: shortest ruled line
ANGLE_SAME = 1.5     # degrees: segments this close in direction on one line are one line
MAJOR_LEN = 0.20     # share of the drawing: a line this long is major structure
SPAN_LEN = 0.06      # share: a line this long running between structure is major
OUTLINE_NEAR = 3.0   # art px: a line this close to the building's outer contour lies on it
SLIVER = 1.5         # art px: leftover ink this thin along a drawn line is that line's edge
SLIVER_AREA = 10.0   # art px²: and no bigger than this
PAPER_ALPHA = 90      # alpha from which a pixel (grey shading included) is ink for the paper test
WALK_WINDOW = 0.03    # share of the perimeter within which outline lines are taken nearest first
SPLIT_MIN = 6.0     # art px: shortest stretch a line is cut into at the outline
ROOF_DEPTH = 0.07     # share of the drawing: level lines this close under the roofline are outline
ROOF_EDGE = 0.03      # share: this close under the roofline, a level line is outline
LOCAL_SPAN = 0.6      # ...or across this share of the building's width where it sits (a stage, a spire)
ROOF_WINDOW = 0.12    # share: wider than any spire, for finding the roofline under them
FACADE_SPAN = 0.7     # a level line across this share of its facade (or the building there) is structure
ROUND_AREA = 0.15     # a curve group with a box this share of a typical opening's is an opening
COLUMN_MAX = 0.25     # share: a column shaft is no longer than this
RUNG_STEP = 0.02      # share: rungs of a quoin ladder stand at most this far apart
WINDOW_W = 0.08       # share: the widest a single window is
UPRIGHT_MAJOR = 0.1   # share: an upright line this long, clear of any opening, is structure
COLUMN_MIN = 0.008    # share: closer than this, two lines are a doubled stroke, not a shaft
COLUMN_STEP = 0.08    # share: neighbouring columns of a colonnade stand at most this far apart
SIDE_SHARE = 0.75     # an upright runs this much of its length beside windows to be their sides
STAGE_MIN = 0.03      # share: shortest upright that counts as running a whole stage
COLUMN_FOOT = 0.06     # share: a column's foot is at most this far above the building's bottom
COLUMN_GAP = 0.035    # share: the two edges of a column shaft stand at most this far apart
SPECK = 4.0           # art px²: leftover ink smaller than this gets no stroke of its own
ATTACH = 0.03         # share: leftover ink this near an opening or detail stroke joins it
CRUMB = 12.0          # art px²: a half-shown detail stroke with no more than this left unshown is dropped
MAX_WIDTH = 2.4       # no stroke wider than this times the median pen; heavier lines get passes
TWIN = 0.8            # a detail stroke this much shown already by outline and major is dropped
OPENING = 0.025      # share: a feature this big is an opening, smaller is a detail
TIER_NAMES = {1: 'outline', 2: 'major', 3: 'openings', 4: 'fine details'}


# ---------------------------------------------------------------- ruled lines

class Ink:
    def __init__(self, alpha):
        self.ink = alpha > ALPHA_INK
        self.H, self.W = self.ink.shape
        self.skel = skeletonize(self.ink)
        sy, sx = np.nonzero(self.skel)
        self.sk = np.stack([sx, sy], 1).astype(float)

    def at(self, pts):
        xi = np.round(pts[..., 0]).astype(int)
        yi = np.round(pts[..., 1]).astype(int)
        ok = (xi >= 0) & (yi >= 0) & (xi < self.W) & (yi < self.H)
        out = np.zeros(xi.shape, bool)
        out[ok] = self.ink[yi[ok], xi[ok]]
        return out


def line_run(ink, p0, u, t_seed, tol):
    """Follow the line p0 + t*u through the ink both ways from the seed interval.
    Returns (t0, t1, present-samples-in-run) or None."""
    n = np.array([-u[1], u[0]])
    T = math.hypot(ink.W, ink.H)
    t = np.arange(-T, T, 1.0)
    pts = p0[None, :] + t[:, None] * u[None, :]
    inside = (pts[:, 0] >= 0) & (pts[:, 1] >= 0) & (pts[:, 0] < ink.W) & (pts[:, 1] < ink.H)
    t, pts = t[inside], pts[inside]
    if len(t) < 3:
        return None
    offs = np.arange(-math.floor(tol), math.floor(tol) + 1)
    grid = pts[:, None, :] + offs[None, :, None] * n[None, None, :]
    present = ink.at(grid).any(axis=1)
    gap = int(GAP * UP)
    closed = ndi.binary_closing(present, structure=np.ones(gap + 1, bool)) | present
    lab, _ = ndi.label(closed)
    c = int(np.argmin(np.abs(t - (t_seed[0] + t_seed[1]) / 2)))
    if lab[c] == 0:
        return None
    idx = np.flatnonzero(lab == lab[c])
    idx = idx[present[idx]]
    if len(idx) < 2:
        return None
    a, b = idx[0], idx[-1]
    return t[a], t[b], present[a:b + 1]


def fit(ink, p0, u, t0, t1, tol):
    """Refit the line to the skeleton pixels lying along it."""
    rel = ink.sk - p0
    along = rel @ u
    perp = rel @ np.array([-u[1], u[0]])
    m = (along >= t0) & (along <= t1) & (np.abs(perp) <= tol + 1)
    if m.sum() < 5:
        return p0, u, m
    pts = ink.sk[m]
    c = pts.mean(axis=0)
    _, _, vt = np.linalg.svd(pts - c, full_matrices=False)
    v = vt[0] if np.dot(vt[0], u) >= 0 else -vt[0]
    return c, v / np.hypot(*v), m


def measure_width(ink, a, b, band):
    """Ink width along the straight stroke a->b. Per sample, the run of ink across
    the line that contains (or nearly touches) its centre. Rows where that run is
    much wider than the line's usual width are crossings or a neighbour line
    touching, and are left out; over the rest the pen reaches the far edge of the
    ink in the typical row (WIDTH_PCT percentile) plus WIDTH_PAD, and no more, so
    a line shows its own ink and not its neighbours'. Edge specks it misses are
    picked up at the end."""
    L = math.hypot(*(b - a))
    u = (b - a) / max(L, 1e-9)
    n = np.array([-u[1], u[0]])
    t = np.arange(0, L + 1, 1.0)
    offs = np.arange(-band, band + 1)
    grid = a[None, None, :] + t[:, None, None] * u[None, None, :] + offs[None, :, None] * n[None, None, :]
    M = ink.at(grid)
    c = band
    need, ext = [], []
    tol = int(round(TOL * UP))
    for row in M:
        near = np.flatnonzero(row[c - tol:c + tol + 1])
        if len(near) == 0:
            continue
        k = c - tol + near[np.argmin(np.abs(near - tol))]
        lo = k
        while lo > 0 and row[lo - 1]:
            lo -= 1
        hi = k
        while hi < len(row) - 1 and row[hi + 1]:
            hi += 1
        need.append(max(abs(lo - c), abs(hi - c)) + 0.5)
        ext.append(hi - lo + 1)
    if not need:
        return 2.0 * UP
    need, ext = np.array(need), np.array(ext)
    ok = ext <= 1.5 * np.median(ext) + 1
    return 2 * float(np.percentile(need[ok], WIDTH_PCT)) + WIDTH_PAD * UP


def find_lines(ink, size):
    """Full-length ruled lines: [{'a','b','w','u','m'}], a/b the end points."""
    tol = TOL * UP
    hough = cv2.HoughLinesP(ink.skel.astype(np.uint8) * 255, rho=1, theta=np.pi / 360,
                            threshold=int(6 * UP), minLineLength=int(MIN_LINE * UP * 0.75),
                            maxLineGap=int(1.5 * UP))
    segs = [] if hough is None else list(np.asarray(hough, float).reshape(-1, 4))
    segs.sort(key=lambda s: -math.hypot(s[2] - s[0], s[3] - s[1]))
    claimed = np.zeros(len(ink.sk), bool)
    seg_used = np.zeros(len(segs), bool)
    S = np.array(segs) if segs else np.zeros((0, 4))
    lines = []
    for k, s in enumerate(segs):
        if seg_used[k]:
            continue
        a0, b0 = s[:2], s[2:]
        u = (b0 - a0) / max(math.hypot(*(b0 - a0)), 1e-9)
        p0 = (a0 + b0) / 2
        L0 = math.hypot(*(b0 - a0))
        seed = (-L0 / 2, L0 / 2)
        run = None
        for _ in range(3):
            run = line_run(ink, p0, u, seed, tol)
            if run is None:
                break
            t0, t1, _ = run
            p1, u1, _ = fit(ink, p0, u, t0, t1, tol)
            if math.degrees(math.acos(min(1.0, abs(float(np.dot(u1, u)))))) > 3 * ANGLE_SAME:
                break
            # carry the seed interval into the refitted line's coordinates
            seed = tuple(float((p0 + tt * u - p1) @ u1) for tt in seed)
            p0, u = p1, u1
        if run is None:
            seg_used[k] = True
            continue
        run = line_run(ink, p0, u, seed, tol)
        if run is None:
            seg_used[k] = True
            continue
        t0, t1, present = run
        if (t1 - t0) < MIN_LINE * UP or present.mean() < 0.8:
            seg_used[k] = True
            continue
        _, _, m = fit(ink, p0, u, t0, t1, tol)
        if m.sum() < 0.6 * (t1 - t0) or (m.any() and claimed[m].mean() >= 0.6):
            seg_used[k] = True
            continue
        a, b = p0 + t0 * u, p0 + t1 * u
        # the stroke's own centre must run on ink, not beside it over paper
        tt = np.arange(0, t1 - t0 + 1, 1.0)
        centre = ink.at(a[None, :] + tt[:, None] * u[None, :])
        if centre.mean() < 0.6:
            seg_used[k] = True
            continue
        claimed |= m
        # segments lying on this line are this line
        if len(S):
            n = np.array([-u[1], u[0]])
            ea, eb = S[:, :2] - p0, S[:, 2:] - p0
            on = ((np.abs(ea @ n) <= tol + 1) & (np.abs(eb @ n) <= tol + 1)
                  & (ea @ u >= t0 - tol) & (ea @ u <= t1 + tol)
                  & (eb @ u >= t0 - tol) & (eb @ u <= t1 + tol))
            seg_used |= on
        seg_used[k] = True
        lines.append({'a': a, 'b': b, 'u': u, 'len': t1 - t0})
    for ln in lines:
        ln['w'] = measure_width(ink, ln['a'], ln['b'], int(math.ceil(8 * UP)))
    return lines


# ---------------------------------------------------------------- building

def building(ink, W, H):
    """Solid building shape (small close so the paper between pinnacles stays
    out; grows if it leaks) and its core without thin tails."""
    def shape(r):
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))
        return ndi.binary_fill_holes(cv2.morphologyEx(ink.astype(np.uint8), cv2.MORPH_CLOSE, k))
    r_wide = max(3, int(0.012 * max(W, H) * UP))
    wide = shape(r_wide)
    mask = wide
    for r in range(2 * UP, r_wide, 2 * UP):
        m = shape(r)
        if m.sum() >= 0.95 * wide.sum():
            mask = m
            break
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (6 * UP + 1, 6 * UP + 1))
    core = cv2.morphologyEx(mask.astype(np.uint8), cv2.MORPH_OPEN, k) > 0
    return mask, core


def classify(lines, ink, mask, core, size):
    def inside(m, p):
        xi = np.clip(np.round(p[:, 0]).astype(int), 0, m.shape[1] - 1)
        yi = np.clip(np.round(p[:, 1]).astype(int), 0, m.shape[0] - 1)
        return m[yi, xi]

    # distance from the building's outer contour (the contour wraps the tails too)
    cs, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    edge = np.ones(mask.shape, np.uint8)
    cv2.drawContours(edge, [max(cs, key=cv2.contourArea)], -1, 0, 1)
    to_edge = ndi.distance_transform_edt(edge)
    # A spire edge that runs straight on down into the tower is two edges: the
    # outline above and an inner line below. Where a line runs along the
    # silhouette (building on one side, paper on the other) for a good stretch at
    # one end and inside the building for a good stretch at the other, cut it
    # there. An overshoot tail has paper on both sides, so it is neither, and a
    # corner line keeps its tail.
    split = []
    for ln in lines:
        a, u = ln['a'], ln['u']
        t = np.arange(0, ln['len'] + 1, UP)
        p = a[None, :] + t[:, None] * u[None, :]
        xi = np.clip(np.round(p[:, 0]).astype(int), 0, mask.shape[1] - 1)
        yi = np.clip(np.round(p[:, 1]).astype(int), 0, mask.shape[0] - 1)
        n = np.array([-u[1], u[0]])
        d = ln['w'] / 2 + 2.5 * UP
        sa = inside(mask, p + n * d)
        sb = inside(mask, p - n * d)
        on_edge = (sa != sb) & (to_edge[yi, xi] <= ln['w'] / 2 + OUTLINE_NEAR * UP)
        interior = core[yi, xi] & sa & sb
        cut = None
        for k in range(len(t)):
            head, tail = slice(0, k), slice(k, len(t))
            for A, B in ((on_edge, interior), (interior, on_edge)):
                if (k * UP >= SPLIT_MIN * UP and (len(t) - k) * UP >= SPLIT_MIN * UP
                        and A[head].mean() >= 0.75 and B[tail].mean() >= 0.75):
                    cut = t[k]
                    break
            if cut is not None:
                break
        if cut is None:
            split.append(ln)
            continue
        for t0, t1 in ((0, cut), (cut, ln['len'])):
            q = dict(ln)
            q['a'], q['b'], q['len'] = a + t0 * u, a + t1 * u, t1 - t0
            split.append(q)
    lines[:] = split
    for ln in lines:
        a, b, u = ln['a'], ln['b'], ln['u']
        n = np.array([-u[1], u[0]])
        t = np.arange(0, ln['len'] + 1, UP)
        p = a[None, :] + t[:, None] * u[None, :]
        on = ink.at(p[:, None, :] + np.arange(-2, 3)[None, :, None] * n[None, None, :]).any(axis=1)
        p = p[on] if on.any() else p
        xi = np.clip(np.round(p[:, 0]).astype(int), 0, mask.shape[1] - 1)
        yi = np.clip(np.round(p[:, 1]).astype(int), 0, mask.shape[0] - 1)
        near = to_edge[yi, xi] <= ln['w'] / 2 + OUTLINE_NEAR * UP
        ln['near'] = float(near.mean())
        ln['cls'] = 1 if ln['near'] >= 0.6 else 0
    for ln in lines:
        if ln['cls'] == 0 and ln['len'] >= MAJOR_LEN * size:
            ln['cls'] = 2
    # reasonably long lines spanning between structure (pilasters, courses)
    for _ in range(2):
        struct = [l for l in lines if l['cls'] in (1, 2)]
        for ln in lines:
            if ln['cls'] != 0 or ln['len'] < SPAN_LEN * size:
                continue
            hits = 0
            for end in (ln['a'], ln['b']):
                for s in struct:
                    v = s['b'] - s['a']
                    L = math.hypot(*v)
                    tt = np.clip(np.dot(end - s['a'], v) / max(L * L, 1e-9), 0, 1)
                    if math.hypot(*(s['a'] + tt * v - end)) <= s['w'] / 2 + ln['w'] / 2 + 2 * UP:
                        hits += 1
                        break
            if hits == 2:
                ln['cls'] = 2

    # Level lines at the roofline (parapets and battlements between the spires)
    # are part of the outline: within ROOF_DEPTH below the top of the building
    # in their own columns. The building's core has the thin pinnacles opened
    # away, so between spires its top is the parapet.
    cols = core.any(axis=0)
    top = np.where(cols, np.argmax(core, axis=0), core.shape[0])
    # the roofline under the spires: the top's lower envelope over a window wider
    # than a spire, so the spires and pinnacles standing on the roof drop out
    top = ndi.maximum_filter1d(top, size=int(ROOF_WINDOW * size) | 1)
    for ln in lines:
        # an upright rising to the roofline or above it (a tower, turret or
        # pinnacle edge) is not the side of a window
        e = ln['a'] if ln['a'][1] < ln['b'][1] else ln['b']
        xe = int(np.clip(round(e[0]), 0, core.shape[1] - 1))
        ln['high'] = bool(abs(ln['u'][1]) > 0.9 and e[1] <= top[xe] + ROOF_DEPTH * size)
    for ln in lines:
        if ln['cls'] == 1 or abs(ln['u'][0]) < 0.85:
            continue
        t = np.arange(0, ln['len'] + 1, UP)
        p = ln['a'][None, :] + t[:, None] * ln['u'][None, :]
        xi = np.clip(np.round(p[:, 0]).astype(int), 0, core.shape[1] - 1)
        depth = p[:, 1] - top[xi]
        dep = np.median(depth)
        if cols[xi].mean() > 0.8 and ln['len'] >= 0.02 * size and -0.02 * size <= dep <= ROOF_DEPTH * size:
            # on the roofline itself: outline; a little under it: major
            ln['cls'] = 1 if dep <= ROOF_EDGE * size else 2
            ln['roof'] = True

    # A level line spanning most of its facade (a cornice, a string course), or
    # most of the building's width where it sits (a spire ledge or cap, a tower
    # band), is structure whatever its length.
    zones = facade_zones(lines, core, size)
    bounds = zones[0]
    xs = np.nonzero(cols)[0]
    edges = np.concatenate([[xs.min()], bounds, [xs.max()]])
    for ln in lines:
        if ln['cls'] != 0 or abs(ln['u'][0]) < 0.85:
            continue
        x0, x1 = sorted((ln['a'][0], ln['b'][0]))
        mid = (ln['a'] + ln['b']) / 2
        z = int(np.searchsorted(bounds, mid[0]))
        if x1 - x0 >= FACADE_SPAN * (edges[z + 1] - edges[z]):
            ln['cls'] = 2
            continue
        yi = int(np.clip(round(mid[1]), 0, core.shape[0] - 1))
        row = core[yi]
        xm = int(np.clip(round(mid[0]), 0, core.shape[1] - 1))
        if not row[xm]:
            continue
        r0 = xm
        while r0 > 0 and row[r0 - 1]:
            r0 -= 1
        r1 = xm
        while r1 < len(row) - 1 and row[r1 + 1]:
            r1 += 1
        if r1 - r0 >= 4 * UP and x1 - x0 >= LOCAL_SPAN * (r1 - r0):
            ln['cls'] = 2

    # An upright that runs a whole stage, touching structure at both ends with
    # continuous ink (a tower edge between its course and its parapet, a
    # pilaster from base to cornice), is structure too, however short the
    # stage.
    for _ in range(2):
        struct = [l for l in lines if l['cls'] in (1, 2)]
        for ln in lines:
            if ln['cls'] != 0 or abs(ln['u'][1]) < 0.9 or ln['len'] < STAGE_MIN * size:
                continue
            hits = 0
            for end in (ln['a'], ln['b']):
                for s_ in struct:
                    if abs(s_['u'][0]) < 0.7:
                        continue
                    v = s_['b'] - s_['a']
                    L = math.hypot(*v)
                    tt = np.clip(np.dot(end - s_['a'], v) / max(L * L, 1e-9), 0, 1)
                    if math.hypot(*(s_['a'] + tt * v - end)) <= s_['w'] / 2 + ln['w'] / 2 + 2 * UP:
                        hits += 1
                        break
            if hits == 2:
                ln['cls'] = 2
                ln['stage'] = True
    return to_edge


# ---------------------------------------------------------------- drawing helpers

def draw_mask(shape, polys, widths, value=1):
    m = np.zeros(shape, np.uint8)
    for p, w in zip(polys, widths):
        cv2.polylines(m, [np.round(p).astype(np.int32)], False, value,
                      thickness=max(1, int(round(w))))
        if len(p) == 1 or plen(p) < 1:
            cv2.circle(m, tuple(np.round(p[0]).astype(int)), max(1, int(w / 2)), value, -1)
    return m


def orient_reading(p):
    """Draw top to bottom, or left to right."""
    d = p[-1] - p[0]
    if abs(d[1]) >= abs(d[0]):
        return p if d[1] >= 0 else p[::-1]
    return p if d[0] >= 0 else p[::-1]


def curves_from(region_ink, dist):
    """Skeleton polylines of leftover ink (curves of arches, ornaments)."""
    sk = skeletonize(region_ink)
    if not sk.any():
        return []
    nodes, edges = skeleton_graph(sk)
    out = []
    for a, b, path in edges:
        pts = np.array([(x, y) for y, x in path], float)
        out.append(pts)
    # isolated single pixels / tiny blobs
    lab, n = ndi.label(region_ink)
    have = np.zeros(region_ink.shape, bool)
    for p in out:
        xi = p[:, 0].astype(int); yi = p[:, 1].astype(int)
        have[yi, xi] = True
    for k, sl in enumerate(ndi.find_objects(lab), 1):
        comp = lab[sl] == k
        if (have[sl] & comp).any():
            continue
        ys, xs = np.nonzero(comp)
        out.append(np.array([[xs.mean() + sl[1].start, ys.mean() + sl[0].start]]))
    return out


def edge_slivers(left, covered):
    """Leftover ink that is only the edge of a line already drawn: thin (at most
    SLIVER art px through), small (SLIVER_AREA art px) and touching the line's stroke. It is not a mark of
    its own, so no stroke is made for it (a stroke there would be a floating
    crumb)."""
    lab, n = ndi.label(left)
    out = np.zeros(left.shape, bool)
    if not n:
        return out
    touch = ndi.binary_dilation(covered, iterations=2)
    dt = ndi.distance_transform_edt(left)
    for k, sl in enumerate(ndi.find_objects(lab), 1):
        comp = lab[sl] == k
        if (2 * dt[sl][comp].max() <= SLIVER * UP and comp.sum() <= SLIVER_AREA * UP * UP
                and (touch[sl] & comp).any()):
            out[sl] |= comp
    return out


def poly_width(p, dist):
    d = resample(p, 1.0) if len(p) > 1 else p
    xi = np.clip(np.round(d[:, 0]).astype(int), 0, dist.shape[1] - 1)
    yi = np.clip(np.round(d[:, 1]).astype(int), 0, dist.shape[0] - 1)
    return 2 * float(np.percentile(dist[yi, xi], 95)) + 1.5 * UP


def bbox_of(polys):
    pts = np.vstack(polys)
    return (pts[:, 0].min(), pts[:, 1].min(), pts[:, 0].max(), pts[:, 1].max())


def refine_features(allf, lines, size, seg, core):
    """Second look at the features once they exist.

    - Round and quatrefoil windows: a compact group of three or more curves at
      least 2% of the drawing tall, whose box is at least ROUND_AREA of a typical
      opening's box, is an opening, however thin its ink.
    - Column shafts (Evan, 1 October 2026: shafts are openings): upright lines
      in pairs a shaft's width apart, standing on the ground, three or more
      such pairs in a row, are a colonnade; each column becomes its own opening.
    - Window sides: an upright major line that runs mostly beside openings
      (through a stack of windows) is cut back into pieces, and each piece goes
      to the window it bounds.
    - Rungs: short level lines stacked five or more in a ladder (quoins) are fine
      details, drawn last, ladder by ladder.
    - A small group lying inside an opening's box belongs to that opening.
    """
    def refresh(f):
        polys = [seg(l) for l in f['lines']] + [c for c, _ in f['curves']]
        bb = bbox_of(polys)
        f['bbox'] = bb
        f['anchor'] = np.array([(bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2])
        f['area'] = (bb[2] - bb[0]) * (bb[3] - bb[1])

    # round windows
    ops = [f for f in allf.values() if f['tier'] == 3 and len(f['lines']) + len(f['curves']) >= 3]
    typical = float(np.median([f['area'] for f in ops])) if ops else 0.0
    for f in allf.values():
        if f['tier'] != 4 or not f['curves'] or f.get('solo'):
            continue
        bb = f['bbox']
        w, h = bb[2] - bb[0], bb[3] - bb[1]
        if (typical and f['area'] >= ROUND_AREA * typical and max(w, h) <= 3 * max(1.0, min(w, h))
                and max(w, h) >= 0.02 * size and len(f['curves']) + len(f['lines']) >= 3):
            f['tier'] = 3

    # colonnades
    ups = [l for l in lines if l['cls'] in (0, 2) and abs(l['u'][1]) > 0.93
           and SPAN_LEN * size <= l['len'] <= COLUMN_MAX * size]
    def span(l):
        return min(l['a'][1], l['b'][1]), max(l['a'][1], l['b'][1])
    pairs, used = [], set()
    for i, a in enumerate(ups):
        if id(a) in used:
            continue
        best = None
        for b in ups:
            if b is a or id(b) in used:
                continue
            dx = abs((a['a'][0] + a['b'][0]) / 2 - (b['a'][0] + b['b'][0]) / 2)
            if dx > COLUMN_GAP * size or dx < COLUMN_MIN * size:
                continue
            (a0, a1), (b0, b1) = span(a), span(b)
            ov = min(a1, b1) - max(a0, b0)
            if ov < 0.75 * min(a1 - a0, b1 - b0) or not 0.75 <= (a1 - a0) / max(b1 - b0, 1) <= 1.33:
                continue
            if best is None or dx < best[0]:
                best = (dx, b)
        if best:
            # a colonnade stands on the ground: the shaft's foot is near the
            # bottom of the building where it stands (tower stages and belfries
            # with paired uprights are not colonnades)
            x = int(np.clip(round((a['a'][0] + a['b'][0]) / 2), 0, core.shape[1] - 1))
            colm = np.flatnonzero(core[:, x])
            foot = max(span(a)[1], span(best[1])[1])
            if len(colm) and colm.max() - foot <= COLUMN_FOOT * size:
                used.update((id(a), id(best[1])))
                pairs.append((a, best[1]))
    rows = []
    for pr in sorted(pairs, key=lambda pr: min(pr[0]['a'][0], pr[1]['a'][0])):
        top = min(span(pr[0])[0], span(pr[1])[0])
        ln_ = span(pr[0])[1] - span(pr[0])[0]
        cx = (pr[0]['a'][0] + pr[1]['a'][0]) / 2
        for r in rows:
            if (abs(r['top'] - top) <= 0.03 * size and 0.75 <= ln_ / r['len'] <= 1.33
                    and cx - r['x'] <= COLUMN_STEP * size):
                r['x'] = cx
                r['pairs'].append(pr)
                break
        else:
            rows.append({'top': top, 'len': ln_, 'pairs': [pr], 'x': cx})
    for r in rows:
        if len(r['pairs']) < 3:
            continue
        for pr in r['pairs']:
            for l in pr:
                l['column'] = True
                for f in allf.values():
                    f['lines'][:] = [x for x in f['lines'] if x is not l]
                l['cls'] = 0
            f = {'lines': list(pr), 'curves': [], 'tier': 3, 'column': True}
            refresh(f)
            allf[('column', id(pr[0]))] = f
    for k in [k for k, f in allf.items() if not f['lines'] and not f['curves']]:
        del allf[k]

    # window sides merged into one long line through a stack of windows
    boxes = [(k, f['bbox']) for k, f in allf.items()
             if f['tier'] == 3 and not f.get('column') and len(f['lines']) + len(f['curves']) >= 2]
    for l in [l for l in lines if l['cls'] == 2 and abs(l['u'][1]) > 0.9 and not l.get('column')]:
        t = np.arange(0, l['len'] + 1, UP)
        p = l['a'][None, :] + t[:, None] * l['u'][None, :]
        owner = np.full(len(t), -1)
        pad = l['w'] / 2 + 2 * UP
        for j, (k, bb) in enumerate(boxes):
            inb = ((p[:, 0] >= bb[0] - pad) & (p[:, 0] <= bb[2] + pad)
                   & (p[:, 1] >= bb[1]) & (p[:, 1] <= bb[3]))
            owner[inb & (owner < 0)] = j
        if (owner >= 0).mean() < SIDE_SHARE:
            continue
        # runs; short runs outside every box go to the window beside them
        runs, s0 = [], 0
        for i in range(1, len(t) + 1):
            if i == len(t) or owner[i] != owner[s0]:
                runs.append([s0, i - 1, owner[s0]])
                s0 = i
        for i, r in enumerate(runs):
            if r[2] < 0 and (r[1] - r[0]) * UP < SPAN_LEN * size:
                r[2] = runs[i - 1][2] if i > 0 and runs[i - 1][2] >= 0 else (
                    runs[i + 1][2] if i + 1 < len(runs) else -1)
        merged = []
        for r in runs:
            if merged and merged[-1][2] == r[2]:
                merged[-1][1] = r[1]
            else:
                merged.append(list(r))
        l['cls'] = -1   # replaced by its pieces
        for r0, r1, j in merged:
            if (r1 - r0) * UP < 2 * UP:
                continue
            q = dict(l)
            q['a'], q['b'], q['len'] = l['a'] + t[r0] * l['u'], l['a'] + t[r1] * l['u'], t[r1] - t[r0]
            if j < 0:
                q['cls'] = 2
                lines.append(q)
            else:
                q['cls'] = 0
                lines.append(q)
                allf[boxes[j][0]]['lines'].append(q)

    # ladders of rungs (quoins): five or more short level lines stacked about
    # RUNG_STEP apart (a skipped rung allowed), alongside a structural upright
    cand = [(k, l) for k, f in allf.items() if not f.get('column') for l in f['lines']
            if abs(l['u'][0]) > 0.9 and l['len'] < SPAN_LEN * size]
    par = list(range(len(cand)))
    def fnd(i):
        while par[i] != i:
            par[i] = par[par[i]]
            i = par[i]
        return i
    geo = []
    for _, l in cand:
        x0, x1 = sorted((l['a'][0], l['b'][0]))
        geo.append((x0, x1, (l['a'][1] + l['b'][1]) / 2))
    for i in range(len(cand)):
        ax0, ax1, ay = geo[i]
        for j in range(i + 1, len(cand)):
            bx0, bx1, by = geo[j]
            if (0 < abs(ay - by) <= 1.8 * RUNG_STEP * size
                    and min(ax1, bx1) - max(ax0, bx0) >= 0.6 * min(ax1 - ax0, bx1 - bx0)):
                par[fnd(i)] = fnd(j)
    groups = defaultdict(list)
    for i in range(len(cand)):
        groups[fnd(i)].append(i)
    uprights = [l for l in lines if l['cls'] in (1, 2) and abs(l['u'][1]) > 0.9]

    def beside_upright(g):
        # quoins hug a corner: an outline or major upright runs along the
        # ladder's end for most of its height (stair treads and balusters do not)
        x0 = min(geo[i][0] for i in g); x1 = max(geo[i][1] for i in g)
        y0 = min(geo[i][2] for i in g); y1 = max(geo[i][2] for i in g)
        reach = 0.5 * (x1 - x0) + 2 * UP
        for l in uprights:
            lx = (l['a'][0] + l['b'][0]) / 2
            ly0, ly1 = sorted((l['a'][1], l['b'][1]))
            if (x0 - reach <= lx <= x1 + reach
                    and min(y1, ly1) - max(y0, ly0) >= 0.6 * (y1 - y0)):
                return True
        return False

    for g in groups.values():
        ys = np.sort([geo[i][2] for i in g])
        if len(g) < 5 or np.median(np.diff(ys)) > RUNG_STEP * size or not beside_upright(g):
            continue
        for i in g:
            k, l = cand[i]
            f = allf.get(k)
            if f is not None:
                f['lines'][:] = [x for x in f['lines'] if x is not l]
            allf[('rung', id(l))] = {'lines': [l], 'curves': [], 'tier': 4, 'rung': True}
    for k in [k for k, f in allf.items() if not f['lines'] and not f['curves']]:
        del allf[k]
    for f in allf.values():
        refresh(f)

    # Upright lines that are not the side of a narrow opening (tower body edges,
    # pilasters) are structure. A window's side stands at the edge of the rest of
    # its window, which is no wider than WINDOW_W. An upright rising to the
    # roofline or above (tower stage, turret and pinnacle edges) is structure
    # from SPAN_LEN up.
    for k, f in list(allf.items()):
        if f.get('column') or f.get('rung'):
            continue
        for l in list(f['lines']):
            if abs(l['u'][1]) < 0.93 or l['len'] < (SPAN_LEN if l.get('high') else UPRIGHT_MAJOR) * size:
                continue
            x = (l['a'][0] + l['b'][0]) / 2
            y0, y1 = sorted((l['a'][1], l['b'][1]))
            pad = 0.012 * size
            beside = False
            for g in allf.values():
                others = [seg(o) for o in g['lines'] if o is not l] + [c for c, _ in g['curves']]
                if g['tier'] != 3 or g.get('column') or len(others) < 2:
                    continue
                bb = bbox_of(others)
                if (bb[2] - bb[0] <= WINDOW_W * size and bb[0] - pad <= x <= bb[2] + pad
                        and min(y1, bb[3]) - max(y0, bb[1]) > 0.3 * (y1 - y0)):
                    beside = True
                    break
            if not beside or (l.get('high') and l['len'] >= SPAN_LEN * size):
                f['lines'][:] = [x_ for x_ in f['lines'] if x_ is not l]
                l['cls'] = 2
    for k in [k for k, f in allf.items() if not f['lines'] and not f['curves']]:
        del allf[k]
    for f in allf.values():
        refresh(f)

    # pieces of one feature whose boxes overlap (the posts and crosses of a
    # balustrade, the parts of a belfry rail) are one group, drawn together
    changed = True
    while changed:
        changed = False
        keys = [k for k, f in allf.items() if not f.get('column') and not f.get('rung')]
        for i, k1 in enumerate(keys):
            if k1 not in allf:
                continue
            f1 = allf[k1]
            b1 = f1['bbox']
            a1 = max(1.0, (b1[2] - b1[0]) * (b1[3] - b1[1]))
            for k2 in keys[i + 1:]:
                if k2 not in allf:
                    continue
                f2 = allf[k2]
                b2 = f2['bbox']
                a2 = max(1.0, (b2[2] - b2[0]) * (b2[3] - b2[1]))
                ix = max(0.0, min(b1[2], b2[2]) - max(b1[0], b2[0]))
                iy = max(0.0, min(b1[3], b2[3]) - max(b1[1], b2[1]))
                ub = (min(b1[0], b2[0]), min(b1[1], b2[1]), max(b1[2], b2[2]), max(b1[3], b2[3]))
                if (ix * iy >= 0.5 * min(a1, a2)
                        and max(ub[2] - ub[0], ub[3] - ub[1]) <= 0.2 * size):
                    f1['lines'] += f2['lines']
                    f1['curves'] += f2['curves']
                    f1['tier'] = min(f1['tier'], f2['tier'])
                    del allf[k2]
                    refresh(f1)
                    b1 = f1['bbox']
                    a1 = max(1.0, (b1[2] - b1[0]) * (b1[3] - b1[1]))
                    changed = True

    # small groups inside an opening's box join it
    ops = [(k, f) for k, f in allf.items() if f['tier'] == 3]
    for k, f in list(allf.items()):
        if f['tier'] != 4 or f.get('rung') or k not in allf:
            continue
        bb = f['bbox']
        a = max(1.0, (bb[2] - bb[0]) * (bb[3] - bb[1]))
        for k2, g in ops:
            ob = g['bbox']
            ix = max(0.0, min(bb[2], ob[2]) - max(bb[0], ob[0]))
            iy = max(0.0, min(bb[3], ob[3]) - max(bb[1], ob[1]))
            if (ix * iy) / a >= 0.6 or (a <= 1.0 and ob[0] <= bb[0] <= ob[2] and ob[1] <= bb[1] <= ob[3]):
                g['lines'] += f['lines']
                g['curves'] += f['curves']
                del allf[k]
                break
    for f in allf.values():
        refresh(f)


# ---------------------------------------------------------------- order helpers

def outline_walk(items, mask):
    """items: list of (key, polyline). One continuous walk clockwise round the
    building. It starts at the foot of the left side (the lowest point of the
    left-most stretch of contour), goes up the left side, over the roof and
    spires, down the right side and back along the ground, so ground lines and
    base tails come when the walk reaches them, last. Each line is drawn in the
    walking direction. Lines whose place on the contour is close (within
    WALK_WINDOW of the perimeter) are taken nearest first from where the pen is,
    so the pen does not double back along a stretch it has just drawn."""
    from scipy.spatial import cKDTree
    if not items:
        return []
    cs, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    ring = max(cs, key=cv2.contourArea)[:, 0, :].astype(float)
    x, y = ring[:, 0], ring[:, 1]
    if (x * np.roll(y, -1) - np.roll(x, -1) * y).sum() < 0:
        ring = ring[::-1]
    x, y = ring[:, 0], ring[:, 1]
    # foot of the left side: bottom-left-most, on a scale of the building's size
    w_, h_ = max(1.0, np.ptp(x)), max(1.0, np.ptp(y))
    start = int(np.argmin((x - x.min()) / w_ - (y - y.min()) / h_))
    ring = np.roll(ring, -start, axis=0)
    s = np.concatenate([[0], np.cumsum(np.hypot(*np.diff(ring, axis=0).T))])
    P = s[-1] + math.hypot(*(ring[0] - ring[-1]))
    tree = cKDTree(ring)
    keyed = []
    for key, p in items:
        d = resample(p, 2.0) if len(p) > 1 else p
        sv = s[tree.query(d)[1]]
        if np.ptp(sv) > P / 2:
            # the line straddles the start of the walk. Most of it after the
            # start (a wall running on down into its base tail): drawn first.
            # Most of it before (a ground line running out past the corner):
            # drawn last, when the walk comes round to it.
            after = (sv <= P / 2).mean() >= 0.5
            uu = np.where(sv > P / 2, sv - P, sv)
            pp = p if uu[-1] >= uu[0] else p[::-1]
            keyed.append((float(uu.min()) if after else float(uu.min()) + P, key, pp))
            continue
        ref = sv[len(sv) // 2]
        uu = ref + (sv - ref + P / 2) % P - P / 2
        fwd = uu[-1] >= uu[0]
        keyed.append((float(uu.min()) % P, key, p if fwd else p[::-1]))
    keyed.sort(key=lambda k: k[0])
    out = []
    pos = keyed[0][2][0] if keyed else None
    win = WALK_WINDOW * P
    while keyed:
        k0 = keyed[0][0]
        best = None
        for i, (kk, key, p) in enumerate(keyed):
            if kk > k0 + win:
                break
            d = math.hypot(*(p[0] - pos))
            if best is None or d < best[0]:
                best = (d, i)
        _, key, p = keyed.pop(best[1])
        out.append((key, p))
        pos = p[-1]
    return out


def facade_zones(lines, core, size):
    ys, xs = np.nonzero(core)
    bh = ys.max() - ys.min()
    cand = sorted(float((l['a'][0] + l['b'][0]) / 2) for l in lines
                  if l['cls'] in (1, 2) and abs(l['u'][1]) > 0.93 and abs(l['b'][1] - l['a'][1]) >= 0.3 * bh)
    clusters = []
    for x in cand:
        if clusters and x - clusters[-1][-1] <= 0.03 * size:
            clusters[-1].append(x)
        else:
            clusters.append([x])
    bounds, last = [], xs.min()
    for c in clusters:
        x = float(np.mean(c))
        if x - last >= 0.05 * size and xs.max() - x >= 0.05 * size:
            bounds.append(x)
            last = x
    bounds = np.array(bounds)
    slopes = []
    for z in range(len(bounds) + 1):
        sl, wt = [], []
        for l in lines:
            if l['len'] < 0.03 * size or abs(l['u'][0]) < 0.8:
                continue
            if int(np.searchsorted(bounds, (l['a'][0] + l['b'][0]) / 2)) != z:
                continue
            sl.append(l['u'][1] / l['u'][0]); wt.append(l['len'])
        if sl:
            o = np.argsort(sl); cw = np.cumsum(np.array(wt)[o])
            slopes.append(float(np.clip(np.array(sl)[o][np.searchsorted(cw, cw[-1] / 2)], -0.6, 0.6)))
        else:
            slopes.append(0.0)
    return bounds, slopes


def row_sweep(items, zones, band):
    """items: (key, anchor xy). Facades left to right; rows top down along the
    wall's slope; rows swept alternately left to right and right to left."""
    bounds, slopes = zones
    byz = defaultdict(list)
    for key, a in items:
        byz[int(np.searchsorted(bounds, a[0]))].append((key, a))
    out = []
    for z in sorted(byz):
        sl = slopes[z]
        mem = byz[z]
        x0 = min(a[0] for _, a in mem)
        mem.sort(key=lambda t: t[1][1] - sl * (t[1][0] - x0))
        rows = []
        for key, a in mem:
            yk = a[1] - sl * (a[0] - x0)
            if rows and yk - rows[-1][0] <= band:
                rows[-1][1].append((key, a))
            else:
                rows.append([yk, [(key, a)]])
        for r, (_, row) in enumerate(rows):
            # rows alternate direction (left to right, then right to left) so
            # the pen does not travel back across the facade between rows
            row.sort(key=lambda t: t[1][0], reverse=bool(r % 2))
            out += [k for k, _ in row]
    return out


def nearest_order(polys, pos, fixed=True):
    """Nearest-next among polylines; fixed=True keeps each one's direction.
    Returns ([(index, reversed)], pen position after)."""
    rest = list(range(len(polys)))
    out = []
    while rest:
        best = None
        for i in rest:
            p = polys[i]
            for rev in ((False,) if fixed else (False, True)):
                d = math.hypot(*((p[-1] if rev else p[0]) - pos))
                if best is None or d < best[0]:
                    best = (d, i, rev)
        _, i, rev = best
        rest.remove(i)
        out.append((i, rev))
        pos = polys[i][0] if rev else polys[i][-1]
    return out, pos


# ---------------------------------------------------------------- build

def build(art_path, old_json_path, debug_path=None):
    old = json.load(open(old_json_path))
    im = Image.open(art_path).convert('RGBA')
    W, H = im.size
    alpha = np.array(im.resize((W * UP, H * UP), Image.LANCZOS))[:, :, 3]
    ink = Ink(alpha)
    size = max(W, H) * UP
    dist = ndi.distance_transform_edt(ink.ink)

    lines = find_lines(ink, size)
    mask, core = building(ink.ink, W, H)
    to_edge = classify(lines, ink, mask, core, size)

    def seg(l):
        return np.array([l['a'], l['b']])

    structure = [l for l in lines if l['cls'] in (1, 2)]
    cover_struct = draw_mask(ink.ink.shape, [seg(l) for l in structure], [l['w'] for l in structure])
    feat_ink = ink.ink & (cover_struct == 0)

    # ------------------------------------------------ features
    short = [l for l in lines if l['cls'] in (0, 4)]
    cover_short = draw_mask(ink.ink.shape, [seg(l) for l in short], [l['w'] for l in short])
    rest_ink = feat_ink & (cover_short == 0)
    rest_ink &= ~edge_slivers(rest_ink, (cover_struct > 0) | (cover_short > 0))
    curves = [c for c in curves_from(rest_ink, dist)]
    curve_w = [poly_width(c, dist) for c in curves]
    # drop curve bits under 1 art px that only retrace covered ink
    keep = []
    for c, w in zip(curves, curve_w):
        if len(c) > 1 and plen(c) < 1.5 * UP:
            continue
        keep.append((c, w))
    curves = [c for c, _ in keep]
    curve_w = [w for _, w in keep]

    group_src = feat_ink.copy()
    lab, nfeat = ndi.label(ndi.binary_dilation(group_src, iterations=int(2.5 * UP)))

    def label_of(p):
        d = resample(p, 1.0) if len(p) > 1 else p
        xi = np.clip(np.round(d[:, 0]).astype(int), 0, lab.shape[1] - 1)
        yi = np.clip(np.round(d[:, 1]).astype(int), 0, lab.shape[0] - 1)
        v = lab[yi, xi]
        v = v[v > 0]
        return int(np.bincount(v).argmax()) if len(v) else 0

    feats = defaultdict(lambda: {'lines': [], 'curves': []})
    for l in short:
        feats[label_of(seg(l))]['lines'].append(l)
    # traced pieces lying on the silhouette (pinnacle and parapet tops, finials)
    # are part of the outline, drawn in the outline walk
    outline_curves = []
    for c, w in zip(curves, curve_w):
        d = resample(c, 1.0) if len(c) > 1 else c
        xi = np.clip(np.round(d[:, 0]).astype(int), 0, to_edge.shape[1] - 1)
        yi = np.clip(np.round(d[:, 1]).astype(int), 0, to_edge.shape[0] - 1)
        if (len(c) > 1 and plen(c) >= 3 * UP
                and (to_edge[yi, xi] <= w / 2 + OUTLINE_NEAR * UP).mean() >= 0.6):
            outline_curves.append((c, w))
        else:
            feats[label_of(c)]['curves'].append((c, w))

    # a "feature" bigger than any opening has chained through trim: split it into
    # its own connected pieces without the joining distance, then single strokes
    def split_big(fid, f):
        polys = [seg(l) for l in f['lines']] + [c for c, _ in f['curves']]
        pts = np.vstack(polys)
        if max(np.ptp(pts[:, 0]), np.ptp(pts[:, 1])) <= 0.2 * size:
            return {fid: f}
        sub = defaultdict(lambda: {'lines': [], 'curves': []})
        mm = np.zeros(lab.shape, bool)
        for p in polys:
            mm |= draw_mask(lab.shape, [p], [2]).astype(bool)
        l2, _ = ndi.label(mm)
        def lab2(p):
            d = resample(p, 1.0) if len(p) > 1 else p
            xi = np.clip(np.round(d[:, 0]).astype(int), 0, lab.shape[1] - 1)
            yi = np.clip(np.round(d[:, 1]).astype(int), 0, lab.shape[0] - 1)
            v = l2[yi, xi]; v = v[v > 0]
            return int(np.bincount(v).argmax()) if len(v) else 0
        for l in f['lines']:
            sub[(fid, lab2(seg(l)))]['lines'].append(l)
        for c, w in f['curves']:
            sub[(fid, lab2(c))]['curves'].append((c, w))
        out = {}
        for k, g in sub.items():
            pp = np.vstack([seg(l) for l in g['lines']] + [c for c, _ in g['curves']])
            if max(np.ptp(pp[:, 0]), np.ptp(pp[:, 1])) <= 0.2 * size:
                out[k] = g
            else:
                for j, l in enumerate(g['lines']):
                    out[(k, 'l', j)] = {'lines': [l], 'curves': [], 'solo': True}
                for j, cw in enumerate(g['curves']):
                    out[(k, 'c', j)] = {'lines': [], 'curves': [cw], 'solo': True}
        return out

    allf = {}
    for fid, f in list(feats.items()):
        allf.update(split_big(fid, f))

    for f in allf.values():
        pts = np.vstack([seg(l) for l in f['lines']] + [c for c, _ in f['curves']])
        bb = (pts[:, 0].min(), pts[:, 1].min(), pts[:, 0].max(), pts[:, 1].max())
        f['bbox'] = bb
        f['anchor'] = np.array([(bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2])
        dim = max(bb[2] - bb[0], bb[3] - bb[1])
        nstrokes = len(f['lines']) + len(f['curves'])
        f['tier'] = 3 if dim >= OPENING * size else 4
        f['area'] = (bb[2] - bb[0]) * (bb[3] - bb[1])
        if (nstrokes == 1 and f['lines'] and f['lines'][0]['len'] < SPAN_LEN * size
                and abs(f['lines'][0]['u'][1]) < 0.5):
            # one short level line alone (a quoin, a battlement step) is a small
            # mark; an upright one is usually the side of an opening
            f['tier'] = 4
        if f.get('solo'):
            # a stroke from a web of trim (quoins, battlements) too big to be one
            # feature: a long straight one is structure, the rest small marks
            f['tier'] = 4
    for k in [k for k, f in allf.items() if f.get('solo') and f['lines']
              and f['lines'][0]['len'] >= SPAN_LEN * size]:
        allf[k]['lines'][0]['cls'] = 2
        del allf[k]

    refine_features(allf, lines, size, seg, core)

    # ------------------------------------------------ order
    strokes = []   # (polyline, width, tier, is_ruled)
    outl = [(seg(l), l['w'], True) for l in lines if l['cls'] == 1]
    outl += [(c, w, False) for c, w in outline_curves]
    walk = outline_walk([(i, p) for i, (p, _, _) in enumerate(outl)], mask)
    for i, p in walk:
        strokes.append((p, outl[i][1], 1, outl[i][2]))

    zones = facade_zones(lines, core, size)
    major = [l for l in lines if l['cls'] == 2]
    cross = [l for l in major if l['len'] >= 0.3 * size]
    rest = [l for l in major if l['len'] < 0.3 * size]
    def calm(ls):
        """Upright lines left to right, then the others top down."""
        up = sorted((l for l in ls if abs(l['u'][1]) > 0.7), key=lambda l: (l['a'][0] + l['b'][0]) / 2)
        flat = sorted((l for l in ls if abs(l['u'][1]) <= 0.7), key=lambda l: min(l['a'][1], l['b'][1]))
        return up + flat

    for l in calm(cross):
        strokes.append((orient_reading(seg(l)), l['w'], 2, True))
    bounds, _ = zones
    byz = defaultdict(list)
    for l in rest:
        byz[int(np.searchsorted(bounds, (l['a'][0] + l['b'][0]) / 2))].append(l)
    for z in sorted(byz):
        for l in calm(byz[z]):
            strokes.append((orient_reading(seg(l)), l['w'], 2, True))

    pos = strokes[-1][0][-1] if strokes else np.array([0.0, 0.0])
    def feature_order(tier):
        fs = {k: f for k, f in allf.items() if f['tier'] == tier}
        if tier == 3:
            # a colonnade first, column by column, left to right
            cols = sorted((k for k, f in fs.items() if f.get('column')), key=lambda k: fs[k]['anchor'][0])
            rest = {k: f for k, f in fs.items() if not f.get('column')}
            hs = [f['bbox'][3] - f['bbox'][1] for f in rest.values()]
            band = max(0.02 * size, 0.5 * float(np.median(hs))) if hs else 0.02 * size
            return cols + row_sweep([(k, f['anchor']) for k, f in rest.items()], zones, band), fs
        # fine details, then the ladders of rungs last, ladder by ladder
        rest = {k: f for k, f in fs.items() if not f.get('rung')}
        rungs = {k: f for k, f in fs.items() if f.get('rung')}
        order = row_sweep([(k, f['anchor']) for k, f in rest.items()], zones, 0.03 * size)
        order += sorted(rungs, key=lambda k: (round(rungs[k]['anchor'][0] / (0.05 * size)), rungs[k]['anchor'][1]))
        return order, fs

    for tier in (3, 4):
        keys, fs = feature_order(tier)
        for k in keys:
            f = fs[k]
            ls = sorted(f['lines'], key=lambda l: -l['len'])
            polys = [orient_reading(seg(l)) for l in ls]
            seq, pos = nearest_order(polys, pos)
            for i, _ in seq:
                strokes.append((polys[i], ls[i]['w'], tier, True))
            cs = f['curves']
            seq, pos = nearest_order([c for c, _ in cs], pos, fixed=False)
            for i, rev in seq:
                c, w = cs[i]
                strokes.append((c[::-1] if rev else c, w, tier, False))

    # ------------------------------------------------ twins already drawn
    # A detail stroke whose ink the outline and major strokes have already shown
    # (a doubled line hugging a heavy edge) would only appear early and float;
    # it is dropped, and anything it alone covered is caught below.
    cover12 = draw_mask(ink.ink.shape, [s_[0] for s_ in strokes if s_[2] <= 2],
                        [s_[1] for s_ in strokes if s_[2] <= 2]) > 0
    kept = []
    for st in strokes:
        if st[2] >= 3:
            m = draw_mask(ink.ink.shape, [st[0]], [st[1]]) > 0
            mine = m & ink.ink
            shown = (mine & cover12).sum() / max(1, mine.sum())
            unshown = int((mine & ~cover12).sum())
            if mine.sum() and (shown >= TWIN or (shown >= 0.5 and unshown <= CRUMB * UP * UP)):
                continue
        kept.append(st)
    strokes = kept

    # A stroke whose centre runs mostly over paper (a piece cut off a line where
    # it crosses a gap) reveals nothing of its own; it is dropped and any ink it
    # alone reached is picked up below.
    # ink as the art's own pixels see it (nearest, not resampled), and as the
    # resampled working copy sees it: a centre must be on both
    # (grey shading counts as ink here from alpha PAPER_ALPHA up)
    art_ink = np.kron((np.array(im)[:, :, 3] >= PAPER_ALPHA).astype(np.uint8),
                      np.ones((UP, UP), np.uint8)).astype(bool)
    near_ink = (alpha >= PAPER_ALPHA) & art_ink
    kept = []
    for st in strokes:
        p = st[0]
        if len(p) >= 2 and plen(p) >= 2:
            d = resample(p, 1.0)
            if near_ink[np.clip(np.round(d[:, 1]).astype(int), 0, ink.H - 1),
                        np.clip(np.round(d[:, 0]).astype(int), 0, ink.W - 1)].mean() < 0.5:
                continue
        kept.append(st)
    strokes = kept

    # Specks of a line's edge the pen just misses: if the nearest stroke is an
    # opening or detail stroke (drawn late anyway), its pen is widened a little
    # to take them in; otherwise they are drawn as a fine detail below.
    strokes = [list(st) for st in strokes]
    cov = draw_mask(ink.ink.shape, [s_[0] for s_ in strokes], [s_[1] for s_ in strokes])
    left = ink.ink & (cov == 0)
    if left.any():
        ids = np.zeros(ink.ink.shape, np.int32)
        for i, st in enumerate(strokes):
            cv2.polylines(ids, [np.round(st[0]).astype(np.int32)], False, i + 1, 1)
        dd, idx = ndi.distance_transform_edt(ids == 0, return_indices=True)
        near = ids[idx[0], idx[1]] - 1
        for i in np.unique(near[left]):
            if strokes[i][2] < 3:
                continue
            need = 2 * float(dd[left & (near == i)].max()) + 1.0 * UP
            if need <= strokes[i][1] + 2 * SLIVER * UP:
                strokes[i][1] = max(strokes[i][1], need)
    strokes = [tuple(st) for st in strokes]
    cov = draw_mask(ink.ink.shape, [s_[0] for s_ in strokes], [s_[1] for s_ in strokes])
    left = ink.ink & (cov == 0)
    lab3, n3 = ndi.label(left)
    extra = 0
    if n3:
        # Ink still uncovered is traced (skeleton, at its own local width, never
        # a fat blob) and drawn right after the nearest opening or detail
        # stroke, so it belongs to that feature; failing one nearby, it is a fine
        # detail at the end.
        ids = np.zeros(ink.ink.shape, np.int32)
        ids_all = np.zeros(ink.ink.shape, np.int32)
        for i, st in enumerate(strokes):
            cv2.polylines(ids_all, [np.round(st[0]).astype(np.int32)], False, i + 1, 1)
            if st[2] >= 3:
                cv2.polylines(ids, [np.round(st[0]).astype(np.int32)], False, i + 1, 1)
        if ids.any():
            dd, idx = ndi.distance_transform_edt(ids == 0, return_indices=True)
        idx_all = ndi.distance_transform_edt(ids_all == 0, return_distances=False, return_indices=True)
        after = defaultdict(list)
        tail = []
        for k, sl in enumerate(ndi.find_objects(lab3), 1):
            comp = lab3[sl] == k
            if comp.sum() < SPECK * UP * UP:
                # a speck is part of the line it sits on: a dab drawn right after
                # the nearest stroke, in that stroke's tier
                ys, xs = np.nonzero(comp)
                ys = ys + sl[0].start; xs = xs + sl[1].start
                cy, cx = int(round(ys.mean())), int(round(xs.mean()))
                j = int(ids_all[idx_all[0][cy, cx], idx_all[1][cy, cx]]) - 1
                if j >= 0:
                    r = max(math.hypot(y_ - cy, x_ - cx) for y_, x_ in zip(ys, xs))
                    dab = np.array([[cx - 0.5, cy], [cx + 0.5, cy]], float)
                    after[j].append((dab, 2 * r + 1.0 * UP, strokes[j][2], False))
                continue
            region = np.zeros(ink.ink.shape, bool)
            region[sl] = comp
            pieces = curves_from(region, dist)
            dt_r = ndi.distance_transform_edt(comp)
            for c in pieces:
                w = min(poly_width(c, dist), 2 * float(dt_r.max()) + 1.5 * UP)
                c = orient_reading(c) if len(c) == 2 else c
                ys, xs = np.nonzero(comp)
                y, x = int(ys[0] + sl[0].start), int(xs[0] + sl[1].start)
                if ids.any() and dd[y, x] <= ATTACH * size:
                    j = int(ids[idx[0][y, x], idx[1][y, x]]) - 1
                    after[j].append((c, w, strokes[j][2], False))
                else:
                    tail.append((c, w, 4, False))
                extra += 1
        merged = []
        for i, st in enumerate(strokes):
            merged.append(st)
            merged += after.get(i, [])
        strokes = merged + tail

    # ------------------------------------------------ heavy strokes: several passes
    # No stroke is wider than MAX_WIDTH times the typical pen. A heavier line is
    # drawn as one stroke that goes along it and back, side by side, the way a
    # hand thickens a heavy line, so it still covers its ink and still draws as
    # one line.
    cap = MAX_WIDTH * float(np.median([st[1] for st in strokes]))
    out = []
    for st in strokes:
        p, w = st[0], st[1]
        if w <= cap or len(p) < 2 or plen(p) < 1:
            out.append(st if w <= cap or len(p) >= 2 else (p, cap) + tuple(st[2:]))
            continue
        k = int(math.ceil((w - cap) / (0.8 * cap))) + 1
        offs = np.linspace(-(w - cap) / 2, (w - cap) / 2, k)
        d = np.gradient(p, axis=0)
        nrm = np.stack([-d[:, 1], d[:, 0]], 1)
        nrm /= np.maximum(np.hypot(*nrm.T), 1e-9)[:, None]
        path = []
        for o in offs:
            q = p + nrm * o
            dq = resample(q, 1.0)
            if near_ink[np.clip(np.round(dq[:, 1]).astype(int), 0, ink.H - 1),
                        np.clip(np.round(dq[:, 0]).astype(int), 0, ink.W - 1)].mean() < 0.5:
                continue   # a pass that would run beside the ink
            path.append(q if len(path) % 2 == 0 else q[::-1])
        if not path:
            path = [p]
        out.append((np.vstack(path), cap) + tuple(st[2:]))
    strokes = out

    # ------------------------------------------------ write
    bx, by, bw, bh = old['box']
    sx = bw / (W * UP)
    sy = bh / (H * UP)
    out_strokes, lens, widths, tiers = [], [], [], []
    for p, w, t, _ in strokes:
        q = np.stack([bx + p[:, 0] * sx, by + p[:, 1] * sy], 1)
        if len(q) == 1:
            q = np.vstack([q, q + [0.1, 0]])
        out_strokes.append('M' + ' L'.join(f'{x:.1f} {y:.1f}' for x, y in q))
        lens.append(max(0.1, round(plen(np.round(q, 1)), 1)))
        widths.append(round(w * sx, 1))
        tiers.append(t)
    out = {
        'version': 2,
        'box': old['box'],
        'penWidth': round(float(np.median(widths)), 1),
        'city': old['city'],
        'strokes': out_strokes,
        'lens': lens,
        'widths': widths,
        'tiers': tiers,
    }
    if debug_path:
        dbg = np.full(ink.ink.shape + (3,), 14, np.uint8)
        dbg[ink.ink] = (55, 55, 55)
        col = {1: (255, 70, 70), 2: (255, 200, 50), 3: (70, 190, 255), 4: (110, 240, 110)}
        for p, w, t, ruled in strokes:
            cv2.polylines(dbg, [np.round(p).astype(np.int32)], False, col[t],
                          thickness=(3 * UP if ruled and t in (1, 2) else UP))
        Image.fromarray(dbg).resize((W, H), Image.LANCZOS).save(debug_path)
    counts = defaultdict(int)
    for t in tiers:
        counts[t] += 1
    return out, dict(counts), {'lines': len(lines), 'extra': extra}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('art')
    ap.add_argument('old_json')
    ap.add_argument('out_json')
    ap.add_argument('--debug')
    a = ap.parse_args()
    out, counts, info = build(a.art, a.old_json, a.debug)
    with open(a.out_json, 'w') as f:
        json.dump(out, f, separators=(',', ':'))
    print(f"{a.out_json}: {len(out['strokes'])} strokes "
          + ', '.join(f'{TIER_NAMES[t]} {counts.get(t, 0)}' for t in (1, 2, 3, 4))
          + f"  ({info['lines']} ruled lines, {info['extra']} coverage patches)")


if __name__ == '__main__':
    main()
