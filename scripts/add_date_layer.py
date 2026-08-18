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


def all_products(client):
    page = 1
    while True:
        body = client._request("GET", f"/shops/{client.shop_id}/products.json?page={page}&limit=50")
        yield from body.get("data", [])
        if not body.get("next_page_url"):
            return
        page += 1


def group_colorway(product, group):
    """Resolve a print_areas group's colorway title (e.g. "Graphite") from
    the product's color option and the group's first variant.

    Read-only on its inputs. Returns None if anything needed is missing:
    no color option, no variant_ids, or the variant/value can't be found.
    This replaces the earlier scheme of clicking swatches by position in
    a fixed reference list, which misclicked whenever a product's dark
    group count or order did not match that list.
    """
    options = product.get("options") or []
    color_option = next((o for o in options if o.get("type") == "color"), None)
    if color_option is None:
        color_option = next(
            (o for o in options if str(o.get("name", "")).lower() == "colors"), None
        )
    if color_option is None:
        return None
    color_values = {v["id"]: v.get("title") for v in color_option.get("values", [])}

    variant_ids = group.get("variant_ids") or []
    if not variant_ids:
        return None
    variant = next(
        (v for v in product.get("variants", []) if v.get("id") == variant_ids[0]), None
    )
    if variant is None:
        return None
    for opt_id in variant.get("options", []):
        if opt_id in color_values:
            return color_values[opt_id]
    return None


def build_plan(product, dated):
    """Compute the browser plan for one gated product. Uses the first group's
    divider (all groups share the same generated geometry)."""
    _, ph = next(iter_back_placeholders(product))
    zone = date_zone_from_divider(find_divider(ph)["y"], dated)
    left_pct, top_pct = editor_percent(zone)
    # print_areas order puts the default/light group first (group 0), which
    # satisfies the driver's documented light-before-dark contract.
    groups = [
        {"dark": group_is_dark(ph), "colorway": group_colorway(product, grp)}
        for grp, ph in iter_back_placeholders(product)
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
        with EditorDriver(cfg) as driver:
            for product in todo:
                try:
                    plan = build_plan(product, dated)
                    driver.apply(product["id"], plan)
                    fresh = client._request("GET", f"/shops/{shop_id}/products/{product['id']}.json")
                    problems = verify(fresh, cfg, dated)
                except LoggedOut:
                    raise
                except Exception as e:  # noqa: BLE001 - report and continue the batch
                    failed.append((product["title"], str(e)))
                    continue
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
