"""Drive the proven Tapstitch API route over the migration ledger.

`tapstitch_api.py` proved every call against the live account on 15-16 Sep 2026,
one product at a time, by hand. This is the loop that runs that same sequence
over the ledger's rows. It adds no new API calls and discovers nothing: if a
step fails here it fails there too.

The sequence per row, which is the 16 Sep hoodie publish written down:

    create_template -> upload the back and front print files -> read the
    template's own print areas -> save_design -> store_product_prefill ->
    store_product_payload -> create_store_product   (nothing public yet)
    -> distribute                                   (LIVE, no undo)
    -> wait for Shopify -> finish_on_shopify (product type, art card, colour
    fixups) -> tapstitch_variant_images.rebind -> ledger

TWO SEPARATE GATES, because the two halves fail differently. `--apply` permits
the Tapstitch-side writes, all of which stay inside Tapstitch. `--publish`
additionally permits distribute(), which puts the product on the storefront as
ACTIVE and purchasable with no undo, and it also requires a bound (`--limit` or
`--temple`) so a forgotten flag cannot launch the whole catalogue. Running with
`--apply` alone builds products and stops short of the storefront, which is the
"build it, check it, then distribute" order tapstitch_api's own docstring
describes. Precedent for the shape: scripts/store_pulldown.py, the other script
whose default path touches the live store, which also plans by default and
gates with --apply.

THE LEDGER IS NOT THE AUTHORITY ON WHAT IS LIVE. Its Salt Lake tee row said
file-approved while that product was live on the storefront, because the tee was
published on 15 Sep during the first proving session, before any of these
set_state calls existed. So every row is checked against the store's real titles
before it is built, the way generate.py has always checked before creating a
Printify product. Trusting the ledger alone would have published a duplicate.

RESUMABLE AT EVERY SEAM, because 132 rows is many sessions' work and the one
irreversible call sits in the middle of it. Each id is written to the ledger the
moment Tapstitch returns it, and each id is READ back on the next run:

    template id only   -> reuse it, re-save the design, create the product.
                          save_design is a PUT, so repeating it is safe. Without
                          this the retry builds a second design and overwrites
                          the only record of the first.
    store product id   -> resume at distribute.
    distribute_started -> do NOT distribute again. Poll for the product instead,
                          because the call may have been accepted and only the
                          confirmation lost. A second distribute is the one way
                          this runner could put a duplicate on the storefront.
    shopify handle     -> already live. Skip distribute entirely and resume at
                          the Shopify half, which is where a row that crashed
                          after publishing gets finished rather than stranded.

That last case is the one place `--apply` alone writes to a product that is
already on the storefront: it sets the product type, colour order and variant
images of a live listing. Those are the same repairs
`tapstitch_publish.py finish` runs ungated, and none of them publish anything, so
the distribute gate is intact; it is named here so it is not a surprise.

Usage:
  python scripts/tapstitch_run.py                                 # plan only
  python scripts/tapstitch_run.py --apply --limit 1               # build 1, no storefront
  python scripts/tapstitch_run.py --apply --publish --limit 1     # build and publish 1
  python scripts/tapstitch_run.py --apply --publish --temple Logan
"""

import argparse
import re
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from PIL import Image

import flatten
import generate
import ledger
import tapstitch_api as T
import tapstitch_variant_images
from shopify_client import ShopifyClient
from tapstitch_approve import resolve_names
from tapstitch_publish import finish_on_shopify, load_config

CONFIG = load_config()
STORE_ID = CONFIG["api"]["shopify_store_id"]
BLANKS = CONFIG["api"]["blanks"]

READY = "file-approved"        # print file built and approved, no product yet
BUILT = "product-created"      # a Tapstitch store product exists for this row
# How long to wait for a distributed product to appear on Shopify. Read from the
# config's timing block rather than hardcoded: that block was written for this
# runner and had no reader until now. Measured 15 Sep 2026, a distribute took
# over a minute to show up, which is why confirmation is against Shopify itself
# rather than the distribute call's own response.
SHOPIFY_WAIT_S = CONFIG["timing"]["publish_timeout_ms"] / 1000
SHOPIFY_POLL_S = 15


