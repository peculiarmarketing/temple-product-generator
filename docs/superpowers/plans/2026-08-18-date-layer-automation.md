# Date Layer Automation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Playwright script that adds the date text layer (with personalization enabled) to unpublished With Date drafts, so Evan's manual work drops to review and publish.

**Architecture:** A standalone operational script following the repo's existing pattern (one script per concern in `scripts/`, offline-testable functions, plain assert tests). Position comes from reading the divider layer via API GET plus the spacing constants in `spacing_defaults.json`. All Printify API access is read-only; every write happens in the browser through Playwright, exactly mirroring Evan's manual editor flow. Nothing publishes.

**Tech Stack:** Python 3.12 (`./.venv.nosync/bin/python`), Playwright (sync API, Chromium), existing `printify_client.PrintifyClient`, plain assert test scripts.

**Spec:** `docs/superpowers/specs/2026-08-18-date-layer-automation-design.md` (read it first; the reversibility section is a hard requirement).

## Global Constraints

- Run everything with `./.venv.nosync/bin/python`. Never system python.
- Zero edits to existing code files. Allowed additive exceptions only: one line in `requirements.txt`, one line in `.gitignore`, new lines in `docs/decisions.md` and `README.md` in the final task. `generate.py`, `layout.py`, `printify_client.py`, and everything in `scripts/` stay untouched.
- NEVER PUT or POST `print_areas` on any With Date product from this feature. Any API write to `print_areas` wipes text layers (error 8253, settled Phase 1 finding). This feature reads via API and writes only through the browser.
- NEVER publish. The script must not call any publish endpoint and must not click any publish control. The existing decision "With Date products are never published via API" stands.
- The Playwright session file (`.playwright/`) holds Evan's auth cookie: gitignored, never committed, never printed, same discipline as `.env`.
- Hard scope: only products whose title contains " - With Date", not starting with "Copy of", with no `external` value (unpublished), with a divider layer present and no text layer present. Everything else is rejected before any browser action.
- Phase gates are real stops. Steps marked **STOP: GATE** require Evan's explicit confirmation before continuing.
- No em dashes in any Evan-facing text (docs, READMEs, print output).
- Do not run the script while a sweep (`generate.py`) is running.

## Known repo facts the executor needs

- Print area for `cc1717-dated`: 4494 x 5097 px at 300 dpi (14.98 x 16.99 inches). From `garments/cc1717-dated.json`.
- Date geometry constants live in `spacing_defaults.json` under `"dated"`: `divider_height_in: 0.04`, `gap_divider_to_date_in: 0.13`, `date_zone_width_in: 7.0`, `date_zone_height_in: 0.91`. The date zone is horizontally centered (see `layout.py:215-223`).
- Divider images were uploaded as `divider black 2in.png` and `divider white 2in.png` (`generate.py:202`). Light colorway groups carry the black divider, dark groups the white one.
- API GET exposes text layers (they appear with instance UUIDs; see the comment above `WRITABLE_TEXT_LAYER_KEYS` in `printify_client.py`). Image and text layers share the `x`, `y`, `scale`, `angle` convention: normalized 0..1, layer center.
- `scripts/publish_drafts.py` provides `load_config()` returning `(token, shop_id)` and shows the candidate-iteration pattern (`all_products`, list endpoint trims fields, judge from full GET).
- Personalization state is visible in `sales_channel_properties.personalisation.layers` (see `tests/test_publish_drafts.py`).
- Test convention: plain python assert scripts, no pytest. Run: `./.venv.nosync/bin/python tests/test_X.py`, which prints `all tests passed`.

## File map

- Create: `scripts/printify_login.py` (headed login, session save, session check)
- Create: `scripts/add_date_layer.py` (math, gating, verification, CLI orchestration)
- Create: `scripts/date_layer_editor.py` (Playwright editor driver, selectors from config)
- Create: `config/date_layer.json` (settings and selectors captured in discovery; no secrets)
- Create: `docs/discovery/2026-08-date-layer-editor-notes.md` (discovery session record)
- Create: `tests/test_add_date_layer.py` (offline tests for math, gating, verification)
- Modify (additive line only): `requirements.txt`, `.gitignore`
- Modify (new lines only, final task): `docs/decisions.md`, `README.md`

