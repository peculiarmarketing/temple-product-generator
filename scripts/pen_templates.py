#!/usr/bin/env python
"""Wire the pen-drawn temple sections into the live theme's page layouts.

  python scripts/pen_templates.py preview [--dry-run]   # preview-only layouts, ?view=pen-preview
  python scripts/pen_templates.py golive [--dry-run] [--link shopify://collections/shop]
  python scripts/pen_templates.py revert                # put back what the last golive replaced

preview writes templates/index.pen-preview.json and templates/product.pen-preview.json,
which Shopify serves only when an address carries ?view=pen-preview, so customers never
see them. golive makes the same two changes to the real templates/index.json and
templates/product.json, and only after Evan's go at the review gate: the showcase goes
first on the homepage with the old slideshow disabled (not deleted), and the drawing band
goes straight after the main product section.

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

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from shopify_client import ShopifyClient  # noqa: E402
from scripts.swatches import theme_file  # noqa: E402
from scripts.web_drawings import main_theme_id, upsert_theme_files  # noqa: E402

SHOWCASE_ID = "pp_temple_showcase"
BAND_ID = "pp_temple_drawing"
INTERIM_LINK = "shopify://collections/temple-tees"
HOME_TEMPLES = "salt-lake, kirtland, nauvoo, logan, mexico-city, rome"
BACKUP_DIR = PROJECT_ROOT / "artifacts/pen_templates"
BANNER = re.compile(r"^\s*/\*.*?\*/\s*", re.S)
EXPECTED_INDEX = {("order",), ("sections", SHOWCASE_ID), ("sections", "hero", "disabled")}
EXPECTED_PRODUCT = {("order",), ("sections", BAND_ID)}


def split_banner(content):
    m = BANNER.match(content)
    banner = m.group(0) if m else ""
    return banner, json.loads(content[len(banner):])


def join_banner(banner, doc):
    return banner + json.dumps(doc, indent=2, ensure_ascii=False) + "\n"


def add_showcase(index_doc, link=INTERIM_LINK):
    doc = copy.deepcopy(index_doc)
    if SHOWCASE_ID in doc["sections"]:
        raise ValueError("this homepage already has the showcase")
    hero = doc["sections"]["hero"]
    slide = hero["blocks"][hero["block_order"][0]]["settings"]
    doc["sections"][SHOWCASE_ID] = {
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
    return doc


def add_band(product_doc):
    doc = copy.deepcopy(product_doc)
    if BAND_ID in doc["sections"]:
        raise ValueError("this product layout already has the drawing band")
    doc["sections"][BAND_ID] = {"type": "pp-temple-drawing", "settings": {}}
    doc["order"].insert(doc["order"].index("main") + 1, BAND_ID)
    return doc


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


EXPECTED = {"templates/index.json": EXPECTED_INDEX, "templates/product.json": EXPECTED_PRODUCT}


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
    for name, fn in (("templates/index.json", lambda d: add_showcase(d, link)),
                     ("templates/product.json", add_band)):
        content = theme_file(client, name)[1]
        banner, doc = split_banner(content)
        new = fn(doc)
        verify(doc, new, EXPECTED[name])
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
        if not revert_check(live, split_banner(files[name].decode())[1], EXPECTED[name]):
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
        p.add_argument("--link", default=INTERIM_LINK, help="the showcase button's link")
    sub.add_parser("revert")
    args = ap.parse_args(argv)
    return {"preview": cmd_preview, "golive": cmd_golive, "revert": cmd_revert}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
