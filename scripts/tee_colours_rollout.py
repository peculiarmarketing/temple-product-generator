#!/usr/bin/env python
"""Add Pink, Light Blue and Cream to every live tee: the 45 temple tees and the
Nauvoo and Salt Lake City map tees (Evan, 8 Oct 2026).

Same shape as scripts/eden_green_rollout.py (read its docstring: why each
product is a SWAP, the cutover order, the Easify consequence), with three
differences for the tees:

  COPY, NOT RE-SAVE. The live tee designs carry five colours and Tapstitch adds
  colours only at the design. Re-saving the live design would make Tapstitch
  re-send the live product's images two minutes later, alt text stripped and
  sometimes FAILED (the 7 Oct relift met that on 39 products). So `copy` makes a
  NEW private design from the live one's exact config with all eight colours
  (tapstitch_api.copy_design, proven by reading the config back); the live
  product is untouched until its replacement takes its address.

  GALLERY CARRIED ACROSS. The temple galleries were finished by hand-run steps
  whose inputs (the Temples/ folder, colourway photos) live on the Mac. Instead
  of rebuilding, `gallery` copies the OLD product's finished gallery image for
  image, alt text and order intact, then adds the three new colours' on-model
  backs after the last on-model shot. Those are composited from the design's own
  Tapstitch print file onto the 8 Oct recolours of the same tee model
  (scripts/tee_new_colour_composites.py), with composite_catalog.py's settings.
  The map tee's gallery is Tapstitch's own flats, so it keeps the new product's
  Tapstitch images (all eight colours), alt text copied from the old product.

  COLOUR ORDER. The old product's order with the new three appended, so the
  page opens on the same colour as before.

Steps per product, each timestamped in artifacts/tapstitch/tee-colours-rollout.json:
  resolved copied built distributed hidden finished gallery cutover verified

GATES as the Eden Green rollout: no flags = plan; --apply = resolve, copy,
build (Tapstitch only, nothing public); --publish = the rest, needs a bound
(--only or --limit). --verify = read-only check of everything past cutover.

  python scripts/tee_colours_rollout.py
  python scripts/tee_colours_rollout.py --apply --publish --only Albuquerque
  python scripts/tee_colours_rollout.py --apply --publish --limit 5
  python scripts/tee_colours_rollout.py --verify
"""
import argparse
import io
import json
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

import build_product_gallery as gallery                      # noqa: E402
import colour_names                                          # noqa: E402
import generate                                              # noqa: E402
import ledger                                                # noqa: E402
import tapstitch_api as T                                    # noqa: E402
import tapstitch_run                                         # noqa: E402
import tee_new_colour_composites as newcomp                  # noqa: E402
from shopify_client import ShopifyClient                     # noqa: E402
from tapstitch_publish import finish_on_shopify              # noqa: E402

GARMENT = "tee"
STATE_PATH = ROOT / "artifacts/tapstitch/tee-colours-rollout.json"
STEPS = ("resolved", "copied", "built", "distributed", "hidden", "finished",
         "gallery", "cutover", "verified")
OLD_COLOURS = {"Black", "Charcoal", "Coffee", "Navy Blue", "Maroon"}
NEW = [("pink", "Pink"), ("light-blue", "Light Blue"), ("cream", "Cream")]
# Map products made by scripts/map_run.py (branch claude/happy-volta-gmsrac);
# not in the ledger. name -> (handle, template id from artifacts/maps/<place>/state.json)
MAPS = {"Nauvoo map": ("essential-heavyweight-map-tee-nauvoo", "1557934356767600640"),
        "Salt Lake City map": ("essential-heavyweight-map-tee-salt-lake-city", "1557943287829123072")}
MIN_PRINT = 0.0005     # as eden_green_rollout: a composite must lift the panel


class StepError(Exception):
    pass


class CutoverError(Exception):
    pass


def now():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def load_state():
    return json.loads(STATE_PATH.read_text()) if STATE_PATH.exists() else {"products": {}}


def save_state(state):
    state["updated_at"] = now()
    STATE_PATH.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")


