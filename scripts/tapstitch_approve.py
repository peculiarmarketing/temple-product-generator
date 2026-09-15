"""Record Evan's approval of built print files, per temple.

The ledger has always had a `file-approved` state and tapstitch_publish.py has
always selected on it, but until now nothing wrote it, so the check reported
zero approved rows however many files existed. This is the door into that state.

Approval is PER TEMPLE, not per row. A temple's tee, crew and hoodie carry the
same drawing; only the frame proportions differ, so the proof sheet shows one
image per temple and approving it approves its garments together.

Only `file-built` rows can be approved. A row still at art-missing or error has
no file to have looked at, and a row already past file-approved belongs to the
publish run, which this must never walk backwards.

Usage:
  python scripts/tapstitch_approve.py --all
  python scripts/tapstitch_approve.py --all --except "Nauvoo,Manti"
  python scripts/tapstitch_approve.py --temple "Salt Lake"
  python scripts/tapstitch_approve.py --revoke --temple "Nauvoo"
  python scripts/tapstitch_approve.py --list
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ledger


def norm(name):
    """Fold the ref-finder star so --except "Lehi" matches the folder "Lehi*"."""
    return name.rstrip("*").strip().casefold()


def resolve_names(data, wanted, label):
    """Map user-typed temple names onto ledger temple names, or stop.

    A typo here would silently approve nothing and look like success, so an
    unmatched name is fatal and prints the near misses.
    """
    known = {norm(r["temple"]): r["temple"] for r in data["rows"]}
    out, missing = set(), []
    for w in wanted:
        hit = known.get(norm(w))
        if hit is None:
            missing.append(w)
        else:
            out.add(hit)
    if missing:
        names = sorted(set(known.values()))
        raise SystemExit(
            f"{label}: no temple named {', '.join(repr(m) for m in missing)} in the ledger.\n"
            f"Known temples: {', '.join(names)}")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--all", action="store_true", help="every temple with built files")
    ap.add_argument("--temple", action="append", default=[],
                    help="one temple; repeatable")
    ap.add_argument("--except", dest="excluded", default="",
                    help="comma-separated temples to hold back from --all")
    ap.add_argument("--revoke", action="store_true",
                    help="move file-approved rows back to file-built")
    ap.add_argument("--list", action="store_true", help="show the current split and exit")
    ap.add_argument("--dry-run", action="store_true", help="say what would change, write nothing")
    a = ap.parse_args()

    data = ledger.load()
    if not data.get("rows"):
        raise SystemExit("The ledger is empty. Run scripts/tapstitch_build.py first.")

    by_temple = {}
    for r in data["rows"]:
        by_temple.setdefault(r["temple"], []).append(r)

    if a.list:
        for temple in sorted(by_temple):
            states = sorted({r["state"] for r in by_temple[temple]})
            print(f"  {temple:22} {', '.join(states)}")
        counts = ledger.counts(data)
        print("\n" + "  ".join(f"{s}: {c}" for s, c in counts.items() if c))
        return

    if not (a.all or a.temple):
        raise SystemExit("Nothing to do: pass --all, or --temple NAME, or --list.")
    if a.excluded and not a.all:
        raise SystemExit("--except only makes sense with --all.")

    source, target = ("file-approved", "file-built") if a.revoke else ("file-built", "file-approved")
    verb = ("revoke" if a.dry_run else "revoked") if a.revoke else \
           ("approve" if a.dry_run else "approved")

    if a.all:
        wanted = set(by_temple)
        held = resolve_names(data, [x for x in a.excluded.split(",") if x.strip()], "--except")
        wanted -= held
    else:
        wanted = resolve_names(data, a.temple, "--temple")
        held = set()

    changed, skipped = [], {}
    for temple in sorted(wanted):
        for r in by_temple[temple]:
            if r["state"] == source:
                changed.append((temple, r["garment"]))
                if not a.dry_run:
                    ledger.set_state(data, temple, r["garment"], target)
            else:
                skipped.setdefault(r["state"], []).append(f"{temple}/{r['garment']}")

    if changed and not a.dry_run:
        ledger.save(data)

    temples_changed = sorted({t for t, _ in changed})
    print(f"{'would ' if a.dry_run else ''}{verb} {len(changed)} rows "
          f"across {len(temples_changed)} temples")
    if held:
        print(f"held back at Evan's instruction: {', '.join(sorted(held))}")
    for state, rows in sorted(skipped.items()):
        note = {"art-missing": "no traced art, nothing to approve",
                "error": "build problems, fix before approving",
                "file-approved": "already approved",
                "file-built": "not approved yet"}.get(state, "")
        print(f"  left at {state}: {len(rows)}" + (f" ({note})" if note else ""))
        if state in ("art-missing", "error"):
            for row in rows:
                print(f"      {row}")

    counts = ledger.counts(data)
    print("\nledger now: " + "  ".join(f"{s} {c}" for s, c in counts.items() if c))


if __name__ == "__main__":
    main()
