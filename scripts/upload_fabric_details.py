#!/usr/bin/env python
"""Append Tapstitch's fabric and construction detail shots to a product gallery.

ADDITIVE ONLY. Appends to the end, never deletes, never touches binding.

THE COLOUR CATCH, from docs/photo-mockup-plan.md. Every `-D-` shot Tapstitch
publishes for a garment is the SAME colourway: all six hoodie shots are mauve.
Putting them unlabelled on the Black listing shows mauve fabric. The plan's
preferred answer, and what this does, is to caption them with the colourway and
place them last: their job is to show weave and construction, not colour, and a
buyer reads a detail shot that way.

Idempotent through deterministic alt text.

  --dry-run  print what would happen and change nothing
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shopify_client import ShopifyClient  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DETAILS = ROOT / "artifacts/photo-mockup-spike/fabric-details"

# Which three, and what each one actually shows. Chosen to span texture, the
# garment's signature feature and its finishing, rather than three of a kind.
PICKS = {
    "hoodie": [("D6.jpg", "Heavyweight fleece texture, shown in Mauve"),
               ("D2.jpg", "Hood construction detail, shown in Mauve"),
               ("D3.jpg", "Ribbed cuff detail, shown in Mauve")],
}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--product-gid", required=True)
    p.add_argument("--garment", required=True, choices=sorted(PICKS))
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    picks = PICKS[args.garment]
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
        mid = sc.upload_media_image(args.product_gid, DETAILS / args.garment / fn, alt)
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
