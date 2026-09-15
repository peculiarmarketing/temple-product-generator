"""Layout engine: computes layer positions per garment from temple art.

Everything anchors to the temple's INK (its actual drawn pixels), never to
the SVG frame, because catalog SVGs are square-padded and ink fractions
vary per drawing. Positions are computed in inches on the print area, then
converted to Printify's normalized coordinates (x, y = layer center as
fraction of area; scale = layer width as fraction of area width).

Profiles are registered in PROFILES; adding a layout is one function plus
one entry. Spacing constants come from spacing_defaults.json, overridable
per garment via the garment config's spacing_overrides.
"""

import io
import json
from pathlib import Path

import numpy as np
import resvg_py
from PIL import Image, ImageDraw, ImageFont

PROJECT_ROOT = Path(__file__).resolve().parent
FONT_PATH = PROJECT_ROOT / "fonts" / "Alata-Regular.ttf"
INK_SAMPLE_PX = 1024
TEMPLES_DIR = PROJECT_ROOT.parent.parent / "Temples"

# The pipeline's own per-temple files (manifest, status, facts fragment, trace
# check composite) live in this subfolder so the temple folder root holds only
# what Evan works with: the two traces, the three garment prints, the art
# close-up, and the source PNG.
WORKING_DIR_NAME = "Working files"


def working_dir(temple_name):
    return TEMPLES_DIR / temple_name / WORKING_DIR_NAME


def working_path(temple_name, filename, for_write=False):
    """Resolve one pipeline file for a temple.

    Writes always land in the working folder. Reads prefer it but fall back
    to the folder root, so a temple whose files have not been moved yet still
    resolves. A non-existent file resolves to the working-folder path, which
    keeps .exists() checks meaning 'no file anywhere'."""
    new = working_dir(temple_name) / filename
    if for_write:
        new.parent.mkdir(parents=True, exist_ok=True)
        return new
    if new.exists():
        return new
    old = TEMPLES_DIR / temple_name / filename
    return old if old.exists() else new


def temple_manifests():
    """{temple folder name: manifest path} for every temple that has one,
    from either location. The working folder wins when both exist."""
    found = {}
    for pattern, depth in ((f"*/{WORKING_DIR_NAME}/manifest.json", 2), ("*/manifest.json", 1)):
        for path in TEMPLES_DIR.glob(pattern):
            temple = path.parents[depth - 1].name
            found.setdefault(temple, path)
    return found


def load_spacing(garment_cfg):
    sp = json.loads((PROJECT_ROOT / "spacing_defaults.json").read_text())
    sp.pop("_comment", None)
    overrides = garment_cfg.get("spacing_overrides") or {}
    for k, v in overrides.items():
        if isinstance(v, dict):
            sp.setdefault(k, {}).update(v)
        else:
            sp[k] = v
    return sp


def rasterize_svg(svg_path, width_px):
    svg = Path(svg_path).read_text()
    return Image.open(io.BytesIO(bytes(resvg_py.svg_to_bytes(svg_string=svg, width=int(width_px))))).convert("RGBA")


def load_art(path, width_px=None):
    """Load SVG or PNG art as RGBA."""
    path = Path(path)
    if path.suffix.lower() == ".svg":
        return rasterize_svg(path, width_px or INK_SAMPLE_PX)
    return Image.open(path).convert("RGBA")


class TempleArt:
    """A temple image with its ink geometry measured."""

    def __init__(self, path):
        self.path = Path(path)
        self.image = load_art(path, INK_SAMPLE_PX)
        alpha = np.asarray(self.image.getchannel("A")) > 10
        ys, xs = np.where(alpha)
        w, h = self.image.size
        self.mask = alpha
        self.frame_aspect = h / w
        # ink bbox as fractions of the frame
        self.ink_l, self.ink_r = xs.min() / w, (xs.max() + 1) / w
        self.ink_t, self.ink_b = ys.min() / h, (ys.max() + 1) / h
        self.ink_w = self.ink_r - self.ink_l
        self.ink_h = self.ink_b - self.ink_t


def render_text(text, height_in, dpi, color=(0, 0, 0, 255)):
    """Render text in Alata, tight-cropped, scaled so ink height = height_in."""
    probe_size = 400
    font = ImageFont.truetype(str(FONT_PATH), probe_size)
    l, t, r, b = font.getbbox(text)
    img = Image.new("RGBA", (r - l + 40, b - t + 40), (0, 0, 0, 0))
    ImageDraw.Draw(img).text((20 - l, 20 - t), text, font=font, fill=color)
    img = img.crop(img.getchannel("A").getbbox())
    target_h = round(height_in * dpi)
    target_w = max(1, round(img.width * target_h / img.height))
    return img.resize((target_w, target_h), Image.LANCZOS)


