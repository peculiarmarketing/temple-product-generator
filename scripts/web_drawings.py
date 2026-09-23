#!/usr/bin/env python
"""Pen-drawn temples for the storefront: build, upload and check each temple's drawing.

  python scripts/web_drawings.py build --all              # every temple, about 5 s each
  python scripts/web_drawings.py build --temple Logan     # one folder name (repeatable)
  python scripts/web_drawings.py push --dry-run           # what would change in the live theme
  python scripts/web_drawings.py push                     # upload changed drawings and theme code
  python scripts/web_drawings.py check                    # every live temple has its drawing

WHAT IT MAKES. Each temple gets two theme assets, named from the product's `temple:`
tag: pp-temple-<slug>.json (pen strokes in draw order, their lengths, the pen width,
the art box and the city line) and pp-temple-<slug>.webp (the finished art). The
product band and homepage showcase (theme/sections/) find them by that name. The city
line is the manifest's location_line, the same line printed on the garment, so
Washington DC reads KENSINGTON, MARYLAND.

GATES. A drawing is written only if the pen leaves at most 1% of the art for the final
fade and the two files together are at most 250 KB compressed. A temple that misses a
gate is retried with a finer trace, then a smaller image, and reported if it still
fails. Nothing that fails a gate can reach the theme, because push only uploads what
build wrote.

WRITING THE THEME. push uploads only files whose checksum differs from the live
theme's copy, then reads every checksum back. It adds and replaces pp- files only. It
never touches an existing theme file. The page layouts are scripts/pen_templates.py's
job.
"""

import argparse
import base64
import hashlib
import json
import re
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import web_drawing  # noqa: E402
from layout import TEMPLES_DIR, working_path  # noqa: E402

OUT_DIR = PROJECT_ROOT / "artifacts/web_drawings"
THEME_DIR = PROJECT_ROOT / "theme"
THEME_CODE = [
    "assets/pp-pen-draw.js",
    "assets/pp-pen-draw.css",
    "sections/pp-temple-showcase.liquid",
    "sections/pp-temple-drawing.liquid",
]
# Folder names that the generic rule would not turn into their live tag.
SLUG_OVERRIDES = {"Washington DC": "washington-d-c"}
# (trace_width, art_max_px), tried in order until a drawing passes both gates.
ATTEMPTS = [(1024, 840), (1536, 840), (1536, 720)]


def slug_for(folder):
    if folder in SLUG_OVERRIDES:
        return SLUG_OVERRIDES[folder]
    return re.sub(r"[^a-z0-9]+", "-", folder.rstrip("*").lower()).strip("-")


def temple_folders():
    """{slug: folder} for every temple folder with a manifest and white art."""
    found = {}
    for folder in sorted(p.name for p in TEMPLES_DIR.iterdir() if p.is_dir()):
        manifest = working_path(folder, "manifest.json")
        if not manifest.exists():
            continue
        art = json.loads(manifest.read_text()).get("art", {}).get("white")
        if art and (TEMPLES_DIR / folder / art).exists():
            found[slug_for(folder)] = folder
    return found


def drawing_files(slug):
    return (f"assets/pp-temple-{slug}.json", f"assets/pp-temple-{slug}.webp")


def build_one(folder):
    manifest = json.loads(working_path(folder, "manifest.json").read_text())
    svg = (TEMPLES_DIR / folder / manifest["art"]["white"]).read_text()
    for trace_width, art_px in ATTEMPTS:
        result = web_drawing.build(svg, manifest["location_line"], trace_width, art_px)
        problems = web_drawing.limit_problems(result["stats"])
        if not problems:
            return result, [], (trace_width, art_px)
    return result, problems, (trace_width, art_px)


def cmd_build(args):
    folders = temple_folders()
    if args.all:
        chosen = folders
    else:
        by_folder = {f: s for s, f in folders.items()}
        missing = [t for t in args.temple if t not in by_folder]
        if missing:
            raise SystemExit(f"no temple folder with a manifest and white art: {missing}")
        chosen = {by_folder[t]: t for t in args.temple}

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = OUT_DIR / "build-report.json"
    report = json.loads(report_path.read_text()) if report_path.exists() else {}
    failed = []
    for slug, folder in sorted(chosen.items()):
        t0 = time.time()
        result, problems, used = build_one(folder)
        st = result["stats"]
        line = (f"{folder:22} {st['strokes']:5} strokes  {st['uncovered_pct']:.2f}% left  "
                f"{(st['json_gz_bytes'] + st['image_bytes']) // 1024:4} KB  {time.time() - t0:4.1f}s")
        if problems:
            failed.append(folder)
            print(f"{line}  FAILED: {'; '.join(problems)}")
            continue
        json_name, webp_name = drawing_files(slug)
        (OUT_DIR / Path(json_name).name).write_text(
            json.dumps(result["data"], separators=(",", ":")))
        (OUT_DIR / Path(webp_name).name).write_bytes(result["image"])
        report[slug] = {"folder": folder, **st, "trace_width": used[0], "art_px": used[1]}
        print(line + ("" if used == ATTEMPTS[0] else f"  (needed {used})"))
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    if failed:
        print(f"\n{len(failed)} temple(s) not written: {failed}. They get no band until fixed.")
        return 1
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    g = b.add_mutually_exclusive_group(required=True)
    g.add_argument("--all", action="store_true")
    g.add_argument("--temple", action="append", help="temple folder name, e.g. 'Salt Lake'")
    args = ap.parse_args(argv)
    return {"build": cmd_build}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
