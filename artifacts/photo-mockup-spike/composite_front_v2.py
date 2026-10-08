#!/usr/bin/env python
"""v2 compositor for the Be Peculiar / Sé Singular wordmarks and the bomber
prints (Evan's review of v1, 8 Oct 2026).

What changed from composite_front.py, and why:

  PLACEMENT. v1 placed the print as a fraction of the collar-to-hem span. The
  generated tee and crew are cut shorter than Tapstitch's flats, so the same
  fraction landed lower on the body. v2 scales from CHEST WIDTH (armpit to
  armpit): on Tapstitch's own flat of each design, the wordmark's top sits
  d x chest below the collar and is w x chest wide (onmodel-v2/flat_geometry.json);
  on each photo the same ratios are applied to the model's chest width.

  SHARPNESS. v1 ran the temple settings (fold warp 220, displace 3, texture
  0.35), which bend and noise thin lettering, on 2048px photos where the
  verse line was ~4px tall. v2 has no displacement of any kind: the art is
  resized once with Lanczos to its exact on-photo size and laid flat, then only
  the photo's broad light and shade is multiplied over it, with a light knit
  texture (0.1). Photos are 4096px (kie.ai 4K or Higgsfield 4K upscale) before
  compositing, and finals are saved as JPEG quality 95.

  python composite_front_v2.py build [prefix]
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter

Image.MAX_IMAGE_PIXELS = None
HERE = Path(__file__).resolve().parent
V2 = HERE.parent / "onmodel-v2"
PRINTS = HERE.parent / "onmodel-front" / "prints"
FLAT = json.loads((V2 / "flat_geometry.json").read_text())

ART = {"en": PRINTS / "art_en.png", "es": PRINTS / "art_es.png",
       "chest": PRINTS / "chest.png", "seal": PRINTS / "seal.png"}

SHADE_GAIN = 1.0     # v1 used 1.8 to darken ink in creases; flat ink wants less
TEXTURE_GAIN = 0.10  # v1 0.35
OPACITY = 0.95
OUT_PX = 5000        # Shopify's maximum; the verse line comes out ~14px tall


def geo_key(photo, art):
    g = photo.split("_")[0]
    if g == "bomber":
        return "bomber_back" if photo.endswith("_back") else "bomber_front"
    return f"{g}_{art}"


def place(L, key, art):
    """Return the print's (left, top, width) in photo pixels."""
    F = FLAT[key]
    chest = L["chest"][1] - L["chest"][0]
    w = F["w"] * chest
    top = L["collar"][1] + F["d"] * chest
    cx = L["collar"][0] + F["cx"] * chest
    return cx - w / 2, top, w


def composite(photo, art_path, left, top, w, angle=0.0):
    """angle: degrees counter-clockwise, for a garment panel that is not level
    (the unzipped bomber's open front panel hangs at ~3.8 deg). The art is
    rotated at full print resolution, then resized once, about its centre."""
    art = Image.open(art_path).convert("RGBA")
    art = art.crop(art.getchannel("A").getbbox())
    W0 = max(1, round(w))
    H0 = max(1, round(w * art.height / art.width))
    if angle:
        k = art.width / W0
        art = art.rotate(angle, resample=Image.BICUBIC, expand=True)
        W, H = max(1, round(art.width / k)), max(1, round(art.height / k))
        left, top = left + (W0 - W) / 2, top + (H0 - H) / 2
    else:
        W, H = W0, H0
    art = art.resize((W, H), Image.LANCZOS)
    a = np.asarray(art, dtype=np.float64)

    x0, y0 = round(left), round(top)
    m = 260                                     # margin for the shade blur
    X0, Y0 = max(x0 - m, 0), max(y0 - m, 0)
    X1, Y1 = min(x0 + W + m, photo.shape[1]), min(y0 + H + m, photo.shape[0])
    region = photo[Y0:Y1, X0:X1]
    lum = region.mean(axis=2)
    s = photo.shape[1] / 2048                   # blur radii were tuned at 2048px
    broad = gaussian_filter(lum, 22 * s)
    folds = gaussian_filter(lum, 5 * s)
    detail = lum - gaussian_filter(lum, 1.6 * s)
    shade = np.clip(1.0 + ((folds + 4) / (broad + 4) - 1.0) * SHADE_GAIN, 0.6, 1.3)

    ys, xs = y0 - Y0, x0 - X0
    sl = (slice(ys, ys + H), slice(xs, xs + W))
    ink = a[..., :3] * shade[sl][..., None] + detail[sl][..., None] * TEXTURE_GAIN
    alpha = a[..., 3:] / 255.0 * OPACITY
    out = photo.copy()
    patch = out[Y0:Y1, X0:X1]
    patch[sl] = patch[sl] * (1 - alpha) + np.clip(ink, 0, 255) * alpha
    return np.clip(out, 0, 255).astype(np.uint8)


# Marked by hand on each garment's base photo (4096px coordinates), 8 Oct 2026,
# from ruler crops. collar = the point named in flat_geometry.json "_collar";
# chest = the garment's left and right body edges where the sleeves meet it.
BASE_LM = {
    "tee": ("tee_black", {"collar": [2045, 1294], "chest": [1470, 2600]}),
    "crew": ("crew_black", {"collar": [2050, 1278], "chest": [1290, 2862]}),
    "hoodie": ("hoodie_gray", {"collar": [2037, 1180], "chest": [1479, 2586]}),
    "bomber_front": ("bomber_navy-blue_front", {"collar": [2008, 1428], "chest": [1300, 2720]}),
    "bomber_back": ("bomber_navy-blue_back", {"collar": [2010, 1144], "chest": [1312, 2714]}),
    "bomber_open": ("bomber_navy-blue_open", None),     # marked separately, one photo
}


