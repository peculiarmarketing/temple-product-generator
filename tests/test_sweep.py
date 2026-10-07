"""Offline tests for scripts/sweep.py. No network, no Temples folder.

Run: ./.venv.nosync/bin/python tests/test_sweep.py

What is pinned: the tags a new product gets match the four-tag scheme every live
product carries (checked against all 45 live tees on 7 Oct 2026), and scan sorts
a folder into the right bucket, including the one the ledger cannot see: a temple
whose products went live but whose later sweep steps never finished.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import sweep as S

# --- tags, as read off the live store 7 Oct 2026 ----------------------------
assert S.expected_tags("Boise", "tee", "BOISE, IDAHO") == \
    ["country:usa", "garment:tee", "state:idaho", "temple:boise"]
assert S.expected_tags("Albuquerque", "crew", "ALBUQUERQUE, NEW MEXICO") == \
    ["country:usa", "garment:crew", "state:new-mexico", "temple:albuquerque"]
# the physical city decides the state, not the temple's name
assert S.expected_tags("Washington DC", "tee", "KENSINGTON, MARYLAND") == \
    ["country:usa", "garment:tee", "state:maryland", "temple:washington-d-c"]
# outside the US: country only
assert S.expected_tags("Rome", "tee", "ROME, ITALY") == \
    ["country:italy", "garment:tee", "temple:rome"]
assert S.expected_tags("Mexico City", "hoodie", "MEXICO CITY, MEXICO") == \
    ["country:mexico", "garment:hoodie", "temple:mexico-city"]
# folder markers and punctuation never reach the tag
assert S.expected_tags("Lehi*", "tee", "LEHI, UTAH")[-1] == "temple:lehi"
assert S.expected_tags("St. George", "tee", "ST. GEORGE, UTAH")[-1] == "temple:st-george"
assert S.expected_tags("Ogden (original)", "tee", "OGDEN, UTAH")[-1] == "temple:ogden-original"
# a two-word state that is also a country-sounding name stays a state
assert "state:new-york" in S.expected_tags("Manhattan", "tee", "NEW YORK, NEW YORK")

# --- scan buckets -----------------------------------------------------------
G = ["tee", "crew", "hoodie"]
live = [{"temple": "Logan", "garment": g, "state": "live"} for g in G]

assert S.classify("Logan", live, G, True, True, True) == ("live", [])
# published before the sweep existed: no state record, so live
assert S.classify("Logan", live, G, True, True, True, None)[0] == "live"
# published by a sweep that stopped before verify: still has work
assert S.classify("Logan", live, G, True, True, True,
                  {"started_at": "2026-10-08T01:00:00"})[0] == "finishing"
assert S.classify("Logan", live, G, True, True, True,
                  {"started_at": "x", "verified_at": "y"})[0] == "live"

# a brand-new folder holding only the design PNG
assert S.classify("St. Paul", [], G, True, False, False) == \
    ("needs-research", ["location", "facts"])
assert S.classify("St. Paul", [], G, True, True, False) == ("needs-research", ["facts"])
assert S.classify("St. Paul", [], G, True, True, True) == ("ready", [])
status, missing = S.classify("St. Paul", [], G, False, True, True)
assert status == "no-art" and "St. Paul.png" in missing[0]

# half-published (one garment live, two not) is ready: run resumes the rest
half = [{"temple": "Cody", "garment": "tee", "state": "live"},
        {"temple": "Cody", "garment": "crew", "state": "product-created"}]
assert S.classify("Cody", half, G, True, True, True) == ("ready", [])

# every step runs in this order, publish before anything that needs a handle
assert S.STEPS.index("publish") < min(S.STEPS.index(s) for s in ("tags", "gallery", "drawing"))
assert S.STEPS[0] == "build"

# --- Temple Art File option order: Salt Lake first, then A to Z -------------
assert S.art_file_order(["Salt Lake", "Albuquerque", "Rome", "Billings"]) == \
    ["Salt Lake", "Albuquerque", "Billings", "Rome"]
assert S.art_file_order(["Salt Lake", "Provo City Center", "Provo", "st. paul"]) == \
    ["Salt Lake", "Provo", "Provo City Center", "st. paul"]

# --- verify against a real live product --------------------------------------
# The Boise tee as the store holds it (fixture read 7 Oct 2026). A finished
# product must verify clean, and each kind of damage must be named.
import copy  # noqa: E402
import json  # noqa: E402

FIX = json.loads((Path(__file__).parent / "fixtures" / "sweep-boise-tee.json").read_text())


class FakeClient:
    def __init__(self, product):
        self.product = product

    def gql(self, query, variables=None):
        return {"productByHandle": self.product}


S.generate.title_for = lambda folder, g, cfg=None: "Essential Heavyweight Temple Tee (Boise)"
S.generate.load_manifest = lambda folder: {"location_line": "BOISE, IDAHO",
                                           "place_tokens": {"default": "Boise"}}
ROW = {"state": "live", "shopify_handle": "essential-heavyweight-temple-tee-boise"}


def check(product):
    return S.verify_product(FakeClient(product), "Boise", "tee", ROW)


assert check(FIX["product"]) == [], check(FIX["product"])

broken = copy.deepcopy(FIX["product"])
broken["media"]["nodes"].insert(0, broken["media"]["nodes"].pop(1))   # flat lay in slot 1
probs = check(broken)
assert any("slot 1" in p for p in probs) and any("standard order" in p for p in probs), probs

broken = copy.deepcopy(FIX["product"])
broken["tags"] = ["garment:tee"]
assert any("missing tags" in p for p in check(broken))

broken = copy.deepcopy(FIX["product"])
broken["options"][0]["values"][1] = "Wine Red"                        # Tapstitch's name
assert any("Tapstitch colour names" in p for p in check(broken))

broken = copy.deepcopy(FIX["product"])
broken["variants"]["nodes"][0]["media"]["nodes"] = [{"id": broken["media"]["nodes"][1]["id"]}]
assert any("not bound to its on-model photo" in p for p in check(broken))

broken = copy.deepcopy(FIX["product"])
broken["descriptionHtml"] = "<section class=\"product-details\">...</section>"
assert any("temple facts" in p for p in check(broken))

assert any("not live" in p for p in
           S.verify_product(FakeClient(FIX["product"]), "Boise", "tee", {"state": "product-created"}))

print("test_sweep: all passed")
