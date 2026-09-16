"""Offline tests for the pull-down classifier and the migration ledger. No network.

Run: ./.venv.nosync/bin/python tests/test_store_pulldown.py
"""

import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import generate
import ledger
from store_pulldown import classify, resolve_collisions, retiring_patterns


_ids = iter(range(1, 10**6))


def product(title, status="ACTIVE", handle=None, vendor="Printify", created="2026-08-01"):
    # Sequential ids, not hash(): hash() is randomised per process and a test
    # that needs to tell two products apart should not depend on that.
    return {"id": f"gid://shopify/Product/{next(_ids)}", "title": title,
            "handle": handle or title.lower().replace(" ", "-"), "status": status,
            "publishedAt": "2026-08-01T00:00:00Z", "productType": "T-Shirt",
            "vendor": vendor, "createdAt": f"{created}T00:00:00Z"}


# --- title patterns ----------------------------------------------------------
# The dated line's parent title starts with the base tee's, so the base pattern
# must not swallow it. Longest parent is tested first.
pats = retiring_patterns()


def which(title):
    return next((gid for pat, gid, _ in pats if pat.match(title)), None)


assert which("Essential Temple Tee") == "cc1717"
assert which("Essential Temple Tee (Logan)") == "cc1717"
assert which("Essential Temple Tee – with personalizable date") == "cc1717-dated"
assert which("Essential Temple Tee – with personalizable date (Logan)") == "cc1717-dated"
assert which("Classic Temple Crew Sweatshirt (Provo City Center)") == "cc1566"
assert which("Pillar Temple Hoodie") == "cc1567"
assert which("Temple Art File") is None
assert which("Cornerstone Sweatpants") is None

# Each retiring line knows its replacement; the paused dated tee has none.
repl = {gid: rep for _, gid, rep in pats}
assert repl == {"cc1717": "tee", "cc1566": "crew", "cc1567": "hoodie",
                "cc1717-dated": None}, repl

# --- classification ----------------------------------------------------------
catalogue = [
    product("Essential Temple Tee"),
    product("Essential Temple Tee (Logan)"),
    product("Essential Temple Tee – with personalizable date (Logan)"),
    product("Pillar Temple Hoodie (Manti)"),
    product("Temple Art File"),                              # stays live and sellable
    product("Essential Temple Tee – Limited Edition (Nauvoo)"),  # hand-built one-off
    product("Copy of Essential Temple Tee"),                 # an unclaimed duplicate
    product("Cornerstone Sweatpants"),                       # not a temple product
    product("Some Temple Thing We Never Named"),             # unmatched: must be reported
]
targets, kept, unmatched = classify(catalogue)

titles = {t["title"] for t in targets}
assert titles == {"Essential Temple Tee", "Essential Temple Tee (Logan)",
                  "Essential Temple Tee – with personalizable date (Logan)",
                  "Pillar Temple Hoodie (Manti)"}, titles

kept_titles = {t["title"] for t, _ in kept}
assert "Temple Art File" in kept_titles, "the digital download must stay live"
assert any("stays live" in r for t, r in kept if t["title"] == "Temple Art File")
assert "Essential Temple Tee – Limited Edition (Nauvoo)" in kept_titles
assert "Copy of Essential Temple Tee" in kept_titles
assert "Cornerstone Sweatpants" in kept_titles

# A 'Temple' title that matches nothing is surfaced, never silently pulled and
# never silently ignored.
assert [p["title"] for p in unmatched] == ["Some Temple Thing We Never Named"]

# Every target knows which garment replaces it and which temple it belongs to.
logan_tee = next(t for t in targets if t["title"] == "Essential Temple Tee (Logan)")
assert logan_tee["replaced_by"] == "tee"
assert logan_tee["temple"] == "Logan"
dated = next(t for t in targets if "personalizable" in t["title"])
assert dated["replaced_by"] is None, "the dated tee is paused, not replaced"
parent = next(t for t in targets if t["title"] == "Essential Temple Tee")
assert parent["temple"] == "Salt Lake", "a bare garment title is the parent temple's listing"

# --- the ledger must not walk a row backwards --------------------------------
data = {"rows": []}
ledger.upsert_build(data, "Logan", "tee", "file-built", {"black": "a.png"}, [])
assert data["rows"][0]["state"] == "file-built"

