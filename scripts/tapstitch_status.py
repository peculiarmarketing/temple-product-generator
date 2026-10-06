"""Where the Tapstitch migration has got to.

The migration recreates roughly 120 products through a web editor across many
sessions. This is how a run finds its place again.

Usage:
  python scripts/tapstitch_status.py              # the summary
  python scripts/tapstitch_status.py --full       # every row
  python scripts/tapstitch_status.py --state file-built
  python scripts/tapstitch_status.py --problems   # only rows with findings
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ledger


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--full", action="store_true", help="list every row")
    ap.add_argument("--state", help="list only rows in this state")
    ap.add_argument("--problems", action="store_true", help="list only rows with findings")
    ap.add_argument("--temple", help="list only this temple's rows")
    a = ap.parse_args()

    data = ledger.load()
    rows = data["rows"]
    if not rows:
        print("The ledger is empty. Run scripts/tapstitch_build.py to populate it.")
        return

    counts = ledger.counts(data)
    print(f"{len(rows)} temple/garment rows, updated {data.get('updated_at', 'never')}\n")
    width = max(len(s) for s in ledger.STATES)
    for state in ledger.STATES:
        if counts.get(state):
            bar = "#" * round(40 * counts[state] / len(rows))
            print(f"  {state:<{width}}  {counts[state]:>4}  {bar}")

    seeded = sum(1 for r in rows if r.get("old_shopify_handle"))
    gaps = [r for r in rows
            if not r.get("old_shopify_handle") and r["state"] != "art-missing"]
    print(f"\n  {seeded} rows know the web address their replacement must inherit.")
    new_products = len(rows) - seeded - len(gaps)
    if new_products:
        print(f"  {new_products} have no old listing to inherit from. Those are new "
              f"temples, not a problem.")
    if gaps:
        print(f"  {len(gaps)} HAVE art but no old address. Those replacements would land "
              f"on a new web address and break their Easify dropdown link:")
        for r in gaps[:10]:
            print(f"      {r['temple']} / {r['garment']}")

    shown = rows
    if a.state:
        shown = [r for r in shown if r["state"] == a.state]
    if a.temple:
        shown = [r for r in shown if r["temple"] == a.temple]
    if a.problems:
        shown = [r for r in shown if r["problems"]]
    if not (a.full or a.state or a.temple or a.problems):
        return

    print(f"\n{'Temple':<22} {'Garment':<9} {'State':<20} Old address")
    for r in shown:
        print(f"{r['temple']:<22} {r['garment']:<9} {r['state']:<20} "
              f"{r.get('old_shopify_handle') or '-'}")
        for p in r["problems"]:
            print(f"{'':<32}  - {p}")
    print(f"\n{len(shown)} rows shown.")


if __name__ == "__main__":
    main()
