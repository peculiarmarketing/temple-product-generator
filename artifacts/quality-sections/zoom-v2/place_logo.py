"""Print the real logo onto a worn shirt: same proportions on every frame.

Size: 0.73 of the collar's outer width. Position: centred on the shirt's centre
front (the lowest point of the collar curve), its top 0.59 logo widths below the
collar band, measured along the slanted centre line. Angle: the logo is rotated
to the slope of the shirt across the chest. It then bends with the fabric: the
ink is displaced along the shirt's own shading (folds), and takes the shirt's
light and shadow. Hands, straps and skin stay in front.
"""
import sys
import numpy as np
from PIL import Image, ImageFilter
sys.path.insert(0, __import__('os').path.dirname(__file__))
from printlay import LOGO, _bilinear



def _fblur(a, r, n=3):
    # float box blur repeated n times (close to a Gaussian), no 8-bit clipping
    for _ in range(n):
        p = np.pad(a, r, mode='edge').cumsum(0).cumsum(1)
        p = np.pad(p, ((1, 0), (1, 0)))
        k = 2 * r + 1
        a = (p[k:, k:] - p[:-k, k:] - p[k:, :-k] + p[:-k, :-k]) / (k * k)
    return a


def _logo_alpha(width):
    lg = Image.open(LOGO).convert('RGBA')
    a = np.array(lg)[..., 3]
    ys, xs = np.nonzero(a > 20)
    crop = lg.crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1)).split()[3]
    s = width / crop.width
    return crop.resize((max(1, round(crop.width * s)), max(1, round(crop.height * s))), Image.LANCZOS)


def place(frame, front, collar_w, angle_deg, bend=3.5, out=None):
    im = Image.open(frame).convert('RGB')
    img = np.asarray(im, np.float32)
    H, W = img.shape[:2]
    Lw = 0.73 * collar_w
    la = _logo_alpha(Lw)
    lh = la.height
    th = np.radians(angle_deg)
    down = np.array([-np.sin(th), np.cos(th)])          # along the slanted centre line
    centre = np.array(front, float) + down * (0.59 * Lw + lh / 2)
    # rotate (PIL rotates counter-clockwise for positive angles)
    rot = la.rotate(-angle_deg, resample=Image.BICUBIC, expand=True)
    alpha = np.zeros((H, W), np.float32)
    px, py = int(round(centre[0] - rot.width / 2)), int(round(centre[1] - rot.height / 2))
    alpha[py:py + rot.height, px:px + rot.width] = np.asarray(rot, np.float32) / 255
    # shirt mask: dark, neutral fabric
    lum = img.mean(2)
    shirt = ((lum < 85) & (img.max(2) - img.min(2) < 28)).astype(np.uint8) * 255
    # close the fabric's light texture specks so the mask is solid cloth, then
    # keep only what is clearly not a hand, strap or skin
    solid = Image.fromarray(shirt).filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.MinFilter(13))
    # anything clearly not black cloth (skin, khaki straps, highlights on a hand),
    # grown by a few pixels, is always in front of the print
    notcloth = (((img.max(2) - img.min(2)) > 30) | (lum > 110)).astype(np.uint8) * 255
    notcloth = Image.fromarray(notcloth).filter(ImageFilter.MinFilter(3)).filter(ImageFilter.MaxFilter(11))
    keep = (np.asarray(solid) > 0) & (np.asarray(notcloth) == 0)
    shirt_m = np.asarray(Image.fromarray(keep.astype(np.uint8) * 255).filter(ImageFilter.GaussianBlur(1.2)), np.float32) / 255
    # bend with the folds: displacement from the shirt's own shading only
    fab = np.where(shirt > 0, lum, np.nan)
    fill = np.nanmean(fab[max(0, py - 50):py + rot.height + 50, max(0, px - 50):px + rot.width + 50])
    fl = np.where(np.asarray(solid) > 0, lum, fill).astype(np.float32)
    sm = _fblur(fl.astype(np.float64), 9)
    gy, gx = np.gradient(sm)
    region = alpha > 0.01
    mag = np.percentile(np.hypot(gx, gy)[region], 95) if region.any() else 1
    dx, dy = gx / (mag + 1e-6) * bend, gy / (mag + 1e-6) * bend
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    alpha = _bilinear(alpha, np.clip(xx - dx, 0, W - 1.001), np.clip(yy - dy, 0, H - 1.001))
    alpha = np.asarray(Image.fromarray((alpha * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.55)), np.float32) / 255
    # fabric light and shadow on the ink, plus a little knit texture
    local = _fblur(fl.astype(np.float64), 12)
    ref = np.percentile(local[alpha > 0.5], 60) if (alpha > 0.5).any() else local.mean()
    shade = np.clip(0.92 + (local - ref) / 255 * 3.0, 0.62, 1.05)
    hp = lum - np.asarray(Image.fromarray(lum.astype(np.uint8)).filter(ImageFilter.GaussianBlur(2)), np.float32)
    tex = 1 + 0.006 * np.clip(hp, -12, 12)
    ink = np.stack([236 * shade, 234 * shade, 229 * shade], 2) * tex[..., None]
    a3 = (alpha * 0.95 * shirt_m)[..., None]
    res = img * (1 - a3) + np.clip(ink, 0, 255) * a3
    Image.fromarray(np.clip(res, 0, 255).astype(np.uint8)).save(out)
    return centre, Lw


if __name__ == '__main__':
    pass
