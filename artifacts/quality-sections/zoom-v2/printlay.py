"""Lay the real Peculiar People logo onto a generated garment photo as if printed.

The art is never drawn by the image model. This scales the white logo PNG to its
true printed size for the photo's scale, bends it slightly with the fabric folds
(displacement from the photo's own shading), lets the fabric's light and shadow
show through, and, at macro scale, lets the knit texture break up the ink a little
the way white ink sits on cotton. Used for every frame of the scroll zoom chain.
"""
import numpy as np
from PIL import Image, ImageFilter

LOGO = '/root/.claude/uploads/6fbf1d82-0c82-53e9-9f7e-454ccd9e0762/c44be4e7-image.png'


def _ink_bbox(a):
    ys, xs = np.nonzero(a > 20)
    return xs.min(), ys.min(), xs.max() + 1, ys.max() + 1


def _bilinear(a, x, y):
    x0 = np.floor(x).astype(int); y0 = np.floor(y).astype(int)
    fx = x - x0; fy = y - y0
    return (a[y0, x0] * (1 - fx) * (1 - fy) + a[y0, x0 + 1] * fx * (1 - fy)
            + a[y0 + 1, x0] * (1 - fx) * fy + a[y0 + 1, x0 + 1] * fx * fy)


def _box(a, r, axis):
    """Box filter of radius r along one axis (edge-padded), via a cumulative sum."""
    if r < 1:
        return a
    pad = [(0, 0)] * a.ndim
    pad[axis] = (r + 1, r)
    c = np.cumsum(np.pad(a, pad, mode='edge'), axis=axis)
    n = a.shape[axis]
    hi = np.take(c, np.arange(2 * r + 1, 2 * r + 1 + n), axis=axis)
    lo = np.take(c, np.arange(0, n), axis=axis)
    return (hi - lo) / (2 * r + 1)


def _blur(a, sigma):
    """Gaussian blur of a float array, approximated by three box passes per axis
    (PIL only blurs 8-bit images, which bands smooth gradients)."""
    a = a.astype(np.float32)
    r = int(round((np.sqrt(4 * sigma * sigma + 1) - 1) / 2))  # 3 boxes of 2r+1 ~ sigma
    for axis in (0, 1):
        for _ in range(3):
            a = _box(a, r, axis)
    return a


