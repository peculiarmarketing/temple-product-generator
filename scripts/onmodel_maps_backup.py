#!/usr/bin/env python
"""Back up the files the map placement lock depends on to Shopify Files.

The 34 locked base photos (324 MB) are gitignored and were otherwise only on
Higgsfield's CDN; the city prints only on Tapstitch's. Shopify Files keeps them
under permanent public links that any pipeline run (Mac or cloud) can download
with plain HTTP, no login. Shopify re-compresses a PNG losslessly, so a copy is
checked by a hash of its decoded pixels (composite_maps.pix), which is what the
lock holds and what build uses.
Evan, 9 Oct 2026 (Drive was the first ask; its connector cannot carry 10 MB files
and the scripts have no Drive login).

  python scripts/onmodel_maps_backup.py            # plan only
  python scripts/onmodel_maps_backup.py --apply    # upload what is missing
  python scripts/onmodel_maps_backup.py --verify   # download every copy, check hashes

composite_maps.py fetch reads artifacts/onmodel-maps/backup.json first.
"""
import argparse
import hashlib
import io
import json
import sys
import time
import urllib.request
from pathlib import Path

import requests
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from shopify_client import ShopifyClient, ShopifyError  # noqa: E402

MAPS = ROOT / "artifacts" / "onmodel-maps"
BACKUP = MAPS / "backup.json"
PREFIX = "pp-onmodel-maps-"


def pix(src):
    """composite_maps.pix: hash of mode, size and decoded pixels."""
    im = Image.open(src)
    h = hashlib.sha1(f"{im.mode}{im.size}".encode())
    h.update(im.tobytes())
    return h.hexdigest()[:16]


def wanted():
    """(path relative to onmodel-maps, pixel hash it must have)."""
    lk = json.loads((MAPS / "placement_lock.json").read_text())
    out = [(P["photo"], P["photo_pixels"]) for P in lk["photos"].values()]
    for p in sorted((MAPS / "prints").glob("*_*_*.png")):
        out.append((p.relative_to(MAPS).as_posix(), pix(p)))
    return out


def download_pix(url):
    with urllib.request.urlopen(url, timeout=300) as r:
        return pix(io.BytesIO(r.read()))


def upload(c, path):
    name = PREFIX + path.relative_to(MAPS).as_posix().replace("/", "-")
    staged = c.gql("""
      mutation($input: [StagedUploadInput!]!) { stagedUploadsCreate(input: $input) {
        stagedTargets { url resourceUrl parameters { name value } } userErrors { message } } }""",
                   {"input": [{"resource": "FILE", "filename": name, "mimeType": "image/png",
                               "httpMethod": "POST", "fileSize": str(path.stat().st_size)}]})
    if staged["stagedUploadsCreate"]["userErrors"]:
        raise ShopifyError(str(staged["stagedUploadsCreate"]["userErrors"]))
    t = staged["stagedUploadsCreate"]["stagedTargets"][0]
    with open(path, "rb") as f:
        up = requests.post(t["url"], data={p["name"]: p["value"] for p in t["parameters"]},
                           files={"file": (name, f, "image/png")}, timeout=300)
    if up.status_code not in (200, 201, 204):
        raise ShopifyError(f"staged upload HTTP {up.status_code}: {up.text[:300]}")
    r = c.gql("""mutation($files: [FileCreateInput!]!) { fileCreate(files: $files) {
        files { id } userErrors { message } } }""",
              {"files": [{"originalSource": t["resourceUrl"], "contentType": "FILE",
                          "filename": name}]})["fileCreate"]
    if r["userErrors"]:
        raise ShopifyError(str(r["userErrors"]))
    fid = r["files"][0]["id"]
    for _ in range(120):
        n = c.gql("""query($id: ID!) { node(id: $id) { ... on GenericFile { fileStatus url } } }""",
                  {"id": fid})["node"]
        if n.get("fileStatus") == "READY" and n.get("url"):
            return fid, n["url"]
        if n.get("fileStatus") == "FAILED":
            raise ShopifyError(f"{name}: Shopify file FAILED")
        time.sleep(2)
    raise ShopifyError(f"{name}: not READY after 4 min")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--verify", action="store_true")
    a = ap.parse_args()
    state = json.loads(BACKUP.read_text()) if BACKUP.exists() else {}
    want = wanted()
    if a.verify:
        bad = 0
        for rel, h in want:
            e = state.get(rel)
            got = download_pix(e["url"]) if e else None
            ok = got == h
            bad += not ok
            if not ok:
                print("BAD", rel, got, "want", h)
        print(f"{len(want) - bad} of {len(want)} backups download without a login and match")
        sys.exit(1 if bad else 0)
    todo = [(rel, h) for rel, h in want if state.get(rel, {}).get("pixels") != h]
    print(f"{len(want)} files, {len(want) - len(todo)} already backed up, {len(todo)} to upload")
    if not a.apply:
        return
    c = ShopifyClient()
    for rel, h in todo:
        path = MAPS / rel
        assert pix(path) == h, f"{rel}: local file does not match the lock"
        fid, url = upload(c, path)
        got = download_pix(url)
        if got != h:
            raise ShopifyError(f"{rel}: Shopify copy hashes {got}, want {h}")
        state[rel] = {"id": fid, "url": url, "pixels": h}
        BACKUP.write_text(json.dumps(state, indent=1, sort_keys=True))
        print("backed up", rel)


if __name__ == "__main__":
    main()
