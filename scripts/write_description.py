"""Write full product descriptions to Printify for one temple's products.

The temple-facts fragment is researched by the session (per the methodology
in reference/skills/cc1717-temple-description-builder) and saved to
Temples/{Name}/temple-facts.html. This script assembles, per garment,
the garment-correct fixed sections plus that fragment, and PUTs it onto
each product recorded in the temple's status.json.

Usage:
  python scripts/write_description.py --temple "San Antonio"
  python scripts/write_description.py --temple Logan --product-id ID --garment cc1717
  python scripts/write_description.py --backfill-dated [--report-only]
"""

import argparse
import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from art_images import match_temple, temple_tokens
from generate import (TEMPLES_DIR, fixed_description, load_garment_config,
                      title_is_dated, title_is_one_off)
from printify_client import PrintifyClient, load_config
from shopify_client import ShopifyClient, ShopifyError

FACTS_RE = re.compile(r'<section class="temple-facts">.*</section>', re.S)
DATED_GARMENT = "cc1717-dated"


def find_facts(title, description, tokens):
    """This temple's researched facts, preferring what is already on the
    product so no temple can inherit another's history. Falls back to the
    temple folder's fragment for products whose description was never
    written. Returns None when neither exists."""
    match = FACTS_RE.search(description or "")
    if match:
        return match.group(0).strip()
    temple = match_temple(title, tokens)
    if not temple:
        return None
    path = TEMPLES_DIR / temple / "temple-facts.html"
    return path.read_text().strip() if path.exists() else None


def backfill_dated(report_only=False):
    """Rebuild every dated tee's description so it opens with the
    Personalization section Evan added (reference/description-blocks/).

    The temple facts are lifted back out of the live description rather than
    read from Temples/{Name}/temple-facts.html, so hand-built products with no
    local facts file are covered too, and no temple can end up carrying
    another's history.

    Written to Printify and Shopify both. Nothing here republishes: a
    republish re-syncs images and variants as well and would undo the UNLISTED
    status on the child listings."""
    cfg = load_garment_config(DATED_GARMENT)
    fixed = fixed_description(cfg)
    if not fixed:
        raise SystemExit(f"No fixed-section assets for {DATED_GARMENT}.")
    opener = fixed.split("\n\n")[0]

    printify = PrintifyClient(*load_config())
    shopify = ShopifyClient()
    tokens = temple_tokens()
    products = sorted(printify.all_products(), key=lambda p: p["title"])
    done = failed = 0
    for product in products:
        title = (product.get("title") or "").strip()
        if not title_is_dated(title) or title_is_one_off(title) or title.lower().startswith("copy of"):
            continue
        description = product.get("description") or ""
        if description.lstrip().startswith(opener.lstrip()):
            print(f"  skip  {title}  (already has the Personalization section)")
            continue
        facts = find_facts(title, description, tokens)
        if not facts:
            print(f"  SKIP  {title}  (no temple facts anywhere; research this temple "
                  f"and run --temple for it first)")
            continue
        rebuilt = fixed + "\n\n" + facts
        if report_only:
            print(f"  would rewrite  {title}  ({len(description)} -> {len(rebuilt)} chars)")
            continue
        try:
            printify.update_product(product["id"], {"description": rebuilt})
            external = product.get("external") or {}
            if external.get("id"):
                shopify.update_product(f"gid://shopify/Product/{external['id']}",
                                       descriptionHtml=rebuilt)
            print(f"  {title}: rewritten ({len(rebuilt)} chars)")
            done += 1
        except (ShopifyError, Exception) as err:
            print(f"  FAILED {title}: {err}")
            failed += 1
    print(f"\n{done} rewritten, {failed} failed.")
    if failed:
        sys.exit(f"{failed} description(s) did not complete.")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--temple")
    ap.add_argument("--product-id", help="Write to one explicit product instead of status.json entries")
    ap.add_argument("--garment", help="Garment id for --product-id (selects the right fixed sections)")
    ap.add_argument("--backfill-dated", action="store_true",
                    help="One-time: add the Personalization section to every existing dated tee")
    ap.add_argument("--report-only", action="store_true", help="with --backfill-dated: write nothing")
    args = ap.parse_args()

    if args.backfill_dated:
        backfill_dated(report_only=args.report_only)
        return
    if not args.temple:
        raise SystemExit("Pass --temple NAME (or --backfill-dated).")

    facts_path = TEMPLES_DIR / args.temple / "temple-facts.html"
    if not facts_path.exists():
        raise SystemExit(f"No {facts_path}. Research the temple first and save the facts fragment there.")
    facts = facts_path.read_text().strip()
    if "temple-facts" not in facts:
        raise SystemExit("Facts fragment must be the <section class=\"temple-facts\"> block.")

    if args.product_id:
        if not args.garment:
            raise SystemExit("--product-id needs --garment.")
        targets = [(args.garment, args.product_id)]
    else:
        status = json.loads((TEMPLES_DIR / args.temple / "status.json").read_text())
        targets = [(r["garment"], r["product_id"]) for r in status.get("results", []) if r.get("product_id")]
        if not targets:
            raise SystemExit("status.json lists no generated products for this temple.")

    c = PrintifyClient(*load_config())
    for gid, pid in targets:
        cfg = load_garment_config(gid)
        fixed = fixed_description(cfg)
        if not fixed:
            print(f"  SKIP {gid}: no fixed-section assets found")
            continue
        c.update_product(pid, {"description": fixed + "\n\n" + facts})
        after = c.get_product(pid)
        print(f"  {after['title']!r}: description written ({len(after['description'])} chars)")


if __name__ == "__main__":
    main()