def lay(photo, ink_left, ink_top, ink_width, displace=3.0, opacity=0.94,
        texture=0.0, blur=0.6, stitch=0.0):
    """photo: RGB PIL image. ink_left/top/width: where the logo's INK goes, in
    photo pixels (floats allowed, may run off the frame). texture: 0..1, how much
    the knit breaks up the ink (use ~0.35 at macro scale). stitch: width of one
    knit stitch in photo pixels; when set (about 6 or more), the ink is laid the way
    DTG ink sits on cotton (see _dtg)."""
    logo = Image.open(LOGO).convert('RGBA')
    la = np.array(logo)[..., 3]
    x0, y0, x1, y1 = _ink_bbox(la)
    s = ink_width / (x1 - x0)
    W, H = photo.size
    # Render only the part of the logo that lands on the photo, at full resolution.
    full_w, full_h = logo.width * s, logo.height * s
    off_x = ink_left - x0 * s
    off_y = ink_top - y0 * s
    alpha = np.zeros((H, W), np.float32)
    # visible window in logo coords
    vx0, vy0 = max(0, -off_x / s), max(0, -off_y / s)
    vx1, vy1 = min(logo.width, (W - off_x) / s), min(logo.height, (H - off_y) / s)
    if vx1 > vx0 and vy1 > vy0:
        box = (int(np.floor(vx0)), int(np.floor(vy0)), int(np.ceil(vx1)), int(np.ceil(vy1)))
        crop = logo.crop(box).split()[3]
        tw, th = max(1, round((box[2] - box[0]) * s)), max(1, round((box[3] - box[1]) * s))
        crop = crop.resize((tw, th), Image.LANCZOS)
        px, py = round(off_x + box[0] * s), round(off_y + box[1] * s)
        a = np.array(crop, np.float32) / 255
        sx0, sy0 = max(0, px), max(0, py)
        sx1, sy1 = min(W, px + tw), min(H, py + th)
        alpha[sy0:sy1, sx0:sx1] = a[sy0 - py:sy1 - py, sx0 - px:sx1 - px]
    img = np.array(photo.convert('RGB'), np.float32)
    lum = img.mean(2)
    # Bend with the folds: shift the ink along the shading gradient.
    sm = np.array(Image.fromarray(lum.astype(np.uint8)).filter(ImageFilter.GaussianBlur(6)), np.float32)
    gy, gx = np.gradient(sm)
    mag = max(float(np.abs(gx).max()), float(np.abs(gy).max()), 1e-6)
    dx, dy = gx / mag * displace, gy / mag * displace
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    alpha = _bilinear(alpha, np.clip(xx - dx, 0, W - 1.001), np.clip(yy - dy, 0, H - 1.001))
    if blur:
        alpha = np.array(Image.fromarray((alpha * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(blur)), np.float32) / 255
    # Light and shadow of the fabric carried onto the ink.
    local = np.array(Image.fromarray(lum.astype(np.uint8)).filter(ImageFilter.GaussianBlur(18)), np.float32)
    ref = np.percentile(local[alpha > 0.5], 70) if (alpha > 0.5).any() else local.mean()
    shade = np.clip(0.93 + 0.5 * (local - ref) / 255 * 4, 0.6, 1.05)
    ink = np.stack([235 * shade, 233 * shade, 228 * shade], 2)
    if texture:
        hp = lum - np.array(Image.fromarray(lum.astype(np.uint8)).filter(ImageFilter.GaussianBlur(3)), np.float32)
        hp = hp / (np.abs(hp).max() + 1e-6)
        alpha = alpha * np.clip(1 - texture * (0.5 - hp), 0, 1)
        ink = ink * (1 + 0.25 * texture * hp)[..., None]
    if stitch >= 6:
        alpha, ink = _dtg(alpha, ink, lum, stitch)
    a3 = (alpha * opacity)[..., None]
    out = img * (1 - a3) + np.clip(ink, 0, 255) * a3
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


def _dtg(alpha, ink, lum, stitch):
    """Direct-to-garment ink at macro scale. The water-based white is sprayed onto
    the knit and soaks in, so: it coats the raised tops of the loops fully and thins
    in the gaps between them (coverage follows the knit relief); the letter edges
    are decided loop by loop rather than by the vector outline (edge threshold
    moved by the relief); the ink carries the fibre texture underneath it (matte,
    never smooth); and the odd surface fibre hair stands up through the ink and
    stays dark. lum is the plain fabric's luminance, stitch the stitch width in px.
    All of it fades in with magnification (full at about 30 px per stitch): from
    arm's length DTG reads as solid matte white, and the knit only shows up close."""
    k = float(np.clip((stitch - 4) / 26, 0.15, 1.0))
    # Knit relief: brightness relative to the stitch-scale neighbourhood, -1..1.
    rel = lum - _blur(lum, stitch * 0.9)
    rel = _blur(rel, max(0.8, stitch * 0.04))
    rel = np.clip(rel / (np.percentile(np.abs(rel), 95) + 1e-6), -1, 1)
    # Edges: soften the outline to about a sixth of a stitch, then cut it at a
    # threshold the relief pushes up and down, so edges step along the loops.
    soft = _blur(alpha, max(1.0, stitch * 0.16))
    t = 0.5 - 0.22 * k * rel
    edge = np.clip((soft - t) / 0.08 + 0.5, 0, 1)
    edge = edge * edge * (3 - 2 * edge)
    # Coverage: full on loop tops, thinner in the valleys between them.
    cover = np.clip(1 - k * (0.20 - 0.30 * rel), 0.55, 1.0)
    # Fibre hairs: thin bright lines in the bare fabric are loose fibres; over the
    # ink they read as dark hairs, so they punch small holes in the coverage.
    hf = lum - _blur(lum, max(1.0, stitch * 0.05))
    hair = np.clip((hf - np.percentile(hf, 99.2)) / (np.abs(hf).max() * 0.3 + 1e-6), 0, 1)
    a = edge * cover * (1 - 0.65 * k * hair)
    # Ink tone: brighter on loop tops, greyer where thin, with the fibre grain.
    grain = np.clip(hf / (np.percentile(np.abs(hf), 98) + 1e-6), -1, 1)
    tone = 0.93 - 0.03 * k + k * (0.12 * rel + 0.06 * grain)
    return a, ink * tone[..., None]
