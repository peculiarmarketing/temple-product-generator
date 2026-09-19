#!/usr/bin/env python
"""Put a retired flat-lay colourway back into a temple's archive.

ONE-TIME MIGRATION, not pipeline. Changing FLAT in build_product_gallery.py picks
a different colourway for the two flat lays, but on a catalogue that has already
been built the old --prune deleted every flat except the one colour it kept. The
new colour is gone from Shopify and has to come back off disk before --reface can
upload it.

Sources, in order:
  1. flat-originals/catalog/{handle}/   every original, archived before the
                                        background recolour deleted them
  2. .flatcache/{garment}/              the classifier's download cache

Writes flat-originals/{temple-slug}/{garment}_{colour}_{back,front}.png, which is
exactly where --reface's fallback looks. Future sweeps need none of this: a fresh
product still carries all its flats, so --reface finds the colour live.

Back and front are told apart PAIRWISE, the same rule build_product_gallery uses:
within one colour the shot with more near-white ink in the centre is the back. An
absolute threshold is tuned to whichever garment it was measured on and silently
mislabels the others.

  --garment tee --colour maroon [--dry-run]
"""
import argparse
import glob
import json
import re
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SPIKE = ROOT / "artifacts/photo-mockup-spike"
sys.path.insert(0, str(SPIKE))
sys.path.insert(0, str(ROOT))
import normalize  # noqa: E402
from shopify_client import ShopifyClient  # noqa: E402

PRETTY = {"navy-blue": "Navy Blue", "royal-blue": "Royal Blue", "dark-gray": "Dark Gray",
          "gray": "Gray", "black": "Black", "coffee": "Coffee", "mauve": "Mauve",
          "maroon": "Maroon"}
QUERY = {"tee": "title:*Heavyweight Temple Tee*", "hoodie": "title:*Temple Hoodie*",
         "crew": "title:*Temple Sweatshirt*"}


def slug(t):
    return re.sub(r"[^A-Za-z0-9]+", "-", t).strip("-").lower()


def measure(path, swatches):
    """(colour name, centre ink fraction) for one flat lay."""
    im = Image.open(path)
    a = np.asarray(im.convert("RGB"), dtype=float)
    bg = normalize.border_region(im)
    body = a[~bg]
    body = body[body.min(axis=1) <= 200]
    if not len(body):
        return None, 0.0
    med = np.median(body, axis=0)
    best = min(swatches.items(),
               key=lambda kv: float(np.linalg.norm(med - np.array(kv[1], dtype=float))))
    h, w = a.shape[:2]
    mid = a[int(h * .4):int(h * .6), int(w * .4):int(w * .6)]
    return best[0], float((mid.min(axis=2) > 200).mean())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--garment", required=True, choices=sorted(QUERY))
    ap.add_argument("--colour", required=True, choices=sorted(PRETTY))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    swatches = json.loads((SPIKE / "true_colors_all.json").read_text())[args.garment]
    want = PRETTY[args.colour]

    sc = ShopifyClient()
    prods = [n for n in sc.gql(
        "query($c:String){products(first:250,query:$c){nodes{title status handle}}}",
        {"c": QUERY[args.garment]})["products"]["nodes"] if n["status"] == "ACTIVE"]

    done, already, missing = 0, 0, []
    for n in sorted(prods, key=lambda x: x["title"]):
        m = re.search(r"\(([^)]+)\)$", n["title"])
        temple = m.group(1) if m else "Salt Lake"
        dest = SPIKE / "flat-originals" / slug(temple)
        if (dest / f"{args.garment}_{args.colour}_back.png").exists() and \
           (dest / f"{args.garment}_{args.colour}_front.png").exists():
            already += 1
            continue

        pool = sorted(glob.glob(str(SPIKE / "flat-originals/catalog" / n["handle"] / "*.png")))
        if not pool:
            pool = sorted(glob.glob(str(SPIKE / ".flatcache" / args.garment / "*.png")))
        hits = []
        for f in pool:
            colour, ink = measure(f, swatches)
            if colour == want:
                hits.append((ink, f))
        if len(hits) < 2:
            missing.append((temple, len(hits)))
            continue
        hits.sort(reverse=True)                     # most centre ink first = the back
        if not args.dry_run:
            dest.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(hits[0][1], dest / f"{args.garment}_{args.colour}_back.png")
            shutil.copyfile(hits[1][1], dest / f"{args.garment}_{args.colour}_front.png")
        done += 1
        print(f"  {temple:22s} back ink {hits[0][0]*100:5.2f}%  front ink {hits[1][0]*100:5.2f}%")

    print(f"\n{'would restore' if args.dry_run else 'restored'} {done}, "
          f"already present {already}, could not find a pair for {len(missing)}")
    for t, k in missing:
        print(f"   {t}: found {k} {want} flat(s), need 2")
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
