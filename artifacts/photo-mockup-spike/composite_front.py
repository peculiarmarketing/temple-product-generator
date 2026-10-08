#!/usr/bin/env python
"""Composite the Be Peculiar / Sé Singular wordmarks and the bomber prints onto
the stock-model on-model photos (build_front_bases.py).

Placement is proportional to the garment's own collar-to-hem span, taken from
Tapstitch's flat mockup of the same design (onmodel-front/prints/front_geometry.json),
so the print lands where Tapstitch renders it whatever size the model wears.
The art is the full-resolution source file, matched against Tapstitch's own
preview of the uploaded print; the image model never draws it.

Landmarks per photo (collar = the front neckline at centre, or the back collar
band for a back view; hem = the bottom of the hem band; centre = the garment's
centre line) come from detect(), are drawn on a check sheet, and can be
overridden by hand in onmodel-front/landmarks.json.

  python composite_front.py detect   # writes landmarks.json + check sheet
  python composite_front.py build    # writes onmodel-front/final/*.jpg
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from composite import build  # noqa: E402

ROOT = HERE.parent / "onmodel-front"
GEO = json.loads((ROOT / "prints/front_geometry.json").read_text())
FOLD = json.loads((HERE / "print_geometry.json").read_text())["fold"]

# which art goes on which photo: (geometry key, art file)
ART = {"en": ROOT / "prints/art_en.png", "es": ROOT / "prints/art_es.png",
       "chest": ROOT / "prints/chest.png", "seal": ROOT / "prints/seal.png"}


def photos():
    """Every approved base and colourway photo, blank: name -> path.

    Kept in onmodel-front/blanks/ as quality-95 JPEGs, committed, because they
    exist nowhere else: the bases are the first generation per stock model
    (shown to Evan 8 Oct 2026) and the colourways one generation from those.
    back_* files are the temple-tee colours, composited by composite_catalog.py.
    """
    return {p.stem: p for p in sorted((ROOT / "blanks").glob("*.jpg"))
            if not p.stem.startswith("back_")}


def garment_of(name):
    g = name.split("_")[0]
    if g == "bomber":
        return "bomber_back" if name.endswith("_back") else "bomber_front"
    return g


def detect(path, geo_key):
    a = np.asarray(Image.open(path).convert("RGB")).astype(float)
    H, W, _ = a.shape
    bg = np.median(np.concatenate([a[:, :40].reshape(-1, 3), a[:, -40:].reshape(-1, 3)]), 0)
    person = np.abs(a - bg).sum(2) > 45
    band = person[int(H * .35):int(H * .55)]
    xs = np.where(band.any(0))[0]
    cx = int((xs.min() + xs.max()) / 2)
    col_x = cx + (int(W * .03) if geo_key == "bomber_front" else 0)   # step off the zip
    strip = a[:, col_x - 6:col_x + 7].mean(1)
    garment = np.median(a[int(H * .45):int(H * .5), col_x - 30:col_x + 30].reshape(-1, 3), 0)
    near = np.abs(strip - garment).sum(1) < max(60, 0.25 * garment.sum())
    # collar: first row from the top third down where the garment colour holds for 12 rows
    start = int(H * (.22 if geo_key == "bomber_back" else .08))   # below the hair
    collar = next(y for y in range(start, int(H * .6))
                  if near[y:y + 12].mean() > 0.9)
    # hem: last row of the garment run below the chest, allowing short gaps
    y, last, gap = int(H * .45), int(H * .45), 0
    while y < H - 1 and gap < 18:
        if near[y]:
            last, gap = y, 0
        else:
            gap += 1
        y += 1
    return {"collar": int(collar), "hem": int(last), "centre": cx,
            "dark": bool(garment.sum() < 150)}


def fix_dark_spans(lm):
    """A near-black garment on dark trousers has no visible hem edge. Every
    colourway is one generation from the same base with only a slight pose
    change, so the collar-to-hem span is effectively constant per garment: take
    the median span of the garment's lighter colours."""
    spans = {}
    for name, L in lm.items():
        if not L.get("dark") and not L.get("failed"):
            spans.setdefault(garment_of(name), []).append(L["hem"] - L["collar"])
    for name, L in lm.items():
        g = garment_of(name)
        if L.get("dark") and not L.get("manual") and spans.get(g):
            L["hem"] = int(L["collar"] + float(np.median(spans[g])))
            L["hem_from_span"] = True


# Marked by hand on each garment's base photo, 8 Oct 2026, from ruler crops:
# collar = bottom of the front neck rib at centre (hoodie: the V where the hood
# meets; bomber front: the V where the collar rib meets the zip; bomber back:
# bottom of the collar band), hem = bottom edge of the hem / waistband.
BASE_LM = {
    "tee": ("tee_black", {"collar": 680, "hem": 1692, "centre": 1024}),
    "hoodie": ("hoodie_gray", {"collar": 735, "hem": 1780, "centre": 1004}),
    "crew": ("crew_black", {"collar": 680, "hem": 1757, "centre": 1024}),
    "bomber_front": ("bomber_navy-blue_front", {"collar": 717, "hem": 1685, "centre": 1004}),
    "bomber_back": ("bomber_navy-blue_back", {"collar": 543, "hem": 1675, "centre": 1004}),
}


