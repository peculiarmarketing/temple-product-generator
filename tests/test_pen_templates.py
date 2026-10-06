"""Offline tests for scripts/pen_templates.py against snapshots of the live layouts.

Run: ./.venv.nosync/bin/python tests/test_pen_templates.py
"""

import contextlib
import copy
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.pen_templates import (  # noqa: E402
    BAND_ID, COLLECTION_LINK, HOME_TEMPLES, NAVY, ORANGE, SHOWCASE_ID,
    changed_paths, guard, homepage_layout, product_layout, split_banner, verify,
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
# round 2, later: the homepage before/after labels in capitals too; the What you get
# cards navy (the theme's accent-1 scheme: navy background, white text) instead of grey.
hs = home["sections"]["process"]["settings"]
assert (S["process"]["settings"]["before_label"], hs["before_label"], hs["after_label"]) == ("The temple", "THE TEMPLE", "THE DRAWING")
assert S["what_you_get"]["settings"]["cards_color_scheme"] == "background-2"
assert home["sections"]["what_you_get"]["settings"]["cards_color_scheme"] == "accent-1"
# The exact set of settings golive may change on the homepage, written out by hand so a
# transform that touches anything else fails here (the guard in planned() uses its own
# independent list, allowed_paths).
HOME_CHANGES = {
    ("order",), ("sections", SHOWCASE_ID), ("sections", "hero", "disabled"),
    ("sections", "browse", "disabled"), ("sections", "featured_products", "settings", "collection"),
    ("sections", "process", "settings", "custom_colors_solid_button_background"),
    ("sections", "suggest_form", "settings", "custom_colors_solid_button_background"),
    ("sections", "process", "settings", "before_label"), ("sections", "process", "settings", "after_label"),
    ("sections", "what_you_get", "settings", "cards_color_scheme"),
}
assert changed_paths(index, home) == HOME_CHANGES, sorted(changed_paths(index, home) ^ HOME_CHANGES)
guard("templates/index.json", index, home)
assert index["order"][0] == "hero" and "disabled" not in S["hero"], "input was mutated"
assert homepage_layout(index, "shopify://collections/x")["sections"][SHOWCASE_ID]["settings"]["link"] == "shopify://collections/x"

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
D = ("sections", "main", "blocks", "Details", "blocks")
STICKY = "e7a28cbe-03cb-4c9d-a2c4-0e3e76ffb3e5"
PRODUCT_CHANGES = {
    ("order",), ("sections", BAND_ID),
    D + ("buy_buttons", "settings", "custom_color"),  # enable_custom_color is already true live
    D + (STICKY, "settings", "enable_custom_btn_color"), D + (STICKY, "settings", "custom_btn_color"),
    ("sections", "comparison_slider_zhGtKY", "settings", "before_label"),
    ("sections", "comparison_slider_zhGtKY", "settings", "after_label"),
}
assert changed_paths(product, prod) == PRODUCT_CHANGES, sorted(changed_paths(product, prod) ^ PRODUCT_CHANGES)
guard("templates/product.json", product, prod)

# the buy-buttons colour toggle is switched on even where it was off
p2 = copy.deepcopy(product)
p2["sections"]["main"]["blocks"]["Details"]["blocks"]["buy_buttons"]["settings"]["enable_custom_color"] = False
assert product_layout(p2)["sections"]["main"]["blocks"]["Details"]["blocks"]["buy_buttons"]["settings"]["enable_custom_color"] is True

# two sticky bars or no comparison slider: refuse rather than colour or label the wrong one
two = copy.deepcopy(product)
blocks = two["sections"]["main"]["blocks"]["Details"]["blocks"]
blocks["second_sticky"] = copy.deepcopy(blocks[STICKY])
none = copy.deepcopy(product)
del none["sections"]["comparison_slider_zhGtKY"]
none["order"].remove("comparison_slider_zhGtKY")
for doc, word in ((two, "product_sticky-atc"), (none, "comparison-slider")):
    try:
        product_layout(doc)
        raise AssertionError(f"product_layout guessed with an ambiguous {word}")
    except ValueError as e:
        assert word in str(e), e

# the guard refuses a change outside the allowed list, and a missing required one
bad = copy.deepcopy(prod)
bad["sections"]["main"]["settings"]["color_scheme"] = "accent-2"
for before, after in ((product, bad), (product, product)):
    try:
        guard("templates/product.json", before, after)
        raise AssertionError("guard let an unexpected layout through")
    except SystemExit:
        pass

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
    verify(product, tampered, PRODUCT_CHANGES)
    raise AssertionError("verify missed a stray change")
except SystemExit:
    pass


# verify also catches an expected change that is MISSING (old slideshow left switched on)
from scripts.pen_templates import revert_check  # noqa: E402
half = copy.deepcopy(home)
del half["sections"]["hero"]["disabled"]
try:
    verify(index, half, HOME_CHANGES)
    raise AssertionError("verify accepted a golive that left the slideshow on")
except SystemExit:
    pass

# revert puts the saved layout back only when the live one is still exactly what golive
# sent; anything edited in the theme editor since (a setting, a colour tweak, a section
# reorder) would be wiped, so it refuses and names what changed.
assert revert_check(home, index, home) is True
assert revert_check(prod, product, prod) is True
edited = copy.deepcopy(home)
edited["sections"]["faq"]["settings"]["heading"] = "Edited after golive"
tweaked = copy.deepcopy(prod)
tweaked["sections"]["main"]["blocks"]["Details"]["blocks"]["buy_buttons"]["settings"]["custom_color"] = "#E07000"
moved = copy.deepcopy(home)
rest = [k for k in moved["order"] if k != SHOWCASE_ID]
rest[-1], rest[-2] = rest[-2], rest[-1]
moved["order"] = [SHOWCASE_ID] + rest
for live, saved, sent, word in ((edited, index, home, "faq"), (tweaked, product, prod, "custom_color"),
                                (moved, index, home, "order")):
    try:
        revert_check(live, saved, sent)
        raise AssertionError(f"revert would wipe a {word} change made after golive")
    except SystemExit as e:
        assert word in str(e), e

# a layout that is already back to the saved copy needs no revert (and must not block the other)
assert revert_check(index, index, home) is False

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

# golive end to end with stand-ins: refuses before any write while the collection 404s,
# checks the homepage row's collection even when --link points elsewhere, and goes ahead at 200.
import scripts.pen_templates as pt  # noqa: E402
class FakeClient:
    def gql(self, query, variables=None):
        assert "primaryDomain" in query, query
        return {"shop": {"primaryDomain": {"host": "shop.example"}}}
FIXTEXT = {"templates/index.json": (FIX / "index.json").read_text(),
           "templates/product.json": (FIX / "product.json").read_text()}
def golive(argv, status):
    asked, writes = [], []
    class Resp:
        status_code = status
    saved = (pt.ShopifyClient, pt.theme_file, pt.main_theme_id, pt.upsert_theme_files, pt.requests.get)
    pt.ShopifyClient = FakeClient
    pt.theme_file = lambda c, n: ("gid://theme/1", FIXTEXT[n])
    pt.main_theme_id = lambda c: "gid://theme/1"
    pt.upsert_theme_files = lambda c, t, f: writes.append(sorted(f))
    pt.requests.get = lambda url, timeout: (asked.append(url), Resp())[1]
    out = io.StringIO()
    try:
        with contextlib.redirect_stdout(out):
            try:
                rc = pt.main(argv)
            except SystemExit as e:
                rc = str(e)
    finally:
        pt.ShopifyClient, pt.theme_file, pt.main_theme_id, pt.upsert_theme_files, pt.requests.get = saved
    return rc, asked, writes

rc, asked, writes = golive(["golive", "--dry-run"], 404)
assert "Online Store" in str(rc) and writes == [], (rc, writes)
assert "https://shop.example/collections/temple-design-products" in asked, asked
rc, asked, writes = golive(["golive", "--dry-run", "--link", "shopify://pages/about"], 404)
assert "Online Store" in str(rc), "the homepage row's collection was not checked"
rc, asked, writes = golive(["golive", "--dry-run"], 200)
assert rc == 0 and writes == [], (rc, writes)

print("ok")
