"""On-model photos for the map products: place each product's real print on the
Higgsfield model photos and fold it into the fabric.

  python composite_maps.py fetch             # fresh checkout: base photos + prints, hash-checked
  python composite_maps.py build [prefix]    # finals for every place in prints/, from the lock
  python composite_maps.py check <place>     # a new city's prints fit the lock, before building
  python composite_maps.py detect            # re-measure landmarks (only to change the lock)
  python composite_maps.py lock [--force]    # freeze placement from landmarks + rules below

LOCKED, 9 Oct 2026 (Evan approved every tee, sweatshirt and hoodie, front and
back, and asked for the placement to be anchored for all future map products).
placement_lock.json holds, per base photo, the exact print canvas quad on the
photo, the hood edge and fold scale, and per garment and view the print canvas
size and Tapstitch placement the quads were measured for. build reads only the
lock: the rules and landmarks below are how it was made, not what build uses.
A new city whose Tapstitch template places its print the same way (check
confirms it) gets its canvas laid on the same quads, so its map lands exactly
where Nauvoo's and Salt Lake City's do. See LOCK.md.

PLACEMENT comes from Tapstitch's own flat lays of the live map products
(flats/, 1400px). On a flat the print's ink box sits a known distance below the
collar and a known distance off the centre line, and it is a known width. Every
one of those is carried to a photo in proportion to the garment's collar-to-hem
length, the same fabric on the flat and on the body, so the print shows at its
true printed size (the temple pipeline sizes by length for the same reason,
photo-mockup-spike/print_geometry.json).

  s       = (photo hem - photo collar) / (flat hem - flat collar)
  ink w   = flat ink w * s
  ink top = photo collar y + (flat ink top - flat collar y) * s
  ink cx  = photo collar x + (flat ink cx - flat collar x) * s

A garment wraps the body, so at true size the map covers more of the visible
back than on a flat lay. On 9 Oct 2026 Evan tried the flat lay's share of the
chest width (onmodel-v2's method; the chest landmarks below) and a step up from
it, then went back to true size: what had looked too big was the heavy fold.

COLLAR, per view and the same on flat and photo: tee and crew, the top edge of the
neck rib at centre; hoodie front, the V where the hood's two sides cross; hoodie
back, the neckline where the hood's outer edges meet the shoulders (on a flat the
hood stands up, on a person it lies down, so the hood itself cannot be the mark).
On the hoodie back the print is kept clear of the hood's point, which a real
person's hood would cover.

FOLD is a quarter of the temple line's: displace 0.75, fold strength 55, band
4-20, shade gain 1.8, texture 0.35, opacity 0.93. The full temple fold (displace
3, strength 220) visibly bent the map frame and streets; Evan, 9 Oct 2026: "too
wavy", chose a gentle bend with the light and shade kept. The temple values were
tuned on 2048px photos whose garment ran about 1170px collar to
hem, so every pixel quantity scales by k = this garment's collar-to-hem / 1170
(fold strength by k squared: the fold gradient is per pixel).
"""

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "photo-mockup-spike"))
import composite  # noqa: E402
from composite import build as fold_build, load_art  # noqa: E402


def _cv_gauss(a, sigma):
    """composite.gauss, by OpenCV: the same separable gaussian, fast enough at 5000px."""
    import cv2
    return cv2.GaussianBlur(np.asarray(a, np.float32), (0, 0), float(sigma)).astype(np.float64)


composite.gauss = _cv_gauss

LOCK = HERE / "placement_lock.json"
VIEWS = [(g, v) for g in ("tee", "crew", "hoodie") for v in ("front", "back")]
# What a print's Tapstitch placement must equal for the lock to hold (prints.json).
PLACEMENT_KEYS = ("piece", "scaleX", "scaleY", "top", "left", "width", "height", "angle")


def places():
    """Every city with a full set of six print files in prints/."""
    names = {p.stem.rsplit("_", 2)[0] for p in (HERE / "prints").glob("*_*_*.png")}
    return sorted(n for n in names
                  if all((HERE / "prints" / f"{n}_{g}_{v}.png").exists() for g, v in VIEWS))


