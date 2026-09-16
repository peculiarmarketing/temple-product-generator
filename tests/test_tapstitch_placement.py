"""Offline tests for the Tapstitch design geometry and payload. No network.

Run: ./.venv.nosync/bin/python tests/test_tapstitch_placement.py

WHY THIS FILE EXISTS. placement() decides where artwork sits on a physical
garment. It is the one thing in the Tapstitch route that fails without erroring:
wrong numbers do not raise, they print wrong clothing. Its only verification used
to be an ad-hoc check run in a shell against a response that lived outside the
repo, so nothing would have caught a regression.

WHAT IS PINNED HERE, and what is deliberately not. Pinned: the geometry Tapstitch
itself stored for the 15 Sep tee, and the invariants (centre, scale, truncation).
Those are observed facts about how their editor works, not choices anyone makes,
so if they change these tests SHOULD go red. NOT pinned: which blank is in use,
its print-area size, its DPI, its colour codes, or the retail price. Those are
Evan's lineup and have already changed twice in a week. The 14 Sep entry in
docs/decisions.md records two tests that failed on correct changes for exactly
that reason, so rectangles appear here as literal INPUTS to a pure function,
never as assertions about what a config currently says.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import tapstitch_api as T

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "tapstitch"


def fixture(name):
    return json.loads((FIXTURES / f"{name}-template.json").read_text())


# --- placement(), against what Tapstitch's own editor stored ------------------
# The 15 Sep tee: back print area x=214 y=194 w=260 h=327, source 4386x5516.
# The editor saved left=344 top=358 width=556 height=700 scale=0.4671428571.

TEE_AREA = {"x": 214.0, "y": 194.0, "width": 260.0, "height": 327.0}
TEE_SRC = (4386, 5516)

got = T.placement(TEE_AREA, TEE_SRC)
assert got["left"] == 344.0, "centred on the canvas instead of on the print area"
assert got["top"] == 357.5, "used the rectangle's corner instead of its centre "\
                            "(and 358 means it was rounded, which we do not do)"
assert got["width"] == 556, "round() instead of int() on the contain-fit gives 557"
assert got["height"] == 700, got
assert got["scaleX"] == 327 / 700, "scaled by the area's width instead of its height"
assert got["scaleX"] == got["scaleY"], "non-uniform scale would distort the art"

# --- the invariants, over rectangles that are just inputs --------------------

for area, src in (({"x": 243.0, "y": 205.0, "width": 210.0, "height": 281.0}, (4122, 5514)),
                  ({"x": 244.0, "y": 205.0, "width": 209.0, "height": 275.0}, (3964, 5218)),
                  ({"x": 247.0, "y": 275.0, "width": 200.0, "height": 268.0}, (4134, 5540)),
                  ({"x": 10.0, "y": 20.0, "width": 100.0, "height": 130.0}, (1000, 1300))):
    p = T.placement(area, src)
    assert p["left"] == area["x"] + area["width"] / 2, (area, p)
    assert p["top"] == area["y"] + area["height"] / 2, (area, p)
    assert p["scaleX"] == p["scaleY"] == area["height"] / 700, (area, p)
    assert p["height"] == 700, (area, p)          # portrait source fits by height
    assert p["width"] == int(700 * src[0] / src[1]), (area, p)

# A landscape source fits by WIDTH instead. This is not hypothetical and these are
# not the formula written out twice: the hoodie's FRONT print area really is wider
# than it is tall, and the numbers below are what Tapstitch PERSISTED for the live
# hoodie on 16 Sep 2026, read back with get_template(). Same standard as the tee.
land = T.placement({"x": 251.0, "y": 275.0, "width": 205.0, "height": 160.0}, (4138, 3230))
assert land["left"] == 353.5, land       # 251 + 205/2
assert land["top"] == 355.0, land        # 275 + 160/2
assert land["width"] == 700, land        # major dimension fills the canvas
assert land["height"] == 546, land       # 546.4 truncated; NOT 546 by luck, see below
assert land["scaleX"] == land["scaleY"] == 0.29304029304029305, land
# 546.4 does not discriminate truncation from rounding, so pin a landscape shape
# where it does: 700 * 3/7 = 300.0 exactly is no help, but 4000x1234 gives 215.95.
edge = T.placement({"x": 0.0, "y": 0.0, "width": 700.0, "height": 215.0}, (4000, 1234))
assert edge["height"] == 215, "landscape minor dimension must truncate, not round"

# --- the aspect guard -------------------------------------------------------
# This is the only thing between a file/area mix-up and a silent misprint. The
# crew's own front and back rectangles differ by 1px wide and 6px tall, so a
# same-garment side swap is the most plausible mistake in a 135-row run, and the
# 1.0 canvas-pixel tolerance is exactly what distinguishes it. Loosening the
# tolerance "to stop it being fussy" is what these cases exist to catch.

CREW_BACK = {"x": 243.0, "y": 205.0, "width": 210.0, "height": 281.0}
CREW_FRONT = {"x": 244.0, "y": 205.0, "width": 209.0, "height": 275.0}

must_raise = [
    (CREW_BACK, (3964, 5218), "crew FRONT file on the crew BACK area"),
    (CREW_BACK, TEE_SRC, "tee file on the crew back area"),
    (TEE_AREA, (4122, 5514), "crew back file on the tee area"),
    (TEE_AREA, (1000, 1000), "square source"),
    (TEE_AREA, (5516, 4386), "landscape source on a portrait area"),
]
for area, src, why in must_raise:
    try:
        T.placement(area, src)
    except T.TapstitchError as e:
        assert str(src[0]) in str(e) and str(src[1]) in str(e), \
            f"the error should name the source size: {e}"
    else:
        raise AssertionError(f"placement() should have refused: {why}")

for area, src, why in ((TEE_AREA, TEE_SRC, "tee"),
                       (CREW_BACK, (4122, 5514), "crew back"),
                       (CREW_FRONT, (3964, 5218), "crew front, the tightest real pass")):
    T.placement(area, src)   # must not raise

# --- print_areas(), against the real response shape -------------------------

for name, sides in (("tee", {"front", "back"}),
                    ("crew", {"front", "back"}),
                    ("hoodie", {"front", "back"})):
    areas = T.print_areas(fixture(name))
    assert set(areas) == sides, (name, sorted(areas))
    assert "left_sleeve" not in areas, \
        f"{name}: a sleeve leaked in; the id filter should have excluded it"
    for side, rect in areas.items():
        assert set(rect) == {"x", "y", "width", "height"}, (name, side, rect)
        assert all(isinstance(v, float) for v in rect.values()), (name, side, rect)

# The `virtual` skip is a SEPARATE mechanism from the id filter, and the real
# fixtures do not reach it: every sleeve detail in them is named `<side>_middle` or
# `<side>_bottom`, so the id comparison rejects it first. Removing the virtual check
# entirely leaves all three fixtures' output identical. This synthetic case is the
# only input that reaches the branch, so without it the skip has zero coverage.
virtual_only = {"craftItemDto": {"customArea": [
    {"name": "front", "details": [{"id": "front_side_middle", "type": "virtual",
                                   "x": "1", "y": "2", "width": "3", "height": "4"}]},
    {"name": "back", "details": [{"id": "back_side_middle", "type": None,
                                  "x": "5", "y": "6", "width": "7", "height": "8"}]}]}}
only = T.print_areas(virtual_only)
assert set(only) == {"back"}, f"a virtual print area was treated as printable: {only}"

# End to end on the real shape: the fixture's own rectangle must still reproduce
# the geometry Tapstitch stored, which is what turns the hand-typed TEE_AREA
# above into a check against what they actually send.
assert T.placement(T.print_areas(fixture("tee"))["back"], TEE_SRC) == got

# --- mockups_back_first() ---------------------------------------------------
# Backs lead because the whole product is a back print; the front carries only a
# 6in logo. Colour ids here are arbitrary: the real ones are lineup, not contract.


def mockup(color_id, placement, name):
    return {"media": {"url": f"https://files.example/{name}.png",
                      "attributes": [{"payload": {"colorId": color_id,
                                                  "placement": placement}}]},
            "option": {"id": "Color", "valueIds": [str(color_id)]}}


mockups = [mockup(1, "FrontImage", "f1"), mockup(2, "FrontImage", "f2"),
           mockup(1, "BackEndImage", "b1"), mockup(2, "BackEndImage", "b2")]
ordered = T.mockups_back_first(mockups, lead_color_id=2)
sides = [m["media"]["attributes"][0]["payload"]["placement"] for m in ordered]
leads = [m["media"]["attributes"][0]["payload"]["colorId"] for m in ordered]
assert sides == ["BackEndImage", "BackEndImage", "FrontImage", "FrontImage"], sides
assert leads == [2, 1, 2, 1], leads
assert len(ordered) == len(mockups), "mockups were dropped"
assert {id(m) for m in ordered} == {id(m) for m in mockups}, "mockups were duplicated"

# --- back_for_front_mockups() ----------------------------------------------
# Pairing is by COLOUR, never by position. The fixture has to be able to FAIL
# under a positional rule or it proves nothing, and `mockups` above cannot: its
# order is f1, f2, b1, b2, for which pairing by colour, by half, and by position
# within each half all give the same answer. Both rules that shipped wrong on
# 16 Sep would pass it.
#
# So pair against the tee's REAL layout, which is interleaved, and against a
# reversed-backs layout. Under "split the gallery in half" the second one yields
# f1 -> b2, which is the class of error that put Gray's variants on the black
# garment's photo.
interleaved = [mockup(1, "FrontImage", "f1"), mockup(1, "BackEndImage", "b1"),
               mockup(2, "FrontImage", "f2"), mockup(2, "BackEndImage", "b2")]
reversed_backs = [mockup(1, "FrontImage", "f1"), mockup(2, "FrontImage", "f2"),
                  mockup(2, "BackEndImage", "b2"), mockup(1, "BackEndImage", "b1")]
for fixture_name, ms in (("posted back-first", mockups),
                         ("interleaved, as the live tee is", interleaved),
                         ("backs in a different order from the fronts", reversed_backs)):
    pairs = T.back_for_front_mockups({"mockups": ms})
    assert pairs == {"f1.png": "b1.png", "f2.png": "b2.png"}, (fixture_name, pairs)

# A colour with a front and no back must be ABSENT rather than paired with
# something else. scripts/tapstitch_variant_images.py relies on a back never being
# a key, which is what makes the rebind idempotent.
odd = T.back_for_front_mockups({"mockups": [mockup(1, "FrontImage", "f1"),
                                            mockup(2, "FrontImage", "f2"),
                                            mockup(1, "BackEndImage", "b1")]})
assert odd == {"f1.png": "b1.png"}, odd

# --- store_product_payload() ------------------------------------------------
# Three safety rules live in here and each is a one-token regression.

PREFILL = {
    "description": {"type": "HTML", "content": "WHOLESALE BLURB"},
    "sizeGuide": {"descriptionHtml": {"IMPERIAL": "<table>bare</table>",
                                      "METRIC": "<table>cm</table>",
                                      "BOTH": "<table>inch and cm</table>"}},
    "mockups": mockups,
    "options": [{"id": "Color", "name": "Color", "position": 1, "values": []}],
    "variants": [{"id": "A", "retailPrice": 1, "costPrice": {"store": 7}},
                 {"id": "B", "retailPrice": 2, "costPrice": {"store": 8}}],
    "costIncludesShipping": False,
    "shippingProfiles": [{"id": "-1", "selected": True},
                         {"id": "-2", "selected": False},
                         {"id": "999", "selected": False}],
    "visibility": {"publish": True},
}

body = T.store_product_payload(PREFILL, "Some Title", 1234,
                               description_html="OUR OWN COPY", lead_color_id=2)

# distribute False is the safety mechanism that lets the caller check a product
# before it is public. Flipping it would publish before anything is verified.
assert body["distribute"] is False, body["distribute"]

# Our copy is the WHOLE body. Tapstitch's blurb and every size table stay out:
# the 15 Sep tee shipped carrying that blurb and this is what prevents a repeat.
assert body["description"] == {"type": "HTML", "content": "OUR OWN COPY"}, body["description"]
for leaked in ("WHOLESALE BLURB", "bare", "cm", "inch and cm"):
    assert leaked not in body["description"]["content"], leaked

assert [v["retailPrice"] for v in body["variants"]] == [1234, 1234]
assert [v["costPrice"] for v in body["variants"]] == [{"store": 7}, {"store": 8}], \
    "every other variant key must survive untouched"
assert body["shippingProfileIds"] == ["-1"], body["shippingProfileIds"]
assert body["title"] == "Some Title"
assert [m["media"]["attributes"][0]["payload"]["placement"]
        for m in body["mockups"]][:2] == ["BackEndImage", "BackEndImage"]

# description_html is required, so no caller can fall back to Tapstitch's copy.
try:
    T.store_product_payload(PREFILL, "Some Title", 1234)
except TypeError:
    pass
else:
    raise AssertionError("description_html must be a required argument")

print("test_tapstitch_placement: all assertions passed")
