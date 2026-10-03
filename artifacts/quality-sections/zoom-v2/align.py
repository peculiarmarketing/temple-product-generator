"""Measure how a generated close-up actually lines up with the crop it was made from.

The model re-renders the reference crop rather than copying it, so the folds land a
little off in position and scale. This finds the scale and shift that best overlay
the child image on the reference (edge maps, normalised correlation, coarse-to-fine
search) and returns the corrected crop rectangle in parent-image pixels. The zoom then
hands off at that exact rectangle, which is what makes the switch invisible.
"""
import numpy as np
from PIL import Image, ImageFilter


def _edges(im, size):
    g = im.convert('L').resize((size, size), Image.LANCZOS).filter(ImageFilter.GaussianBlur(1.2))
    a = np.array(g, np.float32)
    gy, gx = np.gradient(a)
    e = np.hypot(gx, gy)
    # PIL cannot blur float images, so blur an 8-bit copy of the edge map
    e8 = Image.fromarray(np.uint8(np.clip(e / (e.max() + 1e-6) * 255, 0, 255)))
    e = np.array(e8.filter(ImageFilter.GaussianBlur(2)), np.float32)
    return (e - e.mean()) / (e.std() + 1e-6), (a - a.mean()) / (a.std() + 1e-6)


def _score(ref, child, s, dx, dy, size):
    # child scaled by s about the centre and shifted (dx, dy) in ref pixels
    c = Image.fromarray(child)
    w = int(round(size * s))
    c = np.array(c.resize((w, w), Image.BILINEAR), np.float32)
    ox = int(round((size - w) / 2 + dx)); oy = int(round((size - w) / 2 + dy))
    x0, y0 = max(0, ox), max(0, oy); x1, y1 = min(size, ox + w), min(size, oy + w)
    if x1 - x0 < size * 0.6 or y1 - y0 < size * 0.6:
        return -1
    a = ref[y0:y1, x0:x1]; b = c[y0 - oy:y1 - oy, x0 - ox:x1 - ox]
    a = a - a.mean(); b = b - b.mean()
    return float((a * b).sum() / (np.sqrt((a * a).sum() * (b * b).sum()) + 1e-6))


def align(ref_img, child_img, parent_rect, size=256):
    """ref_img: the upscaled reference crop; child_img: the generated image;
    parent_rect: (x0, y0, x1, y1) of the crop in the parent. Returns
    (corrected_rect, scale, dx, dy, score)."""
    re_, rl = _edges(ref_img, size)
    ce, cl = _edges(child_img, size)
    ref = re_ + 0.5 * rl; child = ce + 0.5 * cl
    best = (-2, 1, 0, 0)
    for s in np.linspace(0.85, 1.15, 31):
        for dx in range(-24, 25, 3):
            for dy in range(-24, 25, 3):
                v = _score(ref, child, s, dx, dy, size)
                if v > best[0]:
                    best = (v, s, dx, dy)
    v, s, dx, dy = best
    for s2 in np.linspace(s - 0.01, s + 0.01, 5):
        for dx2 in np.arange(dx - 3, dx + 3.1, 1):
            for dy2 in np.arange(dy - 3, dy + 3.1, 1):
                v2 = _score(ref, child, s2, dx2, dy2, size)
                if v2 > best[0]:
                    best = (v2, s2, dx2, dy2)
    v, s, dx, dy = best
    # child covers, in ref pixels (0..size), the square centred at size/2+d with width size*s
    x0, y0, x1, y1 = parent_rect
    pw = x1 - x0
    k = pw / size
    cw = size * s
    cx0 = (size - cw) / 2 + dx
    cy0 = (size - cw) / 2 + dy
    rect = (x0 + cx0 * k, y0 + cy0 * k, x0 + (cx0 + cw) * k, y0 + (cy0 + cw) * k)
    return rect, s, dx * k, dy * k, v
