#!/usr/bin/env python
"""Run the standard gallery build across every live per-temple product.

Per Evan, 18 Sep 2026: the Salt Lake tee is the template and this is the process
for every product from here. Each product ends up with the eleven slots in
docs/photo-mockup-plan.md, all 1:1 and all on the tee's own light gray except the
temple art card, which stays white.

Three stages per product, the same ones build_product_gallery.py exposes:

  --add     the five on-model backs for THIS temple, the three fabric details,
            and each colour variant bound to its own on-model shot. Additive.
  --reface  gives the two Black flat lays deterministic alt text so slots 2 and
            last stop depending on the pixel classifier. Additive.
  --prune   deletes the eight surplus flat lays and orders the gallery.

NAME MISMATCHES. The alt text has to follow the PRODUCT title, but the composites
live under the TEMPLE FOLDER name, and two disagree. ALIASES maps them. Getting
this backwards publishes "Ogden (original) Temple back print on model" onto a
product titled "(Ogden Original)", which then fails to match on any later run.

Safe to re-run. Every stage skips what is already present.

  --dry-run      print the plan, change nothing
  --temple NAME  repeatable, product-title name; default is all 44
  --limit N
"""
import argparse
import io
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from shopify_client import ShopifyClient  # noqa: E402

PY = str(ROOT / ".venv.nosync/bin/python")
BUILDER = str(ROOT / "scripts/build_product_gallery.py")
# One live product line per garment. Each has 44 per-temple products whose title
# ends in "(Temple)", plus one bare title which is Salt Lake and is already built.
QUERY = {"tee": "title:*Heavyweight Temple Tee*",
         "hoodie": "title:*Temple Hoodie*",
         "crew": "title:*Temple Sweatshirt*"}

# product-title name -> temple folder name on disk
ALIASES = {"Ogden Original": "Ogden (original)", "Washington D.C.": "Washington DC"}

# Five folders carry a trailing asterisk the product titles do not: Heber Valley*,
# Lehi*, Provo Rock Canyon*, Spanish Fork*, West Jordan*. Nothing in the repo
# records what it marks, so it is treated as a folder-name marker only and
# stripped for matching. Do not propagate it into alt text.
def folder_for(comps, temple):
    for cand in (ALIASES.get(temple, temple), temple, temple + "*"):
        d = comps / cand
        if d.is_dir():
            return d
    return None


def temple_of(title):
    m = re.search(r"\(([^)]+)\)$", title)
    return m.group(1) if m else "Salt Lake"


ORIGINALS = ROOT / "artifacts/photo-mockup-spike/flat-originals"


def originals_dir(temple):
    return ORIGINALS / re.sub(r"[^A-Za-z0-9]+", "-", temple).strip("-").lower()


def _print_mask(img, size=192):
    """Binary mask of the near-white print inside the central back panel."""
    sys.path.insert(0, str(ROOT / "artifacts/photo-mockup-spike"))
    import normalize
    a = np.asarray(img.convert("RGB"), dtype=np.float32)
    bg = normalize.border_region(img)
    h, w = a.shape[:2]
    box = np.zeros((h, w), bool)
    box[int(h * .25):int(h * .80), int(w * .25):int(w * .75)] = True
    m = (a.min(axis=2) > 170) & (~bg) & box
    return np.asarray(Image.fromarray((m * 255).astype(np.uint8)).resize((size, size)),
                      dtype=np.float32) / 255.0


def _iou(x, y, t=0.35):
    a, b = x > t, y > t
    u = (a | b).sum()
    return float((a & b).sum() / u) if u else 0.0


