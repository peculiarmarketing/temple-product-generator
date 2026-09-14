"""Flatten a temple design into one print-ready PNG per print area, for Tapstitch.

Tapstitch has no public API, so products are built by hand in their web editor.
The migration plan's core decision (docs/tapstitch-migration-plan.md) is to bake
placement into the FILE instead of positioning elements in the editor: the canvas
is made the exact shape of the print area, so "centered at full size" lines the
canvas edges up with the print area edges and every element lands where the
layout math put it. The browser step then reduces to the same boring clicks every
run, and every file can be checked on this Mac before it touches Tapstitch.

Positions come from layout.compute_stack(), the same gate-approved math the
Printify pipeline uses. This module only composites and checks.

The back design is temple art plus location text (profile back_temple_text). The
logo moved to the front print area when the catalog left Printify.
"""

import json
from functools import lru_cache

import numpy as np
from PIL import Image

import layout
from layout import PROJECT_ROOT, TempleArt, load_art

TEMPLES_DIR = PROJECT_ROOT.parent.parent / "Temples"
ASSETS_DIR = PROJECT_ROOT.parent.parent / "Important Elements"
LOGO_FILES = {"black": ASSETS_DIR / "Peculiar People Logo - Black.png",
              "white": ASSETS_DIR / "Peculiar People Logo - White.png"}
COLORS = {"black": (0, 0, 0, 255), "white": (255, 255, 255, 255)}
INK_RGB = {"black": (0, 0, 0), "white": (255, 255, 255)}

# The whole Printify catalog once printed at ~157 effective DPI because 2048 px
# assets were stretched onto 4494 px print areas. Vector art rasterized to size
# cannot hit that, but a PNG source can, so it is checked rather than assumed.
MIN_EFFECTIVE_DPI = 200

# How close ink may come to the canvas edge before it counts as a problem.
DEFAULT_SAFE_MARGIN_IN = 0.25


# Rasterising a 1.5MB temple SVG is the expensive step, and a full-catalogue run
# asks for the same art repeatedly: three garments share a print area today, so
# the same (path, width) is requested three times in a row.
#
# The caches are TINY on purpose. A print-area-sized RGBA raster is ~67MB, so a
# cache big enough to span the catalogue would hold gigabytes and the machine
# swaps instead of working (measured: a 256-entry cache turned a 3-minute sweep
# into an unfinished one). Callers iterate temple-major, so a handful of slots
# covers every repeat within one temple and evicts as the sweep moves on.
@lru_cache(maxsize=8)
def _cached_art(svg_path, width_px):
    return layout.rasterize_svg(svg_path, width_px)


@lru_cache(maxsize=4)
def _cached_temple_art(svg_path):
    return TempleArt(svg_path)


def clear_caches():
    _cached_art.cache_clear()
    _cached_temple_art.cache_clear()


def temple_folders():
    """Every real temple folder, in name order.

    Skips dotfiles, Evan's numbered working folders, and Temples/All, which is a
    flat mirror of every black SVG kept for the digital download product and is
    not a temple. Any new script that walks Temples/ has to skip it too.
    """
    all_art = TEMPLES_DIR / "All"
    return [f for f in sorted(TEMPLES_DIR.iterdir())
            if f.is_dir() and not f.name.startswith((".", "1.")) and f != all_art]


def matte(img, rgb):
    """Set every pixel's colour to the ink colour, leaving alpha untouched.

    The trap this fixes, measured 27 Aug 2026: rasterised PNGs carry RGB(0,0,0)
    under fully transparent pixels. Tapstitch's previewer (and Finder's
    thumbnailer) resample without premultiplying alpha, so they average that
    hidden black into neighbouring ink and smear grey halos around white art.
    Giving the hidden pixels the ink colour makes the average a no-op.

    Safe only for single-ink art, which is all this pipeline produces; the
    caller's validate() flags anything multi-toned that would be damaged.
    """
    a = np.array(img.convert("RGBA"))
    a[:, :, 0], a[:, :, 1], a[:, :, 2] = rgb
    return Image.fromarray(a, "RGBA")


