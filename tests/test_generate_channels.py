"""Offline tests for the two-channel guards in generate.py. No network.

These cover the three things that keep the retiring Printify pipeline and the
new Tapstitch one from contaminating each other. All three were verified by hand
during the migration build and had no regression test; two of them had already
broken once.

Run: ./.venv.nosync/bin/python tests/test_generate_channels.py
"""

import json
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import flatten
import generate
from generate import all_garment_ids, fixed_description, load_garment_config

# --- channel filtering ------------------------------------------------------
# generate.py IS the Printify pipeline. Sweeping a Tapstitch garment through it
# would fail late and messily: those configs carry no blueprint_id and no print
# provider.
printify = all_garment_ids("printify")
tapstitch = all_garment_ids("tapstitch")
everything = all_garment_ids(None)

assert printify == ["cc1566", "cc1567", "cc1717", "cc1717-dated"], printify
assert tapstitch == ["crew", "hoodie", "tee"], tapstitch
assert set(everything) == set(printify) | set(tapstitch)
assert not set(printify) & set(tapstitch), "a garment cannot be on both channels"
assert all_garment_ids() == printify, "the default must stay printify"

# Ordering is by STEM, not filename. "cc1717-dated.json" sorts before
# "cc1717.json" because '-' < '.', but the ids must come out the other way round.
# This broke once during the migration build.
assert printify.index("cc1717") < printify.index("cc1717-dated"), printify

# Every Printify config declares what replaces it, and the paused dated tee
# declares that nothing does.
replacements = {g: load_garment_config(g).get("replaced_by") for g in printify}
assert replacements == {"cc1717": "tee", "cc1566": "crew", "cc1567": "hoodie",
                        "cc1717-dated": None}, replacements
for gid in tapstitch:
    assert load_garment_config(gid)["layout_profile"] == "back_temple_text", gid

# --- the empty-description guard --------------------------------------------
# THE load-bearing behaviour: a garment whose copy has not been written yet must
# produce an EMPTY description. An empty description beats the wrong garment's
# specifications on a live product page, so a placeholder would be worse than
# nothing. The synthetic cases below are what test that guard, deliberately: this
# block used to assert the three Tapstitch garments were still empty, which stopped
# being a test of the guard and started being a test of how far the copy had got
# the moment the copy was written (16 Sep 2026).
for gid in printify + tapstitch:
    assert len(fixed_description(load_garment_config(gid))) > 1000, gid

# --- the two fixed-section shapes -------------------------------------------
# A garment with a product-details.html assembles details -> intro and drops the
# size guide (Evan, 16 Sep 2026); one without keeps the older intro -> size-guide
# shape. Both are checked against synthetic copy directories so the assertions
# stay true whatever the real garments' copy says.
for gid in tapstitch:
    html = fixed_description(load_garment_config(gid))
    assert html.index('class="product-details"') < html.index('class="product-intro"'), \
        f"{gid}: the details section must lead, before the founder message"
    assert "size-guide" not in html, f"{gid}: the size guide must not be in the description"
for gid in printify:
    assert "size-guide" in fixed_description(load_garment_config(gid)), \
        f"{gid}: the retiring garments keep their size guide"

# Care instructions (Evan, 18 Sep 2026) ride the details shape only, shared from
# one file by all three current lines, and sit between the specs and the founder
# message. The retiring lines must not gain a care section: their live listings
# are not being rewritten, so copy they would never receive should not compose.
for gid in tapstitch:
    html = fixed_description(load_garment_config(gid))
    assert html.index('class="product-details"') < html.index('class="care-instructions"') \
        < html.index('class="product-intro"'), \
        f"{gid}: care instructions belong between the specs and the founder message"
    assert html.count('class="care-instructions"') == 1, f"{gid}: exactly one care section"
for gid in printify:
    assert "care-instructions" not in fixed_description(load_garment_config(gid)), \
        f"{gid}: the retiring garments get no care section"

