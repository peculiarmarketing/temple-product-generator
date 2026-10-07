#!/usr/bin/env python
"""Put Eden Green on every temple hoodie, one temple at a time.

WHY EACH TEMPLE IS A NEW PRODUCT. Tapstitch will not add a colour to a listing
that already exists, so every hoodie is rebuilt as a new Tapstitch store product
from its template, which already carries colour 6655 (read back on all 45 on
22 Sep 2026). Distributing that store product does NOT update the old Shopify
product: it creates a second one with the same title. So each temple is a
swap, not an edit. Boise went first by hand on 22 Sep and this is its sequence
written down, with the three mistakes that run made closed off (below).

THE SEQUENCE, per temple:

    resolve     find the live 6-colour product at the ledger's handle and record
                its id. Everything after this addresses products by ID, because
                the old and new products share a title and, after the swap, the
                handle too.
    build       check the template carries every configured colour, read
                Tapstitch's prefill, create the store product with the OLD
                product's live description. Nothing public.       (--apply)
    distribute  the one call with no undo. The time is recorded BEFORE the call,
                so a lost confirmation leads to polling, never a second call.
    hide        the new product appears ACTIVE, beside the old one, in
                Tapstitch's raw state. It is set to DRAFT at once, so the
                storefront keeps showing the finished old listing while the new
                one is built.
    finish      tapstitch_publish.finish_on_shopify (product type, colour
                renames, Navy Blue first, the swatch gate), then the old
                product's description, tags, SEO, template and peculiar.*
                metafields copied across, and the art card.
    gallery     composite THIS temple onto all seven colourway photos, check
                each carries the print, then build_product_gallery.py --add,
                --reface and --prune with --onmodel-dir given explicitly.
    cutover     first the same read-back `verify` does, minus the live-only
                checks, on the still-hidden product. Only if that is clean: old
                product DRAFT at <handle>-retired-<date>, new product onto the
                clean handle, ACTIVE.
    verify      read everything back, including the live storefront page, and
                only then mark the ledger row live.
                                                                  (--publish)

A check that fails re-opens `finish` and `gallery`, both idempotent, so the next
run repairs rather than failing the same way forever.

THE BOISE RUN'S MISTAKES, and what stops each one here:

  1. Every Boise on-model photo showed the SALT LAKE temple under a "Boise
     Temple" alt. build_product_gallery.py falls back to final-set/, which is
     Salt Lake, when --onmodel-dir is not given. This script always passes it,
     and every live on-model image is compared against THIS temple's own
     composite; a match measures 0.0000 and another temple 0.02 to 0.08.
  2. The Eden Green photo was the bare colourway photo with no print at all.
     Every composite is checked against its blank base before upload.
  3. Boise lost the Temple dropdown. Easify binds its option sets to the
     product ID it resolved at import, not the handle, so every new product is
     born without it. Nothing here can fix that: Evan re-imports
     artifacts/easify/option-sets.csv once, after the rollout. The run summary
     says so; `verify` does not check it.

A gallery on the new product is only built after its last Tapstitch-side change,
because a Tapstitch re-sync re-uploads every image and strips its alt text. That
happened to all 44 old hoodies at 19:37 UTC on 22 Sep when their templates were
edited; their pictures survived, their alt text did not.

STATE lives in artifacts/tapstitch/eden-green-rollout.json: the ids and a
timestamp per finished step, written the moment each is known. A re-run resumes
each temple at its first unfinished step. The ledger row goes to `live` only
after `verify` passes.

GATES, the same shape as scripts/tapstitch_run.py:
  (no flags)   plan only, opens no session
  --apply      resolve and build: Tapstitch-side only, nothing public
  --publish    everything else. Needs --apply and a bound (--temple or --limit).
  --verify     read-only check of every temple that has reached cutover

Run the rest in batches of about five: Tapstitch drops connections after a long
burst (HANDOFF.md, 17 Sep).

  python scripts/eden_green_rollout.py
  python scripts/eden_green_rollout.py --apply --publish --temple Bountiful
  python scripts/eden_green_rollout.py --apply --publish --limit 5
  python scripts/eden_green_rollout.py --verify
"""

