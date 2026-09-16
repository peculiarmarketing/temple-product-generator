"""Create Tapstitch products from the built print files, then finish them on Shopify.

Two halves, deliberately separated:

  the EDITOR half   drives the Tapstitch web editor with Playwright. Tapstitch
                    has no public API, so this is the only way to create a
                    product. It is driven entirely by config/tapstitch.json and
                    CANNOT RUN until that file's nulls are filled in during a
                    live session with the editor open.

  the SHOPIFY half  everything after Tapstitch pushes the product to the store:
                    set the product type, write the description, push the art
                    close-up card to gallery slot 2, delete the old listing. All
                    of it goes through the Shopify Admin API, none of it depends
                    on the editor, and all of it works today.

Splitting them matters because the editor half is the fragile part. A Tapstitch
redesign breaks it; none of it can break the description writer, which is proven
on 158 products.

Usage:
  python scripts/tapstitch_publish.py check                  # what is blocking a run
  python scripts/tapstitch_publish.py finish --handle <h>    # Shopify half only
  python scripts/tapstitch_publish.py run --temple "Logan"   # both halves
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import generate
import ledger
from description_html import compose_description
from layout import PROJECT_ROOT
from shopify_client import ShopifyClient

CONFIG_PATH = PROJECT_ROOT / "config" / "tapstitch.json"


def load_config():
    return json.loads(CONFIG_PATH.read_text())


def missing_config(cfg):
    """Every value the editor half still needs. Empty means it can run."""
    out = []
    for section in ("urls", "selectors", "values"):
        for k, v in cfg.get(section, {}).items():
            if not k.startswith("_") and v is None:
                out.append(f"{section}.{k}")
    return out


def missing_garment_setup():
    """Everything still blocked on Evan picking blanks."""
    out = []
    for gid in generate.all_garment_ids("tapstitch"):
        g = generate.load_garment_config(gid)
        blank = g.get("blank") or {}
        if not blank.get("model"):
            out.append(f"{gid}: no Tapstitch blank chosen")
        if not g.get("colorways"):
            out.append(f"{gid}: no colorways chosen")
        if g["print_area"].get("tbd"):
            out.append(f"{gid}: print_area is still the placeholder "
                       f"(only readable inside the Tapstitch editor)")
        if (g.get("front_print_area") or {}).get("tbd"):
            out.append(f"{gid}: front_print_area is still the placeholder")
        if not g.get("storefront_first_color"):
            out.append(f"{gid}: no storefront_first_color chosen")
        copy_dir = PROJECT_ROOT / g["garment_copy"]
        if not (copy_dir / "product-intro.html").exists():
            missing = "product-intro.html"
            if not (copy_dir / "size-guide.html").exists():
                missing += " and size-guide.html"
            out.append(f"{gid}: {missing} not written yet ({g['garment_copy']})")
    return out


def cmd_check():
    cfg = load_config()
    editor = missing_config(cfg)
    garments = missing_garment_setup()
    print("EDITOR AUTOMATION")
    if editor:
        print(f"  blocked: {len(editor)} values in config/tapstitch.json are still unknown.")
        print("  These need one live session with the Tapstitch editor open:")
        for m in editor:
            print(f"      {m}")
    else:
        # Still not "ready" in the sense that matters. The API route is finished
        # and proven to the point of a live published product, and placement is
        # now derived rather than copied, but nothing drives it over the
        # catalogue. Saying "ready" would invite someone to start a 135-row run.
        print("  config ready, and the API route is PROVEN end to end")
        print("  (create_template -> upload -> save_design -> create_store_product")
        print("  -> distribute). Three products live on the storefront as of")
        print("  16 Sep 2026. Use tapstitch_api.py.")
        print("  Placement is DERIVED from each garment's own print area")
        print("  (tapstitch_api.print_areas/placement), checked against the tee.")
        print("  All three blanks are known and all three have published.")
        print("  NOT built: the catalogue runner and fixup sequencing.")
        print("  create_store_product EXISTS and has run.")
        print("  See docs/discovery/2026-09-tapstitch-editor-api.md.")
    print("\nGARMENT SETUP")
    if garments:
        print(f"  blocked: {len(garments)} items need Evan's blank choices:")
        for m in garments:
            print(f"      {m}")
    else:
        print("  ready.")

    data = ledger.load()
    c = ledger.counts(data)
    print(f"\nLEDGER ({len(data['rows'])} rows)")
    for state in ledger.STATES:
        if c.get(state):
            print(f"  {state:<22} {c[state]}")
    ready = [r for r in data["rows"] if r["state"] == "file-approved"]
    print(f"\n{len(ready)} rows are approved and waiting for a product to be built.")
    return 0 if not (editor or garments) else 1


def finish_on_shopify(client, temple, garment_id, handle, old_handle=None, dry_run=False):
    """The Shopify half. Order matters: product type FIRST, because every fixup
    in shopify_fixups is keyed on it and Tapstitch publishes with it empty."""
    import art_images
    from shopify_fixups import fix_published_product

    post = load_config().get("post_publish", {})
    g = generate.load_garment_config(garment_id)
    product = client.find_product_by_handle(handle)
    if not product:
        raise SystemExit(f"No Shopify product at handle {handle!r}. Did the Tapstitch "
                         f"publish actually land? Tapstitch pushes can lag.")
    actions = []

    ptype = g.get("shopify_product_type") or g["product_type"]
    if product.get("productType") != ptype:
        if not dry_run:
            client.update_product(product["id"], productType=ptype)
        actions.append(f"product type set to {ptype!r}")

    facts_path = generate.working_path(temple, "temple-facts.html")
    fixed = generate.fixed_description(g)
    if not fixed:
        actions.append("SKIPPED description: no garment copy written yet")
    elif not facts_path.exists():
        actions.append(f"SKIPPED description: no temple-facts.html for {temple}")
    else:
        html = compose_description(fixed, facts_path.read_text())
        if not dry_run:
            client.update_product(product["id"], descriptionHtml=html)
        actions.append(f"description written ({len(html)} bytes)")

    if not dry_run:
        art_images.push_catalog(only_temple=temple)
        actions += fix_published_product(client, product["id"], ptype)
    else:
        actions.append("would push the art card and run the Shopify fixups")

    if old_handle and old_handle != handle:
        if post.get("delete_old_listing"):
            actions.append(f"old listing {old_handle!r} still needs deleting "
                           f"(store_pulldown.py delete --handle {old_handle})")
        else:
            # Evan's 16 Sep 2026 call: replacements take their own address and
            # old listings stay DRAFT. Deleting was the only irreversible step in
            # the migration and it ate the Printify fallback one product at a
            # time, so this must not keep pointing at it.
            actions.append(f"old listing {old_handle!r} stays DRAFT, not deleted; "
                           f"its dropdown row is repointed by easify_options sync")
    if post.get("set_variant_back_images"):
        # Not automated here on purpose: the repair needs a Tapstitch session and
        # this function is the Shopify half. Naming it in the action list is what
        # stops "required after every publish" depending on memory.
        actions.append("run scripts/tapstitch_variant_images.py "
                       f"--handle {handle} (variants publish bound to the FRONT)")
    return actions


def cmd_finish(handle, temple, garment, dry_run):
    client = ShopifyClient()
    data = ledger.load()
    row = next((r for r in data["rows"]
                if r["temple"] == temple and r["garment"] == garment), None)
    actions = finish_on_shopify(client, temple, garment, handle,
                                old_handle=(row or {}).get("old_shopify_handle"),
                                dry_run=dry_run)
    for a in actions:
        print(f"  {a}")
    if not dry_run and row:
        ledger.set_state(data, temple, garment, "description-written", shopify_handle=handle)
        ledger.save(data)


def cmd_run(args):
    cfg = load_config()
    blocked = missing_config(cfg) + missing_garment_setup()
    if blocked:
        print("Cannot run yet. Blocking items:\n")
        for b in blocked:
            print(f"  {b}")
        print("\nRun `check` for the full picture. The editor values need one live "
              "session with Tapstitch open; the garment items need Evan's blank choices.")
        return 1
    raise SystemExit(
        "The editor steps are configured but not yet written. They are deliberately "
        "left for the first live session, when the network-traffic question in "
        "config/tapstitch.json's _first_session_checklist gets answered: if the "
        "editor's save call carries positions and upload references, a direct call "
        "replaces the whole click path and none of these selectors are needed.")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["check", "finish", "run"])
    ap.add_argument("--handle", help="with `finish`: the new Shopify handle")
    ap.add_argument("--temple")
    ap.add_argument("--garment")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    if a.command == "check":
        sys.exit(cmd_check())
    if a.command == "finish":
        if not (a.handle and a.temple and a.garment):
            raise SystemExit("finish needs --handle, --temple and --garment")
        cmd_finish(a.handle, a.temple, a.garment, a.dry_run)
        return
    sys.exit(cmd_run(a))


if __name__ == "__main__":
    main()
