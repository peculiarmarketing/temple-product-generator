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

Temple manifest (Temples/{Name}/Working files/manifest.json):
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
import shutil
import sys
from datetime import datetime
from pathlib import Path

from PIL import Image

import layout
from description_html import compose_description
from layout import (PROJECT_ROOT, TEMPLES_DIR, WORKING_DIR_NAME, TempleArt, load_art,
                    temple_manifests, working_path)
from printify_client import PrintifyClient, PrintifyError, load_config

# Flat folder of every temple's black SVG under its clean place-token name,
# kept for the digital download files. Not a temple folder; the sweep skips it.
ALL_ART_DIR = TEMPLES_DIR / "All"
ASSETS_DIR = PROJECT_ROOT.parent.parent / "Important Elements"
LOGO_FILES = {"black": ASSETS_DIR / "Peculiar People Logo - Black.png",
              "white": ASSETS_DIR / "Peculiar People Logo - White.png"}
TARGET_ART_PX = 4096
COLORS = {"black": (0, 0, 0, 255), "white": (255, 255, 255, 255)}
GARMENTS_DIR = PROJECT_ROOT / "garments"
CATALOG_CONFIG = PROJECT_ROOT / "config" / "catalog.json"

# Titles carry the temple in parentheses ("Essential Temple Tee (Logan)"),
# except the parent temple's, which carry the bare garment line. Anything
# reading a title back has to cope with both shapes.
PLACE_SUFFIX_RE = re.compile(r"\(([^()]+)\)\s*$")
DATED_MARKERS = ("with date", "personalizable date")
ONE_OFF_MARKER = "limited edition"


def load_catalog_config():
    return json.loads(CATALOG_CONFIG.read_text())


def parent_temple():
    """The temple whose products are the storefront's parent listings: bare
    garment titles, with every other temple's product reachable through the
    parent page's Easify Temple dropdown. All products publish ACTIVE on
    Shopify (Evan's 26 Aug 2026 decision); children published before that
    date remain UNLISTED but their URLs still resolve."""
    return load_catalog_config()["parent_temple"]


def load_garment_config(garment_id):
    return json.loads((GARMENTS_DIR / f"{garment_id}.json").read_text())


def build_title(garment_cfg, temple_name, place):
    """The one place a product title is composed. The parent temple gets the
    bare garment title; every other temple gets the parenthesized place."""
    if temple_name == parent_temple():
        return garment_cfg["naming"]["title_parent"]
    return garment_cfg["naming"]["title"].format(place=place)


def parent_titles():
    """Every garment's bare parent title, for reading a title back to a temple."""
    return {load_garment_config(p.stem)["naming"]["title_parent"]
            for p in GARMENTS_DIR.glob("*.json")}


def title_is_dated(title):
    """True for the personalizable line. Matches the current wording and the
    retired ' - With Date' suffix, because Printify duplicates and older
    products carry both."""
    t = (title or "").lower()
    return any(marker in t for marker in DATED_MARKERS)


def title_is_one_off(title):
    """Limited Edition products are Evan's hand-built one-offs (front-logo
    designs, the Nauvoo limited run). The pipeline never claims one as a
    duplicate, never auto-publishes one, and never gives one a dropdown row."""
    return ONE_OFF_MARKER in (title or "").lower()


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


def ensure_art_files(folder, temple_name):
    """SVG pair, tracing it from the source PNG if needed. The trace only
    stands if it passes the tracer skill's health checks."""
    try:
        return detect_art_files(folder)
    except SystemExit:
        from trace_art import find_source_png, trace_temple
        if find_source_png(folder, temple_name) is None:
            raise
        trace_temple(folder, temple_name)
        return detect_art_files(folder)


