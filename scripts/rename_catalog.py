"""One-time backfill: rename the whole catalog to the new product naming.

  python scripts/rename_catalog.py --report-only          # the full old -> new table
  python scripts/rename_catalog.py --only "Logan Temple Hoodie"
  python scripts/rename_catalog.py                        # the whole catalog

Old titles led with the temple ("Logan Temple Hoodie"). New titles lead with
the garment line and carry the temple in parentheses ("Pillar Temple Hoodie
(Logan)"), except the parent temple's, which carry the bare line ("Pillar
Temple Hoodie"). See garments/*.json and config/catalog.json.

Each product is written on BOTH sides: the title goes to Printify, then to
Shopify. Deliberately no Printify republish. A republish re-syncs title,
images and variants together and would undo the UNLISTED status that keeps
every non-parent listing off the storefront. Shopify keeps a product's handle
across a title change, so every Easify dropdown URL and every existing link
survives untouched.

Shopify is addressed by the Shopify product id Printify already stores in
external.id, never by title: two products currently share the title "Nauvoo
Temple Sweatshirt (front logo)", and a title lookup cannot tell them apart.

Anything this cannot parse is a hard stop, printed and skipped rather than
renamed to a guess.
"""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from art_images import temple_tokens
from generate import build_title, load_garment_config, parent_titles, title_is_dated
from printify_client import PrintifyClient, PrintifyError, load_config
from shopify_client import ShopifyClient, ShopifyError

# blueprint -> garment config id. 706 splits on whether the title is dated.
BLUEPRINTS = {706: ("cc1717", "cc1717-dated"), 1296: ("cc1566", None), 1298: ("cc1567", None)}

# Evan's hand-built one-offs. Their old titles do not follow the pattern (one
# is a hoodie titled "Sweatshirt"), so they are named explicitly rather than
# parsed. Evan's 22 Aug 2026 call: they all become Limited Edition under the
# garment line they actually are.
ONE_OFFS = {
    "Nauvoo Temple Tee - Limited Edition": "Essential Temple Tee – Limited Edition (Nauvoo)",
    "Nauvoo Temple Hoodie (front logo)": "Pillar Temple Hoodie – Limited Edition (Nauvoo)",
    "Nauvoo Temple Sweatshirt (front logo)": "Classic Temple Crew Sweatshirt – Limited Edition (Nauvoo)",
}

# Products Evan already renamed by hand, in wordings that predate the settled
# one. Canonical is an en dash and lowercase: "Essential Temple Tee – with
# personalizable date (Layton)".
NORMALIZE = {
    "Essential Temple Tee - with personalizable date": "Essential Temple Tee – with personalizable date",
    "Essential Temple Tee – With Personalizable Date (Layton)":
        "Essential Temple Tee – with personalizable date (Layton)",
}


def garment_for(product):
    """The garment config id behind a product, from its blueprint plus, for
    the tee blueprint, whether the title is the personalizable line."""
    base, dated = BLUEPRINTS.get(product.get("blueprint_id"), (None, None))
    if base is None:
        return None
    return dated if (dated and title_is_dated(product.get("title") or "")) else base


def parse_old_title(title, tokens):
    """Pull the place token out of an old '{place} Temple {Garment}' title.

    Longest token first, so 'Provo City Center Temple Tee' resolves to Provo
    City Center and not Provo. Returns (temple_folder, place_token) or None."""
    for tok in sorted(tokens, key=len, reverse=True):
        if title.startswith(tok + " Temple "):
            return tokens[tok], tok
    return None


def intended_title(product, tokens, current_titles):
    """(new_title, note). new_title is None when nothing should change; note
    explains a skip or a hard stop."""
    title = (product.get("title") or "").strip()

    if title.lower().startswith("copy of"):
        return None, "unclaimed duplicate, renamed when the generator claims it"
    if title in ONE_OFFS:
        return ONE_OFFS[title], "one-off"
    if title in NORMALIZE:
        return NORMALIZE[title], "normalizing an earlier hand rename"
    if title in current_titles or title in parent_titles():
        return None, "already correct"

    garment = garment_for(product)
    if garment is None:
        return None, f"HARD STOP: unknown blueprint {product.get('blueprint_id')}"
    parsed = parse_old_title(title, tokens)
    if parsed is None:
        return None, "HARD STOP: cannot read a temple out of this title"
    temple, place = parsed
    return build_title(load_garment_config(garment), temple, place), ""


def shopify_gid(product):
    external = product.get("external") or {}
    sid = external.get("id")
    return f"gid://shopify/Product/{sid}" if sid else None


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--report-only", action="store_true", help="print the table, write nothing")
    ap.add_argument("--only", help="restrict to products whose title contains this text")
    args = ap.parse_args()

    token, shop_id = load_config()
    printify = PrintifyClient(token, shop_id)
    shopify = ShopifyClient()

    products = sorted(printify.all_products(), key=lambda p: p["title"])
    tokens = temple_tokens()

    # Every title a correctly named product could already have, so a re-run
    # recognizes its own past work instead of trying to parse it as an old title.
    current_titles = set()
    for gid_path in (PROJECT_ROOT / "garments").glob("*.json"):
        cfg = load_garment_config(gid_path.stem)
        current_titles.add(cfg["naming"]["title_parent"])
        for tok in tokens:
            current_titles.add(cfg["naming"]["title"].format(place=tok))
    current_titles.update(ONE_OFFS.values())

    plan, skipped, stops = [], [], []
    for product in products:
        title = product["title"].strip()
        if args.only and args.only.lower() not in title.lower():
            continue
        new, note = intended_title(product, tokens, current_titles)
        if new is None:
            (stops if note.startswith("HARD STOP") else skipped).append((title, note))
            continue
        if new == title:
            skipped.append((title, "already correct"))
            continue
        plan.append((product, title, new, note))

    print(f"{len(products)} product(s) on Printify\n")
    for _, old, new, note in plan:
        suffix = f"   [{note}]" if note else ""
        print(f"  {old}\n    -> {new}{suffix}")
    if skipped:
        print(f"\nUnchanged ({len(skipped)}):")
        for title, note in skipped:
            print(f"  {title}  ({note})")
    if stops:
        print(f"\nCOULD NOT PARSE ({len(stops)}) - these are left alone:")
        for title, note in stops:
            print(f"  {title}  ({note})")

    print(f"\n{len(plan)} rename(s) planned, {len(skipped)} unchanged, {len(stops)} unparseable.")
    if args.report_only:
        print("Report only, nothing written.")
        return
    if not plan:
        return

    failures = 0
    for product, old, new, _ in plan:
        try:
            printify.update_product(product["id"], {"title": new})
        except PrintifyError as err:
            print(f"  PRINTIFY FAILED {old!r}: {err}")
            failures += 1
            continue
        gid = shopify_gid(product)
        if not gid:
            print(f"  {old!r} -> {new!r} (Printify only; never published to Shopify)")
            continue
        try:
            shopify.update_product(gid, title=new)
        except ShopifyError as err:
            print(f"  SHOPIFY FAILED {old!r} (Printify already renamed): {err}")
            failures += 1
            continue
        print(f"  {old!r} -> {new!r}")

    if failures:
        sys.exit(f"\n{failures} rename(s) did not complete on both sides.")
    print(f"\nDone. {len(plan)} product(s) renamed on Printify and Shopify.")


if __name__ == "__main__":
    main()