PLACES = places()
OUT_PX = 5000
REF_SPAN = 1170.0
FOLD = dict(displace=0.75, shade_gain=1.8, texture=0.35, opacity=0.93, strength=55.0, band=(4, 20))
LEAD = {"tee": "maroon", "crew": "black", "hoodie": "navy-blue"}

# Evan, 9 Oct 2026, after the true-size build: every back print 10% smaller (top
# edge held, so it shrinks from the bottom), every front logo 1 inch higher, the
# hoodie's logo also 10% smaller, and the hoodie map higher, with the hood lying
# over its very top (hood_edge below). Prints centre on the photo's own measured
# centre line (centre_x), which on the hoodie is the middle of the hood.
# Then, after the hood fix: every front logo another 5% smaller and 1.5in higher.
SCALE = {("tee", "back"): 0.90, ("crew", "back"): 0.90, ("hoodie", "back"): 0.90,
         ("tee", "front"): 0.95, ("crew", "front"): 0.95, ("hoodie", "front"): 0.90 * 0.95}
# Evan, then: the hoodie's chest logo a little lower, twice (0.75in each, from 2.5).
RAISE_IN = {("tee", "front"): 2.5, ("crew", "front"): 2.5, ("hoodie", "front"): 1.0}
LOGO_IN = 6.0          # front logo's true ink width, the inch ruler on each flat
# The map's top sits this share of its height above the hood's tip, so the hood
# hides a small notch of it (Evan, 9 Oct 2026: keep it small).
HOOD_COVER = 0.03
# Below the hood's edge the print is held flat for this many px (2880 scale),
# blending into the gentle fold: the hood's cast shadow is the hood lying on the
# print, not a crease in it, and folding to it bent the frame line at the tip.
HOOD_FLAT_BAND = 80
# Measured by hand on each hoodie-back photo (2880px), the hood's tip at centre
# back: registration carried it within ~40px, too loose for a 3% overlap.
HOOD_TIP = {"black": 15, "coffee": 15, "eden-green": 15, "gray": 30, "mauve": 25,
            "navy-blue": 15, "royal-blue": 5}          # x right of centre_x
HOOD_TIP_Y = {"black": 1095, "coffee": 1125, "eden-green": 1110, "gray": 1105,
              "mauve": 1095, "navy-blue": 1092, "royal-blue": 1095}

# Hand marks on each lead base photo (2880px): collar point, hem y at centre, and
# the chest: left and right x where the sleeve meets the body, at chest_y.
BASE_LM = {
    ("tee", "front"): {"collar": [1437, 900], "hem": 2625, "chest": [907, 1925], "chest_y": 1775},
    ("tee", "back"): {"collar": [1437, 730], "hem": 2620, "chest": [917, 1930], "chest_y": 1740},
    # Sweatshirt refitted 9 Oct 2026 to Tapstitch's own loose, long fit (Evan's
    # reference photo, refs/crew_fit_tapstitch.jpg); the boxy first bases are in gen/boxy/.
    ("crew", "front"): {"collar": [1412, 800], "hem": 2532, "chest": [900, 1925], "chest_y": 1500},
    ("crew", "back"): {"collar": [1412, 675], "hem": 2537, "chest": [912, 1925], "chest_y": 1500},
    ("hoodie", "front"): {"collar": [1437, 895], "hem": 2520, "chest": [975, 1875], "chest_y": 1700},
    ("hoodie", "back"): {"collar": [1437, 800], "hem": 2520, "chest": [962, 1900], "chest_y": 1700,
                         "hood_point": 1095},
}
# The same marks on Tapstitch's flats (1400px). Front collars are onmodel-v2's.
FLAT_LM = {
    ("tee", "front"): {"collar": [693, 226], "hem": 1213, "chest": [290, 1082]},
    ("tee", "back"): {"collar": [690, 224], "hem": 1212, "chest": [290, 1082]},
    ("crew", "front"): {"collar": [699, 288], "hem": 1081, "chest": [382, 1018]},
    ("crew", "back"): {"collar": [700, 307], "hem": 1105, "chest": [382, 1018]},
    ("hoodie", "front"): {"collar": [700, 525], "hem": 1219, "chest": [355, 1045]},
    ("hoodie", "back"): {"collar": [700, 440], "hem": 1219, "chest": [355, 1045]},
}


