#!/usr/bin/env python
"""Keep every live map's art in Shopify Files, with the index in git.

The map art is gitignored for size (about 260 MB for 27 maps): the 300 dpi back
and front art in the workspace (designs/city-map-back/out/<place>/) and the
print files, design cards and review sheet map_run.py makes from it
(artifacts/maps/<place>/*.png). Shopify Files keeps a copy of each under a
permanent public link that any run, Mac or cloud, can download with plain HTTP.
Shopify may re-compress a PNG losslessly, so a copy is checked by a hash of its
decoded pixels, the same check onmodel_maps_backup.py uses.
Evan, 9 Oct 2026: "keep the index in github but upload all the files to shopify".

Where to find things:
  artifacts/maps/art_index.json   machine index: file -> Shopify id, url, pixel hash
  artifacts/maps/ART_INDEX.md     the same per map, readable, with the live
                                  listings and their on-model photo links

  python scripts/map_art_backup.py                 # plan only
  python scripts/map_art_backup.py --apply         # upload what is missing or changed, write both indexes
  python scripts/map_art_backup.py --verify        # download every copy, check hashes
  python scripts/map_art_backup.py --fetch nauvoo  # restore a map's missing files (no place: all)
  python scripts/map_art_backup.py --index         # rewrite ART_INDEX.md only

Run --apply again whenever a live map's art is rebuilt (a changed file uploads
again under a new link; the index keeps only the current one).
"""
import argparse
import io
import json
import re
import sys
import urllib.request
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import map_run as M                                      # noqa: E402
from onmodel_maps_backup import pix, upload              # noqa: E402
from shopify_client import ShopifyClient, ShopifyError   # noqa: E402

INDEX = M.OUT / "art_index.json"
README = M.OUT / "ART_INDEX.md"
PREFIX = "pp-map-art-"
GARMENT_WORD = {"tee": "tee", "crew": "sweatshirt", "hoodie": "hoodie"}


def live_places():
    places = json.loads((M.maps_dir() / "places.json").read_text())
    return {k: p for k, p in places.items() if not k.startswith("_") and p.get("status") == "live"}


def local_files(name, p):
    """[(key, local path, what it is)]. Keys are stable names for the index:
    art/<place>/<file> lives in the workspace's out/, maps/<place>/<file> here."""
    back, front, _ = M.art_paths(name, p, check=False)
    out = [(f"art/{name}/{back.name}", back, "back art, 300 dpi (source of every back print)"),
           (f"art/{name}/{front.name}", front, "front logo art, 300 dpi")]
    for f in sorted((M.OUT / name).glob("*.png")):
        out.append((f"maps/{name}/{f.name}", f, describe(f.name)))
    return out


def describe(fn):
    m = re.search(r" (tee|crew|hoodie) white (back|front) print \(map\)\.png$", fn)
    if m:
        return f"{GARMENT_WORD[m[1]]} {m[2]} print file (as uploaded to Tapstitch)"
    if fn.endswith(" map card.png"):
        return "map close-up card (gallery)"
    if fn.endswith(" logo card.png"):
        return "coordinates logo close-up card (gallery)"
    if fn.endswith(" review.png"):
        return "review sheet"
    return "map file"


def path_for(key):
    kind, name, fn = key.split("/", 2)
    return (M.maps_dir() / "out" / name / fn) if kind == "art" else (M.OUT / name / fn)


def shopify_name(key):
    return PREFIX + re.sub(r"[^a-z0-9.]+", "-", key.lower()).strip("-")


def download(url):
    with urllib.request.urlopen(url, timeout=300) as r:
        return r.read()


def load():
    return json.loads(INDEX.read_text()) if INDEX.exists() else {}


def save(idx):
    INDEX.write_text(json.dumps(idx, indent=1, sort_keys=True) + "\n")


def listings(c, name):
    """[(garment, handle, title, [(alt, url)] on-model photos)] for the index."""
    state = M.load_state(name)
    out = []
    for g in M.GARMENTS:
        h = (state.get(g) or {}).get("shopify_handle")
        if not h:
            continue
        p = c.gql("""query($h: String!) { productByHandle(handle: $h) { title
            media(first: 100) { nodes { alt ... on MediaImage { image { url } } } } } }""",
                  {"h": h})["productByHandle"]
        photos = [(m["alt"], m["image"]["url"].split("?")[0]) for m in p["media"]["nodes"]
                  if " on model - " in (m.get("alt") or "") and m.get("image")]
        out.append((g, h, p["title"], photos))
    return out


