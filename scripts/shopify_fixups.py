"""Shopify-side corrections a Tapstitch publish cannot make itself.

  python scripts/shopify_fixups.py all --report-only     # what would change
  python scripts/shopify_fixups.py all                   # every fixup, whole catalog
  python scripts/shopify_fixups.py color-names
  python scripts/shopify_fixups.py color-order
  python scripts/shopify_fixups.py all --handle logan-temple-hoodie

Two fixups, both idempotent and safe to re-run:

color-names (also accepted as hoodie-color, its old name)
  Tapstitch colour names, from the `colorways` block in each garment config:
  Caramel Machiato -> Caramel, Wine Red -> Maroon, Grape Purple -> Grape
  (Evan's call, 14 Sep 2026). Adding or changing one is a config edit, not a
  code edit. Shopify-only, so anything that re-syncs variants from Tapstitch
  pushes the original names back; that is why this is a re-runnable command.

color-order
  Moves each garment's `storefront_first_color` to the front of its Color
  option. Shopify preselects variant position 1 and computes position from the
  option value order, so this is the only lever it gives over which variant a
  product page opens on. It is also the swatch display order, so the chosen
  color moves to the front of the swatch row too.

Nothing here touches a product's status. scripts/tapstitch_publish.py calls
fix_published_product() on each product it finishes, so a normal run needs
neither command by hand.
"""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
# Also as a sibling, so art_images resolves however this module is imported.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from art_images import EXCLUDE_MARKERS
from generate import GARMENTS_DIR, load_garment_config
from shopify_client import ShopifyClient

COLOR_OPTION = "Color"
SIZE_OPTION = "Size"
# Shopify re-derives every option's value order from the variant sequence after
# a reorder, so this is a best effort, not a guarantee: a first color missing a
# size pushes that size to the back. Feeding it in canonically each time keeps
# a re-run from compounding the damage.
SIZE_ORDER = ["S", "M", "L", "XL", "2XL", "3XL", "4XL"]
OTHER_ORDERS = {SIZE_OPTION: SIZE_ORDER}


def colorway_renames_by_type():
    """{productType: [(Tapstitch name, storefront name), ...]}.

    Tapstitch's own colour names ship through to Shopify, and three of them are
    not what Evan wants a customer to read: Caramel Machiato, Wine Red and Grape
    Purple become Caramel, Maroon and Grape. The mapping lives in each Tapstitch
    garment config's `colorways`, so adding or renaming a colour is a config edit.

    Shopify-only: Tapstitch order line items keep their own names, and anything
    that re-syncs variants from Tapstitch will push the original names back. That
    is why this is a re-runnable command in the end-of-run sequence and not a
    one-shot.
    """
    out = {}
    for path in GARMENTS_DIR.glob("*.json"):
        cfg = load_garment_config(path.stem)
        if cfg.get("channel") != "tapstitch":
            continue
        pairs = [(c["tapstitch"], c["shopify"]) for c in cfg.get("colorways", [])
                 if c.get("tapstitch") and c.get("shopify") and c["tapstitch"] != c["shopify"]]
        if pairs:
            out.setdefault(cfg["product_type"], []).extend(pairs)
    return out


def wants_colorway_renames(product):
    """Any temple product of a type that has renames declared. Copies, templates
    and test titles excluded; Limited Edition included, since a mislabeled colour
    reads equally wrong on a one-off."""
    if product.get("productType") not in colorway_renames_by_type():
        return False
    title = product["title"]
    if " Temple" not in title:
        return False
    return not any(x in title.lower() for x in EXCLUDE_MARKERS if x != "limited edition")


def first_colors_by_type():
    """{Shopify productType: the color that should sit first}, from
    `storefront_first_color` in garments/*.json. Two garments sharing a
    product type must agree; a disagreement is a hard stop rather than a
    coin flip."""
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


def fix_published_product(client, product_gid, product_type, report_only=False):
    """Every Shopify fixup for one product. Returns a list of action strings,
    empty when nothing needed doing. Used per-product at publish time and in
    bulk by the commands below."""
    actions = []
    for old_name, new_name in colorway_renames_by_type().get(product_type, []):
        if report_only:
            actions.append(f"would rename {old_name} -> {new_name}")
        elif client.rename_option_value(product_gid, COLOR_OPTION, old_name, new_name):
            actions.append(f"{old_name} -> {new_name}")
    # After the renames, so a product asking for a storefront colour name finds
    # it under that name rather than Tapstitch's original.
    first = first_colors_by_type().get(product_type)
    if first:
        if report_only:
            actions.append(f"would put {first} first")
        elif client.reorder_option_values(product_gid, COLOR_OPTION, first, OTHER_ORDERS):
            actions.append(f"{first} first")
    return actions


def run(command, report_only=False, handle=None):
    client = ShopifyClient()
    catalog = sorted(client.all_products_summary(), key=lambda p: p["title"])
    if handle:
        catalog = [p for p in catalog if p["handle"] == handle]
        if not catalog:
            raise SystemExit(f"No Shopify product with handle {handle!r}.")

    do_color = command in ("all", "color-names", "hoodie-color")
    do_order = command in ("all", "color-order")
    first_colors = first_colors_by_type()
    changed = 0
    for product in catalog:
        title, gid = product["title"], product["id"]
        actions = []
        if do_color and wants_colorway_renames(product):
            for old_name, new_name in colorway_renames_by_type()[product["productType"]]:
                if report_only:
                    actions.append(f"maybe {old_name} -> {new_name}")
                elif client.rename_option_value(gid, COLOR_OPTION, old_name, new_name):
                    actions.append(f"{old_name} -> {new_name}")
        # After the renames, so a product asking for a storefront colour name finds
        # it under that name rather than Tapstitch's original.
        if do_order and wants_color_order(product):
            first = first_colors[product["productType"]]
            if report_only:
                actions.append(f"maybe {first} first")
            elif client.reorder_option_values(gid, COLOR_OPTION, first, OTHER_ORDERS):
                actions.append(f"{first} first")
        if actions:
            changed += 1
            print(f"  {title!r}: {', '.join(actions)}")

    print(f"\n{len(catalog)} product(s) scanned, {changed} touched.")
    if report_only:
        print("Report only, nothing written. The colorway lines say 'maybe' because "
              "whether the old name is still present is only known at write time.")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command",
                    choices=["all", "color-names", "hoodie-color", "color-order"])
    ap.add_argument("--report-only", action="store_true", help="print, write nothing")
    ap.add_argument("--handle", help="restrict to one product handle")
    args = ap.parse_args()
    run(args.command, report_only=args.report_only, handle=args.handle)


if __name__ == "__main__":
    main()
