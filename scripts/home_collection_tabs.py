#!/usr/bin/env python
"""Turn the homepage "Shop by garment" row into collection tabs.

  python scripts/home_collection_tabs.py preview [--dry-run]  # ?view=tabs-preview only
  python scripts/home_collection_tabs.py golive [--dry-run]   # the real templates/index.json
  python scripts/home_collection_tabs.py revert               # put back what golive replaced

The `browse` section (a featured-collection on All Designs, 3 cards) becomes
sections/pp-collection-tabs.liquid with four tabs: Hoodies, Tees, Sweatshirts and
All Products (Evan, 8 Oct 2026). It keeps its key and its place in the order, and
nothing else in the template may move: the new layout is compared with the live
one key by key before anything is sent.

preview and golive both upload the section and pp-home.css/js first, so a template
never names a section the theme does not have yet. golive saves the live
index.json to artifacts/pen_templates/<timestamp>-tabs/ before writing; revert
restores it only if the live file is still exactly what golive sent.
"""

import argparse
import copy
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from shopify_client import ShopifyClient  # noqa: E402
from scripts.pen_templates import changed_paths, join_banner, split_banner  # noqa: E402
from scripts.swatches import theme_file  # noqa: E402
from scripts.web_drawings import upsert_theme_files  # noqa: E402

SECTION_KEY = "browse"
TABS = [("Hoodies", "hoodies"), ("Tees", "tees"), ("Sweatshirts", "sweatshirts"),
        ("All Products", "temple-design-products")]
CODE = ["sections/pp-collection-tabs.liquid", "assets/pp-home.css", "assets/pp-home.js"]
PREVIEW = "templates/index.tabs-preview.json"
BACKUP_DIR = PROJECT_ROOT / "artifacts/pen_templates"


def tabs_section(old):
    """The new section, carrying over the old one's heading, image and spacing."""
    o = old["settings"]
    blocks = {f"tab_{handle.replace('-', '_')}": {
        "type": "collection_tab",
        "settings": {"label": label, "collection": handle, "limit": 16}}
        for label, handle in TABS}
    return {
        "type": "pp-collection-tabs",
        "blocks": blocks,
        "block_order": list(blocks),
        "settings": {
            "title": o.get("title", "Shop by garment"),
            "columns_desktop": 4,
            "image_ratio": o.get("image_ratio", "square"),
            "show_secondary_image": o.get("show_secondary_image", True),
            "color_scheme": o.get("color_scheme", "background-1"),
            "cards_color_scheme": o.get("cards_color_scheme", "background-1"),
            "padding_top": o.get("padding_top", 36),
            "padding_bottom": o.get("padding_bottom", 36),
        },
    }


def new_layout(doc):
    if doc["sections"].get(SECTION_KEY, {}).get("type") == "pp-collection-tabs":
        return None
    after = copy.deepcopy(doc)
    after["sections"][SECTION_KEY] = tabs_section(doc["sections"][SECTION_KEY])
    moved = {p[:2] for p in changed_paths(doc, after)}
    if moved - {("sections", SECTION_KEY)}:
        raise SystemExit(f"refusing: would also change {sorted(moved)}")
    return after


def serialise(banner, doc):
    return join_banner(banner, doc).encode()


def upload_code(client, theme_id):
    upsert_theme_files(client, theme_id, {n: (PROJECT_ROOT / "theme" / n).read_bytes()
                                          for n in CODE})
    print(f"uploaded {', '.join(CODE)}")


def cmd_write(args, target):
    client = ShopifyClient()
    theme_id, content = theme_file(client, "templates/index.json")
    banner, doc = split_banner(content)
    after = new_layout(doc)
    if after is None:
        print("templates/index.json already carries the tabs section.")
        return
    print(f"{SECTION_KEY}: featured-collection -> pp-collection-tabs "
          f"({', '.join(label for label, _ in TABS)})")
    if args.dry_run:
        return
    upload_code(client, theme_id)
    body = serialise(banner, after)
    if target == "templates/index.json":
        out = BACKUP_DIR / (time.strftime("%Y%m%d-%H%M%S") + "-tabs")
        out.mkdir(parents=True, exist_ok=True)
        (out / "index.json").write_text(content)
        (out / "index.after.json").write_bytes(body)
        print(f"backup: {out.relative_to(PROJECT_ROOT)}")
    upsert_theme_files(client, theme_id, {target: body})
    _, back = theme_file(client, target)
    if split_banner(back)[1] != after:
        raise SystemExit(f"{target}: read-back differs from what was sent")
    print(f"wrote {target}, read back")


def cmd_revert(_args):
    client = ShopifyClient()
    saves = sorted(BACKUP_DIR.glob("*-tabs"))
    if not saves:
        raise SystemExit("no tabs backup to restore.")
    save = saves[-1]
    theme_id, live = theme_file(client, "templates/index.json")
    sent = split_banner((save / "index.after.json").read_text())[1]
    if split_banner(live)[1] != sent:
        raise SystemExit("the live homepage changed since golive; not overwriting it.")
    upsert_theme_files(client, theme_id, {"templates/index.json":
                                          (save / "index.json").read_bytes()})
    print(f"restored templates/index.json from {save.relative_to(PROJECT_ROOT)}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("preview", "golive"):
        p = sub.add_parser(name)
        p.add_argument("--dry-run", action="store_true")
    sub.add_parser("revert")
    args = ap.parse_args(argv)
    if args.cmd == "revert":
        cmd_revert(args)
    else:
        cmd_write(args, PREVIEW if args.cmd == "preview" else "templates/index.json")


if __name__ == "__main__":
    main()
