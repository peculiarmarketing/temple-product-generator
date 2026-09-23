#!/usr/bin/env python
"""Wire the pen-drawn temple sections into the live theme's page layouts.

  python scripts/pen_templates.py preview [--dry-run]   # preview-only layouts, ?view=pen-preview
  python scripts/pen_templates.py golive [--dry-run] [--link shopify://collections/<handle>]
  python scripts/pen_templates.py revert                # put back what the last golive replaced

preview writes templates/index.pen-preview.json and templates/product.pen-preview.json,
which Shopify serves only when an address carries ?view=pen-preview, so customers never
see them. golive makes the same changes to the real templates/index.json and
templates/product.json, and only after Evan's go at the review gate. Homepage: the
showcase goes first, the old slideshow and the Browse row are switched off (not deleted),
"The temples" row shows Temple Design Products, and the remaining orange buttons turn
navy. Product page: the drawing band goes straight after the main product section, Add to
Cart (buy buttons and sticky bar) turns orange, and the before/after slider labels become
THE TEMPLE / THE DRAWING. homepage_layout and product_layout hold the full list.

Every write is checked first: the new layout is compared with the live one key by key,
and nothing is sent if anything beyond the intended change would move. golive saves both
live files to artifacts/pen_templates/<timestamp>/ before writing, and revert restores
the newest save, but only if the live layouts are still exactly that save plus golive's
change; an edit made in the theme editor since then makes it refuse rather than wipe it.
Unlike config/settings_data.json in swatches.py, these layouts are re-serialised whole:
adding a section is a structural edit, and the key-by-key check is what guarantees
nothing else changed. Do not run golive or revert with the theme editor
open on the live theme; the editor saves whole files and the last save wins.
"""

import argparse
import copy
import json
import re
import sys
import time
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from shopify_client import ShopifyClient  # noqa: E402
from scripts.swatches import theme_file  # noqa: E402
from scripts.web_drawings import main_theme_id, upsert_theme_files  # noqa: E402

SHOWCASE_ID = "pp_temple_showcase"
BAND_ID = "pp_temple_drawing"
COLLECTION = "temple-design-products"
COLLECTION_LINK = f"shopify://collections/{COLLECTION}"
HOME_TEMPLES = "salt-lake, kirtland, nauvoo, logan, mexico-city, rome"
ORANGE = "#F58000"  # Add to Cart only
NAVY = "#001A58"    # every other button
# Homepage sections whose orange button turns navy.
NAVY_BUTTON_SECTIONS = ("process", "suggest_form")
BACKUP_DIR = PROJECT_ROOT / "artifacts/pen_templates"
BANNER = re.compile(r"^\s*/\*.*?\*/\s*", re.S)


def split_banner(content):
    m = BANNER.match(content)
    banner = m.group(0) if m else ""
    return banner, json.loads(content[len(banner):])


def join_banner(banner, doc):
    return banner + json.dumps(doc, indent=2, ensure_ascii=False) + "\n"


def _block_id(blocks, block_type):
    ids = [k for k, b in blocks.items() if b.get("type") == block_type]
    if len(ids) != 1:
        raise ValueError(f"expected one {block_type} block, found {len(ids)}")
    return ids[0]


def _section_id(doc, section_type):
    ids = [k for k, sec in doc["sections"].items() if sec.get("type") == section_type]
    if len(ids) != 1:
        raise ValueError(f"expected one {section_type} section, found {len(ids)}")
    return ids[0]


def homepage_layout(index_doc, link=COLLECTION_LINK):
    """The showcase goes first and the old slideshow is switched off (kept, not deleted).
    "The temples" row shows the Temple Design Products collection, the Browse row (whose
    state-collection cards died with those collections) is switched off, and the other
    orange buttons turn navy so Add to Cart is the only orange one."""
    doc = copy.deepcopy(index_doc)
    if SHOWCASE_ID in doc["sections"]:
        raise ValueError("this homepage already has the showcase")
    sections = doc["sections"]
    hero = sections["hero"]
    slide = hero["blocks"][hero["block_order"][0]]["settings"]
    sections[SHOWCASE_ID] = {
        "type": "pp-temple-showcase",
        "settings": {
            "heading": slide["heading"],
            "subheading": slide.get("subheading", ""),
            "button_label": slide.get("button_label", ""),
            "link": link,
            "temples": HOME_TEMPLES,
        },
    }
    doc["order"].insert(0, SHOWCASE_ID)
    hero["disabled"] = True
    sections["browse"]["disabled"] = True
    sections["featured_products"]["settings"]["collection"] = COLLECTION
    for sec in NAVY_BUTTON_SECTIONS:
        sections[sec]["settings"]["custom_colors_solid_button_background"] = NAVY
    return doc