def scaffold_manifest(temple_name):
    """Build a manifest automatically from temples.json plus the folder's
    art files. New temples need only a folder with two SVGs, provided the
    dataset has a VERIFIED location for them."""
    dataset = json.loads((PROJECT_ROOT / "temples.json").read_text())
    dataset.pop("_comment", None)
    # A trailing '*' is Evan's ref-finder marker on the FOLDER, never part of the
    # temple's name. Left in, it reaches the dataset lookup (which misses), the
    # slug, the Temples/All mirror filename, and worst of all the place token,
    # which is what prints in the product title: "Essential Temple Tee (Lehi*)".
    # Hand-written manifests already strip it (see West Jordan*); scaffolded ones
    # must too.
    clean_name = temple_name.rstrip("*").strip()
    entry = dataset.get(temple_name) or dataset.get(clean_name)
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
        "slug": clean_name.lower().replace(" ", "-").replace(".", ""),
        "official_name": entry["official_name"],
        "location_line": entry["location_line"],
        "place_tokens": {"default": clean_name},
        "art": ensure_art_files(folder, temple_name),
        "garments": "all",
        "scaffolded": True,
    }
    working_path(temple_name, "manifest.json", for_write=True).write_text(
        json.dumps(manifest, indent=2))
    print(f"scaffolded manifest for {temple_name}: {entry['location_line']} "
          f"({manifest['art']['black']} / {manifest['art']['white']})")
    return manifest


def mirror_black_art(temple_name, manifest):
    """Duplicate the temple's black SVG into Temples/All/ under its clean
    place-token name (folder names can carry ref-finder stars and old
    spellings; the token is the customer-facing name). Refreshes the copy
    when the source art is newer; the source is never touched."""
    src = TEMPLES_DIR / temple_name / manifest["art"]["black"]
    dest = ALL_ART_DIR / f"{manifest['place_tokens']['default']} black.svg"
    if dest.exists() and dest.stat().st_mtime >= src.stat().st_mtime:
        return
    ALL_ART_DIR.mkdir(exist_ok=True)
    shutil.copy2(src, dest)
    print(f"  mirrored {src.name} -> Temples/All/{dest.name}")


def load_manifest(temple_name):
    path = working_path(temple_name, "manifest.json")
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


TEXT_RENDER_PX = 600  # fixed tall render; every profile downscales, so text stays crisp


def location_text_images(temple_name, manifest, garment_cfg):
    """Evan's override files win; otherwise render with Alata at a fixed
    generous resolution, always fresh, and save '(auto)' copies into the
    temple's working folder for inspection. '(auto)' files are never read back
    as input, so a stale render can't outlive a manifest edit. The override
    lookup stays on the folder root, which is where Evan puts his own files."""
    folder = TEMPLES_DIR / temple_name
    out = {}
    for color in ("black", "white"):
        override = layout.find_text_override(folder, color)
        if override:
            out[color] = (load_art(override), override.name, True)
            continue
        img = layout.render_text(manifest["location_line"], TEXT_RENDER_PX / 300, 300, COLORS[color])
        name = f"{temple_name} location text {color} (auto).png"
        img.save(working_path(temple_name, name, for_write=True))
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


_PRODUCTS_CACHE = None


def fetch_all_products(c, refresh=False):
    """One product list per run; generated titles are appended by callers."""
    global _PRODUCTS_CACHE
    if _PRODUCTS_CACHE is not None and not refresh:
        return _PRODUCTS_CACHE
    _PRODUCTS_CACHE = c.all_products()
    return _PRODUCTS_CACHE


