#!/usr/bin/env python
"""Put the per-temple catalogue galleries on the same gray as everything else.

The Salt Lake products were rebuilt by build_product_gallery.py, which assumes
that gallery: a lead flat, an art card, on-model shots, fabric details. The other
44 live tees are a different shape. Each is 10 Tapstitch flat lays on pure white
plus one art card, and nothing else. This script is for that shape.

Background only. Every image is already 1:1, so nothing is cropped and nothing is
resampled. The art card keeps its white background, as on Salt Lake.

THE RISK THIS EXISTS TO MANAGE. Five of the ten flats on each product are bound
to a colour variant. Replacing an image means deleting the original, and deleting
a variant-bound image blanks that variant on the storefront. So the order is
fixed and never varies:

    upload the gray copy -> wait for READY -> rebind every variant that pointed
    at the original -> move it into the original's slot -> only then delete

If any step fails partway the product is left with a duplicate image, which is
cosmetic and re-runnable. It is never left with a variant pointing at nothing.

IDEMPOTENT WITHOUT ALT TEXT. These flats arrive unlabelled and the pixel
classifier cannot reliably tell a front from a back on this line, so identity is
not the test. Instead an image is considered done when its border already reads
the target gray. Re-running skips those, so an interrupted run resumes.

ARCHIVING. Originals go to flat-originals/catalog/, which is GITIGNORED, unlike
the Salt Lake archive. 440 PNGs is about 220MB and Tapstitch can republish these
from the print files in ../Temples/, so they are recoverable by a route the Salt
Lake flats no longer had. They are still written to disk before any delete.

  --handle H     one product
  --all          every live per-temple tee
  --dry-run      report and change nothing
  --limit N      stop after N products
"""
import argparse
import sys
import time
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "artifacts/photo-mockup-spike"))
import normalize  # noqa: E402
from shopify_client import ShopifyClient  # noqa: E402

SPIKE = ROOT / "artifacts/photo-mockup-spike"
ARCHIVE = SPIKE / "flat-originals/catalog"
# Wildcards, not an exact phrase: the quoted form matches only the bare
# "Essential Heavyweight Temple Tee", which is the Salt Lake product. The
# per-temple ones carry a suffix, and the ")" test then excludes Salt Lake
# because build_product_gallery.py has already rebuilt it.
CATALOGUE_QUERY = "title:*Heavyweight Temple Tee*"
ART_MARKER = "line art close-up"
GARMENT = "tee"
TOLERANCE = 3        # border within this of the target gray counts as already done

PRODUCT = """query($h:String!){productByHandle(handle:$h){id title status
 media(first:60){nodes{id alt ... on MediaImage{image{url width height}}}}
 variants(first:100){nodes{id title media(first:1){nodes{id}}}}}}"""


def fetch(sc, handle):
    p = sc.gql(PRODUCT, {"h": handle})["productByHandle"]
    if not p:
        raise SystemExit(f"no product with handle {handle!r}")
    return p


def download(url, dest):
    if dest.exists():
        return dest
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(urllib.request.urlopen(req, timeout=90).read())
    return dest


def border_is(img, gray, tol=TOLERANCE):
    """True when the frame edge already reads `gray`: this one is done."""
    a = np.asarray(img.convert("RGB"), dtype=float)
    edge = np.concatenate([a[:6].reshape(-1, 3), a[-6:].reshape(-1, 3),
                           a[:, :6].reshape(-1, 3), a[:, -6:].reshape(-1, 3)])
    return bool(np.abs(edge.mean(axis=0) - np.asarray(gray, dtype=float)).max() <= tol)


def plan(p, gray, cachedir):
    """(todo, skipped, pale) for one product."""
    bound = {}
    for v in p["variants"]["nodes"]:
        mid = (v["media"]["nodes"] or [{}])[0].get("id")
        if mid:
            bound.setdefault(mid, []).append(v["id"])
    todo, skipped, pale = [], [], []
    for i, m in enumerate(p["media"]["nodes"]):
        if ART_MARKER in (m.get("alt") or "").lower():
            continue                                  # the art card stays white
        src = download(m["image"]["url"],
                       cachedir / (m["image"]["url"].split("/")[-1].split("?")[0]))
        img = Image.open(src)
        if border_is(img, gray):
            skipped.append(m["id"])
            continue
        _, rep = normalize.separated_gray(img, gray)
        if rep.get("adjusted"):
            # Do NOT quietly darken one image: its nine siblings would stay on the
            # standard gray and the product would look wrong rather than broken.
            pale.append((m["id"], rep))
            continue
        todo.append({"id": m["id"], "pos": i, "src": src,
                     "variants": bound.get(m["id"], [])})
    return todo, skipped, pale


