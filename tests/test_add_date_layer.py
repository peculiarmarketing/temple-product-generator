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

from scripts.add_date_layer import (
    gate,
    verify,
    find_divider,
    group_is_dark,
    is_text_layer,
)


def divider_layer(color="white", y=0.685):
    return {"id": "img123", "name": f"divider {color} 2in.png", "x": 0.5, "y": y, "scale": 0.1335, "angle": 0}


def text_layer(y=0.7206, text="June 14, 2026"):
    return {
        "id": "uuid-1", "type": "text/plain", "input_text": text,
        "font_family": "Alata", "font_color": "#FFFFFF",
        "x": 0.5, "y": y, "scale": 0.4, "angle": 0,
    }


def dated_product(layers_per_group=None, **overrides):
    if layers_per_group is None:
        layers_per_group = [[divider_layer("white")], [divider_layer("black")]]
    p = {
        "id": "prod1",
        "title": "Logan Temple Tee - With Date",
        "external": None,
        "is_locked": False,
        "sales_channel_properties": {"personalisation": {"strategy": "pstudio"}},
        "print_areas": [
            {"variant_ids": [1, 2], "placeholders": [{"position": "back", "images": layers}]}
            for layers in layers_per_group
        ],
    }
    p.update(overrides)
    return p


def check_gate(name, product, want_ok, want_reason_part):
    ok, reason = gate(product)
    assert ok == want_ok, f"{name}: expected ok={want_ok}, got {ok} ({reason})"
    assert want_reason_part in reason, f"{name}: expected '{want_reason_part}' in '{reason}'"


check_gate("clean candidate", dated_product(), True, "needs date layer")
check_gate("not dated", dated_product(title="Logan Temple Tee"), False, "not a With Date")
check_gate("unclaimed duplicate", dated_product(title="Copy of Logan Temple Tee - With Date"), False, "unclaimed duplicate")
check_gate("already published", dated_product(external={"id": "1"}), False, "already published")
check_gate("locked", dated_product(is_locked=True), False, "locked")
check_gate("no divider", dated_product(layers_per_group=[[]]), False, "divider layer not found")
check_gate(
    "layer already present",
    dated_product(layers_per_group=[[divider_layer("white"), text_layer()]]),
    False,
    "date layer already present",
)

assert is_text_layer(text_layer())
assert not is_text_layer(divider_layer())
assert find_divider({"position": "back", "images": [divider_layer("black")]})["name"] == "divider black 2in.png"
assert group_is_dark({"position": "back", "images": [divider_layer("white")]})
assert not group_is_dark({"position": "back", "images": [divider_layer("black")]})

CFG = {"placeholder_text": "June 14, 2026"}
DATED_SPACING = DATED

good = dated_product(
    layers_per_group=[[divider_layer("white"), text_layer()]],
    sales_channel_properties={"personalisation": {"strategy": "pstudio", "layers": [{"personalisation_id": "t"}]}},
)
assert verify(good, CFG, DATED_SPACING) == [], f"expected clean verify, got {verify(good, CFG, DATED_SPACING)}"

missing_layer = dated_product(layers_per_group=[[divider_layer("white")]])
problems = verify(missing_layer, CFG, DATED_SPACING)
assert any("expected 1 text layer" in p for p in problems), problems

wrong_text = dated_product(
    layers_per_group=[[divider_layer("white"), text_layer(text="wrong words")]],
    sales_channel_properties={"personalisation": {"strategy": "pstudio", "layers": [{"personalisation_id": "t"}]}},
)
problems = verify(wrong_text, CFG, DATED_SPACING)
assert any("placeholder text" in p for p in problems), problems

drifted = dated_product(
    layers_per_group=[[divider_layer("white"), text_layer(y=0.80)]],
    sales_channel_properties={"personalisation": {"strategy": "pstudio", "layers": [{"personalisation_id": "t"}]}},
)
problems = verify(drifted, CFG, DATED_SPACING)
assert any("not within tolerance" in p for p in problems), problems

no_personalization = dated_product(layers_per_group=[[divider_layer("white"), text_layer()]])
problems = verify(no_personalization, CFG, DATED_SPACING)
assert any("personalisation layers empty" in p for p in problems), problems

print("all tests passed")
