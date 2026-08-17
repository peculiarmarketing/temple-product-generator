"""Phase 1 driver: prove the Printify API round-trip.

One subcommand per spec step (docs/temple-catalog-generator-plan.md, Phase 1).
Every subcommand saves its raw API response under artifacts/phase1/ and fails
loudly. Run from anywhere; paths are resolved from this file's location.
"""

import argparse
import base64
import json
import sys
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from printify_client import PrintifyClient, PrintifyError, load_config, writable_product_body

ART = PROJECT_ROOT / "artifacts" / "phase1"
STOREFRONT = "https://peculiarpeopleco.com"
EXPECTED_PRODUCT_TYPES = {"tee": "T-Shirt", "sweatshirt": "Sweatshirt", "hoodie": "Hoodie"}
FLOAT_TOL = 1e-4


def save(name, data):
    ART.mkdir(parents=True, exist_ok=True)
    path = ART / name
    path.write_text(json.dumps(data, indent=2))
    print(f"saved {path.relative_to(PROJECT_ROOT)}")
    return path


def load(name):
    return json.loads((ART / name).read_text())


def client():
    token, shop_id = load_config()
    return PrintifyClient(token, shop_id)


def cmd_shops(args):
    c = client()
    shops = c.get_shops()
    save("shops.json", shops)
    match = [s for s in shops if s.get("id") == c.shop_id]
    if not match:
        raise SystemExit(f"FAIL: shop {c.shop_id} not in response: {shops}")
    print(f"PASS: shop {c.shop_id} present: {match[0].get('title')} "
          f"(sales_channel: {match[0].get('sales_channel')})")


def cmd_list_candidates(args):
    c = client()
    items, page = [], 1
    while True:
        resp = c.list_products(page=page)
        data = resp.get("data", resp) if isinstance(resp, dict) else resp
        if not data:
            break
        items.extend(data)
        last = resp.get("last_page") if isinstance(resp, dict) else None
        if last is None or page >= last:
            break
        page += 1
    candidates = [
        {
            "id": p["id"],
            "title": p["title"],
            "blueprint_id": p.get("blueprint_id"),
            "visible": p.get("visible"),
            "is_locked": p.get("is_locked"),
            "print_area_groups": len(p.get("print_areas", [])),
        }
        for p in items
        if "temple tee" in p["title"].lower() and "api test" not in p["title"].lower()
    ]
    save("candidates.json", candidates)
    print(f"{len(items)} products in shop, {len(candidates)} tee candidates:\n")
    for p in candidates:
        print(f"  {p['id']}  groups={p['print_area_groups']}  visible={p['visible']}  {p['title']}")


def summarize_layers(product):
    groups = []
    for area in product.get("print_areas", []):
        placeholders = []
        for ph in area.get("placeholders", []):
            layers = []
            for im in ph.get("images", []):
                entry = {k: im.get(k) for k in ("id", "name", "type", "x", "y", "scale", "angle")}
                if im.get("type") == "text/svg":
                    entry.update({k: im.get(k) for k in (
                        "font_family", "font_size", "font_weight", "font_color",
                        "font_style", "input_text", "text_align")})
                layers.append(entry)
            placeholders.append({"position": ph["position"], "layers": layers})
        groups.append({"variant_ids": area["variant_ids"], "placeholders": placeholders})
    return groups


def cmd_fetch(args):
    c = client()
    product = c.get_product(args.product_id)
    save("reference_product.json", product)
    notes = {
        "id": product["id"],
        "title": product["title"],
        "blueprint_id": product["blueprint_id"],
        "print_provider_id": product["print_provider_id"],
        "variant_count": len(product.get("variants", [])),
        "enabled_variant_count": sum(1 for v in product.get("variants", []) if v.get("is_enabled")),
        "group_count": len(product.get("print_areas", [])),
        "groups": summarize_layers(product),
    }
    save("reference_notes.json", notes)
    print(f"{notes['title']}: blueprint {notes['blueprint_id']}, "
          f"provider {notes['print_provider_id']}, {notes['group_count']} print area groups, "
          f"{notes['enabled_variant_count']}/{notes['variant_count']} variants enabled")
    for i, g in enumerate(notes["groups"]):
        for ph in g["placeholders"]:
            names = [(l.get("name") or l.get("input_text") or l.get("id"),
                      l.get("type"), l.get("scale")) for l in ph["layers"]]
            print(f"  group {i} ({len(g['variant_ids'])} variants) {ph['position']}: {names}")