def ink_color(garment_cfg):
    """The single ink colour this garment's design prints in.

    A Tapstitch template binds ONE design to a LIST of colour codes, so a
    garment whose colourways disagree about ink cannot be one product. Every
    current colourway is white on a dark ground; a light colourway added later
    needs its own listing, and this raises rather than silently printing white
    art onto it.
    """
    inks = {c["ink"] for c in garment_cfg["colorways"]}
    if len(inks) != 1:
        raise T.TapstitchError(
            f"{garment_cfg['garment_id']}: colourways disagree about ink "
            f"({sorted(inks)}). One template prints one design, so this needs "
            f"one product per ink, not one product.")
    return inks.pop()


def lead_color_id(garment_cfg):
    """The Tapstitch numeric colour id the gallery should lead with.

    storefront_first_color is the post-rename SHOPIFY display name, which
    matches nothing on Tapstitch's side. Resolve it through the colorways table
    to that entry's `code`, which is what mockups_back_first() sorts on. Passing
    any other field fails quiet: the sort simply leaves Tapstitch's own order and
    every gallery opens on the wrong colour with no error anywhere.
    """
    want = garment_cfg.get("storefront_first_color")
    for c in garment_cfg["colorways"]:
        if c["shopify"] == want:
            return c["code"]
    raise T.TapstitchError(
        f"{garment_cfg['garment_id']}: storefront_first_color {want!r} is not a "
        f"`shopify` name in colorways, so the gallery's lead colour cannot be "
        f"resolved. Fix the garment config rather than passing the name through.")


def print_files(temple, garment_id, color):
    """(back, front) print file paths, checked to exist.

    The build pass wrote these and the ledger row recorded their names, but a
    name is not a path and a file can be deleted after a row is approved.
    """
    back = flatten.back_file_path(temple, garment_id, color)
    front = flatten.front_file_path(garment_id, color)
    missing = [str(p) for p in (back, front) if not p.exists()]
    if missing:
        raise T.TapstitchError(f"print file(s) missing: {', '.join(missing)}. "
                               f"Re-run scripts/tapstitch_build.py.")
    return back, front


def blockers(row, garment_cfg, live_titles):
    """Every reason this row must not be built, checked before anything is written.

    Description completeness is a gate rather than a warning. finish_on_shopify
    skips the description when a temple has no facts, which is right for a
    product that already exists, but a product created here carries its
    description from birth: creating one for a factless temple would put a
    listing on the storefront missing the section people actually read.

    The title check is skipped once a row has a store product of its own. After
    that point its title existing on the store is the expected outcome, not a
    collision, and treating it as one strands every row that crashed after
    distribute: the runner would refuse to finish the very product it published.
    """
    temple, garment_id = row["temple"], row["garment"]
    out = []
    _, reason = generate.description_for(temple, garment_cfg)
    if reason:
        out.append(reason)
    if not row.get("tapstitch_store_product_id"):
        try:
            if generate.title_for(temple, garment_id, garment_cfg) in live_titles:
                out.append(f"a product titled "
                           f"{generate.title_for(temple, garment_id, garment_cfg)!r} "
                           f"already exists on the store")
        except SystemExit as e:
            out.append(f"manifest: {str(e)[:120]}")
    if not row.get("shopify_handle"):
        # A row that is already live has nothing left to upload, so a print file
        # deleted since it published is no reason to refuse to FINISH it. Only a
        # row that still has to build one needs the file on disk.
        try:
            print_files(temple, garment_id, ink_color(garment_cfg))
        except T.TapstitchError as e:
            out.append(str(e))
    return out


def save_design(s, template_id, garment_id, garment_cfg, pngs, note):
    """Place both print files on their own sides and save. Nothing public."""
    back_png, front_png = pngs
    areas = T.print_areas(T.get_template(s, template_id))
    pieces = {}
    for png, area_cfg in ((back_png, garment_cfg["print_area"]),
                          (front_png, garment_cfg["front_print_area"])):
        side = area_cfg["position"]
        if side not in areas:
            raise T.TapstitchError(
                f"Tapstitch states no print area named {side!r} for this blank; "
                f"it has {sorted(areas)}. The garment config and the blank "
                f"disagree about which sides print.")
        src = T.upload_print_file(s, png)
        with Image.open(png) as im:
            src_size = im.size
        geometry = T.placement(areas[side], src_size)
        pieces[side] = T.design_object(side, src, geometry, src_size)
    T.save_design(s, template_id, BLANKS[garment_id], pieces)
    note(f"design saved ({', '.join(sorted(pieces))})")


