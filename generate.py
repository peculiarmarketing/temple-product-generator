"""Temple product generator: the duplicate-then-edit pipeline.

Flow per temple per garment (see docs/decisions.md for why):
  1. Evan duplicates ANY suitable product of that garment in the Printify UI.
     The duplicate carries the API-invisible settings: mockup selections,
     personalization config (With Date sources only), shipping. The design on
     it does not matter; it is replaced wholesale.
  2. This script claims an unclaimed "Copy of ..." duplicate matching the
     garment's blueprint/provider (With Date copies go to the dated line),
     uploads the temple's art and rendered assets, computes the layout, and
     PUTs the design swap plus the real title onto it.
  3. Text layers cannot survive any API write; location text and the divider
     are rendered images. On dated products Evan re-adds the personalization
     text layer in the editor afterward.

Usage:
  python generate.py --temple Logan --garments cc1717 --dry-run
  python generate.py --temple Logan --garments cc1717 --test-suffix " GENERATOR TEST"
  python generate.py --temple Logan --garments cc1717 --duplicate-id <id>

Temple manifest (Temples/{Name}/manifest.json):
  {
    "slug": "logan",
    "official_name": "Logan Utah Temple",
    "location_line": "LOGAN, UTAH",
    "place_tokens": {"default": "Logan"},
    "art": {"black": "Logan black.svg", "white": "Logan white.svg"},
    "garments": ["cc1717"]
  }
"""

import argparse
import base64
import io
import json
import re
import sys
from datetime import datetime
from pathlib import Path

from PIL import Image

import layout
from layout import PROJECT_ROOT, TempleArt, load_art
from printify_client import PrintifyClient, PrintifyError, load_config

TEMPLES_DIR = PROJECT_ROOT.parent.parent / "Temples"
ASSETS_DIR = PROJECT_ROOT.parent.parent / "Important Elements"
LOGO_FILES = {"black": ASSETS_DIR / "Peculiar People Logo - Black.png",
              "white": ASSETS_DIR / "Peculiar People Logo - White.png"}
TARGET_ART_PX = 4096
COLORS = {"black": (0, 0, 0, 255), "white": (255, 255, 255, 255)}


def detect_art_files(folder):
    """Find the black and white temple SVGs in a folder root (never in
    subfolders, never the location text files)."""
    art = {}
    for color in ("black", "white"):
        hits = [p for p in folder.glob("*.svg")
                if color in p.name.lower() and "location text" not in p.name.lower()]
        if len(hits) != 1:
            raise SystemExit(f"Expected exactly one {color} SVG in {folder}, found "
                             f"{[p.name for p in hits] or 'none'}. Fix the folder or write a manifest.")
        art[color] = hits[0].name
    return art


def scaffold_manifest(temple_name):
    """Build a manifest automatically from temples.json plus the folder's
    art files. New temples need only a folder with two SVGs, provided the
    dataset has a VERIFIED location for them."""
    dataset = json.loads((PROJECT_ROOT / "temples.json").read_text())
    dataset.pop("_comment", None)
    entry = dataset.get(temple_name)
    if entry is None:
        raise SystemExit(
            f"{temple_name!r} has no manifest and is not in temples.json. Add it: look up the "
            f"temple's PHYSICAL city (churchofjesuschristtemples.org), add an entry with "
            f"verified=true, and re-run. Note the physical city can differ from the name "
            f"(Washington D.C. Temple prints KENSINGTON, MARYLAND).")
    if not entry.get("verified"):
        raise SystemExit(
            f"{temple_name!r} is in temples.json but unverified ({entry['location_line']!r}). "
            f"Verify the physical location against churchofjesuschristtemples.org, set "
            f"verified=true, and re-run. Do not guess.")
    folder = TEMPLES_DIR / temple_name
    manifest = {
        "slug": temple_name.lower().replace(" ", "-").replace(".", ""),
        "official_name": entry["official_name"],
        "location_line": entry["location_line"],
        "place_tokens": {"default": temple_name},
        "art": detect_art_files(folder),
        "garments": ["cc1717"],
        "scaffolded": True,
    }
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"scaffolded manifest for {temple_name}: {entry['location_line']} "
          f"({manifest['art']['black']} / {manifest['art']['white']})")
    return manifest


