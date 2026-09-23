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

from shopify_client import ShopifyClient  # noqa: E402

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

    if not existing:
        res = c.gql("""mutation($input: CollectionInput!) { collectionCreate(input: $input) {
            collection { id } userErrors { field message } } }""",
            {"input": {"title": TITLE, "handle": HANDLE,
                       "ruleSet": {"appliedDisjunctively": True, "rules": RULES}}})["collectionCreate"]
        if res["userErrors"]:
            raise SystemExit(f"collectionCreate failed: {res['userErrors']}")
        cid = res["collection"]["id"]
        pubs = c.gql("{ publications(first: 20) { nodes { id name } } }")["publications"]["nodes"]
        store = [p["id"] for p in pubs if p["name"] == "Online Store"]
        try:
            errs = c.gql("""mutation($id: ID!, $p: [PublicationInput!]!) { publishablePublish(id: $id,
                input: $p) { userErrors { message } } }""",
                {"id": cid, "p": [{"publicationId": pid} for pid in store]})["publishablePublish"]["userErrors"]
        except Exception as exc:  # most likely a missing write_publications scope
            errs = [str(exc)]
        if errs or not store:
            print(f"created, but NOT published to the Online Store ({errs or 'no Online Store channel'}).")
            print("Evan: Shopify admin > Products > Collections > Shop > Sales channels > Online Store.")

    after = c.gql("""query($h: String!) { collectionByHandle(handle: $h) {
        products(first: 50) { nodes { title } } } }""", {"h": HANDLE})["collectionByHandle"]
    print("Shop now holds:", [n["title"] for n in after["products"]["nodes"]])
    return 0


if __name__ == "__main__":
    sys.exit(main())
