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


def text_layer(y=0.7206, text="June 14, 2026", color="#FFFFFF", scale=0.4673, font_family="Alata"):
    return {
        "id": "uuid-1", "type": "text/plain", "input_text": text,
        "font_family": font_family, "font_color": color,
        "x": 0.5, "y": y, "scale": scale, "angle": 0,
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
check_gate("no back print area", dated_product(layers_per_group=[]), False, "no back print area")
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

CFG = {
    "placeholder_text": "June 14, 2026",
    "font_family": "Alata",
    "font_color_light_groups": "#000000",
    "font_color_dark_groups": "#ffffff",
    "expected_scale": 0.4673,
}
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

no_backs = dated_product(layers_per_group=[])
no_backs["sales_channel_properties"] = {"personalisation": {"strategy": "pstudio", "layers": [{"personalisation_id": "t"}]}}
problems = verify(no_backs, CFG, DATED_SPACING)
assert any("no back placeholders" in p for p in problems), problems

wrong_color = dated_product(
    layers_per_group=[[divider_layer("white"), text_layer(color="#000000")]],
    sales_channel_properties={"personalisation": {"strategy": "pstudio", "layers": [{"personalisation_id": "t"}]}},
)
problems = verify(wrong_color, CFG, DATED_SPACING)
assert any("color" in p for p in problems), problems

wrong_scale = dated_product(
    layers_per_group=[[divider_layer("white"), text_layer(scale=0.5)]],
    sales_channel_properties={"personalisation": {"strategy": "pstudio", "layers": [{"personalisation_id": "t"}]}},
)
problems = verify(wrong_scale, CFG, DATED_SPACING)
assert any("scale" in p for p in problems), problems

wrong_font = dated_product(
    layers_per_group=[[divider_layer("white"), text_layer(font_family="Arial")]],
    sales_channel_properties={"personalisation": {"strategy": "pstudio", "layers": [{"personalisation_id": "t"}]}},
)
problems = verify(wrong_font, CFG, DATED_SPACING)
assert any("font is" in p for p in problems), problems

print("all tests passed")

from scripts.add_date_layer import build_plan, group_colorway


def colorway_option():
    return {
        "name": "Colors",
        "type": "color",
        "values": [
            {"id": 100, "title": "Graphite"},
            {"id": 200, "title": "White"},
        ],
    }


def colorway_variant(variant_id, color_value_id, size_value_id=999):
    return {"id": variant_id, "options": [color_value_id, size_value_id]}


# group_colorway: a color option mapping two variants to two colorway titles,
# plus a group whose variant id is not in product["variants"] at all.
colorway_fixture = {
    "options": [colorway_option()],
    "variants": [colorway_variant(10, 100), colorway_variant(20, 200)],
}
assert group_colorway(colorway_fixture, {"variant_ids": [10]}) == "Graphite"
assert group_colorway(colorway_fixture, {"variant_ids": [20]}) == "White"
assert group_colorway(colorway_fixture, {"variant_ids": [999999]}) is None
assert group_colorway({"options": [], "variants": []}, {"variant_ids": [10]}) is None

# build_plan: groups carry exactly {"dark", "colorway"}, no "index". Light
# group (divider "black") maps to variant 20 / "White"; dark group (divider
# "white") maps to variant 10 / "Graphite".
colorway_product = dated_product(
    layers_per_group=[[divider_layer("black")], [divider_layer("white")]],
    options=[colorway_option()],
    variants=[colorway_variant(20, 200), colorway_variant(10, 100)],
)
colorway_product["print_areas"][0]["variant_ids"] = [20]
colorway_product["print_areas"][1]["variant_ids"] = [10]

plan = build_plan(colorway_product, DATED_SPACING)
assert len(plan["groups"]) == 2, plan["groups"]
for g in plan["groups"]:
    assert set(g.keys()) == {"dark", "colorway"}, g
assert plan["groups"][0] == {"dark": False, "colorway": "White"}, plan["groups"][0]
assert plan["groups"][1] == {"dark": True, "colorway": "Graphite"}, plan["groups"][1]

print("all group-contract tests passed")
