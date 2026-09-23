#!/usr/bin/env python
"""The Shop collection behind the homepage button: one card per garment, plus designs
that are not a single temple's.

  python scripts/shop_collection.py            # dry run: what exists and what would change
  python scripts/shop_collection.py --apply    # create and publish it, tag the art file

Rules (any of): tag listing:parent (the Salt Lake tee, crew and, after the Easify
re-import, hoodie; their Temple dropdown reaches every other temple) or tag
listing:standalone (products with no dropdown: the Temple Art File now, future
non-temple designs later). The two tags stay separate so the planned parents-only All
Temples collection never picks up the art file.
"""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from shopify_client import ShopifyClient, ShopifyError  # noqa: E402

HANDLE = "shop"
TITLE = "Shop"
STANDALONE = "listing:standalone"
STANDALONE_PRODUCTS = ["temple-art-file"]
RULES = [{"column": "TAG", "relation": "EQUALS", "condition": "listing:parent"},
         {"column": "TAG", "relation": "EQUALS", "condition": STANDALONE}]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args(argv)
    c = ShopifyClient()

    existing = c.gql("""query($h: String!) { collectionByHandle(handle: $h) { id title
        products(first: 50) { nodes { title } } } }""", {"h": HANDLE})["collectionByHandle"]
    todo_tags = []
    for handle in STANDALONE_PRODUCTS:
        p = c.gql("""query($h: String!) { productByHandle(handle: $h) { id tags } }""",
                  {"h": handle})["productByHandle"]
        if p is None:
            raise SystemExit(f"no product with handle {handle}")
        if STANDALONE not in p["tags"]:
            todo_tags.append((handle, p["id"]))

    print(f"collection {HANDLE}: {'exists' if existing else 'to create'}")
    print(f"tag {STANDALONE} to add on: {[h for h, _ in todo_tags] or 'nothing'}")
    if not args.apply:
        print("\nDRY RUN. Re-run with --apply after Evan's go.")
        return 0

    for handle, gid in todo_tags:
        errs = c.gql("""mutation($id: ID!, $t: [String!]!) { tagsAdd(id: $id, tags: $t) {
            userErrors { message } } }""", {"id": gid, "t": [STANDALONE]})["tagsAdd"]["userErrors"]
        if errs:
            raise SystemExit(f"tagging {handle} failed: {errs}")

    cid = existing["id"] if existing else None
    if not existing:
        res = c.gql("""mutation($input: CollectionInput!) { collectionCreate(input: $input) {
            collection { id } userErrors { field message } } }""",
            {"input": {"title": TITLE, "handle": HANDLE,
                       "ruleSet": {"appliedDisjunctively": True, "rules": RULES}}})["collectionCreate"]
        if res["userErrors"]:
            raise SystemExit(f"collectionCreate failed: {res['userErrors']}")
        cid = res["collection"]["id"]

    # Publish on every --apply, not just on creation, so a run that could not publish
    # can be finished later. The app's token has no publications scope today, so this
    # usually ends in the manual step below rather than a crash.
    problem = publish_to_online_store(c, cid)
    if problem:
        print(f"Shop exists but is NOT published to the Online Store ({problem}).")
        print("Until it is, it shows as a missing page. Evan: Shopify admin > Products > "
              "Collections > Shop > Sales channels > Online Store.")
        return 1

    after = c.gql("""query($h: String!) { collectionByHandle(handle: $h) {
        products(first: 50) { nodes { title } } } }""", {"h": HANDLE})["collectionByHandle"]
    print("Shop now holds:", [n["title"] for n in after["products"]["nodes"]])
    return 0


def publish_to_online_store(c, cid):
    """None when published; otherwise the reason it could not be."""
    try:
        pubs = c.gql("{ publications(first: 20) { nodes { id name } } }")["publications"]["nodes"]
        store = [p["id"] for p in pubs if p["name"] == "Online Store"]
        if not store:
            return "no Online Store channel found"
        errs = c.gql("""mutation($id: ID!, $p: [PublicationInput!]!) { publishablePublish(id: $id,
            input: $p) { userErrors { message } } }""",
            {"id": cid, "p": [{"publicationId": pid} for pid in store]})["publishablePublish"]["userErrors"]
    except ShopifyError as exc:  # most likely the missing read/write_publications scope
        return str(exc)[:160]
    return f"{errs}" if errs else None


if __name__ == "__main__":
    sys.exit(main())