def next_step(entry):
    return next((s for s in STEPS if not entry.get(s)), None)


PRODUCT_Q = """
query($id: ID!) { product(id: $id) {
  id title handle status productType tags templateSuffix onlineStoreUrl
  descriptionHtml seo { title description }
  options { name optionValues { name } }
  variants(first: 100) { nodes { id title price selectedOptions { name value }
    media(first: 1) { nodes { id } } } }
  media(first: 60) { nodes { id alt status ... on MediaImage { image { url width height } } } }
  metafields(first: 50, namespace: "peculiar") { nodes { key type value } }
  collections(first: 30) { nodes { handle } }
} }"""


def product(sc, gid):
    p = sc.gql(PRODUCT_Q, {"id": gid})["product"]
    if not p:
        raise StepError(f"no Shopify product {gid}")
    return p


def colours(p):
    return [v["name"] for o in p["options"] if o["name"] == "Color" for v in o["optionValues"]]


def items(data):
    """(name, kind, handle, template id, alt temple) for every tee in scope."""
    out = []
    for r in data["rows"]:
        if r["garment"] == GARMENT:
            out.append((r["temple"], "temple", r["shopify_handle"], r["tapstitch_template_id"], r))
    for name, (handle, tpl) in MAPS.items():
        out.append((name, "map", handle, tpl, None))
    return out


# ---------------------------------------------------------------- steps

def step_resolve(sc, entry, handle):
    p = sc.find_product_by_handle(handle)
    if not p:
        raise StepError(f"nothing at {handle}")
    old = product(sc, p["id"])
    have = set(colours(old))
    if have != OLD_COLOURS:
        raise StepError(f"{handle} has colours {sorted(have)}; expected the five. Done already?")
    if old["status"] != "ACTIVE":
        raise StepError(f"{handle} is {old['status']}, not ACTIVE")
    entry.update(old_id=old["id"], handle=old["handle"], title=old["title"].strip(),
                 old_colour_order=colours(old))


def step_copy(s, entry, template_id, blank):
    entry["source_template_id"] = template_id
    entry["template_id"] = T.copy_design(s, template_id, blank, blank["colorCodes"].split(","))


def step_build(s, sc, entry, cfg):
    prefill = T.store_product_prefill(s, tapstitch_run.STORE_ID, entry["template_id"])
    offered = {v["name"] for o in prefill["options"] if o["name"] == "Color" for v in o["values"]}
    wanted = {c["tapstitch"] for c in cfg["colorways"]}
    sizes = [v for o in prefill["options"] if o["name"] == "Size" for v in o["values"]]
    if offered != wanted or len(prefill["variants"]) != len(wanted) * len(sizes):
        raise StepError(f"prefill offers {sorted(offered)} over {len(prefill['variants'])} variants")
    old = product(sc, entry["old_id"])
    price = f"{cfg['price_usd']:.2f}"
    stray = {v["price"] for v in old["variants"]["nodes"]} - {price}
    if stray:
        raise StepError(f"old product sells at {sorted(stray)}, config says {price}")
    payload = T.store_product_payload(prefill, entry["title"], int(round(cfg["price_usd"] * 100)),
                                      old["descriptionHtml"], tapstitch_run.lead_color_id(cfg))
    entry["store_product_id"] = T.create_store_product(s, tapstitch_run.STORE_ID, payload)


def find_new(sc, title, old_id, since=None):
    nodes = sc.gql("""
      query($q: String!) { products(first: 50, sortKey: CREATED_AT, reverse: true, query: $q) {
        nodes { id title handle status createdAt } } }""", {"q": f'title:"{title}"'})["products"]["nodes"]
    floor = datetime.fromisoformat(since).timestamp() - 120 if since else 0
    hits = [n for n in nodes if n["title"].strip() == title and n["id"] != old_id
            and datetime.fromisoformat(n["createdAt"].replace("Z", "+00:00")).timestamp() >= floor
            and "-retired-" not in n["handle"]]
    if len(hits) > 1:
        raise StepError(f"{len(hits)} other products titled {title!r}; distribute twice? Stopping.")
    return hits[0] if hits else None


