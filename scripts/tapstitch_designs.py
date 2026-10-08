"""List the Tapstitch Designs tab: every saved design, published or not.

Read-only. Works on the Mac (Chrome profile cookies) and in a cloud session
(the TAPSTITCH_COOKIES secret); tapstitch_api.session() picks whichever exists.

Usage:
  python scripts/tapstitch_designs.py              # every design, newest first
  python scripts/tapstitch_designs.py --q "Boise"  # search box
  python scripts/tapstitch_designs.py --raw        # also save the full records

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

# The record's field names are not yet confirmed from a logged-in run, so the
# summary takes the first of these that is present and --raw keeps everything.
NAME_KEYS = ("name", "title", "productName", "templateName")
ID_KEYS = ("uniqueId", "id", "productId")
WHEN_KEYS = ("updateTime", "updatedAt", "createTime", "createdAt", "gmtModified")


def first(d, keys):
    for k in keys:
        if d.get(k) not in (None, ""):
            return d[k]
    return ""


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--q", default="", help="search text, as the tab's search box")
    ap.add_argument("--raw", action="store_true", help="save the full records as JSON")
    a = ap.parse_args()

    s = T.session()
    try:
        T.store_products(s, page_size=1)
    except T.TapstitchError as e:
        sys.exit(f"Not logged in to Tapstitch ({e}). The cookies have expired or "
                 "are wrong; refresh TAPSTITCH_COOKIES or re-run tapstitch_login.py.")

    records, page = [], 1
    while True:
        pg = T.designs(s, page=page, page_size=60, q=a.q)
        records += pg["data"]
        if page >= (pg.get("totalPage") or 1):
            break
        page += 1

    print(f"{len(records)} designs in the Designs tab\n")
    for d in records:
        print(f"  {first(d, NAME_KEYS)!s:<60}  {first(d, ID_KEYS)!s:<24}  {first(d, WHEN_KEYS)}")

    if a.raw:
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        out = RAW_DIR / f"designs-{date.today().isoformat()}.json"
        out.write_text(json.dumps(records, indent=2))
        print(f"\nFull records: {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