def run_product(sc, handle, gray, dry):
    p = fetch(sc, handle)
    cachedir = SPIKE / ".flatcache/catalog" / handle
    todo, skipped, pale = plan(p, gray, cachedir)
    print(f"{p['title'][:48]:48s} [{p['status']:6s}] "
          f"{len(p['media']['nodes']):2d} img  todo {len(todo):2d}  done {len(skipped):2d}"
          + (f"  PALE {len(pale)}" if pale else ""))
    for mid, rep in pale:
        print(f"    REFUSING {mid.split('/')[-1]}: body {rep['body_luma']:.0f} sits "
              f"{rep['separation']:.0f} from the backdrop, under "
              f"{normalize.MIN_SEPARATION}. It would vanish.")
    if dry or not todo:
        return len(todo), len(pale)

    ARCHIVE.mkdir(parents=True, exist_ok=True)
    for t in todo:
        keep = ARCHIVE / handle / t["src"].name
        keep.parent.mkdir(parents=True, exist_ok=True)
        if not keep.exists():
            keep.write_bytes(t["src"].read_bytes())

        img, _ = normalize.gray_background(Image.open(t["src"]), gray)
        out = cachedir / ("gray_" + t["src"].stem + ".png")
        img.save(out, "PNG", optimize=True)

        alt = (next(m for m in p["media"]["nodes"] if m["id"] == t["id"]).get("alt") or "")
        new = sc.upload_media_image(p["id"], out, alt)
        sc.wait_for_media_ready(new)

        if t["variants"]:
            ups = [{"id": vid, "mediaId": new} for vid in t["variants"]]
            for i in range(0, len(ups), 25):
                r = sc.gql("""mutation($pid:ID!,$variants:[ProductVariantsBulkInput!]!){
                  productVariantsBulkUpdate(productId:$pid,variants:$variants){
                    userErrors{message}}}""",
                    {"pid": p["id"], "variants": ups[i:i + 25]})
                errs = r["productVariantsBulkUpdate"]["userErrors"]
                if errs:
                    raise SystemExit(f"rebind failed, NOT deleting the original: {errs}")

        sc.move_media_to_position(p["id"], new, t["pos"])
        r = sc.gql("""mutation($pid:ID!,$ids:[ID!]!){productDeleteMedia(productId:$pid,
          mediaIds:$ids){deletedMediaIds mediaUserErrors{message}}}""",
            {"pid": p["id"], "ids": [t["id"]]})["productDeleteMedia"]
        if r["mediaUserErrors"]:
            raise SystemExit(str(r["mediaUserErrors"]))
        print(f"    slot {t['pos']:2d} replaced"
              + (f", {len(t['variants'])} variant(s) rebound" if t["variants"] else ""))
    return len(todo), len(pale)


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--handle")
    g.add_argument("--all", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int)
    args = ap.parse_args()

    sc = ShopifyClient()
    gray = normalize.backdrop_gray(GARMENT)
    print(f"target backdrop for the {GARMENT}: {gray}\n")

    if args.handle:
        handles = [args.handle]
    else:
        r = sc.gql("""query($c:String){products(first:250,query:$c){
          nodes{handle title status}}}""", {"c": CATALOGUE_QUERY})["products"]["nodes"]
        handles = [n["handle"] for n in r
                   if n["status"] == "ACTIVE" and n["title"].endswith(")")]
        handles.sort()
        print(f"{len(handles)} live per-temple tees\n")
    if args.limit:
        handles = handles[:args.limit]

    t0, changed, pale = time.time(), 0, 0
    for i, h in enumerate(handles, 1):
        c, pl = run_product(sc, h, gray, args.dry_run)
        changed += c
        pale += pl
        if not args.dry_run and c:
            el = time.time() - t0
            print(f"    [{i}/{len(handles)}] {el/60:.1f} min elapsed, "
                  f"~{el/i*(len(handles)-i)/60:.0f} min left")
    print(f"\n{'would change' if args.dry_run else 'changed'} {changed} image(s) "
          f"across {len(handles)} product(s)" + (f", {pale} refused as pale" if pale else ""))


if __name__ == "__main__":
    main()