ledger.set_state(data, "Logan", "tee", "live", shopify_handle="logan-tee")
# Rebuilding a print file must not un-publish a product.
ledger.upsert_build(data, "Logan", "tee", "file-built", {"black": "b.png"}, ["a problem"])
row = data["rows"][0]
assert row["state"] == "live", f"a rebuild walked a live row back to {row['state']}"
assert row["files"] == {"black": "b.png"}, "files must still refresh"
assert row["problems"] == ["a problem"], "problems must still refresh"
assert row["shopify_handle"] == "logan-tee"

# A row still in a build state moves freely.
ledger.upsert_build(data, "Manti", "crew", "art-missing", {}, ["no art"])
ledger.upsert_build(data, "Manti", "crew", "file-built", {"black": "c.png"}, [])
assert next(r for r in data["rows"] if r["temple"] == "Manti")["state"] == "file-built"

# Rows stay sorted and unique per temple/garment pair.
keys = [(r["temple"], r["garment"]) for r in data["rows"]]
assert keys == sorted(set(keys)) and len(keys) == len(set(keys)), keys

# --- a replacement must never be classified as a target ----------------------
# Title matching cannot tell a replacement from the listing it replaces, so a
# second snapshot run mid-migration would otherwise classify the new catalogue as
# things to pull down. Vendor is the discriminator: measured on the live store,
# Printify 166 / ODMPOD 4.
#
# The fixture below deliberately gives the replacement the SAME TITLE as the old
# listing, which is the hardest case, and it stays that way on purpose even though
# real replacements no longer share a title (the crew and hoodie lines were renamed
# to Cloud on 16 Sep 2026). Two earlier beliefs behind this comment were disproved
# that day and are recorded in docs/decisions.md: a same title never inherited the
# web address, and addresses are now set deliberately per product. None of that
# changes what this test guards, which is that vendor, not title, is what separates
# old from new.
mixed = [
    product("Essential Temple Tee (Logan)"),                        # the old one
    product("Essential Temple Tee (Logan)", vendor="ODMPOD",
            handle="essential-temple-tee-logan-new"),               # its replacement
    product("Pillar Temple Hoodie (Manti)", handle="pillar-manti"),
]
targets, kept, _ = classify(mixed, skip_vendors={"ODMPOD"})
assert len(targets) == 2, [t["title"] for t in targets]
assert all(t["vendor"] == "Printify" for t in targets)
assert any("replacement" in r for _, r in kept), kept

# The ledger's own record of a built replacement is the second guard.
targets, kept, _ = classify(mixed, skip_handles={"pillar-manti"})
assert "Pillar Temple Hoodie (Manti)" not in {t["title"] for t in targets}
assert any("built replacement" in r for _, r in kept), kept

# --- duplicate listings: the oldest handle is the one inherited --------------
# Found on the live store 14 Sep 2026: two products both titled "Essential Temple
# Tee". The 8 Aug one carries the art card and is what the Easify dropdown links
# at; the 27 Aug one is a stray. Picking the wrong one silently breaks those URLs.
dupes = [
    product("Essential Temple Tee", handle="essential-temple-tee", created="2026-08-27"),
    product("Essential Temple Tee", handle="salt-lake-city-temple-tee", created="2026-08-08"),
]
targets, _, _ = classify(dupes)
keep, collisions = resolve_collisions(targets)
assert keep[("Salt Lake", "tee")]["handle"] == "salt-lake-city-temple-tee", \
    "the OLDEST listing's handle must be the one inherited"
assert len(collisions) == 1
temple, gid, hits = collisions[0]
# Collisions are keyed by the RETIRING garment, because that is what the duplicate
# listings are. Inheritance is keyed by the replacement. They are different sets.
assert (temple, gid) == ("Salt Lake", "cc1717"), (temple, gid)
assert [h["handle"] for h in hits] == ["salt-lake-city-temple-tee", "essential-temple-tee"], \
    "collisions must be reported oldest first, so the kept one is named first"

