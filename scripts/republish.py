"""Re-push every already-published Printify product to Shopify, then repair.

  python scripts/republish.py --report-only
  python scripts/republish.py
  python scripts/republish.py --only "(Bountiful)"

A republish re-syncs title, description, images and variants together. Measured
22 Aug 2026 on one tee and one hoodie, it keeps the title and the listing
status (both were UNLISTED children at the time; new products publish ACTIVE
since Evan's 26 Aug 2026 decision) but it also:

  - DELETES the Shopify-side art close-up cards outright
  - reverts the hoodie's Blue Jean colorway to Printify's True Navy
  - reverts the Color option order, so pages stop opening on the wanted color
  - does NOT change the featured image

So the repair is not optional and is built into this script: after the pushes
settle it re-runs the Shopify fixups, re-pushes the art cards, and re-seats the
featured photos. Running the republish without the repair leaves the storefront
worse than before.

Unclaimed "Copy of ..." drafts are never published. They have no Shopify
counterpart, so publishing one would create a junk product on the storefront.
"""

import argparse
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from printify_client import PrintifyClient, PrintifyError, load_config

PUBLISH_FLAGS = {
    "title": True, "description": True, "images": True, "variants": True,
    "tags": True, "keyFeatures": True, "shipping_template": True,
}
# Shopify needs to finish ingesting the re-pushed mockups before the art cards
# can be attached and positioned; the same wait the end-of-run sequence uses.
SETTLE_S = 180


def publishable(product):
    """(ok, reason). Only products that already exist on Shopify."""
    title = (product.get("title") or "").strip()
    if title.lower().startswith("copy of"):
        return False, "unclaimed duplicate, publishing it would create a junk product"
    if not product.get("external"):
        return False, "never published; use scripts/publish_drafts.py for new drafts"
    if product.get("is_locked"):
        return False, "locked, a publish is already in progress"
    return True, "republish"


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--report-only", action="store_true", help="list, publish nothing")
    ap.add_argument("--only", help="restrict to titles containing this text")
    ap.add_argument("--skip-repair", action="store_true",
                    help="do not run the repair passes afterward (leaves the storefront broken)")
    args = ap.parse_args()

    client = PrintifyClient(*load_config())
    products = sorted(client.all_products(), key=lambda p: p["title"])
    todo, skipped = [], []
    for product in products:
        title = product["title"].strip()
        if args.only and args.only.lower() not in title.lower():
            continue
        ok, reason = publishable(product)
        (todo if ok else skipped).append((product, reason))

    for product, reason in skipped:
        print(f"skip     {product['title']}  ({reason})")
    print(f"\n{len(todo)} product(s) to republish, {len(skipped)} skipped.")
    if args.report_only:
        print("Report only, nothing published.")
        return
    if not todo:
        return

    failures = 0
    for i, (product, _) in enumerate(todo, start=1):
        try:
            client._request("POST",
                            f"/shops/{client.shop_id}/products/{product['id']}/publish.json",
                            json=PUBLISH_FLAGS)
            print(f"  [{i}/{len(todo)}] pushed  {product['title']}")
        except PrintifyError as err:
            print(f"  [{i}/{len(todo)}] FAILED  {product['title']}: {err}")
            failures += 1
    print(f"\n{len(todo) - failures} pushed, {failures} failed.")

    if args.skip_repair:
        print("\nRepair skipped. The art cards, the Blue Jean colorway and the color "
              "order are all reverted right now. Run these when ready:\n"
              "  scripts/shopify_fixups.py all\n"
              "  scripts/art_images.py push --all\n"
              "  scripts/shopify_fixups.py featured-photo")
        return

    print(f"\nWaiting {SETTLE_S}s for Shopify to finish ingesting the re-pushed mockups ...")
    time.sleep(SETTLE_S)

    from art_images import push_catalog
    from shopify_fixups import run as fixups_run
    print("\n--- repair 1/3: Shopify fixups (hoodie colorway, color order)")
    fixups_run("all")
    print("\n--- repair 2/3: art close-up cards")
    push_catalog(only_temple=None)
    print("\n--- repair 3/3: featured photos")
    fixups_run("featured-photo")


if __name__ == "__main__":
    main()