def create_product(s, temple, garment_id, garment_cfg, template_id, note):
    """Build the Shopify-bound store product. Still nothing public."""
    title = generate.title_for(temple, garment_id, garment_cfg)
    html, reason = generate.description_for(temple, garment_cfg)
    if not html:
        raise T.TapstitchError(f"refusing to create a product with no description: {reason}")
    prefill = T.store_product_prefill(s, STORE_ID, template_id)
    payload = T.store_product_payload(
        prefill, title, int(round(garment_cfg["price_usd"] * 100)), html,
        lead_color_id(garment_cfg))
    store_product_id = T.create_store_product(s, STORE_ID, payload)
    note(f"store product {store_product_id} ({title!r})")
    return store_product_id


def wait_for_shopify(client, title, timeout_s=None):
    """Poll Shopify for the distributed product. Returns its handle.

    distribute() returning is not the product existing: measured 15 Sep 2026, it
    took over a minute to appear. Everything after this needs the real handle,
    which Shopify derives from the title, so it is read back rather than guessed.
    """
    deadline = time.time() + (SHOPIFY_WAIT_S if timeout_s is None else timeout_s)
    while True:
        product = client.find_product_by_title(title)
        if product:
            return product["handle"]
        if time.time() >= deadline:
            raise T.TapstitchError(
                f"{title!r} did not appear on Shopify in time. The distribute "
                f"call was accepted, so the row is recorded as distributed and "
                f"the next run will poll again rather than distributing twice. "
                f"Check the store before clearing distribute_started_at by hand.")
        time.sleep(SHOPIFY_POLL_S)


def finish_half(s, client, data, row, handle, template_id, note):
    """The Shopify half, after the product is live. Idempotent and re-runnable.

    Separated so a row that crashed anywhere after distribute re-enters HERE on
    the next run instead of going near distribute again.
    """
    temple, garment_id = row["temple"], row["garment"]
    # write_description False: the product was created carrying the composed
    # description, so writing it again is a second identical write to the same
    # field through a second composition that could drift from the first.
    for action in finish_on_shopify(client, temple, garment_id, handle,
                                    old_handle=row.get("old_shopify_handle"),
                                    write_description=False):
        note(action)
    ledger.set_state(data, temple, garment_id, "card-pushed", problems=[])
    ledger.save(data)

    rebound = tapstitch_variant_images.rebind(client, s, handle, template_id)
    # rebind reports its failures by RETURNING them, so a row cannot be called
    # live on the strength of a string that happens to be truthy. None means
    # nothing needed changing; only a note naming a rebind is a success.
    if rebound is not None and "rebound" not in rebound:
        raise T.TapstitchError(f"variant image repair did not run: {rebound}")
    note(rebound or "variant images already on the back")
    ledger.set_state(data, temple, garment_id, "live", problems=[])
    ledger.save(data)
    return "live"