def step_distribute(s, sc, state, entry):
    if not entry.get("distribute_started_at"):
        if find_new(sc, entry["title"], entry["old_id"]):
            raise StepError("a second product with this title already exists")
        entry["distribute_started_at"] = now()
        save_state(state)
        T.distribute(s, [entry["store_product_id"]])
    deadline = time.time() + tapstitch_run.SHOPIFY_WAIT_S
    while True:
        new = find_new(sc, entry["title"], entry["old_id"], entry["distribute_started_at"])
        if new:
            break
        if time.time() >= deadline:
            raise StepError("new product has not appeared; the next run polls again")
        time.sleep(tapstitch_run.SHOPIFY_POLL_S)
    entry["new_id"] = new["id"]
    if new["status"] == "ACTIVE":
        sc.update_product(new["id"], status="DRAFT")


def step_hide(sc, entry, note):
    note(tapstitch_run.wait_for_import(sc, product(sc, entry["new_id"])["handle"]))
    if product(sc, entry["new_id"])["status"] != "DRAFT":
        sc.update_product(entry["new_id"], status="DRAFT")


def step_finish(sc, entry, name, note):
    new_id = entry["new_id"]
    handle = product(sc, new_id)["handle"]
    for action in finish_on_shopify(sc, name, GARMENT, handle,
                                    write_description=False, push_art_card=False):
        if "tapstitch_variant_images" not in action:
            note(action)
    stale = tapstitch_run.stale_colorways(sc, GARMENT, handle)
    if stale:
        raise StepError(f"Tapstitch colour names survived the rename: {stale}")
    order = entry["old_colour_order"] + [n for _, n in NEW]
    reorder_colours(sc, new_id, order)
    old = product(sc, entry["old_id"])
    sc.update_product(new_id, descriptionHtml=old["descriptionHtml"], tags=old["tags"],
                      seo=old["seo"], templateSuffix=old["templateSuffix"],
                      productType=old["productType"])
    fields = [{"ownerId": new_id, "namespace": "peculiar", "key": m["key"],
               "type": m["type"], "value": m["value"]} for m in old["metafields"]["nodes"]]
    for i in range(0, len(fields), 25):
        errs = sc.gql("""mutation($m: [MetafieldsSetInput!]!) { metafieldsSet(metafields: $m) {
            userErrors { field message } } }""", {"m": fields[i:i + 25]})["metafieldsSet"]["userErrors"]
        if errs:
            raise StepError(f"metafieldsSet: {errs}")
    note(f"colours {order}; description, tags, SEO, template, {len(fields)} metafields copied")


def reorder_colours(sc, gid, order):
    p = sc.gql("""query($id: ID!) { product(id: $id) { options { id name optionValues { name } } } }""",
               {"id": gid})["product"]
    payload = []
    for o in p["options"]:
        names = [v["name"] for v in o["optionValues"]]
        if o["name"] == "Color":
            if sorted(names) != sorted(order):
                raise StepError(f"colours {names} vs wanted {order}")
            names = order
        elif o["name"] == "Size":
            canon = ["XS", "S", "M", "L", "XL", "2XL", "3XL"]
            names = [n for n in canon if n in names] + [n for n in names if n not in canon]
        payload.append({"id": o["id"], "values": [{"name": n} for n in names]})
    errs = sc.gql("""mutation($p: ID!, $o: [OptionReorderInput!]!) {
        productOptionsReorder(productId: $p, options: $o) { userErrors { message } } }""",
                  {"p": gid, "o": payload})["productOptionsReorder"]["userErrors"]
    if errs:
        raise StepError(f"reorder: {errs}")


def _panel(img, size=512):
    import build_garment_catalog
    a = np.asarray(img.convert("L").resize((size, size)), dtype=np.float32)
    return a[build_garment_catalog.back_panel(size, size)]