def product_layout(product_doc):
    """The drawing band goes straight after the main product section. Add to Cart, in the
    buy buttons and the sticky bar, turns orange (it was blue #0035B2); the before/after
    slider says THE TEMPLE / THE DRAWING."""
    doc = copy.deepcopy(product_doc)
    if BAND_ID in doc["sections"]:
        raise ValueError("this product layout already has the drawing band")
    doc["sections"][BAND_ID] = {"type": "pp-temple-drawing", "settings": {}}
    doc["order"].insert(doc["order"].index("main") + 1, BAND_ID)
    details = doc["sections"]["main"]["blocks"]["Details"]["blocks"]
    buy = details[_block_id(details, "product_buy-buttons")]["settings"]
    buy["enable_custom_color"] = True
    buy["custom_color"] = ORANGE
    sticky = details[_block_id(details, "product_sticky-atc")]["settings"]
    sticky["enable_custom_btn_color"] = True
    sticky["custom_btn_color"] = ORANGE
    slider = doc["sections"][_section_id(doc, "comparison-slider")]["settings"]
    slider["before_label"], slider["after_label"] = "THE TEMPLE", "THE DRAWING"
    return doc


def collection_problem(link, domain, get=None):
    """Why golive must wait, or None. A button to a collection that is not on the Online
    Store is a link to a missing page, and "The temples" row would show Shopify's
    placeholder products. The admin token cannot read publishing, so this asks the
    storefront itself."""
    m = re.fullmatch(r"shopify://collections/([\w-]+)", link)
    if not m:
        return None
    get = get or (lambda url: requests.get(url, timeout=20).status_code)
    status = get(f"https://{domain}/collections/{m.group(1)}")  # products.json answers 200 for anything
    if status == 200:
        return None
    return (f"collection '{m.group(1)}' is not on the Online Store yet (storefront said {status}). "
            f"Publish it first: Shopify admin > Products > Collections > it > Sales channels > "
            f"Online Store. Nothing sent.")


def expected_paths(name, before_doc):
    """Every setting golive is allowed to change in this layout, and nothing else.
    Settings already at their new value do not change, so they drop out."""
    after = homepage_layout(before_doc) if name.endswith("index.json") else product_layout(before_doc)
    return changed_paths(before_doc, after)


def changed_paths(a, b, prefix=()):
    if isinstance(a, dict) and isinstance(b, dict):
        out = set()
        for k in set(a) | set(b):
            if k not in a or k not in b:
                out.add(prefix + (k,))
            elif a[k] != b[k]:
                out |= changed_paths(a[k], b[k], prefix + (k,))
        return out
    return set() if a == b else {prefix}


def verify(before, after, expected):
    moved = changed_paths(before, after)
    if moved != expected:
        raise SystemExit(f"the edit would change {sorted(moved)}, expected exactly "
                         f"{sorted(expected)}. Nothing sent.")


def revert_check(live_doc, saved_doc, expected):
    """True when the live layout is exactly the saved one plus golive's change (safe to
    revert), False when it is already back to the saved copy. Anything else, such as an
    edit or a section reorder made in the theme editor since golive, stops with nothing
    sent, because restoring the saved copy would wipe it."""
    moved = changed_paths(saved_doc, live_doc)
    if not moved:
        return False
    added = {p[1] for p in expected if p[0] == "sections" and len(p) == 2}
    reordered = [k for k in live_doc.get("order", []) if k not in added] != saved_doc.get("order")
    if moved != expected or reordered:
        extra = sorted(moved - expected) or (["order"] if reordered else sorted(expected - moved))
        raise SystemExit(f"the live layout has changed since golive at {extra}. "
                         f"Reverting would wipe that. Nothing sent; remove the pp_ sections in the "
                         f"theme editor instead, or save that edit elsewhere first.")
    return True


