"""Shopify-side corrections the Printify publish cannot make itself.

  python scripts/shopify_fixups.py all --report-only     # what would change
  python scripts/shopify_fixups.py all                   # both fixups, whole catalog
  python scripts/shopify_fixups.py unlist
  python scripts/shopify_fixups.py hoodie-color
  python scripts/shopify_fixups.py color-order
  python scripts/shopify_fixups.py all --handle logan-temple-hoodie

Two fixups, both idempotent and safe to re-run:

color-order
  Moves each garment's `storefront_first_color` to the front of its Color
  option (Moss on tees, True Navy on crews, Denim on hoodies). Shopify
  preselects variant position 1 and computes position from the option value
  order, so this is the only lever it gives over which variant a product page
  opens on. It is also the swatch display order, so the chosen color moves to
  the front of the swatch row too. Printify's own default variant is a
  separate, Printify-side thing that never crosses over; see
  scripts/default_variant.py.

unlist
  Every temple product except the parent temple's goes to Shopify status
  UNLISTED. The storefront then shows one listing per garment line and
  shoppers reach the rest through the Easify Temple dropdown on the parent
  page. Unlisted products keep working URLs, so every dropdown link and every
  existing link still resolves.

hoodie-color
  Renames the hoodie colorway "True Navy" to "Blue Jean". Printify labels this
  colorway True Navy on the CC1567 hoodie, but it does not match the True Navy
  on the CC1717 tee or the CC1566 crew; it matches their Blue Jean. Evan's
  call (22 Aug 2026): Printify has it wrong and the storefront should read
  Blue Jean. The rename is Shopify-only, so Printify order line items still
  say True Navy, and any future Printify republish re-syncs variants and
  pushes the old name back. That is why this is a standalone re-runnable
  command and part of the end-of-run sequence, not a one-shot.

publish_drafts.py calls fix_published_product() on each product it publishes,
so a normal run needs neither command by hand.
"""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
# Also as a sibling: publish_drafts imports this as scripts.shopify_fixups,
# where the scripts directory is not on the path the way it is for a direct run.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from art_images import EXCLUDE_MARKERS, match_temple, temple_tokens
from generate import GARMENTS_DIR, load_garment_config, parent_temple, parent_titles
from shopify_client import ShopifyClient

HOODIE_TYPE = "Hoodie"
COLOR_OPTION = "Color"
HOODIE_OLD_COLOR = "True Navy"
HOODIE_NEW_COLOR = "Blue Jean"
HOODIE_OPTION = COLOR_OPTION  # kept for readability at the hoodie call sites
SIZE_OPTION = "Size"
# Shopify re-derives every option's value order from the variant sequence after
# a reorder, so this is a best effort, not a guarantee: a first color missing a
# size pushes that size to the back. Feeding it in canonically each time keeps
# a re-run from compounding the damage.
SIZE_ORDER = ["S", "M", "L", "XL", "2XL", "3XL", "4XL"]
OTHER_ORDERS = {SIZE_OPTION: SIZE_ORDER}


def first_colors_by_type():
    """{Shopify productType: the color that should sit first}, from
    `storefront_first_color` in garments/*.json. Two garments sharing a
    product type must agree; a disagreement is a hard stop rather than a
    coin flip (the tee and the dated tee are both "T-Shirt")."""
    out = {}
    for path in GARMENTS_DIR.glob("*.json"):
        cfg = load_garment_config(path.stem)
        color = cfg.get("storefront_first_color")
        if not color:
            continue
        ptype = cfg["product_type"]
        if out.get(ptype, color) != color:
            raise SystemExit(f"{ptype}: garments disagree on storefront_first_color "
                             f"({out[ptype]!r} vs {color!r}). Fix garments/*.json.")
        out[ptype] = color
    return out


def wants_color_order(product):
    """Any temple product whose garment declares a first color. Copies and
    test products excluded; Limited Edition one-offs included, since the
    swatch order is equally wrong on them."""
    if product.get("productType") not in first_colors_by_type():
        return False
    title = product["title"]
    if " Temple" not in title:
        return False
    return not any(x in title.lower() for x in EXCLUDE_MARKERS if x != "limited edition")


def is_parent_product(title):
    """Parent listings carry the bare garment title, no place in parentheses."""
    return title.strip() in parent_titles()


