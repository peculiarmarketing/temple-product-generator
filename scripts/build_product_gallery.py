#!/usr/bin/env python
"""Build one product's gallery to the agreed layout. THE process, per Evan, 17 Sep 2026.

Gallery, in order:

  1  on-model back, lead colour          the hero
  2  flat back mockup, lead colour       clean design view
  3  temple art closeup                  the design card
  4  lifestyle shot                      NOT BUILT YET, slot left for it
  5+ on-model back, every other colour   each bound to its variant
  .. fabric and construction details     captioned with the colourway shown
  last flat front mockup with chest logo

Runs in three stages so the destructive one is never a surprise:

  --report   classify what is on the product now and print the plan. Changes nothing.
  --add      upload on-model backs and fabric details, bind variants. Additive only.
  --prune    delete the surplus flat mockups, then order the gallery.

`--add` is safe to re-run: every image this uploads carries a deterministic alt
text and anything already present is skipped. `--prune` refuses to touch a media
item that is still bound to a variant, which is the failure that would blank a
variant on the storefront.

THE CLASSIFIER. Tapstitch's flat mockups reach Shopify with no alt text, so which
one is "Black front" has to be worked out from the pixels. Two signals:
  colour  - mean garment colour matched against true_colors_all.json
  side    - the back carries the temple print, the front a small chest logo, so
            the back has several times more near-white ink
Both are printed in --report so a human can check before anything is deleted.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shopify_client import ShopifyClient  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SPIKE = ROOT / "artifacts/photo-mockup-spike"
TRUE = json.loads((SPIKE / "true_colors_all.json").read_text())

LEAD = {"hoodie": "navy-blue", "tee": "black", "crew": "gray"}
ORDER = {
    "hoodie": ["navy-blue", "gray", "black", "coffee", "mauve", "royal-blue"],
    "tee": ["black", "dark-gray", "navy-blue", "maroon", "coffee"],
    "crew": ["gray", "black"],
}
PRETTY = {"navy-blue": "Navy Blue", "royal-blue": "Royal Blue", "dark-gray": "Dark Gray",
          "gray": "Gray", "black": "Black", "coffee": "Coffee", "mauve": "Mauve",
          "maroon": "Maroon"}
SWATCH = {"navy-blue": "Navy Blue", "royal-blue": "Royal Blue", "dark-gray": "Dark Gray",
          "gray": "Gray", "black": "Black", "coffee": "Coffee", "mauve": "Mauve",
          "maroon": "Maroon"}


def on_model_alt(temple, colour):
    return f"{temple} Temple back print on model - {PRETTY[colour]}"


def detail_alts(garment):
    d = SPIKE / "fabric-details" / garment
    if not d.exists():
        return []
    return sorted(json.loads((d / "captions.json").read_text()).items())


def classify(url, garment, cache):
    """(colour_key, 'back'|'front', ink_fraction) for one flat mockup."""
    import urllib.request
    p = cache / (url.split("/")[-1].split("?")[0])
    if not p.exists():
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        p.write_bytes(urllib.request.urlopen(req, timeout=60).read())
    a = np.asarray(Image.open(p).convert("RGB"), dtype=float)
    h, w = a.shape[:2]
    # Middle 20% only. A wider box catches the white BACKGROUND these flat lays
    # sit on, which put the front at 4.6% ink and made it read as a back. Checked
    # against all 12 hoodie mockups: backs 12.3-22.8%, fronts 1.1-1.7%.
    mid = a[int(h * 0.40):int(h * 0.60), int(w * 0.40):int(w * 0.60)]
    flat = mid.reshape(-1, 3)
    ink = float((flat.min(axis=1) > 200).mean())          # near-white pixels

    # Colour comes from the MEDIAN of every garment pixel in the whole image, not
    # the mean of the centre. On a back the temple print covers a fifth of the
    # centre and drags the mean badly: all five tee backs read "Dark Gray" at
    # distances up to 57. The median over the whole garment ignores the print and
    # put every one of the ten tee mockups within 9 of its true swatch.
    allp = a.reshape(-1, 3)
    body = allp[allp.min(axis=1) <= 200]                  # drops white bg AND white ink
    mean = np.median(body, axis=0) if len(body) else flat.mean(axis=0)
    best, bestd = None, 1e9
    for key, name in SWATCH.items():
        ref = TRUE.get(garment, {}).get(name)
        if not ref:
            continue
        dist = float(np.linalg.norm(mean - np.array(ref, dtype=float)))
        if dist < bestd:
            best, bestd = key, dist
    return best, bestd, ink


def fetch(sc, gid):
    return sc.gql("""
      query($id: ID!) { product(id: $id) {
        title status
        media(first: 60) { nodes { ... on MediaImage { id alt image { url } } } }
        variants(first: 100) { nodes { id title
          media(first: 1) { nodes { ... on MediaImage { id } } } } } } }""",
        {"id": gid})["product"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--product-gid", required=True)
    ap.add_argument("--garment", required=True, choices=sorted(ORDER))
    ap.add_argument("--temple", default="Salt Lake")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--report", action="store_true")
    g.add_argument("--add", action="store_true")
    g.add_argument("--prune", action="store_true")
    args = ap.parse_args()

    sc = ShopifyClient()
    prod = fetch(sc, args.product_gid)
    media = prod["media"]["nodes"]
    lead = LEAD[args.garment]
    cache = SPIKE / ".flatcache" / args.garment
    cache.mkdir(parents=True, exist_ok=True)

    ours = {m.get("alt"): m["id"] for m in media if m.get("alt")}
    flats = [m for m in media if not m.get("alt")]
    art = [m for m in media if "line art" in (m.get("alt") or "").lower()]

    print(f"product : {prod['title']}  [{prod['status']}]")
    print(f"gallery : {len(media)} images, {len(flats)} unlabelled flat mockup(s)\n")

    if flats:
        print("classifying the unlabelled flat mockups:")
        print(f"  {'media':20s} {'colour':12s} {'dist':>5s} {'ink%':>6s}  side")
    seen = {}
    for m in flats:
        colour, dist, ink = classify(m["image"]["url"], args.garment, cache)
        side = "back" if ink > 0.06 else "front"
        seen[m["id"]] = (colour, side)
        star = "  <- KEEP" if colour == lead else ""
        print(f"  {m['id'].split('/')[-1]:20s} {PRETTY.get(colour, '?'):12s} "
              f"{dist:5.1f} {ink*100:6.2f}  {side}{star}")

    keep = {mid for mid, (c, s) in seen.items() if c == lead}
    drop = [mid for mid in seen if mid not in keep]
    bound = {(v["media"]["nodes"] or [{}])[0].get("id") for v in prod["variants"]["nodes"]}
    bound.discard(None)
    clash = [m for m in drop if m in bound]

    print(f"\nkeep {len(keep)} flat mockup(s) in the lead colour ({PRETTY[lead]}), drop {len(drop)}")
    if clash:
        print(f"  BLOCKED: {len(clash)} of those are still bound to a variant. Run --add first.")
    print(f"art closeup present: {'yes' if art else 'NO'}")
    missing = [c for c in ORDER[args.garment] if on_model_alt(args.temple, c) not in ours]
    print(f"on-model backs missing: {', '.join(missing) if missing else 'none'}")
    caps = detail_alts(args.garment)
    print(f"fabric details missing: {sum(1 for _, a in caps if a not in ours)} of {len(caps)}")

    if args.report:
        print("\nREPORT ONLY. Nothing changed.")
        return

    if args.add:
        for c in ORDER[args.garment]:
            alt = on_model_alt(args.temple, c)
            if alt in ours:
                continue
            f = SPIKE / "final-set" / f"{args.garment}_{c}.jpg"
            if not f.exists():
                raise SystemExit(f"missing {f}")
            mid = sc.upload_media_image(args.product_gid, f, alt)
            sc.wait_for_media_ready(mid)
            ours[alt] = mid
            print(f"  uploaded on-model {c}")
        for fn, alt in caps:
            if alt in ours:
                continue
            mid = sc.upload_media_image(args.product_gid,
                                        SPIKE / "fabric-details" / args.garment / fn, alt)
            sc.wait_for_media_ready(mid)
            ours[alt] = mid
            print(f"  uploaded detail {fn}")
        prod = fetch(sc, args.product_gid)
        by_alt = {m.get("alt"): m["id"] for m in prod["media"]["nodes"] if m.get("alt")}
        ups = []
        for v in prod["variants"]["nodes"]:
            colour = v["title"].split(" / ")[0]
            key = next((k for k, p in PRETTY.items() if p == colour), None)
            target = by_alt.get(on_model_alt(args.temple, key)) if key else None
            cur = (v["media"]["nodes"] or [{}])[0].get("id")
            if target and cur != target:
                ups.append({"id": v["id"], "mediaId": target})
        for i in range(0, len(ups), 25):
            sc.gql("""
              mutation($pid: ID!, $variants: [ProductVariantsBulkInput!]!) {
                productVariantsBulkUpdate(productId: $pid, variants: $variants) {
                  userErrors { message } } }""",
                {"pid": args.product_gid, "variants": ups[i:i+25]})
        print(f"  bound {len(ups)} variant(s) to their on-model back")
        print("\nADD complete. Run --report to check, then --prune.")
        return

    # --prune
    if clash:
        raise SystemExit("refusing to prune: surplus mockups are still variant-bound.")
    if drop:
        res = sc.gql("""
          mutation($pid: ID!, $ids: [ID!]!) {
            productDeleteMedia(productId: $pid, mediaIds: $ids) {
              deletedMediaIds mediaUserErrors { message } } }""",
            {"pid": args.product_gid, "ids": drop})["productDeleteMedia"]
        if res["mediaUserErrors"]:
            raise SystemExit(str(res["mediaUserErrors"]))
        print(f"  deleted {len(res['deletedMediaIds'])} surplus flat mockup(s)")

    prod = fetch(sc, args.product_gid)
    by_alt = {m.get("alt"): m["id"] for m in prod["media"]["nodes"] if m.get("alt")}
    still = {m["id"] for m in prod["media"]["nodes"] if not m.get("alt")}
    lead_back = next((m for m in still if seen.get(m, (None, None))[1] == "back"), None)
    lead_front = next((m for m in still if seen.get(m, (None, None))[1] == "front"), None)
    target = [by_alt[on_model_alt(args.temple, lead)]]
    if lead_back:
        target.append(lead_back)
    if art:
        target.append(art[0]["id"])
    for c in ORDER[args.garment]:
        if c != lead:
            target.append(by_alt[on_model_alt(args.temple, c)])
    for _, alt in caps:
        if alt in by_alt:
            target.append(by_alt[alt])
    if lead_front:
        target.append(lead_front)
    for idx, mid in enumerate(target):
        sc.move_media_to_position(args.product_gid, mid, idx)
    print("\nFINAL GALLERY:")
    for i, m in enumerate(fetch(sc, args.product_gid)["media"]["nodes"]):
        print(f"  {i+1:2d}. {m.get('alt') or '(flat mockup, lead colour)'}")


if __name__ == "__main__":
    main()
