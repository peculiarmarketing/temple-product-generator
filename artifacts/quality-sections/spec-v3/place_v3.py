"""Lay the four real front designs on the spec-v3 group photo.

Input: base/spec-v3-base.png (kie.ai GPT Image 2, task 06cac5e5, 3504x2336,
plain blanks; Evan kept its original sneakers). Output: web/ and qa/.

Prints go on with composite() from photo-mockup-spike/composite_front_v2.py,
the compositor the Be Peculiar and bomber product photos use: the art is resized
once and laid flat (no warping, so lettering stays sharp), then takes the photo's
broad light and shade and a light knit texture.

Placement, measured on gridded close-ups of the base (qa/grid-*.jpg):
- chest = the garment's body width where the sleeves meet it.
- Hoodie wordmark: option F, Evan 8 Oct 2026 (51% of chest wide, top 23% of
  chest below the hood's V), as in composite_front_v2.WORDMARK.
- Box logo and coordinates logo: both print 6 in wide against the wordmark's
  11 in, so they take 6/11 of the wordmark's share of the chest; top 0.59 logo
  widths below the collar band, the spec-v2 rule.
- Bomber chest logo: flat_geometry.json bomber_front ratios (w 0.1672, d 0.1516,
  cx 0.1906 of chest). The jacket is worn open, so the logo moves out with its
  panel: centred 0.1906 chest from where the zip edge sits on that panel.

Usage: python place_v3.py
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter, map_coordinates

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "photo-mockup-spike"))
from composite_front_v2 import composite  # noqa: E402

ART = HERE / "art"
BOX_SHARE = 11.0 / 21.65 * 6.0 / 11.0     # 6 in logo on the tee's 21.65 in chest

# name, art file, collar (x, y), chest px, how to place
G = {
    "bomber": ("bomber-chest-print.png", (1305, 503), 400),
    "hoodie": ("wordmark-print.png", (1980, 539), 369),
    "crew": ("coords-salt-lake-white.png", (1223, 1287), 487),
    "tee": ("box-logo-white.png", (2323, 1242), 346),   # x: torso centre; he is turned slightly
}
BOMBER_ZIP_SHIFT = 54   # open panel's zip edge sits this far right of centre at the logo

# Evan's alignment pass, 9 Oct: (dx px, dy px, degrees counter-clockwise).
# About 15 px to the inch on these chests. The bomber turns so the box's left
# border runs parallel to the zip beside it, measured at 12.3 deg from vertical
# (zip teeth x vs y, y 540 to 660, bottom further right).
ADJUST = {
    "bomber": (0, 0, 12.3),
    "hoodie": (14, 15, 0.0),    # down about an inch; 7th pass: 1.5 in right; 8th: back 8 px left
    "crew": (30, 15, 6.5),      # right, rising to the right (2nd: +2 deg; 5th: +1.5; 6th: +22 right, +15 down, +1.5 deg)
    "tee": (42, 57, 4.5),       # down and right, low at the bottom left (2nd: +8 right; 3rd: +15 down, +11 right; 4th, 5th: +1.5 deg; 6th: +15 right, +30 down)
}
# 2nd pass: the tee logo read too small; scaled about its own centre.
SCALE = {"tee": 1.3}

# 2nd pass: the BE of the hoodie wordmark bends over the fold under it (a dark
# vertical crease near x 1900). Only the left share of the print is warped, fading
# out across the E, so PECULIAR and the verse line stay flat and sharp.
# rows: the BE and box end at 0.802 of the art's height; the verse line below is
# left flat (warping it smeared the small lettering).
WARP = {"hoodie": {"share": 0.27, "fade": 0.06, "px": 3.0, "rows": 0.80}}


def warp_art(art_path, photo, left, top, w, share, fade, px, rows):
    """Resize the art to its on-photo size, push its ink along the fabric's own
    shading (as zoom-v2/place_logo.py does) inside the left `share` of the print,
    and return a temp file plus the left/top/width of its ink after warping."""
    art = Image.open(art_path).convert("RGBA")
    art = art.crop(art.getchannel("A").getbbox())
    W, H = round(w), round(w * art.height / art.width)
    pad = 8
    a = np.zeros((H + 2 * pad, W + 2 * pad, 4))
    a[pad:pad + H, pad:pad + W] = np.asarray(art.resize((W, H), Image.LANCZOS), float)
    x0, y0 = round(left) - pad, round(top) - pad
    lum = photo[y0:y0 + a.shape[0], x0:x0 + a.shape[1]].mean(2)
    gy, gx = np.gradient(gaussian_filter(lum, 3.0))
    mag = np.percentile(np.hypot(gx, gy), 95) + 1e-6
    xs = (np.arange(a.shape[1]) - pad) / W
    ys = (np.arange(a.shape[0]) - pad) / H
    ramp = (np.clip((share - xs) / fade, 0, 1)[None, :]      # 1 on the BE, 0 past it
            * np.clip((rows - ys) / 0.04, 0, 1)[:, None])    # and 0 on the verse line
    dx, dy = gx / mag * px * ramp, gy / mag * px * ramp
    yy, xx = np.mgrid[0:a.shape[0], 0:a.shape[1]].astype(float)
    out = np.stack([map_coordinates(a[..., c], [yy - dy, xx - dx], order=1) for c in range(4)], -1)
    im = Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), "RGBA")
    bx0, by0, bx1, _ = im.getchannel("A").getbbox()
    tmp = HERE / "art" / f"_warped_{Path(art_path).stem}.png"
    im.save(tmp)
    return tmp, x0 + bx0, y0 + by0, bx1 - bx0


def placement(name):
    art, (cx, cy), chest = G[name]
    if name == "hoodie":
        w = 11.0 / 21.65 * chest
        return cx - w / 2, cy + 5.0 / 21.65 * chest, w
    if name == "bomber":
        w = 0.1672 * chest
        x = cx + BOMBER_ZIP_SHIFT + 0.1906 * chest
        return x - w / 2, cy + 0.1516 * chest, w
    w = BOX_SHARE * chest
    return cx - w / 2, cy + 0.59 * w, w


def main():
    photo = np.asarray(Image.open(HERE / "base" / "spec-v3-base.png").convert("RGB"), np.float64)
    for name in G:
        left, top, w = placement(name)
        dx, dy, angle = ADJUST[name]
        s = SCALE.get(name, 1.0)
        left, top, w = left - w * (s - 1) / 2 + dx, top + dy, w * s
        art = ART / G[name][0]
        if name in WARP:
            art, left, top, w = warp_art(art, photo, left, top, w, **WARP[name])
        photo = composite(photo, art, left, top, w, angle).astype(np.float64)
        print(f"{name:7s} {G[name][0]:28s} left {left:7.1f} top {top:7.1f} width {w:6.1f} angle {angle}")
    out = Image.fromarray(photo.astype(np.uint8))
    (HERE / "web").mkdir(exist_ok=True)
    out.save(HERE / "web" / "pp-spec-group-v3.png")
    out.save(HERE / "web" / "pp-spec-group-v3.jpg", quality=95, subsampling=0)


if __name__ == "__main__":
    main()