import argparse
import io
import json
import subprocess
import sys
import tempfile
import time
from datetime import date, datetime
from pathlib import Path

import numpy as np
import requests
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import art_images                                            # noqa: E402
import build_garment_catalog                                 # noqa: E402
import build_product_gallery as gallery                      # noqa: E402
import colour_names                                          # noqa: E402
import generate                                              # noqa: E402
import ledger                                                # noqa: E402
import tapstitch_api as T                                    # noqa: E402
import tapstitch_run                                         # noqa: E402
from shopify_client import ShopifyClient                     # noqa: E402
from tapstitch_approve import resolve_names                  # noqa: E402
from tapstitch_publish import finish_on_shopify              # noqa: E402

GARMENT = "hoodie"
STATE_PATH = ROOT / "artifacts/tapstitch/eden-green-rollout.json"
BLANKS = ROOT / "artifacts/photo-mockup-spike/colourway-photos"
STEPS = ("resolved", "built", "distributed", "hidden", "finished", "gallery",
         "cutover", "verified")
SUPERSEDED = gallery.SUPERSEDED

# Measured 22 Sep 2026 on Boise's composites against their blank colourway
# photos: the share of the back panel the print lifts by more than 60 levels.
# Printed colours ran 0.0022 (Mauve, the palest) to 0.0195; the bare Eden Green
# photo Boise shipped measured 0.0000.
MIN_PRINT = 0.0005
# The share of the back panel that differs from THIS temple's composite by more
# than 40 levels. The same file re-encoded by Shopify measured 0.0000; Salt Lake
# against Boise measured 0.0228 to 0.0793.
MAX_OFF_COMPOSITE = 0.005


class StepError(Exception):
    pass


class CutoverError(Exception):
    """A half-finished cutover: the clean address may not resolve. Stops the run."""


# ---------------------------------------------------------------- state

def now():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def load_state():
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return {"temples": {}}


def save_state(state):
    state["updated_at"] = now()
    STATE_PATH.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")


def mark(state, entry, step):
    entry[step] = now()
    save_state(state)


def reopen(state, entry):
    """Send a temple back through finish and gallery, both idempotent."""
    entry.pop("finished", None)
    entry.pop("gallery", None)
    save_state(state)


def next_step(entry):
    return next((s for s in STEPS if not entry.get(s)), None)


# ---------------------------------------------------------------- reading

PRODUCT_Q = """
query($id: ID!) { product(id: $id) {
  id title handle status vendor productType tags templateSuffix createdAt
  onlineStoreUrl descriptionHtml seo { title description }
  options { name optionValues { name } }
  variants(first: 100) { nodes { id title price
    media(first: 1) { nodes { id } } } }
  media(first: 60) { nodes { id alt ... on MediaImage { image { url width height } } } }
  metafields(first: 50, namespace: "peculiar") { nodes { key type value } }
  collections(first: 30) { nodes { handle } }
} }"""


def product(sc, gid):
    p = sc.gql(PRODUCT_Q, {"id": gid})["product"]
    if not p:
        raise StepError(f"no Shopify product {gid}")
    return p


def colours(p):
    return [v["name"] for o in p["options"] if o["name"] == "Color"
            for v in o["optionValues"]]


def find_new(sc, title, old_id, since=None):
    """The product distribute() created: same title, not the old id, newer.

    Newest first, because the bare Salt Lake title is a prefix of all 45
    hoodie titles and a plain search would bury the new one. `since` None
    means any age, which is the check before distributing at all.
    """
    nodes = sc.gql("""
      query($q: String!) { products(first: 50, sortKey: CREATED_AT, reverse: true,
                                    query: $q) {
        nodes { id title handle status createdAt } } }""",
        {"q": f'title:"{title}"'})["products"]["nodes"]
    floor = datetime.fromisoformat(since).timestamp() - 120 if since else 0
    hits = [n for n in nodes if n["title"].strip() == title and n["id"] != old_id
            and datetime.fromisoformat(n["createdAt"].replace("Z", "+00:00")).timestamp() >= floor]
    if len(hits) > 1:
        raise StepError(f"{len(hits)} other products titled {title!r}: "
                        f"{[h['id'] for h in hits]}. Distribute may have run twice. "
                        "Stopping this temple for a person to look.")
    return hits[0] if hits else None


