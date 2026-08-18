"""Offline tests for date-layer math, gating, and verification. No network.

Run: ./.venv.nosync/bin/python tests/test_add_date_layer.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.add_date_layer import (
    area_inches,
    date_zone_from_divider,
    editor_percent,
    norm_center,
)

DATED = {
    "divider_height_in": 0.04,
    "gap_divider_to_date_in": 0.13,
    "date_zone_width_in": 7.0,
    "date_zone_height_in": 0.91,
}


def close(a, b, tol=0.01):
    assert abs(a - b) <= tol, f"{a} not within {tol} of {b}"


w_in, h_in = area_inches()
close(w_in, 14.98)
close(h_in, 16.99)

# Divider center at normalized y 0.685 on the 16.99in area:
# center 11.6382in, bottom 11.6582in, date zone center 12.2432in.
zone = date_zone_from_divider(0.685, DATED)
close(zone["center_x_in"], 7.49)
close(zone["center_y_in"], 12.2432)
close(zone["width_in"], 7.0)
close(zone["height_in"], 0.91)

# Editor percent per the Task 2 calibration (top-left anchor over print area).
left_pct, top_pct = editor_percent(zone)
close(left_pct, 26.64, tol=0.05)
close(top_pct, 69.38, tol=0.05)

# Normalized center for API-side verification.
x_norm, y_norm = norm_center(zone)
close(x_norm, 0.5, tol=0.001)
close(y_norm, 12.2432 / 16.99, tol=0.001)

print("all math tests passed")