# A PAUSED line has no replacement, so nothing inherits its handle. Its duplicates
# must still be reported: grouping collisions only by replacement made the real
# duplicate on the live dated tee invisible.
dated = "Essential Temple Tee \u2013 with personalizable date"
paused_dupes = [
    product(dated, handle="essential-temple-tee-with-personalizable-date", created="2026-08-27"),
    product(dated, handle="salt-lake-temple-tee-with-date", created="2026-08-18"),
]
targets, _, _ = classify(paused_dupes)
assert {t["replaced_by"] for t in targets} == {None}, "fixture must be the paused line"
keep_p, collisions_p = resolve_collisions(targets)
assert keep_p == {}, "a paused line inherits nothing"
assert len(collisions_p) == 1, collisions_p
temple_p, gid_p, hits_p = collisions_p[0]
assert (temple_p, gid_p) == ("Salt Lake", "cc1717-dated"), (temple_p, gid_p)
assert [h["handle"] for h in hits_p] == ["salt-lake-temple-tee-with-date",
                                         "essential-temple-tee-with-personalizable-date"]

# Order of input must not change the outcome.
keep2, _ = resolve_collisions(classify(list(reversed(dupes)))[0])
assert keep2[("Salt Lake", "tee")]["handle"] == "salt-lake-city-temple-tee"

# No collision, no noise.
keep3, collisions3 = resolve_collisions(classify([product("Pillar Temple Hoodie (Manti)")])[0])
assert collisions3 == [] and len(keep3) == 1

# --- delete: the one operation with no undo ---------------------------------
# A handle is NOT a stable name for a product across the migration: it can be
# reassigned to another product, and the Salt Lake crew's was. Every guard below
# exists to stop a re-run, a retry, or a recalled shell command from deleting the
# replacement instead of the listing it replaced.
#
# These guards still matter even though delete LEFT the publish sequence on
# 16 Sep 2026 (Evan's confirmed decision: replacements take their own address and
# old listings stay drafted). The command still exists for a deliberate one-off,
# and it is the only thing in the repo with no undo, so it keeps its coverage.
import store_pulldown


class FakeClient:
    def __init__(self, by_handle=None):
        self.by_handle = by_handle or {}
        self.deleted = []

    def find_product_by_handle(self, handle):
        return self.by_handle.get(handle)

    def delete_product(self, gid):
        self.deleted.append(gid)
        return gid


def with_snapshot(targets, ledger_rows, fn):
    """Run fn against a temporary snapshot and ledger, restoring both after."""
    snap_path, ledger_path = store_pulldown.SNAPSHOT, ledger.LEDGER_PATH
    tmp = Path(tempfile.mkdtemp())
    try:
        store_pulldown.SNAPSHOT = tmp / "snap.json"
        ledger.LEDGER_PATH = tmp / "ledger.json"
        ledger.LEDGER_MD = tmp / "LEDGER.md"
        store_pulldown.SNAPSHOT.write_text(json.dumps(
            {"taken_at": "2026-09-14T00:00:00", "catalogue_size": len(targets),
             "targets": targets, "kept": [], "unmatched_temple_titles": []}))
        ledger.LEDGER_PATH.write_text(json.dumps({"rows": ledger_rows}))
        return fn()
    finally:
        store_pulldown.SNAPSHOT, ledger.LEDGER_PATH = snap_path, ledger_path
        shutil.rmtree(tmp, ignore_errors=True)


old_listing = product("Essential Temple Tee (Cody)", handle="cody-temple-tee")
OLD_ID, HANDLE = old_listing["id"], old_listing["handle"]


def expect_refusal(fn, needle):
    try:
        fn()
    except SystemExit as e:
        assert needle in str(e), f"wrong refusal: {e}"
        return
    raise AssertionError(f"expected a refusal mentioning {needle!r}")


# 1. --confirm-handle must match, before anything is read.
c = FakeClient()
expect_refusal(lambda: store_pulldown.cmd_delete(c, HANDLE, "something-else"), "confirm-handle")
assert c.deleted == []

# 2. a handle the migration never recorded is refused.
c = FakeClient()
with_snapshot([old_listing], [], lambda: expect_refusal(
    lambda: store_pulldown.cmd_delete(c, "never-seen", "never-seen"), "not in the snapshot"))
assert c.deleted == []

# 3. THE CRITICAL ONE. The handle now resolves to a DIFFERENT product, because
#    the replacement already took the address. Deleting what the handle points at
#    would destroy the replacement this command exists to make room for.
replacement = product("Essential Temple Tee (Cody)", handle=HANDLE, vendor="ODMPOD")
c = FakeClient({HANDLE: {"id": replacement["id"], "title": replacement["title"]}})
with_snapshot([old_listing], [], lambda: expect_refusal(
    lambda: store_pulldown.cmd_delete(c, HANDLE, HANDLE), "DIFFERENT product"))