def _paste(canvas, img, layer, dpi):
    """Composite one layer onto the canvas at its computed inch position.

    A frame may legitimately overhang the canvas top (square-padded SVGs whose
    ink sits below the frame top). Crop the overhang, never shift the art, or
    the ink stops matching the geometry that was computed for it.
    """
    w = max(1, round(layer["w_in"] * dpi))
    h = max(1, round(layer["h_in"] * dpi))
    resized = img.resize((w, h), Image.LANCZOS)
    px = round(layer["cx_in"] * dpi - w / 2)
    py = round(layer["cy_in"] * dpi - h / 2)
    crop_l, crop_t = max(0, -px), max(0, -py)
    if crop_l or crop_t:
        resized = resized.crop((crop_l, crop_t, resized.width, resized.height))
    canvas.alpha_composite(resized, (max(px, 0), max(py, 0)))


def _geometry(layers):
    return {l["key"]: {k: (round(v, 4) if isinstance(v, (int, float)) else v)
                       for k, v in l.items()
                       if k.endswith("_in") or k in ("x", "y", "scale", "corner")}
            for l in layers}


def build_back(temple_name, manifest, garment_cfg, color):
    """The back print file. Returns {image, raw, geometry, sources}: the matted
    image at exactly the print area's pixel size, the pre-matte canvas the
    validator needs, the geometry it was built from, and the source sizes."""
    area = garment_cfg["print_area"]
    dpi = area["dpi"]
    folder = TEMPLES_DIR / temple_name
    svg_path = folder / manifest["art"][color]

    temple = _cached_temple_art(svg_path)
    override = layout.find_text_override(folder, color)
    if override:
        text_img = load_art(override)
    else:
        text_img = layout.render_text(manifest["location_line"],
                                      layout.location_text_height(garment_cfg),
                                      dpi, COLORS[color])
    logo_img = load_art(LOGO_FILES[color])
    layers = layout.compute_stack(temple, garment_cfg, text_img,
                                  logo_img.height / logo_img.width)

    canvas = Image.new("RGBA", (area["width_px"], area["height_px"]), (0, 0, 0, 0))
    sources = {}
    for lyr in layers:
        if lyr["key"] == "temple":
            art = _cached_art(svg_path, max(1, round(lyr["w_in"] * dpi))) \
                if svg_path.suffix.lower() == ".svg" else load_art(svg_path)
            sources["temple"] = (art.width, lyr["w_in"], svg_path.suffix.lower())
            _paste(canvas, art, lyr, dpi)
        elif lyr["key"] == "location_text":
            sources["location_text"] = (text_img.width, lyr["w_in"],
                                        (override.suffix.lower() if override else ".png"))
            _paste(canvas, text_img, lyr, dpi)
        else:
            raise SystemExit(
                f"{temple_name}/{garment_cfg['garment_id']}: layout profile "
                f"{garment_cfg['layout_profile']!r} produced an unexpected layer "
                f"{lyr['key']!r}. The Tapstitch back design is temple plus location "
                f"text only; check the garment's layout_profile.")

    return {"image": matte(canvas, INK_RGB[color]), "raw": canvas,
            "geometry": _geometry(layers), "sources": sources}


def build_front_logo(garment_cfg, color):
    """The front print file: the logo alone on a canvas shaped to the front print
    area, so the editor step is identical to the back (upload, centre, full size).

    Sized and positioned from the garment's front_print_area: logo_width_in wide,
    its top logo_top_margin_in below the top of the print area, centred across.
    Centring the logo in the canvas instead would drop it to mid-chest.
    """
    area = garment_cfg.get("front_print_area")
    if not area:
        raise SystemExit(f"{garment_cfg['garment_id']}: no front_print_area in the garment config.")
    dpi = area["dpi"]
    area_w_in = area["width_px"] / dpi
    area_h_in = area["height_px"] / dpi

    logo_img = load_art(LOGO_FILES[color])
    w_in = area["logo_width_in"]
    h_in = w_in * logo_img.height / logo_img.width
    layer = {"key": "logo", "w_in": w_in, "h_in": h_in,
             "cx_in": area_w_in / 2,
             "cy_in": area["logo_top_margin_in"] + h_in / 2,
             "top_in": area["logo_top_margin_in"],
             "bottom_in": area["logo_top_margin_in"] + h_in,
             "x": 0.5, "y": (area["logo_top_margin_in"] + h_in / 2) / area_h_in,
             "scale": w_in / area_w_in}

    canvas = Image.new("RGBA", (area["width_px"], area["height_px"]), (0, 0, 0, 0))
    _paste(canvas, logo_img, layer, dpi)
    sources = {"logo": (logo_img.width, w_in, ".png")}
    return {"image": matte(canvas, INK_RGB[color]), "raw": canvas,
            "geometry": _geometry([layer]), "sources": sources}


