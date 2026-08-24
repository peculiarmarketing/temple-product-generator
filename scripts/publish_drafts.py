"""Publish eligible Printify drafts to the Shopify store via the API.

  python scripts/publish_drafts.py --report-only   # list what would publish and why
  python scripts/publish_drafts.py                 # publish everything eligible
  python scripts/publish_drafts.py --only "Brigham City Temple Tee"

Auto-publishes never-published products, including personalizable ones (the
With Date line) once their date-layer verification passes (see
scripts/add_date_layer.py); unverified dated drafts stay held. Safety gate:
a draft must carry the temple-facts description section (proof the pipeline
finished it). Economy shipping is NOT a gate (Evan's 19 Aug 2026 decision):
new drafts default it off and the API field is read-only, so drafts publish
regardless and the run output notes any product going live without Economy
for Evan to flip in the UI whenever. Publish settings the API cannot touch
(mockup choices, variant visibility, shipping options) ride the duplicate,
so what the donor product had is what goes live.
"""

import argparse
import sys
import time
from pathlib import Path

import requests
from dotenv import dotenv_values

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from generate import title_is_dated, title_is_one_off
from printify_client import PrintifyClient, PrintifyError, load_config
from scripts.default_variant import ensure_default, garments_by_blueprint
from scripts.shopify_fixups import fix_published_product
from shopify_client import ShopifyClient

PUBLISH_FLAGS = {
    "title": True,
    "description": True,
    "images": True,
    "variants": True,
    "tags": True,
    "keyFeatures": True,
    "shipping_template": True,
}

POLL_INTERVAL_S = 5
POLL_TIMEOUT_S = 240


def eligibility(product):
    """(ok, reason) for auto-publishing one product dict from the API."""
    title = product.get("title", "")
    if product.get("external"):
        return False, "already published"
    if product.get("is_locked"):
        return False, "locked, a publish is already in progress"
    if title.startswith("Copy of"):
        return False, "unclaimed duplicate"
    if title_is_one_off(title):
        return False, "Limited Edition one-off, Evan publishes these by hand"
    personalisation = (product.get("sales_channel_properties") or {}).get("personalisation") or {}
    if title_is_dated(title) or personalisation.get("layers"):
        # Lazy import keeps this module import-light and avoids coupling
        # at import time.
        from scripts.add_date_layer import verify, load_layer_config, load_dated_spacing
        problems = verify(product, load_layer_config(), load_dated_spacing())
        if problems:
            return False, f"dated draft failed date-layer verification: {problems[0]}"
    if 'class="temple-facts"' not in (product.get("description") or ""):
        return False, "description has no temple facts section yet"
    return True, "eligible"


def wanted_colorway(product):
    """The default colorway this product's garment declares, or None.

    Keyed the same way as scripts/default_variant.py: blueprint plus whether
    the title is the dated line."""
    key = (product.get("blueprint_id"), title_is_dated(product.get("title") or ""))
    spec = garments_by_blueprint().get(key)
    return spec[1] if spec else None


def default_variant_note(product):
    """What is wrong with this product's default variant, or None.

    A donor duplicate carries its own default, so a fresh draft routinely
    lands on the wrong colorway. Reported here, then fixed by
    fix_default_variant immediately before the publish."""
    colorway = wanted_colorway(product)
    if colorway is None:
        return None
    default = next((v for v in product.get("variants", []) if v.get("is_default")), None)
    if default is None:
        return f"no default variant set; will set {colorway}"
    current = (default.get("title") or "").split("/")[0].strip()
    if current == colorway:
        return None
    return f"default variant is {current!r}, not {colorway!r}; will be set before publishing"


def fix_default_variant(client, product):
    """Put the default variant on the garment's declared colorway, BEFORE the
    publish, so the publish push carries it.

    This used to run after publish_one, which cost two things. Printify locks a
    product while its publish is in flight, so the write raced the lock and
    failed with code 8252 often enough to matter. Worse, when it did succeed it
    was by definition an edit Printify had not pushed to the store, so every
    dated tee sat in the Printify UI badged "unpublished changes" from the
    moment it went live (observed across the 23 Aug 2026 sweep). Clearing that
    badge means a republish, and a republish deletes the art cards and reverts
    the Shopify colorway and option order. Doing the write first avoids the
    whole chain.

    Reported, never fatal. If it fails, the product still publishes, just on
    the donor's colorway; fix it afterward with default_variant.py followed by
    republish.py, since by then only a republish can carry the change over."""
    colorway = wanted_colorway(product)
    if colorway is None:
        return
    try:
        note = ensure_default(client, product, colorway)
        if note:
            print(f"  Default variant: {note}")
    except Exception as err:
        print(f"  DEFAULT VARIANT FAILED ({err}); publishing anyway on the donor's "
              f"colorway. Afterward: scripts/default_variant.py --only "
              f"{product['title']!r} then scripts/republish.py --only {product['title']!r}")


