"""Rebuild a temple's pen-drawing stroke file so the website animation draws it the
way a person would.

The theme animation (assets/pp-pen-draw.js) reveals the finished art
(pp-temple-<slug>.webp) through a mask of pen strokes listed in
pp-temple-<slug>.json. The first-generation stroke files were a raw skeleton of
the art: every line was cut into fragments wherever another line touched it,
and the fragments were drawn in an order unrelated to what they depict, so the
drawing looked random and crossings appeared as stubs.

This script rebuilds the strokes from the finished art and orders them the way
Evan specified (1 October 2026):

  1. Outer heavy lines: heavy-weight lines on the building's silhouette.
  2. Inner heavy lines: the other heavy structural edges.
  3. Openings: windows, doors, arches, column shafts. One feature is finished
     before the pen moves to the next.
  4. Small marks: sills, window dividers, doubled trim lines, inner arch lines,
     column caps, doubled "searching" strokes, and anything too small to be a
     line (the statue on the spire, for one).

Rules inside that order:
  - A line is one straight edge (or one smooth curve). The pen lifts at sharp
    corners and never at a crossing: fragments on either side of a crossing
    are joined back into the single line they came from, so a crossing line is
    drawn whole, later, over the first.
  - An overshoot tail is drawn as part of the line it extends.

Evan's rule of 9 October 2026, for every temple: the drawing goes in the order
a person would draw it (the full outline, then the major lines, then the larger
windows and doors, then the fine details), one whole line at a time, never in
fragments. So:
  - Whole lines (heal, continuation, split_corners). Loose pieces are joined
    when their ends point at each other, with each end's direction fitted over
    up to 8 art pixels and read from behind the junction, where a crossing pulls the
    skeleton sideways. What lies across the gap decides: ink all the way is one
    line the skeleton broke at a junction; one short stretch of paper is a pen
    lift inside the line (bridged when nearly straight); paper, ink, paper is a
    different line crossing between two features (stacked windows), which stay
    apart. A corner must turn sharply both close in and further out, so a kink
    at a crossing does not cut a straight line in two.
  - Tiny pieces (absorb_tiny). A piece under 1.5% of the drawing is dropped if
    longer lines already cover its ink, hangs on the end of its parent line if
    it continues from that end, and otherwise is drawn with the small marks.
  - Outline (tier 1, outline_walk). One walk clockwise round the building's
    outer contour from its topmost point; each outline line is drawn where it
    falls along the walk, in the walking direction, so each stroke starts near
    where the last one ended. A short line lying wholly on the silhouette
    belongs to the outline too.
  - Later tiers (facade_zones, sweep). The drawing is split into facades at its
    tall vertical edges. Facade by facade, left to right, the pen works from the
    top down, always to the nearest line or feature among those near the top of
    what is left (rows follow the wall's perspective slope). A feature is
    finished before the next.
  - Every stroke's width covers its line's ink at the 95th percentile of the
    measured width, so a joined line still uncovers the heavier stretches.

The drawing's weight classes come from prompts/temple-sketch-prompt.md: heavy
silhouette and structure, medium overshoot tails, light interior detail.
Weight is measured from the art as the ink's width along each line.

Usage:
  python scripts/pen_strokes.py ART.webp OLD.json OUT.json [--debug DEBUG.png]

OLD.json supplies the art box and the city line, which are kept unchanged.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict

import cv2
import numpy as np
from PIL import Image
from scipy import ndimage as ndi
from skimage.filters import threshold_multiotsu
from skimage.morphology import skeletonize

UP = 3              # supersampling before skeletonizing, for smoother geometry
ALPHA_INK = 110     # alpha above which a pixel is ink
CORNER_DEG = 38     # turn sharper than this lifts the pen
MERGE_DEG = 28      # fragments meeting at a junction this close to straight are one line
JOIN_DEG = 24       # loose pieces whose ends point at each other this closely are one line
JOIN_REACH = 24 * UP  # how far back from an end its direction is read
TINY = 0.015       # pieces shorter than this share of the drawing are not lines on their own
ROW_BAND = 0.04     # depth of the band at the top of a facade the later tiers pick their next line from
ZONE_MIN = 0.05     # narrowest facade (share of the drawing) the later tiers sweep on its own
ABSORB_DEG = 75     # a tiny piece hangs on a parent line's end if it turns no more than this
GAP_MAX = 14 * UP   # widest pen-lift gap (open paper) bridged inside one nearly straight line
INK_GAP_MAX = 30 * UP  # widest inked stretch bridged where the skeleton broke a line up
TIER_NAMES = {1: 'outer heavy', 2: 'inner heavy', 3: 'openings', 4: 'small marks'}

N8 = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]


# ---------------------------------------------------------------- geometry

def plen(pts):
    d = np.diff(pts, axis=0)
    return float(np.hypot(d[:, 0], d[:, 1]).sum()) if len(pts) > 1 else 0.0


def rdp(pts, eps):
    if len(pts) < 3:
        return pts
    a, b = pts[0], pts[-1]
    ab = b - a
    n = math.hypot(*ab)
    if n == 0:
        d = np.hypot(*(pts - a).T)
    else:
        d = np.abs(ab[0] * (pts[:, 1] - a[1]) - ab[1] * (pts[:, 0] - a[0])) / n
    i = int(np.argmax(d))
    if d[i] > eps:
        return np.vstack([rdp(pts[:i + 1], eps)[:-1], rdp(pts[i:], eps)])
    return np.array([a, b])


def direction_from(pts, reach):
    """Unit vector pointing away from pts[0] along the polyline, averaged over `reach` px."""
    acc = 0.0
    p0 = pts[0]
    target = pts[-1]
    for k in range(1, len(pts)):
        acc += math.hypot(*(pts[k] - pts[k - 1]))
        if acc >= reach:
            target = pts[k]
            break
    v = target - p0
    n = math.hypot(*v)
    return v / n if n else np.array([0.0, 0.0])


def angle_between(u, v):
    c = float(np.clip(np.dot(u, v), -1, 1))
    return math.degrees(math.acos(c))


def resample(pts, step):
    L = plen(pts)
    if L == 0:
        return pts[:1]
    seg = np.hypot(*np.diff(pts, axis=0).T)
    cum = np.concatenate([[0], np.cumsum(seg)])
    s = np.linspace(0, L, max(2, int(L / step) + 1))
    x = np.interp(s, cum, pts[:, 0])
    y = np.interp(s, cum, pts[:, 1])
    return np.stack([x, y], 1)



def end_tangent(pts, at_start, th):
    """Unit tangent pointing OUT of the polyline at one end, fitted (least squares)
    over a stretch that skips the end itself: the last few pixels at a junction or
    crossing are pulled sideways by the other line's ink, so a tangent read right at
    the end points the wrong way."""
    d = resample(pts if at_start else pts[::-1], UP)
    n = len(d)
    if n < 3:
        v = d[0] - d[-1]
        nv = math.hypot(*v)
        return v / nv if nv else np.array([0.0, 0.0])
    length = (n - 1) * UP
    i0 = int(min(0.6 * th, 0.25 * length) / UP)
    i1 = int(min(max(0.45 * length, 6 * UP), JOIN_REACH) / UP)
    i1 = min(max(i1, i0 + 2), n - 1)
    seg = d[i0:i1 + 1]
    c = seg - seg.mean(axis=0)
    _, _, vt = np.linalg.svd(c, full_matrices=False)
    u = vt[0]
    if np.dot(u, d[i0] - d[i1]) < 0:
        u = -u
    return u / max(math.hypot(*u), 1e-9)


def continuation(pa, ta, tha, pb, tb, thb, ink=None):
    """Score for joining end a to end b as one line (lower is better), or None.
    Ends join when they point at each other (one smooth line through the gap) and
    the gap is small for its straightness: a hair at any angle under JOIN_DEG, a
    pen-lift gap in the sketch when nearly collinear."""
    th = max(tha, thb)
    gap = math.hypot(*(pb - pa))
    dev = angle_between(ta, -tb)
    if dev > JOIN_DEG:
        return None
    near = max(1.2 * th, 3 * UP)
    if gap <= near:
        return gap / UP + 0.6 * dev
    if gap > max(4.0 * th, INK_GAP_MAX):
        return None
    v = (pb - pa) / gap
    if np.dot(v, ta) <= 0.2 or np.dot(-v, tb) <= 0.2:
        return None
    lat = max(abs(ta[0] * (pb - pa)[1] - ta[1] * (pb - pa)[0]),
              abs(tb[0] * (pa - pb)[1] - tb[1] * (pa - pb)[0]))
    if lat > max(0.75 * th, 2 * UP) + 0.12 * gap:
        return None
    # What lies across the gap decides it. Ink all the way: the line runs on
    # through a junction the skeleton broke up. One stretch of paper: a pen lift
    # inside the line, bridged when short (and, if longer than a hair, nearly
    # straight). Paper, then ink, then paper again: another line crosses open
    # paper between the pieces (a sill or ledge between two stacked windows), so
    # they are different features and stay apart.
    if ink is not None:
        n = max(5, int(gap / UP))
        k = (np.arange(n) + 0.5) / n
        q = pa[None, :] + k[:, None] * (pb - pa)[None, :]
        xi = np.clip(q[:, 0].round().astype(int), 0, ink.shape[1] - 1)
        yi = np.clip(q[:, 1].round().astype(int), 0, ink.shape[0] - 1)
        paper = ~ink[yi, xi]
        runs = int(paper[0]) + int(np.count_nonzero(paper[1:] & ~paper[:-1]))
        if runs > 1:
            return None
        if runs == 1:
            plen_paper = paper.sum() * gap / n
            if plen_paper > max(1.5 * th, GAP_MAX):
                return None
            if plen_paper > near and dev > 12:
                return None
    return gap / UP + 0.6 * dev + lat / UP


def heal(lines, thick_at, shape, ink=None):
    """Skeleton junctions and the sketch itself leave lines in pieces: two
    Y-junctions a few pixels apart, a wobble where a crossing line pulled the
    skeleton sideways, a pen lift mid-line. Join pieces whose ends point at each
    other into the one line they came from (see continuation()), repeatedly, so a
    line broken at several crossings comes back whole. Then drop slivers that only
    retrace a longer line's ink."""
    from scipy.spatial import cKDTree
    segs = [s for s in lines if plen(s) >= 1.5 * UP]
    for _ in range(8):
        th = [float(np.median(thick_at(resample(s, UP)))) for s in segs]
        ends_xy = []
        ends_id = []
        tans = []
        for i, s in enumerate(segs):
            ends_xy += [s[0], s[-1]]
            ends_id += [(i, True), (i, False)]
            tans += [end_tangent(s, True, th[i]), end_tangent(s, False, th[i])]
        tree = cKDTree(np.array(ends_xy))
        lim = max(4.0 * max(th), GAP_MAX)
        cand = []
        for x, y in tree.query_pairs(lim):
            (i, ea), (j, eb) = ends_id[x], ends_id[y]
            if i == j:
                continue
            sc = continuation(ends_xy[x], tans[x], th[i], ends_xy[y], tans[y], th[j], ink)
            if sc is not None:
                cand.append((sc, x, y))
        cand.sort()
        used = set()
        pairs = []
        for _, x, y in cand:
            if x in used or y in used:
                continue
            used.update((x, y))
            pairs.append((x, y))
        if not pairs:
            break
        # union pieces along the chosen end pairs into chains
        link = {}
        for x, y in pairs:
            link[ends_id[x]] = ends_id[y]
            link[ends_id[y]] = ends_id[x]
        seen = set()
        out = []
        for i in range(len(segs)):
            if i in seen:
                continue
            # go to a chain end
            cur, free = i, True   # free = the end we leave from is the start
            hops = 0
            while (cur, free) in link and hops < len(segs):
                j, ej = link[(cur, free)]
                cur, free = j, not ej
                hops += 1
                if cur == i:
                    break
            pts = []
            enter_start = free   # we enter cur at this end
            while cur not in seen:
                seen.add(cur)
                s = segs[cur] if enter_start else segs[cur][::-1]
                pts.append(s)
                leave = (cur, not enter_start)
                if leave not in link:
                    break
                cur, ej = link[leave]
                enter_start = ej
            out.append(np.vstack(pts))
        segs = out
    # slivers: a short line lying along a longer line's ink
    segs.sort(key=plen, reverse=True)
    owner = np.zeros(shape, np.uint8)
    kept = []
    for s in segs:
        d = resample(s, UP)
        t = float(np.median(thick_at(d)))
        xi = np.clip(d[:, 0].round().astype(int), 0, shape[1] - 1)
        yi = np.clip(d[:, 1].round().astype(int), 0, shape[0] - 1)
        if kept and owner[yi, xi].mean() >= 0.85:
            continue
        kept.append(s)
        cv2.polylines(owner, [s.round().astype(np.int32)], False, 1,
                      thickness=max(1, int(t + 3 * UP)))
    return kept