def new_composites(s, entry, tmp):
    out = Path(tmp) / entry["handle"]
    out.mkdir(parents=True, exist_ok=True)
    art, _ = newcomp.back_print(s, entry["source_template_id"], out / "back_print.png")
    files = newcomp.composite(art, out)
    for slug, p in files.items():
        blank = Image.open(newcomp.BLANKS / f"back_tee_{slug}.jpg")
        # 15 levels, not eden_green_rollout's 60: white ink on Cream (~225) can
        # only lift a pixel ~30. A bare blank measures 0.0000 either way.
        share = float(((_panel(Image.open(p)) - _panel(blank)) > 15).mean())
        if share < MIN_PRINT:
            raise StepError(f"{slug} composite carries no print ({share:.4f})")
    return files


def bind(sc, gid, by_colour):
    p = product(sc, gid)
    upd = []
    for v in p["variants"]["nodes"]:
        col = next(o["value"] for o in v["selectedOptions"] if o["name"] == "Color")
        if col not in by_colour:
            raise StepError(f"no image for colour {col}")
        upd.append({"id": v["id"], "mediaId": by_colour[col]})
    errs = sc.gql("""mutation($p: ID!, $v: [ProductVariantsBulkInput!]!) {
        productVariantsBulkUpdate(productId: $p, variants: $v) { userErrors { message } } }""",
                  {"p": gid, "v": upd})["productVariantsBulkUpdate"]["userErrors"]
    if errs:
        raise StepError(f"bind: {errs}")


def reorder_media(sc, gid, ids):
    r = sc.gql("""mutation($id: ID!, $m: [MoveInput!]!) {
        productReorderMedia(id: $id, moves: $m) { job { id } mediaUserErrors { message } } }""",
               {"id": gid, "m": [{"id": m, "newPosition": str(i)} for i, m in enumerate(ids)]}
               )["productReorderMedia"]
    if r["mediaUserErrors"]:
        raise StepError(str(r["mediaUserErrors"]))
    sc._wait_for_job((r.get("job") or {}).get("id"))


def add_by_url(sc, gid, url, alt):
    r = sc.gql("""mutation($p: ID!, $m: [CreateMediaInput!]!) {
        productCreateMedia(productId: $p, media: $m) { media { id } mediaUserErrors { message } } }""",
               {"p": gid, "m": [{"originalSource": url, "alt": alt, "mediaContentType": "IMAGE"}]}
               )["productCreateMedia"]
    if r["mediaUserErrors"]:
        raise StepError(str(r["mediaUserErrors"]))
    return r["media"][0]["id"]


def step_gallery_temple(s, sc, entry, alt_temple, tmp, note):
    """New gallery = the old gallery, copied, plus the three new on-model backs
    after the last on-model shot. Tapstitch's own images on the new product go."""
    new_id = entry["new_id"]
    old, new = product(sc, entry["old_id"]), product(sc, new_id)
    copied = entry.setdefault("copied_media", {})          # old media id -> new media id
    for m in old["media"]["nodes"]:
        if m["id"] not in copied:
            copied[m["id"]] = add_by_url(sc, new_id, m["image"]["url"], m.get("alt") or "")
    added = entry.setdefault("new_onmodel", {})
    files = None
    for slug, name in NEW:
        if slug not in added:
            files = files or new_composites(s, entry, tmp)
            added[slug] = sc.upload_media_image(new_id, files[slug],
                                                gallery.on_model_alt(alt_temple, GARMENT, slug))
    for mid in list(copied.values()) + list(added.values()):
        sc.wait_for_media_ready(mid, timeout_s=300)
    # Order: the old order with the new three after the last on-model shot.
    old_ids = [copied[m["id"]] for m in old["media"]["nodes"]]
    alts = [m.get("alt") or "" for m in old["media"]["nodes"]]
    last_onmodel = max(i for i, a in enumerate(alts) if " back print on model - " in a)
    order = old_ids[:last_onmodel + 1] + [added[s] for s, _ in NEW] + old_ids[last_onmodel + 1:]
    # Bind every colour to its on-model back, then drop Tapstitch's images.
    by_alt = {a: copied[m["id"]] for m, a in zip(old["media"]["nodes"], alts)}
    by_colour = {}
    for c in entry["old_colour_order"]:
        a = gallery.on_model_alt(alt_temple, GARMENT, colour_names.slug_for(GARMENT, c))
        if a not in by_alt:
            raise StepError(f"old gallery has no {a!r}")
        by_colour[c] = by_alt[a]
    for slug, name in NEW:
        by_colour[name] = added[slug]
    bind(sc, new_id, by_colour)
    keep = set(order)
    stray = [m["id"] for m in product(sc, new_id)["media"]["nodes"] if m["id"] not in keep]
    if stray:
        sc.delete_media(new_id, stray)
    reorder_media(sc, new_id, order)
    entry["gallery_order"] = order
    note(f"gallery: {len(old_ids)} copied + 3 new on-model, {len(stray)} Tapstitch images removed")


