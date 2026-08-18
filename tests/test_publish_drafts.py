"""Offline tests for the publish eligibility filter. No network.

Run: ./.venv.nosync/bin/python tests/test_publish_drafts.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.publish_drafts import eligibility


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


def check(name, product, want_ok, want_reason_part):
    ok, reason = eligibility(product)
    assert ok == want_ok, f"{name}: expected ok={want_ok}, got {ok} ({reason})"
    assert want_reason_part in reason, f"{name}: expected reason with '{want_reason_part}', got '{reason}'"


check("clean draft", base_product(), True, "eligible")
check("already published", base_product(external={"id": "1", "handle": "x"}), False, "already published")
check("locked", base_product(is_locked=True), False, "locked")
check("unclaimed duplicate", base_product(title="Copy of Logan Temple Tee"), False, "unclaimed duplicate")
check("front logo test product", base_product(title="Nauvoo Temple Tee (front logo)"), False, "test product")
check("dated by title", base_product(title="Logan Temple Tee - With Date"), False, "dated")
check(
    "personalizable by layers",
    base_product(
        sales_channel_properties={
            "personalisation": {"layers": [{"personalisation_id": "text"}], "strategy": "pstudio"}
        }
    ),
    False,
    "personalizable",
)
check("missing facts section", base_product(description="just an intro"), False, "temple facts")
check("no description at all", base_product(description=None), False, "temple facts")
check("economy off", base_product(is_economy_shipping_enabled=False), False, "economy")
check("scp missing entirely", base_product(sales_channel_properties=None), True, "eligible")

print("all tests passed")
