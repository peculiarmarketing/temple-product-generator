"""Keep each garment's default variant on the colorway Evan wants.

  python scripts/default_variant.py --report-only
  python scripts/default_variant.py
  python scripts/default_variant.py --only "(Bountiful)"

The wanted colorway is declared per garment as `default_colorway` in
garments/*.json; only the dated tee sets one today (Moss, Evan's 22 Aug 2026
decision). A garment with no `default_colorway` is left alone.

The size is preserved: a product defaulting to "True Navy / L" moves to
"Moss / L", not to whatever Moss variant happens to come first. If that exact
size is not enabled, the first enabled variant of the colorway is used.

Scope note, measured 22 Aug 2026: is_default IS writable through the Printify
API, contrary to the Revision-2 spec. What it moves is Printify's own default,
which is what drives mockup selection. Shopify orders variants itself and does
not follow it, so the storefront's preselected variant is unchanged by this.
"""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from generate import GARMENTS_DIR, load_garment_config, title_is_one_off
from printify_client import PrintifyClient, PrintifyError, load_config


def colorway_of(variant):
    return (variant.get("title") or "").split("/")[0].strip()


def size_of(variant):
    parts = (variant.get("title") or "").split("/")
    return parts[1].strip() if len(parts) > 1 else ""


def wanted_default(variants, colorway):
    """The variant that should carry is_default, or None if the colorway has
    no enabled variant on this product. Keeps the current default's size."""
    candidates = [v for v in variants
                  if colorway_of(v) == colorway and v.get("is_enabled")]
    if not candidates:
        return None
    current = next((v for v in variants if v.get("is_default")), None)
    if current:
        same_size = next((v for v in candidates if size_of(v) == size_of(current)), None)
        if same_size:
            return same_size
    return candidates[0]


def garments_by_blueprint():
    """{(blueprint_id, dated): (garment_id, default_colorway)} for the garments
    that declare a default colorway."""
    out = {}
    for path in GARMENTS_DIR.glob("*.json"):
        cfg = load_garment_config(path.stem)
        colorway = cfg.get("default_colorway")
        if colorway:
            out[(cfg["blueprint_id"], "dated" in cfg["layout_profile"])] = (path.stem, colorway)
    return out


def ensure_default(client, product, colorway):
    """Move this product's default variant onto `colorway`. Returns a
    description of what changed, or None when it was already right or the
    colorway is not available. Idempotent."""
    variants = product.get("variants") or []
    current = next((v for v in variants if v.get("is_default")), None)
    if current and colorway_of(current) == colorway:
        return None
    target = wanted_default(variants, colorway)
    if target is None:
        return f"no enabled {colorway} variant"
    body = {"variants": [{"id": v["id"], "price": v["price"],
                          "is_enabled": v["is_enabled"],
                          "is_default": v["id"] == target["id"]} for v in variants]}
    client.update_product(product["id"], body)
    was = current["title"] if current else "nothing"
    return f"{was} -> {target['title']}"


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--report-only", action="store_true", help="print, write nothing")
    ap.add_argument("--only", help="restrict to titles containing this text")
    args = ap.parse_args()

    client = PrintifyClient(*load_config())
    wanted = garments_by_blueprint()
    if not wanted:
        print("No garment declares a default_colorway. Nothing to do.")
        return

    from generate import title_is_dated
    changed = failed = ok = 0
    for product in sorted(client.all_products(), key=lambda p: p["title"]):
        title = product["title"].strip()
        if title.lower().startswith("copy of") or title_is_one_off(title):
            continue
        if args.only and args.only.lower() not in title.lower():
            continue
        key = (product.get("blueprint_id"), title_is_dated(title))
        if key not in wanted:
            continue
        _, colorway = wanted[key]
        current = next((v for v in product.get("variants", []) if v.get("is_default")), None)
        if current and colorway_of(current) == colorway:
            ok += 1
            continue
        if args.report_only:
            target = wanted_default(product.get("variants") or [], colorway)
            where = target["title"] if target else f"NO ENABLED {colorway}"
            print(f"  would set  {title}  ({current['title'] if current else 'nothing'} -> {where})")
            changed += 1
            continue
        try:
            note = ensure_default(client, product, colorway)
            print(f"  {title}: {note}")
            changed += 1
        except PrintifyError as err:
            print(f"  FAILED {title}: {err}")
            failed += 1

    verb = "would change" if args.report_only else "changed"
    print(f"\n{changed} {verb}, {ok} already correct, {failed} failed.")
    if failed:
        sys.exit(f"{failed} product(s) did not update.")


if __name__ == "__main__":
    main()
