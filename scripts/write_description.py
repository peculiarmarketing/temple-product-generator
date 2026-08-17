"""Write full product descriptions to Printify for one temple's products.

The temple-facts fragment is researched by the session (per the methodology
in reference/skills/cc1717-temple-description-builder) and saved to
Temples/{Name}/temple-facts.html. This script assembles, per garment,
the garment-correct fixed sections plus that fragment, and PUTs it onto
each product recorded in the temple's status.json.

Usage:
  python scripts/write_description.py --temple "San Antonio"
  python scripts/write_description.py --temple Logan --product-id ID --garment cc1717
"""

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from generate import TEMPLES_DIR, fixed_description
from printify_client import PrintifyClient, load_config


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--temple", required=True)
    ap.add_argument("--product-id", help="Write to one explicit product instead of status.json entries")
    ap.add_argument("--garment", help="Garment id for --product-id (selects the right fixed sections)")
    args = ap.parse_args()

    facts_path = TEMPLES_DIR / args.temple / "temple-facts.html"
    if not facts_path.exists():
        raise SystemExit(f"No {facts_path}. Research the temple first and save the facts fragment there.")
    facts = facts_path.read_text().strip()
    if "temple-facts" not in facts:
        raise SystemExit("Facts fragment must be the <section class=\"temple-facts\"> block.")

    if args.product_id:
        if not args.garment:
            raise SystemExit("--product-id needs --garment.")
        targets = [(args.garment, args.product_id)]
    else:
        status = json.loads((TEMPLES_DIR / args.temple / "status.json").read_text())
        targets = [(r["garment"], r["product_id"]) for r in status.get("results", []) if r.get("product_id")]
        if not targets:
            raise SystemExit("status.json lists no generated products for this temple.")

    c = PrintifyClient(*load_config())
    for gid, pid in targets:
        cfg = json.loads((PROJECT_ROOT / "garments" / f"{gid}.json").read_text())
        fixed = fixed_description(cfg)
        if not fixed:
            print(f"  SKIP {gid}: no fixed-section assets found")
            continue
        c.update_product(pid, {"description": fixed + "\n\n" + facts})
        after = c.get_product(pid)
        print(f"  {after['title']!r}: description written ({len(after['description'])} chars)")


if __name__ == "__main__":
    main()
