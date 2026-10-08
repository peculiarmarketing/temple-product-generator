"""List the Tapstitch Designs tab: every saved design, published or not.

Read-only. Works on the Mac (Chrome profile cookies) and in a cloud session
(the TAPSTITCH_COOKIES secret); tapstitch_api.session() picks whichever exists.

Usage:
  python scripts/tapstitch_designs.py                # every design, newest first
  python scripts/tapstitch_designs.py --unpublished  # only those not on the store
  python scripts/tapstitch_designs.py --q "Hoodie"   # search box
  python scripts/tapstitch_designs.py --raw          # also save the full records

Columns: when the design was saved, its store status, the blank, the blank SKU,
the design id, and the title of the store product it feeds. A record carries no
date or design title of its own (see tapstitch_api.designs()), so the time is
decoded from the id and the title comes from the linked store product.

Store status, from the linked store products' own status:
  published   at least one linked store product is published to the website
  delisted    linked, but every linked store product is delisted
  not linked  never added to a store

The search box matches the blank's name, the blank SKU or the design id, not
the store product's title, so --q "Boise" finds nothing.

TRAP: the Designs endpoint answers a logged-out caller with code 200 and an
empty list, not an error, so "0 designs" alone would be a silent failure. The
login is checked first against the store-products list, which does refuse a
logged-out caller (code 10004, "User not login").

--raw writes to artifacts/tapstitch/network/, which is gitignored: the records
can carry account detail.
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import tapstitch_api as T

RAW_DIR = ROOT / "artifacts" / "tapstitch" / "network"


def all_pages(fetch):
    records, page = [], 1
    while True:
        pg = fetch(page)
        records += pg["data"]
        if page >= (pg.get("totalPage") or 1):
            return records
        page += 1


def linked(d):
    """The store products made from design d, as (uniqueId, title) pairs."""
    return [(p["uniqueId"], p.get("title") or "")
            for st in (d.get("linkedStoresProductList") or {}).get("stores") or []
            for p in st.get("products") or []]


def store_status(d, status_by_id):
    states = {status_by_id.get(pid, "unknown") for pid, _ in linked(d)}
    if not states:
        return "not linked"
    if "published" in states:
        return "published"
    return "delisted" if states == {"delisted"} else "/".join(sorted(states))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--q", default="", help="search text, as the tab's search box")
    ap.add_argument("--unpublished", action="store_true",
                    help="only designs with no published store product")
    ap.add_argument("--raw", action="store_true", help="save the full records as JSON")
    a = ap.parse_args()

    s = T.session()
    try:
        products = all_pages(lambda p: T.store_products(s, "", p, 60))
    except T.TapstitchError as e:
        sys.exit(f"Not logged in to Tapstitch ({e}). The cookies have expired or "
                 "are wrong; refresh TAPSTITCH_COOKIES or re-run tapstitch_login.py.")
    status_by_id = {p["uniqueId"]: (p.get("status") or {}).get("value", "unknown")
                    for p in products}

    records = all_pages(lambda p: T.designs(s, page=p, page_size=60, q=a.q))
    rows = [(d, store_status(d, status_by_id)) for d in records]
    if a.unpublished:
        rows = [(d, st) for d, st in rows if st != "published"]

    label = "designs with no published store product" if a.unpublished else "designs"
    print(f"{len(rows)} {label} (of {len(records)} in the Designs tab)\n")
    for d, st in rows:
        when = T.id_time(d["uniqueId"]).strftime("%Y-%m-%d %H:%M")
        titles = sorted({t for _, t in linked(d)})
        print(f"  {when}  {st:<10}  {d.get('name', ''):<36}  {d.get('bsSn', ''):<16}  "
              f"{d['uniqueId']:<20}  {'; '.join(titles)}")

    if a.raw:
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        out = RAW_DIR / f"designs-{date.today().isoformat()}.json"
        out.write_text(json.dumps(records, indent=2))
        print(f"\nFull records: {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