def run_row(s, client, data, row, publish, note):
    """One temple/garment through the whole sequence. Returns the final state."""
    temple, garment_id = row["temple"], row["garment"]
    garment_cfg = generate.load_garment_config(garment_id)
    template_id = row.get("tapstitch_template_id")
    store_product_id = row.get("tapstitch_store_product_id")
    handle = row.get("shopify_handle")

    if handle:
        note(f"already live at {handle}: resuming the Shopify half")
        return finish_half(s, client, data, row, handle, template_id, note)

    if not store_product_id:
        if template_id:
            # Reuse rather than rebuild. save_design is a PUT on this id, so
            # repeating it is safe, and creating a second template would orphan
            # this one along with the only record that it exists.
            note(f"reusing template {template_id} from an earlier run")
            pngs = print_files(temple, garment_id, ink_color(garment_cfg))
        else:
            pngs = print_files(temple, garment_id, ink_color(garment_cfg))
            template_id = T.create_template(s, BLANKS[garment_id])
            note(f"template {template_id}")
            ledger.set_state(data, temple, garment_id, row["state"],
                             tapstitch_template_id=template_id)
            ledger.save(data)
        save_design(s, template_id, garment_id, garment_cfg, pngs, note)
        store_product_id = create_product(s, temple, garment_id, garment_cfg,
                                          template_id, note)
        ledger.set_state(data, temple, garment_id, BUILT, problems=[],
                         tapstitch_store_product_id=store_product_id)
        ledger.save(data)

    if not publish:
        note("stopped before distribute: --publish not given")
        return BUILT

    title = generate.title_for(temple, garment_id, garment_cfg)
    already = client.find_product_by_title(title)
    if already:
        # Last look before the one call with no undo. A product under this title
        # is already on the store, so distributing would at best do nothing and
        # at worst list it twice. This covers the case the ledger cannot see: a
        # row built with --apply and then published by hand from the Tapstitch
        # UI carries a store product id and no marker, and without this check
        # would be distributed a second time.
        note(f"already on the store at {already['handle']}: skipping distribute")
    elif row.get("distribute_started_at"):
        # The call was made on an earlier run and its confirmation was lost.
        # Polling is the safe half of the retry; distributing again is not.
        note(f"distribute already attempted {row['distribute_started_at']}: "
             f"polling instead of repeating it")
    else:
        # Recorded BEFORE the call, not after: a distribute that Tapstitch
        # accepted and then failed to answer is indistinguishable from one that
        # never landed, and of the two possible mistakes, polling for a product
        # that was never published is the recoverable one.
        ledger.set_state(data, temple, garment_id, BUILT,
                         distribute_started_at=datetime.now().isoformat(timespec="seconds"))
        ledger.save(data)
        T.distribute(s, [store_product_id])

    handle = wait_for_shopify(client, title)
    note(f"live at {handle}")
    ledger.set_state(data, temple, garment_id, BUILT, shopify_handle=handle)
    ledger.save(data)
    return finish_half(s, client, data, row, handle, template_id, note)


def selected(data, temples, garment_ids):
    """Rows this run could touch, in ledger order.

    product-created is a half-finished publish waiting to be resumed.

    card-pushed is included too, which looks like revisiting finished work and is
    not: it means the Shopify fixups ran but the variant-image repair did not
    confirm. Such a row is a LIVE product still showing the near-blank front,
    and excluding it left the runner unable to finish the one thing the repo
    calls "the one that would have failed quietly". Resuming is safe because the
    row carries a handle, so it re-enters at finish_half(), which is idempotent
    and never goes near distribute.

    `live` is never revisited: re-running must not republish a live product.
    """
    out = []
    for r in data["rows"]:
        if temples and r["temple"] not in temples:
            continue
        if garment_ids and r["garment"] not in garment_ids:
            continue
        if r["state"] in (READY, BUILT, "card-pushed"):
            out.append(r)
    return out


def safe_error(err):
    """An error string safe to write to the git-tracked ledger.

    requests puts the whole request URL in its transport errors, and the print
    file upload's URL is a signed OSS one: the signature rides in the query
    string and the account's login id is a path segment. ledger.save() writes
    problems into ledger.json and LEDGER.md, both tracked, so the URL is cut back
    to its host here rather than committed. The failure is still identifiable
    from the exception type and the host.
    """
    text = f"{type(err).__name__}: {err}"
    text = re.split(r"\s+with url:", text)[0]        # the path requests appends
    text = re.sub(r"(https?://[^/\s]+)\S*", r"\1/...", text)
    return text.split("?", 1)[0][:200]


def record_failure(data, row, err):
    """Keep the ids, keep the state, record why. The next run resumes from here."""
    ledger.set_state(data, row["temple"], row["garment"],
                     row.get("state", READY), problems=[safe_error(err)])
    ledger.save(data)


