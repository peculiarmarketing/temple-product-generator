"""Bind every Shopify variant to its own colourway's BACK image.

WHY THIS EXISTS, measured on the live hoodie publish 16 Sep 2026. Tapstitch
attaches each mockup to a colour option value, and Shopify then binds each
variant to the FIRST image of its colour at import. Tapstitch hands its mockups
back front-first, and the front of these garments carries only a 6in logo, so
every variant ends up bound to an almost blank garment.

That matters more than it sounds. The theme shows the SELECTED VARIANT'S image,
which is a fourth thing called "default" and the only one the shopper actually
sees. The gallery order and `featuredMedia` can both be correct while the page
still opens on the blank front, which is exactly what happened to the crew on
16 Sep before this was found.

Posting the mockups back-first (`tapstitch_api.mockups_back_first`) fixes the
GALLERY order, and that was confirmed to carry through, but it does NOT change
the binding: the hoodie came back front-bound anyway. So this runs after every
publish rather than as a fallback, and re-running it is how a Tapstitch variant
re-sync gets repaired.

WHY THIS IS NOT IN scripts/shopify_fixups.py, which is where the other
re-runnable Shopify repairs live: the pairing cannot be done from Shopify alone.
Shopify keeps none of Tapstitch's mockup metadata, so the only exact way to know
which image is a given variant's back is to ask Tapstitch, match on the filename
Shopify preserved, and pair by colorId. shopify_fixups.py deliberately has no
Tapstitch dependency, so this keeps its own file.

POSITION IS NOT A SUBSTITUTE, learned the expensive way the same day. Two wrong
rules were tried before this one. Pairing colours by their order in the VARIANT
list is wrong because the colour-order fixup rewrites that sequence, and it bound
Gray's variants to the BLACK garment's photo. Pairing by halves of the gallery is
wrong because the layout is not consistent between products: the tee published on
15 Sep is INTERLEAVED (front, back, front, back, one pair per colour) while a
product posted through mockups_back_first is every back then every front. A rule
that fits one silently corrupts the other.

    ./.venv.nosync/bin/python scripts/tapstitch_variant_images.py --report-only
    ./.venv.nosync/bin/python scripts/tapstitch_variant_images.py --handle H
    ./.venv.nosync/bin/python scripts/tapstitch_variant_images.py \
        --handle H --template-id 1549714541104005120

Products are found through the migration ledger, which records each replacement's
`shopify_handle` and `tapstitch_template_id`. Pass `--template-id` for a product
that has no ledger row, such as the 15 Sep tee test.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ledger
import tapstitch_api as T
from shopify_client import ShopifyClient, ShopifyError

STORE_ID = "1402569694703132672"


def ledger_targets(handle=None):
    """[(handle, template_id)] for live replacements the ledger knows about."""
    rows = ledger.load()["rows"]
    rows = rows if isinstance(rows, list) else list(rows.values())
    out = []
    for r in rows:
        if not r.get("shopify_handle") or not r.get("tapstitch_template_id"):
            continue
        if handle and r["shopify_handle"] != handle:
            continue
        out.append((r["shopify_handle"], r["tapstitch_template_id"]))
    return out


def rebind(client, session, handle, template_id, report_only=False):
    """Returns a one-line note, or None when nothing needed changing."""
    product = client.find_product_by_handle(handle)
    if not product:
        return f"{handle}: no such Shopify product"
    prefill = T.store_product_prefill(session, STORE_ID, template_id)
    pairs = T.back_for_front_mockups(prefill)
    if not pairs:
        return f"{handle}: Tapstitch returned no front/back mockup pairs"

    data = client.gql("""
      query($id: ID!) { product(id: $id) {
        media(first: 60) { nodes { ... on MediaImage { id image { url } } } }
        variants(first: 100) { nodes { id title
          media(first: 1) { nodes { ... on MediaImage { id } } } } } } }""",
      {"id": product["id"]})["product"]

    name_of = {}
    for node in data["media"]["nodes"]:
        if node.get("id"):
            name_of[node["id"]] = node["image"]["url"].split("/")[-1].split("?")[0]
    id_of = {name: mid for mid, name in name_of.items()}

    updates = []
    for v in data["variants"]["nodes"]:
        bound = (v["media"]["nodes"] or [{}])[0].get("id")
        back_name = pairs.get(name_of.get(bound))
        # A variant already on a back is not a key in `pairs`, which is what
        # makes this idempotent.
        if back_name and id_of.get(back_name):
            updates.append({"id": v["id"], "mediaId": id_of[back_name]})
    if not updates:
        return None
    if report_only:
        return f"{handle}: would rebind {len(updates)} variant image(s) to the back"
    res = client.gql("""
      mutation($pid: ID!, $variants: [ProductVariantsBulkInput!]!) {
        productVariantsBulkUpdate(productId: $pid, variants: $variants) {
          userErrors { field message } } }""",
      {"pid": product["id"], "variants": updates})["productVariantsBulkUpdate"]
    if res["userErrors"]:
        raise ShopifyError(str(res["userErrors"]))
    return f"{handle}: rebound {len(updates)} variant image(s) to the back"


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--report-only", action="store_true", help="print, write nothing")
    ap.add_argument("--handle", help="restrict to one product handle")
    ap.add_argument("--template-id",
                    help="use this Tapstitch template instead of the ledger's; "
                         "needs --handle")
    a = ap.parse_args()

    if a.template_id and not a.handle:
        raise SystemExit("--template-id needs --handle.")
    targets = ([(a.handle, a.template_id)] if a.template_id
               else ledger_targets(a.handle))
    if not targets:
        raise SystemExit("Nothing to do: no ledger row carries both a "
                         "shopify_handle and a tapstitch_template_id"
                         + (f" for {a.handle!r}." if a.handle else "."))

    client, session = ShopifyClient(), T.session()
    touched = 0
    for handle, template_id in targets:
        note = rebind(client, session, handle, template_id, report_only=a.report_only)
        if note:
            touched += 1
            print(f"  {note}")
    print(f"\n{len(targets)} product(s) checked, {touched} needing work.")
    if a.report_only:
        print("Report only, nothing written.")


if __name__ == "__main__":
    main()
