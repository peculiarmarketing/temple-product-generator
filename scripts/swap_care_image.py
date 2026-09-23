#!/usr/bin/env python
"""Point every live garment's care-instructions image at the owned SVG.

The care row in each description shows a screenshot someone took on 18 Sep
2026 (Screenshot_2026-09-18_at_4.40.25_PM.png). Its replacement,
care-symbols.svg, is already in Files: the same five ISO symbols, drawn clean.

WHY THE DESCRIPTIONS HAVE TO CHANGE. Replacing the screenshot's bytes in place
does not reach customers: the CDN serves that path with a one-year cache, so
the ?v= pinned in every description keeps returning the old image. Only a new
URL does. Shopify has no way to patch part of descriptionHtml, so each product
gets its whole description written back with that one src changed. Nothing
else in the tag (alt, width, height) or the description is touched.

    swap_care_image.py --garment tee --garment crew             # dry run
    swap_care_image.py --garment tee --garment crew --apply
    swap_care_image.py --garment tee --apply --revert           # put it back

--garment is required and hoodie is never implied. While the Eden Green
rollout is running, each hoodie swap copies the old description onto the new
product, so hoodies go after the last temple is done.

Every product is re-read after the run, and the counts are reported from that
read, not from the mutation responses.
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from shopify_client import ShopifyClient                     # noqa: E402

OLD = ("https://cdn.shopify.com/s/files/1/0923/2957/4772/files/"
       "Screenshot_2026-09-18_at_4.40.25_PM.png?v=1789771279")
NEW = ("https://cdn.shopify.com/s/files/1/0923/2957/4772/files/"
       "care-symbols.svg?v=1790100016")


def live_garments(sc, garment):
    out, after = [], None
    while True:
        r = sc.gql("""
          query($q: String!, $a: String) {
            products(first: 50, after: $a, query: $q) {
              nodes { id handle descriptionHtml }
              pageInfo { hasNextPage endCursor } } }""",
            {"q": f"status:active AND tag:'garment:{garment}'", "a": after})["products"]
        out += r["nodes"]
        if not r["pageInfo"]["hasNextPage"]:
            return out
        after = r["pageInfo"]["endCursor"]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--garment", action="append", required=True,
                    choices=["tee", "crew", "hoodie"])
    ap.add_argument("--apply", action="store_true", help="write; default is a dry run")
    ap.add_argument("--revert", action="store_true", help="swap the SVG back to the screenshot")
    args = ap.parse_args()
    src, dst = (NEW, OLD) if args.revert else (OLD, NEW)

    sc = ShopifyClient()
    failed = []
    for garment in args.garment:
        products = live_garments(sc, garment)
        todo = [p for p in products if src in p["descriptionHtml"]]
        print(f"{garment}: {len(products)} live, {len(todo)} to change, "
              f"{sum(dst in p['descriptionHtml'] for p in products)} already done, "
              f"{sum(src not in p['descriptionHtml'] and dst not in p['descriptionHtml'] for p in products)} "
              f"with no care image")
        for p in todo:
            if p["descriptionHtml"].count(src) != 1:
                failed.append(f"{p['handle']}: image appears {p['descriptionHtml'].count(src)} times")
                continue
            if not args.apply:
                continue
            try:
                sc.update_product(p["id"], descriptionHtml=p["descriptionHtml"].replace(src, dst))
            except Exception as e:                            # keep going, report at the end
                failed.append(f"{p['handle']}: {e}")

        if args.apply:
            after = live_garments(sc, garment)
            print(f"  read back: {sum(dst in p['descriptionHtml'] for p in after)} on the "
                  f"{'screenshot' if args.revert else 'SVG'}, "
                  f"{sum(src in p['descriptionHtml'] for p in after)} still on the old image")

    for f in failed:
        print("FAILED", f)
    if not args.apply:
        print("dry run: nothing written. Add --apply to write.")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
