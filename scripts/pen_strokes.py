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
  - Inside a tier the pen moves to the nearest next line (or feature).

The drawing's weight classes come from temple-sketch-prompt.md: heavy
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



def end_dir(pts, at_start, reach):
    """Unit tangent pointing OUT of the polyline at one end."""
    return direction_from(pts if at_start else pts[::-1], reach) * -1


def heal(lines, thick_at, shape):
    """Skeleton junctions still leave lines in pieces: two Y-junctions a few pixels
    apart, a wobble where a crossing line pulled the skeleton sideways. Join pieces
    whose ends nearly meet and point the same way, then drop slivers that only
    retrace a longer line's ink."""
    from scipy.spatial import cKDTree
    reach = 8 * UP
    segs = [s for s in lines if plen(s) >= 1.5 * UP]
    for _ in range(6):
        th = [float(np.median(thick_at(resample(s, UP)))) for s in segs]
        ends_xy = []
        ends_id = []
        for i, s in enumerate(segs):
            ends_xy += [s[0], s[-1]]
            ends_id += [(i, True), (i, False)]
        tree = cKDTree(np.array(ends_xy))
        lim = max(2.2 * max(th), 6 * UP)
        cand = []
        for x, y in tree.query_pairs(lim):
            (i, ea), (j, eb) = ends_id[x], ends_id[y]
            if i == j:
                continue
            pa, pb = ends_xy[x], ends_xy[y]
            gap = math.hypot(*(pb - pa))
            if gap > max(2.2 * max(th[i], th[j]), 6 * UP):
                continue
            da = end_dir(segs[i], ea, reach)
            db = end_dir(segs[j], eb, reach)
            dev = angle_between(da, -db)
            if dev > 16:
                continue
            if gap > 1.5 * UP and angle_between((pb - pa) / gap, da) > 30:
                continue
            cand.append((gap + 0.5 * dev, x, y))
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
    reach = 9 * UP
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

    # split chains at sharp corners
    lines = []
    for pts in chains:
        if plen(pts) < 2 * UP:
            continue
        simp = rdp(pts, 1.6 * UP)
        cut = [0]
        for k in range(1, len(simp) - 1):
            back = direction_from(simp[k::-1], 6 * UP)
            fwd = direction_from(simp[k:], 6 * UP)
            turn = 180 - angle_between(back, fwd)
            if turn > CORNER_DEG:
                cut.append(k)
        cut.append(len(simp) - 1)
        for s, t in zip(cut[:-1], cut[1:]):
            seg = simp[s:t + 1]
            if plen(seg) >= 2 * UP:
                lines.append(seg)

    # ------------------------------------------------ heal: join collinear pieces, drop duplicates
    lines = heal(lines, thick_at, ink.shape)

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
        ln['w'] = float(np.percentile(th, 90))
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

    def ends(i):
        return L[i]['pts'][0], L[i]['pts'][-1]

    ordered = []
    # start where a hand starts an outline: the topmost point of the drawing
    top = min((ln for ln in L if ln['tier'] == 1), key=lambda ln: ln['pts'][:, 1].min(), default=None)
    pos = top['pts'][np.argmin(top['pts'][:, 1])] if top is not None else np.array([0.0, 0.0])
    for tier in (1, 2):
        items = [i for i, ln in enumerate(L) if ln['tier'] == tier]
        for i, rev in nearest_path(items, pos, ends):
            ordered.append((i, rev))
            pos = ends(i)[0] if rev else ends(i)[1]
    # openings: features in nearest order, each finished before the next
    fmem = defaultdict(list)
    for i, ln in enumerate(L):
        if ln['tier'] == 3:
            fmem[ln.get('feat', ('solo', i))].append(i)
    fkeys = list(fmem)

    def fends(k):
        pts = np.vstack([L[i]['pts'] for i in fmem[k]])
        c = pts.mean(axis=0)
        return c, c

    for k, _ in nearest_path(fkeys, pos, fends):
        for i, rev in nearest_path(fmem[k], pos, ends):
            ordered.append((i, rev))
            pos = ends(i)[0] if rev else ends(i)[1]
    items = [i for i, ln in enumerate(L) if ln['tier'] == 4]
    for i, rev in nearest_path(items, pos, ends):
        ordered.append((i, rev))
        pos = ends(i)[0] if rev else ends(i)[1]

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

    import collections
    print('why:', collections.Counter(L[i].get('why', '-') for i, _ in ordered if L[i]['tier'] == 4))
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
