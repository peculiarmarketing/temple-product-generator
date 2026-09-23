"""Offline tests for scripts/pen_templates.py against snapshots of the live layouts.

Run: ./.venv.nosync/bin/python tests/test_pen_templates.py
"""

import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.pen_templates import (  # noqa: E402
    BAND_ID, COLLECTION_LINK, HOME_TEMPLES, NAVY, ORANGE, SHOWCASE_ID,
    changed_paths, expected_paths, homepage_layout, product_layout, split_banner, verify,
)

FIX = Path(__file__).resolve().parent / "fixtures/theme"
_, index = split_banner((FIX / "index.json").read_text())
_, product = split_banner((FIX / "product.json").read_text())
S = index["sections"]

# homepage: showcase first, hero switched off (not deleted), wording copied exactly
home = homepage_layout(index)
slide = S["hero"]["blocks"][S["hero"]["block_order"][0]]["settings"]
show = home["sections"][SHOWCASE_ID]
assert home["order"][0] == SHOWCASE_ID and home["order"][1:] == index["order"]
assert home["sections"]["hero"]["disabled"] is True
assert show["type"] == "pp-temple-showcase"
assert show["settings"]["heading"] == slide["heading"] == "Made to start the conversation"
assert show["settings"]["subheading"] == slide["subheading"]
assert show["settings"]["button_label"] == slide["button_label"] == "Find your temple"
assert show["settings"]["link"] == COLLECTION_LINK == "shopify://collections/temple-design-products"
assert show["settings"]["temples"] == HOME_TEMPLES
assert "hero" in home["sections"], "the old banner must be kept, only disabled"
# round 2: the Browse row (dead state-collection cards) is switched off, not deleted;
# "The temples" row shows the new collection; the other orange buttons turn navy.
assert home["sections"]["browse"]["disabled"] is True and "browse" in home["order"]
assert home["sections"]["featured_products"]["settings"]["collection"] == "temple-design-products"
for sec in ("process", "suggest_form"):
    assert S[sec]["settings"]["custom_colors_solid_button_background"] == ORANGE
    assert home["sections"][sec]["settings"]["custom_colors_solid_button_background"] == NAVY
verify(index, home, expected_paths("templates/index.json", index))
assert index["order"][0] == "hero" and "disabled" not in S["hero"], "input was mutated"

# product: band right after main; Add to Cart (main and sticky bar) is the only orange
# button; the before/after slider says THE TEMPLE / THE DRAWING. Nothing else moves.
prod = product_layout(product)
P = prod["sections"]
assert prod["order"][prod["order"].index("main") + 1] == BAND_ID
assert P[BAND_ID] == {"type": "pp-temple-drawing", "settings": {}}
details = P["main"]["blocks"]["Details"]["blocks"]
buy = next(b for b in details.values() if b["type"] == "product_buy-buttons")["settings"]
sticky = next(b for b in details.values() if b["type"] == "product_sticky-atc")["settings"]
assert buy["enable_custom_color"] is True and buy["custom_color"] == ORANGE
assert buy["secondary_btn_custom_color"].lower() == NAVY.lower(), "Buy it now stays navy"
assert sticky["enable_custom_btn_color"] is True and sticky["custom_btn_color"] == ORANGE
slider = next(v for v in P.values() if v["type"] == "comparison-slider")["settings"]
assert (slider["before_label"], slider["after_label"]) == ("THE TEMPLE", "THE DRAWING")
verify(product, prod, expected_paths("templates/product.json", product))
assert len(expected_paths("templates/product.json", product)) == 7

# running twice is refused rather than doubling the section
for fn, doc in ((homepage_layout, home), (product_layout, prod)):
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
    verify(product, tampered, expected_paths("templates/product.json", product))
    raise AssertionError("verify missed a stray change")
except SystemExit:
    pass


# verify also catches an expected change that is MISSING (old slideshow left switched on)
from scripts.pen_templates import revert_check  # noqa: E402
EXPECTED_INDEX = expected_paths("templates/index.json", index)
EXPECTED_PRODUCT = expected_paths("templates/product.json", product)
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


# ...and a section reorder made after golive (order is one list, which golive changes
# anyway) must also refuse, or revert would quietly put the old order back.
moved = copy.deepcopy(home)
rest = [k for k in moved["order"] if k != SHOWCASE_ID]
rest[-1], rest[-2] = rest[-2], rest[-1]
moved["order"] = [SHOWCASE_ID] + rest
try:
    revert_check(moved, index, EXPECTED_INDEX)
    raise AssertionError("revert would wipe a section reorder made after golive")
except SystemExit:
    pass


# a layout that is already back to the saved copy needs no revert (and must not block the other)
assert revert_check(index, index, EXPECTED_INDEX) is False
assert revert_check(home, index, EXPECTED_INDEX) is True


# golive refuses while the button's collection is not on the Online Store: the homepage
# would otherwise link to a missing page and show placeholder products.
from scripts.pen_templates import collection_problem  # noqa: E402
seen = []
def fake_get(status):
    def get(url):
        seen.append(url)
        return status
    return get
assert collection_problem(COLLECTION_LINK, "shop.example", fake_get(200)) is None
# the collection page, not products.json: that answers 200 with [] even for no collection
assert seen[-1] == "https://shop.example/collections/temple-design-products"
msg = collection_problem(COLLECTION_LINK, "shop.example", fake_get(404))
assert msg and "Online Store" in msg, msg
assert collection_problem("shopify://pages/about", "shop.example", fake_get(404)) is None

print("ok")
