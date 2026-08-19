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

from printify_client import PrintifyClient, PrintifyError, load_config

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
    if "(front logo)" in title.lower():
        return False, "test product"
    personalisation = (product.get("sales_channel_properties") or {}).get("personalisation") or {}
    if " - With Date" in title or personalisation.get("layers"):
        # Lazy import keeps this module import-light and avoids coupling
        # at import time.
        from scripts.add_date_layer import verify, load_layer_config, load_dated_spacing
        problems = verify(product, load_layer_config(), load_dated_spacing())
        if problems:
            return False, f"dated draft failed date-layer verification: {problems[0]}"
    if 'class="temple-facts"' not in (product.get("description") or ""):
        return False, "description has no temple facts section yet"
    return True, "eligible"


def all_products(client):
    products, page = [], 1
    while True:
        data = client._request("GET", f"/shops/{client.shop_id}/products.json?limit=50&page={page}")
        products.extend(data["data"])
        if not data.get("next_page_url"):
            break
        page += 1
    return products


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
        try:
            result = publish_one(client, product, shopify=shopify)
        except PrintifyError as err:
            print(f"  FAILED: {err}")
            failures += 1
            continue
        if result:
            note = "" if result["via"] == "printify" else " (Printify still syncing its own status)"
            print(f"  Live on Shopify: {result['handle']}{note}")
        else:
            print(f"  TIMED OUT after {POLL_TIMEOUT_S}s: Printify accepted the publish but neither "
                  "Printify nor Shopify confirms it yet. Check the product in Printify before retrying.")
            failures += 1

    if failures:
        sys.exit(f"\n{failures} publish(es) did not complete.")
    print(f"\nDone. {len(to_publish)} product(s) published.")


if __name__ == "__main__":
    main()
