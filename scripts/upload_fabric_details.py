#!/usr/bin/env python
"""Append Tapstitch's fabric and construction detail shots to a product gallery.

ADDITIVE ONLY. Appends to the end, never deletes, never touches binding.

THE COLOUR CATCH, from docs/photo-mockup-plan.md. Every `-D-` shot Tapstitch
publishes for a garment is the SAME colourway: all six hoodie shots are mauve.
Putting them unlabelled on the Black listing shows mauve fabric. The plan's
preferred answer, and what this does, is to caption them with the colourway and
place them last: their job is to show weave and construction, not colour, and a
buyer reads a detail shot that way.

Every shot is put through artifacts/photo-mockup-spike/normalize.py on the way
up: the white backdrop becomes the garment's own light gray and the frame is
cropped from 2048x2731 to a square, so a detail shot no longer breaks the
gallery's shape or flashes white between two gray images.

Idempotent through deterministic alt text.

  --dry-run  print what would happen and change nothing
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "artifacts/photo-mockup-spike"))
import normalize  # noqa: E402
from shopify_client import ShopifyClient  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DETAILS = ROOT / "artifacts/photo-mockup-spike/fabric-details"


def picks_for(garment):
    """Which three shots ship for a garment, and what each one shows.

    Read from the garment's captions.json rather than a dict in here. This file
    used to carry its own hardcoded list covering the hoodie only, while
    build_product_gallery.py read captions.json for all three garments, so the
    two disagreed about the tee and the crew. captions.json is the richer source
    and is now the only one.
    """
    f = DETAILS / garment / "captions.json"
    if not f.exists():
        raise SystemExit(f"no captions.json for {garment!r} at {f}")
    return sorted((k, v) for k, v in json.loads(f.read_text()).items()
                  if not k.startswith("_"))


def notice_for(garment):
    """Text stamped across the bottom of every shot, or None. A _notice key in
    captions.json; keys starting with _ are directives rather than images."""
    f = DETAILS / garment / "captions.json"
    return json.loads(f.read_text()).get("_notice") if f.exists() else None


GARMENTS = sorted(d.name for d in DETAILS.iterdir()
                  if d.is_dir() and (d / "captions.json").exists())


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--product-gid", required=True)
    p.add_argument("--garment", required=True, choices=GARMENTS)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    picks = picks_for(args.garment)
    for fn, _ in picks:
        if not (DETAILS / args.garment / fn).exists():
            raise SystemExit(f"missing {DETAILS / args.garment / fn}")

    sc = ShopifyClient()
    data = sc.gql("""
      query($id: ID!) { product(id: $id) {
        title status
        media(first: 60) { nodes { ... on MediaImage { id alt } } } } }""",
        {"id": args.product_gid})["product"]
    existing_alts = {m.get("alt") for m in data["media"]["nodes"]}
    n_before = len(data["media"]["nodes"])

    todo = [(fn, alt) for fn, alt in picks if alt not in existing_alts]
    print(f"product : {data['title']}  [{data['status']}]")
    print(f"gallery : {n_before} images now")
    if len(todo) < len(picks):
        print(f"skipping {len(picks) - len(todo)} already present")
    for fn, alt in todo:
        print(f"  append {fn:8s} alt='{alt}'")
    print(f"\nwould become {n_before + len(todo)} images. Nothing deleted.")
    if args.dry_run:
        print("\nDRY RUN, nothing sent.")
        return

    for fn, alt in todo:
        norm, st = normalize.for_upload(DETAILS / args.garment / fn, args.garment,
                                        notice=notice_for(args.garment))
        print(f"  normalized {fn:8s} {st['src'][0]}x{st['src'][1]} -> "
              f"{st['out'][0]}x{st['out'][1]}, backdrop {st['gray']}, "
              f"{st['bg_fraction']*100:.0f}% background")
        mid = sc.upload_media_image(args.product_gid, norm, alt)
        sc.wait_for_media_ready(mid)
        print(f"  uploaded {fn:8s} {mid}")
    after = sc.gql("""
      query($id: ID!) { product(id: $id) {
        media(first: 60) { nodes { ... on MediaImage { alt } } } } }""",
        {"id": args.product_gid})["product"]["media"]["nodes"]
    print(f"\ngallery now {len(after)} images. Last three:")
    for m in after[-3:]:
        print(f"   {m.get('alt') or '(no alt)'}")


if __name__ == "__main__":
    main()