def planned(client, link):
    """[(filename, live raw content, live banner, new doc)] for both layouts, each verified.
    The raw content is what golive backs up, so the backup is the exact file that was checked."""
    out = []
    for name, fn in (("templates/index.json", lambda d: homepage_layout(d, link)),
                     ("templates/product.json", product_layout)):
        content = theme_file(client, name)[1]
        banner, doc = split_banner(content)
        new = fn(doc)
        verify(doc, new, expected_paths(name, doc))
        out.append((name, content, banner, new))
    return out


def cmd_preview(args):
    client = ShopifyClient()
    theme_gid = main_theme_id(client)
    files = {}
    for name, _content, _banner, new in planned(client, args.link):
        target = name.replace(".json", ".pen-preview.json")
        files[target] = join_banner("", new).encode()
        print(f"{target}: {len(new['order'])} sections, first {new['order'][:2]}")
    if args.dry_run:
        print("\nDRY RUN, nothing sent.")
        return 0
    upsert_theme_files(client, theme_gid, files)
    # Compare content, not bytes: Shopify may reformat a layout file when it saves it.
    wrong = [n for n in files if split_banner(theme_file(client, n)[1])[1] != json.loads(files[n])]
    if wrong:
        raise SystemExit(f"read-back mismatch on {wrong}")
    print("preview layouts written. Customers see nothing; add ?view=pen-preview to view.")
    return 0


def cmd_golive(args):
    client = ShopifyClient()
    theme_gid = main_theme_id(client)
    plans = planned(client, args.link)
    for name, _c, _b, new in plans:
        print(f"{name}: order becomes {new['order'][:3]} ...")
    problem = collection_problem(args.link, client.url.split("/")[2])
    if problem:
        raise SystemExit(problem)
    if args.dry_run:
        print("\nDRY RUN, nothing sent.")
        return 0
    stamp = BACKUP_DIR / time.strftime("%Y%m%d-%H%M%S")
    stamp.mkdir(parents=True)
    files = {}
    for name, content, banner, new in plans:
        (stamp / Path(name).name).write_text(content)
        files[name] = join_banner(banner, new).encode()
    print(f"live layouts saved to {stamp.relative_to(PROJECT_ROOT)}")
    upsert_theme_files(client, theme_gid, files)
    for name, _c, _b, new in plans:
        _, live = split_banner(theme_file(client, name)[1])
        if live != new:
            raise SystemExit(f"{name} read back different from what was sent. Run revert.")
    print("live. Undo with: scripts/pen_templates.py revert")
    return 0


def cmd_revert(_args):
    saves = sorted(p for p in BACKUP_DIR.glob("*") if p.is_dir()) if BACKUP_DIR.exists() else []
    if not saves:
        raise SystemExit("no golive backup found in artifacts/pen_templates/.")
    latest = saves[-1]
    files = {f"templates/{p.name}": p.read_bytes() for p in sorted(latest.glob("*.json"))}
    client = ShopifyClient()
    for name in list(files):
        live = split_banner(theme_file(client, name)[1])[1]
        saved = split_banner(files[name].decode())[1]
        if not revert_check(live, saved, expected_paths(name, saved)):
            print(f"{name} is already the saved copy; left alone.")
            del files[name]
    if not files:
        print("nothing to revert.")
        return 0
    upsert_theme_files(client, main_theme_id(client), files)
    for name, body in files.items():  # content, not bytes: Shopify may reformat on save
        if split_banner(theme_file(client, name)[1])[1] != split_banner(body.decode())[1]:
            raise SystemExit(f"{name} did not read back as the saved copy. Check it by hand.")
    print(f"restored {sorted(files)} from {latest.relative_to(PROJECT_ROOT)}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for cmd in ("preview", "golive"):
        p = sub.add_parser(cmd)
        p.add_argument("--dry-run", action="store_true")
        p.add_argument("--link", default=COLLECTION_LINK, help="the showcase button's link")
    sub.add_parser("revert")
    args = ap.parse_args(argv)
    return {"preview": cmd_preview, "golive": cmd_golive, "revert": cmd_revert}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