def load_manifest(temple_name):
    path = TEMPLES_DIR / temple_name / "manifest.json"
    if not path.exists():
        return scaffold_manifest(temple_name)
    m = json.loads(path.read_text())
    for color in ("black", "white"):
        art = TEMPLES_DIR / temple_name / m["art"][color]
        if not art.exists():
            raise SystemExit(f"Manifest names missing art file: {art}")
    return m


def bump_svg_resolution(svg_text, target_px=TARGET_ART_PX):
    """Raise the declared width/height so Printify rasterizes at print
    resolution. Preserves aspect; never touches the file on disk."""
    m = re.search(r'width="([0-9.]+)"\s+height="([0-9.]+)"', svg_text)
    if not m:
        return svg_text
    w, h = float(m.group(1)), float(m.group(2))
    factor = target_px / max(w, h)
    if factor <= 1:
        return svg_text
    return svg_text.replace(m.group(0), f'width="{round(w * factor)}" height="{round(h * factor)}"', 1)


def png_bytes(img):
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def location_text_images(temple_name, manifest, garment_cfg):
    """Evan's override files win; otherwise render with Alata and save the
    result into the temple folder so it is inspectable and reusable."""
    folder = TEMPLES_DIR / temple_name
    height_in = layout.location_text_height(garment_cfg)
    out = {}
    for color in ("black", "white"):
        override = layout.find_text_override(folder, color)
        if override:
            out[color] = (load_art(override), override.name, True)
            continue
        img = layout.render_text(manifest["location_line"], height_in,
                                 garment_cfg["print_area"]["dpi"], COLORS[color])
        name = f"{temple_name} location text {color}.png"
        img.save(folder / name)
        out[color] = (img, name, False)
    return out


def upload_assets(c, temple_name, manifest, garment_cfg, dry_run):
    """Upload everything one product needs; returns {asset_key: upload_id}.
    Uploads are content-deduplicated by Printify, so re-runs are idempotent."""
    folder = TEMPLES_DIR / temple_name
    uploads = {}

    def up(key, file_name, data_bytes):
        if dry_run:
            uploads[key] = f"DRY-{key}"
            print(f"  would upload {key}: {file_name} ({len(data_bytes)} bytes)")
            return
        resp = c.upload_image(file_name, base64.b64encode(data_bytes).decode())
        uploads[key] = resp["id"]
        print(f"  uploaded {key}: {file_name} -> {resp['id']} ({resp.get('width')}x{resp.get('height')})")

    for color in ("black", "white"):
        art_path = folder / manifest["art"][color]
        if art_path.suffix.lower() == ".svg":
            data = bump_svg_resolution(art_path.read_text()).encode()
        else:
            data = art_path.read_bytes()
        up(f"temple_{color}", art_path.name, data)

    texts = location_text_images(temple_name, manifest, garment_cfg)
    for color, (img, name, is_override) in texts.items():
        up(f"location_text_{color}", name, png_bytes(img))

    for color, path in LOGO_FILES.items():
        up(f"logo_{color}", path.name, path.read_bytes())

    if "dated" in garment_cfg["layout_profile"]:
        for color in ("black", "white"):
            img = layout.render_divider(garment_cfg, COLORS[color], garment_cfg["print_area"]["dpi"])
            up(f"divider_{color}", f"divider {color} 2in.png", png_bytes(img))

    return uploads, texts["black"][0]


