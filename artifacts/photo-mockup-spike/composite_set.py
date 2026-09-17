#!/usr/bin/env python
"""Composite the temple print onto every colourway photo, at TRUE physical size.

Sizing is derived from inches, not from ratios measured off a mockup. The
earlier ratio method rendered the temple 0.9% too wide on the tee, 6.9% on the
crew and 9.1% on the hoodie, because a ratio taken from a flat lay does not
survive the move onto a worn garment.

The chain is exact:
  - the print file is 300 dpi at final size, so Salt Lake's ink measures
    11.98 x 14.87 in with the location text 0.70 in tall, on every garment;
  - the size guide gives Length, collar to hem, for the size the model wears;
  - collar and hem are marked on each base photo.
Therefore px_per_inch = (hem - collar) / length_in, and the art is drawn at
px_per_inch / 300 of its file size. Nothing else is needed and no ratio is
involved.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from composite import build, load_art  # noqa: E402

Image.MAX_IMAGE_PIXELS = None
FILE_DPI = 300.0


def quad_for(art_path, collar, hem, centre, length_in, top_below_collar_in,
             scale_nudge=1.0):
    px_per_in = (hem - collar) / length_in
    # scale_nudge is art direction, not physics. At 1.0 the temple prints at its
    # true 11.98in. Anything else deliberately breaks that, so it is a visible
    # per-garment number rather than a tweak buried in the maths. If a garment
    # consistently needs a nudge, the real cause is probably a wrong length_in,
    # i.e. the model is wearing a different size than assumed.
    scale = px_per_in / FILE_DPI * scale_nudge

    art_im = Image.open(art_path)
    a = np.array(art_im)
    ys, xs = np.nonzero(a[..., 3] > 10)

    cw, ch = art_im.width * scale, art_im.height * scale
    ink_w = (xs.max() - xs.min()) * scale
    ink_top = collar + top_below_collar_in * px_per_in

    left = (centre - ink_w / 2) - xs.min() * scale
    top = ink_top - ys.min() * scale
    quad = [(left, top), (left + cw, top), (left + cw, top + ch), (left, top + ch)]
    return quad, px_per_in, ink_w / px_per_in, (ys.max() - ys.min()) * scale / px_per_in


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--indir", required=True)
    p.add_argument("--outdir", required=True)
    p.add_argument("--temple-dir", required=True)
    p.add_argument("--temple", default="Salt Lake")
    p.add_argument("--geometry", required=True, help="print_geometry.json")
    p.add_argument("--displace", type=float, default=3.0)
    args = p.parse_args()

    geo = json.load(open(args.geometry))
    src, dst = Path(args.indir), Path(args.outdir)
    dst.mkdir(parents=True, exist_ok=True)
    td = Path(args.temple_dir)

    for garment in ("tee", "crew", "hoodie"):
        g = geo[garment]
        art = td / f"{args.temple} {garment} white back print (auto).png"
        if not art.exists():
            print(f"{garment}: no print file, skipped")
            continue
        quad, ppi, w_in, h_in = quad_for(
            art, g["collar"], g["hem"], g["centre"],
            g["length_in"], g["ink_top_below_collar_in"],
            g.get("scale_nudge", 1.0))
        art_arr = load_art(str(art), quad)
        nudge = g.get("scale_nudge", 1.0)
        flag = "" if nudge == 1.0 else f"   nudge x{nudge}"
        print(f"{garment}: {ppi:.2f} px/in  temple {w_in:.2f} x {h_in:.2f} in  "
              f"top {g['ink_top_below_collar_in']:.1f} in below collar{flag}")
        for f in sorted(src.glob(f"{garment}_*.png")):
            rgb = np.asarray(Image.open(f).convert("RGB"), dtype=np.float64)
            out, _ = build(rgb, art_arr, quad, args.displace, 1.0, 0.35, 0.93, scale=1.0)
            Image.fromarray(out).save(dst / f"{f.stem}.jpg", quality=94)


if __name__ == "__main__":
    main()