def find_text_override(temple_dir, color):
    """Evan's manual location-text file, if present: '*location text*{color}*.svg/.png'.
    Files carrying '(auto)' are the generator's own renders, never overrides."""
    temple_dir = Path(temple_dir)
    for ext in ("svg", "png"):
        hits = sorted(temple_dir.glob(f"*location text*{color}*.{ext}")) + \
               sorted(temple_dir.glob(f"*Location Text*{color.title()}*.{ext}"))
        hits = [h for h in hits if "(auto)" not in h.name]
        if hits:
            return hits[0]
    return None


def _layer(key, cx_in, cy_in, w_in, h_in, area_w_in, area_h_in):
    return {
        "key": key,
        "cx_in": cx_in, "cy_in": cy_in, "w_in": w_in, "h_in": h_in,
        "top_in": cy_in - h_in / 2, "bottom_in": cy_in + h_in / 2,
        "x": cx_in / area_w_in, "y": cy_in / area_h_in, "scale": w_in / area_w_in,
    }


def _place_temple(temple, sp, area_w_in, area_h_in, stack_below_in):
    """Ink top at top margin, ink centered horizontally, target ink width,
    shrink to fit if the full stack would breach the bottom margin."""
    frame_w_in = sp["temple_target_ink_width_in"] / temple.ink_w
    frame_h_in = frame_w_in * temple.frame_aspect
    ink_h_in = frame_h_in * temple.ink_h
    max_ink_h_in = area_h_in - sp["top_margin_in"] - sp["bottom_margin_in"] - stack_below_in
    if ink_h_in > max_ink_h_in:
        factor = max_ink_h_in / ink_h_in
        frame_w_in *= factor
        frame_h_in *= factor
        ink_h_in = max_ink_h_in
    frame_top_in = sp["top_margin_in"] - temple.ink_t * frame_h_in
    ink_cx_frac = (temple.ink_l + temple.ink_r) / 2
    frame_cx_in = area_w_in / 2 - (ink_cx_frac - 0.5) * frame_w_in
    layer = _layer("temple", frame_cx_in, frame_top_in + frame_h_in / 2,
                   frame_w_in, frame_h_in, area_w_in, area_h_in)
    layer["ink_bottom_in"] = sp["top_margin_in"] + ink_h_in
    layer["ink_width_in"] = frame_w_in * temple.ink_w
    return layer


def _sky_logo(temple, temple_layer, sp, logo_aspect, area_w_in, area_h_in, override=None):
    """Place the logo in open sky near the temple, preferring the sides.
    Left and right are tried at the full gap, compressing down to the
    minimum gap when the top margin forces it; center is used only when
    neither side can hold the minimum gap above the ink in its column
    band (Evan's rule, 19 Aug 2026). The logo can never overlap linework:
    its bottom always sits at least the minimum gap above the band's
    first ink. A manifest override
    {"dated_logo": {"corner": "left"|"center"|"right", "gap_above_ink_in": x}}
    forces the choice and gap unclamped."""
    d = sp["dated"]
    override = override or {}
    logo_w_in = sp["logo_width_in"]
    logo_h_in = logo_w_in * logo_aspect
    gap = override.get("gap_above_ink_in", d["logo_gap_above_ink_in"])
    min_gap = d.get("logo_min_gap_above_ink_in", gap)
    pad_in = 0.25
    mh, mw = temple.mask.shape
    px_x = mw / temple_layer["w_in"]
    px_y = mh / temple_layer["h_in"]

    def band_first_ink(xfrac):
        cx_in = area_w_in * xfrac
        l_in = cx_in - logo_w_in / 2 - pad_in - (temple_layer["cx_in"] - temple_layer["w_in"] / 2)
        r_in = l_in + logo_w_in + 2 * pad_in
        l, r = max(0, int(l_in * px_x)), min(mw, int(r_in * px_x))
        band = temple.mask[:, l:r] if r > l else temple.mask[:, 0:1]
        rows = np.where(band.any(axis=1))[0]
        first_ink_row = rows[0] if len(rows) else band.shape[0]
        return cx_in, temple_layer["top_in"] + first_ink_row / px_y

    def place(xfrac, use_gap):
        cx_in, first_ink_in = band_first_ink(xfrac)
        bottom_in = first_ink_in - use_gap
        return cx_in, bottom_in - logo_h_in, bottom_in

    def best_fit(xfrac):
        """Largest gap in [min_gap, gap] whose logo top clears the top
        margin, or None if even min_gap cannot."""
        _, first_ink_in = band_first_ink(xfrac)
        achievable = first_ink_in - d["logo_min_top_in"] - logo_h_in
        if achievable < min_gap:
            return None
        return place(xfrac, min(gap, achievable))

    positions = {"left": d["logo_corner_x_fraction"], "center": 0.5,
                 "right": 1 - d["logo_corner_x_fraction"]}
    if override.get("corner") in positions:
        side = override["corner"]
        cx_in, top_in, bottom_in = place(positions[side], gap)
        # honor the explicit choice; never clamp downward into ink
    else:
        fitting = {s: r for s in ("left", "right")
                   if (r := best_fit(positions[s])) is not None}
        if fitting:
            side = max(fitting, key=lambda s: fitting[s][1])  # lowest fit = nearest temple
            cx_in, top_in, bottom_in = fitting[side]
        else:
            side = "center"
            result = best_fit(0.5)
            if result is None:
                # even center cannot hold min_gap under the top margin;
                # keep min_gap and let the logo ride high instead
                result = place(0.5, min_gap)
            cx_in, top_in, bottom_in = result
    return _layer("logo", cx_in, top_in + logo_h_in / 2, logo_w_in, logo_h_in, area_w_in, area_h_in), side