---

### Task 1: Playwright dependency, session storage, login script

**Files:**
- Modify: `requirements.txt` (one added line)
- Modify: `.gitignore` (one added line)
- Create: `scripts/printify_login.py`

**Interfaces:**
- Produces: `SESSION_FILE` path constant (`.playwright/printify-session.json`) and a working saved session that Tasks 2 and 5 load via `storage_state`.
- Produces: `scripts/printify_login.py --check` exit code 0 when the session is valid, 1 when missing or expired.

- [ ] **Step 1: Add the dependency and ignore rule**

Append to `requirements.txt` (keep existing lines untouched):

```
playwright==1.55.0
```

Append to `.gitignore`:

```
.playwright/
```

- [ ] **Step 2: Install**

```bash
./.venv.nosync/bin/pip install playwright==1.55.0
./.venv.nosync/bin/python -m playwright install chromium
```

Note: the second command downloads a Chromium build (roughly 150 MB) to `~/Library/Caches/ms-playwright/`, outside the repo and outside iCloud sync. If the pinned version conflicts with something, resolve by bumping the pin, never by touching existing pins.

- [ ] **Step 3: Write the login script**

Create `scripts/printify_login.py`:

```python
"""Headed Printify login for the date-layer automation.

Evan types credentials himself in the opened browser window. This script
never sees, stores, or types credentials. It waits for the app to reach a
logged-in state, then saves browser storage state (cookies plus local
storage) to .playwright/printify-session.json.

The session file is gitignored. Never commit it, never print its contents.

Login:  ./.venv.nosync/bin/python scripts/printify_login.py
Check:  ./.venv.nosync/bin/python scripts/printify_login.py --check
"""

import argparse
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SESSION_FILE = PROJECT_ROOT / ".playwright" / "printify-session.json"
LOGIN_URL = "https://printify.com/app/login"
APP_URL = "https://printify.com/app/store/products"


def _is_logged_in(page):
    return page.url.startswith("https://printify.com/app") and "login" not in page.url


def login():
    SESSION_FILE.parent.mkdir(exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto(LOGIN_URL)
        print("Log in inside the browser window. Waiting up to 5 minutes.")
        page.wait_for_url(
            lambda url: url.startswith("https://printify.com/app") and "login" not in url,
            timeout=300_000,
        )
        page.wait_for_load_state("networkidle")
        context.storage_state(path=str(SESSION_FILE))
        browser.close()
    print(f"Session saved to {SESSION_FILE.relative_to(PROJECT_ROOT)}")


def check():
    if not SESSION_FILE.exists():
        print("No session file. Run scripts/printify_login.py first.")
        return 1
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(storage_state=str(SESSION_FILE))
        page = context.new_page()
        page.goto(APP_URL, wait_until="networkidle")
        ok = _is_logged_in(page)
        browser.close()
    if ok:
        print("Session is valid.")
        return 0
    print("Session expired. Re-run scripts/printify_login.py (headed login).")
    return 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify the saved session still works")
    args = parser.parse_args()
    sys.exit(check() if args.check else login() or 0)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Evan performs the headed login**

Run and hand the window to Evan:

```bash
./.venv.nosync/bin/python scripts/printify_login.py
```

Expected: Evan logs in, script prints `Session saved to .playwright/printify-session.json`.

- [ ] **Step 5: Verify the session works headlessly**

```bash
./.venv.nosync/bin/python scripts/printify_login.py --check
```

Expected: `Session is valid.` and exit code 0.

- [ ] **Step 6: Confirm nothing sensitive is staged, then commit**

```bash
git status --short
```

Expected: only `requirements.txt`, `.gitignore`, `scripts/printify_login.py`. The `.playwright/` directory must NOT appear.

```bash
git add requirements.txt .gitignore scripts/printify_login.py
git commit -m "feat: playwright login and session persistence for date-layer automation"
```

**Phase 1 gate note:** the spec requires proof the session persists across days. The check re-runs as a precondition of Task 5. Do not treat the gate as passed until that later check also succeeds.

---

### Task 2: Discovery session (supervised, with Evan)

This is the spec's Phase 0. It is a working session, not a coding task. Evan should be present or reachable. The Brigham City Tee - With Date draft (currently awaiting its layer) is the subject; the layer added during this session is real work Evan needed done anyway, so the session ends with that draft ready for Evan to review and publish.

**Files:**
- Create: `config/date_layer.json`
- Create: `docs/discovery/2026-08-date-layer-editor-notes.md`
- Create: `artifacts/date-layer/reference-product.json` (GET snapshot of the reference product; committed, no secrets)

**Interfaces:**
- Produces: `config/date_layer.json` with the exact schema below. Tasks 3 to 6 read it. Keys are fixed; values recorded live in this session replace the examples.

- [ ] **Step 1: Snapshot the reference product via API**

Pick one published With Date tee (Evan names his best hand-built one). Fetch and save its full GET body:

```bash
cd "/Users/evandavis/Library/Mobile Documents/com~apple~CloudDocs/1. Peculiar People/Claude Projects/temple-product-generator"
./.venv.nosync/bin/python - <<'EOF'
import json, sys
sys.path.insert(0, ".")
from printify_client import PrintifyClient
from scripts.publish_drafts import load_config