def fixed_description(garment_cfg):
    """The garment's verbatim fixed sections, behind an optional
    garment-specific block (the dated line's Personalization section). Set at
    swap time so a published draft never carries the donor temple's facts; the
    description event later replaces the whole field with these fixed sections
    plus verified temple facts.

    Copy lives per garment in reference/garment-copy/{garment_id}/ rather than
    inside a per-blank description skill. Two shapes exist. Garments with a
    product-details.html assemble as details -> intro (Evan, 16 Sep 2026: the
    product-specific details lead, the size guide drops out of the description
    entirely, and compose_description() still appends temple facts last).
    Garments without one -- the retiring Printify CC1566/1567/1717 configs --
    keep the older intro -> size-guide shape they were built with. A garment
    whose copy is missing still returns empty, which is the point: an empty
    description beats the wrong garment's specifications on a live page."""
    assets = PROJECT_ROOT / (garment_cfg.get("garment_copy")
                             or f"reference/garment-copy/{garment_cfg['garment_id']}")
    intro = assets / "product-intro.html"
    details = assets / "product-details.html"
    guide = assets / "size-guide.html"
    if details.exists():
        if not intro.exists():
            return ""  # empty beats a wrong temple's history on a live page
        fixed_parts = [details.read_text().strip(), intro.read_text().strip()]
    else:
        if not (intro.exists() and guide.exists()):
            return ""  # empty beats a wrong temple's history on a live page
        fixed_parts = [intro.read_text().strip(), guide.read_text().strip()]
    parts = []
    prefix = garment_cfg.get("description_prefix")
    if prefix:
        prefix_path = PROJECT_ROOT / prefix
        if not prefix_path.exists():
            raise SystemExit(f"{garment_cfg['garment_id']}: description_prefix "
                             f"{prefix} is missing; refusing to write a partial description.")
        parts.append(prefix_path.read_text().strip())
    parts += fixed_parts
    return "\n\n".join(parts)


def find_duplicate(c, garment_cfg):
    """Find unclaimed 'Copy of ...' products usable for this garment. Any
    duplicate of the right blueprint/provider works (Evan: 'it doesn't matter
    which one I duplicate'); the design is replaced wholesale. The one
    discriminator is the dated line: only those duplicates carry the
    personalization config, so they are reserved for it.
    Limited Edition copies are ignored (Evan's hand-built one-offs)."""
    items = fetch_all_products(c)
    dated_garment = "dated" in garment_cfg["layout_profile"]
    dupes = []
    for p in items:
        title = p["title"].strip()
        if not title.lower().startswith("copy of"):
            continue
        if p.get("blueprint_id") != garment_cfg["blueprint_id"] or \
           p.get("print_provider_id") != garment_cfg["print_provider_id"]:
            continue
        if title_is_one_off(title):
            continue
        if title_is_dated(title) != dated_garment:
            continue
        dupes.append(p)
    return dupes, [p["title"] for p in items]


