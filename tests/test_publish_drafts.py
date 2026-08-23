"""Offline tests for the publish eligibility filter. No network.

Run: ./.venv.nosync/bin/python tests/test_publish_drafts.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.default_variant import wanted_default
from scripts.publish_drafts import default_variant_note, eligibility
from scripts.add_date_layer import load_layer_config

CFG = load_layer_config()


def base_product(**overrides):
    p = {
        "title": "Essential Temple Tee (Logan)",
        "blueprint_id": 706,
        "external": None,
        "is_locked": False,
        "is_economy_shipping_enabled": True,
        "description": 'intro <section class="temple-facts">facts</section>',
        "sales_channel_properties": {"personalisation": {"strategy": "pstudio"}},
    }
    p.update(overrides)
    return p


def divider_layer(color="white", y=0.685):
    return {"id": "img123", "name": f"divider {color} 2in.png", "x": 0.5, "y": y, "scale": 0.1335, "angle": 0}


def text_layer(y=0.7206, text=None, color="#FFFFFF"):
    return {
        "id": "uuid-1", "type": "text/plain", "input_text": text if text is not None else CFG["placeholder_text"],
        "font_family": "Alata", "font_color": color,
        "x": 0.5, "y": y, "scale": CFG["expected_scale"], "angle": 0,
    }


def dated_print_areas(layers_per_group):
    """One back placeholder group per images list, mirroring test_add_date_layer.py's dated_product shape."""
    return [
        {"variant_ids": [i], "placeholders": [{"position": "back", "images": layers}]}
        for i, layers in enumerate(layers_per_group)
    ]


def check(name, product, want_ok, want_reason_part):
    ok, reason = eligibility(product)
    assert ok == want_ok, f"{name}: expected ok={want_ok}, got {ok} ({reason})"
    assert want_reason_part in reason, f"{name}: expected reason with '{want_reason_part}', got '{reason}'"


check("clean draft", base_product(), True, "eligible")
check("already published", base_product(external={"id": "1", "handle": "x"}), False, "already published")
check("locked", base_product(is_locked=True), False, "locked")
check("unclaimed duplicate", base_product(title="Copy of Essential Temple Tee (Logan)"), False,
      "unclaimed duplicate")
check("parent temple product", base_product(title="Essential Temple Tee"), True, "eligible")
check("limited edition one-off",
      base_product(title="Essential Temple Tee – Limited Edition (Nauvoo)"), False, "Limited Edition")
check("limited edition hoodie one-off",
      base_product(title="Pillar Temple Hoodie – Limited Edition (Nauvoo)"), False, "Limited Edition")
check("dated by title", base_product(title="Essential Temple Tee – with personalizable date (Logan)"),
      False, "date-layer verification")
check("retired With Date suffix still reads as dated",
      base_product(title="Logan Temple Tee - With Date"), False, "date-layer verification")
check(
    "personalizable by layers",
    base_product(
        sales_channel_properties={
            "personalisation": {"layers": [{"personalisation_id": "text"}], "strategy": "pstudio"}
        },
        # No date text layer actually placed yet, so verification must fail
        # rather than let this through on the personalisation toggle alone.
        print_areas=dated_print_areas([[divider_layer("white")]]),
    ),
    False,
    "date-layer verification",
)
check(
    "dated with fully verified layers",
    base_product(
        title="Essential Temple Tee – with personalizable date (Logan)",
        sales_channel_properties={
            "personalisation": {"strategy": "pstudio", "layers": [{"personalisation_id": "text"}]}
        },
        print_areas=dated_print_areas([
            [divider_layer("white"), text_layer()],
            [divider_layer("black"), text_layer(color="#000000")],
        ]),
    ),
    True,
    "eligible",
)
check(
    "dated with one group missing its text layer",
    base_product(
        title="Essential Temple Tee – with personalizable date (Logan)",
        sales_channel_properties={
            "personalisation": {"strategy": "pstudio", "layers": [{"personalisation_id": "text"}]}
        },
        print_areas=dated_print_areas([
            [divider_layer("white"), text_layer()],
            [divider_layer("black")],
        ]),
    ),
    False,
    "date-layer verification",
)
check("missing facts section", base_product(description="just an intro"), False, "temple facts")
check("no description at all", base_product(description=None), False, "temple facts")
check("economy off still publishes", base_product(is_economy_shipping_enabled=False), True, "eligible")
check("scp missing entirely", base_product(sales_channel_properties=None), True, "eligible")

# --- the Moss default-variant note (reports, never gates)

def check_note(name, product, want_part):
    note = default_variant_note(product)
    if want_part is None:
        assert note is None, f"{name}: expected no note, got {note!r}"
        return
    assert note and want_part in note, f"{name}: expected note with {want_part!r}, got {note!r}"


check_note("base product is not dated, no note",
           base_product(variants=[{"is_default": True, "title": "Graphite / L"}]), None)
check_note("dated on Moss is fine",
           base_product(title="Essential Temple Tee – with personalizable date (Logan)",
                        variants=[{"is_default": True, "title": "Moss / L"}]), None)
check_note("dated on the wrong colorway is reported",
           base_product(title="Essential Temple Tee – with personalizable date (Logan)",
                        variants=[{"is_default": True, "title": "Graphite / L"}]), "Graphite")
check_note("dated with no default at all",
           base_product(title="Essential Temple Tee – with personalizable date (Logan)",
                        variants=[{"is_default": False, "title": "Moss / L"}]),
           "no default variant")
check_note("a garment that declares no default colorway is left alone",
           base_product(blueprint_id=1298, title="Pillar Temple Hoodie (Logan)",
                        variants=[{"is_default": True, "title": "Crimson / L"}]), None)

# --- picking the replacement default keeps the size

def check_pick(name, variants, colorway, want_title):
    got = wanted_default(variants, colorway)
    got_title = got["title"] if got else None
    assert got_title == want_title, f"{name}: expected {want_title!r}, got {got_title!r}"


VARIANTS = [
    {"id": 1, "title": "True Navy / L", "is_enabled": True, "is_default": True},
    {"id": 2, "title": "Moss / S", "is_enabled": True},
    {"id": 3, "title": "Moss / L", "is_enabled": True},
    {"id": 4, "title": "Moss / 4XL", "is_enabled": False},
]
check_pick("keeps the current default's size", VARIANTS, "Moss", "Moss / L")
check_pick("falls back to the first enabled of the colorway",
           [dict(VARIANTS[0], title="True Navy / 2XL"), VARIANTS[1], VARIANTS[3]], "Moss", "Moss / S")
check_pick("never picks a disabled variant",
           [VARIANTS[0], VARIANTS[3]], "Moss", None)
check_pick("colorway absent entirely", [VARIANTS[0]], "Ivory", None)

print("all tests passed")