def verify(prod, temple, garment):
    """Prove the BACK flat lay really shows THIS product's temple.

    The check that would have caught 18 Sep 2026's mistake on its first product
    rather than its forty-fourth: a flat lay reading "SALT LAKE CITY, UTAH" went
    onto Boise under a "Boise Temple" alt, because the archive the fallback drew
    on was not temple scoped. Alt text cannot catch that, since the same code
    wrote the alt and picked the file. Only the pixels can.

    Compare the PRINT, not the photo. A first attempt correlated whole garments
    and passed Boise against Albuquerque's originals, because the blank tee is
    identical between temples and swamps the few percent of pixels that differ.
    Isolating the near-white linework in the central back panel and taking
    intersection-over-union separates them completely: measured 1.000 against its
    own original and 0.047 to 0.072 against three other temples.

    Only the back is checked. The front carries the chest logo, which is the same
    on every temple by design, so there is nothing there to tell them apart.
    """
    # Compares against the white original --reface archived for THIS temple.
    # Background replacement does not touch the print, so a gray live flat still
    # scores 1.000 against its own white original.
    arch = sorted(originals_dir(temple).glob(f"{garment}_*_back.*"))
    if not arch:
        return [f"no archived back original for {temple}, cannot verify"]
    backs = [m for m in prod["media"]["nodes"]
             if "back print flat lay" in (m.get("alt") or "")]
    if not backs:
        return ["no back flat lay in the gallery"]
    problems = []
    for m in backs:
        req = urllib.request.Request(m["image"]["url"],
                                     headers={"User-Agent": "Mozilla/5.0"})
        live = _print_mask(Image.open(io.BytesIO(
            urllib.request.urlopen(req, timeout=90).read())))
        best = max(_iou(live, _print_mask(Image.open(f))) for f in arch)
        if best < 0.50:
            problems.append(f"{m.get('alt')!r} does not match any original of this "
                            f"product (best print IoU {best:.3f}). It is almost "
                            "certainly another temple's flat lay.")
    return problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--garment", required=True, choices=sorted(QUERY))
    ap.add_argument("--composites", required=True,
                    help="dir of {Temple}/{garment}_{colour}.jpg")
    ap.add_argument("--temple", action="append")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--stages", default="add,reface,prune")
    ap.add_argument("--verify", action="store_true",
                    help="check each finished gallery instead of building it")
    args = ap.parse_args()

    comps = Path(args.composites)
    sc = ShopifyClient()
    prods = [n for n in sc.gql(
        "query($c:String){products(first:250,query:$c){nodes{id title status handle}}}",
        {"c": QUERY[args.garment]})["products"]["nodes"] if n["status"] == "ACTIVE"]

    todo = []
    for n in sorted(prods, key=lambda x: x["title"]):
        t = temple_of(n["title"])
        if t == "Salt Lake":
            continue                       # already built, and its own product
        if args.temple and t not in args.temple:
            continue
        folder = folder_for(comps, t)
        if folder is None:
            print(f"  !! {t}: no composites under {comps}")
            continue
        todo.append((n, t, folder))
    if args.limit:
        todo = todo[:args.limit]

    stages = [s.strip() for s in args.stages.split(",") if s.strip()]
    print(f"{len(todo)} {args.garment} product(s), stages: {', '.join(stages)}\n")
    t0, failed = time.time(), []
    for i, (n, temple, folder) in enumerate(todo, 1):
        print(f"[{i}/{len(todo)}] {n['title']}")
        if args.verify:
            pr = sc.gql("""query($id:ID!){product(id:$id){media(first:60){nodes{alt
              ... on MediaImage{image{url}}}}}}""", {"id": n["id"]})["product"]
            probs = verify(pr, temple, args.garment)
            print("    " + ("OK" if not probs else "\n    ".join(probs)))
            if probs:
                failed.append((n["title"], "verify"))
            continue
        if args.dry_run:
            print(f"    temple {temple!r}  composites {folder}")
            continue
        for st in stages:
            cmd = [PY, BUILDER, "--product-gid", n["id"], "--garment", args.garment,
                   "--temple", temple, "--onmodel-dir", str(folder), f"--{st}"]
            r = subprocess.run(cmd, capture_output=True, text=True)
            if r.returncode != 0:
                print(f"    {st} FAILED\n{r.stdout[-800:]}{r.stderr[-800:]}")
                failed.append((n["title"], st))
                break
            for line in r.stdout.splitlines():
                if line.startswith("  ") and line.strip():
                    print(f"   {line.strip()[:96]}")
        el = time.time() - t0
        print(f"    {el/60:.1f} min elapsed, ~{(el/i)*(len(todo)-i)/60:.0f} min left")
    if failed:
        print(f"\nFAILED {len(failed)}:")
        for t, s in failed:
            print(f"   {t}  at --{s}")
    print(f"\ndone in {(time.time()-t0)/60:.1f} min")


if __name__ == "__main__":
    main()
