#!/usr/bin/env python
"""
THROWAWAY SPIKE. Composites a flat print file onto a photo of a blank garment.

Mechanism, in three steps, all driven off the garment photo itself:
  1. quad     - the four corners of the print area, marked once per photo
  2. fold map - blurred luminance of the photo; its slope bends the art
  3. shading  - local/broad luminance ratio, multiplied over the ink

The art is never redrawn. Pixels are only moved and shaded.
"""
import argparse
import json

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None


def gauss(a, sigma):
    """Separable gaussian blur of a float 2D array (PIL cannot blur mode F)."""
    sigma = float(sigma)
    if sigma <= 0:
        return a.copy()
    r = max(1, int(3 * sigma))
    x = np.arange(-r, r + 1, dtype=np.float64)
    k = np.exp(-x * x / (2 * sigma * sigma))
    k /= k.sum()

    pad = np.pad(a, ((0, 0), (r, r)), mode="edge")
    out = np.zeros_like(a)
    for i, w in enumerate(k):
        out += w * pad[:, i:i + a.shape[1]]

    pad = np.pad(out, ((r, r), (0, 0)), mode="edge")
    res = np.zeros_like(a)
    for i, w in enumerate(k):
        res += w * pad[i:i + a.shape[0], :]
    return res


def homography(src, dst):
    """3x3 matrix mapping the four src points onto the four dst points."""
    rows = []
    for (x, y), (u, v) in zip(src, dst):
        rows.append([x, y, 1, 0, 0, 0, -u * x, -u * y, -u])
        rows.append([0, 0, 0, x, y, 1, -v * x, -v * y, -v])
    _, _, vt = np.linalg.svd(np.asarray(rows, dtype=np.float64))
    h = vt[-1].reshape(3, 3)
    return h / h[2, 2]


def sample(img, u, v):
    """Bilinear sample of an HxWxC float image at float coords (u, v)."""
    h, w = img.shape[:2]
    u0 = np.floor(u).astype(np.int64)
    v0 = np.floor(v).astype(np.int64)
    fu = (u - u0)[..., None]
    fv = (v - v0)[..., None]

    def at(uu, vv):
        return img[np.clip(vv, 0, h - 1), np.clip(uu, 0, w - 1)]

    top = at(u0, v0) * (1 - fu) + at(u0 + 1, v0) * fu
    bot = at(u0, v0 + 1) * (1 - fu) + at(u0 + 1, v0 + 1) * fu
    return top * (1 - fv) + bot * fv


def load_art(path, quad, supersample=3.0):
    """Downscale the print file to ~supersample x its on-screen size.

    Point-sampling a 4386px print file straight down to a few hundred pixels
    drops thin lines between samples. LANCZOS averages them in first.
    """
    art = Image.open(path).convert("RGBA")
    qx = [p[0] for p in quad]
    qy = [p[1] for p in quad]
    want_w = int(max(1.0, (max(qx) - min(qx)) * supersample))
    if want_w < art.width:
        want_h = int(round(art.height * want_w / art.width))
        art = art.resize((want_w, want_h), Image.LANCZOS)
    return np.asarray(art, dtype=np.float64)


