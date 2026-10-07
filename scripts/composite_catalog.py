#!/usr/bin/env python
"""Composite every temple onto the on-model colourway photos, one garment at a time.

composite_set.py does one temple. This does the catalogue, and it loads the
colourway photos and the geometry once rather than 45 times.

CENTRE ANCHORED, via print_geometry.json's print_centre_below_collar_in. Read the
_anchor note there before touching placement: temple artwork is normalised to
about 12in wide but runs 7.45in to 15.34in tall, so where the block sits is the
whole question and it is already settled.

  --garment tee --outdir DIR [--temple NAME ...] [--force]
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SPIKE = ROOT / "artifacts/photo-mockup-spike"
sys.path.insert(0, str(SPIKE))
from composite import build, load_art  # noqa: E402
from composite_set import quad_for  # noqa: E402

Image.MAX_IMAGE_PIXELS = None
TEMPLES = ROOT.parent.parent / "Temples"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--garment", required=True, choices=("tee", "crew", "hoodie"))
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--temple", action="append", help="repeatable; default is all")
    ap.add_argument("--displace", type=float, default=3.0)
    ap.add_argument("--force", action="store_true", help="redo temples already written")
    args = ap.parse_args()

    geometry = json.loads((SPIKE / "print_geometry.json").read_text())
    geo, fold = geometry[args.garment], geometry["fold"]
    out = Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)

    # the blank colourway photos, loaded once
    photos = {}
    for f in sorted((SPIKE / "colourway-photos").glob(f"{args.garment}_*.png")):
        photos[f.stem] = np.asarray(Image.open(f).convert("RGB"), dtype=np.float64)
    if not photos:
        raise SystemExit(f"no {args.garment} colourway photos in {SPIKE/'colourway-photos'}")
    print(f"{len(photos)} colourway photos: {', '.join(sorted(photos))}\n")

    names = args.temple or sorted(
        d.name for d in TEMPLES.iterdir()
        if d.is_dir() and (d / f"{d.name} {args.garment} white back print (auto).png").exists())
    print(f"{len(names)} temples with a {args.garment} print file\n")

    t0, done, skipped = time.time(), 0, 0
    for i, name in enumerate(names, 1):
        dst = out / name
        art_path = TEMPLES / name / f"{name} {args.garment} white back print (auto).png"
        if not art_path.exists():
            print(f"  {name}: no print file, skipped")
            continue
        if not args.force and dst.exists() and len(list(dst.glob("*.jpg"))) == len(photos):
            skipped += 1
            continue
        dst.mkdir(parents=True, exist_ok=True)
        quad, ppi, w_in, h_in = quad_for(
            art_path, geo["collar"], geo["hem"], geo["centre"], geo["length_in"],
            geo["ink_top_below_collar_in"], geo.get("scale_nudge", 1.0),
            geo.get("print_centre_below_collar_in"))
        art = load_art(str(art_path), quad)
        for stem, rgb in photos.items():
            img, _ = build(rgb, art, quad, args.displace, fold["shade_gain"], 0.35, 0.93, scale=1.0,
                           fold_strength=fold["strength"], fold_band=fold["band_px"])
            Image.fromarray(img).save(dst / f"{stem}.jpg", quality=94)
        done += 1
        el = time.time() - t0
        print(f"  [{i}/{len(names)}] {name:24s} {w_in:5.2f} x {h_in:5.2f} in   "
              f"{el/60:.1f} min elapsed, ~{(el/done)*(len(names)-i)/60:.0f} min left")
    print(f"\ncomposited {done} temple(s), skipped {skipped} already done, "
          f"{done*len(photos)} images in {(time.time()-t0)/60:.1f} min")


if __name__ == "__main__":
    main()
