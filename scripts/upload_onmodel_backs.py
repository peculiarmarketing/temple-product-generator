#!/usr/bin/env python
"""Add the on-model back photos to a live product's gallery, at the top.

ADDITIVE ONLY. This never deletes live media and never touches variant binding.
The target layout in docs/photo-mockup-plan.md eventually drops the per-colour
flat mockups and rebinds each variant to its on-model back, but both of those
are destructive and are deliberately not done here.

Idempotent: every image is uploaded with a deterministic alt text, and anything
already present with that alt is skipped, so a re-run repairs a partial upload
rather than duplicating the gallery.

  --dry-run   print exactly what would happen and change nothing
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import colour_names  # noqa: E402
from shopify_client import ShopifyClient  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FINAL_SET = ROOT / "artifacts/photo-mockup-spike/final-set"

# Gallery order per garment: lead colour first, then the rest in the order the
# storefront lists the variants, so the gallery and the swatch row agree.
COLOUR_ORDER = {
    "hoodie": ["navy-blue", "gray", "black", "coffee", "mauve", "royal-blue"],
    "tee": ["black", "dark-gray", "navy-blue", "maroon", "coffee"],
    "crew": ["gray", "black"],
}
def alt_for(temple, garment, colour):
    """The alt text every on-model photo carries.

    The colour name comes from colour_names, the one map in the repo, because
    this string is not decoration: bind_variants_to_onmodel.py pairs a variant
    to its photo by matching the variant's colour against its tail, so an alt
    written under a stale name silently binds nothing."""
    return f"{temple} Temple back print on model - {colour_names.name_for(garment, colour)}"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--product-gid", required=True)
    p.add_argument("--garment", required=True, choices=sorted(COLOUR_ORDER))
    p.add_argument("--temple", default="Salt Lake")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    colours = COLOUR_ORDER[args.garment]
    files = []
    for c in colours:
        f = FINAL_SET / f"{args.garment}_{c}.jpg"
        if not f.exists():
            raise SystemExit(f"missing {f}")
        files.append((c, f))

    sc = ShopifyClient()
    data = sc.gql("""
      query($id: ID!) { product(id: $id) {
        title status
        media(first: 60) { edges { node { ... on MediaImage { id alt } } } } } }""",
        {"id": args.product_gid})
    prod = data["product"]
    existing = [e["node"] for e in prod["media"]["edges"]]
    existing_alts = {m.get("alt") for m in existing}

    print(f"product : {prod['title']}  [{prod['status']}]")
    print(f"gallery : {len(existing)} images now")
    todo = [(c, f) for c, f in files if alt_for(args.temple, args.garment, c) not in existing_alts]
    skip = [c for c, _ in files if alt_for(args.temple, args.garment, c) in existing_alts]
    if skip:
        print(f"skipping (already present): {', '.join(skip)}")
    print(f"to upload: {len(todo)} -> gallery would become {len(existing) + len(todo)}")
    for i, (c, f) in enumerate(todo):
        print(f"   {i}. {f.name:26s} alt='{alt_for(args.temple, args.garment, c)}'")
    print("\nNothing is deleted. Variant binding is not touched.")
    if args.dry_run:
        print("\nDRY RUN, nothing sent.")
        return

    new_ids = []
    for c, f in todo:
        alt = alt_for(args.temple, args.garment, c)
        mid = sc.upload_media_image(args.product_gid, f, alt)
        sc.wait_for_media_ready(mid)
        new_ids.append((c, mid))
        print(f"  uploaded {c:11s} {mid}")

    # Put them at the top, in COLOUR_ORDER, lead colour first.
    for idx, (c, mid) in enumerate(new_ids):
        sc.move_media_to_position(args.product_gid, mid, idx)
        print(f"  positioned {c:11s} -> slot {idx + 1}")

    after = sc.gql("""
      query($id: ID!) { product(id: $id) {
        media(first: 60) { edges { node { ... on MediaImage { id alt } } } } } }""",
        {"id": args.product_gid})["product"]["media"]["edges"]
    print(f"\ngallery now {len(after)} images. First six:")
    for e in after[:6]:
        print(f"   {e['node'].get('alt') or '(no alt)'}")


if __name__ == "__main__":
    main()
