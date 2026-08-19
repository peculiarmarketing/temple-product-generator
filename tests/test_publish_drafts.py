"""Offline tests for the publish eligibility filter. No network.

Run: ./.venv.nosync/bin/python tests/test_publish_drafts.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.publish_drafts import eligibility
from scripts.add_date_layer import load_layer_config

CFG = load_layer_config()


def base_product(**overrides):
    p = {
        "title": "Logan Temple Tee",
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
check("unclaimed duplicate", base_product(title="Copy of Logan Temple Tee"), False, "unclaimed duplicate")
check("front logo test product", base_product(title="Nauvoo Temple Tee (front logo)"), False, "test product")
check("dated by title", base_product(title="Logan Temple Tee - With Date"), False, "date-layer verification")
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
        title="Logan Temple Tee - With Date",
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
        title="Logan Temple Tee - With Date",
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

print("all tests passed")
