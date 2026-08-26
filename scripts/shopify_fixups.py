"""Shopify-side corrections the Printify publish cannot make itself.

  python scripts/shopify_fixups.py all --report-only     # what would change
  python scripts/shopify_fixups.py all                   # every fixup, whole catalog
  python scripts/shopify_fixups.py hoodie-color
  python scripts/shopify_fixups.py color-order
  python scripts/shopify_fixups.py featured-photo
  python scripts/shopify_fixups.py all --handle logan-temple-hoodie

Three fixups, all idempotent and safe to re-run:

color-order
  Moves each garment's `storefront_first_color` to the front of its Color
  option (Moss on tees, True Navy on crews, Denim on hoodies). Shopify
  preselects variant position 1 and computes position from the option value
  order, so this is the only lever it gives over which variant a product page
  opens on. It is also the swatch display order, so the chosen color moves to
  the front of the swatch row too. Printify's own default variant is a
  separate, Printify-side thing that never crosses over; see
  scripts/default_variant.py.

featured-photo
  Moves the `storefront_featured_color` mockup to gallery position 1, keeping
  the art close-up card at position 2. Printify's mockup order decides the
  featured photo and leads with Graphite, so a dated tee can open on the Moss
  variant while the card still shows a Graphite shirt. Only the dated tee sets
  a featured color today (Moss, Evan's 22 Aug 2026 choice).

There is no unlist fixup anymore. New products stay ACTIVE on Shopify (Evan's
26 Aug 2026 decision); children published before then remain UNLISTED and
nothing here touches a product's status either way.

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

from art_images import EXCLUDE_MARKERS
from generate import GARMENTS_DIR, load_garment_config, title_is_dated
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
ART_ALT_PREFIX = "Temple line art close-up"


def featured_colors_by_type():
    """{productType: colorway whose mockup should be the featured photo}, from
    `storefront_featured_color` in garments/*.json. Only the dated tee sets one
    (Moss), and it shares the "T-Shirt" product type with the base tee, so this
    cannot be keyed by type alone: see wants_featured_photo."""
    out = {}
    for path in GARMENTS_DIR.glob("*.json"):
        cfg = load_garment_config(path.stem)
        color = cfg.get("storefront_featured_color")
        if color:
            out[path.stem] = (cfg["product_type"], color)
    return out


def featured_color_for(product):
    """The featured colorway for one product, or None.

    Matched on product type AND the dated marker, because the dated tee and
    the base tee are both "T-Shirt" and only the dated line has a featured
    color set."""
    for gid, (ptype, color) in featured_colors_by_type().items():
        if product.get("productType") != ptype:
            continue
        if ("dated" in gid) != title_is_dated(product["title"]):
            continue
        return color
    return None


_PRINTIFY_BY_SHOPIFY_ID = None


def printify_mockup_rgb(product_gid, colorway):
    """Average garment colour of Printify's default mockup for a colorway, or
    None. Used only as a fallback: it costs a Printify catalog fetch and an
    image download, and most products can be matched on Shopify alone."""
    global _PRINTIFY_BY_SHOPIFY_ID
    if _PRINTIFY_BY_SHOPIFY_ID is None:
        from printify_client import PrintifyClient, load_config
        client = PrintifyClient(*load_config())
        _PRINTIFY_BY_SHOPIFY_ID = {}
        for prod in client.all_products():
            external = prod.get("external") or {}
            if external.get("id"):
                _PRINTIFY_BY_SHOPIFY_ID[str(external["id"])] = prod
    product = _PRINTIFY_BY_SHOPIFY_ID.get(product_gid.rsplit("/", 1)[-1])
    if not product:
        return None
    titles = {v["id"]: v.get("title") or "" for v in product.get("variants", [])}
    for image in product.get("images", []):
        if not image.get("is_default"):
            continue
        colors = {titles.get(v, "").split("/")[0].strip() for v in (image.get("variant_ids") or [])}
        if colors == {colorway}:
            return ShopifyClient.mean_rgb(image["src"])
    return None


def set_featured_photo(client, product_gid, title, colorway):
    """Put the colorway's mockup at gallery position 1 and keep the art card
    at position 2. Returns an action string or None.

    Printify's own mockup order decides the featured photo and it leads with
    Graphite, which is why a product can open on the Moss variant while the
    card still shows a Graphite shirt. A republish does not change this."""
    media_id = client.media_id_for_colorway(product_gid, colorway)
    if media_id is None:
        # Some products carry no per-variant images on Shopify, so there is no
        # URL linking a colorway to a mockup. Fall back to matching Printify's
        # own mockup for that colorway by garment colour.
        rgb = printify_mockup_rgb(product_gid, colorway)
        media_id = client.media_id_by_color(product_gid, rgb) if rgb else None
    if media_id is None:
        return None
    if client.media_position(product_gid, media_id) == 0:
        return None
    client.move_media_to_position(product_gid, media_id, 0)
    media, _ = client.product_media_and_variants(product_gid)
    art = next((m["id"] for m in media if (m.get("alt") or "").startswith(ART_ALT_PREFIX)), None)
    if art and client.media_position(product_gid, art) != 1:
        client.move_media_to_position(product_gid, art, 1)
    return f"{colorway} photo featured"


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


def fix_published_product(client, product_gid, product_type, report_only=False):
    """Every Shopify fixup for one product. Returns a list of action strings,
    empty when nothing needed doing. Used per-product at publish time and in
    bulk by the commands below."""
    actions = []
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
    catalog = sorted(client.all_products_summary(), key=lambda p: p["title"])
    if handle:
        catalog = [p for p in catalog if p["handle"] == handle]
        if not catalog:
            raise SystemExit(f"No Shopify product with handle {handle!r}.")

    do_color = command in ("all", "hoodie-color")
    do_order = command in ("all", "color-order")
    do_photo = command in ("all", "featured-photo")
    first_colors = first_colors_by_type()
    changed = 0
    for product in catalog:
        title, gid = product["title"], product["id"]
        actions = []
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
        # Last: it reseats the art card, so it must run after the card exists.
        if do_photo and wants_color_order(product):
            featured = featured_color_for(product)
            if featured and report_only:
                actions.append(f"maybe feature {featured}")
            elif featured:
                note = set_featured_photo(client, gid, title, featured)
                if note:
                    actions.append(note)
        if actions:
            changed += 1
            print(f"  {title!r}: {', '.join(actions)}")

    print(f"\n{len(catalog)} product(s) scanned, {changed} touched.")
    if report_only:
        print("Report only, nothing written. The colorway lines say 'maybe' because "
              "whether True Navy is still present is only known at write time.")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command",
                    choices=["all", "hoodie-color", "color-order", "featured-photo"])
    ap.add_argument("--report-only", action="store_true", help="print, write nothing")
    ap.add_argument("--handle", help="restrict to one product handle")
    args = ap.parse_args()
    run(args.command, report_only=args.report_only, handle=args.handle)


if __name__ == "__main__":
    main()
