"""Render one hand-off of the dive as video frames, with the same math the canvas
engine uses (pp-quality.js, initDive): an exponential zoom toward the fixed point of
the next frame's square, and the next frame faded in over that square with soft
edges that narrow to nothing at the hand-off. Used where a generated video segment
warped the lettering, since this only ever moves the real frames.

usage: render_seg.py A.png B.png x y w out_dir [size] [frames]
(x, y, w: the square of B inside A, in A's pixels)"""
import sys, os
import numpy as np
from PIL import Image, ImageFilter

a_path, b_path, x, y, w, out = sys.argv[1:7]
size = int(sys.argv[7]) if len(sys.argv) > 7 else 1440
n = int(sys.argv[8]) if len(sys.argv) > 8 else 121
A = Image.open(a_path).convert('RGB'); B = Image.open(b_path).convert('RGB')
N = A.width
rx, ry, rw = float(x) / N, float(y) / N, float(w) / N
fx, fy = rx / (1 - rw), ry / (1 - rw)
os.makedirs(out, exist_ok=True)

def ease(t):  # same reading pace as the page: slower near each end
    return t - np.sin(2 * np.pi * t) / (2 * np.pi) * 0.7

for i in range(n):
    t = ease(i / (n - 1))
    sz = rw ** t
    ox, oy = fx * (1 - sz), fy * (1 - sz)
    frame = A.resize((size, size), Image.LANCZOS, box=(ox * N, oy * N, (ox + sz) * N, (oy + sz) * N))
    alpha = min(1, max(0, (t - 0.22) / 0.55))
    if alpha > 0:
        u = size / sz
        dx, dy, ds = (rx - ox) * u, (ry - oy) * u, rw * u
        f = max(0.0, 0.14 * (1 - t)) * ds
        # draw B at its square (only the part on screen)
        x0, y0 = max(0, int(np.floor(dx))), max(0, int(np.floor(dy)))
        x1, y1 = min(size, int(np.ceil(dx + ds))), min(size, int(np.ceil(dy + ds)))
        bw = B.width
        box = tuple(min(bw, max(0.0, v)) for v in
                    ((x0 - dx) / ds * bw, (y0 - dy) / ds * bw, (x1 - dx) / ds * bw, (y1 - dy) / ds * bw))
        patch = np.asarray(B.resize((x1 - x0, y1 - y0), Image.LANCZOS, box=box), np.float32)
        yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32) + 0.5
        if f > 0.5:
            m = np.clip(np.minimum.reduce([xx - dx, dx + ds - xx, yy - dy, dy + ds - yy]) / f, 0, 1)
            m = m * m * (3 - 2 * m)
        else:
            m = np.ones_like(xx)
        base = np.asarray(frame, np.float32)
        k = (m * alpha)[..., None]
        base[y0:y1, x0:x1] = base[y0:y1, x0:x1] * (1 - k) + patch * k
        frame = Image.fromarray(base.clip(0, 255).astype(np.uint8))
    frame.save(f'{out}/f{i:04d}.png')
print('rendered', n, 'frames to', out)
