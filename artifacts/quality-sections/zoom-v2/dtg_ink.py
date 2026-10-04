"""Swap in model-rendered DTG ink on a chain frame without letting the letters move.

The image model (gpt_image_2_5 sunburst) re-renders a frame with the ink looking
like a real white DTG print on cotton, but it redraws the whole picture, so its
fabric and letter edges drift a little. This keeps the original frame and takes
the generated pixels only where they are ink: brighter than the original fabric,
and inside the true letter shapes grown by about half a knit stitch. The letter
mask is the difference between the finished frame and its logo-free base, so it
is exactly where printlay put the real logo. Outside that zone the frame is byte
for byte the old one, which keeps every hand-off in the zoom where it was.

    python dtg_ink.py chain3/K2.png chain3/K2a_raw.png gen.png 16 4 3 chain3/K2dtg.png
    python dtg_ink.py chain3/K1.png chain3/K1a_raw.png gen.png 4 1.0 1.2 chain3/K1dtg.png
"""
import sys
import numpy as np
from PIL import Image, ImageFilter


def _rgb(f):
    return np.asarray(Image.open(f).convert('RGB').resize((2048, 2048), Image.LANCZOS), np.float32)


def _u8(a):
    return Image.fromarray(np.clip(a * 255, 0, 255).astype(np.uint8))


def _f(im):
    return np.asarray(im, np.float32) / 255


def composite(orig, base, gen, grow, close, feather):
    o, b, g = _rgb(orig), _rgb(base), _rgb(gen)
    d = np.clip((o.mean(2) - b.mean(2) - 6) / 40, 0, 1)
    letters = _f(_u8(d).filter(ImageFilter.GaussianBlur(close))) > 0.35
    zone = _f(_u8(letters.astype(float)).filter(ImageFilter.MaxFilter(2 * grow + 1)).filter(ImageFilter.GaussianBlur(feather)))
    a = np.clip((g.mean(2) - o.mean(2) - 12) / 55, 0, 1)
    a = _f(_u8(a).filter(ImageFilter.GaussianBlur(0.6))) * zone
    # inside the solid letters take the generated ink fully, so its knit relief survives
    core = _f(_u8(letters.astype(float)).filter(ImageFilter.MinFilter(5)).filter(ImageFilter.GaussianBlur(1.5)))
    a = np.maximum(a, core)
    out = o * (1 - a[..., None]) + g * a[..., None]
    ink = a > 0.5
    iou = (ink & letters).sum() / max(1, (ink | letters).sum())
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)), iou


if __name__ == '__main__':
    orig, base, gen, grow, close, feather, out = sys.argv[1:8]
    im, iou = composite(orig, base, gen, int(grow), float(close), float(feather))
    im.save(out)
    print(out, 'ink IoU vs letters %.3f' % iou)