def step_gallery_map(s, sc, entry, note):
    """Tapstitch's own flats for all eight colours, each variant on its back,
    alt text as the old product's (map_run.py sets one alt for the set)."""
    import tapstitch_variant_images
    new_id = entry["new_id"]
    handle = product(sc, new_id)["handle"]
    msg = tapstitch_variant_images.rebind(sc, s, handle, entry["template_id"])
    if msg:
        note(msg)
    old_alts = {m.get("alt") or "" for m in product(sc, entry["old_id"])["media"]["nodes"]}
    if len(old_alts) != 1:
        raise StepError(f"old map gallery has {len(old_alts)} alt texts; expected one for the set")
    alt = next(iter(old_alts))
    for m in product(sc, new_id)["media"]["nodes"]:
        if (m.get("alt") or "") != alt:
            sc.update_media_alt(new_id, m["id"], alt)
    entry["gallery_order"] = [m["id"] for m in product(sc, new_id)["media"]["nodes"]]
    note(f"gallery: {len(entry['gallery_order'])} Tapstitch images, alt {alt!r}")


def check(sc, entry, kind, alt_temple, cfg, domain=None):
    probs = []
    new, old = product(sc, entry["new_id"]), product(sc, entry["old_id"])
    want_c = entry["old_colour_order"] + [n for _, n in NEW]
    if colours(new) != want_c:
        probs.append(f"colours {colours(new)}")
    sizes = [v for o in old["options"] if o["name"] == "Size" for v in o["optionValues"]]
    if len(new["variants"]["nodes"]) != len(want_c) * len(sizes):
        probs.append(f"{len(new['variants']['nodes'])} variants")
    if {v["price"] for v in new["variants"]["nodes"]} != {f"{cfg['price_usd']:.2f}"}:
        probs.append("prices differ")
    for k in ("descriptionHtml", "seo", "templateSuffix", "productType"):
        if new[k] != old[k]:
            probs.append(f"{k} differs")
    if sorted(new["tags"]) != sorted(old["tags"]):
        probs.append("tags differ")
    meta = lambda p: sorted((m["key"], m["type"], m["value"]) for m in p["metafields"]["nodes"])
    if meta(new) != meta(old):
        probs.append("metafields differ")
    media = new["media"]["nodes"]
    if any(m["status"] != "READY" for m in media):
        probs.append("media not READY")
    if [m["id"] for m in media] != entry.get("gallery_order"):
        probs.append("gallery order differs from the one built")
    alt_of = {m["id"]: m.get("alt") or "" for m in media}
    if kind == "temple":
        want_alts = [m.get("alt") or "" for m in old["media"]["nodes"]]
        last = max(i for i, a in enumerate(want_alts) if " back print on model - " in a)
        want_alts = want_alts[:last + 1] + [gallery.on_model_alt(alt_temple, GARMENT, s) for s, _ in NEW] \
            + want_alts[last + 1:]
        if [alt_of[m["id"]] for m in media] != want_alts:
            probs.append("gallery alts differ from old + new three")
        for v in new["variants"]["nodes"]:
            col = next(o["value"] for o in v["selectedOptions"] if o["name"] == "Color")
            b = (v["media"]["nodes"] or [{}])[0].get("id")
            if alt_of.get(b) != gallery.on_model_alt(alt_temple, GARMENT, colour_names.slug_for(GARMENT, col)):
                probs.append(f"{v['title']} bound to {alt_of.get(b)!r}")
                break
    else:
        if any(not (v["media"]["nodes"]) for v in new["variants"]["nodes"]):
            probs.append("a variant has no image")
    if domain is None:
        return probs
    if new["status"] != "ACTIVE" or new["handle"] != entry["handle"]:
        probs.append(f"live: new product {new['status']} at {new['handle']}")
    if not new["onlineStoreUrl"]:
        probs.append("live: new product not on the Online Store")
    if old["status"] != "DRAFT" or old["handle"] == entry["handle"]:
        probs.append(f"live: old product {old['status']} at {old['handle']}")
    missing = {c["handle"] for c in old["collections"]["nodes"]} - {c["handle"] for c in new["collections"]["nodes"]}
    if missing:
        probs.append(f"live, settling: missing from collections {sorted(missing)}")
    page = requests.get(f"{domain}/products/{entry['handle']}.js", timeout=30,
                        headers={"User-Agent": "Mozilla/5.0"})
    if not page.ok or str(page.json().get("id")) != entry["new_id"].split("/")[-1]:
        probs.append(f"live, settling: storefront does not serve the new product ({page.status_code})")
    return probs


