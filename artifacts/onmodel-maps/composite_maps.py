"""On-model photos for the map products: place each product's real print on the
Higgsfield model photos and fold it into the fabric.

  python composite_maps.py detect            # landmarks for every base photo + check sheet
  python composite_maps.py build [prefix]    # finals for both places, or names starting prefix

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

PLACES = ["nauvoo", "salt-lake-city"]
OUT_PX = 5000
REF_SPAN = 1170.0
FOLD = dict(displace=0.75, shade_gain=1.8, texture=0.35, opacity=0.93, strength=55.0, band=(4, 20))
LEAD = {"tee": "maroon", "crew": "black", "hoodie": "navy-blue"}

# Evan, 9 Oct 2026, after the true-size build: every back print 10% smaller (top
# edge held, so it shrinks from the bottom), every front logo 1 inch higher, the
# hoodie's logo also 10% smaller, and the hoodie map higher, with the hood lying
# over its very top (HOOD_LM below). Prints centre on the photo's own measured
# centre line (centre_x), which on the hoodie is the middle of the hood.
SCALE = {("tee", "back"): 0.90, ("crew", "back"): 0.90, ("hoodie", "back"): 0.90,
         ("hoodie", "front"): 0.90}
RAISE_IN = {"front": 1.0}
LOGO_IN = 6.0          # front logo's true ink width, the inch ruler on each flat
# The hood's lower outline on the hoodie-back lead photo (2880px): where its left
# edge meets the shoulder, its point at centre back, where its right edge meets
# the shoulder. Carried to each colour by the registration.
HOOD_LM = {"left": [1050, 788], "point": [1437, 1095], "right": [1812, 788]}

# Hand marks on each lead base photo (2880px): collar point, hem y at centre, and
# the chest: left and right x where the sleeve meets the body, at chest_y.
BASE_LM = {
    ("tee", "front"): {"collar": [1437, 900], "hem": 2625, "chest": [907, 1925], "chest_y": 1775},
    ("tee", "back"): {"collar": [1437, 730], "hem": 2620, "chest": [917, 1930], "chest_y": 1740},
    ("crew", "front"): {"collar": [1412, 825], "hem": 2375, "chest": [900, 1912], "chest_y": 1500},
    ("crew", "back"): {"collar": [1412, 700], "hem": 2380, "chest": [912, 1925], "chest_y": 1500},
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
            L["hood"] = {k: [round(c) for c in tx(*p)] for k, p in HOOD_LM.items()}
        lm[name] = L
    for name, L in lm.items():
        if name.startswith("hoodie_back") and "hood" not in L:
            L["hood"] = HOOD_LM
        L["centre_x"] = centre_x(base_dir / f"{name}.png", L)
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
    if v in RAISE_IN:
        front = json.loads((HERE / "flats" / "ink_boxes.json").read_text())[f"{place}_{g}_front"]
        px_per_in = (front[2] - front[0]) / LOGO_IN * s
        top -= RAISE_IN[v] * px_per_in
    cx = L.get("centre_x", L["collar"][0])
    note = ""
    if "hood" in L:
        note = f"hood covers the top {max(0, round(L['hood']['point'][1] - top))}px"
    return cx - w / 2, top, w, note


def hood_mask(L, shape):
    """1 inside the hood (above its lower outline, between its two edges), 0
    elsewhere, feathered 3px: the hood lies over the top of the map."""
    import cv2
    H, W = shape
    r = W / 2880
    (lx, ly), (px, py), (rx, ry) = (L["hood"][k] for k in ("left", "point", "right"))
    dx = L.get("centre_x", px) - px          # the hood sits on the measured centre line
    lx, px, rx = lx + dx, px + dx, rx + dx
    xs = np.linspace(lx, rx, 200)
    # a parabola through the three marks: the hood's two sides meeting at its point
    A = np.array([[lx * lx, lx, 1], [px * px, px, 1], [rx * rx, rx, 1]], float)
    a, b, c = np.linalg.solve(A, [ly, py, ry])
    ys = a * xs * xs + b * xs + c
    poly = [(x * r, y * r) for x, y in zip(xs, ys)] + [(rx * r, 0), (lx * r, 0)]
    m = np.zeros((H, W), np.uint8)
    cv2.fillPoly(m, [np.array(poly, np.int32)], 255)
    m = cv2.GaussianBlur(m.astype(np.float32) / 255, (0, 0), 3 * r)
    return m


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
        if "hood" in L:
            dx = L.get("centre_x", L["hood"]["point"][0]) - L["hood"]["point"][0]
            d.line([(x + dx, y) for x, y in (L["hood"]["left"], L["hood"]["point"], L["hood"]["right"])],
                   fill=(255, 0, 0), width=8)
        im = im.resize((480, 480))
        ImageDraw.Draw(im).text((6, 6), f"{name} {L['how']}", fill=(255, 255, 0))
        tiles.append(im)
    cols = 6
    out = Image.new("RGB", (cols * 480, ((len(tiles) + cols - 1) // cols) * 480))
    for i, t in enumerate(tiles):
        out.paste(t, ((i % cols) * 480, (i // cols) * 480))
    (HERE / "review").mkdir(exist_ok=True)
    out.save(HERE / "review" / "landmarks.jpg", quality=85)


def build(only=None):
    lm = json.loads((HERE / "landmarks.json").read_text())
    out_dir = HERE / "final"
    out_dir.mkdir(exist_ok=True)
    log = {}
    for name, L in sorted(lm.items()):
        g, v, c = parse(name)
        if only and not any(f"{p}_{name}".startswith(only) for p in PLACES):
            continue
        src = HERE / "blanks" / f"{name}.jpg"
        if not src.exists():
            src = HERE / "gen" / "base" / f"{name}.png"
        im = Image.open(src).convert("RGB")
        r = OUT_PX / 2880                       # landmarks are in 2880px coordinates
        photo = np.asarray(im.resize((OUT_PX, OUT_PX), Image.LANCZOS), dtype=np.float64)
        k = (L["hem"] - L["collar"][1]) * r / REF_SPAN
        for place in PLACES:
            fn = f"{place}_{name}"
            if only and not fn.startswith(only):
                continue
            left, top, w, note = target_box(name, L, place)
            quad = [(x * r, y * r) for x, y in canvas_quad(place, g, v, left, top, w)]
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
            if "hood" in L:                      # the hood lies over the map's top
                hm = hood_mask(L, photo.shape[:2])[cy0:cy1, cx0:cx1, None]
                part = (part * (1 - hm) + photo[cy0:cy1, cx0:cx1] * hm).astype(np.uint8)
            img[cy0:cy1, cx0:cx1] = part
            flat = img.copy()
            flat[cy0:cy1, cx0:cx1] = fpart
            Image.fromarray(img).save(out_dir / f"{fn}.jpg", quality=95, subsampling=0)
            x0, y0 = int(left * r), int(top * r)
            ink = json.loads((HERE / "flats" / "ink_boxes.json").read_text())[f"{place}_{g}_{v}"]
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
     "build": lambda: build(sys.argv[2] if len(sys.argv) > 2 else None)}[sys.argv[1]]()
