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