def names_for(row, title):
    """(alt temple, folder, art card temple) for one row.

    Three names, because the repo uses three: on-model alts follow the PRODUCT
    title ("Ogden Original"), composites live under the Temples/ FOLDER
    ("Ogden (original)"), and art cards carry the folder name the card builder
    resolves ("Temple line art close-up - Washington DC").
    """
    return (build_garment_catalog.temple_of(title), row["temple"],
            art_images.match_temple(title, art_images.temple_tokens()))


# ---------------------------------------------------------------- pixels

def _panel(img, size=512):
    a = np.asarray(img.convert("L").resize((size, size)), dtype=np.float32)
    return a[build_garment_catalog.back_panel(size, size)]


def print_share(img, slug):
    """How much of the back panel the print lifts off this colour's blank photo.
    Signed on purpose: the ink is white, so a print makes the panel LIGHTER."""
    blank = Image.open(BLANKS / f"{GARMENT}_{slug}.png")
    return float(((_panel(img) - _panel(blank)) > 60).mean())


def off_share(img, reference):
    return float((np.abs(_panel(img) - _panel(reference)) > 40).mean())


def fetch_image(url):
    r = requests.get(url, timeout=90, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    return Image.open(io.BytesIO(r.content))


class Composites:
    """This run's on-model composites, one temple at a time, in a temp dir.

    Regenerated rather than kept: composite_catalog.py rebuilds a temple's seven
    in about ten seconds, and it reproduces final-set/ exactly for Salt Lake
    (0.0000 on all six original colours), so Salt Lake needs no special case.
    """

    def __init__(self):
        self._dir = tempfile.TemporaryDirectory(prefix="eden-composites-")
        self.root = Path(self._dir.name)

    def folder(self, temple_folder):
        out = self.root / temple_folder
        if not out.is_dir():
            r = subprocess.run(
                [sys.executable, str(ROOT / "scripts/composite_catalog.py"),
                 "--garment", GARMENT, "--outdir", str(self.root),
                 "--temple", temple_folder], capture_output=True, text=True)
            if r.returncode != 0:
                raise StepError(f"compositing {temple_folder} failed: "
                                f"{(r.stdout + r.stderr)[-400:]}")
        want = gallery.ORDER[GARMENT]
        missing = [c for c in want if not (out / f"{GARMENT}_{c}.jpg").exists()]
        if missing:
            raise StepError(f"no {', '.join(missing)} composite for {temple_folder}")
        for c in want:
            share = print_share(Image.open(out / f"{GARMENT}_{c}.jpg"), c)
            if share < MIN_PRINT:
                raise StepError(f"the {c} composite for {temple_folder} carries no "
                                f"print ({share:.4f}); it is the blank photo")
        return out

    def close(self):
        self._dir.cleanup()


def wrong_onmodel(p, alt_temple, folder):
    """On-model images on this product that are not THIS temple's composite."""
    out = []
    for m in p["media"]["nodes"]:
        alt = m.get("alt") or ""
        for c in gallery.ORDER[GARMENT]:
            if alt == gallery.on_model_alt(alt_temple, GARMENT, c):
                share = off_share(fetch_image(m["image"]["url"]),
                                  Image.open(folder / f"{GARMENT}_{c}.jpg"))
                if share > MAX_OFF_COMPOSITE:
                    out.append((m["id"], alt, share))
    return out


# ---------------------------------------------------------------- steps

def step_resolve(sc, entry, row, cfg, note):
    p = sc.find_product_by_handle(row["shopify_handle"])
    if not p:
        raise StepError(f"nothing at {row['shopify_handle']}")
    old = product(sc, p["id"])
    have = colours(old)
    if len(have) != len(cfg["colorways"]) - 1 or "Eden Green" in have:
        raise StepError(f"{old['handle']} has colours {have}; expected the six "
                        "without Eden Green. Is it already rolled out?")
    if old["status"] != "ACTIVE":
        raise StepError(f"{old['handle']} is {old['status']}, not ACTIVE")
    entry.update(old_id=old["id"], handle=old["handle"], title=old["title"].strip())
    note(f"old product {old['id']} at {old['handle']}, {len(have)} colours")


def step_build(s, sc, entry, row, cfg, note):
    tpl = T.get_template(s, row["tapstitch_template_id"])
    codes = set(str(tpl["colorCode"]).split(","))
    missing = [c["shopify"] for c in cfg["colorways"] if str(c["code"]) not in codes]
    if missing:
        raise StepError(f"template {row['tapstitch_template_id']} lacks {missing}")
    prefill = T.store_product_prefill(s, tapstitch_run.STORE_ID,
                                      row["tapstitch_template_id"])
    offered = {v["name"] for o in prefill["options"] if o["name"] == "Color"
               for v in o["values"]}
    wanted = {c["tapstitch"] for c in cfg["colorways"]}
    sizes = [v for o in prefill["options"] if o["name"] == "Size" for v in o["values"]]
    if offered != wanted or len(prefill["variants"]) != len(wanted) * len(sizes):
        raise StepError(f"prefill offers {sorted(offered)} over "
                        f"{len(prefill['variants'])} variants; wanted {sorted(wanted)}")
    old = product(sc, entry["old_id"])
    price = f"{cfg['price_usd']:.2f}"
    stray = {v["price"] for v in old["variants"]["nodes"]} - {price}
    if stray:
        raise StepError(f"old product sells at {sorted(stray)}, config says {price}")
    if not old["descriptionHtml"]:
        raise StepError("old product has no description to carry across")
    payload = T.store_product_payload(prefill, entry["title"],
                                      int(round(cfg["price_usd"] * 100)),
                                      old["descriptionHtml"],
                                      tapstitch_run.lead_color_id(cfg))
    entry["store_product_id"] = T.create_store_product(s, tapstitch_run.STORE_ID, payload)
    note(f"store product {entry['store_product_id']}, {len(prefill['variants'])} variants")


def step_distribute(s, sc, state, entry, note):
    if not entry.get("distribute_started_at"):
        early = find_new(sc, entry["title"], entry["old_id"])
        if early:
            raise StepError(f"a second product titled {entry['title']!r} already "
                            f"exists ({early['id']}) and this run never distributed. "
                            "Stopping rather than listing it a third time.")
        entry["distribute_started_at"] = now()
        save_state(state)
        T.distribute(s, [entry["store_product_id"]])
        note("distributed")
    else:
        note(f"distribute already attempted {entry['distribute_started_at']}: polling")
    deadline = time.time() + tapstitch_run.SHOPIFY_WAIT_S
    while True:
        new = find_new(sc, entry["title"], entry["old_id"], entry["distribute_started_at"])
        if new:
            break
        if time.time() >= deadline:
            raise StepError("the new product has not appeared on Shopify. The call "
                            "was made, so the next run polls again rather than "
                            "distributing twice.")
        time.sleep(tapstitch_run.SHOPIFY_POLL_S)
    entry["new_id"] = new["id"]
    note(f"new product {new['id']} at {new['handle']}")
    # Hidden the moment it exists; step_hide re-checks after the import.
    if new["status"] == "ACTIVE":
        sc.update_product(new["id"], status="DRAFT")


def step_hide(sc, entry, note):
    note(tapstitch_run.wait_for_import(sc, product(sc, entry["new_id"])["handle"]))
    if product(sc, entry["new_id"])["status"] != "DRAFT":
        sc.update_product(entry["new_id"], status="DRAFT")
    note("new product hidden as DRAFT while it is built")


def step_finish(sc, entry, row, cfg, note):
    new_id = entry["new_id"]
    handle = product(sc, new_id)["handle"]
    for action in finish_on_shopify(sc, row["temple"], GARMENT, handle,
                                    write_description=False, push_art_card=False):
        # finish_on_shopify names the flat-mockup rebind as a follow-up; the
        # gallery step binds every variant to its on-model photo instead.
        if "tapstitch_variant_images" not in action:
            note(action)
    stale = tapstitch_run.stale_colorways(sc, GARMENT, handle)
    if stale:
        raise StepError(f"Tapstitch colour names survived the rename: {stale}")

    # The old product's text, byte for byte. The fixed sections are hardcoded
    # assets and nothing may re-compose them on the way across.
    old = product(sc, entry["old_id"])
    sc.update_product(new_id, descriptionHtml=old["descriptionHtml"], tags=old["tags"],
                      seo=old["seo"], templateSuffix=old["templateSuffix"])
    fields = [{"ownerId": new_id, "namespace": "peculiar", "key": m["key"],
               "type": m["type"], "value": m["value"]}
              for m in old["metafields"]["nodes"]]
    for i in range(0, len(fields), 25):
        errs = sc.gql("""
          mutation($m: [MetafieldsSetInput!]!) { metafieldsSet(metafields: $m) {
            userErrors { field message } } }""", {"m": fields[i:i + 25]})["metafieldsSet"]["userErrors"]
        if errs:
            raise StepError(f"metafieldsSet: {errs}")
    note(f"description, {len(old['tags'])} tags, SEO and {len(fields)} metafields copied")

    # The card for THIS product only; see finish_on_shopify's push_art_card.
    _, _, card_temple = names_for(row, entry["title"])
    alt = f"{art_images.ALT_MARKER} - {card_temple}"
    if not any((m.get("alt") or "") == alt for m in product(sc, new_id)["media"]["nodes"]):
        card = art_images.override_path(card_temple) or (
            art_images.card_path(card_temple) if art_images.card_path(card_temple).exists()
            else art_images.make(card_temple))
        sc.wait_for_media_ready(sc.upload_media_image(new_id, card, alt))
        note(f"art card attached ({card_temple})")


def _builder(new_id, alt_temple, folder, stage, note):
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts/build_product_gallery.py"),
         "--product-gid", new_id, "--garment", GARMENT, "--temple", alt_temple,
         "--onmodel-dir", str(folder), f"--{stage}"], capture_output=True, text=True)
    if r.returncode != 0:
        raise StepError(f"gallery --{stage} failed: {(r.stdout + r.stderr)[-600:]}")
    for line in r.stdout.splitlines():
        if line.startswith("  ") and line.strip():
            note(f"  {line.strip()[:100]}")