def all_products(client):
    # next_page_url goes null one page early on this shop, which hid 31 drafts.
    return client.all_products()


def shopify_find(shopify, title):
    """Exact-title lookup on Shopify. Returns the product dict or None."""
    domain, token = shopify
    resp = requests.get(
        f"https://{domain}/admin/api/2024-01/products.json",
        params={"title": title},
        headers={"X-Shopify-Access-Token": token},
        timeout=30,
    )
    resp.raise_for_status()
    hits = [p for p in resp.json()["products"] if p["title"] == title]
    return hits[0] if hits else None


def publish_one(client, product, shopify=None):
    """POST the publish, then confirm it landed. Printify's own external field
    can lag the actual Shopify push by many minutes (measured 18 Aug 2026), so
    Shopify itself is checked as the authoritative signal when creds exist."""
    pid = product["id"]
    client._request("POST", f"/shops/{client.shop_id}/products/{pid}/publish.json", json=PUBLISH_FLAGS)
    deadline = time.time() + POLL_TIMEOUT_S
    while time.time() < deadline:
        time.sleep(POLL_INTERVAL_S)
        fresh = client._request("GET", f"/shops/{client.shop_id}/products/{pid}.json")
        external = fresh.get("external")
        if external:
            return {"handle": external.get("handle"), "via": "printify"}
        if shopify:
            live = shopify_find(shopify, product["title"])
            if live and live.get("status") == "active":
                return {"handle": live.get("handle"), "via": "shopify"}
    return None


def apply_fixups(handle, title):
    """Shopify-side corrections a Printify publish cannot make: unlist the
    child listings, and rename the hoodie's mislabeled True Navy colorway.
    See scripts/shopify_fixups.py. A failure here is reported, never fatal:
    the product is already live and the fixups are re-runnable."""
    try:
        client = ShopifyClient()
        live = client.find_product_by_handle(handle)
        if not live:
            print(f"  fixups skipped: no Shopify product with handle {handle!r}")
            return
        actions = fix_published_product(client, live["id"], title, live.get("productType"))
        print(f"  Shopify fixups: {', '.join(actions)}" if actions
              else "  Shopify fixups: nothing needed")
    except SystemExit as err:          # missing Shopify creds
        print(f"  fixups skipped: {err}")
    except Exception as err:
        print(f"  FIXUPS FAILED ({err}); re-run "
              f"scripts/shopify_fixups.py all --handle {handle}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-only", action="store_true", help="list candidates, publish nothing")
    parser.add_argument("--only", help="restrict to products whose title contains this text")
    args = parser.parse_args()

    token, shop_id = load_config()
    client = PrintifyClient(token, shop_id)

    env = dotenv_values(PROJECT_ROOT / ".env")
    shopify = None
    if env.get("SHOPIFY_STORE_DOMAIN") and env.get("SHOPIFY_ADMIN_TOKEN"):
        shopify = (env["SHOPIFY_STORE_DOMAIN"], env["SHOPIFY_ADMIN_TOKEN"])

    unpublished = [p for p in all_products(client) if not p.get("external")]
    if args.only:
        unpublished = [p for p in unpublished if args.only.lower() in p["title"].lower()]
    if not unpublished:
        print("No unpublished drafts found.")
        return

    to_publish = []
    for summary in unpublished:
        # The list endpoint trims some fields; judge from the full product.
        product = client._request("GET", f"/shops/{client.shop_id}/products/{summary['id']}.json")
        ok, reason = eligibility(product)
        if ok and not product.get("is_economy_shipping_enabled"):
            reason = "eligible, note: economy shipping is off (flip in Printify UI whenever)"
        marker = "PUBLISH" if ok else "skip"
        print(f"{marker:7}  {product['title']}  ({reason})")
        variant_note = default_variant_note(product)
        if variant_note:
            print(f"         note: {variant_note}")
        if ok:
            to_publish.append(product)

    if args.report_only:
        print(f"\nReport only. {len(to_publish)} draft(s) would be published.")
        return
    if not to_publish:
        print("\nNothing eligible to publish.")
        return

    failures = 0
    for product in to_publish:
        print(f"\nPublishing {product['title']} ...")
        fix_default_variant(client, product)
        try:
            result = publish_one(client, product, shopify=shopify)
        except PrintifyError as err:
            print(f"  FAILED: {err}")
            failures += 1
            continue
        if result:
            note = "" if result["via"] == "printify" else " (Printify still syncing its own status)"
            print(f"  Live on Shopify: {result['handle']}{note}")
            apply_fixups(result["handle"], product["title"])
        else:
            print(f"  TIMED OUT after {POLL_TIMEOUT_S}s: Printify accepted the publish but neither "
                  "Printify nor Shopify confirms it yet. Check the product in Printify before retrying.")
            failures += 1

    if failures:
        sys.exit(f"\n{failures} publish(es) did not complete.")
    print(f"\nDone. {len(to_publish)} product(s) published.")


if __name__ == "__main__":
    main()