PRODUCT_ID = "REPLACE_WITH_REFERENCE_PRODUCT_ID"  # Evan names the product; find its id in the Printify URL
token, shop_id = load_config()
client = PrintifyClient(token, shop_id)
product = client._request("GET", f"/shops/{shop_id}/products/{PRODUCT_ID}.json")
from pathlib import Path
Path("artifacts/date-layer").mkdir(parents=True, exist_ok=True)
Path("artifacts/date-layer/reference-product.json").write_text(json.dumps(product, indent=2))
print("saved")
EOF
```

From the snapshot, record into the discovery notes:
- The text layer objects: `font_family`, `font_size`, `font_color`, `input_text`, `x`, `y`, `scale`, `angle`, `type`.
- Whether the text layer appears once per print-area group or once overall.
- Whether image layers carry a `name` field in GET (decides divider matching strategy).
- The `sales_channel_properties.personalisation` block (personalization config as the API sees it).
- Derived check: confirm `y` of the text layer minus computed date-zone center from the divider `y` is near zero (validates the position formula in Task 3 against reality).

- [ ] **Step 2: Open the editor on the Brigham City draft through the saved session**

Use a small throwaway driver (do not commit) to open a headed browser with `storage_state=SESSION_FILE`, navigate to the product list, and open the Brigham City Tee - With Date draft in the editor. Record in the notes:
- The exact editor URL pattern once the editor is open (becomes `editor_url_template`).
- How print-area groups are switched in the UI, and how many groups this product has.

- [ ] **Step 3: Perform the manual flow once, recording every step**

With Evan directing (or following his written steps), add the date text layer to the draft the way he always does: add text, type the placeholder, set font, size, color per group, position it, enable personalization, save. While doing it, record in the notes for every control touched:
- Its visible label and role (for selector design).
- For the position fields: the values entered, and which corner of the text box they anchor (drag the layer, watch the numbers).
- Whether the layer must be added separately per group, or once with per-group color overrides.
- The personalization toggle's label and any settings it opens (prompt text, required flag, character limit behavior given the known Printify bug where the character limit field does not render).

- [ ] **Step 4: Calibrate editor fields against the API**

After saving, re-run the GET from Step 1 against the Brigham City draft. Compare the editor's Position left/top percent values with the GET layer's normalized center `x`, `y`. Record the exact conversion in the notes. Expected relationship (verify, do not assume): `left_pct = (center_x_norm - width_frac / 2) * 100`, `top_pct = (center_y_norm - height_frac / 2) * 100`. If the editor anchors differently, record the actual formula; Task 3's conversion function and test expectations follow the notes, not the guess.

- [ ] **Step 5: Write the config**

Create `config/date_layer.json`. Schema is fixed; every value below is an example to be replaced with the recorded truth:

```json
{
  "_comment": "Captured in the 2026-08 discovery session (docs/discovery/2026-08-date-layer-editor-notes.md). Selectors verified against the live editor on that date. No secrets in this file.",
  "editor_url_template": "https://printify.com/app/editor?product_id={product_id}",
  "placeholder_text": "June 14, 2026",
  "font_family": "Alata",
  "font_size": 48,
  "font_color_light_groups": "#000000",
  "font_color_dark_groups": "#FFFFFF",
  "layer_per_group": true,
  "position_anchor": "top_left_percent_of_print_area",
  "personalization": {
    "toggle_label": "Personalizable text",
    "prompt_text": "Your date (as you want it printed)",
    "required": true
  },
  "divider_match": "name",
  "selectors": {
    "add_text_button": {"kind": "role", "role": "button", "name": "Add text"},
    "text_input": {"kind": "role", "role": "textbox", "name": "Text"},
    "font_family_input": {"kind": "label", "label": "Font"},
    "font_size_input": {"kind": "label", "label": "Font size"},
    "color_input": {"kind": "label", "label": "Color"},
    "position_left_input": {"kind": "label", "label": "Position left"},
    "position_top_input": {"kind": "label", "label": "Position top"},
    "center_horizontal_button": {"kind": "role", "role": "button", "name": "Center horizontally"},
    "personalization_toggle": {"kind": "label", "label": "Personalizable text"},
    "save_button": {"kind": "role", "role": "button", "name": "Save"},
    "layers_panel": {"kind": "role", "role": "heading", "name": "Variants and layers"},
    "login_form_marker": {"kind": "role", "role": "textbox", "name": "Email"}
  }
}
```

Notes for the executor: prefer the center-horizontal alignment button over typing Position left when both exist (centering is the design intent and survives width changes). `divider_match` is `"name"` if GET exposes layer names, else `"uploads"` (Task 4 implements both).

- [ ] **Step 6: Write the discovery notes document**

Create `docs/discovery/2026-08-date-layer-editor-notes.md` containing: the recorded click path (ordered list of controls with labels), the per-group answer, the position calibration formula with the observed numbers, the personalization settings inventory, the reference product id, and any editor oddities (autosave behavior, toasts, group switching quirks). This document is what a repair session reads when Printify changes the editor.

- [ ] **Step 7: STOP: GATE (spec Phase 0 gate)**

Present to Evan: the config values, the calibration result, and the Brigham City draft now carrying its layer (he reviews it in the editor and publishes it himself when satisfied). Evan confirms the captured settings are canonical. Do not proceed until he does.

- [ ] **Step 8: Commit**

```bash
git add config/date_layer.json docs/discovery/2026-08-date-layer-editor-notes.md artifacts/date-layer/reference-product.json
git commit -m "docs: date-layer discovery session, editor calibration, canonical settings config"
```

---

### Task 3: Position math (offline, test-first)

**Files:**
- Create: `scripts/add_date_layer.py` (math functions only in this task)
- Create: `tests/test_add_date_layer.py`

**Interfaces:**
- Consumes: `spacing_defaults.json` `"dated"` block; calibration formula from the Task 2 notes.
- Produces: `area_inches() -> (w_in, h_in)`, `date_zone_from_divider(divider_y_norm: float, dated: dict) -> dict` (keys `center_x_in`, `center_y_in`, `width_in`, `height_in`), `editor_percent(zone: dict) -> (left_pct, top_pct)` rounded to 2 decimals, `norm_center(zone: dict) -> (x_norm, y_norm)`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_add_date_layer.py`:

