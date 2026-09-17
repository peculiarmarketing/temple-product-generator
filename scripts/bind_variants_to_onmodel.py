#!/usr/bin/env python
"""Bind every colour variant to its ON-MODEL back photo.

WHY THIS IS NOT tapstitch_variant_images.py. That script binds variants to the
flat BACK mockup, and it has to ask Tapstitch which mockup is which because
Shopify keeps none of Tapstitch's metadata: the only exact pairing is colorId
plus the filename Shopify preserved.

This one needs none of that. upload_onmodel_backs.py writes a deterministic alt
text on every image it uploads, so the colour is carried in Shopify itself and
the pairing is a string match. Two consequences worth knowing:

  - it works on products with no usable tapstitch_template_id, which is what
    blocks the 15 Sep tee from tapstitch_variant_images.py entirely;
  - it cannot bind a colour whose on-model photo was never uploaded, and it
    leaves such a variant alone rather than unbinding it.

Idempotent: a variant already on its on-model back is not queued.

  --dry-run  print the before and after for every variant and change nothing
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shopify_client import ShopifyClient  # noqa: E402

ALT_PREFIX = "Temple back print on model - "


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--product-gid", required=True)
    p.add_argument("--temple", default="Salt Lake")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    sc = ShopifyClient()
    data = sc.gql("""
      query($id: ID!) { product(id: $id) {
        title status
        media(first: 60) { nodes { ... on MediaImage { id alt } } }
        variants(first: 100) { nodes { id title
          media(first: 1) { nodes { ... on MediaImage { id alt } } } } } } }""",
        {"id": args.product_gid})["product"]

    want = f"{args.temple} {ALT_PREFIX}"
    onmodel = {}
    for m in data["media"]["nodes"]:
        alt = m.get("alt") or ""
        if alt.startswith(want):
            onmodel[alt[len(want):]] = m["id"]
    if not onmodel:
        raise SystemExit(f"no on-model media found with alt starting '{want}'. "
                         f"Run upload_onmodel_backs.py first.")

    print(f"product : {data['title']}  [{data['status']}]")
    print(f"on-model photos found: {', '.join(sorted(onmodel))}\n")

    updates, already, missing = [], [], set()
    print(f"{'variant':22s} {'bound now':46s} -> after")
    for v in data["variants"]["nodes"]:
        colour = v["title"].split(" / ")[0]
        target = onmodel.get(colour)
        bound = (v["media"]["nodes"] or [{}])[0]
        bound_id, bound_alt = bound.get("id"), bound.get("alt") or "(no alt: flat mockup)"
        if not target:
            missing.add(colour)
            continue
        if bound_id == target:
            already.append(v["title"])
            continue
        updates.append({"id": v["id"], "mediaId": target})
        if len(updates) <= 6 or v["title"].endswith("/ S"):
            print(f"{v['title']:22s} {bound_alt:46s} -> on model, {colour}")

    if missing:
        print(f"\nno on-model photo for: {', '.join(sorted(missing))}. Left untouched.")
    if already:
        print(f"already correct: {len(already)} variant(s)")
    print(f"\nto rebind: {len(updates)} variant(s)")
    if not updates:
        print("nothing to do.")
        return
    if args.dry_run:
        print("\nDRY RUN, nothing sent.")
        return

    for i in range(0, len(updates), 25):
        chunk = updates[i:i + 25]
        res = sc.gql("""
          mutation($pid: ID!, $variants: [ProductVariantsBulkInput!]!) {
            productVariantsBulkUpdate(productId: $pid, variants: $variants) {
              userErrors { field message } } }""",
            {"pid": args.product_gid, "variants": chunk})["productVariantsBulkUpdate"]
        if res["userErrors"]:
            raise SystemExit(str(res["userErrors"]))
        print(f"  rebound {i + len(chunk)}/{len(updates)}")

    after = sc.gql("""
      query($id: ID!) { product(id: $id) {
        variants(first: 100) { nodes { title
          media(first: 1) { nodes { ... on MediaImage { alt } } } } } } }""",
        {"id": args.product_gid})["product"]["variants"]["nodes"]
    seen = {}
    for v in after:
        c = v["title"].split(" / ")[0]
        if c not in seen:
            seen[c] = (v["media"]["nodes"] or [{}])[0].get("alt") or "(no alt)"
    print("\nverified, one variant per colour:")
    for c, alt in seen.items():
        print(f"  {c:12s} -> {alt}")


if __name__ == "__main__":
    main()