def back_stack(temple, garment_cfg, sp, logo_aspect, text_aspect):
    """Base design: temple, location text, logo, all centered, top-anchored."""
    area = garment_cfg["print_area"]
    area_w_in = area["width_px"] / area["dpi"]
    area_h_in = area["height_px"] / area["dpi"]
    text_h = sp["location_text_height_in"]
    logo_h = sp["logo_width_in"] * logo_aspect
    stack_below = sp["gap_ink_to_text_in"] + text_h + sp["gap_text_to_logo_in"] + logo_h

    temple_layer = _place_temple(temple, sp, area_w_in, area_h_in, stack_below)
    y = temple_layer["ink_bottom_in"] + sp["gap_ink_to_text_in"]
    text_layer = _layer("location_text", area_w_in / 2, y + text_h / 2,
                        text_h * text_aspect, text_h, area_w_in, area_h_in)
    y = text_layer["bottom_in"] + sp["gap_text_to_logo_in"]
    logo_layer = _layer("logo", area_w_in / 2, y + logo_h / 2,
                        sp["logo_width_in"], logo_h, area_w_in, area_h_in)
    return [temple_layer, text_layer, logo_layer]


def back_stack_dated(temple, garment_cfg, sp, logo_aspect, text_aspect, logo_override=None):
    """With Date design: temple, small location text, divider, date zone,
    logo floated in open sky (left, center, or right). The date zone is
    reserved space; the personalization text layer is added by hand in
    Printify."""
    area = garment_cfg["print_area"]
    area_w_in = area["width_px"] / area["dpi"]
    area_h_in = area["height_px"] / area["dpi"]
    d = sp["dated"]
    text_h = d["location_text_height_in"]
    stack_below = (sp["gap_ink_to_text_in"] + text_h + d["gap_text_to_divider_in"] +
                   d["divider_height_in"] + d["gap_divider_to_date_in"] + d["date_zone_height_in"])

    temple_layer = _place_temple(temple, sp, area_w_in, area_h_in, stack_below)
    y = temple_layer["ink_bottom_in"] + sp["gap_ink_to_text_in"]
    text_layer = _layer("location_text", area_w_in / 2, y + text_h / 2,
                        text_h * text_aspect, text_h, area_w_in, area_h_in)
    y = text_layer["bottom_in"] + d["gap_text_to_divider_in"]
    divider = _layer("divider", area_w_in / 2, y + d["divider_height_in"] / 2,
                     d["divider_width_in"], d["divider_height_in"], area_w_in, area_h_in)
    y = divider["bottom_in"] + d["gap_divider_to_date_in"]
    date_zone = _layer("date_zone", area_w_in / 2, y + d["date_zone_height_in"] / 2,
                       d["date_zone_width_in"], d["date_zone_height_in"], area_w_in, area_h_in)
    logo_layer, side = _sky_logo(temple, temple_layer, sp, logo_aspect, area_w_in, area_h_in,
                                 override=logo_override)
    logo_layer["corner"] = side
    return [temple_layer, text_layer, divider, date_zone, logo_layer]


