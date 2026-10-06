"""Offline tests for the garment and description guards in generate.py. No network.

Run: ./.venv.nosync/bin/python tests/test_generate_channels.py
"""

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import flatten
import generate
from generate import all_garment_ids, fixed_description, load_garment_config

# --- channel filtering ------------------------------------------------------
# Only configs that say "channel": "tapstitch" are swept into a run, so a
# half-written new garment cannot reach the store by accident.
tapstitch = all_garment_ids()
assert tapstitch == ["crew", "hoodie", "tee"], tapstitch
assert all_garment_ids("tapstitch") == tapstitch
assert set(all_garment_ids(None)) == set(tapstitch), "every garment config is a Tapstitch one"
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
for gid in tapstitch:
    assert len(fixed_description(load_garment_config(gid))) > 1000, gid

# --- the fixed-section shape -------------------------------------------------
# Each garment assembles details -> care -> intro and drops the size guide
# (Evan, 16 Sep 2026). Checked against synthetic copy directories below as well,
# so the assertions stay true whatever the real garments' copy says.
for gid in tapstitch:
    html = fixed_description(load_garment_config(gid))
    assert html.index('class="product-details"') < html.index('class="product-intro"'), \
        f"{gid}: the details section must lead, before the founder message"
    assert "size-guide" not in html, f"{gid}: the size guide must not be in the description"

# Care instructions (Evan, 18 Sep 2026) are shared from one file by all three
# lines, and sit between the specs and the founder message.
for gid in tapstitch:
    html = fixed_description(load_garment_config(gid))
    assert html.index('class="product-details"') < html.index('class="care-instructions"') \
        < html.index('class="product-intro"'), \
        f"{gid}: care instructions belong between the specs and the founder message"
    assert html.count('class="care-instructions"') == 1, f"{gid}: exactly one care section"
# One shared file, byte-identical on every line, is the whole point of CARE_COPY:
# a wash temperature can never be right on the crew and stale on the tee.
care = (generate.PROJECT_ROOT / generate.CARE_COPY).read_text().strip()
for gid in tapstitch:
    assert care in fixed_description(load_garment_config(gid)), \
        f"{gid}: must carry the shared care file verbatim"

real = generate.PROJECT_ROOT / "reference" / "garment-copy" / "tee"

# a garment pointed at a directory that does not exist at all
cfg = dict(load_garment_config("tee"), garment_copy="reference/garment-copy/nope")
assert fixed_description(cfg) == "", "a missing copy directory must yield empty"

# and the half-populated cases: details and intro are both required. Either one
# missing must yield empty, or a product page ships half a description.
rel = Path("artifacts") / "test-garment-copy"
half = generate.PROJECT_ROOT / rel
try:
    half.mkdir(parents=True, exist_ok=True)
    cfg = dict(load_garment_config("tee"), garment_copy=str(rel))
    shutil.copy2(real / "product-intro.html", half / "product-intro.html")
    assert fixed_description(cfg) == "", \
        "intro present but details missing must still yield empty"
    (half / "product-details.html").write_text(
        '<section class="product-details"><p>d</p></section>')
    html = fixed_description(cfg)
    assert html and html.index('class="product-details"') < html.index('class="product-intro"')

    # A size-guide.html beside the other files is ignored rather than appended,
    # which is the case the three real folders are in (their size-guide.html
    # files predate the decision and are still on disk).
    shutil.copy2(real / "size-guide.html", half / "size-guide.html")
    assert "size-guide" not in fixed_description(cfg), \
        "a size-guide.html on disk must not reach the description"

    # details alone is not a description, because the founder message is the
    # rest of it.
    (half / "product-intro.html").unlink()
    assert fixed_description(cfg) == "", \
        "details present but intro missing must still yield empty"
finally:
    shutil.rmtree(half, ignore_errors=True)

# A garment whose care file has gone missing must hard-stop too,
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
