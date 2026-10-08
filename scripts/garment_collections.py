"""One collection per garment, showing one card per design (Evan, 8 Oct 2026).

Each garment collection shows the parent listing of every design line on that
garment: the Salt Lake temple parent, the Salt Lake map parent, Be Peculiar
English, Be Peculiar Espanol, and whatever lines come next. Every other temple
or map is one Easify dropdown away on its parent, so the collections stay short
however many temples and maps there are.

THE RULE. A product shows in a garment collection when it carries BOTH tags:

    apparel:<garment>   which garment it is (tee, crew, hoodie, bomber)
    listing:parent      it is the card for its design line

Both conditions have to hold, and a Shopify smart collection is either all-AND
or all-OR, so "tee AND (parent OR standalone)" cannot be written. That is why a
design with no dropdown at all (Be Peculiar, the jacket) carries listing:parent
too: it is its own line's only card. listing:standalone stays on the Temple Art
File, which belongs to no garment.

apparel: and not garment:. garment:<x> is the temple tag; the hidden
temple-tees collection ("Marquee: designed temples") is the rule garment:tee and
feeds the homepage temple marquee, so a non-temple product must never carry it.
Temple parents carry both.

Note listing:parent is also a rule of Temple Design Products (the Shop menu
collection, listing:parent OR listing:standalone), so every line's parent shows
there as well.

New collections are created unpublished: the app token has no
write_publications. Tick the sales channels in the admin once.

  python scripts/garment_collections.py           # report what is missing
  python scripts/garment_collections.py --apply   # add tags, create collections
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shopify_client import ShopifyClient

COLLECTIONS = [
    {"handle": "tees", "title": "Tees", "apparel": "tee"},
    {"handle": "sweatshirts", "title": "Sweatshirts", "apparel": "crew"},
    {"handle": "hoodies", "title": "Hoodies", "apparel": "hoodie"},
    {"handle": "jackets", "title": "Jackets", "apparel": "bomber"},
]
PARENT = "listing:parent"

# The card for each design line on each garment, by handle, with the tags it
# needs. A line's parent is added here when the line launches.
CARDS = {
    # Salt Lake temple parents: already listing:parent, need apparel:
    "essential-heavyweight-temple-tee": ["apparel:tee"],
    "salt-lake-temple-sweatshirt": ["apparel:crew"],
    "cloud-temple-hoodie": ["apparel:hoodie"],
    # Salt Lake map parents (scripts/map_run.py --parent sets these at publish)
    "essential-heavyweight-map-tee-salt-lake-city": ["apparel:tee", PARENT],
    "ultra-soft-map-sweatshirt-salt-lake-city": ["apparel:crew", PARENT],
    "ultra-soft-oversized-map-hoodie-salt-lake-city": ["apparel:hoodie", PARENT],
    # Be Peculiar, English and Espanol as separate cards
    "essential-heavyweight-be-peculiar-tee": ["apparel:tee", PARENT],
    "essential-heavyweight-be-peculiar-tee-espanol": ["apparel:tee", PARENT],
    "ultra-soft-be-peculiar-sweatshirt": ["apparel:crew", PARENT],
    "ultra-soft-be-peculiar-sweatshirt-espanol": ["apparel:crew", PARENT],
    "ultra-soft-oversized-be-peculiar-hoodie": ["apparel:hoodie", PARENT],
    "ultra-soft-oversized-be-peculiar-hoodie-espanol": ["apparel:hoodie", PARENT],
    # Temple Seal Bomber Jacket
    "temple-seal-bomber-jacket": ["apparel:bomber", PARENT],
}


def ensure_tags(client, apply):
    notes = []
    for handle, want in CARDS.items():
        p = client.gql("query($h: String!) { productByHandle(handle: $h) { id tags status } }",
                       {"h": handle})["productByHandle"]
        if not p:
            notes.append(f"{handle}: not on the store yet")
            continue
        missing = [t for t in want if t not in p["tags"]]
        if not missing:
            continue
        if apply:
            errs = client.gql("""mutation($id: ID!, $t: [String!]!) { tagsAdd(id: $id, tags: $t) {
                userErrors { message } } }""", {"id": p["id"], "t": missing})["tagsAdd"]["userErrors"]
            if errs:
                raise SystemExit(f"{handle}: tagsAdd refused: {errs}")
        notes.append(f"{handle} ({p['status'].lower()}): {'added' if apply else 'needs'} "
                     f"{', '.join(missing)}")
    return notes


def ensure_collections(client, apply):
    notes = []
    for c in COLLECTIONS:
        rules = [{"column": "TAG", "relation": "EQUALS", "condition": f"apparel:{c['apparel']}"},
                 {"column": "TAG", "relation": "EQUALS", "condition": PARENT}]
        have = client.gql("""query($h: String!) { collectionByHandle(handle: $h) { id
            ruleSet { appliedDisjunctively rules { column relation condition } } } }""",
            {"h": c["handle"]})["collectionByHandle"]
        if have:
            rs = have["ruleSet"] or {}
            got = sorted(r["condition"] for r in rs.get("rules", []))
            if rs.get("appliedDisjunctively") or got != sorted(r["condition"] for r in rules):
                notes.append(f"{c['handle']}: exists with different rules {got}; left as is")
            continue
        if apply:
            r = client.gql("""mutation($i: CollectionInput!) { collectionCreate(input: $i) {
                collection { id } userErrors { message } } }""",
                {"i": {"title": c["title"], "handle": c["handle"],
                       "ruleSet": {"appliedDisjunctively": False, "rules": rules}}})["collectionCreate"]
            if r["userErrors"]:
                raise SystemExit(f"{c['handle']}: {r['userErrors']}")
        notes.append(f"{c['handle']}: {'created (unpublished)' if apply else 'missing'}")
    return notes


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    client = ShopifyClient()
    for n in ensure_tags(client, a.apply) + ensure_collections(client, a.apply):
        print(f"  {n}")
    for c in COLLECTIONS:
        col = client.gql("""query($h: String!) { collectionByHandle(handle: $h) {
            products(first: 50) { nodes { handle status } } } }""", {"h": c["handle"]})["collectionByHandle"]
        if col:
            print(f"{c['handle']}: " + ", ".join(f"{p['handle']}" + ("" if p["status"] == "ACTIVE" else f" ({p['status'].lower()})")
                                                for p in col["products"]["nodes"]))


if __name__ == "__main__":
    main()