def edges(path):
    from scipy import ndimage
    g = np.asarray(Image.open(path).convert("L"), dtype=float)
    return np.hypot(ndimage.sobel(g, 0), ndimage.sobel(g, 1))


def shift(base_e, e, y0, y1, x0=500, x1=1550):
    from skimage.registration import phase_cross_correlation
    (dy, dx), _, _ = phase_cross_correlation(base_e[y0:y1, x0:x1], e[y0:y1, x0:x1],
                                             upsample_factor=4)
    return -dy, -dx     # how far the photo moved relative to the base


def cmd_detect():
    """Base landmarks are by hand; every colourway is registered to its base
    twice, once around the neck (collar, centre) and once around the hem, so a
    slight change of stance moves each landmark with it."""
    ph = photos()
    lm, tiles = {}, []
    base_edges = {g: edges(ph[b]) for g, (b, _) in BASE_LM.items()}
    for name, p in ph.items():
        g = garment_of(name)
        base_name, B = BASE_LM[g]
        if name == base_name:
            lm[name] = dict(B)
        else:
            e = edges(p)
            cdy, cdx = shift(base_edges[g], e, B["collar"] - 260, B["collar"] + 260)
            hdy, _ = shift(base_edges[g], e, B["hem"] - 220, B["hem"] + 120)
            # A slight change of stance moves a landmark a few pixels. A big
            # jump is the correlation locking onto the wrong feature (the pink
            # tee's collar matched its face, 220px up): keep the base mark.
            if max(abs(cdy), abs(cdx)) > 40:
                cdy = cdx = 0.0
            if abs(hdy) > 40:
                hdy = 0.0
            lm[name] = {"collar": int(round(B["collar"] + cdy)), "hem": int(round(B["hem"] + hdy)),
                        "centre": int(round(B["centre"] + cdx)),
                        "shift": [round(float(cdx), 1), round(float(cdy), 1), round(float(hdy), 1)]}
        im = Image.open(p).convert("RGB")
        d = ImageDraw.Draw(im)
        L = lm[name]
        d.line([(0, L["collar"]), (im.width, L["collar"])], fill=(255, 0, 0), width=5)
        d.line([(0, L["hem"]), (im.width, L["hem"])], fill=(0, 200, 255), width=5)
        d.line([(L["centre"], 0), (L["centre"], im.height)], fill=(255, 220, 0), width=4)
        im.thumbnail((420, 420))
        ImageDraw.Draw(im).text((6, 6), name, fill=(255, 0, 0))
        tiles.append(im)
    (ROOT / "landmarks.json").write_text(json.dumps(lm, indent=1))
    cols = 6
    S = Image.new("RGB", (cols * 420, ((len(tiles) + cols - 1) // cols) * 420), "white")
    for i, t in enumerate(tiles):
        S.paste(t, ((i % cols) * 420, (i // cols) * 420))
    S.save(ROOT / "landmarks-check.jpg", quality=85)
    print(json.dumps({k: v.get("shift") for k, v in lm.items()}))


def place(L, geo_key, art_path):
    g = GEO[geo_key]
    ppi = (L["hem"] - L["collar"]) / g["collar_to_hem_in"]
    art = Image.open(art_path).convert("RGBA")
    art = art.crop(art.getchannel("A").getbbox())
    w = g["ink_w_in"] * ppi
    h = w * art.height / art.width
    top = L["collar"] + g["ink_top_below_collar_in"] * ppi
    cx = L["centre"] + g["ink_cx_off_in"] * ppi
    quad = [(cx - w / 2, top), (cx + w / 2, top), (cx + w / 2, top + h), (cx - w / 2, top + h)]
    art = art.resize((max(1, int(w * 3)), max(1, int(h * 3))), Image.LANCZOS)
    return np.asarray(art, dtype=np.float64), quad


def cmd_build(only=None):
    lm = json.loads((ROOT / "landmarks.json").read_text())
    out = ROOT / "final"
    out.mkdir(exist_ok=True)
    for name, p in photos().items():
        if only and not name.startswith(only):
            continue
        g = garment_of(name)
        jobs = ([("en", "en"), ("es", "es")] if g in ("tee", "crew", "hoodie")
                else [("chest", None)] if g == "bomber_front" else [("seal", None)])
        photo = np.asarray(Image.open(p).convert("RGB"), dtype=np.float64)
        for art_key, suffix in jobs:
            art, quad = place(lm[name], g, ART[art_key])
            img, _ = build(photo, art, quad, 3.0, FOLD["shade_gain"], 0.35, 0.93, scale=1.0,
                           fold_strength=FOLD["strength"], fold_band=tuple(FOLD["band_px"]))
            fn = out / (f"{name}_{suffix}.jpg" if suffix else f"{name}.jpg")
            Image.fromarray(img).save(fn, quality=92)
            print("wrote", fn.name)


if __name__ == "__main__":
    {"detect": cmd_detect, "build": lambda: cmd_build(sys.argv[2] if len(sys.argv) > 2 else None)}[sys.argv[1]]()
