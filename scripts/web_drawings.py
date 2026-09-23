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
from shopify_client import ShopifyClient  # noqa: E402

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


def md5(b):
    return hashlib.md5(b).hexdigest()


def main_theme_id(client):
    nodes = client.gql("{ themes(first: 1, roles: [MAIN]) { nodes { id name } } }")["themes"]["nodes"]
    if not nodes:
        raise SystemExit("no published theme found.")
    return nodes[0]["id"]


def remote_checksums(client, theme_gid, patterns):
    """{filename: md5} for live theme files matching the patterns (Shopify wildcards)."""
    out, after = {}, None
    while True:
        theme = client.gql("""
          query($id: ID!, $f: [String!], $after: String) { theme(id: $id) {
            files(filenames: $f, first: 250, after: $after) {
              nodes { filename checksumMd5 }
              pageInfo { hasNextPage endCursor } } } }""",
            {"id": theme_gid, "f": patterns, "after": after})["theme"]
        page = theme["files"]
        out.update({n["filename"]: n["checksumMd5"] for n in page["nodes"]})
        if not page["pageInfo"]["hasNextPage"]:
            return out
        after = page["pageInfo"]["endCursor"]


def upsert_theme_files(client, theme_gid, files):
    """Write {filename: bytes} into the theme, 10 per call. Text as TEXT, images as BASE64."""
    names = sorted(files)
    for i in range(0, len(names), 10):
        batch = []
        for name in names[i:i + 10]:
            body = files[name]
            if name.endswith(".webp"):
                batch.append({"filename": name, "body": {"type": "BASE64",
                              "value": base64.b64encode(body).decode()}})
            else:
                batch.append({"filename": name, "body": {"type": "TEXT", "value": body.decode()}})
        result = client.gql("""
          mutation($themeId: ID!, $files: [OnlineStoreThemeFilesUpsertFileInput!]!) {
            themeFilesUpsert(themeId: $themeId, files: $files) {
              upsertedThemeFiles { filename }
              userErrors { filename code message } } }""",
            {"themeId": theme_gid, "files": batch})["themeFilesUpsert"]
        if result["userErrors"]:
            raise SystemExit(f"theme write refused: {result['userErrors']}")


def plan_uploads(local, remote):
    return sorted(n for n, b in local.items() if remote.get(n) != md5(b))


def local_theme_files(slugs=None):
    files = {name: (THEME_DIR / name).read_bytes() for name in THEME_CODE}
    for path in sorted(OUT_DIR.glob("pp-temple-*")):
        if path.suffix not in (".json", ".webp"):
            continue
        slug = path.stem[len("pp-temple-"):]
        if slugs is None or slug in slugs:
            files[f"assets/{path.name}"] = path.read_bytes()
    return files


PATTERNS = ["assets/pp-*", "sections/pp-*"]


def cmd_push(args):
    slugs = None
    if args.temple:
        folders = {f: s for s, f in temple_folders().items()}
        slugs = {folders[t] for t in args.temple}
    local = local_theme_files(slugs)
    client = ShopifyClient()
    theme_gid = main_theme_id(client)
    todo = plan_uploads(local, remote_checksums(client, theme_gid, PATTERNS))
    print(f"theme  : {theme_gid}")
    print(f"local  : {len(local)} files, {len(todo)} new or changed")
    for name in todo:
        print(f"  {name}  {len(local[name]) // 1024} KB")
    if not todo:
        print("the live theme already has all of these. Nothing to do.")
        return 0
    if args.dry_run:
        print("\nDRY RUN, nothing sent.")
        return 0
    upsert_theme_files(client, theme_gid, {n: local[n] for n in todo})
    after = remote_checksums(client, theme_gid, PATTERNS)
    wrong = [n for n in todo if after.get(n) != md5(local[n])]
    if wrong:
        raise SystemExit(f"read-back mismatch on {wrong}. Re-run push; if it persists, stop.")
    print(f"written and read back: {len(todo)} files.")
    return 0


def live_temple_slugs(client):
    slugs, after = set(), None
    while True:
        page = client.gql("""
          query($after: String) { products(first: 250, after: $after, query: "status:active") {
            nodes { tags } pageInfo { hasNextPage endCursor } } }""", {"after": after})["products"]
        for node in page["nodes"]:
            slugs |= {t[len("temple:"):] for t in node["tags"] if t.startswith("temple:")}
        if not page["pageInfo"]["hasNextPage"]:
            return slugs
        after = page["pageInfo"]["endCursor"]


def cmd_check(_args):
    client = ShopifyClient()
    theme_gid = main_theme_id(client)
    remote = remote_checksums(client, theme_gid, PATTERNS)
    slugs = live_temple_slugs(client)
    missing = sorted(s for s in slugs if not all(f in remote for f in drawing_files(s)))
    code_missing = [n for n in THEME_CODE if n not in remote]
    print(f"live temples: {len(slugs)}   with drawings in the theme: {len(slugs) - len(missing)}")
    if code_missing:
        print(f"theme code missing: {code_missing}")
    if missing:
        print(f"no drawing yet (their product band stays hidden): {missing}")
        print("fix: web_drawings.py build --temple '<folder>' && web_drawings.py push")
    return 1 if (missing or code_missing) else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    g = b.add_mutually_exclusive_group(required=True)
    g.add_argument("--all", action="store_true")
    g.add_argument("--temple", action="append", help="temple folder name, e.g. 'Salt Lake'")
    p = sub.add_parser("push")
    p.add_argument("--temple", action="append", help="limit drawings to these folders")
    p.add_argument("--dry-run", action="store_true")
    sub.add_parser("check")
    args = ap.parse_args(argv)
    return {"build": cmd_build, "push": cmd_push, "check": cmd_check}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