def group(name):
    g = name.split("_")[0]
    if g == "bomber":
        return "bomber_" + name.rsplit("_", 1)[1]
    return g


def register(base, img):
    """Scale and shift that map the base photo onto img (similarity, by ECC on
    edge maps at 1024px). A colourway is one generation from its base with a
    slight change of pose, so its landmarks move with the torso."""
    import cv2

    def edge(p):
        g = np.asarray(Image.open(p).convert("L").resize((1024, 1024), Image.LANCZOS), np.float32)
        g = cv2.GaussianBlur(g, (0, 0), 2)
        e = np.hypot(cv2.Sobel(g, cv2.CV_32F, 1, 0), cv2.Sobel(g, cv2.CV_32F, 0, 1))
        return e / (e.max() or 1)
    a, b = edge(base), edge(img)
    mask = np.zeros_like(a, np.uint8)
    mask[230:800, 250:774] = 1                  # the torso, clear of the face
    warp = np.eye(2, 3, dtype=np.float32)
    _, warp = cv2.findTransformECC(a, b, warp, cv2.MOTION_AFFINE,
                                   (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 300, 1e-6),
                                   mask, 5)
    return warp                                  # maps base (x,y,1) -> img, at 1024px


def detect():
    """Base landmarks are by hand; every other photo is registered to its base."""
    from PIL import ImageDraw
    blanks = sorted(p.stem for p in (V2 / "blanks").glob("*.jpg"))
    lm_p = V2 / "landmarks.json"
    old = json.loads(lm_p.read_text()) if lm_p.exists() else {}
    lm = {}
    for name in blanks:
        g = group(name)
        base, B = BASE_LM[g]
        if B is None:
            if name in old:
                lm[name] = old[name]
            continue
        if name == base:
            lm[name] = dict(B, how="hand")
            continue
        if not (V2 / "blanks" / f"{base}.jpg").exists():
            print("waiting for base", base, "->", name)
            continue
        if old.get(name, {}).get("how") == "hand":
            lm[name] = old[name]
            continue
        w = register(V2 / "blanks" / f"{base}.jpg", V2 / "blanks" / f"{name}.jpg")
        k = 4096 / 1024

        def tx(x, y):
            u = w[0, 0] * x / k + w[0, 1] * y / k + w[0, 2]
            v = w[1, 0] * x / k + w[1, 1] * y / k + w[1, 2]
            return [round(u * k), round(v * k)]
        c = tx(*B["collar"])
        yl = B["collar"][1] + 600
        l, r = tx(B["chest"][0], yl), tx(B["chest"][1], yl)
        scale = float(np.hypot(w[0, 0], w[1, 0]))
        lm[name] = {"collar": c, "chest": [l[0], r[0]], "how": "registered",
                    "scale": round(scale, 4), "shift": [round(float(w[0, 2] * k)), round(float(w[1, 2] * k))]}
    lm_p.write_text(json.dumps(lm, indent=1))
    # check sheet: collar point, chest span, and where each print will land
    tiles = []
    for name, L in lm.items():
        im = Image.open(V2 / "blanks" / f"{name}.jpg").convert("RGB")
        d = ImageDraw.Draw(im)
        cx, cy = L["collar"]
        d.ellipse([cx - 18, cy - 18, cx + 18, cy + 18], outline=(255, 0, 0), width=8)
        yc = cy + 600
        d.line([(L["chest"][0], yc), (L["chest"][1], yc)], fill=(0, 220, 255), width=10)
        for art, _ in jobs_for(name)[:1]:
            left, top, wdt = place(L, geo_key(name, art), art)
            a = Image.open(ART[art])
            a = a.crop(a.getchannel("A").getbbox())
            h = wdt * a.height / a.width
            d.rectangle([left, top, left + wdt, top + h], outline=(255, 220, 0), width=8)
        im = im.resize((512, 512))
        ImageDraw.Draw(im).text((6, 6), name, fill=(255, 0, 0))
        tiles.append(im)
    cols = 6
    S = Image.new("RGB", (cols * 512, ((len(tiles) + cols - 1) // cols) * 512), "white")
    for i, t in enumerate(tiles):
        S.paste(t, ((i % cols) * 512, (i // cols) * 512))
    S.save(V2 / "landmarks-check.jpg", quality=85)
    print(json.dumps({k: (v.get("scale"), v.get("shift")) for k, v in lm.items()}))


def jobs_for(name):
    g = name.split("_")[0]
    if g in ("tee", "crew", "hoodie"):
        return [("en", f"{name}_en"), ("es", f"{name}_es")]
    if name.endswith("_back"):
        return [("seal", name)]
    return [("chest", name)]                    # bomber front, zipped or open


def build(only=None):
    lm = json.loads((V2 / "landmarks.json").read_text())
    out = V2 / "final"
    out.mkdir(exist_ok=True)
    for name, L in sorted(lm.items()):
        if only and not name.startswith(only):
            continue
        im = Image.open(V2 / "blanks" / f"{name}.jpg").convert("RGB")
        k = OUT_PX / im.width                   # landmarks are in 4096px blank coordinates
        photo = np.asarray(im.resize((OUT_PX, OUT_PX), Image.LANCZOS), dtype=np.float64)
        for art, fn in jobs_for(name):
            key = geo_key(name, art)
            left, top, w = (v * k for v in place(L, key, art))
            img = composite(photo, ART[art], left, top, w, L.get("angle", 0.0))
            Image.fromarray(img).save(out / f"{fn}.jpg", quality=95, subsampling=0)
            print("wrote", fn, f"print {round(w)}px wide at ({round(left)},{round(top)})")


if __name__ == "__main__":
    {"detect": detect,
     "build": lambda: build(sys.argv[2] if len(sys.argv) > 2 else None)}[sys.argv[1]]()