def split_corners(chains):
    """Split chains where the pen would lift: at sharp corners. A corner is a turn
    sharper than CORNER_DEG read both close in (6 px) and further out (16 px), so
    a short kink where a crossing line pulls the skeleton sideways does not cut a
    straight line in two; a real corner turns at both scales."""
    lines = []
    for pts in chains:
        if plen(pts) < 2 * UP:
            continue
        simp = rdp(pts, 1.6 * UP)
        cut = [0]
        for k in range(1, len(simp) - 1):
            turn = 180 - angle_between(direction_from(simp[k::-1], 6 * UP),
                                       direction_from(simp[k:], 6 * UP))
            if turn <= CORNER_DEG:
                continue
            wide = 180 - angle_between(direction_from(simp[k::-1], 16 * UP),
                                       direction_from(simp[k:], 16 * UP))
            if wide > 0.75 * CORNER_DEG:
                cut.append(k)
        cut.append(len(simp) - 1)
        for s, t in zip(cut[:-1], cut[1:]):
            seg = simp[s:t + 1]
            if plen(seg) >= 2 * UP:
                lines.append(seg)
    return lines


def absorb_tiny(lines, thick_at, ink, size):
    """A tiny piece (under TINY of the drawing) is not a line a person draws on
    its own. If the longer lines already cover its ink it is dropped. If it hangs
    off the end of a longer line (a hook, the last bit of a corner, a stub left
    where the skeleton forked) it is drawn as the end of that line. Otherwise it
    stays and is drawn later with the small marks."""
    from scipy.spatial import cKDTree
    tiny_len = TINY * size
    lens = [plen(s) for s in lines]
    big = [s.copy() for s, l in zip(lines, lens) if l >= tiny_len]
    tiny = sorted((s for s, l in zip(lines, lens) if l < tiny_len), key=plen, reverse=True)
    owner = np.zeros(ink.shape, np.uint8)

    def width(s):
        return max(1, int(math.ceil(float(np.percentile(thick_at(resample(s, UP)), 90)) * 1.15 + 2 * UP)))

    for s in big:
        cv2.polylines(owner, [s.round().astype(np.int32)], False, 1, thickness=width(s))
    kept = []
    dropped = absorbed = 0
    for t in tiny:
        w = width(t)
        x0 = max(0, int(t[:, 0].min()) - w); x1 = min(ink.shape[1], int(t[:, 0].max()) + w + 1)
        y0 = max(0, int(t[:, 1].min()) - w); y1 = min(ink.shape[0], int(t[:, 1].max()) + w + 1)
        m = np.zeros((y1 - y0, x1 - x0), np.uint8)
        cv2.polylines(m, [(t - [x0, y0]).round().astype(np.int32)], False, 1, thickness=w)
        mine = (m > 0) & ink[y0:y1, x0:x1]
        unique = int((mine & (owner[y0:y1, x0:x1] == 0)).sum())
        if unique < (1.5 * UP) ** 2:
            dropped += 1
            continue
        th = float(np.median(thick_at(resample(t, UP))))
        touch = max(1.5 * th, 4 * UP)
        best = None
        if big:
            ends_xy = np.array([p for s in big for p in (s[0], s[-1])])
            tree = cKDTree(ends_xy)
            for t_start in (True, False):
                q = t[0] if t_start else t[-1]
                for k in tree.query_ball_point(q, touch):
                    bi, b_start = divmod(k, 2)[0], k % 2 == 0
                    out = end_tangent(big[bi], b_start, th)
                    tt = resample(t if t_start else t[::-1], UP)
                    v = tt[-1] - tt[0]
                    nv = math.hypot(*v)
                    if nv == 0 or angle_between(out, v / nv) > ABSORB_DEG:
                        continue
                    d = math.hypot(*(ends_xy[k] - q))
                    if best is None or d < best[0]:
                        best = (d, bi, b_start, t_start)
        if best is not None:
            _, bi, b_start, t_start = best
            tail = t if t_start else t[::-1]
            big[bi] = np.vstack([tail[::-1], big[bi]]) if b_start else np.vstack([big[bi], tail])
            absorbed += 1
        else:
            kept.append(t)
        cv2.polylines(owner, [t.round().astype(np.int32)], False, 1, thickness=w)
    return big + kept, dropped, absorbed


