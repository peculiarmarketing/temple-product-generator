"""Offline tests for scripts/pen_templates.py against snapshots of the live layouts.

Run: ./.venv.nosync/bin/python tests/test_pen_templates.py
"""

import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.pen_templates import (  # noqa: E402
    BAND_ID, HOME_TEMPLES, INTERIM_LINK, SHOWCASE_ID,
    add_band, add_showcase, changed_paths, split_banner, verify,
)

FIX = Path(__file__).resolve().parent / "fixtures/theme"
_, index = split_banner((FIX / "index.json").read_text())
_, product = split_banner((FIX / "product.json").read_text())

# homepage: showcase first, hero switched off (not deleted), wording copied exactly
home = add_showcase(index)
slide = index["sections"]["hero"]["blocks"][index["sections"]["hero"]["block_order"][0]]["settings"]
show = home["sections"][SHOWCASE_ID]
assert home["order"][0] == SHOWCASE_ID and home["order"][1:] == index["order"]
assert home["sections"]["hero"]["disabled"] is True
assert show["type"] == "pp-temple-showcase"
assert show["settings"]["heading"] == slide["heading"] == "Made to start the conversation"
assert show["settings"]["subheading"] == slide["subheading"]
assert show["settings"]["button_label"] == slide["button_label"] == "Find your temple"
assert show["settings"]["link"] == INTERIM_LINK
assert show["settings"]["temples"] == HOME_TEMPLES
assert "hero" in home["sections"], "the old banner must be kept, only disabled"
verify(index, home, {("order",), ("sections", SHOWCASE_ID), ("sections", "hero", "disabled")})
assert index["order"][0] == "hero" and "disabled" not in index["sections"]["hero"], "input was mutated"
assert add_showcase(index, "shopify://collections/shop")["sections"][SHOWCASE_ID]["settings"]["link"] == "shopify://collections/shop"

# product: band right after main, nothing else moved
prod = add_band(product)
assert prod["order"][prod["order"].index("main") + 1] == BAND_ID
assert prod["sections"][BAND_ID] == {"type": "pp-temple-drawing", "settings": {}}
verify(product, prod, {("order",), ("sections", BAND_ID)})

# running twice is refused rather than doubling the section
for fn, doc in ((add_showcase, home), (add_band, prod)):
    try:
        fn(doc)
        raise AssertionError(f"{fn.__name__} ran twice")
    except ValueError:
        pass

# verify catches a stray change anywhere else
tampered = copy.deepcopy(prod)
tampered["sections"]["main"]["settings"]["x"] = 1
assert ("sections", "main", "settings", "x") in changed_paths(product, tampered)
try:
    verify(product, tampered, {("order",), ("sections", BAND_ID)})
    raise AssertionError("verify missed a stray change")
except SystemExit:
    pass


# verify also catches an expected change that is MISSING (old slideshow left switched on)
from scripts.pen_templates import EXPECTED_INDEX, EXPECTED_PRODUCT, revert_check  # noqa: E402
half = copy.deepcopy(home)
del half["sections"]["hero"]["disabled"]
try:
    verify(index, half, EXPECTED_INDEX)
    raise AssertionError("verify accepted a golive that left the slideshow on")
except SystemExit:
    pass

# revert puts back the saved layout only when the live one is exactly "saved + golive";
# anything edited in the theme editor since golive would be wiped, so it refuses.
revert_check(home, index, EXPECTED_INDEX)
revert_check(prod, product, EXPECTED_PRODUCT)
edited = copy.deepcopy(home)
edited["sections"]["faq"]["settings"]["heading"] = "Edited after golive"
try:
    revert_check(edited, index, EXPECTED_INDEX)
    raise AssertionError("revert would wipe an edit made after golive")
except SystemExit as e:
    assert "faq" in str(e), e

print("ok")