def validate(img, garment_cfg, sources, color, area_key="print_area", pre_matte=None):
    """Problems with one built file, as a list of strings. Never raises: a caller
    building 46 temples wants every finding at once, not the first one."""
    problems = []
    area = garment_cfg[area_key]
    dpi = area["dpi"]

    if img.size != (area["width_px"], area["height_px"]):
        problems.append(f"canvas is {img.width}x{img.height}, print area is "
                        f"{area['width_px']}x{area['height_px']}; 'centre at full size' "
                        f"would not align the edges")

    alpha = np.asarray(img.getchannel("A"))
    if not (alpha < 255).any():
        problems.append("no transparency anywhere; the file would print as a solid block")
    ink = alpha > 10
    if not ink.any():
        problems.append("no ink at all; the file is empty")
        return problems

    ys, xs = np.where(ink)
    sp = layout.load_spacing(garment_cfg)
    safe_in = sp.get("safe_margin_in", DEFAULT_SAFE_MARGIN_IN)
    safe_px = safe_in * dpi
    for label, value, limit, side in (
            ("left", xs.min(), safe_px, "edge"),
            ("top", ys.min(), safe_px, "edge"),
            ("right", img.width - 1 - xs.max(), safe_px, "edge"),
            ("bottom", img.height - 1 - ys.max(), safe_px, "edge")):
        if value < limit:
            problems.append(f"ink comes within {value / dpi:.2f}in of the {label} {side}; "
                            f"the safe margin is {safe_in:.2f}in")

    for key, (src_px, w_in, suffix) in sources.items():
        if suffix == ".svg":
            continue  # vector, rasterised straight to the target size
        effective = src_px / w_in if w_in else 0
        if effective < MIN_EFFECTIVE_DPI:
            problems.append(f"{key}: {src_px}px source stretched to {w_in:.2f}in is "
                            f"{effective:.0f} effective DPI, under the {MIN_EFFECTIVE_DPI} floor")

    if pre_matte is not None:
        a = np.array(pre_matte.convert("RGBA"))
        vis = a[a[:, :, 3] > 10][:, :3]
        if len(vis) and len(np.unique(vis, axis=0)) > 1:
            problems.append("visible pixels are not all one colour; the matte pass would "
                            "flatten real detail. This art is not single-ink.")
    return problems


def _inside(path, root):
    """True when path is inside root once both are resolved.

    The project constraint is absolute: write nothing outside Claude Projects and
    the sibling Temples folders. temple_name reaches here from a --temple command
    line argument, so "../../somewhere" would otherwise resolve to a stray write
    into iCloud Drive. Checked at the point of the write so every caller is
    covered, rather than once per script.
    """
    try:
        return path.resolve().is_relative_to(root.resolve())
    except (OSError, ValueError):
        return False


def back_file_path(temple_name, garment_id, color):
    """Print files land in the temple's own folder. The '(auto)' marker is
    load-bearing: layout.find_text_override() skips '(auto)' files, so the
    generator can never mistake its own output for one of Evan's overrides."""
    path = TEMPLES_DIR / temple_name / f"{temple_name} {garment_id} {color} back print (auto).png"
    if not _inside(path, TEMPLES_DIR):
        raise SystemExit(f"Refusing to write outside the Temples folder: {temple_name!r} "
                         f"resolves to {path}")
    return path


def front_file_path(garment_id, color):
    """One front logo file per garment per colour, not one per temple.

    Guarded like back_file_path(): garment_id reaches here from the --garments
    command line argument. Today load_garment_config() would fail on a bad id
    before this is ever called, but that is incidental to how that function
    happens to work, not a designed protection, so the check belongs here too.
    """
    root = PROJECT_ROOT / "artifacts" / "tapstitch" / "front-logo"
    path = root / f"{garment_id} {color} front print (auto).png"
    if not _inside(path, root):
        raise SystemExit(f"Refusing to write outside {root}: garment {garment_id!r}")
    return path


def save(img, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)
    return path
