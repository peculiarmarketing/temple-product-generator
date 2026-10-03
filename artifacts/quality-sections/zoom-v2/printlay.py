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


def lay(photo, ink_left, ink_top, ink_width, displace=3.0, opacity=0.94,
        texture=0.0, blur=0.6):
    """photo: RGB PIL image. ink_left/top/width: where the logo's INK goes, in
    photo pixels (floats allowed, may run off the frame). texture: 0..1, how much
    the knit breaks up the ink (use ~0.35 at macro scale)."""
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
    a3 = (alpha * opacity)[..., None]
    out = img * (1 - a3) + np.clip(ink, 0, 255) * a3
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))