```python
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
```

If the Task 2 calibration recorded a different anchor formula, adjust the two `editor_percent` expectations to the recorded formula before running; the notes are authoritative.

- [ ] **Step 2: Run to verify failure**

```bash
./.venv.nosync/bin/python tests/test_add_date_layer.py
```

Expected: `ModuleNotFoundError` or `ImportError` (script does not exist yet).

- [ ] **Step 3: Implement the math**

Create `scripts/add_date_layer.py`:

```python
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
```

- [ ] **Step 4: Run to verify pass**

```bash
./.venv.nosync/bin/python tests/test_add_date_layer.py
```

Expected: `all math tests passed`.

- [ ] **Step 5: Commit**

```bash
git add scripts/add_date_layer.py tests/test_add_date_layer.py
git commit -m "feat: date zone position math from divider layer and spacing constants"
```

---

### Task 4: Gating, divider detection, verification (offline, test-first)

**Files:**
- Modify: `scripts/add_date_layer.py` (append functions from Task 3's file; this is the same new file, not an existing-code edit)
- Modify: `tests/test_add_date_layer.py` (append tests)

**Interfaces:**
- Consumes: math functions from Task 3.
- Produces: `iter_back_placeholders(product) -> iterator of (group, placeholder)`, `is_text_layer(layer) -> bool`, `find_divider(placeholder) -> dict | None`, `group_is_dark(placeholder) -> bool`, `gate(product) -> (bool, str)`, `verify(product, cfg, dated) -> list[str]` (empty list means verified).

- [ ] **Step 1: Append the failing tests**

Append to `tests/test_add_date_layer.py`:

```python
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
```

Fixture note: the `text_layer` default `y=0.7206` is the computed date-zone center for a divider at `y=0.685` (12.2432 / 16.99). If Task 2's calibration changed the formula, recompute this fixture value from the recorded formula.

- [ ] **Step 2: Run to verify failure**

```bash
./.venv.nosync/bin/python tests/test_add_date_layer.py
```

Expected: `ImportError: cannot import name 'gate'`.

- [ ] **Step 3: Implement**

Append to `scripts/add_date_layer.py`:

```python
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
```

If the Task 2 notes recorded `divider_match: "uploads"` (GET layers carry no `name`), also append this fallback and switch `find_divider` callers to it via the config flag in Task 6:

```python
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
```

- [ ] **Step 4: Run to verify pass**

```bash
./.venv.nosync/bin/python tests/test_add_date_layer.py
```

Expected: `all math tests passed` then `all tests passed`.

- [ ] **Step 5: Commit**

```bash
git add scripts/add_date_layer.py tests/test_add_date_layer.py
git commit -m "feat: candidate gating and post-save verification for date layers"
```

---

### Task 5: Editor driver and first live run

**Files:**
- Create: `scripts/date_layer_editor.py`

**Interfaces:**
- Consumes: `config/date_layer.json` (selectors, settings), `SESSION_FILE` from `scripts/printify_login.py`, math from `scripts/add_date_layer.py`.
- Produces: `EditorDriver` context manager with `apply(product_id, plan) -> None` where `plan` is `{"left_pct": float, "top_pct": float, "groups": [{"dark": bool}]}`, and `LoggedOut` exception. Task 6 calls exactly this.

**Precondition (Phase 1 gate closure):** on a different day than Task 1, run:

```bash
./.venv.nosync/bin/python scripts/printify_login.py --check
```

Expected: `Session is valid.` If expired, Evan re-runs the headed login. Record the two passing dates in the commit message. This closes the spec's Phase 1 gate.

**Precondition (target draft):** one unpublished With Date draft missing its layer must exist. Sources: the next new-temple sweep, or a `--replace` regeneration Evan initiates. Evan picks the target. Do not manufacture targets any other way.

- [ ] **Step 1: Write the driver skeleton from the discovery notes**

Create `scripts/date_layer_editor.py`. The selector plumbing below is fixed; the flow inside `apply` MUST follow the click path recorded in `docs/discovery/2026-08-date-layer-editor-notes.md`, which overrides the representative flow shown here if they differ:

```python
"""Playwright driver for the Printify editor date-layer flow.

Mirrors Evan's manual click path exactly as recorded in
docs/discovery/2026-08-date-layer-editor-notes.md. That document is the
authority for the flow; update it and config/date_layer.json together
whenever Printify changes the editor.

Never clicks publish. Never deletes or moves existing layers.
"""

import json
from pathlib import Path

from playwright.sync_api import sync_playwright

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SESSION_FILE = PROJECT_ROOT / ".playwright" / "printify-session.json"


class LoggedOut(Exception):
    """Saved session is no longer valid. Re-run scripts/printify_login.py."""


def _locator(page, sel):
    if sel["kind"] == "role":
        return page.get_by_role(sel["role"], name=sel["name"])
    if sel["kind"] == "label":
        return page.get_by_label(sel["label"])
    if sel["kind"] == "text":
        return page.get_by_text(sel["text"])
    if sel["kind"] == "css":
        return page.locator(sel["css"])
    raise ValueError(f"unknown selector kind: {sel['kind']}")


class EditorDriver:
    def __init__(self, cfg, headed=True, slow_mo_ms=150):
        self.cfg = cfg
        self.headed = headed
        self.slow_mo_ms = slow_mo_ms

    def __enter__(self):
        if not SESSION_FILE.exists():
            raise LoggedOut("no session file")
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(
            headless=not self.headed, slow_mo=self.slow_mo_ms
        )
        self._context = self._browser.new_context(storage_state=str(SESSION_FILE))
        self.page = self._context.new_page()
        return self

    def __exit__(self, *exc):
        self._browser.close()
        self._pw.stop()
        return False

    def _sel(self, name):
        return _locator(self.page, self.cfg["selectors"][name])

    def _assert_logged_in(self):
        if self._sel("login_form_marker").is_visible(timeout=2000):
            raise LoggedOut("editor redirected to login")

    def open_product(self, product_id):
        url = self.cfg["editor_url_template"].format(product_id=product_id)
        self.page.goto(url, wait_until="networkidle")
        self._assert_logged_in()
        self._sel("layers_panel").wait_for(timeout=30_000)

    def has_text_layer(self):
        """In-editor idempotency guard, independent of the API-side gate."""
        return self._sel("existing_text_layer_marker").count() > 0

    def add_date_layer_to_current_group(self, dark):
        cfg = self.cfg
        self._sel("add_text_button").click()
        self._sel("text_input").fill(cfg["placeholder_text"])
        self._sel("font_family_input").fill(cfg["font_family"])
        self._sel("font_size_input").fill(str(cfg["font_size"]))
        color = cfg["font_color_dark_groups"] if dark else cfg["font_color_light_groups"]
        self._sel("color_input").fill(color)

    def position_layer(self, left_pct, top_pct):
        # Prefer the centering control for x; type only the vertical position.
        self._sel("center_horizontal_button").click()
        self._sel("position_top_input").fill(str(top_pct))
        self._sel("position_top_input").press("Enter")

    def enable_personalization(self):
        self._sel("personalization_toggle").click()

    def save(self):
        self._sel("save_button").click()
        self.page.wait_for_load_state("networkidle")

    def apply(self, product_id, plan):
        """Full recorded flow for one product. The discovery notes are the
        authority; keep this method in sync with them."""
        self.open_product(product_id)
        if self.has_text_layer():
            return
        for group in plan["groups"]:
            # Group switching per the discovery notes (control recorded there).
            self._sel("group_switcher").click()
            self._sel_group(group)
            self.add_date_layer_to_current_group(group["dark"])
            self.position_layer(plan["left_pct"], plan["top_pct"])
            self.enable_personalization()
        self.save()

    def _sel_group(self, group):
        # Selecting a specific group; implementation follows the discovery
        # notes' recorded control (tab list, dropdown, or thumbnails).
        raise NotImplementedError("implement from the discovery notes in this task")
```

Before proceeding, replace `_sel_group` and reconcile `apply` with the recorded click path, and add the `existing_text_layer_marker` and `group_switcher` selectors to `config/date_layer.json` from the notes. If discovery found `layer_per_group: false`, simplify `apply` accordingly (single add, per-group color override per the notes). The committed driver must contain no `NotImplementedError`.

- [ ] **Step 2: Dry connectivity test (no changes to any product)**

Write a throwaway three-liner (do not commit) that enters `EditorDriver`, opens the target draft with `open_product`, prints `has_text_layer()`, and exits without touching anything.

Run it. Expected: browser opens logged in, editor loads, prints `False`, exits cleanly.

- [ ] **Step 3: Live run on the target draft**

Drive the full `apply` on the one target product, headed so Evan can watch if he wants. Then verify via API:

```bash
./.venv.nosync/bin/python - <<'EOF'
import sys
sys.path.insert(0, ".")
from printify_client import PrintifyClient
from scripts.publish_drafts import load_config
from scripts.add_date_layer import verify, load_layer_config, load_dated_spacing

PRODUCT_ID = "REPLACE_WITH_TARGET_ID"
token, shop_id = load_config()
client = PrintifyClient(token, shop_id)
product = client._request("GET", f"/shops/{shop_id}/products/{PRODUCT_ID}.json")
problems = verify(product, load_layer_config(), load_dated_spacing())
print("VERIFIED" if not problems else "\n".join(problems))
EOF
```

Expected: `VERIFIED`. If not, fix the driver against the notes and re-run on the same draft (the in-editor guard makes re-runs safe: fix the broken layer by hand in the editor first if one was half-added, exactly as with a manual mistake).

- [ ] **Step 4: STOP: GATE (spec Phase 2 gate)**

Evan opens the draft in the Printify editor, compares it against his hand-built standard, and publishes it himself when satisfied. Do not proceed until he confirms.

- [ ] **Step 5: Commit**

```bash
git add scripts/date_layer_editor.py config/date_layer.json
git commit -m "feat: playwright editor driver, first live date layer verified (session checks passed on two days: <date1>, <date2>)"
```

---

### Task 6: Batch CLI, candidate listing, docs

**Files:**
- Modify: `scripts/add_date_layer.py` (append CLI; still the new file)
- Modify: `docs/decisions.md` (new bullet only)
- Modify: `README.md` (new lines only)

**Interfaces:**
- Consumes: `gate`, `verify`, math from Tasks 3 and 4; `EditorDriver` and `LoggedOut` from Task 5; `load_config` from `scripts/publish_drafts.py`.
- Produces: the operator-facing CLI.

- [ ] **Step 1: Append the CLI**

Append to `scripts/add_date_layer.py`:

```python
def all_products(client):
    page = 1
    while True:
        body = client._request("GET", f"/shops/{client.shop_id}/products.json?page={page}&limit=50")
        yield from body.get("data", [])
        if not body.get("next_page_url"):
            return
        page += 1


def build_plan(product, dated):
    """Compute the browser plan for one gated product. Uses the first group's
    divider (all groups share the same generated geometry)."""
    _, ph = next(iter_back_placeholders(product))
    zone = date_zone_from_divider(find_divider(ph)["y"], dated)
    left_pct, top_pct = editor_percent(zone)
    groups = [
        {"index": i, "dark": group_is_dark(p)}
        for i, (_, p) in enumerate(iter_back_placeholders(product))
    ]
    return {"left_pct": left_pct, "top_pct": top_pct, "groups": groups}


def main():
    import argparse

    from printify_client import PrintifyClient
    from scripts.publish_drafts import load_config
    from scripts.date_layer_editor import EditorDriver, LoggedOut

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-only", action="store_true", help="list candidates, change nothing")
    parser.add_argument("--product-id", help="run on this product only (still gated)")
    parser.add_argument("--headless", action="store_true", help="run the browser headless")
    args = parser.parse_args()

    token, shop_id = load_config()
    client = PrintifyClient(token, shop_id)
    cfg = load_layer_config()
    dated = load_dated_spacing()

    if args.product_id:
        summaries = [{"id": args.product_id}]
    else:
        summaries = [
            s for s in all_products(client)
            if " - With Date" in (s.get("title") or "") and not s.get("external")
        ]

    todo = []
    for summary in summaries:
        product = client._request("GET", f"/shops/{shop_id}/products/{summary['id']}.json")
        ok, reason = gate(product)
        marker = "ADD" if ok else "skip"
        print(f"{marker:5}  {product['title']}  ({reason})")
        if ok:
            todo.append(product)

    if args.report_only or not todo:
        print(f"\n{len(todo)} draft(s) need a date layer." + (" Report only." if args.report_only else ""))
        return

    done, failed = [], []
    try:
        with EditorDriver(cfg, headed=not args.headless) as driver:
            for product in todo:
                plan = build_plan(product, dated)
                try:
                    driver.apply(product["id"], plan)
                except LoggedOut:
                    raise
                except Exception as e:  # noqa: BLE001 - report and continue the batch
                    failed.append((product["title"], str(e)))
                    continue
                fresh = client._request("GET", f"/shops/{shop_id}/products/{product['id']}.json")
                problems = verify(fresh, cfg, dated)
                (done if not problems else failed).append(
                    (product["title"], "verified" if not problems else "; ".join(problems))
                )
    except LoggedOut:
        print("\nSession expired. Run: ./.venv.nosync/bin/python scripts/printify_login.py")
        return

    print("\nSummary:")
    for title, note in done:
        print(f"  OK    {title}  ({note})")
    for title, note in failed:
        print(f"  FAIL  {title}  ({note})")
    if failed:
        print("\nFailed drafts are untouched or fixable in the editor; the manual flow always works.")
    print("Review and publish in Printify by hand, as always. This script never publishes.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the offline tests (regression)**

```bash
./.venv.nosync/bin/python tests/test_add_date_layer.py
```

Expected: `all math tests passed` then `all tests passed`.

- [ ] **Step 3: Run report-only against the live shop**

```bash
./.venv.nosync/bin/python scripts/add_date_layer.py --report-only
```

Expected: every With Date product listed with a correct marker and reason; published ones and layered ones say skip; count line at the end. No browser opens.

- [ ] **Step 4: Update the docs**

Append one bullet to the decisions list in `docs/decisions.md`:

```markdown
- **Date layers are added by script, optionally.** `scripts/add_date_layer.py` drives the Printify editor via Playwright to add the date text layer and enable personalization on unpublished With Date drafts, positioned from the divider layer read via GET plus `spacing_defaults.json` dated constants. It runs only when Evan invokes it, never publishes, and touches nothing else; the manual editor flow remains the standing fallback and the off switch is simply not running it. Editor click path and calibration live in `docs/discovery/2026-08-date-layer-editor-notes.md`; a Printify editor redesign means a repair session against that document. Session auth via `scripts/printify_login.py` (gitignored `.playwright/`).
```

In `README.md`, add to the end-of-run sequence (new line only, after the publish_drafts step):

```markdown
4. (Optional) `scripts/add_date_layer.py` adds date text layers to With Date drafts via the browser; then review and publish those by hand in Printify. Skipping this step means adding layers manually, as before.
```

Adjust the list number to fit the existing sequence formatting.

- [ ] **Step 5: Commit**

```bash
git add scripts/add_date_layer.py docs/decisions.md README.md
git commit -m "feat: batch CLI for date layers, report mode, docs and decision record"
```

- [ ] **Step 6: STOP: GATE (spec Phase 3 gate)**

The gate closes on the next real sweep: Evan duplicates, sweeps, runs `add_date_layer.py`, and his only With Date work is review and publish. Evan confirms the sweep felt right and the layers matched his standard. Any friction found becomes a follow-up, not a silent fix.

---

## Self-review record

- Spec coverage: Phase 0 = Task 2, Phase 1 = Task 1 plus the Task 5 precondition (two-day session check), Phase 2 = Task 5, Phase 3 = Task 6. Position computation = Task 3 (divider GET plus spacing constants; sidecar fallback not needed since GET exposes what we need, and the uploads fallback in Task 4 covers the divider-name risk). Settings capture = Task 2. Reversibility: no existing code files modified, additive lines only, hard scope in `gate()`, in-editor guard in `has_text_layer()`, publish gate untouched. Security: session gitignored, credentials typed by Evan only, `LoggedOut` never attempts login.
- Task ordering vs spec: Task 1 (login tooling) runs before the discovery session because discovery drives the editor through the saved Playwright session, so the captured selectors match the exact browser the script will use. The spec's gates still close in order (Phase 0 gate in Task 2, Phase 1 gate closes at Task 5's precondition).
- Known unknowns are quarantined: everything selector- and flow-shaped resolves in Task 2 and is consumed as config plus notes, never guessed silently. Two driver methods are explicitly finished inside Task 5 Step 1 from the notes, and the step forbids committing an unfinished driver.