def step_gallery(sc, entry, row, comps, note):
    new_id = entry["new_id"]
    alt_temple, folder_name, _ = names_for(row, entry["title"])
    folder = comps.folder(folder_name)
    # A wrong image under the right alt would make --add skip that colour. Move
    # it out of the way first; --add then uploads the right one and rebinds.
    for mid, alt, share in wrong_onmodel(product(sc, new_id), alt_temple, folder):
        sc.update_media_alt(new_id, mid, SUPERSEDED + alt)
        note(f"not this temple's photo ({share:.4f}): {alt}")
    _builder(new_id, alt_temple, folder, "add", note)
    # Read from the product, not from this run: an earlier run may have renamed
    # them and died before getting here.
    p = product(sc, new_id)
    stale = [m["id"] for m in p["media"]["nodes"]
             if (m.get("alt") or "").startswith(SUPERSEDED)]
    if stale:
        bound = {(v["media"]["nodes"] or [{}])[0].get("id") for v in p["variants"]["nodes"]}
        if bound & set(stale):
            raise StepError("a superseded photo is still bound to a variant")
        note(f"deleted {len(sc.delete_media(new_id, stale))} superseded photo(s)")
    _builder(new_id, alt_temple, folder, "reface", note)
    _builder(new_id, alt_temple, folder, "prune", note)


