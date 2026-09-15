"""Render preview PNGs of computed layouts for Evan's gate review.

Usage:
  python preview.py --temple "Salt Lake" --garment cc1717
  python preview.py --temple Provo --garment cc1717-dated

Previews render at 150 dpi (half print resolution) on a white canvas with
a light border marking the print area edge.
"""

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw

import layout
from layout import (PROJECT_ROOT, TEMPLES_DIR, TempleArt, load_art, render_text,
                    working_path)
LOGO_BLACK = PROJECT_ROOT.parent.parent / "Important Elements" / "Peculiar People Logo - Black.png"
PREVIEW_DPI = 150
OUT_DIR = PROJECT_ROOT / "artifacts" / "phase2-previews"


def find_temple_svg(temple_name, color="black"):
    folder = TEMPLES_DIR / temple_name
    exact = folder / f"{temple_name} {color}.svg"
    if exact.exists():
        return exact
    hits = sorted(folder.glob(f"*{color}*.svg"))
    if not hits:
        raise SystemExit(f"No {color} SVG found in {folder}")
    return hits[0]


def build_preview(temple_name, location_text, garment_id, spacing_overrides=None, suffix=""):
    garment_cfg = json.loads((PROJECT_ROOT / "garments" / f"{garment_id}.json").read_text())
    if spacing_overrides:
        merged = garment_cfg.get("spacing_overrides") or {}
        for k, v in spacing_overrides.items():
            if isinstance(v, dict):
                merged.setdefault(k, {}).update(v)
            else:
                merged[k] = v
        garment_cfg["spacing_overrides"] = merged
    svg_path = find_temple_svg(temple_name)
    temple = TempleArt(svg_path)
    logo_img = load_art(LOGO_BLACK)
    logo_aspect = logo_img.height / logo_img.width

    override = layout.find_text_override(TEMPLES_DIR / temple_name, "black")
    text_img = load_art(override) if override else \
        render_text(location_text, layout.location_text_height(garment_cfg), garment_cfg["print_area"]["dpi"])
    manifest_path = working_path(temple_name, "manifest.json")
    logo_override = json.loads(manifest_path.read_text()).get("dated_logo") if manifest_path.exists() else None
    layers = layout.compute_stack(temple, garment_cfg, text_img, logo_aspect, logo_override=logo_override)

    area = garment_cfg["print_area"]
    scale = PREVIEW_DPI / area["dpi"]
    W, H = round(area["width_px"] * scale), round(area["height_px"] * scale)
    canvas = Image.new("RGBA", (W, H), (255, 255, 255, 255))
    draw = ImageDraw.Draw(canvas)
    draw.rectangle([0, 0, W - 1, H - 1], outline=(200, 200, 200, 255), width=2)

    def paste(img, layer):
        w = max(1, round(layer["w_in"] * PREVIEW_DPI))
        h = max(1, round(layer["h_in"] * PREVIEW_DPI))
        resized = img.resize((w, h), Image.LANCZOS)
        px = round(layer["cx_in"] * PREVIEW_DPI - w / 2)
        py = round(layer["cy_in"] * PREVIEW_DPI - h / 2)
        # A frame may legitimately overhang the print area (square-padded SVGs
        # whose ink sits below the frame top). Crop the overhang; never shift.
        crop_l, crop_t = max(0, -px), max(0, -py)
        if crop_l or crop_t:
            resized = resized.crop((crop_l, crop_t, resized.width, resized.height))
        canvas.alpha_composite(resized, (max(px, 0), max(py, 0)))

    for layer in layers:
        if layer["key"] == "temple":
            paste(layout.rasterize_svg(svg_path, round(layer["w_in"] * PREVIEW_DPI)), layer)
        elif layer["key"] == "location_text":
            paste(text_img, layer)
        elif layer["key"] == "logo":
            paste(logo_img, layer)
        elif layer["key"] == "divider":
            x0 = round((layer["cx_in"] - layer["w_in"] / 2) * PREVIEW_DPI)
            y0 = round((layer["cy_in"] - layer["h_in"] / 2) * PREVIEW_DPI)
            draw.rectangle([x0, y0, x0 + round(layer["w_in"] * PREVIEW_DPI),
                            y0 + max(2, round(layer["h_in"] * PREVIEW_DPI))], fill=(0, 0, 0, 255))
        elif layer["key"] == "date_zone":
            sample = render_text("SEPTEMBER 25, 2024", layer["h_in"], PREVIEW_DPI, color=(150, 150, 150, 255))
            natural_w_in = sample.width / sample.height * layer["h_in"]
            paste(sample, {**layer, "w_in": natural_w_in})

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"{temple_name.lower().replace(' ', '-')}_{garment_id}{suffix}.png"
    canvas.convert("RGB").save(out)
    geo = {l["key"]: {k: (round(v, 3) if isinstance(v, (int, float)) else v)
                      for k, v in l.items() if k.endswith("_in") or k in ("x", "y", "scale", "corner")}
           for l in layers}
    (OUT_DIR / f"{out.stem}_geometry.json").write_text(json.dumps(geo, indent=2))
    print(f"saved {out.relative_to(PROJECT_ROOT)}")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--temple", required=True)
    ap.add_argument("--location", required=True, help='e.g. "LOGAN, UTAH"')
    ap.add_argument("--garment", default="cc1717")
    ap.add_argument("--override", help='JSON spacing overrides, e.g. \'{"dated": {"divider_width_in": 2.0}}\'')
    ap.add_argument("--suffix", default="", help="output filename suffix for variant renders")
    a = ap.parse_args()
    build_preview(a.temple, a.location, a.garment,
                  spacing_overrides=json.loads(a.override) if a.override else None, suffix=a.suffix)