def step_cutover(sc, entry, kind, alt_temple, cfg, note):
    probs = check(sc, entry, kind, alt_temple, cfg)
    if probs:
        entry.pop("finished", None)
        entry.pop("gallery", None)
        raise StepError("not cutting over: " + "; ".join(probs))
    clean, retired = entry["handle"], f"{entry['handle']}-retired-{date.today().isoformat()}"
    try:
        old = product(sc, entry["old_id"])
        if old["handle"] == clean:
            sc.update_product(entry["old_id"], status="DRAFT", handle=retired)
        elif old["status"] != "DRAFT":
            sc.update_product(entry["old_id"], status="DRAFT")
        sc.update_product(entry["new_id"], handle=clean, status="ACTIVE")
    except Exception as e:
        try:
            old = product(sc, entry["old_id"])
            intact = old["handle"] == clean and old["status"] == "ACTIVE"
        except Exception:
            intact = False
        if intact:
            raise StepError(f"cutover did not start: {e}")
        raise CutoverError(f"cutover of {clean} stopped part way: {e}")
    note(f"old DRAFT at {retired}; new ACTIVE at {clean}")


def step_verify(sc, entry, kind, alt_temple, cfg, domain, row, note):
    for _ in range(6):
        probs = check(sc, entry, kind, alt_temple, cfg, domain)
        if not probs or not all(p.startswith("live, settling") for p in probs):
            break
        time.sleep(15)
    if probs:
        raise StepError("verify: " + "; ".join(probs))
    if row is not None:
        data = ledger.load()
        ledger.set_state(data, row["temple"], GARMENT, "live", problems=[],
                         shopify_handle=entry["handle"], tapstitch_template_id=entry["template_id"],
                         tapstitch_store_product_id=entry["store_product_id"])
        ledger.save(data)
    note("verified")