def cmd_create_test(args):
    c = client()
    reference = load("reference_product.json")
    body = writable_product_body(reference)
    body["title"] = f"{reference['title']} API TEST"
    save("post_body.json", body)
    created = c.create_product(body)
    save("create_response.json", created)
    (ART / "test_product_id.txt").write_text(str(created["id"]))
    print(f"created test product {created['id']}: {created['title']}")


def match_group(posted_area, returned_areas):
    want = set(posted_area["variant_ids"])
    for area in returned_areas:
        if set(area["variant_ids"]) == want:
            return area
    return None


def diff_layers(posted, returned, rows, where):
    if len(posted) != len(returned):
        rows.append(("FAIL", where, f"layer count {len(posted)} -> {len(returned)}"))
        return
    returned_by_id = {l.get("id"): l for l in returned}
    for pl in posted:
        is_text = pl.get("type") == "text/svg"
        rl = None
        if not is_text:
            rl = returned_by_id.get(pl.get("id"))
        else:
            matches = [l for l in returned if l.get("input_text") == pl.get("input_text")]
            rl = matches[0] if matches else None
        label = pl.get("input_text") or pl.get("id")
        if rl is None:
            rows.append(("FAIL", where, f"layer {label} missing after POST"))
            continue
        for k in ("x", "y", "scale", "angle"):
            pv, rv = pl.get(k), rl.get(k)
            if pv is not None and abs(float(pv) - float(rv)) > FLOAT_TOL:
                rows.append(("FAIL", where, f"layer {label} {k}: {pv} -> {rv}"))
        if is_text:
            for k in ("font_family", "font_size", "font_weight", "font_color", "font_style", "text_align"):
                if pl.get(k) != rl.get(k):
                    rows.append(("FAIL", where, f"text layer {label} {k}: {pl.get(k)} -> {rl.get(k)}"))
        rows.append(("PASS", where, f"layer {label} intact"))


def cmd_verify(args):
    c = client()
    test_id = (ART / "test_product_id.txt").read_text().strip()
    created = c.get_product(test_id)
    save("created_product.json", created)
    posted = load("post_body.json")

    rows = []
    rows.append(("PASS" if created["title"] == posted["title"] else "FAIL",
                 "title", f"{posted['title']} -> {created['title']}"))
    pa_posted, pa_returned = posted["print_areas"], created["print_areas"]
    rows.append(("PASS" if len(pa_posted) == len(pa_returned) else "FAIL",
                 "groups", f"count {len(pa_posted)} -> {len(pa_returned)}"))
    for i, area in enumerate(pa_posted):
        match = match_group(area, pa_returned)
        if match is None:
            rows.append(("FAIL", f"group {i}", "no returned group with identical variant_ids"))
            continue
        rows.append(("PASS", f"group {i}", f"variant_ids preserved ({len(area['variant_ids'])} variants)"))
        returned_ph = {p["position"]: p for p in match["placeholders"]}
        for ph in area["placeholders"]:
            rp = returned_ph.get(ph["position"])
            if rp is None:
                rows.append(("FAIL", f"group {i}", f"position {ph['position']} missing"))
                continue
            diff_layers(ph["images"], rp["images"], rows, f"group {i} {ph['position']}")

    failures = [r for r in rows if r[0] == "FAIL"]
    lines = ["# Round-trip diff: posted body vs GET after POST", "",
             f"Test product: {test_id}", "",
             "| Result | Where | Detail |", "|---|---|---|"]
    lines += [f"| {r[0]} | {r[1]} | {r[2]} |" for r in rows]
    lines += ["", f"**{'CLEAN ROUND-TRIP' if not failures else str(len(failures)) + ' FAILURES'}**"]
    (ART / "roundtrip_diff.md").write_text("\n".join(lines))
    print(f"saved artifacts/phase1/roundtrip_diff.md")
    print("CLEAN ROUND-TRIP" if not failures else f"{len(failures)} FAILURES:")
    for r in failures:
        print(f"  FAIL {r[1]}: {r[2]}")