def outline_walk(items, L, region):
    """Order outline lines as one walk round the building. The building's outer
    contour is traced clockwise from its topmost point (a spire tip); each line is
    placed at where it lies along that contour and drawn in the walking direction,
    so every stroke starts near where the last one ended."""
    from scipy.spatial import cKDTree
    if not items:
        return []
    cs, _ = cv2.findContours(region.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    ring = max(cs, key=cv2.contourArea)[:, 0, :].astype(float)
    x, y = ring[:, 0], ring[:, 1]
    if (x * np.roll(y, -1) - np.roll(x, -1) * y).sum() < 0:   # clockwise on screen
        ring = ring[::-1]
    ring = np.roll(ring, -int(np.argmin(ring[:, 1])), axis=0)
    s = np.concatenate([[0], np.cumsum(np.hypot(*np.diff(ring, axis=0).T))])
    P = s[-1] + math.hypot(*(ring[0] - ring[-1]))
    tree = cKDTree(ring)
    keyed = []
    for i in items:
        d = L[i]['dense']
        sv = s[tree.query(d)[1]]
        ref = sv[len(sv) // 2]
        u = ref + (sv - ref + P / 2) % P - P / 2
        forward = u[-1] >= u[0]
        keyed.append((float(u.min()) % P, float(u.max()), i, not forward))
    keyed.sort()
    return [(i, rev) for _, _, i, rev in keyed]


def facade_zones(L, region, size):
    """Split the drawing into facades at its tall vertical edges (tower corners,
    the corner where two walls meet). Returns the zone bounds in x and each zone's
    perspective slope (how far its horizontal lines fall per unit across), so rows
    of windows that slope with the wall are still read as one row."""
    ys, xs = np.nonzero(region)
    bh = ys.max() - ys.min()
    cand = []
    for ln in L:
        if ln.get('blob') or ln['tier'] not in (1, 2):
            continue
        d = ln['dense']
        if abs(ln['dir'][1]) > 0.93 and np.ptp(d[:, 1]) >= 0.3 * bh:
            cand.append(float(ln['mid'][0]))
    cand.sort()
    clusters = []
    for x in cand:
        if clusters and x - clusters[-1][-1] <= 0.03 * size:
            clusters[-1].append(x)
        else:
            clusters.append([x])
    bounds = []
    last = xs.min()
    for c in clusters:
        x = float(np.mean(c))
        if x - last >= ZONE_MIN * size and xs.max() - x >= ZONE_MIN * size:
            bounds.append(x)
            last = x
    bounds = np.array(bounds)
    slopes = []
    for z in range(len(bounds) + 1):
        sl, wt = [], []
        for ln in L:
            if ln.get('blob') or ln['len'] < 0.03 * size or abs(ln['dir'][0]) < 0.8:
                continue
            if int(np.searchsorted(bounds, ln['mid'][0])) != z:
                continue
            sl.append(ln['dir'][1] / ln['dir'][0])
            wt.append(ln['len'])
        if sl:
            o = np.argsort(sl)
            cw = np.cumsum(np.array(wt)[o])
            slopes.append(float(np.clip(np.array(sl)[o][np.searchsorted(cw, cw[-1] / 2)], -0.6, 0.6)))
        else:
            slopes.append(0.0)
    return bounds, slopes


def sweep(groups, L, zones, size, tier, pen):
    """Calm sweep over groups of lines (a feature, or one line): facades left to
    right; inside a facade, from the top down. The pen moves to the nearest group
    among those near the top of what is left (a band ROW_BAND of the drawing
    deep, measured along the wall's perspective slope), so it works down the
    facade without long jumps and never goes back up to something it passed. A
    vertical line is placed by its top end, anything else by its centre. Yields
    groups in order; pen() gives the current pen position."""
    bounds, slopes = zones
    info = []
    for g in groups:
        pts = np.vstack([L[i]['dense'] for i in g])
        if len(g) == 1 and not L[g[0]].get('blob') and abs(L[g[0]]['dir'][1]) > 0.7:
            d = L[g[0]]['dense']
            anchor = d[0] if d[0][1] < d[-1][1] else d[-1]
        else:
            anchor = (pts.min(axis=0) + pts.max(axis=0)) / 2
        tips = np.array([p for i in g for p in (L[i]['pts'][0], L[i]['pts'][-1])])
        info.append((g, anchor, tips))
    band = ROW_BAND * size
    byzone = defaultdict(list)
    for item in info:
        byzone[int(np.searchsorted(bounds, item[1][0]))].append(item)
    for z in sorted(byzone):
        sl = slopes[z]
        mem = byzone[z]
        x0 = min(a[0] for _, a, _ in mem)
        rest = [(a[1] - sl * (a[0] - x0), g, tips) for g, a, tips in mem]
        rest.sort(key=lambda t: t[0])
        while rest:
            top = rest[0][0]
            p = pen()
            best = None
            for k, (yk, g, tips) in enumerate(rest):
                if yk > top + band:
                    break
                d = float(np.min(np.hypot(*(tips - p).T)))
                if best is None or d < best[0]:
                    best = (d, k)
            _, k = best
            yield rest.pop(k)[1]


def nearest_path(items, start_pt, endpoints):
    """Greedy pen path: always the nearest unvisited item; each may be drawn from
    either end. endpoints(item) -> (p_start, p_end). Returns [(item, reversed)]."""
    out = []
    rest = list(items)
    pos = start_pt
    while rest:
        best = None
        for it in rest:
            a, b = endpoints(it)
            for rev, p in ((False, a), (True, b)):
                d = math.hypot(*(p - pos))
                if best is None or d < best[0]:
                    best = (d, it, rev)
        _, it, rev = best
        rest.remove(it)
        out.append((it, rev))
        a, b = endpoints(it)
        pos = a if rev else b
    return out


# ---------------------------------------------------------------- skeleton graph

def skeleton_graph(skel):
    """Edges of the skeleton as pixel polylines between nodes (ends and junctions).
    Adjacent junction pixels are clustered into one node."""
    ys, xs = np.nonzero(skel)
    on = set(zip(ys.tolist(), xs.tolist()))
    deg = {}
    for p in on:
        deg[p] = sum((p[0] + dy, p[1] + dx) in on for dy, dx in N8)
    nodepix = {p for p, d in deg.items() if d != 2}
    # cluster node pixels
    node_of = {}
    nodes = []
    for p in nodepix:
        if p in node_of:
            continue
        stack = [p]
        node_of[p] = len(nodes)
        members = []
        while stack:
            q = stack.pop()
            members.append(q)
            for dy, dx in N8:
                r = (q[0] + dy, q[1] + dx)
                if r in nodepix and r not in node_of:
                    node_of[r] = len(nodes)
                    stack.append(r)
        nodes.append(np.mean(np.array(members, float), axis=0)[::-1])  # (x, y)
    edges = []  # (node_a, node_b, [(y,x)...])
    seen = set()
    for p in nodepix:
        for dy, dx in N8:
            q = (p[0] + dy, p[1] + dx)
            if q not in on or q in nodepix:
                continue
            if (p, q) in seen:
                continue
            path = [p, q]
            prev, cur = p, q
            while cur not in nodepix:
                nxt = None
                for ddy, ddx in N8:
                    r = (cur[0] + ddy, cur[1] + ddx)
                    if r in on and r != prev and r not in path[-3:]:
                        nxt = r
                        break
                if nxt is None:
                    break
                prev, cur = cur, nxt
                path.append(cur)
            seen.add((path[-1], path[-2]))
            seen.add((p, q))
            a = node_of[p]
            b = node_of.get(path[-1], None)
            if b is None:  # dead end without a node (should not happen)
                continue
            edges.append([a, b, path])
    # pure loops with no node pixels (closed rings, e.g. a round window)
    covered = set(nodepix)
    for e in edges:
        covered.update(e[2])
    rest = on - covered
    while rest:
        p = rest.pop()
        path = [p]
        cur, prev = p, None
        while True:
            nxt = None
            for dy, dx in N8:
                r = (cur[0] + dy, cur[1] + dx)
                if r in rest:
                    nxt = r
                    break
            if nxt is None:
                break
            rest.discard(nxt)
            path.append(nxt)
            cur = nxt
        if len(path) > 4:
            nid = len(nodes)
            nodes.append(np.array(path[0][::-1], float))
            edges.append([nid, nid, path + [path[0]]])
    return nodes, edges


# ---------------------------------------------------------------- main build

def build(art_path, old_json_path, debug_path=None):
    old = json.load(open(old_json_path))
    im = Image.open(art_path).convert('RGBA')
    W, H = im.size
    alpha = np.array(im.resize((W * UP, H * UP), Image.LANCZOS))[:, :, 3]
    ink = alpha > ALPHA_INK
    ink = ndi.binary_opening(ink, iterations=1)
    dist = ndi.distance_transform_edt(ink)
    skel = skeletonize(ink)

    nodes, edges = skeleton_graph(skel)
    nodes = [np.array(n, float) for n in nodes]

    def thick_at(pts):
        xi = np.clip(pts[:, 0].round().astype(int), 0, ink.shape[1] - 1)
        yi = np.clip(pts[:, 1].round().astype(int), 0, ink.shape[0] - 1)
        return 2 * dist[yi, xi]

    # edge polylines in (x, y), oriented a -> b
    E = []
    for a, b, path in edges:
        pts = np.array([(x, y) for y, x in path], float)
        pts[0] = nodes[a]
        pts[-1] = nodes[b]
        E.append({'a': a, 'b': b, 'pts': pts})

    # prune spurs: short edges ending in a free end, born of thick strokes and blobs
    for _ in range(3):
        deg = defaultdict(int)
        for e in E:
            deg[e['a']] += 1
            deg[e['b']] += 1
        keep = []
        for e in E:
            L = plen(e['pts'])
            t = float(np.median(thick_at(e['pts']))) if len(e['pts']) else 1
            free = (deg[e['a']] == 1) != (deg[e['b']] == 1)
            if free and L < max(1.6 * t, 4 * UP):
                continue
            keep.append(e)
        E = keep

    # collapse short bridges between junctions: an X crossing skeletonizes as two
    # Y junctions joined by a short edge
    parent = list(range(len(nodes)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    deg = defaultdict(int)
    for e in E:
        deg[e['a']] += 1
        deg[e['b']] += 1
    for e in E:
        if e['a'] == e['b'] or deg[e['a']] < 3 or deg[e['b']] < 3:
            continue
        L = plen(e['pts'])
        t = float(thick_at(e['pts']).max())
        if L <= max(1.1 * t, 3 * UP):
            e['bridge'] = True
            parent[find(e['a'])] = find(e['b'])
    groups = defaultdict(list)
    for i in range(len(nodes)):
        groups[find(i)].append(i)
    center = {}
    for r, mem in groups.items():
        c = np.mean([nodes[i] for i in mem], axis=0)
        for i in mem:
            center[i] = (r, c)
    E2 = []
    for e in E:
        if e.get('bridge'):
            continue
        ra, ca = center[e['a']]
        rb, cb = center[e['b']]
        pts = e['pts'].copy()
        pts[0] = ca
        pts[-1] = cb
        E2.append({'a': ra, 'b': rb, 'pts': pts})
    E = E2

    # join fragments through junctions: at each node pair the straightest edges
    inc = defaultdict(list)  # node -> [(edge index, end 'a'|'b')]
    for i, e in enumerate(E):
        inc[e['a']].append((i, 'a'))
        inc[e['b']].append((i, 'b'))
    link = {}  # (edge, end) -> (edge, end)
    reach = 14 * UP
    for nd, ends in inc.items():
        if len(ends) < 2:
            continue
        dirs = []
        for i, end in ends:
            pts = E[i]['pts'] if end == 'a' else E[i]['pts'][::-1]
            dirs.append(direction_from(pts, reach))
        cand = []
        for x in range(len(ends)):
            for y in range(x + 1, len(ends)):
                if ends[x][0] == ends[y][0]:
                    continue
                dev = 180 - angle_between(dirs[x], dirs[y])
                if dev <= MERGE_DEG:
                    cand.append((dev, x, y))
        used = set()
        for dev, x, y in sorted(cand):
            if x in used or y in used:
                continue
            used.update((x, y))
            link[ends[x]] = ends[y]
            link[ends[y]] = ends[x]

    # walk chains
    visited = set()
    chains = []
    for i in range(len(E)):
        if i in visited:
            continue
        # walk to one end of the chain
        start, start_end = i, 'a'
        guard = 0
        while (start, start_end) in link and guard < len(E):
            j, je = link[(start, start_end)]
            start, start_end = j, ('b' if je == 'a' else 'a')
            guard += 1
            if start == i:
                break
        # now traverse from start, entering at start_end
        cur, enter = start, start_end
        pts_all = []
        guard = 0
        while cur not in visited and guard <= len(E):
            visited.add(cur)
            pts = E[cur]['pts'] if enter == 'a' else E[cur]['pts'][::-1]
            pts_all.append(pts if not pts_all else pts[1:])
            out = 'b' if enter == 'a' else 'a'
            if (cur, out) not in link:
                break
            cur, enter = link[(cur, out)]
            guard += 1
        chains.append(np.vstack(pts_all))

    lines = split_corners(chains)

    # ------------------------------------------------ heal: join collinear pieces, drop duplicates
    lines = heal(lines, thick_at, ink.shape, ink)

    # ------------------------------------------------ building region: ink closed and filled
    r = max(3, int(0.012 * max(W, H) * UP))
    closed = cv2.morphologyEx(ink.astype(np.uint8), cv2.MORPH_CLOSE,
                              cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1)))
    region = ndi.binary_fill_holes(closed)
    size = max(W, H) * UP

    def inside(x, y):
        xi, yi = int(round(x)), int(round(y))
        if xi < 0 or yi < 0 or xi >= region.shape[1] or yi >= region.shape[0]:
            return False
        return bool(region[yi, xi])

    def side_status(d, th):
        """Per point: 1 outline (paper on one side), 0 interior, -1 out in the paper."""
        tang = np.gradient(d, axis=0) if len(d) > 1 else np.array([[1.0, 0.0]])
        nrm = np.stack([-tang[:, 1], tang[:, 0]], 1)
        nrm /= np.maximum(np.hypot(*nrm.T), 1e-9)[:, None]
        off = th / 2 + 2.5 * UP
        st = np.empty(len(d), int)
        for k, (p, n, o) in enumerate(zip(d, nrm, off)):
            a_in = inside(*(p + n * o))
            b_in = inside(*(p - n * o))
            st[k] = 1 if a_in != b_in else (0 if a_in else -1)
        return st

    # A spire edge and the wall line straight below it are collinear, so they were
    # joined like a line passing through a crossing. Where a line runs along the
    # outline for a stretch and then into the building for a stretch, those are two
    # edges: cut it there.
    run_min = 0.04 * size
    split = []
    for seg in lines:
        d = resample(seg, UP)
        st = side_status(d, thick_at(d))
        lab = st.copy()
        for k in range(1, len(lab)):          # paper stretches take their neighbour's side
            if lab[k] == -1:
                lab[k] = lab[k - 1]
        for k in range(len(lab) - 2, -1, -1):
            if lab[k] == -1:
                lab[k] = lab[k + 1]
        runs = []
        s = 0
        for k in range(1, len(lab) + 1):
            if k == len(lab) or lab[k] != lab[s]:
                runs.append([s, k, lab[s]])
                s = k
        # absorb short runs into the previous one
        merged = []
        for rr in runs:
            if merged and ((rr[1] - rr[0]) * UP < run_min or merged[-1][2] == rr[2]):
                merged[-1][1] = rr[1]
            else:
                merged.append(rr)
        if len(merged) > 1 and (merged[0][1] - merged[0][0]) * UP < run_min:
            merged[1][0] = merged[0][0]
            merged.pop(0)
        if len(merged) <= 1:
            split.append(seg)
            continue
        for s0, s1, _ in merged:
            piece = d[s0:min(s1 + 1, len(d))]
            if len(piece) >= 2:
                split.append(rdp(piece, 1.6 * UP))
    lines = split

    # ------------------------------------------------ tiny pieces: drop or hang on their parent line
    lines, n_drop, n_absorb = absorb_tiny(lines, thick_at, ink, size)

    # ------------------------------------------------ measure each line
    allth = []
    L = []
    for seg in lines:
        dense = resample(seg, UP)
        th = thick_at(dense)
        L.append({'pts': seg, 'dense': dense, 'th': th, 'len': plen(seg)})
        allth.append(th)
    allth = np.concatenate(allth)
    t_light_med, t_med_heavy = threshold_multiotsu(allth[allth > 0], classes=3)

    for ln in L:
        th = ln['th']
        core = th[(np.arange(len(th)) > 2 * UP) & (np.arange(len(th)) < len(th) - 2 * UP)]
        core = core if len(core) >= 3 else th
        ln['weight'] = float(np.median(core))
        ln['heavy_frac'] = float((core >= t_med_heavy).mean())
        ln['w'] = float(np.percentile(th, 95))
        d = ln['dense']
        st = side_status(d, th)
        known = st[st >= 0]
        # a stretch out in the paper is either a tail or a slim spire; it counts as
        # outline only when the line has no inside stretch at all
        ln['sil'] = float((known == 1).mean()) if len(known) else 1.0
        # length running out past the building into open paper: overshoot tails,
        # which the sketch puts only on structural lines
        ln['outside'] = float((st == -1).sum()) * UP
        ln['dir'] = (d[-1] - d[0]) / max(math.hypot(*(d[-1] - d[0])), 1e-9)
        ln['bbox'] = (d[:, 0].min(), d[:, 1].min(), d[:, 0].max(), d[:, 1].max())
        ln['mid'] = d.mean(axis=0)


    # ------------------------------------------------ tiers
    # The art's three weights are not always cleanly separated, so the outline is
    # found by position as well as weight: a line is outer when one side of it is
    # open paper, and it is long or weighty enough to be structure, not a detail.
    for ln in L:
        structural = ln['weight'] >= t_light_med or ln['len'] >= 0.06 * size
        if ln['sil'] >= 0.5 and structural and ln['len'] >= 0.02 * size:
            ln['tier'] = 1
        elif ln['sil'] >= 0.75 and ln['len'] >= TINY * size:
            # a short piece lying wholly on the silhouette: the outline is drawn
            # complete before anything inside it (Evan, 9 October 2026)
            ln['tier'] = 1
        elif ln['heavy_frac'] >= 0.5 and ln['len'] >= 0.02 * size:
            ln['tier'] = 2
        elif ln['outside'] >= 0.02 * size and ln['len'] - ln['outside'] >= 0.02 * size:
            ln['tier'] = 2  # crosses the outline with a tail: a band, ledge or wall edge
        else:
            ln['tier'] = 3

    # doubled lines: a line running parallel and close to a longer one
    def parallel_partner(a, b, gap):
        if angle_between(a['dir'], b['dir']) > 10 and angle_between(a['dir'], -b['dir']) > 10:
            return None
        u = b['dir']
        rel = a['dense'] - b['dense'][0]
        along = rel @ u
        perp = np.abs(rel[:, 0] * u[1] - rel[:, 1] * u[0])
        lo, hi = sorted(((b['dense'][0] - b['dense'][0]) @ u, (b['dense'][-1] - b['dense'][0]) @ u))
        within = (along >= lo) & (along <= hi)
        if within.mean() < 0.6:
            return None
        g = float(np.median(perp[within]))
        if g > gap or g < 1.0 * UP:
            return None
        return g

    light_t = float(np.median(allth[allth < t_light_med])) if (allth < t_light_med).any() else 2 * UP
    heavy_t = float(np.median(allth[allth >= t_med_heavy]))
    for i, a in enumerate(L):
        for j, b in enumerate(L):
            if i == j or b['len'] < a['len']:
                continue
            if b['len'] == a['len'] and j < i:
                continue
            gap = 2.2 * heavy_t if a['tier'] in (1, 2) and b['tier'] in (1, 2) else max(2.2 * light_t, 3 * UP)
            g = parallel_partner(a, b, gap)
            if g is not None:
                a['double_of'] = j
                break

    # light-line features: light lines linked by shared junctions/near touches,
    # ignoring long lines (trim bands, shafts) as links
    light = [i for i, ln in enumerate(L) if ln['tier'] == 3]
    longcut = 0.12 * size
    tree_pts = []
    for i in light:
        if L[i]['len'] <= longcut:
            tree_pts.append((i, L[i]['dense']))
    par = {i: i for i in light}

    def f2(i):
        while par[i] != i:
            par[i] = par[par[i]]
            i = par[i]
        return i

    touch = 1.5 * light_t + 2 * UP
    for x in range(len(tree_pts)):
        i, pi = tree_pts[x]
        bi = L[i]['bbox']
        for y in range(x + 1, len(tree_pts)):
            j, pj = tree_pts[y]
            bj = L[j]['bbox']
            if bi[0] - touch > bj[2] or bj[0] - touch > bi[2] or bi[1] - touch > bj[3] or bj[1] - touch > bi[3]:
                continue
            dmin = np.min(np.hypot(*(pi[::2, None, :] - pj[None, ::2, :]).transpose(2, 0, 1)))
            if dmin <= touch:
                par[f2(i)] = f2(j)
    feat = defaultdict(list)
    for i in light:
        feat[f2(i)].append(i)
    # a group bigger than any one opening has chained through trim lines: it is
    # not a feature, so its lines stand alone
    for fid in list(feat):
        mem = feat[fid]
        bb = [L[i]['bbox'] for i in mem]
        if max(max(b[2] for b in bb) - min(b[0] for b in bb),
               max(b[3] for b in bb) - min(b[1] for b in bb)) > 0.2 * size:
            del feat[fid]
            for i in mem:
                feat[('solo', i)] = [i]
    for fid, mem in feat.items():
        for i in mem:
            L[i]['feat'] = fid

    # a long light line belonging to no opening is structure (a band, ledge or
    # inner wall edge), unless it is one edge of a column shaft: two long
    # verticals standing side by side a column's width apart
    def shaft_partner(i):
        a = L[i]
        if abs(a['dir'][1]) < 0.9:
            return False
        for j, b in enumerate(L):
            if j == i or b['tier'] not in (3,) or abs(b['dir'][1]) < 0.9:
                continue
            if abs(a['mid'][0] - b['mid'][0]) > 0.035 * size:
                continue
            lo = max(a['bbox'][1], b['bbox'][1])
            hi = min(a['bbox'][3], b['bbox'][3])
            if hi - lo >= 0.6 * min(a['bbox'][3] - a['bbox'][1], b['bbox'][3] - b['bbox'][1]):
                return True
        return False

    for fid, mem in list(feat.items()):
        if len(mem) != 1:
            continue
        i = mem[0]
        if L[i]['len'] >= 0.04 * size and not shaft_partner(i):
            L[i]['tier'] = 2
            L[i]['why2'] = 'long solo'
            del feat[fid]
            L[i].pop('feat', None)

    # small marks
    for fid, mem in feat.items():
        if len(mem) == 1:
            ln = L[mem[0]]
            if ln['len'] < 0.03 * size:
                ln['tier'] = 4; ln['why'] = 'short solo'
            continue
        xs = [L[i]['bbox'] for i in mem]
        fx0 = min(b[0] for b in xs); fy0 = min(b[1] for b in xs)
        fx1 = max(b[2] for b in xs); fy1 = max(b[3] for b in xs)
        fc = np.array([(fx0 + fx1) / 2, (fy0 + fy1) / 2])
        for i in mem:
            ln = L[i]
            others = [L[k]['bbox'] for k in mem if k != i]
            ox0 = min(b[0] for b in others); oy0 = min(b[1] for b in others)
            ox1 = max(b[2] for b in others); oy1 = max(b[3] for b in others)
            m = 1.5 * light_t
            b = ln['bbox']
            fdim = max(ox1 - ox0, oy1 - oy0)
            if (b[0] > ox0 + m and b[2] < ox1 - m and b[1] > oy0 + m and b[3] < oy1 - m
                    and ln['len'] < 0.6 * fdim):
                ln['tier'] = 4; ln['why'] = 'divider'  # divider inside the opening
    for i, ln in enumerate(L):
        j = ln.get('double_of')
        if j is None:
            continue
        p = L[j]
        if ln['tier'] in (1, 2) and p['tier'] in (1, 2):
            ln['tier'] = 4; ln['why'] = 'searching'  # searching stroke beside a heavy edge
            continue
        if ln['tier'] != 3:
            continue
        horiz = abs(ln['dir'][0]) > 0.85
        fid = ln.get('feat')
        if fid is not None and fid == p.get('feat') and horiz:
            mem = feat[fid]
            fy1 = max(L[k]['bbox'][3] for k in mem)
            fy0 = min(L[k]['bbox'][1] for k in mem)
            if ln['mid'][1] > (fy0 + fy1) / 2 and p['mid'][1] > (fy0 + fy1) / 2:
                lower, upper = (ln, p) if ln['mid'][1] > p['mid'][1] else (p, ln)
                lower['tier'] = 4; lower['why'] = 'sill'  # sill below the window bottom
                continue
        if fid is not None and fid == p.get('feat'):
            mem = feat[fid]
            c = np.mean([L[k]['mid'] for k in mem], axis=0)
            inner = ln if math.hypot(*(ln['mid'] - c)) < math.hypot(*(p['mid'] - c)) else p
            if inner['tier'] == 3:
                inner['tier'] = 4; inner['why'] = 'inner'  # inner arch line / inner of a doubled pair
            continue
        ln['tier'] = 4; ln['why'] = 'doubled'  # doubled trim line

    # ------------------------------------------------ leftovers: ink no stroke covers
    cover = np.zeros(ink.shape, np.uint8)
    for ln in L:
        cv2.polylines(cover, [ln['pts'].round().astype(np.int32)], False, 1,
                      thickness=max(1, int(math.ceil(ln['w'] * 1.15 + 2 * UP))))
    left = ink & (cover == 0)
    lab, n = ndi.label(left)
    if n:
        sizes = ndi.sum(left, lab, range(1, n + 1))
        for k, sz in enumerate(sizes, 1):
            if sz < (3 * UP) ** 2:
                continue
            comp = lab == k
            ys, xs = np.nonzero(comp)
            # a scribble across the blob, top to bottom, wide enough to cover it
            cdist = ndi.distance_transform_edt(comp)
            w = 2 * float(cdist.max()) + 2 * UP
            order = np.argsort(ys)
            yy = np.linspace(ys.min(), ys.max(), max(2, int((ys.max() - ys.min()) / max(w * 0.6, 1)) + 1))
            pts = []
            for k2, y in enumerate(yy):
                row = xs[np.abs(ys - y) <= w * 0.3]
                if len(row) == 0:
                    continue
                pts.append((row.min(), y) if k2 % 2 == 0 else (row.max(), y))
                pts.append((row.max(), y) if k2 % 2 == 0 else (row.min(), y))
            if len(pts) < 2:
                pts = [(xs.min(), ys.min()), (xs.max(), ys.max())]
            p = np.array(pts, float)
            L.append({'pts': p, 'dense': resample(p, UP), 'len': plen(p), 'w': w,
                      'tier': 4, 'mid': p.mean(axis=0), 'blob': True, 'why': 'blob'})

    # ------------------------------------------------ order
    def ends(i):
        return L[i]['pts'][0], L[i]['pts'][-1]

    ordered = []
    pos = np.array([0.0, 0.0])

    def emit(seq):
        nonlocal pos
        for i, rev in seq:
            ordered.append((i, rev))
            pos = ends(i)[0] if rev else ends(i)[1]

    # tier 1: once round the building, clockwise from the top
    emit(outline_walk([i for i, ln in enumerate(L) if ln['tier'] == 1], L, region))
    # tiers 2-4: facade by facade, left to right; inside a facade, row by row from
    # the top, each row swept from the side the pen is on
    zones = facade_zones(L, region, size)
    for tier in (2, 3, 4):
        if tier == 3:
            fmem = defaultdict(list)
            for i, ln in enumerate(L):
                if ln['tier'] == 3:
                    fmem[ln.get('feat', ('solo', i))].append(i)
            groups = list(fmem.values())
        else:
            groups = [[i] for i, ln in enumerate(L) if ln['tier'] == tier]
        for grp in sweep(groups, L, zones, size, tier, lambda: pos):
            # one feature is finished before the next; inside it the pen goes to
            # the nearest line
            emit(nearest_path(grp, pos, ends))
    # ------------------------------------------------ write
    bx, by, bw, bh = old['box']
    sx = bw / (W * UP)
    sy = bh / (H * UP)

    def to_box(p):
        return np.stack([bx + p[:, 0] * sx, by + p[:, 1] * sy], 1)

    strokes, lens, widths, tiers = [], [], [], []
    for i, rev in ordered:
        ln = L[i]
        p = to_box(ln['pts'][::-1] if rev else ln['pts'])
        strokes.append('M' + ' L'.join(f'{x:.1f} {y:.1f}' for x, y in p))
        lens.append(round(plen(np.round(p, 1)), 1))
        # pen covers the measured ink width plus a small margin, no more, so a line
        # drawn early does not uncover pieces of lines that come later
        widths.append(round((ln['w'] * 1.15 + 1.5 * UP) * sx, 1))
        tiers.append(ln['tier'])
    out = {
        'version': 2,
        'box': old['box'],
        'penWidth': round(float(np.median(widths)), 1),
        'city': old['city'],
        'strokes': strokes,
        'lens': lens,
        'widths': widths,
        'tiers': tiers,
    }

    if debug_path:
        dbg = np.full((H * UP, W * UP, 3), 18, np.uint8)
        dbg[ink] = (60, 60, 60)
        col = {1: (255, 80, 80), 2: (255, 200, 60), 3: (80, 200, 255), 4: (120, 255, 120)}
        for i, rev in ordered:
            ln = L[i]
            cv2.polylines(dbg, [ln['pts'].round().astype(np.int32)], False, col[ln['tier']], thickness=UP)
        Image.fromarray(dbg).resize((W, H), Image.LANCZOS).save(debug_path)
        rng = np.random.default_rng(1)
        dbg = np.full((H * UP, W * UP, 3), 18, np.uint8)
        for i, rev in ordered:
            c = tuple(int(v) for v in rng.integers(70, 256, 3))
            cv2.polylines(dbg, [L[i]['pts'].round().astype(np.int32)], False, c, thickness=2 * UP)
        Image.fromarray(dbg).resize((W, H), Image.LANCZOS).save(debug_path.replace('.png', '-strokes.png'))

    counts = defaultdict(int)
    for t in tiers:
        counts[t] += 1
    return out, dict(counts), (t_light_med / UP, t_med_heavy / UP)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('art')
    ap.add_argument('old_json')
    ap.add_argument('out_json')
    ap.add_argument('--debug')
    a = ap.parse_args()
    out, counts, th = build(a.art, a.old_json, a.debug)
    with open(a.out_json, 'w') as f:
        json.dump(out, f, separators=(',', ':'))
    print(f"{a.out_json}: {len(out['strokes'])} strokes "
          + ', '.join(f'{TIER_NAMES[t]} {counts.get(t, 0)}' for t in (1, 2, 3, 4))
          + f'  (weight cuts {th[0]:.1f}px / {th[1]:.1f}px)')


if __name__ == '__main__':
    main()