def write_readme(idx, c=None):
    places = live_places()
    lines = ["# City map art: where every file is", "",
             "Written by `scripts/map_art_backup.py`; do not edit by hand. The files are gitignored for size; "
             "each has a permanent copy in Shopify Files (links below, no login). Restore a map's files with "
             "`python scripts/map_art_backup.py --fetch <place>`. Machine index: `art_index.json`.", "",
             "- **Back and front art** (300 dpi): `designs/city-map-back/out/<place>/` in the workspace. "
             "Built by `designs/city-map-back/build_map_back.py <place>`.",
             "- **Print files, cards, review sheet**: `artifacts/maps/<place>/` here. Built by "
             "`scripts/map_run.py <place> --review`. Each map's Tapstitch template and Shopify handles are in "
             "`artifacts/maps/<place>/state.json`.",
             "- **On-model photos**: on each live listing (links below). Rebuild with "
             "`artifacts/onmodel-maps/composite_maps.py build <place>` (see `artifacts/onmodel-maps/LOCK.md`).",
             "", f"{len(places)} live maps, {len(idx)} files backed up.", ""]
    for name in sorted(places):
        city, region = M.city_state(places[name])
        lines += [f"## {city}, {region} (`{name}`)", ""]
        for key in sorted(k for k in idx if k.split("/")[1] == name):
            e = idx[key]
            lines.append(f"- [{key.split('/', 2)[2]}]({e['url']}): {e['what']}, "
                         f"{size(e['bytes'])}. Local: `{key_local(key)}`")
        if c:
            for g, h, title, photos in listings(c, name):
                lines.append(f"- Listing: [{title}](https://peculiarpeopleco.com/products/{h}), "
                             f"{len(photos)} on-model photos: "
                             + ", ".join(f"[{a.rsplit(' - ', 1)[-1]} {('back' if 'back print' in a else 'front')}]({u})"
                                         for a, u in photos))
        lines.append("")
    README.write_text("\n".join(lines))
    print("wrote", README.relative_to(ROOT))


def size(n):
    return f"{n / 1e6:.1f} MB" if n >= 1e5 else f"{round(n / 1e3)} KB"


def dpi_of(path):
    with Image.open(path) as im:
        d = im.info.get("dpi")
    return [round(float(x), 4) for x in d] if d else None


def restore_dpi(path, want):
    """Shopify rewrites a PNG's resolution tag (a print file with none comes back
    tagged 72 dpi); put back the one the original had. Pixels are untouched."""
    if dpi_of(path) == want:
        return
    with Image.open(path) as im:
        im.load()
        im.info.pop("dpi", None)
        im.save(path, **({"dpi": tuple(want)} if want else {}))


def key_local(key):
    kind, name, fn = key.split("/", 2)
    return f"designs/city-map-back/out/{name}/{fn}" if kind == "art" else f"artifacts/maps/{name}/{fn}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--index", action="store_true")
    ap.add_argument("--fetch", nargs="*", metavar="PLACE")
    a = ap.parse_args()
    idx = load()

    if a.fetch is not None:
        keys = [k for k in idx if not a.fetch or k.split("/")[1] in a.fetch]
        if not keys:
            raise SystemExit(f"nothing in {INDEX.name} for {a.fetch}")
        for k in keys:
            path, e = path_for(k), idx[k]
            if path.exists() and pix(path) == e["pixels"]:
                continue
            data = download(e["url"])
            if pix(io.BytesIO(data)) != e["pixels"]:
                raise SystemExit(f"{k}: the Shopify copy does not match its hash")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            restore_dpi(path, e.get("dpi"))
            print("fetched", key_local(k))
        print(f"{len(keys)} files present and matching")
        return

    if a.verify:
        bad = 0
        for k, e in sorted(idx.items()):
            ok = pix(io.BytesIO(download(e["url"]))) == e["pixels"]
            bad += not ok
            if not ok:
                print("BAD", k)
        print(f"{len(idx) - bad} of {len(idx)} copies download without a login and match")
        sys.exit(1 if bad else 0)

    if a.index:
        write_readme(idx, ShopifyClient())
        return

    want = [w for name, p in sorted(live_places().items()) for w in local_files(name, p)]
    missing = [str(path) for _, path, _ in want if not path.exists()]
    if missing:
        raise SystemExit(f"{len(missing)} local files missing, e.g. {missing[0]}; rebuild them first")
    todo = []
    for key, path, what in want:
        h = pix(path)
        if idx.get(key, {}).get("pixels") != h:
            todo.append((key, path, what, h))
    stale = sorted(set(idx) - {k for k, _, _ in want})
    print(f"{len(want)} files, {len(want) - len(todo)} already backed up, {len(todo)} to upload, "
          f"{len(stale)} index entries no longer current")
    if not a.apply:
        return
    c = ShopifyClient()
    for i, (key, path, what, h) in enumerate(todo, 1):
        fid, url = upload(c, path, shopify_name(key))
        if pix(io.BytesIO(download(url))) != h:
            raise ShopifyError(f"{key}: Shopify copy does not match")
        idx[key] = {"id": fid, "url": url, "pixels": h, "bytes": path.stat().st_size, "what": what,
                    "dpi": dpi_of(path)}
        save(idx)
        print(f"[{i}/{len(todo)}] backed up {key}")
    for k in stale:
        del idx[k]
    save(idx)
    write_readme(idx, c)


if __name__ == "__main__":
    main()