def parse(name):
    g, v, c = name.split("_", 2)
    return g, v, c


def register(base, img):
    """Affine map from the base photo onto a colourway (ECC on edge maps at 1024px).
    A colourway is one generation from its base with a slight change of pose and
    framing, so its landmarks move with the torso."""
    import cv2

    def edge(p):
        g = np.asarray(Image.open(p).convert("L").resize((1024, 1024), Image.LANCZOS), np.float32)
        g = cv2.GaussianBlur(g, (0, 0), 2)
        e = np.hypot(cv2.Sobel(g, cv2.CV_32F, 1, 0), cv2.Sobel(g, cv2.CV_32F, 0, 1))
        return e / (e.max() or 1)
    a, b = edge(base), edge(img)
    mask = np.zeros_like(a, np.uint8)
    mask[250:960, 180:844] = 1                  # the garment, clear of the face
    warp = np.eye(2, 3, dtype=np.float32)
    _, warp = cv2.findTransformECC(a, b, warp, cv2.MOTION_AFFINE,
                                   (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 400, 1e-6),
                                   mask, 5)
    return warp


def detect():
    base_dir = HERE / "gen" / "base"
    lm_p = HERE / "landmarks.json"
    old = json.loads(lm_p.read_text()) if lm_p.exists() else {}
    lm = {}
    for p in sorted(base_dir.glob("*.png")):
        name = p.stem
        g, v, c = parse(name)
        B = BASE_LM[(g, v)]
        if c == LEAD[g]:
            lm[name] = dict(B, how="hand")
            continue
        if old.get(name, {}).get("how") == "hand" and "chest" in old[name]:
            lm[name] = old[name]
            continue
        w = register(base_dir / f"{g}_{v}_{LEAD[g]}.png", p)
        k = 2880 / 1024

        def tx(x, y):
            return [float(w[0, 0] * x / k + w[0, 1] * y / k + w[0, 2]) * k,
                    float(w[1, 0] * x / k + w[1, 1] * y / k + w[1, 2]) * k]
        cx, cy = B["collar"]
        c2 = tx(cx, cy)
        h2 = tx(cx, B["hem"])
        l2 = tx(B["chest"][0], B["chest_y"])
        r2 = tx(B["chest"][1], B["chest_y"])
        L = {"collar": [round(c2[0]), round(c2[1])], "hem": round(h2[1]),
             "chest": [round(l2[0]), round(r2[0])], "chest_y": round((l2[1] + r2[1]) / 2),
             "how": "registered",
             "scale": round(float(np.hypot(w[0, 0], w[1, 0])), 4)}
        if "hood_point" in B:
            L["hood_point"] = round(tx(cx, B["hood_point"])[1])
        lm[name] = L
    for name, L in lm.items():
        L.pop("hood", None)
        L["centre_x"] = centre_x(base_dir / f"{name}.png", L)
        if name.startswith("hoodie_back"):
            c = name.split("_", 2)[2]
            L["hood_tip"] = [L["centre_x"] + HOOD_TIP[c], HOOD_TIP_Y[c]]
            L["hood_edge"] = hood_edge(base_dir / f"{name}.png", L["hood_tip"])
    lm_p.write_text(json.dumps(lm, indent=1))
    sheet(lm)
    return lm


def centre_x(path, L):
    """The photo's own centre line: the median midpoint of the head and neck
    silhouette, 0.08 to 0.35 chest widths above the collar (on a hoodie, the
    middle of the hood). Registration carries the hand-marked collar to each
    colour well in height but drifts sideways when the pose shifts (up to 9.6% of
    the chest on the royal blue hoodie), so the centre is measured, not carried."""
    from scipy.ndimage import binary_opening, label
    a = np.asarray(Image.open(path).convert("RGB").resize((1440, 1440)), dtype=float)
    bg = np.median(np.concatenate([a[:60, :60].reshape(-1, 3), a[:60, -60:].reshape(-1, 3)]), 0)
    dist = np.sqrt(((a - bg) ** 2).sum(2))
    s = 0.5
    cy, cx = L["collar"][1] * s, L["collar"][0] * s
    chest = (L["chest"][1] - L["chest"][0]) * s
    for th in (28, 16, 10):                      # the heather gray is near the backdrop
        fg = binary_opening(dist > th, iterations=2)
        mids = []
        for r in range(int(cy - 0.35 * chest), int(cy - 0.08 * chest), 3):
            lab, k = label(fg[r])
            for i in range(1, k + 1):
                xx = np.nonzero(lab == i)[0]
                if xx.min() <= cx <= xx.max() and xx.size < 0.95 * fg.shape[1]:
                    mids.append((xx.min() + xx.max()) / 2)
        if mids:
            return round(float(np.median(mids)) / s)
    return L["collar"][0]