def check_title_collision(intended, all_titles, ignore_ids_titles=()):
    """Refuse to create a title that already exists. Exact match is the whole
    check now: the place token is parenthesized and sits at the end, so
    'Essential Temple Tee (Provo)' can no longer nest inside 'Essential Temple
    Tee (Provo City Center)' the way the old prefix titles did. The parent
    temple's bare title is a prefix of every child title by design, which is
    exactly what the retired nesting rule would have flagged 117 times."""
    problems = []
    for t in all_titles:
        if t in ignore_ids_titles:
            continue
        if t.startswith("Copy of ") or "TEMPLATE" in t.upper() or title_is_one_off(t):
            continue
        if t == intended:
            problems.append(f"exact duplicate: {t!r}")
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
    garment_cfg = load_garment_config(garment_id)
    manifest = load_manifest(temple_name)
    place = manifest["place_tokens"].get(garment_id, manifest["place_tokens"]["default"])
    title = build_title(garment_cfg, temple_name, place) + (args.test_suffix or "")
    print(f"[{garment_id}] {temple_name} -> {title!r}")

    # 1. find the product to edit
    if getattr(args, "in_place", False):
        # Backfill path: regenerate the design onto the EXISTING live product,
        # keeping its title, Shopify URL, mockups, and settings.
        matches = [p for p in fetch_all_products(c) if p["title"].strip() == title]
        if len(matches) != 1:
            raise SystemExit(f"--in-place needs exactly one product titled {title!r}; "
                             f"found {len(matches)}.")
        duplicate = c.get_product(matches[0]["id"])
        all_titles = []
    elif args.duplicate_id:
        duplicate = c.get_product(args.duplicate_id)
        all_titles = []
    elif args.fixture:
        duplicate = json.loads(Path(args.fixture).read_text())
        all_titles = []
        print(f"  using fixture duplicate {duplicate['id']} ({duplicate['title']!r})")
    else:
        dupes, all_titles = find_duplicate(c, garment_cfg)
        if not dupes:
            kind = "a personalizable date product" if "dated" in garment_cfg["layout_profile"] else \
                   f"any {garment_cfg['display_name']} product (not dated, not Limited Edition)"
            raise SystemExit(f"No usable 'Copy of ...' duplicate for {garment_id} in the shop. "
                             f"Duplicate {kind} in the Printify UI first.")
        duplicate = c.get_product(dupes[0]["id"])
        if len(dupes) > 1:
            print(f"  {len(dupes)} unclaimed duplicates available; claiming {duplicate['title']!r} "
                  f"({duplicate['id']})")

    # 2. title collision pre-check (skipped in test mode, which suffixes the title)
    if not args.test_suffix and not args.duplicate_id and not args.fixture:
        problems = check_title_collision(title, all_titles, ignore_ids_titles=(duplicate["title"],))
        if problems and args.replace:
            exact_only = all(p.startswith("exact duplicate") for p in problems)
            if exact_only:
                print(f"  --replace: creating alongside the existing product; retire the old one "
                      f"when publishing this draft")
                problems = []
        if problems:
            raise SystemExit(f"Title collision for {title!r}:\n  " + "\n  ".join(problems))

    # 3. assets and layout
    uploads, text_img = upload_assets(c, temple_name, manifest, garment_cfg, args.dry_run)
    temple = TempleArt(TEMPLES_DIR / temple_name / manifest["art"]["black"])
    logo_img = load_art(LOGO_FILES["black"])
    layers = layout.compute_stack(temple, garment_cfg, text_img, logo_img.height / logo_img.width,
                                  logo_override=manifest.get("dated_logo"))
    areas = build_print_areas(duplicate, layers, uploads, garment_cfg)

    # Full description when the temple's researched facts exist; fixed
    # sections alone otherwise. Keeps regeneration idempotent.
    fixed = fixed_description(garment_cfg)
    facts_path = working_path(temple_name, "temple-facts.html")
    facts = facts_path.read_text().strip() if (fixed and facts_path.exists()) else None
    description = compose_description(fixed, facts)
    body = {"title": title, "print_areas": areas, "description": description}
    if args.dry_run:
        out = PROJECT_ROOT / "artifacts" / "phase3" / f"dryrun_{temple_name.lower().replace(' ', '-')}_{garment_id}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"duplicate_id": duplicate["id"], "body": body}, indent=2))
        print(f"  dry run: body saved to {out.relative_to(PROJECT_ROOT)}, nothing sent")
        return {"garment": garment_id, "dry_run": True, "title": title}

    # 4. the swap
    c.update_product(duplicate["id"], body)
    after = c.get_product(duplicate["id"])
    if _PRODUCTS_CACHE is not None:
        _PRODUCTS_CACHE[:] = [p for p in _PRODUCTS_CACHE if p["id"] != duplicate["id"]] + \
                             [{"id": after["id"], "title": after["title"],
                               "blueprint_id": after["blueprint_id"],
                               "print_provider_id": after["print_provider_id"]}]
    n_groups = len(after["print_areas"])
    print(f"  PUT ok: {after['title']!r}, {n_groups} groups")
    if "dated" in garment_cfg["layout_profile"]:
        print("  REMINDER: re-add the personalization text layer in the Printify editor.")
    return {"garment": garment_id, "product_id": duplicate["id"], "title": after["title"]}


