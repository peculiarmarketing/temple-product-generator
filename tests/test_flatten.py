"""Offline tests for the Tapstitch flattener. No network.

Run: ./.venv.nosync/bin/python tests/test_flatten.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
from PIL import Image

import flatten
import layout
from generate import load_garment_config, load_manifest

TEE = load_garment_config("tee")
AREA = TEE["print_area"]

# --- the halo trap -----------------------------------------------------------
# Rasterised PNGs carry RGB(0,0,0) under fully transparent pixels. Tapstitch's
# previewer resamples without premultiplying alpha and smears that hidden black
# into grey halos around white ink. Measured 27 Aug 2026.

img = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
img.putpixel((4, 4), (255, 255, 255, 255))
img.putpixel((3, 4), (255, 255, 255, 128))   # antialiased edge
before = np.array(img)
assert (before[0, 0][:3] == 0).all(), "fixture should start with black under transparency"

after = np.array(flatten.matte(img, (255, 255, 255)))
assert (after[:, :, :3] == 255).all(), "matte must set EVERY pixel's colour to the ink colour"
assert (after[:, :, 3] == before[:, :, 3]).all(), "matte must not touch alpha"

# Black art is already matte-safe, so the pass is a no-op on it.
black = Image.new("RGBA", (4, 4), (0, 0, 0, 0))
black.putpixel((1, 1), (0, 0, 0, 255))
assert np.array_equal(np.array(flatten.matte(black, (0, 0, 0))), np.array(black))

# --- a real build ------------------------------------------------------------
manifest = load_manifest("Salt Lake")
built = flatten.build_back("Salt Lake", manifest, TEE, "white")
out, geo, raw = built["image"], built["geometry"], built["raw"]

assert out.size == (AREA["width_px"], AREA["height_px"]), \
    "canvas must match the print area exactly, or 'centre at full size' misaligns the edges"
assert out.mode == "RGBA"

alpha = np.asarray(out.getchannel("A"))
assert (alpha < 255).any(), "a print file with no transparency would print as a solid block"
assert (alpha > 10).any(), "the file has no ink in it"

hidden = np.array(out)[alpha == 0][:, :3]
assert (hidden == 255).all(), "white build still carries dark pixels under transparency"

# --- the back design carries no logo ----------------------------------------
assert set(geo) == {"temple", "location_text"}, \
    f"the Tapstitch back is temple plus location text only, got {sorted(geo)}"
assert TEE["layout_profile"] == "back_temple_text"

# --- the composite agrees with the layout math ------------------------------
# The flattener must place ink where compute_stack said it would, not merely
# somewhere plausible. Check the topmost ink row against the computed top margin.
dpi = AREA["dpi"]
ys, xs = np.where(alpha > 10)
bottom_in = (ys.max() + 1) / dpi
assert abs(bottom_in - geo["location_text"]["bottom_in"]) < 0.05, \
    f"ink ends at {bottom_in:.3f}in, layout said {geo['location_text']['bottom_in']}in"

# Top-anchored: the first ink row sits at the top margin.
top_cfg = dict(TEE, spacing_overrides={**(TEE.get("spacing_overrides") or {}),
                                       "vertical_anchor": "top"})
r_top = flatten.build_back("Salt Lake", manifest, top_cfg, "white")
sp_top = layout.load_spacing(top_cfg)
ys_top = np.where(np.asarray(r_top["image"].getchannel("A")) > 10)[0]
assert abs(ys_top.min() / dpi - sp_top["top_margin_in"]) < 0.05, \
    f"top-anchored ink starts at {ys_top.min() / dpi:.3f}in, " \
    f"layout said {sp_top['top_margin_in']}in"
assert abs((ys_top.max() + 1) / dpi
           - r_top["geometry"]["location_text"]["bottom_in"]) < 0.05

# Centred: equal space above and below, and the block is the same height either way.
ctr_cfg = dict(TEE, spacing_overrides={**(TEE.get("spacing_overrides") or {}),
                                       "vertical_anchor": "center"})
r_ctr = flatten.build_back("Salt Lake", manifest, ctr_cfg, "white")
ys_ctr = np.where(np.asarray(r_ctr["image"].getchannel("A")) > 10)[0]
above, below = ys_ctr.min(), AREA["height_px"] - 1 - ys_ctr.max()
assert abs(above - below) < 0.1 * dpi, \
    f"centred design is not balanced: {above/dpi:.2f}in above, {below/dpi:.2f}in below"
assert abs((ys_ctr.max() - ys_ctr.min()) - (ys_top.max() - ys_top.min())) < 0.05 * dpi, \
    "centring must move the block, not resize it"

# The location line is a fixed height on every temple: it is the temple art that
# varies, never the type. Regression guard for Evan's 14 Sep 2026 rule.
heights = set()
for other in ("Logan", "Monticello", "Bountiful"):
    g = flatten.build_back(other, load_manifest(other), TEE, "white")["geometry"]
    heights.add(round(g["location_text"]["h_in"], 4))
heights.add(round(geo["location_text"]["h_in"], 4))
assert len(heights) == 1, f"location line height varies between temples: {heights}"

# --- validate() reports rather than raises -----------------------------------
assert flatten.validate(out, TEE, built["sources"], "white", pre_matte=raw) == []

wrong_size = out.resize((100, 100))
probs = flatten.validate(wrong_size, TEE, built["sources"], "white")
assert any("canvas is" in p for p in probs), probs

solid = Image.new("RGBA", (AREA["width_px"], AREA["height_px"]), (0, 0, 0, 255))
probs = flatten.validate(solid, TEE, {}, "black")
assert any("no transparency" in p for p in probs), probs

empty = Image.new("RGBA", (AREA["width_px"], AREA["height_px"]), (0, 0, 0, 0))
assert any("no ink at all" in p for p in flatten.validate(empty, TEE, {}, "black"))

# ink hard against the edge
edgy = Image.new("RGBA", (AREA["width_px"], AREA["height_px"]), (0, 0, 0, 0))
edgy.putpixel((0, 0), (0, 0, 0, 255))
edgy.putpixel((500, 500), (0, 0, 0, 255))
probs = flatten.validate(edgy, TEE, {}, "black")
assert sum("safe margin" in p for p in probs) >= 2, probs

# a low-resolution PNG source stretched across the print area
probs = flatten.validate(out, TEE, {"temple": (2048, 14.98, ".png")}, "white")
assert any("effective DPI" in p for p in probs), probs
# vector sources are exempt: they rasterise straight to the target size
assert flatten.validate(out, TEE, {"temple": (2048, 14.98, ".svg")}, "white") == []

# multi-toned art would be destroyed by the matte pass, so it is flagged
multi = Image.new("RGBA", (AREA["width_px"], AREA["height_px"]), (0, 0, 0, 0))
multi.putpixel((10, 10), (255, 0, 0, 255))
multi.putpixel((11, 10), (0, 0, 255, 255))
probs = flatten.validate(out, TEE, {}, "white", pre_matte=multi)
assert any("not single-ink" in p for p in probs), probs

# --- the front logo file -----------------------------------------------------
front = flatten.build_front_logo(TEE, "white")
fa = TEE["front_print_area"]
assert front["image"].size == (fa["width_px"], fa["height_px"])
assert flatten.validate(front["image"], TEE, front["sources"], "white",
                        area_key="front_print_area", pre_matte=front["raw"]) == []
# The logo sits near the top of the chest, not centred in the canvas: centring
# it in the print area would drop it to mid-chest.
fdpi = fa["dpi"]
fys = np.where(np.asarray(front["image"].getchannel("A")) > 10)[0]
assert abs(fys.min() / fdpi - fa["logo_top_margin_in"]) < 0.05, \
    f"logo top at {fys.min() / fdpi:.3f}in, config says {fa['logo_top_margin_in']}in"

# Centring is opt-in. With no override the profile still anchors to the top,
# which is what leaves the retiring Printify layouts exactly as they were.
bare = dict(TEE, spacing_overrides={})
assert layout.load_spacing(bare).get("vertical_anchor") in (None, "top")
bare_ys = np.where(np.asarray(
    flatten.build_back("Salt Lake", manifest, bare, "white")["image"]
    .getchannel("A")) > 10)[0]
assert abs(bare_ys.min() / dpi - layout.load_spacing(bare)["top_margin_in"]) < 0.05

# --- output paths are marked (auto) ------------------------------------------
# layout.find_text_override() skips '(auto)' files, so the generator can never
# mistake its own output for one of Evan's hand-made override files.
back_path = flatten.back_file_path("Salt Lake", "tee", "black")
assert "(auto)" in back_path.name and back_path.parent.name == "Salt Lake"

# --- write containment -------------------------------------------------------
# temple_name reaches back_file_path() from a --temple command line argument and
# becomes a write path inside Evan's iCloud Drive. The project constraint is
# absolute: write nothing outside Claude Projects and the sibling Temples folders.
for escape in ("../../escape", "..", "Logan/../../escape", "/tmp/escape"):
    try:
        flatten.back_file_path(escape, "tee", "black")
        raise AssertionError(f"traversal not blocked: {escape!r}")
    except SystemExit:
        pass
# The real temple folder names carry dots, parentheses and ref-finder stars, and
# every one of them must still be allowed through.
for real in ("St. George", "Ogden (original)", "Lehi*", "Heber Valley*", "Salt Lake"):
    path = flatten.back_file_path(real, "tee", "black")
    assert path.parent.name == real, path

# The front logo path takes garment_id from --garments and needs the same guard.
# Contained to front-logo/ rather than its parent, because "a/../../b" resolves
# back up into artifacts/tapstitch/ and would pass a looser check.
assert flatten.front_file_path("tee", "black").parent.name == "front-logo"
for escape in ("../../escape", "a/../../b", "/tmp/escape"):
    try:
        flatten.front_file_path(escape, "black")
        raise AssertionError(f"traversal not blocked: {escape!r}")
    except SystemExit:
        pass
assert layout.find_text_override(back_path.parent, "black") is None or \
    "(auto)" not in layout.find_text_override(back_path.parent, "black").name

print("all tests passed")