# One shared file, byte-identical on every line, is the whole point of CARE_COPY:
# a wash temperature can never be right on the crew and stale on the tee.
care = (generate.PROJECT_ROOT / generate.CARE_COPY).read_text().strip()
for gid in tapstitch:
    assert care in fixed_description(load_garment_config(gid)), \
        f"{gid}: must carry the shared care file verbatim"

with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    real = generate.PROJECT_ROOT / "reference" / "garment-copy" / "cc1717"

    # a garment pointed at a directory that does not exist at all
    cfg = dict(load_garment_config("cc1717"), garment_copy="reference/garment-copy/nope")
    assert fixed_description(cfg) == "", "a missing copy directory must yield empty"

    # and the half-populated case: the check is `and`, not `or`. One file present
    # and one missing must still yield empty, or a product page ships an intro
    # with no size guide.
    rel = Path("artifacts") / "test-garment-copy"
    half = generate.PROJECT_ROOT / rel
    try:
        half.mkdir(parents=True, exist_ok=True)
        shutil.copy2(real / "product-intro.html", half / "product-intro.html")
        cfg = dict(load_garment_config("cc1717"), garment_copy=str(rel))
        assert fixed_description(cfg) == "", \
            "intro present but size guide missing must still yield empty"
        shutil.copy2(real / "size-guide.html", half / "size-guide.html")
        assert fixed_description(cfg) != "", "both files present must yield real copy"

        # Now the details-first shape, in the same directory. A product-details.html
        # switches the garment to details -> intro; the size guide sitting beside it
        # must be ignored rather than appended, which is the case the three real
        # Tapstitch folders are in (their size-guide.html files were written before
        # the same decision and are still on disk).
        (half / "product-details.html").write_text(
            '<section class="product-details"><p>d</p></section>')
        html = fixed_description(cfg)
        assert "size-guide" not in html, \
            "a garment with product-details.html must drop the size guide"
        assert html.index('class="product-details"') < html.index('class="product-intro"')

        # The details shape must not secretly still REQUIRE the size guide. Every
        # other case here has one on disk (so do all three real Tapstitch
        # folders, left over from before the decision), so without this the
        # branch that drops it is never exercised without it and a regression
        # re-adding the requirement would block every Tapstitch row instead.
        (half / "size-guide.html").unlink()
        html = fixed_description(cfg)
        assert html and "size-guide" not in html, \
            "the details shape must not depend on a size-guide.html being present"

        # ...and the guard applies to this shape too: details alone is not a
        # description, because the founder message is the rest of it.
        (half / "product-intro.html").unlink()
        assert fixed_description(cfg) == "", \
            "details present but intro missing must still yield empty"
    finally:
        shutil.rmtree(half, ignore_errors=True)

# A details-shape garment whose care file has gone missing must hard-stop too,
# rather than quietly ship a page with no care instructions on it. Unlike the
# copy guard above this does NOT degrade to empty: one missing shared file must
# not blank an entire catalogue of live descriptions.
_care = generate.PROJECT_ROOT / generate.CARE_COPY
_saved = _care.read_text()
try:
    _care.unlink()
    try:
        fixed_description(load_garment_config("crew"))
        raise AssertionError("a missing care file must refuse, not degrade")
    except SystemExit:
        pass
finally:
    _care.write_text(_saved)
assert fixed_description(load_garment_config("crew")), "care file must be restored"

# A dated-style garment whose description_prefix is missing must hard-stop
# rather than publish a partial description.
cfg = dict(load_garment_config("cc1717"), description_prefix="reference/nope.html")
try:
    fixed_description(cfg)
    raise AssertionError("a missing description_prefix must refuse, not degrade")
except SystemExit:
    pass

# --- the temple scan --------------------------------------------------------
# Temples/All is a flat mirror of every black SVG kept for the digital download
# product. It is not a temple, and a sweep that treated it as one would put a
# bogus row in the ledger.
names = [f.name for f in flatten.temple_folders()]
assert "All" not in names, "Temples/All must never be swept as a temple"
assert not any(n.startswith((".", "1.")) for n in names), names
assert "Salt Lake" in names and len(names) > 30, len(names)
assert names == sorted(names), "temple order must be stable"

print("all tests passed")
