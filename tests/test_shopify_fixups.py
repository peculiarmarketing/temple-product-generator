"""Offline tests for the Shopify fixup tables and the migration ledger. No network.

Run: ./.venv.nosync/bin/python tests/test_shopify_fixups.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import generate
import ledger
import shopify_fixups

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

# --- the Shopify fixup tables -------------------------------------------------
# Every caller degrades silently rather than failing: an empty table makes
# wants_color_order() return False for every product and fix_published_product()
# stop reordering colours while still reporting success. So the tables are
# checked directly.
first = shopify_fixups.first_colors_by_type()
assert set(first) == {"T-Shirt", "Sweatshirt", "Hoodie"}, first
assert all(first.values()), "every product type must name a first colour"

# Every garment's OWN title must pass the same filter. Derived
# from config, never written out: asserting the literal "Cloud Temple Hoodie" here
# would pin a name Evan has already changed once, which is the 14 Sep lesson. What
# is pinned is the contract, that a title this pipeline composes is one the fixups
# recognise. Renaming a line and silently losing its colour ordering is the failure
# this catches.
for gid in generate.all_garment_ids():
    cfg = generate.load_garment_config(gid)
    for title in (cfg["naming"]["title"].format(place="Manti"),
                  cfg["naming"]["title_parent"]):
        assert shopify_fixups.wants_color_order(
            {"productType": cfg["product_type"], "title": title}), \
            f"{gid} composes {title!r}, which the colour-order fixup does not recognise"

# Every garment's first colour is in the table, and is a colourway that garment
# actually has.
for gid in generate.all_garment_ids():
    cfg = generate.load_garment_config(gid)
    want = cfg.get("storefront_first_color")
    if not want:
        continue
    assert first[cfg["product_type"]] == want, \
        f"{gid} declares {want!r}, but the table says {first[cfg['product_type']]!r}"
    names = [c["shopify"] for c in cfg.get("colorways", [])]
    if names:
        assert want in names, f"{gid} opens on {want!r}, which is not one of {names}"

# --- Tapstitch colorway renames come from config, not code ------------------
# Tapstitch's own colour names ship through to Shopify and three read wrong on a
# storefront. The mapping lives in each garment config's `colorways`.
renames = shopify_fixups.colorway_renames_by_type()
# Every rename must be derivable from a garment config, and every config pair
# whose two names differ must appear. This is the whole point of the mechanism:
# changing a colour name is a config edit, never a code edit.
expected = {}
for gid in generate.all_garment_ids():
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
for gid in generate.all_garment_ids():
    cfg = generate.load_garment_config(gid)
    assert cfg["colorways"], gid
    for c in cfg["colorways"]:
        assert c["ink"] in ("black", "white"), (gid, c)
        assert c["tapstitch"] and c["shopify"], (gid, c)
    # Sizes and the blank model are what make a product orderable.
    assert cfg["blank"]["model"] and cfg["blank"]["sizes"], gid

print("all tests passed")