def resume_note(row):
    """What a half-finished row would do next, named in the plan output.

    A row that says "ready" while carrying a handle would otherwise look like a
    fresh build about to duplicate a live product, when it is the opposite: the
    finish steps for a product that is already on the storefront.
    """
    if row.get("shopify_handle"):
        return "  (resume: finish the Shopify half)"
    if row.get("distribute_started_at"):
        return "  (resume: poll Shopify, already distributed)"
    if row.get("tapstitch_store_product_id"):
        return "  (resume: distribute)"
    if row.get("tapstitch_template_id"):
        return "  (resume: reuse the existing template)"
    return ""


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true",
                    help="permit the Tapstitch-side writes (nothing public)")
    ap.add_argument("--publish", action="store_true",
                    help="also distribute to Shopify. LIVE and irreversible.")
    ap.add_argument("--temple", action="append",
                    help="restrict to this temple; repeatable")
    ap.add_argument("--garments", help="comma-separated garment ids")
    ap.add_argument("--limit", type=int,
                    help="build at most this many ready rows")
    a = ap.parse_args()

    if a.publish and not a.apply:
        raise SystemExit("--publish needs --apply: a row cannot be distributed "
                         "without being built first.")
    if a.limit is not None and a.limit < 1:
        raise SystemExit(f"--limit {a.limit} would not build anything. Omit it "
                         f"to run every ready row, or pass 1 or more.")
    if a.publish and a.limit is None and not a.temple:
        # The bound is the whole safety story once --publish is on: there are
        # about a hundred ready rows and distribute() has no undo.
        raise SystemExit("--publish needs a bound: pass --limit N, or --temple "
                         "to publish one temple's rows. Both flags together is "
                         "the safest first run.")

    known = generate.all_garment_ids(None)
    garment_ids = (a.garments.split(",") if a.garments
                   else generate.all_garment_ids("tapstitch"))
    unknown = [g for g in garment_ids if g not in known]
    if unknown:
        raise SystemExit(f"Unknown garment id(s): {', '.join(unknown)}. "
                         f"Known: {', '.join(known)}")

    data = ledger.load()
    # resolve_names is fatal on a typo and folds the ref-finder star, so
    # --temple "Lehi" finds the folder "Lehi*" instead of silently selecting
    # nothing and reporting success.
    temples = resolve_names(data, a.temple, "--temple") if a.temple else set()
    rows = selected(data, temples, set(garment_ids))
    if not rows:
        print(f"Nothing selected. Rows must be {READY}, or {BUILT} / card-pushed "
              f"to resume; everything else is either unbuilt or already live.")
        return 0

    client = ShopifyClient()
    live_titles = {p["title"].strip() for p in client.all_products_summary()}

    ready, blocked = [], []
    for r in rows:
        cfg = generate.load_garment_config(r["garment"])
        reasons = blockers(r, cfg, live_titles)
        (blocked if reasons else ready).append((r, reasons))

    plan = ready[:a.limit] if a.limit is not None else ready
    print(f"{len(rows)} selected: {len(ready)} ready, {len(blocked)} blocked. "
          f"This run would build {len(plan)}.\n")
    for r, reasons in blocked:
        print(f"  BLOCKED {r['temple']:<20} {r['garment']:<8}")
        for reason in reasons:
            print(f"          - {reason}")
    if blocked:
        print()
    for r, _ in plan:
        print(f"  ready   {r['temple']:<20} {r['garment']:<8}{resume_note(r)}")

    if not a.apply:
        print("\nPlan only. Re-run with --apply to build these in Tapstitch, "
              "and --publish as well to put them on the storefront.")
        return 0
    if not plan:
        print("\nNothing to do: every selected row is blocked.")
        return 1

    if a.publish:
        print(f"\nAbout to DISTRIBUTE {len(plan)} product(s) to the live "
              f"storefront. There is no undo.\n")
    else:
        print(f"\nBuilding {len(plan)} product(s) inside Tapstitch. Nothing "
              f"reaches the storefront without --publish.\n")
    s = T.session()
    done, failed = 0, []
    for r, _ in plan:
        print(f"{r['temple']} {r['garment']}")

        def note(msg):
            print(f"    {msg}", flush=True)

        try:
            print(f"    -> {run_row(s, client, data, r, a.publish, note)}\n")
            done += 1
        except (Exception, SystemExit) as e:
            # SystemExit as well as Exception: this codebase signals user-facing
            # failures with raise SystemExit, which is a BaseException, so
            # catching Exception alone would let finish_on_shopify's missing
            # handle or a config disagreement end the whole run silently, with
            # nothing recorded on the row that stopped it.
            record_failure(data, r, e)
            failed.append((r["temple"], r["garment"], safe_error(e)))
            print(f"    FAILED {safe_error(e)}\n")

    print(f"{done} finished, {len(failed)} failed.")
    for temple, gid, err in failed:
        print(f"  {temple} {gid}: {err}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