def find_duplicate(c, garment_cfg):
    """Find unclaimed 'Copy of ...' products usable for this garment. Any
    duplicate of the right blueprint/provider works (Evan: 'it doesn't matter
    which one I duplicate'); the design is replaced wholesale. The one
    discriminator is 'With Date': only those duplicates carry the
    personalization config, so they are reserved for the dated line.
    Front-logo copies are ignored (test products)."""
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
    dated_garment = "dated" in garment_cfg["layout_profile"]
    dupes = []
    for p in items:
        title = p["title"].strip()
        if not title.lower().startswith("copy of"):
            continue
        if p.get("blueprint_id") != garment_cfg["blueprint_id"] or \
           p.get("print_provider_id") != garment_cfg["print_provider_id"]:
            continue
        if "front logo" in title.lower():
            continue
        if ("with date" in title.lower()) != dated_garment:
            continue
        dupes.append(p)
    return dupes, [p["title"] for p in items]


def check_title_collision(intended, all_titles, ignore_ids_titles=()):
    """The description skills resolve on exact title and hard-stop on
    ambiguity. Refuse to create a title that collides or nests with an
    existing one (Provo vs Provo City Center; Nauvoo vs Limited Edition)."""
    problems = []
    for t in all_titles:
        if t in ignore_ids_titles:
            continue
        if t == intended:
            problems.append(f"exact duplicate: {t!r}")
        elif t.startswith("Copy of ") or "TEMPLATE" in t.upper():
            continue
        elif intended in t or t in intended:
            problems.append(f"nests with existing: {t!r}")
    return problems


def detect_group_colors(duplicate):
    """Per print-area group, decide black or white art from the template's
    placeholder layer names. The largest image layer in the back placeholder
    is the temple slot; its name carries the color."""
    colors = []
    for area in duplicate["print_areas"]:
        back = next((ph for ph in area["placeholders"] if ph["position"] == "back"), None)
        if back is None or not back.get("images"):
            colors.append(None)
            continue
        images = [im for im in back["images"] if im.get("type") != "text/svg"]
        biggest = max(images, key=lambda im: im.get("scale", 0))
        name = (biggest.get("name") or "").lower()
        colors.append("white" if "white" in name else "black")
    return colors


def build_print_areas(duplicate, layers, uploads, garment_cfg):
    """Construct print_areas from scratch: same groups (variant_ids) as the
    duplicate, layers entirely from the computed layout, colored per group."""
    group_colors = detect_group_colors(duplicate)
    position = garment_cfg["print_area"]["position"]
    key_to_asset = {"temple": "temple_{c}", "location_text": "location_text_{c}",
                    "logo": "logo_{c}", "divider": "divider_{c}"}
    areas = []
    for area, color in zip(duplicate["print_areas"], group_colors):
        if color is None:
            areas.append({"variant_ids": area["variant_ids"], "placeholders": []})
            continue
        images = []
        for layer in layers:
            if layer["key"] == "date_zone":
                continue  # reserved space; the personalization layer is manual
            asset_key = key_to_asset[layer["key"]].format(c=color)
            images.append({"id": uploads[asset_key], "x": layer["x"], "y": layer["y"],
                           "scale": layer["scale"], "angle": 0})
        areas.append({"variant_ids": area["variant_ids"],
                      "placeholders": [{"position": position, "images": images}]})
    return areas


