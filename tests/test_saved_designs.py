"""Offline tests for publishing hand-saved Tapstitch designs. No network.

Run: ./.venv.nosync/bin/python tests/test_saved_designs.py

Pinned: the colour filter keeps variants, option values and mockups in step;
a front-only design leads with its front and drops the blank backs; a re-save
sends the template's own design unchanged with only the colours swapped; and
every entry in config/saved_designs.json is complete and self-consistent. The
records are synthetic, shaped like the live prefill and template.
"""

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import tapstitch_api as T

spec = importlib.util.spec_from_file_location("psd", ROOT / "scripts" / "publish_saved_design.py")
P = importlib.util.module_from_spec(spec)
spec.loader.exec_module(P)


def mockup(colour, placement):
    return {"media": {"url": f"{colour}-{placement}",
                      "attributes": [{"payload": {"colorId": colour, "placement": placement}}]}}


def variant(colour, size):
    return {"selectedOptions": [{"id": "Color", "valueId": str(colour)},
                                {"id": "Size", "valueId": size}], "retailPrice": 1}


PREFILL = {
    "options": [{"id": "Color", "name": "Color",
                 "values": [{"id": "1", "name": "Black"}, {"id": "2", "name": "Pink"},
                            {"id": "3", "name": "Coffee"}]},
                {"id": "Size", "name": "Size", "values": [{"id": "S", "name": "S"}]}],
    "variants": [variant(c, "S") for c in (1, 2, 3)],
    "mockups": [mockup(c, p) for c in (1, 2, 3) for p in ("FrontImage", "BackEndImage")],
    "costIncludesShipping": False,
    "shippingProfiles": [{"id": "-1", "selected": True}],
    "visibility": "VISIBLE",
}

# --- filter_colours() ---------------------------------------------------------
f = T.filter_colours(PREFILL, [3, 1])
assert [v["name"] for v in f["options"][0]["values"]] == ["Black", "Coffee"]
assert f["options"][1] == PREFILL["options"][1], "the Size option is untouched"
assert len(f["variants"]) == 2 and len(f["mockups"]) == 4
assert len(PREFILL["variants"]) == 3, "the prefill itself is not modified"
try:
    T.filter_colours(PREFILL, [1, 9])
except T.TapstitchError:
    pass
else:
    raise AssertionError("a colour the template lacks must raise, not vanish")

# --- order_mockups() ----------------------------------------------------------
front = T.order_mockups(f["mockups"], "front", 3, "back")
assert [(m["media"]["url"]) for m in front] == ["3-FrontImage", "1-FrontImage"]
back = T.order_mockups(f["mockups"], "back", 1, None)
assert [m["media"]["url"] for m in back][:2] == ["1-BackEndImage", "3-BackEndImage"]
assert len(back) == 4

# --- resave_body() ------------------------------------------------------------
CONFIG = json.dumps([{"piece": "front", "embs": [], "objects": [{"src": "x.png", "left": 1}],
                      "canvasSize": {"width": 700, "height": 700}}])
TEMPLATE = {"templateId": "9", "productId": "8", "colorCode": "1", "config": CONFIG,
            "printType": 13, "specialProcessTags": ["DTF"], "designTools": "2d-layers",
            "printingPreferenceType": "original", "resourceCode": -1, "isUsedHd": False,
            "branding": {"innerNeckLabelCommitId": "0", "hangtagCommitId": "0"}}
body = T.resave_body(TEMPLATE, [1, 2])
assert body["colorCode"] == "1,2"
assert body["config"] == CONFIG, "the design is sent back byte for byte"
assert body["printType"] == 13, "an editor-made design keeps its own print type"
assert json.loads(body["mockupConfig"]) == [{"piece": "front",
                                             "objects": [{"src": "x.png", "left": 1}],
                                             "canvasSize": {"width": 700, "height": 700}}]

# --- payload_for(): price, colours and gallery reach the create call ---------
cfg = P.load_config()
p = dict(cfg["products"]["2"], colours=[1, 3], lead_colour=1)
P.description = lambda c, q: "<p>copy</p>"
pl = P.payload_for(cfg, p, PREFILL)
assert {v["retailPrice"] for v in pl["variants"]} == {6499}
assert pl["distribute"] is False and pl["tags"] == []
assert all(m["media"]["attributes"][0]["payload"]["placement"] == "FrontImage"
           for m in pl["mockups"])

# --- config/saved_designs.json ------------------------------------------------
NEEDED = {"design", "approved", "template_id", "garment", "title", "handle", "price_usd",
          "product_type", "colours", "lead_colour", "lead_side", "renames", "tags",
          "details", "intro"}
handles = set()
for key, e in cfg["products"].items():
    assert NEEDED <= set(e), f"#{key} missing {NEEDED - set(e)}"
    assert e["lead_colour"] in e["colours"], f"#{key} lead colour not offered"
    assert e["lead_side"] in ("front", "back"), key
    assert e["handle"] not in handles, f"#{key} duplicate handle"
    handles.add(e["handle"])
    assert not any(t.split(":")[0] in ("temple", "garment", "country", "state") for t in e["tags"]), \
        f"#{key}: the temple collections and the homepage marquee are smart collections on those tags"
    assert "—" not in e["title"], f"#{key} title has an em dash"

print("test_saved_designs: all assertions passed")