def cmd_upload_test(args):
    c = client()
    svg = Path(args.svg) if args.svg else PROJECT_ROOT.parent.parent / "Temples" / "San Antonio" / "San Antonio black.svg"
    raw = svg.read_bytes()
    print(f"uploading {svg.name} ({len(raw)} bytes) as base64")
    try:
        resp = c.upload_image("api-test-temple.svg", base64.b64encode(raw).decode())
    except PrintifyError as e:
        save("upload_response.json", {"accepted": False, "status": e.status, "body": e.body[:2000]})
        print(f"REJECTED: HTTP {e.status}. Rasterization will be required in Phase 2.")
        return
    resp["accepted"] = True
    save("upload_response.json", resp)
    print(f"accepted: mime_type={resp.get('mime_type')} "
          f"size={resp.get('width')}x{resp.get('height')} id={resp.get('id')}")
    c.archive_upload(resp["id"])
    print("test upload archived from media library")


def cmd_delete_test(args):
    c = client()
    test_id = (ART / "test_product_id.txt").read_text().strip()
    c.delete_product(test_id)
    try:
        c.get_product(test_id)
        raise SystemExit(f"FAIL: product {test_id} still exists after DELETE. "
                         f"An API TEST product remains in the shop.")
    except PrintifyError as e:
        save("deletion.json", {"deleted": True, "get_status_after_delete": e.status})
        print(f"PASS: test product {test_id} deleted (GET now returns {e.status})")


def get_shopify_product_type(handle):
    # Public storefront JSON. Swappable for Admin API or a manual check if the
    # storefront ever becomes password protected.
    resp = requests.get(f"{STOREFRONT}/products/{handle}.json",
                        headers={"User-Agent": "peculiar-people-generator"}, timeout=30)
    resp.raise_for_status()
    return resp.json()["product"]["product_type"]


def cmd_product_type(args):
    listing = requests.get(f"{STOREFRONT}/products.json?limit=250",
                           headers={"User-Agent": "peculiar-people-generator"}, timeout=30).json()
    by_type = {}
    for p in listing["products"]:
        by_type.setdefault(p["product_type"], p["handle"])
    results = {}
    ok = True
    for garment, expected in EXPECTED_PRODUCT_TYPES.items():
        handle = by_type.get(expected)
        if handle is None:
            results[garment] = {"expected": expected, "found": None}
            ok = False
            print(f"FAIL: no published product with product_type {expected}")
            continue
        observed = get_shopify_product_type(handle)
        results[garment] = {"expected": expected, "handle": handle, "observed": observed}
        status = "PASS" if observed == expected else "FAIL"
        ok = ok and observed == expected
        print(f"{status}: {garment} ({handle}): product_type is {observed!r}")
    save("shopify_product_type.json", results)
    if not ok:
        raise SystemExit("product_type check failed")


def cmd_publish_check(args):
    shops = load("shops.json")
    listing = requests.get(f"{STOREFRONT}/products.json?limit=250",
                           headers={"User-Agent": "peculiar-people-generator"}, timeout=30).json()
    latest = max(p["published_at"] for p in listing["products"] if p.get("published_at"))
    assessment = {
        "sales_channel": [s.get("sales_channel") for s in shops],
        "latest_storefront_published_at": latest,
        "conclusion": "Assessed, not proven: recent publish timestamps show the publish "
                      "path working on the current plan. No test publish performed.",
    }
    save("publish_check.json", assessment)
    print(f"sales_channel: {assessment['sales_channel']}")
    print(f"latest published_at on storefront: {latest}")
    print(assessment["conclusion"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("shops").set_defaults(fn=cmd_shops)
    sub.add_parser("list-candidates").set_defaults(fn=cmd_list_candidates)
    p = sub.add_parser("fetch")
    p.add_argument("--product-id", required=True)
    p.set_defaults(fn=cmd_fetch)
    sub.add_parser("create-test").set_defaults(fn=cmd_create_test)
    sub.add_parser("verify").set_defaults(fn=cmd_verify)
    p = sub.add_parser("upload-test")
    p.add_argument("--svg")
    p.set_defaults(fn=cmd_upload_test)
    sub.add_parser("delete-test").set_defaults(fn=cmd_delete_test)
    sub.add_parser("product-type").set_defaults(fn=cmd_product_type)
    sub.add_parser("publish-check").set_defaults(fn=cmd_publish_check)
    args = parser.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