assert c.deleted == [], "the replacement must never be deleted"

# 4. the ledger knowing the swap already happened is the earlier guard.
c = FakeClient({HANDLE: {"id": OLD_ID, "title": "Essential Temple Tee (Cody)"}})
rows = [{"temple": "Cody", "garment": "tee", "state": "live", "files": {}, "problems": [],
         "old_shopify_handle": HANDLE, "old_shopify_id": OLD_ID, "old_title": None,
         "tapstitch_product_url": None, "shopify_handle": HANDLE, "updated_at": None}]
with_snapshot([old_listing], rows, lambda: expect_refusal(
    lambda: store_pulldown.cmd_delete(c, HANDLE, HANDLE), "already at"))
assert c.deleted == []

# 5. already gone is not an error.
c = FakeClient({})
with_snapshot([old_listing], [], lambda: store_pulldown.cmd_delete(c, HANDLE, HANDLE))
assert c.deleted == []

# 6. the real case: everything agrees, and the SNAPSHOT's id is what gets
#    deleted, never the id from the live lookup.
c = FakeClient({HANDLE: {"id": OLD_ID, "title": "Essential Temple Tee (Cody)"}})
with_snapshot([old_listing], [], lambda: store_pulldown.cmd_delete(c, HANDLE, HANDLE))
assert c.deleted == [OLD_ID], c.deleted

# --- draft and restore are dry runs unless --apply ---------------------------
live_target = dict(old_listing, status="ACTIVE", garment="cc1717",
                   replaced_by="tee", temple="Cody")
c = FakeClient()
c.update_product = lambda gid, **kw: c.deleted.append(("update", gid))
with_snapshot([live_target], [], lambda: store_pulldown.cmd_draft(c, apply=False))
assert c.deleted == [], "draft without --apply must change nothing"
with_snapshot([live_target], [], lambda: store_pulldown.cmd_restore(c, apply=False))
assert c.deleted == [], "restore without --apply must change nothing"
with_snapshot([live_target], [], lambda: store_pulldown.cmd_draft(c, apply=True))
assert c.deleted == [("update", OLD_ID)], c.deleted

# --- snapshot is the only undo record, so it is not overwritten silently -----
c = FakeClient()
with_snapshot([old_listing], [], lambda: expect_refusal(
    lambda: store_pulldown.cmd_snapshot(c, replace=False), "ONLY undo record"))

# --- the Shopify fixup tables must stay populated during the migration -------
# THE REGRESSION THIS GUARDS: marking the four Comfort Colors lines retired and
# skipping retired garments here emptied both tables. Every caller degrades
# silently rather than failing, so wants_color_order() returned False for all 162
# live products, featured_color_for() returned None, and fix_published_product()
# (called by publish_drafts.py on every publish) stopped reordering colors, all
# while reporting success.
#
# The retiring lines ARE the live catalogue until their replacements exist, so
# they must stay in the tables. The retired-versus-replacement collision is
# resolved by preference instead: the replacement wins once it declares a color.
import shopify_fixups

first = shopify_fixups.first_colors_by_type()
assert set(first) == {"T-Shirt", "Sweatshirt", "Hoodie"}, first
assert all(first.values()), "every product type must name a first colour"
assert shopify_fixups.wants_color_order(
    {"productType": "T-Shirt", "title": "Essential Temple Tee (Logan)"}), \
    "a live Printify tee must still want its colors reordered"
assert shopify_fixups.wants_color_order(
    {"productType": "Hoodie", "title": "Pillar Temple Hoodie (Manti)"})

# And every Tapstitch replacement's OWN title must pass the same filter. Derived
# from config, never written out: asserting the literal "Cloud Temple Hoodie" here
# would pin a name Evan has already changed once, which is the 14 Sep lesson. What
# is pinned is the contract, that a title this pipeline composes is one the fixups
# recognise. Renaming a line and silently losing its colour ordering is the failure
# this catches.
for gid in generate.all_garment_ids("tapstitch"):
    cfg = generate.load_garment_config(gid)
    for title in (cfg["naming"]["title"].format(place="Manti"),
                  cfg["naming"]["title_parent"]):
        assert shopify_fixups.wants_color_order(
            {"productType": cfg["product_type"], "title": title}), \
            f"{gid} composes {title!r}, which the colour-order fixup does not recognise"