def wants_unlisting(product, tokens):
    """A child temple product that is not already unlisted.

    Scoped through match_temple so it can only ever touch a product this
    pipeline recognizes as one temple's listing: Limited Edition one-offs,
    unclaimed copies and anything non-temple are invisible to it."""
    title = product["title"]
    if is_parent_product(title):
        return False
    if match_temple(title, tokens) is None:
        return False
    return product["status"] != "UNLISTED"


def wants_hoodie_color(product):
    """Any hoodie in the temple catalog, parent and Limited Edition included:
    the colorway is mislabeled on all of them equally. Copies and test
    products are excluded."""
    if product.get("productType") != HOODIE_TYPE:
        return False
    title = product["title"]
    if " Temple" not in title:
        return False
    return not any(x in title.lower() for x in EXCLUDE_MARKERS if x != "limited edition")


def fix_published_product(client, product_gid, title, product_type, report_only=False):
    """Every Shopify fixup for one product. Returns a list of action strings,
    empty when nothing needed doing. Used per-product at publish time and in
    bulk by the commands below."""
    actions = []
    if not is_parent_product(title):
        if report_only:
            actions.append("would unlist")
        else:
            client.update_product(product_gid, status="UNLISTED")
            actions.append("unlisted")
    if product_type == HOODIE_TYPE:
        if report_only:
            actions.append(f"would rename {HOODIE_OLD_COLOR} -> {HOODIE_NEW_COLOR}")
        elif client.rename_option_value(product_gid, HOODIE_OPTION,
                                        HOODIE_OLD_COLOR, HOODIE_NEW_COLOR):
            actions.append(f"{HOODIE_OLD_COLOR} -> {HOODIE_NEW_COLOR}")
    # After the rename, so a hoodie asking for Blue Jean finds it under that name.
    first = first_colors_by_type().get(product_type)
    if first:
        if report_only:
            actions.append(f"would put {first} first")
        elif client.reorder_option_values(product_gid, COLOR_OPTION, first, OTHER_ORDERS):
            actions.append(f"{first} first")
    return actions


def run(command, report_only=False, handle=None):
    client = ShopifyClient()
    tokens = temple_tokens()
    catalog = sorted(client.all_products_summary(), key=lambda p: p["title"])
    if handle:
        catalog = [p for p in catalog if p["handle"] == handle]
        if not catalog:
            raise SystemExit(f"No Shopify product with handle {handle!r}.")

    do_unlist = command in ("all", "unlist")
    do_color = command in ("all", "hoodie-color")
    do_order = command in ("all", "color-order")
    first_colors = first_colors_by_type()
    changed = 0
    for product in catalog:
        title, gid = product["title"], product["id"]
        actions = []
        if do_unlist and wants_unlisting(product, tokens):
            if report_only:
                actions.append("unlist")
            else:
                client.update_product(gid, status="UNLISTED")
                actions.append("unlisted")
        if do_color and wants_hoodie_color(product):
            if report_only:
                actions.append(f"maybe {HOODIE_OLD_COLOR} -> {HOODIE_NEW_COLOR}")
            elif client.rename_option_value(gid, HOODIE_OPTION,
                                            HOODIE_OLD_COLOR, HOODIE_NEW_COLOR):
                actions.append(f"{HOODIE_OLD_COLOR} -> {HOODIE_NEW_COLOR}")
        # After the rename, so a hoodie asking for Blue Jean finds it under that name.
        if do_order and wants_color_order(product):
            first = first_colors[product["productType"]]
            if report_only:
                actions.append(f"maybe {first} first")
            elif client.reorder_option_values(gid, COLOR_OPTION, first, OTHER_ORDERS):
                actions.append(f"{first} first")
        if actions:
            changed += 1
            print(f"  {title!r}: {', '.join(actions)}")

    parents = [p["title"] for p in catalog if is_parent_product(p["title"])]
    print(f"\n{len(catalog)} product(s) scanned, {changed} touched. "
          f"Parent listings left active: {', '.join(sorted(parents)) or 'none in scope'}")
    if report_only:
        print("Report only, nothing written. The colorway lines say 'maybe' because "
              "whether True Navy is still present is only known at write time.")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["all", "unlist", "hoodie-color", "color-order"])
    ap.add_argument("--report-only", action="store_true", help="print, write nothing")
    ap.add_argument("--handle", help="restrict to one product handle")
    args = ap.parse_args()
    run(args.command, report_only=args.report_only, handle=args.handle)


if __name__ == "__main__":
    main()
