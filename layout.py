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
    """Evan's manual location-text file, if present: '*location text*{color}*.svg/.png'."""
    temple_dir = Path(temple_dir)
    for ext in ("svg", "png"):
        hits = sorted(temple_dir.glob(f"*location text*{color}*.{ext}")) + \
               sorted(temple_dir.glob(f"*Location Text*{color.title()}*.{ext}"))
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


def _corner_logo(temple, temple_layer, sp, logo_aspect, area_w_in, area_h_in):
    """Pick the emptier top corner near the temple, per Evan: not flush to
    any edge, close to the linework."""
    d = sp["dated"]
    logo_w_in = sp["logo_width_in"]
    logo_h_in = logo_w_in * logo_aspect
    results = {}
    for side, xfrac in (("left", d["logo_corner_x_fraction"]), ("right", 1 - d["logo_corner_x_fraction"])):
        cx_in = area_w_in * xfrac
        # column band of the logo footprint plus padding, in temple-mask pixels
        mask_w = temple.mask.shape[1]
        px_per_in = mask_w / temple_layer["w_in"]
        band_l_in = cx_in - logo_w_in / 2 - 0.25 - (temple_layer["cx_in"] - temple_layer["w_in"] / 2)
        band_r_in = band_l_in + logo_w_in + 0.5
        l = max(0, int(band_l_in * px_per_in))
        r = min(mask_w, int(band_r_in * px_per_in))
        band = temple.mask[:, l:r] if r > l else temple.mask[:, 0:1]
        rows = np.where(band.any(axis=1))[0]
        first_ink_row = rows[0] if len(rows) else band.shape[0]
        first_ink_in = temple_layer["top_in"] + first_ink_row / (temple.mask.shape[0] / temple_layer["h_in"])
        ink_amount = band.sum()
        results[side] = (first_ink_in, ink_amount, cx_in)
    side = min(results, key=lambda s: results[s][1])
    first_ink_in, _, cx_in = results[side]
    bottom_in = first_ink_in - d["logo_gap_above_ink_in"]
    top_in = max(d["logo_min_top_in"], bottom_in - logo_h_in)
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


def back_stack_dated(temple, garment_cfg, sp, logo_aspect, text_aspect):
    """With Date design: temple, small location text, divider, date zone,
    logo floated in the emptier sky corner. The date zone is reserved space;
    the actual personalization text layer is added by hand in Printify."""
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
    logo_layer, side = _corner_logo(temple, temple_layer, sp, logo_aspect, area_w_in, area_h_in)
    logo_layer["corner"] = side
    return [temple_layer, text_layer, divider, date_zone, logo_layer]


PROFILES = {"back_stack": back_stack, "back_stack_dated": back_stack_dated}


def compute_stack(temple_art, garment_cfg, location_text, logo_aspect):
    """Main entry: returns the layer list for one temple on one garment."""
    sp = load_spacing(garment_cfg)
    profile = PROFILES[garment_cfg["layout_profile"]]
    dpi = garment_cfg["print_area"]["dpi"]
    text_h = sp["dated"]["location_text_height_in"] if "dated" in garment_cfg["layout_profile"] \
        else sp["location_text_height_in"]
    text_img = render_text(location_text, text_h, dpi)
    text_aspect = text_img.width / text_img.height
    layers = profile(temple_art, garment_cfg, sp, logo_aspect, text_aspect)
    return layers, text_img