def check(sc, entry, row, cfg, comps, domain=None):
    """Every property of a finished temple, read back. Returns problems.

    With `domain` None, only what can be true of the still-hidden product: the
    content, colours, variants and gallery. With it, also the live state.
    """
    probs = []
    alt_temple, folder_name, card_temple = names_for(row, entry["title"])
    new, old = product(sc, entry["new_id"]), product(sc, entry["old_id"])

    expected = [c["shopify"] for c in cfg["colorways"]]
    if sorted(colours(new)) != sorted(expected) or colours(new)[0] != cfg["storefront_first_color"]:
        probs.append(f"colours are {colours(new)}")
    variants = new["variants"]["nodes"]
    sizes = [v for o in old["options"] if o["name"] == "Size" for v in o["optionValues"]]
    if len(variants) != len(expected) * len(sizes):
        probs.append(f"{len(variants)} variants, expected {len(expected) * len(sizes)}")
    if {v["price"] for v in variants} != {f"{cfg['price_usd']:.2f}"}:
        probs.append(f"prices {sorted({v['price'] for v in variants})}")

    for key in ("descriptionHtml", "seo", "templateSuffix"):
        if new[key] != old[key]:
            probs.append(f"{key} differs from the old product")
    if sorted(new["tags"]) != sorted(old["tags"]):
        probs.append(f"tags {new['tags']} vs {old['tags']}")

    def meta(p):
        return sorted((m["key"], m["type"], m["value"]) for m in p["metafields"]["nodes"])

    if meta(new) != meta(old):
        probs.append("peculiar metafields differ from the old product")

    want = gallery.gallery_order(alt_temple, GARMENT, f"{art_images.ALT_MARKER} - {card_temple}")
    have = [m.get("alt") or "" for m in new["media"]["nodes"]]
    if any(a.startswith(SUPERSEDED) for a in have):
        probs.append("superseded photos are still in the gallery")
    if have != want:
        probs.append(f"gallery is {have}")
    if any((m.get("image") or {}).get("width") != (m.get("image") or {}).get("height")
           for m in new["media"]["nodes"]):
        probs.append("a gallery image is not square")
    by_id = {m["id"]: m.get("alt") for m in new["media"]["nodes"]}
    for v in variants:
        colour = v["title"].split(" / ")[0]
        target = gallery.on_model_alt(alt_temple, GARMENT, colour_names.slug_for(GARMENT, colour))
        bound = by_id.get((v["media"]["nodes"] or [{}])[0].get("id"))
        if bound != target:
            probs.append(f"{v['title']} is bound to {bound!r}")
            break
    for _, alt, share in wrong_onmodel(new, alt_temple, comps.folder(folder_name)):
        probs.append(f"{alt!r} is not this temple's photo ({share:.4f})")
    probs += build_garment_catalog.verify(new, alt_temple, GARMENT)

    if domain is None:
        return probs
    if new["status"] != "ACTIVE" or new["handle"] != entry["handle"]:
        probs.append(f"live: new product is {new['status']} at {new['handle']}")
    if not new["onlineStoreUrl"]:
        probs.append("live: new product is not on the Online Store")
    if old["status"] != "DRAFT" or old["handle"] == entry["handle"]:
        probs.append(f"live: old product is {old['status']} at {old['handle']}")
    want_coll = {c["handle"] for c in old["collections"]["nodes"]}
    have_coll = {c["handle"] for c in new["collections"]["nodes"]}
    if want_coll - have_coll:
        probs.append(f"live, settling: missing from collections {sorted(want_coll - have_coll)}")
    page = requests.get(f"{domain}/products/{entry['handle']}.js", timeout=30,
                        headers={"User-Agent": "Mozilla/5.0"})
    if not page.ok or str(page.json().get("id")) != entry["new_id"].split("/")[-1]:
        probs.append(f"live, settling: storefront {entry['handle']} does not serve "
                     f"the new product (HTTP {page.status_code})")
    return probs