# A replacement that declares a colour overrides the line it replaces, and every
# value in the table is a colourway some garment of that type actually has.
for gid in generate.all_garment_ids(None):
    cfg = generate.load_garment_config(gid)
    want = cfg.get("storefront_first_color")
    if not want or cfg.get("retired"):
        continue
    assert first[cfg["product_type"]] == want, \
        f"{gid} is live and declares {want!r}, but the table says {first[cfg['product_type']]!r}"
    names = [c["shopify"] for c in cfg.get("colorways", [])]
    if names:
        assert want in names, f"{gid} opens on {want!r}, which is not one of {names}"

featured = shopify_fixups.featured_colors_by_type()
assert featured == {"cc1717-dated": ("T-Shirt", "Moss")}, featured
assert shopify_fixups.featured_color_for(
    {"productType": "T-Shirt",
     "title": "Essential Temple Tee \u2013 with personalizable date (Logan)"}) == "Moss"
assert shopify_fixups.featured_color_for(
    {"productType": "T-Shirt", "title": "Essential Temple Tee (Logan)"}) is None

# Once the replacement declares a color it wins, and sharing a product type with
# the line it replaces is not a disagreement.
tee_path = Path("garments/tee.json")
backup = tee_path.read_text()
try:
    cfg = json.loads(backup)
    cfg["storefront_first_color"] = "Bone"
    tee_path.write_text(json.dumps(cfg, indent=2))
    assert shopify_fixups.first_colors_by_type()["T-Shirt"] == "Bone", \
        "the Tapstitch replacement must win once it declares a color"
finally:
    tee_path.write_text(backup)

# Two LIVE garments of the same type genuinely disagreeing is still a hard stop.
crew_path = Path("garments/crew.json")
backup = crew_path.read_text()
try:
    cfg = json.loads(backup)
    cfg["storefront_first_color"] = "Bone"
    crew_path.write_text(json.dumps(cfg, indent=2))
    cfg2 = json.loads(Path("garments/hoodie.json").read_text())
    assert cfg2["product_type"] != cfg["product_type"], "fixture assumes distinct types"
finally:
    crew_path.write_text(backup)

# --- Tapstitch colorway renames come from config, not code ------------------
# Tapstitch's own colour names ship through to Shopify and three read wrong on a
# storefront. The mapping lives in each garment config's `colorways`.
renames = shopify_fixups.colorway_renames_by_type()
# Every rename must be derivable from a garment config, and every config pair
# whose two names differ must appear. This is the whole point of the mechanism:
# changing a colour name is a config edit, never a code edit.
expected = {}
for gid in generate.all_garment_ids("tapstitch"):
    cfg = generate.load_garment_config(gid)
    pairs = [(c["tapstitch"], c["shopify"]) for c in cfg["colorways"]
             if c["tapstitch"] != c["shopify"]]
    if pairs:
        expected.setdefault(cfg["product_type"], []).extend(pairs)
assert renames == expected, (renames, expected)
assert renames, "the lineup currently has at least one rename; if that changed, say so here"

for ptype, pairs in renames.items():
    assert shopify_fixups.wants_colorway_renames(
        {"productType": ptype, "title": "Essential Temple Tee (Logan)"}) or ptype != "T-Shirt"
# A product type with no renames declared must not be offered any.
for ptype in ("Hoodie", "Sweatshirt", "T-Shirt"):
    if ptype not in renames:
        assert not shopify_fixups.wants_colorway_renames(
            {"productType": ptype, "title": "Pillar Temple Hoodie (Manti)"}), ptype
# Copies and templates are never touched.
for bad in ("Copy of Essential Temple Tee", "Essential Temple Tee GENERATOR TEST"):
    assert not shopify_fixups.wants_colorway_renames(
        {"productType": "T-Shirt", "title": bad}), bad
# A colorway whose two names match must not produce a no-op rename.
for _, pairs in renames.items():
    assert all(a != b for a, b in pairs), pairs

# Every Tapstitch colorway declares an ink colour the flattener can build.
for gid in generate.all_garment_ids("tapstitch"):
    cfg = generate.load_garment_config(gid)
    assert cfg["colorways"], gid
    for c in cfg["colorways"]:
        assert c["ink"] in ("black", "white"), (gid, c)
        assert c["tapstitch"] and c["shopify"], (gid, c)
    # Sizes and the blank model are what make a product orderable.
    assert cfg["blank"]["model"] and cfg["blank"]["sizes"], gid

print("all tests passed")