def run_one(s, sc, state, entry, item, cfg, blank, domain, tmp, publish, note):
    name, kind, handle, tpl, row = item
    alt_temple = None
    if kind == "temple":
        import build_garment_catalog
        alt_temple = build_garment_catalog.temple_of(entry.get("title") or "") if entry.get("title") else None

    def done(step):
        entry[step] = now()
        save_state(state)

    if not entry.get("resolved"):
        step_resolve(sc, entry, handle); done("resolved")
    if kind == "temple":
        import build_garment_catalog
        alt_temple = build_garment_catalog.temple_of(entry["title"])
    if not entry.get("copied"):
        step_copy(s, entry, tpl, blank); done("copied"); note(f"design copied -> {entry['template_id']}")
    if not entry.get("built"):
        step_build(s, sc, entry, cfg); done("built"); note(f"store product {entry['store_product_id']}")
    if not publish:
        note(f"held at {next_step(entry)}: --publish not given")
        return
    if not entry.get("distributed"):
        step_distribute(s, sc, state, entry); done("distributed"); note(f"new product {entry['new_id']}")
    if not entry.get("hidden"):
        step_hide(sc, entry, note); done("hidden")
    if not entry.get("finished"):
        step_finish(sc, entry, row["temple"] if row else name, note); done("finished")
    if not entry.get("gallery"):
        if kind == "temple":
            step_gallery_temple(s, sc, entry, alt_temple, tmp, note)
        else:
            step_gallery_map(s, sc, entry, note)
        done("gallery")
    if not entry.get("cutover"):
        step_cutover(sc, entry, kind, alt_temple, cfg, note); done("cutover")
    if not entry.get("verified"):
        step_verify(sc, entry, kind, alt_temple, cfg, domain, row, note); done("verified")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--publish", action="store_true")
    ap.add_argument("--only", action="append", help="temple name or 'Nauvoo map'; repeatable")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--verify", action="store_true")
    a = ap.parse_args(argv)
    if a.publish and not a.apply:
        raise SystemExit("--publish needs --apply")
    if a.publish and not (a.only or a.limit):
        raise SystemExit("--publish needs a bound: --only or --limit")

    cfg = generate.load_garment_config(GARMENT)
    blank = json.loads((ROOT / "config/tapstitch.json").read_text())["api"]["blanks"][GARMENT]
    if len(blank["colorCodes"].split(",")) != len(cfg["colorways"]):
        raise SystemExit("config/tapstitch.json tee colours and garments/tee.json disagree")
    state = load_state()
    entries = state["products"]
    todo = [i for i in items(ledger.load()) if not a.only or i[0] in a.only]
    if a.verify:
        todo = [i for i in todo if entries.get(i[0], {}).get("cutover")]
    else:
        todo = [i for i in todo if not entries.get(i[0], {}).get("verified")]
        if a.limit:
            todo = todo[:a.limit]
    done_n = sum(1 for e in entries.values() if e.get("verified"))
    print(f"{done_n} verified with the new colours. This run: {len(todo)}.")
    for i in todo:
        e = entries.get(i[0], {})
        print(f"  {i[0]:<24} next: {next_step(e) or 'done'}"
              + (f"   (last problem: {e['problem']})" if e.get("problem") else ""))
    if not (a.apply or a.verify) or not todo:
        return 0

    sc = ShopifyClient()
    domain = sc.gql("{ shop { primaryDomain { url } } }")["shop"]["primaryDomain"]["url"]
    s = None if a.verify else T.session()
    failed, streak = [], 0
    with tempfile.TemporaryDirectory(prefix="tee-colours-") as tmp:
        for item in todo:
            print(f"\n{item[0]}", flush=True)
            entry = entries.setdefault(item[0], {})

            def note(msg):
                print(f"    {msg}", flush=True)
            try:
                if a.verify:
                    import build_garment_catalog
                    alt = build_garment_catalog.temple_of(entry["title"]) if item[1] == "temple" else None
                    probs = check(sc, entry, item[1], alt, cfg, domain)
                    note("OK" if not probs else "; ".join(probs))
                    if probs:
                        failed.append(item[0])
                    continue
                run_one(s, sc, state, entry, item, cfg, blank, domain, tmp, a.publish, note)
                entry.pop("problem", None)
                save_state(state)
                streak = 0
            except CutoverError as e:
                entry["problem"] = tapstitch_run.safe_error(e)
                save_state(state)
                print(f"    STOPPING THE RUN: {e}")
                failed.append(item[0])
                break
            except (Exception, SystemExit) as e:
                entry["problem"] = tapstitch_run.safe_error(e)
                save_state(state)
                print(f"    FAILED at {next_step(entry)}: {tapstitch_run.safe_error(e)}")
                failed.append(item[0])
                streak += 1
                if streak >= 2:
                    print("\nTwo in a row failed. Stopping for a person to look.")
                    break
    print(f"\n{len(todo) - len(failed)} ok, {len(failed)} failed: {failed}")
    if a.publish:
        print("Every new temple tee is born without the Easify Temple dropdown: "
              "re-import artifacts/easify/option-sets.csv after the last one.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