def write_status(temple_name, results, errors):
    status_path = working_path(temple_name, "status.json")
    status = json.loads(status_path.read_text()) if status_path.exists() else {"results": [], "errors": []}
    status_path = working_path(temple_name, "status.json", for_write=True)
    keep = {r["garment"] for r in results}
    status["results"] = [r for r in status.get("results", []) if r.get("garment") not in keep] + results
    status["errors"] = errors
    status["generated_at"] = datetime.now().isoformat(timespec="seconds")
    status_path.write_text(json.dumps(status, indent=2))


def all_garment_ids(channel="printify"):
    """Garment ids for one channel, or every id when channel is None.

    Defaults to printify because this module IS the Printify pipeline. The
    Tapstitch garments share the garments/ folder, and sweeping one of them
    through the Printify API would fail late and messily (no blueprint_id,
    no print provider), so they are filtered out at the source. A config
    with no channel is treated as printify: that was the only channel when
    the four Comfort Colors files were written."""
    ids = []
    for path in (PROJECT_ROOT / "garments").glob("*.json"):
        cfg = json.loads(path.read_text())
        if channel is None or cfg.get("channel", "printify") == channel:
            ids.append(path.stem)
    return sorted(ids)  # by stem, not filename: "cc1717" sorts before "cc1717-dated"


