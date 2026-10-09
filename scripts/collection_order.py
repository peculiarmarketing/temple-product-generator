"""Card order for the shop collections behind the homepage "Shop by garment" tabs.

Each garment collection reads temple, map, Be Peculiar, Be Peculiar Espanol;
All Designs (the "All Products" tab) reads hoodies, tees, sweatshirts, then the
Art File and the bomber. Sort order is set to MANUAL and the listed handles are
moved to the front in this order. The collection rules are not touched, so a
product that joins later through its tags lands after these.

Usage:
  python scripts/collection_order.py            # report only
  python scripts/collection_order.py --apply    # write
"""

import argparse
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from shopify_client import ShopifyClient

HOODIES = ["cloud-temple-hoodie", "ultra-soft-oversized-map-hoodie-salt-lake-city",
           "ultra-soft-oversized-be-peculiar-hoodie",
           "ultra-soft-oversized-be-peculiar-hoodie-espanol"]
TEES = ["essential-heavyweight-temple-tee", "essential-heavyweight-map-tee-salt-lake-city",
        "essential-heavyweight-be-peculiar-tee", "essential-heavyweight-be-peculiar-tee-espanol"]
SWEATSHIRTS = ["salt-lake-temple-sweatshirt", "ultra-soft-map-sweatshirt-salt-lake-city",
               "ultra-soft-be-peculiar-sweatshirt", "ultra-soft-be-peculiar-sweatshirt-espanol"]
ORDER = {
    "hoodies": HOODIES,
    "tees": TEES,
    "sweatshirts": SWEATSHIRTS,
    "temple-design-products": HOODIES + TEES + SWEATSHIRTS
                              + ["temple-art-file", "temple-seal-bomber-jacket"],
}


def collection(client, handle):
    data = client.gql("""query($h: String!) { collectionByHandle(handle: $h) {
        id sortOrder products(first: 250, sortKey: COLLECTION_DEFAULT) {
          nodes { id handle status } } } }""", {"h": handle})
    return data["collectionByHandle"]


def wait_job(client, job):
    while job and not job["done"]:
        time.sleep(1)
        job = client.gql("query($id: ID!) { job(id: $id) { id done } }",
                         {"id": job["id"]})["job"]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="write to the live store")
    args = ap.parse_args()
    client = ShopifyClient()
    for handle, want in ORDER.items():
        c = collection(client, handle)
        active = [p["handle"] for p in c["products"]["nodes"] if p["status"] == "ACTIVE"]
        missing = [h for h in want if h not in active]
        if missing:
            raise SystemExit(f"{handle}: not in the collection or not ACTIVE: {missing}")
        if c["sortOrder"] == "MANUAL" and active[:len(want)] == want:
            print(f"{handle}: already in order")
            continue
        print(f"{handle}: {c['sortOrder']} -> MANUAL, {len(want)} cards to the front")
        if not args.apply:
            continue
        if c["sortOrder"] != "MANUAL":
            errs = client.gql("""mutation($i: CollectionInput!) { collectionUpdate(input: $i) {
                userErrors { field message } } }""",
                {"i": {"id": c["id"], "sortOrder": "MANUAL"}})["collectionUpdate"]["userErrors"]
            if errs:
                raise SystemExit(f"{handle}: {errs}")
        ids = {p["handle"]: p["id"] for p in c["products"]["nodes"]}
        moves = [{"id": ids[h], "newPosition": str(i)} for i, h in enumerate(want)]
        out = client.gql("""mutation($id: ID!, $m: [MoveInput!]!) {
            collectionReorderProducts(id: $id, moves: $m) {
              job { id done } userErrors { field message } } }""",
            {"id": c["id"], "m": moves})["collectionReorderProducts"]
        if out["userErrors"]:
            raise SystemExit(f"{handle}: {out['userErrors']}")
        wait_job(client, out["job"])
        now = [p["handle"] for p in collection(client, handle)["products"]["nodes"]
               if p["status"] == "ACTIVE"]
        if now[:len(want)] != want:
            raise SystemExit(f"{handle}: read-back order is {now}")
        print("  done, read back")


if __name__ == "__main__":
    main()