def step_cutover(sc, state, entry, row, cfg, comps, note):
    """Old product off the clean handle and hidden, then the new one onto it.

    Gated on the read-back first, so a defect is caught while the new product
    is still hidden. Old first, because Shopify will not give a handle to two
    products. Between the two calls the clean address resolves to nothing, and a
    lost response on the first call looks exactly like a failure, so ANY
    failure once the first call has been sent ends the run as CutoverError
    unless the old product is provably still in place.
    """
    probs = check(sc, entry, row, cfg, comps)
    if probs:
        reopen(state, entry)
        raise StepError("not cutting over: " + "; ".join(probs))
    clean = entry["handle"]
    retired = f"{clean}-retired-{date.today().isoformat()}"
    try:
        old = product(sc, entry["old_id"])
        if old["handle"] == clean:
            sc.update_product(entry["old_id"], status="DRAFT", handle=retired)
            note(f"old product DRAFT at {retired}")
        elif old["status"] != "DRAFT":
            sc.update_product(entry["old_id"], status="DRAFT")
            note(f"old product DRAFT at {old['handle']}")
        sc.update_product(entry["new_id"], handle=clean, status="ACTIVE")
    except Exception as e:
        try:
            old = product(sc, entry["old_id"])
            intact = old["handle"] == clean and old["status"] == "ACTIVE"
        except Exception:
            intact = False
        if intact:
            raise StepError(f"cutover did not start: {e}")
        raise CutoverError(f"cutover of {clean} stopped part way: {e}. The address "
                           f"may be dark. Re-run this temple.")
    note(f"new product ACTIVE at {clean}")