def sweep(c, args):
    """Morning-run behavior: walk every temple folder, figure out what is
    missing, generate what has a duplicate waiting, and report the rest.
    A garment is satisfied when a product with its intended title already
    exists in the shop (hand-built or generated)."""
    existing_titles = {p["title"].strip() for p in fetch_all_products(c)}
    rows, generated = [], 0
    for folder in sorted(TEMPLES_DIR.iterdir()):
        if not folder.is_dir() or folder.name.startswith((".", "1.")) or folder == ALL_ART_DIR:
            continue
        temple = folder.name
        try:
            if args.report_only:
                detect_art_files(folder)
            else:
                ensure_art_files(folder, temple)
        except SystemExit as e:
            state = "NO ART YET" if "no source PNG" in str(e) or "Expected exactly one" in str(e) \
                else f"TRACE FAILED: {str(e)[:70]}"
            rows.append((temple, "-", state))
            continue
        try:
            manifest = load_manifest(temple)
        except SystemExit as e:
            rows.append((temple, "-", f"NEEDS LOCATION VERIFICATION"))
            continue
        if not args.report_only:
            mirror_black_art(temple, manifest)
        listed = manifest.get("garments", "all")
        if listed == "all":
            garment_ids = all_garment_ids()
        else:
            known = set(all_garment_ids())
            garment_ids = [g for g in listed if g in known]
            # Filtering keeps a Tapstitch id in a manifest from reaching the
            # Printify API, but a dropped id must never be silent: before this
            # filter existed a typo'd id failed loudly at load_garment_config,
            # and a temple that quietly looks satisfied is worse than an error.
            for g in listed:
                if g not in known:
                    rows.append((temple, g, "UNKNOWN GARMENT in manifest, skipped"))
        results, errors = [], []
        # try/finally, not a plain call after the loop: a transient API fault
        # raises straight past the loop and used to take every product this
        # temple had already generated with it. The products existed on
        # Printify but status.json never recorded them, so the descriptions
        # step silently skipped them on the next run.
        try:
            for gid in garment_ids:
                cfg = load_garment_config(gid)
                place = manifest["place_tokens"].get(gid, manifest["place_tokens"]["default"])
                intended = build_title(cfg, temple, place)
                if intended in existing_titles:
                    rows.append((temple, gid, "exists"))
                    continue
                if args.report_only:
                    rows.append((temple, gid, "PENDING"))
                    continue
                try:
                    r = generate_one(c, temple, gid, args)
                    results.append(r)
                    existing_titles.add(intended)
                    generated += 1
                    rows.append((temple, gid, "GENERATED"))
                except SystemExit as e:
                    msg = str(e)
                    if "No usable 'Copy of" in msg:
                        rows.append((temple, gid, "WAITING FOR DUPLICATE"))
                    else:
                        errors.append({"garment": gid, "error": msg})
                        rows.append((temple, gid, f"ERROR: {msg[:60]}"))
        finally:
            if results or errors:
                write_status(temple, results, errors)
    print()
    print(f"{'Temple':<20} {'Garment':<14} State")
    for t, g, s in rows:
        if s != "exists" or args.verbose:
            print(f"{t:<20} {g:<14} {s}")
    n_exists = sum(1 for r in rows if r[2] == "exists")
    print(f"\n{n_exists} satisfied, {generated} generated, "
          f"{sum(1 for r in rows if 'WAITING' in r[2])} waiting for duplicates, "
          f"{sum(1 for r in rows if r[2] in ('PENDING',))} pending, "
          f"{sum(1 for r in rows if 'ERROR' in r[2])} errors, "
          f"{sum(1 for r in rows if r[2] == 'NO ART YET')} folders without art")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--temple", help="Temple folder name, e.g. 'Logan'")
    ap.add_argument("--sweep", action="store_true",
                    help="Walk all temple folders: generate what has duplicates waiting, report the rest")
    ap.add_argument("--report-only", action="store_true",
                    help="With --sweep: coverage report only, no API writes")
    ap.add_argument("--in-place", dest="in_place", action="store_true",
                    help="Backfill: PUT the design onto the EXISTING product with the intended title "
                         "(preserves Shopify URL and settings; publish manually afterward)")
    ap.add_argument("--verbose", action="store_true", help="With --sweep: also list satisfied rows")
    ap.add_argument("--garments", help="Comma-separated garment ids; default: manifest's list")
    ap.add_argument("--dry-run", action="store_true", help="No API writes; save the would-be body")
    ap.add_argument("--test-suffix", help='e.g. " GENERATOR TEST": skips collision abort, marks title')
    ap.add_argument("--duplicate-id", help="Explicit product id to edit instead of searching")
    ap.add_argument("--fixture", help="Path to a saved product JSON to use as the duplicate (offline test)")
    ap.add_argument("--scaffold-only", action="store_true",
                    help="Only create the manifest (from temples.json) and exit")
    ap.add_argument("--replace", action="store_true",
                    help="Permit an exact-title duplicate: the new draft replaces a live product, "
                         "which must be retired when the draft is published")
    args = ap.parse_args()

    if args.scaffold_only:
        load_manifest(args.temple)
        return

    if args.sweep:
        sweep(PrintifyClient(*load_config()), args)
        return
    if not args.temple:
        raise SystemExit("Pass --temple NAME, or --sweep for all temples.")

    c = None if (args.dry_run and args.fixture) else PrintifyClient(*load_config())
    manifest = load_manifest(args.temple)
    mirror_black_art(args.temple, manifest)
    listed = manifest.get("garments", "all")
    if args.garments:
        garment_ids = args.garments.split(",")
    elif listed == "all":
        # every garment config present; adding a config extends every temple
        garment_ids = sorted(p.stem for p in (PROJECT_ROOT / "garments").glob("*.json"))
    else:
        garment_ids = listed
    if not garment_ids:
        raise SystemExit("No garments requested and none configured.")

    results, errors = [], []
    try:
        for gid in garment_ids:
            try:
                results.append(generate_one(c, args.temple, gid.strip(), args))
            except (PrintifyError, SystemExit) as e:
                errors.append({"garment": gid, "error": str(e)})
                print(f"  ERROR [{gid}]: {e}")
    finally:
        if not args.dry_run and not args.fixture and (results or errors):
            write_status(args.temple, results, errors)
            print(f"status.json updated in {args.temple}/{WORKING_DIR_NAME}")
    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