def target_box(name, L, place):
    """Ink box (left, top, width) on the 2880px photo, from the flat's ratios."""
    g, v, _ = parse(name)
    F = FLAT_LM[(g, v)]
    ink = json.loads((HERE / "flats" / "ink_boxes.json").read_text())[f"{place}_{g}_{v}"]
    # True inches: the print scales with the garment's collar-to-hem length, the
    # same fabric on the flat and on the body (see the module docstring).
    s = (L["hem"] - L["collar"][1]) / (F["hem"] - F["collar"][1])
    w = (ink[2] - ink[0]) * s * SCALE.get((g, v), 1.0)
    top = L["collar"][1] + (ink[1] - F["collar"][1]) * s
    if (g, v) in RAISE_IN:
        front = json.loads((HERE / "flats" / "ink_boxes.json").read_text())[f"{place}_{g}_front"]
        px_per_in = (front[2] - front[0]) / LOGO_IN * s
        top -= RAISE_IN[(g, v)] * px_per_in
    cx = L.get("centre_x", L["collar"][0])
    note = ""
    if "hood_tip" in L:
        # Hoodie back: centred on the hood's own seam, and the map's top tucked a
        # fixed 3% of its height under the hood's tip, so every colour shows the
        # hood lying over the very top of the design (Evan, 9 Oct 2026).
        cx = L["hood_tip"][0]
        h = w * (ink[3] - ink[1]) / (ink[2] - ink[0])
        top = L["hood_tip"][1] - HOOD_COVER * h
        note = f"hood covers the top {round(HOOD_COVER * h)}px"
    return cx - w / 2, top, w, note


def hood_edge(path, tip):
    """The hood's lower edge traced on this photo (2880px): for every 4th column
    within 300px of the tip, the row of the strongest bright-to-dark step going
    down (the hood's edge, its cast shadow below), between 220px above the tip
    and 30px below it. Median-filtered, then forced to rise away from the tip on
    each side (a hood edge never dips back), with the tip pinned to the hand
    measurement. Marks carried from the lead photo did not follow each colour's
    own hood, so the edge is traced per photo."""
    import cv2
    tx, ty = tip
    g = cv2.GaussianBlur(np.asarray(Image.open(path).convert("L"), np.float32), (0, 0), 2)
    dy = np.zeros_like(g)
    dy[1:-1] = g[2:] - g[:-2]
    xs = np.arange(tx - 300, tx + 301, 4)
    ys = np.array([ty - 220 + int(np.argmin(dy[ty - 220:ty + 30, x - 1:x + 2].mean(1)))
                   for x in xs], float)
    ys = np.array([np.median(ys[max(0, i - 2):i + 3]) for i in range(len(ys))])
    i0 = int(np.argmin(np.abs(xs - tx)))
    ys[i0] = ty
    for i in range(i0 + 1, len(ys)):
        ys[i] = min(ys[i], ys[i - 1])
    for i in range(i0 - 1, -1, -1):
        ys[i] = min(ys[i], ys[i + 1])
    return [[int(x), int(y)] for x, y in zip(xs, ys)]


def hood_mask(L, shape, band=0):
    """1 above the traced hood edge (the hood), 0 below, feathered 2px: the hood
    lies over the top of the map. With band > 0, the region from the edge down to
    band px below it instead, fading from 1 at the edge to 0 (the flat zone)."""
    import cv2
    H, W = shape
    r = W / 2880
    edge = [(x * r, y * r) for x, y in L["hood_edge"]]
    if not band:
        poly = edge + [(edge[-1][0], 0), (edge[0][0], 0)]
        m = np.zeros((H, W), np.uint8)
        cv2.fillPoly(m, [np.array(poly, np.int32)], 255)
        return cv2.GaussianBlur(m.astype(np.float32) / 255, (0, 0), 2 * r)
    xs = np.array([p[0] for p in edge])
    ey = np.interp(np.arange(W), xs, [p[1] for p in edge], left=-1e9, right=-1e9)
    below = np.arange(H)[:, None] - ey[None, :]
    return np.clip(1 - below / (band * r), 0, 1) * (below >= -2 * r)