def back_temple_text(temple, garment_cfg, sp, logo_aspect, text_aspect):
    """Tapstitch back design: temple and location text only, centered and
    top-anchored. The logo left the back for the front print area when the
    catalog moved off Printify (Evan, 14 Sep 2026), where a second print
    location cost $4.90 and killed the margin. logo_aspect is unused here
    and kept only so every profile takes the same arguments."""
    area = garment_cfg["print_area"]
    area_w_in = area["width_px"] / area["dpi"]
    area_h_in = area["height_px"] / area["dpi"]
    text_h = sp["location_text_height_in"]
    stack_below = sp["gap_ink_to_text_in"] + text_h

    temple_layer = _place_temple(temple, sp, area_w_in, area_h_in, stack_below)
    y = temple_layer["ink_bottom_in"] + sp["gap_ink_to_text_in"]
    text_layer = _layer("location_text", area_w_in / 2, y + text_h / 2,
                        text_h * text_aspect, text_h, area_w_in, area_h_in)
    layers = [temple_layer, text_layer]

    # Losing the logo exposed how much top-anchoring varies between temples. A
    # tall narrow temple fills the area; a wide short one hits its target width
    # early and leaves the rest of the canvas empty (measured 14 Sep 2026 across
    # 40 temples: 2.5in to 8.6in of empty canvas below the text). Centring the
    # block instead makes every temple sit at the same height on the garment.
    # Top-anchoring stays the default because it is what the live catalogue used.
    if sp.get("vertical_anchor") == "center":
        block_top = sp["top_margin_in"]          # _place_temple puts ink top here
        block_bottom = text_layer["bottom_in"]
        shift = (area_h_in - (block_bottom - block_top)) / 2 - block_top
        for lyr in layers:
            for key in ("cy_in", "top_in", "bottom_in", "ink_bottom_in"):
                if key in lyr:
                    lyr[key] += shift
            lyr["y"] = lyr["cy_in"] / area_h_in
    return layers


PROFILES = {"back_stack": back_stack, "back_stack_dated": back_stack_dated,
            "back_temple_text": back_temple_text}


def location_text_height(garment_cfg):
    sp = load_spacing(garment_cfg)
    return sp["dated"]["location_text_height_in"] if "dated" in garment_cfg["layout_profile"] \
        else sp["location_text_height_in"]


def render_divider(garment_cfg, color=(0, 0, 0, 255), dpi=300):
    """Solid rule between location and date on dated products. Rendered rather
    than reusing the shop's 1.png/2.png assets so length changes keep the
    approved 0.04in thickness."""
    sp = load_spacing(garment_cfg)["dated"]
    w = max(1, round(sp["divider_width_in"] * dpi))
    h = max(2, round(sp["divider_height_in"] * dpi))
    return Image.new("RGBA", (w, h), color)


def render_art_card(svg_path, size=2048, coverage=0.86):
    """Product-gallery close-up: the black line art centered on a clean white
    square. Centered by ink, not frame, so square-padded and trimmed SVGs
    come out identical."""
    img = rasterize_svg(svg_path, size + 512)
    ink = img.crop(img.getchannel("A").getbbox())
    target = round(size * coverage)
    scale = target / max(ink.size)
    ink = ink.resize((max(1, round(ink.width * scale)), max(1, round(ink.height * scale))), Image.LANCZOS)
    card = Image.new("RGB", (size, size), (255, 255, 255))
    card.paste(ink, ((size - ink.width) // 2, (size - ink.height) // 2), ink)
    return card


def compute_stack(temple_art, garment_cfg, text_img, logo_aspect, logo_override=None):
    """Main entry: returns the layer list for one temple on one garment.
    text_img is the location-text image (auto-rendered or Evan's override);
    only its aspect ratio matters here. logo_override is the manifest's
    optional dated_logo dict."""
    sp = load_spacing(garment_cfg)
    profile = PROFILES[garment_cfg["layout_profile"]]
    text_aspect = text_img.width / text_img.height
    if "dated" in garment_cfg["layout_profile"]:
        return profile(temple_art, garment_cfg, sp, logo_aspect, text_aspect, logo_override=logo_override)
    return profile(temple_art, garment_cfg, sp, logo_aspect, text_aspect)