def build(photo, art, quad, displace, shade_gain, texture_gain, opacity,
          scale=1.0, flat=False, fold_strength=0.0, fold_band=(4, 20)):
    ah, aw = art.shape[:2]
    H, W = photo.shape[:2]

    # --- the fold map and the shading, both read straight off the photo ---
    lum = photo.mean(axis=2)
    broad = gauss(lum, 22 * scale)          # overall lighting across the back
    folds = gauss(lum, 5 * scale)           # lighting plus the big folds
    detail = lum - gauss(lum, 1.6 * scale)  # the knit texture

    gy, gx = np.gradient(gauss(lum, 7 * scale))
    norm = np.percentile(np.hypot(gx, gy), 99) or 1.0
    gx = np.clip(gx / norm, -1, 1)
    gy = np.clip(gy / norm, -1, 1)

    shade = (folds + 4.0) / (broad + 4.0)
    shade = np.clip(1.0 + (shade - 1.0) * shade_gain, 0.45, 1.55)

    # --- map the print-area rectangle onto the marked quad ---
    src = [(0, 0), (aw, 0), (aw, ah), (0, ah)]
    hinv = np.linalg.inv(homography(src, quad))

    qx = [p[0] for p in quad]
    qy = [p[1] for p in quad]
    pad = int(8 * scale)
    x0, x1 = max(int(min(qx)) - pad, 0), min(int(max(qx)) + pad, W)
    y0, y1 = max(int(min(qy)) - pad, 0), min(int(max(qy)) + pad, H)

    yy, xx = np.mgrid[y0:y1, x0:x1]
    X = xx.astype(np.float64)
    Y = yy.astype(np.float64)

    if not flat:
        # a point on screen shows the art that sat here before the fabric moved
        X = X - displace * gx[y0:y1, x0:x1]
        Y = Y - displace * gy[y0:y1, x0:x1]

        # Pull the print into the creases. The usual mockup displacement map:
        # a band-pass of the photo's log luminance, so only crease-sized shading
        # counts and the effect is relative to the garment's own brightness.
        # Moving along its slope draws art in from both walls of a dark crease,
        # so every line that crosses a fold bends into it along the fold's whole
        # length, in proportion to how deep the fold looks. One strength for
        # every photo: a soft fold (the hoodie) moves the art less than a sharp
        # one (the tee) without any per-garment number.
        if fold_strength:
            L = np.log(lum + 8.0)
            band = gauss(L, fold_band[0] * scale) - gauss(L, fold_band[1] * scale)
            by, bx = np.gradient(band)
            X = X + fold_strength * bx[y0:y1, x0:x1]
            Y = Y + fold_strength * by[y0:y1, x0:x1]

    den = hinv[2, 0] * X + hinv[2, 1] * Y + hinv[2, 2]
    u = (hinv[0, 0] * X + hinv[0, 1] * Y + hinv[0, 2]) / den
    v = (hinv[1, 0] * X + hinv[1, 1] * Y + hinv[1, 2]) / den

    inside = (u >= 0) & (u <= aw - 1) & (v >= 0) & (v <= ah - 1)
    picked = sample(art, u, v)
    alpha = (picked[..., 3] / 255.0) * np.where(inside, 1.0, 0.0) * opacity

    ink = picked[..., :3]
    if not flat:
        s = shade[y0:y1, x0:x1][..., None]
        t = detail[y0:y1, x0:x1][..., None] * texture_gain
        ink = np.clip(ink * s + t, 0, 255)

    out = photo.copy()
    region = out[y0:y1, x0:x1]
    out[y0:y1, x0:x1] = region * (1 - alpha[..., None]) + ink * alpha[..., None]

    foldview = np.clip((gauss(lum, 7 * scale) - broad) * 6 + 128, 0, 255)
    return np.clip(out, 0, 255).astype(np.uint8), foldview.astype(np.uint8)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--photo", required=True)
    p.add_argument("--art", required=True)
    p.add_argument("--quad", required=True, help="JSON list of 4 [x,y] TL,TR,BR,BL")
    p.add_argument("--upscale", type=float, default=1.0,
                   help="render at this multiple of the photo's native size")
    p.add_argument("--displace", type=float, default=3.0)
    p.add_argument("--shade-gain", type=float, default=1.0)
    p.add_argument("--texture-gain", type=float, default=0.35)
    p.add_argument("--opacity", type=float, default=0.93)
    p.add_argument("--out", required=True)
    p.add_argument("--out-flat")
    p.add_argument("--out-foldmap")
    args = p.parse_args()

    f = args.upscale
    photo_im = Image.open(args.photo).convert("RGB")
    if f != 1.0:
        photo_im = photo_im.resize(
            (int(photo_im.width * f), int(photo_im.height * f)), Image.LANCZOS)
    photo = np.asarray(photo_im, dtype=np.float64)

    quad = [(x * f, y * f) for x, y in json.loads(args.quad)]
    art = load_art(args.art, quad)

    final, foldview = build(photo, art, quad, args.displace * f, args.shade_gain,
                            args.texture_gain, args.opacity, scale=f)
    Image.fromarray(final).save(args.out, quality=95)
    print("wrote", args.out, final.shape)

    if args.out_flat:
        flat, _ = build(photo, art, quad, 0, 0, 0, 1.0, scale=f, flat=True)
        Image.fromarray(flat).save(args.out_flat, quality=95)
        print("wrote", args.out_flat)

    if args.out_foldmap:
        Image.fromarray(foldview).save(args.out_foldmap, quality=95)
        print("wrote", args.out_foldmap)


if __name__ == "__main__":
    main()
