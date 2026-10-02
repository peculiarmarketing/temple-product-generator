"""Take the Printify temple catalogue off the storefront, in two steps.

Evan's decision, 14 Sep 2026: the store goes dark now, but nothing is destroyed.
Every temple listing goes to DRAFT.

The second step, deleting each old listing as its replacement published, is
RETIRED (Evan, 16 Sep 2026, asked and confirmed). Its whole purpose was to free
the old address for the replacement, and that never worked: Shopify builds a new
product's address from its title and ignores whatever just came free.
Replacements take their own address, old listings stay DRAFT indefinitely, and
scripts/easify_options.py sync repoints the dropdown links. `delete` below
remains for a deliberate one-off and is not part of any sequence.

  snapshot                      record the catalogue before anything changes. Always first.
  draft                         show what would change (the default is a dry run)
  draft --apply                 actually set every temple listing to DRAFT
  restore                       show what would come back
  restore --apply               put them back to the status the snapshot recorded
  delete --handle H --confirm-handle H    delete one old listing (one-off; NOT part of publishing)

Nothing here touches Printify. Those products stay as the way back.

Three mechanisms this file exists to respect, all learned the hard way:

1. A handle is not a stable name for a product. It can be reassigned to another
   product, and the Salt Lake crew's was: the Printify listing was deleted and
   the replacement was given that address deliberately. Every destructive
   operation is therefore pinned to the product ID recorded in the snapshot,
   never to a handle re-resolved against the live store.
2. The snapshot is the ONLY undo record for `draft`. Overwriting it after a
   draft run would record everything as already-DRAFT and silently turn `restore`
   into a no-op, so `snapshot` refuses to overwrite without --replace.
3. A Tapstitch replacement carries the SAME TITLE as the listing it replaces
   (deliberately, so it inherits the handle). Title matching alone therefore
   cannot tell them apart once both exist, and a later snapshot would classify
   the new catalogue as pull-down targets. Vendor is the discriminator: the
   retiring listings are Printify, the replacements are ODMPOD.
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import generate
import ledger
from art_images import EXCLUDE_MARKERS, match_temple, temple_tokens
from layout import PROJECT_ROOT
from shopify_client import ShopifyClient

SNAPSHOT = PROJECT_ROOT / "artifacts" / "tapstitch" / "pre-migration-catalog.json"

# Not a Printify product and not part of this migration: the $4.95 temple SVG
# download. It stays live and sellable while the garment catalogue is dark.
KEEP_LIVE_TITLES = {"Temple Art File"}


def replacement_vendors():
    """Vendors that identify a Tapstitch product, from the garment configs.

    Measured on the live store 14 Sep 2026: Printify 166 products, ODMPOD 4
    (Evan's Tapstitch tests), Peculiar People 1. A replacement must never be
    classified as a pull-down target, and its title cannot distinguish it.
    """
    out = set()
    for gid in generate.all_garment_ids("tapstitch"):
        vendor = generate.load_garment_config(gid).get("vendor")
        if vendor:
            out.add(vendor)
    return out


def replacement_handles():
    """Handles the ledger already knows belong to built replacements."""
    return {r["shopify_handle"] for r in ledger.load()["rows"] if r.get("shopify_handle")}


def retiring_patterns():
    """[(compiled title pattern, garment_id, replaced_by)] for the retiring lines.

    A title is either the bare parent title ('Essential Temple Tee') or the
    parent plus a parenthesised place ('Essential Temple Tee (Logan)'). Longest
    parent first so 'Essential Temple Tee - with personalizable date' is tested
    before 'Essential Temple Tee'.
    """
    out = []
    for gid in generate.all_garment_ids("printify"):
        cfg = generate.load_garment_config(gid)
        parent = cfg["naming"]["title_parent"]
        out.append((len(parent), re.compile(rf"^{re.escape(parent)}(?: \(.+\))?$"),
                    gid, cfg.get("replaced_by")))
    return [(p, g, r) for _, p, g, r in sorted(out, key=lambda t: -t[0])]


def cfg_replaced_by(garment_id):
    return generate.load_garment_config(garment_id).get("replaced_by")


def classify(products, skip_vendors=frozenset(), skip_handles=frozenset()):
    """Split the catalogue into what comes down, what stays, and what needs a
    human look. Anything with 'Temple' in the title that matches no garment
    pattern is reported rather than silently ignored or silently pulled."""
    patterns = retiring_patterns()
    tokens = temple_tokens()
    targets, kept, unmatched = [], [], []
    for p in products:
        title = p["title"].strip()
        if title in KEEP_LIVE_TITLES:
            kept.append((p, "not a Printify product; stays live"))
            continue
        if p.get("vendor") in skip_vendors:
            kept.append((p, f"a {p['vendor']} product; this is a replacement, not a target"))
            continue
        if p.get("handle") in skip_handles:
            kept.append((p, "the ledger says this is a built replacement"))
            continue
        if any(x in title.lower() for x in EXCLUDE_MARKERS):
            kept.append((p, "copy, template, test or one-off"))
            continue
        hit = next(((gid, rep) for pat, gid, rep in patterns if pat.match(title)), None)
        if hit:
            gid, replaced_by = hit
            targets.append({**p, "garment": gid, "replaced_by": replaced_by,
                            "temple": match_temple(title, tokens)})
        elif "Temple" in title:
            unmatched.append(p)
        else:
            kept.append((p, "not a temple product"))
    return targets, kept, unmatched


def resolve_collisions(targets):
    """({(temple, replacement garment): the target whose handle is inherited},
    [(temple, retiring garment, listings oldest first)]).

    Two listings can map to the same temple and garment: on 14 Sep 2026 two live
    products both titled "Essential Temple Tee" sat at salt-lake-city-temple-tee
    (created 8 Aug, carries the art card) and essential-temple-tee (created
    27 Aug, does not). Only one handle can be inherited, so the OLDEST wins: the
    original is the one the Easify dropdown URLs point at. Collisions are
    returned rather than resolved silently, because a stray duplicate on the
    live store is a real problem someone has to decide about.
    """
    # Detection groups by GARMENT, inheritance groups by REPLACEMENT. They are
    # not the same set: the paused dated tee has no replacement, so grouping only
    # by replacement made its duplicate invisible. Nothing inherits that handle,
    # but a stray duplicate on the live store is still something to report.
    by_garment, by_pair = {}, {}
    for t in targets:
        if not t["temple"]:
            continue
        by_garment.setdefault((t["temple"], t["garment"]), []).append(t)
        if t["replaced_by"]:
            by_pair.setdefault((t["temple"], t["replaced_by"]), []).append(t)

    collisions = []
    for (temple, gid), hits in sorted(by_garment.items()):
        if len(hits) > 1:
            collisions.append((temple, gid,
                               sorted(hits, key=lambda h: h.get("createdAt") or "")))
    keep = {pair: sorted(hits, key=lambda h: h.get("createdAt") or "")[0]
            for pair, hits in sorted(by_pair.items())}
    return keep, collisions


def cmd_snapshot(client, replace=False):
    if SNAPSHOT.exists() and not replace:
        raise SystemExit(
            f"{SNAPSHOT.name} already exists and is the ONLY undo record for `draft`.\n"
            f"Overwriting it after a draft run would record every listing as already "
            f"DRAFT, and `restore` would then silently do nothing.\n"
            f"Pass --replace only if you are certain no draft run needs undoing.")

    products = client.all_products_summary()
    targets, kept, unmatched = classify(products, skip_vendors=replacement_vendors(),
                                        skip_handles=replacement_handles())
    keep, collisions = resolve_collisions(targets)

    SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT.write_text(json.dumps({
        "taken_at": datetime.now().isoformat(timespec="seconds"),
        "catalogue_size": len(products),
        "targets": targets,
        "kept": [{**p, "reason": r} for p, r in kept],
        "unmatched_temple_titles": unmatched,
    }, indent=2) + "\n")

    # Seed the ledger with the handle each replacement must inherit. This has to
    # happen while the catalogue is intact; it is the whole reason snapshot runs first.
    data = ledger.load()
    for (temple, gid), t in keep.items():
        ledger.set_state(data, temple, gid,
                         next((r["state"] for r in data["rows"]
                               if r["temple"] == temple and r["garment"] == gid),
                              "art-missing"),
                         old_shopify_handle=t["handle"], old_shopify_id=t["id"],
                         old_title=t["title"])
    ledger.save(data)

    print(f"catalogue: {len(products)} products")
    print(f"  {len(targets)} temple listings to pull down")
    print(f"  {len(kept)} left alone")
    print(f"  {len(unmatched)} titles containing 'Temple' that matched no garment (REVIEW THESE)")
    for p in unmatched:
        print(f"      {p['title']!r}  [{p['status']}]  {p['handle']}")
    print(f"  {len(keep)} ledger rows given the web address their replacement inherits")
    if collisions:
        print(f"\n{len(collisions)} DUPLICATE LISTINGS on the live store. Two products map "
              f"to the same temple and garment, so only one address can be inherited.")
        print("Where a replacement inherits the address, the OLDEST is kept because that "
              "is the one the Easify dropdown links at. The strays need a decision:")
        for temple, gid, hits in collisions:
            inherits = any(k == (temple, cfg_replaced_by(gid)) for k in keep)
            note = "" if inherits else "   (paused line: nothing inherits this address)"
            print(f"    {temple} / {gid}{note}")
            for n, h in enumerate(hits):
                mark = ("KEPT   " if inherits else "OLDEST ") if n == 0 else "STRAY  "
                print(f"      {mark} {h['handle']:<34} created {(h.get('createdAt') or '?')[:10]}"
                      f"  {h['title']!r}")
    print(f"\nwritten: {SNAPSHOT.relative_to(PROJECT_ROOT)}")
    no_temple = [t for t in targets if not t["temple"]]
    if no_temple:
        print(f"\n{len(no_temple)} listings could not be read back to a temple folder "
              f"(their old address will not be inherited automatically):")
        for t in no_temple:
            print(f"      {t['title']!r}")


def load_snapshot():
    if not SNAPSHOT.exists():
        raise SystemExit("Run `snapshot` first. Nothing here acts on the live store "
                         "without the catalogue recorded as it was beforehand.")
    return json.loads(SNAPSHOT.read_text())


def cmd_draft(client, apply):
    snap = load_snapshot()
    targets = snap["targets"]
    live = [t for t in targets if t["status"] != "DRAFT"]

    print(f"KEEPING LIVE ({len(snap['kept'])} products), including:")
    for k in snap["kept"]:
        if "stays live" in k["reason"] or "replacement" in k["reason"]:
            print(f"    {k['title']!r}  ({k['reason']})")
    print(f"\nPULLING DOWN: {len(live)} listings currently live "
          f"({len(targets) - len(live)} already draft)")
    by_garment = {}
    for t in live:
        by_garment.setdefault(t["garment"], []).append(t)
    for gid, rows in sorted(by_garment.items()):
        print(f"    {gid:<14} {len(rows)} listings")
    if snap["unmatched_temple_titles"]:
        print(f"\nNOT TOUCHED, please review ({len(snap['unmatched_temple_titles'])}):")
        for p in snap["unmatched_temple_titles"]:
            print(f"    {p['title']!r}")

    if not apply:
        print(f"\nDRY RUN. Nothing changed. Re-run with --apply to take these "
              f"{len(live)} listings off the storefront.")
        return
    done, failed = 0, []
    for t in live:
        try:
            client.update_product(t["id"], status="DRAFT")
            done += 1
            print(f"  drafted: {t['title']}")
        except Exception as e:
            failed.append((t["title"], str(e)[:120]))
    print(f"\n{done} drafted, {len(failed)} failed")
    for title, err in failed:
        print(f"  FAILED {title!r}: {err}")


def cmd_restore(client, apply):
    """The undo for `draft`. Pinned to recorded product IDs, and it reports what
    it could not bring back rather than aborting on the first failure: by the
    time this runs, the snapshot may name products that were deleted at swap."""
    snap = load_snapshot()
    wanted = [t for t in snap["targets"] if t["status"] != "DRAFT"]
    print(f"{len(wanted)} listings would go back to the status the snapshot recorded "
          f"(taken {snap['taken_at']}).")
    if not apply:
        print("DRY RUN. Nothing changed. Re-run with --apply.")
        return
    done, failed = 0, []
    for t in wanted:
        try:
            client.update_product(t["id"], status=t["status"])
            done += 1
        except Exception as e:
            failed.append((t["title"], t["handle"], str(e)[:120]))
    print(f"{done} restored, {len(failed)} failed")
    for title, handle, err in failed:
        print(f"  FAILED {title!r} ({handle}): {err}")
    if failed:
        print("\nA failure here usually means that product was deleted at swap time, "
              "which is expected once the migration has started. The listings above "
              "are still down; check them by hand.")


def cmd_delete(client, handle, confirm_handle):
    """Delete one old listing. A deliberate one-off, not part of publishing.

    Pinned to the product ID the snapshot recorded, NOT to whatever the handle
    resolves to now, because a handle can be reassigned to another product and an
    id cannot. That is not hypothetical: the Salt Lake crew's replacement was
    given its predecessor's address, so a live lookup of that handle now returns
    the new product, and a re-run or a retry against it would delete the
    replacement rather than the listing it replaced.
    """
    if confirm_handle != handle:
        raise SystemExit("delete needs --confirm-handle to match --handle exactly. "
                         "This is the one operation with no undo.")
    snap = load_snapshot()
    match = next((t for t in snap["targets"] + snap.get("kept", [])
                  if t.get("handle") == handle), None)
    if not match:
        raise SystemExit(f"{handle!r} is not in the snapshot. Refusing to delete a product "
                         f"this migration never recorded.")
    if match.get("title") in KEEP_LIVE_TITLES:
        raise SystemExit(f"{handle!r} is {match['title']!r}, which stays live by design "
                         f"(KEEP_LIVE_TITLES). Nothing done.")

    row = next((r for r in ledger.load()["rows"]
                if r.get("old_shopify_handle") == handle), None)
    if row and row["state"] in ("description-written", "card-pushed", "live"):
        raise SystemExit(
            f"The ledger says {row['temple']}/{row['garment']} is already at "
            f"{row['state']!r}, so the replacement is live and now owns {handle!r}. "
            f"Deleting it would destroy the replacement. Nothing done.")

    live = client.find_product_by_handle(handle)
    if not live:
        print(f"{handle!r} is already gone.")
        return
    if live["id"] != match["id"]:
        raise SystemExit(
            f"{handle!r} now resolves to a DIFFERENT product than the snapshot recorded.\n"
            f"  snapshot: {match['id']}  {match['title']!r}\n"
            f"  live now: {live['id']}  {live['title']!r}\n"
            f"The replacement has almost certainly already taken this address. "
            f"Nothing done.")

    reason = ("so its replacement can take the address"
              if match.get("replaced_by") else "(no replacement; deleting outright)")
    print(f"deleting {match['title']!r} ({handle}, {match['id']}) {reason}")
    client.delete_product(match["id"])
    print("deleted.")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["snapshot", "draft", "restore", "delete"])
    ap.add_argument("--apply", action="store_true",
                    help="with draft/restore: actually change the live store. "
                         "Without it they are dry runs.")
    ap.add_argument("--replace", action="store_true",
                    help="with snapshot: overwrite an existing snapshot. See the warning.")
    ap.add_argument("--handle", help="with delete: the handle of the listing to remove")
    ap.add_argument("--confirm-handle", dest="confirm_handle",
                    help="with delete: the same handle again. Deletion has no undo.")
    a = ap.parse_args()

    client = ShopifyClient()
    if a.command == "snapshot":
        cmd_snapshot(client, a.replace)
    elif a.command == "draft":
        cmd_draft(client, a.apply)
    elif a.command == "restore":
        cmd_restore(client, a.apply)
    elif a.command == "delete":
        if not a.handle:
            raise SystemExit("delete needs --handle and --confirm-handle")
        cmd_delete(client, a.handle, a.confirm_handle)


if __name__ == "__main__":
    main()