def step_verify(sc, state, entry, row, cfg, comps, domain, note):
    # Smart collections re-evaluate, and the storefront catches up, a moment
    # after the cutover lands. Those are the only problems worth waiting on.
    for _ in range(4):
        probs = check(sc, entry, row, cfg, comps, domain)
        if not probs or not all(p.startswith("live, settling") for p in probs):
            break
        time.sleep(15)
    if probs:
        if not all(p.startswith("live") for p in probs):
            reopen(state, entry)
        raise StepError("verify: " + "; ".join(probs))
    data = ledger.load()
    fields = {"shopify_handle": entry["handle"]}
    if entry.get("store_product_id"):
        fields["tapstitch_store_product_id"] = entry["store_product_id"]
    ledger.set_state(data, row["temple"], GARMENT, "live", problems=[], **fields)
    ledger.save(data)
    note("verified; ledger row live")


# ---------------------------------------------------------------- driver

def run_temple(s, sc, state, entry, row, cfg, comps, domain, publish, note):
    """One temple as far as the gates allow. Returns False if it was held back."""
    if not entry.get("resolved"):
        step_resolve(sc, entry, row, cfg, note)
        mark(state, entry, "resolved")
    if not entry.get("built"):
        step_build(s, sc, entry, row, cfg, note)
        mark(state, entry, "built")
    if not publish:
        note("held at distribute: --publish not given" if not entry.get("distributed")
             else f"held at {next_step(entry)}: --publish not given")
        return False
    if not entry.get("distributed"):
        step_distribute(s, sc, state, entry, note)
        mark(state, entry, "distributed")
    if not entry.get("hidden"):
        step_hide(sc, entry, note)
        mark(state, entry, "hidden")
    if not entry.get("finished"):
        step_finish(sc, entry, row, cfg, note)
        mark(state, entry, "finished")
    if not entry.get("gallery"):
        step_gallery(sc, entry, row, comps, note)
        mark(state, entry, "gallery")
    if not entry.get("cutover"):
        step_cutover(sc, state, entry, row, cfg, comps, note)
        mark(state, entry, "cutover")
    if not entry.get("verified"):
        step_verify(sc, state, entry, row, cfg, comps, domain, note)
        mark(state, entry, "verified")
    return True


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="resolve and build in Tapstitch")
    ap.add_argument("--publish", action="store_true",
                    help="distribute, build and cut over. LIVE, no undo.")
    ap.add_argument("--temple", action="append", help="ledger temple name; repeatable")
    ap.add_argument("--limit", type=int, help="at most this many unfinished temples")
    ap.add_argument("--verify", action="store_true",
                    help="read-only check of every temple past cutover")
    a = ap.parse_args(argv)
    if a.publish and not a.apply:
        raise SystemExit("--publish needs --apply")
    if a.limit is not None and a.limit < 1:
        raise SystemExit(f"--limit {a.limit} would not select anything. Pass 1 or more.")
    if a.publish and a.limit is None and not a.temple:
        raise SystemExit("--publish needs a bound: --temple or --limit")

    cfg = generate.load_garment_config(GARMENT)
    data, state = ledger.load(), load_state()
    temples = resolve_names(data, a.temple, "--temple") if a.temple else None
    line = [r for r in data["rows"] if r["garment"] == GARMENT]
    rows = [r for r in line if temples is None or r["temple"] in temples]
    entries = state["temples"]

    if a.verify:
        rows = [r for r in rows if entries.get(r["temple"], {}).get("cutover")]
    else:
        rows = [r for r in rows if not entries.get(r["temple"], {}).get("verified")]
        if a.limit is not None:
            rows = rows[:a.limit]
    done = sum(1 for e in entries.values() if e.get("verified"))
    print(f"{done} of {len(line)} hoodies verified with Eden Green. This run: {len(rows)}.\n")
    for r in rows:
        e = entries.get(r["temple"], {})
        extra = f"  (last problem: {e['problem']})" if e.get("problem") else ""
        print(f"  {r['temple']:<22} next: {next_step(e) or 'done'}{extra}")
    if not rows:
        return 0
    if not (a.apply or a.verify):
        print("\nPlan only. --apply builds in Tapstitch; --publish as well goes live.")
        return 0

    drift = colour_names.check_against_garments(generate.load_garment_config, [GARMENT])
    if drift:
        raise SystemExit("colour names disagree:\n  " + "\n  ".join(drift))
    sc = ShopifyClient()
    domain = sc.gql("{ shop { primaryDomain { url } } }")["shop"]["primaryDomain"]["url"]
    comps = Composites()
    s = None if a.verify else T.session()
    failed, streak = [], 0

    def note(msg):
        print(f"    {msg}", flush=True)

    try:
        for r in rows:
            print(f"\n{r['temple']}")
            entry = entries.setdefault(r["temple"], {})
            try:
                if a.verify:
                    probs = check(sc, entry, r, cfg, comps, domain)
                    note("OK" if not probs else "\n    ".join(probs))
                    if probs:
                        failed.append((r["temple"], "verify"))
                    continue
                finished = run_temple(s, sc, state, entry, r, cfg, comps, domain,
                                      a.publish, note)
                streak = 0
            except CutoverError as e:
                entry["problem"] = tapstitch_run.safe_error(e)
                save_state(state)
                print(f"    STOPPING THE RUN: {e}")
                failed.append((r["temple"], "cutover"))
                break
            except (Exception, SystemExit) as e:
                entry["problem"] = tapstitch_run.safe_error(e)
                save_state(state)
                print(f"    FAILED at {next_step(entry)}: {tapstitch_run.safe_error(e)}")
                failed.append((r["temple"], next_step(entry)))
                streak += 1
                if streak >= 2:
                    print("\nTwo temples in a row failed. Stopping for a person to look.")
                    break
            else:
                # A temple held back by the gates has not fixed whatever stopped
                # it last time, so its recorded problem stays.
                if finished:
                    entry.pop("problem", None)
                    save_state(state)
    finally:
        comps.close()

    print(f"\n{len(rows) - len(failed)} ok, {len(failed)} failed.")
    for t, st in failed:
        print(f"  {t}: stopped at {st}")
    if a.publish:
        print("\nEvery new product is born without the Temple dropdown. After the "
              "last temple, re-import artifacts/easify/option-sets.csv in Easify.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
