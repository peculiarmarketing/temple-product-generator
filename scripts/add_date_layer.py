"""Add the date text layer to unpublished With Date drafts via Playwright.

The Printify API cannot write text layers (error 8253) and any print_areas
write wipes them, so this script drives the editor UI instead, mirroring
Evan's manual flow. The API is used read-only: to find candidates, locate
the divider layer, and verify results. Nothing here ever publishes.

Report:  ./.venv.nosync/bin/python scripts/add_date_layer.py --report-only
One:     ./.venv.nosync/bin/python scripts/add_date_layer.py --product-id <id>
All:     ./.venv.nosync/bin/python scripts/add_date_layer.py
"""

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# cc1717-dated print area (garments/cc1717-dated.json). Only dated garment today;
# if a dated hoodie ever exists, lift these from its garment config instead.
AREA = {"width_px": 4494, "height_px": 5097, "dpi": 300}


def area_inches():
    return AREA["width_px"] / AREA["dpi"], AREA["height_px"] / AREA["dpi"]


def load_dated_spacing():
    spacing = json.loads((PROJECT_ROOT / "spacing_defaults.json").read_text())
    return spacing["dated"]


def load_layer_config():
    return json.loads((PROJECT_ROOT / "config" / "date_layer.json").read_text())


def date_zone_from_divider(divider_y_norm, dated):
    """Date zone rectangle in inches, from the divider layer's normalized center y.

    Mirrors layout.py's dated stack: date zone sits gap_divider_to_date_in
    below the divider's bottom edge, horizontally centered.
    """
    w_in, h_in = area_inches()
    divider_bottom_in = divider_y_norm * h_in + dated["divider_height_in"] / 2
    center_y_in = (
        divider_bottom_in
        + dated["gap_divider_to_date_in"]
        + dated["date_zone_height_in"] / 2
    )
    return {
        "center_x_in": w_in / 2,
        "center_y_in": center_y_in,
        "width_in": dated["date_zone_width_in"],
        "height_in": dated["date_zone_height_in"],
    }


def editor_percent(zone):
    """Editor Position left/top values. Anchor formula per the discovery
    calibration (docs/discovery/2026-08-date-layer-editor-notes.md)."""
    w_in, h_in = area_inches()
    left = (zone["center_x_in"] - zone["width_in"] / 2) / w_in * 100
    top = (zone["center_y_in"] - zone["height_in"] / 2) / h_in * 100
    return round(left, 2), round(top, 2)


def norm_center(zone):
    w_in, h_in = area_inches()
    return zone["center_x_in"] / w_in, zone["center_y_in"] / h_in


def iter_back_placeholders(product):
    for group in product.get("print_areas", []):
        for ph in group.get("placeholders", []):
            if ph.get("position") == "back":
                yield group, ph


def is_text_layer(layer):
    return "input_text" in layer or str(layer.get("type", "")).startswith("text")


def find_divider(placeholder):
    for layer in placeholder.get("images", []):
        if str(layer.get("name", "")).lower().startswith("divider"):
            return layer
    return None


def group_is_dark(placeholder):
    """Dark colorway groups carry the white divider art."""
    d = find_divider(placeholder)
    return bool(d) and "white" in str(d.get("name", "")).lower()


def gate(product):
    """Hard scope filter. Everything must pass before any browser action."""
    title = product.get("title") or ""
    if " - With Date" not in title:
        return False, "not a With Date product"
    if title.startswith("Copy of"):
        return False, "unclaimed duplicate"
    if product.get("external"):
        return False, "already published"
    if product.get("is_locked"):
        return False, "locked"
    backs = list(iter_back_placeholders(product))
    if not backs:
        return False, "no back print area"
    if any(find_divider(ph) is None for _, ph in backs):
        return False, "divider layer not found (design not generated yet?)"
    if any(any(is_text_layer(l) for l in ph.get("images", [])) for _, ph in backs):
        return False, "date layer already present"
    return True, "needs date layer"


def verify(product, cfg, dated, tolerance=0.005):
    """Compare a product's saved state against the expected date layer.

    Returns a list of problems; empty means verified.
    """
    problems = []
    _, h_in = area_inches()
    for group, ph in iter_back_placeholders(product):
        texts = [l for l in ph.get("images", []) if is_text_layer(l)]
        label = f"group variants {group.get('variant_ids', [])[:1]}"
        if len(texts) != 1:
            problems.append(f"{label}: expected 1 text layer, found {len(texts)}")
            continue
        t = texts[0]
        if t.get("input_text") != cfg["placeholder_text"]:
            problems.append(f"{label}: placeholder text is {t.get('input_text')!r}")
        divider = find_divider(ph)
        if divider is None:
            problems.append(f"{label}: divider missing at verify time")
            continue
        zone = date_zone_from_divider(divider["y"], dated)
        want_y = zone["center_y_in"] / h_in
        if abs(t.get("y", -1) - want_y) > tolerance:
            problems.append(
                f"{label}: text y {t.get('y')} not within tolerance of {want_y:.4f}"
            )
    personalisation = (product.get("sales_channel_properties") or {}).get("personalisation") or {}
    if not personalisation.get("layers"):
        problems.append("personalisation layers empty (toggle did not stick)")
    return problems


def resolve_divider_ids(client):
    """Fallback divider matching when GET layers carry no name field:
    resolve the divider upload ids by file name from the media library."""
    ids, page = set(), 1
    while True:
        body = client._request("GET", f"/uploads.json?page={page}&limit=100")
        for item in body.get("data", []):
            if str(item.get("file_name", "")).lower().startswith("divider"):
                ids.add(item["id"])
        if not body.get("next_page_url"):
            return ids
        page += 1