def generate_one(c, temple_name, garment_id, args):
    garment_cfg = json.loads((PROJECT_ROOT / "garments" / f"{garment_id}.json").read_text())
    manifest = load_manifest(temple_name)
    place = manifest["place_tokens"].get(garment_id, manifest["place_tokens"]["default"])
    title = garment_cfg["naming"]["title"].format(place=place) + (args.test_suffix or "")
    print(f"[{garment_id}] {temple_name} -> {title!r}")

    # 1. find the duplicate to edit
    if args.duplicate_id:
        duplicate = c.get_product(args.duplicate_id)
        all_titles = []
    elif args.fixture:
        duplicate = json.loads(Path(args.fixture).read_text())
        all_titles = []
        print(f"  using fixture duplicate {duplicate['id']} ({duplicate['title']!r})")
    else:
        dupes, all_titles = find_duplicate(c, garment_cfg)
        if not dupes:
            kind = "a With Date product" if "dated" in garment_cfg["layout_profile"] else \
                   f"any {garment_cfg['display_name']} product (not With Date, not front logo)"
            raise SystemExit(f"No usable 'Copy of ...' duplicate for {garment_id} in the shop. "
                             f"Duplicate {kind} in the Printify UI first.")
        duplicate = c.get_product(dupes[0]["id"])
        if len(dupes) > 1:
            print(f"  {len(dupes)} unclaimed duplicates available; claiming {duplicate['title']!r} "
                  f"({duplicate['id']})")

    # 2. title collision pre-check (skipped in test mode, which suffixes the title)
    if not args.test_suffix and not args.duplicate_id and not args.fixture:
        problems = check_title_collision(title, all_titles, ignore_ids_titles=(duplicate["title"],))
        if problems:
            raise SystemExit(f"Title collision for {title!r}:\n  " + "\n  ".join(problems))

    # 3. assets and layout
    uploads, text_img = upload_assets(c, temple_name, manifest, garment_cfg, args.dry_run)
    temple = TempleArt(TEMPLES_DIR / temple_name / manifest["art"]["black"])
    logo_img = load_art(LOGO_FILES["black"])
    layers = layout.compute_stack(temple, garment_cfg, text_img, logo_img.height / logo_img.width)
    areas = build_print_areas(duplicate, layers, uploads, garment_cfg)

    body = {"title": title, "print_areas": areas}
    if args.dry_run:
        out = PROJECT_ROOT / "artifacts" / "phase3" / f"dryrun_{temple_name.lower().replace(' ', '-')}_{garment_id}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"duplicate_id": duplicate["id"], "body": body}, indent=2))
        print(f"  dry run: body saved to {out.relative_to(PROJECT_ROOT)}, nothing sent")
        return {"garment": garment_id, "dry_run": True, "title": title}

    # 4. the swap
    c.update_product(duplicate["id"], body)
    after = c.get_product(duplicate["id"])
    n_groups = len(after["print_areas"])
    print(f"  PUT ok: {after['title']!r}, {n_groups} groups")
    if "dated" in garment_cfg["layout_profile"]:
        print("  REMINDER: re-add the personalization text layer in the Printify editor.")
    return {"garment": garment_id, "product_id": duplicate["id"], "title": after["title"]}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--temple", required=True, help="Temple folder name, e.g. 'Logan'")
    ap.add_argument("--garments", help="Comma-separated garment ids; default: manifest's list")
    ap.add_argument("--dry-run", action="store_true", help="No API writes; save the would-be body")
    ap.add_argument("--test-suffix", help='e.g. " GENERATOR TEST": skips collision abort, marks title')
    ap.add_argument("--duplicate-id", help="Explicit product id to edit instead of searching")
    ap.add_argument("--fixture", help="Path to a saved product JSON to use as the duplicate (offline test)")
    ap.add_argument("--scaffold-only", action="store_true",
                    help="Only create the manifest (from temples.json) and exit")
    args = ap.parse_args()

    if args.scaffold_only:
        load_manifest(args.temple)
        return

    c = None if (args.dry_run and args.fixture) else PrintifyClient(*load_config())
    manifest = load_manifest(args.temple)
    garment_ids = args.garments.split(",") if args.garments else manifest.get("garments", [])
    if not garment_ids:
        raise SystemExit("No garments requested and manifest lists none.")

    results, errors = [], []
    for gid in garment_ids:
        try:
            results.append(generate_one(c, args.temple, gid.strip(), args))
        except (PrintifyError, SystemExit) as e:
            errors.append({"garment": gid, "error": str(e)})
            print(f"  ERROR [{gid}]: {e}")

    status = {"generated_at": datetime.now().isoformat(timespec="seconds"),
              "results": results, "errors": errors}
    if not args.dry_run and not args.fixture:
        (TEMPLES_DIR / args.temple / "status.json").write_text(json.dumps(status, indent=2))
        print(f"status.json written to the {args.temple} folder")
    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