def canvas_quad(place, g, v, left, top, w):
    """The whole print canvas placed so its ink lands on the target box."""
    pb = json.loads((HERE / "prints" / "ink_boxes.json").read_text())[f"{place}_{g}_{v}"]
    (cw, ch), ink = pb["size"], pb["ink"]
    k = w / (ink[2] - ink[0])
    x0, y0 = left - ink[0] * k, top - ink[1] * k
    return [(x0, y0), (x0 + cw * k, y0), (x0 + cw * k, y0 + ch * k), (x0, y0 + ch * k)]


def sheet(lm):
    tiles = []
    for name, L in sorted(lm.items()):
        im = Image.open(HERE / "gen" / "base" / f"{name}.png").convert("RGB")
        d = ImageDraw.Draw(im)
        cx, cy = L["collar"]
        d.ellipse([cx - 25, cy - 25, cx + 25, cy + 25], outline=(0, 255, 0), width=8)
        d.line([(cx - 300, L["hem"]), (cx + 300, L["hem"])], fill=(0, 255, 0), width=8)
        d.line([(L["chest"][0], L["chest_y"]), (L["chest"][1], L["chest_y"])], fill=(0, 220, 255), width=8)
        left, top, w, _ = target_box(name, L, "salt-lake-city")
        g, v, _ = parse(name)
        ink = json.loads((HERE / "flats" / "ink_boxes.json").read_text())[f"salt-lake-city_{g}_{v}"]
        h = w * (ink[3] - ink[1]) / (ink[2] - ink[0])
        d.rectangle([left, top, left + w, top + h], outline=(255, 220, 0), width=8)
        d.line([(L.get("centre_x", cx), cy - 400), (L.get("centre_x", cx), L["hem"])], fill=(255, 0, 255), width=6)
        if "hood_edge" in L:
            d.line([tuple(p) for p in L["hood_edge"]], fill=(255, 0, 0), width=8)
        im = im.resize((480, 480))
        ImageDraw.Draw(im).text((6, 6), f"{name} {L['how']}", fill=(255, 255, 0))
        tiles.append(im)
    cols = 6
    out = Image.new("RGB", (cols * 480, ((len(tiles) + cols - 1) // cols) * 480))
    for i, t in enumerate(tiles):
        out.paste(t, ((i % cols) * 480, (i // cols) * 480))
    (HERE / "review").mkdir(exist_ok=True)
    out.save(HERE / "review" / "landmarks.jpg", quality=85)


def sha(path):
    import hashlib
    return hashlib.sha1(Path(path).read_bytes()).hexdigest()[:16]


def lock(force=False):
    """Freeze today's placement: every base photo's canvas quad (2880px), worked
    out from the reference city's prints by the rules above, plus what each
    garment and view's print canvas and Tapstitch placement were."""
    if LOCK.exists() and not force:
        raise SystemExit("placement_lock.json exists; the placement is locked. "
                         "Pass --force only for a change Evan approved.")
    ref = "salt-lake-city"
    lm = json.loads((HERE / "landmarks.json").read_text())
    pb = json.loads((HERE / "prints" / "ink_boxes.json").read_text())
    tp = json.loads((HERE / "prints" / "prints.json").read_text())
    out = {"_what": "Locked map print placement, 9 Oct 2026 (Evan approved). See LOCK.md.",
           "reference": ref, "views": {}, "photos": {}}
    for g, v in VIEWS:
        key = f"{ref}_{g}_{v}"
        others = [p for p in PLACES if pb[f"{p}_{g}_{v}"] != pb[key]]
        assert not others, f"{g} {v}: {others} differ from {ref}; cannot lock one placement"
        out["views"][f"{g}_{v}"] = {
            "canvas": pb[key]["size"], "ink": pb[key]["ink"],
            "tapstitch": {k: tp[f"{key}.png"][k] for k in PLACEMENT_KEYS},
            "rules": {"scale": SCALE.get((g, v), 1.0), "raise_in": RAISE_IN.get((g, v), 0.0)}}
    for name, L in sorted(lm.items()):
        g, v, _ = parse(name)
        left, top, w, note = target_box(name, L, ref)
        quad = canvas_quad(ref, g, v, left, top, w)
        src = photo_path(name)
        out["photos"][name] = {
            "canvas_quad": [[round(x, 2), round(y, 2)] for x, y in quad],
            "ink_box": [round(left, 2), round(top, 2), round(w, 2)],
            "span": L["hem"] - L["collar"][1],
            "hood_edge": L.get("hood_edge"), "note": note,
            "photo": src.relative_to(HERE).as_posix(), "photo_sha1": sha(src)}
    out["rules"] = {"fold": FOLD, "hood_cover": HOOD_COVER, "hood_flat_band": HOOD_FLAT_BAND,
                    "out_px": OUT_PX, "ref_span": REF_SPAN}
    LOCK.write_text(json.dumps(out, indent=1))
    print(f"locked {len(out['photos'])} photos x {len(VIEWS)} views")


def check(place):
    """A new city fits the lock: all six prints present, each canvas the locked
    size, and (where prints.json has it) Tapstitch's placement unchanged. A
    different canvas or placement would print somewhere else on the garment, so
    the lock would put the on-model map in the wrong place; refuse instead."""
    lk = json.loads(LOCK.read_text())
    tp = json.loads((HERE / "prints" / "prints.json").read_text())
    bad = []
    for g, v in VIEWS:
        V = lk["views"][f"{g}_{v}"]
        p = HERE / "prints" / f"{place}_{g}_{v}.png"
        if not p.exists():
            bad.append(f"missing prints/{p.name}")
            continue
        size = list(Image.open(p).size)
        if size != V["canvas"]:
            bad.append(f"{p.name}: canvas {size}, locked {V['canvas']}")
        t = tp.get(p.name)
        if t is None:
            bad.append(f"{p.name}: no Tapstitch placement in prints/prints.json")
        else:
            diff = {k: (t.get(k), V["tapstitch"][k]) for k in PLACEMENT_KEYS
                    if t.get(k) != V["tapstitch"][k]}
            if diff:
                bad.append(f"{p.name}: placement differs {diff}")
    for name, P in lk["photos"].items():
        if sha(HERE / P["photo"]) != P["photo_sha1"]:
            bad.append(f"base photo {P['photo']} changed since the lock")
    print(f"{place}: " + ("fits the lock" if not bad else "DOES NOT fit the lock"))
    for b in bad:
        print("   ", b)
    return not bad


def fetch():
    """Download whatever is missing: every locked base photo (gen/jobs.json, the
    Higgsfield results; gitignored for size) and every city's print files
    (prints/prints.json, Tapstitch). Base photos must hash to the lock."""
    import urllib.request
    lk = json.loads(LOCK.read_text())
    jobs = json.loads((HERE / "gen" / "jobs.json").read_text())
    want = [(HERE / P["photo"], jobs[n]["url"], P["photo_sha1"]) for n, P in lk["photos"].items()]
    want += [(HERE / "prints" / f, t["src"], None)
             for f, t in json.loads((HERE / "prints" / "prints.json").read_text()).items()]
    for path, url, h in want:
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            urllib.request.urlretrieve(url, path)
            print("fetched", path.relative_to(HERE))
        if h and sha(path) != h:
            raise SystemExit(f"{path.name} does not match the lock")
    print(f"all {len(want)} files present, base photos match the lock")


def photo_path(name):
    src = HERE / "blanks" / f"{name}.jpg"
    return src if src.exists() else HERE / "gen" / "base" / f"{name}.png"


def build(only=None):
    lk = json.loads(LOCK.read_text())
    out_dir = HERE / "final"
    out_dir.mkdir(exist_ok=True)
    log = {}
    for name, L in sorted(lk["photos"].items()):
        g, v, c = parse(name)
        if only and not any(f"{p}_{name}".startswith(only) for p in PLACES):
            continue
        src = HERE / L["photo"]
        assert sha(src) == L["photo_sha1"], f"{src.name} changed since the lock"
        im = Image.open(src).convert("RGB")
        r = OUT_PX / 2880                       # the lock is in 2880px coordinates
        photo = np.asarray(im.resize((OUT_PX, OUT_PX), Image.LANCZOS), dtype=np.float64)
        k = L["span"] * r / REF_SPAN
        for place in PLACES:
            fn = f"{place}_{name}"
            if only and not fn.startswith(only):
                continue
            V = lk["views"][f"{g}_{v}"]
            size = list(Image.open(HERE / "prints" / f"{place}_{g}_{v}.png").size)
            assert size == V["canvas"], f"{place} {g} {v}: canvas {size}, locked {V['canvas']}; run check"
            left, top, w = L["ink_box"]
            note = L["note"]
            quad = [(x * r, y * r) for x, y in L["canvas_quad"]]
            art_path = HERE / "prints" / f"{place}_{g}_{v}.png"
            art = load_art(str(art_path), quad)
            # Work on the print's neighbourhood only; the margin keeps every blur's
            # reach inside real photo, so the crop edge never shows.
            m = int(80 * k)
            qx, qy = [p[0] for p in quad], [p[1] for p in quad]
            cx0, cy0 = max(int(min(qx)) - m, 0), max(int(min(qy)) - m, 0)
            cx1, cy1 = min(int(max(qx)) + m, OUT_PX), min(int(max(qy)) + m, OUT_PX)
            sub = photo[cy0:cy1, cx0:cx1]
            q2 = [(x - cx0, y - cy0) for x, y in quad]
            part, _ = fold_build(sub, art, q2, FOLD["displace"] * k, FOLD["shade_gain"],
                                 FOLD["texture"], FOLD["opacity"], scale=k,
                                 fold_strength=FOLD["strength"] * k * k, fold_band=FOLD["band"])
            fpart, _ = fold_build(sub, art, q2, 0, 1.0, 0.0, 1.0, scale=k, flat=True)
            img = photo.astype(np.uint8).copy()
            if L.get("hood_edge"):
                # Held flat just below the hood (same shading, no displacement),
                # then the hood itself laid over the map's top.
                still, _ = fold_build(sub, art, q2, 0.0, FOLD["shade_gain"], FOLD["texture"],
                                      FOLD["opacity"], scale=k, fold_strength=0.0, fold_band=FOLD["band"])
                fb = hood_mask(L, photo.shape[:2], band=HOOD_FLAT_BAND)[cy0:cy1, cx0:cx1, None]
                part = part * (1 - fb) + still * fb
                hm = hood_mask(L, photo.shape[:2])[cy0:cy1, cx0:cx1, None]
                part = (part * (1 - hm) + photo[cy0:cy1, cx0:cx1] * hm).astype(np.uint8)
            img[cy0:cy1, cx0:cx1] = part
            flat = img.copy()
            flat[cy0:cy1, cx0:cx1] = fpart
            Image.fromarray(img).save(out_dir / f"{fn}.jpg", quality=95, subsampling=0)
            x0, y0 = int(left * r), int(top * r)
            ink = V["ink"]
            h = int(w * r * (ink[3] - ink[1]) / (ink[2] - ink[0]))
            a = img[y0:y0 + h, x0:x0 + int(w * r)].mean(2).ravel()
            b = flat[y0:y0 + h, x0:x0 + int(w * r)].mean(2).ravel()
            corr = float(np.corrcoef(a, b)[0, 1]) if a.size else None
            log[fn] = {"ink_px": [round(left * r), round(top * r), round(w * r)], "k": round(k, 3),
                       "fold_vs_flat_r": round(corr, 4) if corr else None, "note": note}
            print(fn, log[fn])
    p = HERE / "review" / "build_log.json"
    old = json.loads(p.read_text()) if p.exists() else {}
    old.update(log)
    p.write_text(json.dumps(old, indent=1))


if __name__ == "__main__":
    {"detect": detect,
     "fetch": fetch,
     "lock": lambda: lock("--force" in sys.argv),
     "check": lambda: sys.exit(0 if check(sys.argv[2]) else 1),
     "build": lambda: build(sys.argv[2] if len(sys.argv) > 2 else None)}[sys.argv[1]]()
