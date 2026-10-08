"""Publish designs that were saved by hand in the Tapstitch editor.

The temple pipeline (tapstitch_run.py, sweep.py) builds every design itself and
keys everything on a temple: the title, the facts fragment, the tags, the
gallery and the Easify dropdown. A design Evan made in the editor has none of
that, so it goes through this script instead, driven by config/saved_designs.json.
The order is the same one every other route here keeps: build, check,
distribute, with distribute the only call that reaches the storefront.

Steps, per product (the number is the key in config/saved_designs.json):

  check       read-only. The template exists, is valid, is not already linked
              to a store product, and carries the configured colours (or will,
              once re-saved). The description files exist.
  resave      only for an entry with `resave_colours`: re-save the design with
              the configured colours, then read it back. Tapstitch only. (--apply)
  build       prefill, keep the configured colours, order the mockups for the
              side the design leads with, attach the composed description and
              price, create the store product. Nothing public.       (--apply)
  distribute  the one call with no undo. The time is recorded BEFORE the call,
              so a lost confirmation leads to polling Tapstitch, never a
              second call.                                         (--publish)

The Shopify half (DRAFT at once, product type, handle, tags, SEO, colour
renames, lead colour, alt text) is done separately; this script prints what it
needs per product. An entry is only acted on while its `approved` is true.

STATE lives in artifacts/tapstitch/saved-designs.json, written the moment each
id is known, so a re-run resumes rather than repeating a step.

  python scripts/publish_saved_design.py                      # check all, plan only
  python scripts/publish_saved_design.py --apply --only 2     # resave + build #2
  python scripts/publish_saved_design.py --apply --publish --only 2
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import tapstitch_api as T                                    # noqa: E402
from description_html import compose_description            # noqa: E402

CONFIG = ROOT / "config" / "saved_designs.json"
STATE_PATH = ROOT / "artifacts" / "tapstitch" / "saved-designs.json"


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_config():
    return json.loads(CONFIG.read_text())


def load_state():
    return json.loads(STATE_PATH.read_text()) if STATE_PATH.exists() else {}


def save_state(st):
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(st, indent=2, sort_keys=True))


def description(cfg, p):
    """details -> care -> intro, the same order generate.fixed_description()
    uses, shaped by compose_description(). Raises rather than publishing a
    product with part of its copy missing."""
    parts = [ROOT / p["details"], ROOT / cfg["care_copy"], ROOT / p["intro"]]
    missing = [str(x.relative_to(ROOT)) for x in parts if not x.exists()]
    if missing:
        raise SystemExit(f"description files missing: {', '.join(missing)}")
    return compose_description("\n\n".join(x.read_text().strip() for x in parts))


def problems(cfg, p, template, design):
    """What stops this product being built. Empty means ready."""
    out = []
    if not p.get("approved"):
        out.append("not approved in config/saved_designs.json")
    if template["templateId"] != p["template_id"]:
        out.append("template id mismatch")
    have = set(str(template["colorCode"]).split(","))
    want = {str(c) for c in p["colours"]}
    if have != want and not p.get("resave_colours"):
        out.append(f"template colours {sorted(have)} != configured {sorted(want)} "
                   "and resave_colours is not set")
    if design is None:
        out.append("not found in the Designs tab")
    elif (design.get("linkedStoresProductList") or {}).get("productCount"):
        out.append("already linked to a store product")
    elif not all(x.get("ok") for x in design.get("displayStatus") or []):
        out.append("Tapstitch marks the design not ok")
    for key in ("details", "intro"):
        if not (ROOT / p[key]).exists():
            out.append(f"missing {p[key]}")
    if str(p["lead_colour"]) not in want:
        out.append("lead colour is not one of the colours")
    return out


def find_design(s, template_id):
    page = 1
    while True:
        pg = T.designs(s, page=page, page_size=60)
        for d in pg["data"]:
            if d.get("templateId") == template_id:
                return d
        if page >= (pg.get("totalPage") or 1):
            return None
        page += 1


def payload_for(cfg, p, prefill):
    kept = T.filter_colours(prefill, p["colours"])
    body = T.store_product_payload(kept, p["title"], round(p["price_usd"] * 100),
                                   description(cfg, p))
    body["mockups"] = T.order_mockups(kept["mockups"], p["lead_side"],
                                      p["lead_colour"], p.get("drop_side"))
    return body


def shopify_checklist(key, p):
    print(f"  Shopify half for #{key}, through the connector, right after distribute:")
    print(f"    status DRAFT; productType {p['product_type']!r}; handle {p['handle']!r}")
    print(f"    tags {p['tags']}; renames {p['renames']}; lead colour first")
    print("    alt text on every image; SEO title and description; then read back")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", action="append", default=[], help="product key, repeatable")
    ap.add_argument("--apply", action="store_true", help="resave and build: Tapstitch only")
    ap.add_argument("--publish", action="store_true", help="distribute: reaches the store")
    a = ap.parse_args(argv)
    if a.publish and not (a.apply and a.only):
        sys.exit("--publish needs --apply and at least one --only")

    cfg = load_config()
    keys = a.only or sorted(cfg["products"])
    s = T.session()
    try:
        T.store_products(s, page_size=1)
    except T.TapstitchError as e:
        sys.exit(f"Not logged in to Tapstitch ({e}). Refresh TAPSTITCH_COOKIES.")
    st = load_state()

    for key in keys:
        p = cfg["products"][key]
        rec = st.setdefault(key, {"template_id": p["template_id"]})
        print(f"#{key} {p['design']}: {p['title']}")

        if rec.get("distribute_started_at"):
            print(f"  distribute already called at {rec['distribute_started_at']}; "
                  "check Shopify, never call it again")
            continue

        if not rec.get("store_product_id"):
            tpl = T.get_template(s, p["template_id"])
            bad = problems(cfg, p, tpl, find_design(s, p["template_id"]))
            if bad:
                print("  blocked: " + "; ".join(bad))
                continue
            if not a.apply:
                print("  ready (plan only)")
                continue
            have = set(str(tpl["colorCode"]).split(","))
            if p.get("resave_colours") and have != {str(c) for c in p["colours"]}:
                rec["resaved_commit"] = T.resave_colours(s, p["template_id"], p["colours"])
                rec["resaved_at"] = now()
                save_state(st)
                print(f"  re-saved with {p['colours']}: commit {rec['resaved_commit']}")
            prefill = T.store_product_prefill(s, cfg["store_id"], p["template_id"])
            rec["store_product_id"] = T.create_store_product(
                s, cfg["store_id"], payload_for(cfg, p, prefill))
            rec["built_at"] = now()
            save_state(st)
            print(f"  built store product {rec['store_product_id']} (not public)")

        if not a.publish:
            continue
        rec["distribute_started_at"] = now()
        save_state(st)
        T.distribute(s, [rec["store_product_id"]])
        rec["distributed_at"] = now()
        save_state(st)
        print("  distributed")
        shopify_checklist(key, p)


if __name__ == "__main__":
    main()
