"""Write full product descriptions to Printify for one temple's products.

The temple-facts fragment is researched by the session (per the methodology
in reference/skills/cc1717-temple-description-builder) and saved to
Temples/{Name}/temple-facts.html. This script assembles, per garment,
the garment-correct fixed sections plus that fragment, and PUTs it onto
each product recorded in the temple's status.json.

Usage:
  python scripts/write_description.py --temple "San Antonio"
  python scripts/write_description.py --temple Logan --product-id ID --garment cc1717
  python scripts/write_description.py --repair [--report-only]
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


BLUEPRINTS = {706: ("cc1717", "cc1717-dated"), 1296: ("cc1566", None), 1298: ("cc1567", None)}


def garment_for(product):
    """The garment config id behind a Printify product."""
    base, dated = BLUEPRINTS.get(product.get("blueprint_id"), (None, None))
    if base is None:
        return None
    return dated if (dated and title_is_dated(product.get("title") or "")) else base


def temple_of(title, tokens):
    """The temple folder behind a title, Limited Edition one-offs included.

    match_temple deliberately refuses those (they get no art card and no
    dropdown row), but they are still a temple's product and still need that
    temple's history on the page."""
    temple = match_temple(title, tokens)
    if temple:
        return temple
    m = re.search(r"\(([^()]+)\)\s*$", title.strip())
    return tokens.get(m.group(1).strip()) if m else None


def build_facts_index(printify_products, shopify_by_title, tokens):
    """{temple: facts fragment}, from the most trustworthy source available.

    Order: the temple's own local fragment, then any of its products that
    still carries one, Printify before Shopify. Keyed by temple so a product
    can never inherit another temple's history."""
    index = {}
    for temple in {temple_of(p["title"], tokens) for p in printify_products}:
        if not temple:
            continue
        path = TEMPLES_DIR / temple / "temple-facts.html"
        if path.exists() and "temple-facts" in path.read_text():
            index[temple] = path.read_text().strip()
    for source in (printify_products,
                   [{"title": t, "description": h} for t, h in shopify_by_title.items()]):
        for product in source:
            temple = temple_of(product["title"], tokens)
            if not temple or temple in index:
                continue
            match = FACTS_RE.search(product.get("description") or "")
            if match:
                index[temple] = match.group(0).strip()
    return index


def is_broken(description, opener):
    """A description is broken when it is empty, carries no temple facts, or
    is a dated tee missing the Personalization opener. Anything else is left
    alone: some live products carry an older approved intro, and replacing
    that is a copy decision, not a repair."""
    text = (description or "").strip()
    if not text or 'class="temple-facts"' not in text:
        return True
    return bool(opener) and not text.startswith(opener.strip())


def repair(report_only=False, normalize=False):
    """Rebuild every product's description from the garment's fixed sections
    plus its own temple's facts, on Printify AND Shopify.

    By default only BROKEN descriptions are touched (empty, no temple facts,
    or a dated tee missing the Personalization opener). Pass normalize=True to
    also rewrite intact descriptions that differ from the repo's current copy.

    Two problems this fixes at once. Products whose descriptions only ever
    existed on Shopify (written by the claude.ai event, never pushed to
    Printify) were blanked when the catalog was republished, because a
    republish pushes Printify's empty field over Shopify's copy. And the
    dated tees need the Personalization opener that the garment config now
    declares. Facts come from the product itself where it still has them, so
    nothing is invented and no temple inherits another's history."""
    printify = PrintifyClient(*load_config())
    shopify = ShopifyClient()
    tokens = temple_tokens()

    products = [p for p in sorted(printify.all_products(), key=lambda x: x["title"])
                if not p["title"].lower().startswith("copy of")]
    shopify_by_title, cursor = {}, None
    while True:
        data = shopify.gql("""
          query($after: String) { products(first: 50, after: $after) {
            pageInfo { hasNextPage endCursor }
            nodes { id title descriptionHtml } } }""", {"after": cursor})
        block = data["products"]
        for node in block["nodes"]:
            shopify_by_title[node["title"].strip()] = node["descriptionHtml"] or ""
        if not block["pageInfo"]["hasNextPage"]:
            break
        cursor = block["pageInfo"]["endCursor"]
    shopify_ids = {}
    facts_index = build_facts_index(products, shopify_by_title, tokens)

    fixed_cache, written, skipped, missing = {}, 0, 0, []
    for product in products:
        title = product["title"].strip()
        temple = temple_of(title, tokens)
        garment = garment_for(product)
        if not temple or not garment:
            skipped += 1
            continue
        facts = facts_index.get(temple)
        if not facts:
            missing.append(title)
            continue
        if garment not in fixed_cache:
            fixed_cache[garment] = fixed_description(load_garment_config(garment))
        fixed = fixed_cache[garment]
        if not fixed:
            skipped += 1
            continue
        wanted = fixed + "\n\n" + facts

        opener = fixed.split("\n\n")[0] if garment == "cc1717-dated" else ""
        live = shopify_by_title.get(title)
        if normalize:
            needs_printify = (product.get("description") or "").strip() != wanted
            needs_shopify = live is not None and live.strip() != wanted
        else:
            needs_printify = is_broken(product.get("description"), opener)
            needs_shopify = live is not None and is_broken(live, opener)
        if not (needs_printify or needs_shopify):
            continue
        where = ", ".join(w for w, f in (("Printify", needs_printify), ("Shopify", needs_shopify)) if f)
        if report_only:
            print(f"  would write {where:<19} {title}  ({len((product.get('description') or ''))} -> {len(wanted)} chars)")
            written += 1
            continue
        try:
            if needs_printify:
                printify.update_product(product["id"], {"description": wanted})
            if needs_shopify:
                external = product.get("external") or {}
                if external.get("id"):
                    shopify.update_product(f"gid://shopify/Product/{external['id']}",
                                           descriptionHtml=wanted)
            print(f"  {title}: {where} ({len(wanted)} chars)")
            written += 1
        except Exception as err:
            print(f"  FAILED {title}: {err}")
    verb = "would write" if report_only else "written"
    print(f"\n{written} {verb}, {skipped} out of scope, {len(missing)} with no facts anywhere.")
    for title in missing:
        print(f"  NO FACTS: {title}  (research this temple, save the fragment, re-run)")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--temple")
    ap.add_argument("--product-id", help="Write to one explicit product instead of status.json entries")
    ap.add_argument("--garment", help="Garment id for --product-id (selects the right fixed sections)")
    ap.add_argument("--repair", action="store_true",
                    help="Rebuild every product's description on Printify and Shopify from its "
                         "garment's fixed sections plus its own temple's facts")
    ap.add_argument("--normalize", action="store_true",
                    help="Also rewrite descriptions that are intact but differ from the repo's "
                         "current approved copy. A copy decision, not a repair: some live products "
                         "carry an older intro.")
    ap.add_argument("--report-only", action="store_true", help="with --repair: write nothing")
    args = ap.parse_args()

    if args.repair or args.normalize:
        repair(report_only=args.report_only, normalize=args.normalize)
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
