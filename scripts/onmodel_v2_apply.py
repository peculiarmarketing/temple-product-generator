#!/usr/bin/env python
"""Swap the v1 on-model photos for v2 on the seven Be Peculiar / seal bomber drafts.

Evan, 8 Oct 2026: full replace on the draft products so he can preview them in
Shopify. Order per product, chosen so a variant never points at a missing image:

  1. upload every v2 final and close-up card (staged upload, no git needed)
  2. wait until each is READY
  3. bind each colour's variants to its new on-model shot (bomber: the back shot)
  4. delete the v1 on-model media (alt contains " on model - ")
  5. reorder: v2 on-model in gallery order (lead colour first), cards, then the
     Tapstitch flats in their existing order
  6. read back: order, alts, every variant bound to a v2 image, status still DRAFT

  python scripts/onmodel_v2_apply.py            # plan only
  python scripts/onmodel_v2_apply.py --apply    # do it
  python scripts/onmodel_v2_apply.py --verify   # read back only
Products stay DRAFT; nothing here touches status.
"""
import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "artifacts" / "photo-mockup-spike"))
from shopify_client import ShopifyClient, ShopifyError  # noqa: E402
from review_v2 import gallery_order  # noqa: E402

V2 = ROOT / "artifacts" / "onmodel-v2"
STATE = V2 / "applied.json"

# product id -> (finals prefix, language suffix or None, lead final, cards, alt prefixes)
PRODUCTS = {
    15350048260468: ("crew", "es", "crew_black_es", ["card_crew_es"], "Sé Singular sweatshirt front print"),
    15350036955508: ("crew", "en", "crew_black_en", ["card_crew_en"], "Be Peculiar sweatshirt front print"),
    15350048326004: ("hoodie", "es", "hoodie_coffee_es", ["card_hoodie_es"], "Sé Singular hoodie front print"),
    15350048391540: ("hoodie", "en", "hoodie_gray_en", ["card_hoodie_en"], "Be Peculiar hoodie front print"),
    15350048424308: ("tee", "es", "tee_navy-blue_es", ["card_tee_es"], "Sé Singular tee front print"),
    15350048457076: ("tee", "en", "tee_black_en", ["card_tee_en"], "Be Peculiar tee front print"),
    15350048522612: ("bomber", None, "bomber_navy-blue_back", ["card_bomber_seal"], None),
}
CARD_ALT = {
    "card_tee_en": "Be Peculiar design close-up", "card_crew_en": "Be Peculiar design close-up",
    "card_hoodie_en": "Be Peculiar design close-up", "card_tee_es": "Sé Singular design close-up",
    "card_crew_es": "Sé Singular design close-up", "card_hoodie_es": "Sé Singular design close-up",
    "card_bomber_chest": "Temple Seal bomber jacket chest logo close-up",
    "card_bomber_seal": "Temple Seal bomber jacket back seal close-up",
}

Q = """query($id: ID!) { product(id: $id) { id title status
  media(first: 80) { nodes { id alt status mediaContentType } }
  variants(first: 100) { nodes { id selectedOptions { name value } media(first: 1) { nodes { id } } } } } }"""


def colour_name(slug, values):
    for v in values:
        if v.lower().replace(" ", "-") == slug:
            return v
    raise SystemExit(f"no colour value for {slug} in {values}")


def plan_for(pid, product):
    g, lang, lead, cards, prefix = PRODUCTS[pid]
    finals = sorted(p.stem for p in (V2 / "final").glob(f"{g}_*.jpg")
                    if lang is None or p.stem.endswith(f"_{lang}"))
    finals = gallery_order(finals, lead)
    colours = sorted({o["value"] for v in product["variants"]["nodes"]
                      for o in v["selectedOptions"] if o["name"] == "Color"})
    items = []
    for f in finals:
        slug = f.split("_")[1]
        c = colour_name(slug, colours)
        if g == "bomber":
            if f.endswith("_back"):
                alt = f"Temple Seal bomber jacket back print on model - {c}"
            elif f.endswith("_open"):
                alt = f"Temple Seal bomber jacket chest logo on model, unzipped over a white tee - {c}"
            else:
                alt = f"Temple Seal bomber jacket chest logo on model - {c}"
            binds = f.endswith("_back")
        else:
            alt = f"{prefix} on model - {c}"
            binds = True
        items.append({"key": f, "path": str(V2 / "final" / f"{f}.jpg"), "alt": alt,
                      "colour": c if binds else None})
    for cd in cards:
        items.append({"key": cd, "path": str(V2 / "cards" / f"{cd}.png"), "alt": CARD_ALT[cd], "colour": None})
    return items


def is_v1_onmodel(alt):
    return " on model - " in (alt or "") or " on model, " in (alt or "")


def apply(c, pid, state, do):
    gid = f"gid://shopify/Product/{pid}"
    p = c.gql(Q, {"id": gid})["product"]
    assert p["status"] == "DRAFT", f"{p['title']} is {p['status']}, refusing"
    items = plan_for(pid, p)
    st = state.setdefault(str(pid), {"uploaded": {}})
    old = [m for m in p["media"]["nodes"] if is_v1_onmodel(m["alt"]) and m["id"] not in st["uploaded"].values()]
    flats = [m["id"] for m in p["media"]["nodes"]
             if not is_v1_onmodel(m["alt"]) and m["id"] not in st["uploaded"].values()]
    print(f"\n{p['title']}: {len(items)} new ({sum(1 for i in items if i['colour'])} bound), "
          f"{len(old)} v1 to delete, {len(flats)} flats kept")
    if not do:
        for i in items:
            print("   ", i["key"], "|", i["alt"], "| bind" if i["colour"] else "")
        return
    # 1-2 upload and wait
    for i in items:
        if i["key"] in st["uploaded"]:
            continue
        mid = c.upload_media_image(gid, i["path"], i["alt"])
        st["uploaded"][i["key"]] = mid
        STATE.write_text(json.dumps(state, indent=1))
        print("   uploaded", i["key"], mid)
    for i in items:
        c.wait_for_media_ready(st["uploaded"][i["key"]], timeout_s=300)
    # 3 bind variants
    by_colour = {i["colour"]: st["uploaded"][i["key"]] for i in items if i["colour"]}
    upd = []
    for v in p["variants"]["nodes"]:
        col = next(o["value"] for o in v["selectedOptions"] if o["name"] == "Color")
        upd.append({"id": v["id"], "mediaId": by_colour[col]})
    r = c.gql("""mutation($pid: ID!, $v: [ProductVariantsBulkInput!]!) {
        productVariantsBulkUpdate(productId: $pid, variants: $v) { userErrors { field message } } }""",
              {"pid": gid, "v": upd})["productVariantsBulkUpdate"]
    if r["userErrors"]:
        raise ShopifyError(str(r["userErrors"]))
    print("   bound", len(upd), "variants")
    # 4 delete v1
    if old:
        c.delete_media(gid, [m["id"] for m in old])
        print("   deleted", len(old), "v1 on-model images")
    # 5 reorder in one call
    order = [st["uploaded"][i["key"]] for i in items] + flats
    moves = [{"id": m, "newPosition": str(n)} for n, m in enumerate(order)]
    r = c.gql("""mutation($id: ID!, $moves: [MoveInput!]!) {
        productReorderMedia(id: $id, moves: $moves) { job { id } mediaUserErrors { message } } }""",
              {"id": gid, "moves": moves})["productReorderMedia"]
    if r["mediaUserErrors"]:
        raise ShopifyError(str(r["mediaUserErrors"]))
    c._wait_for_job((r.get("job") or {}).get("id"))
    st["order"] = order
    STATE.write_text(json.dumps(state, indent=1))


def verify(c, pid, state):
    gid = f"gid://shopify/Product/{pid}"
    p = c.gql(Q, {"id": gid})["product"]
    st = state.get(str(pid), {})
    want = st.get("order", [])
    have = [m["id"] for m in p["media"]["nodes"]]
    v2 = set(st.get("uploaded", {}).values())
    problems = []
    if p["status"] != "DRAFT":
        problems.append(f"status {p['status']}")
    if have != want:
        problems.append(f"order differs ({len(have)} vs {len(want)})")
    if any(m["status"] != "READY" for m in p["media"]["nodes"]):
        problems.append("media not READY: " + ", ".join(m["alt"] for m in p["media"]["nodes"] if m["status"] != "READY"))
    if any(not m["alt"] for m in p["media"]["nodes"]):
        problems.append("blank alt text")
    stale = [m["alt"] for m in p["media"]["nodes"] if is_v1_onmodel(m["alt"]) and m["id"] not in v2]
    if stale:
        problems.append(f"{len(stale)} v1 on-model left")
    alt = {m["id"]: m["alt"] for m in p["media"]["nodes"]}
    for v in p["variants"]["nodes"]:
        col = next(o["value"] for o in v["selectedOptions"] if o["name"] == "Color")
        mids = [m["id"] for m in v["media"]["nodes"]]
        if not mids or mids[0] not in v2 or not alt.get(mids[0], "").endswith(f"- {col}"):
            problems.append(f"variant {v['id'].split('/')[-1]} ({col}) bound to {alt.get(mids[0]) if mids else None}")
    print(f"{'OK ' if not problems else 'BAD'} {p['title']}: {len(have)} images, slot 1 = {alt.get(have[0]) if have else None}")
    for pr in problems[:6]:
        print("     ", pr)
    return not problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--swap-wordmarks", action="store_true",
                    help="replace the tee/crew/hoodie on-model shots in place (option F, 8 Oct)")
    ap.add_argument("--swap-cards", action="store_true",
                    help="replace the close-up cards and the unzipped bomber in place")
    a = ap.parse_args()
    c = ShopifyClient()
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    if a.swap_wordmarks:
        for pid, spec in PRODUCTS.items():
            if spec[0] == "bomber":
                continue
            keys = [i["key"] for i in plan_for(pid, c.gql(Q, {"id": f"gid://shopify/Product/{pid}"})["product"])
                    if not i["key"].startswith("card_")]
            print(pid)
            swap(c, pid, keys)
        a.verify = True
        state = json.loads(STATE.read_text())
    if a.swap_cards:
        for pid, spec in PRODUCTS.items():
            keys = list(spec[3]) + (["bomber_navy-blue_open"] if spec[0] == "bomber" else [])
            print(pid)
            swap(c, pid, keys, drop=["card_bomber_chest"] if spec[0] == "bomber" else [])
        a.verify = True
        state = json.loads(STATE.read_text())
    if a.verify:
        ok = all([verify(c, pid, state) for pid in PRODUCTS])
        sys.exit(0 if ok else 1)
    for pid in PRODUCTS:
        apply(c, pid, state, a.apply)
        if a.apply:
            time.sleep(1)
    if a.apply:
        print()
        ok = all([verify(c, pid, state) for pid in PRODUCTS])
        sys.exit(0 if ok else 1)



def swap(c, pid, keys, drop=()):
    """Replace single v2 images in place (same alt, same gallery slot) and drop
    others. For changes after the first apply: the black-on-white cards and the
    re-angled unzipped bomber, then the option F wordmark shots (Evan, 8 Oct
    2026). A bound image's variants are re-pointed to its replacement first."""
    gid = f"gid://shopify/Product/{pid}"
    state = json.loads(STATE.read_text())
    st = state[str(pid)]
    p = c.gql(Q, {"id": gid})["product"]
    assert p["status"] == "DRAFT"
    bound = {m["id"] for v in p["variants"]["nodes"] for m in v["media"]["nodes"]}
    ids = [m["id"] for m in p["media"]["nodes"]]
    alt = {m["id"]: m["alt"] for m in p["media"]["nodes"]}
    items = {i["key"]: i for i in plan_for(pid, p)}
    for k in drop:
        mid = st["uploaded"].pop(k, None)
        if mid and mid in ids:
            assert mid not in bound
            c.delete_media(gid, [mid])
            ids.remove(mid)
            print("   dropped", k)
    for k in keys:
        old = st["uploaded"][k]
        new = c.upload_media_image(gid, items[k]["path"], alt[old])
        c.wait_for_media_ready(new, timeout_s=300)
        if old in bound:   # re-point this colour's variants before the old image goes
            vs = [{"id": v["id"], "mediaId": new} for v in p["variants"]["nodes"]
                  if any(m["id"] == old for m in v["media"]["nodes"])]
            r = c.gql("""mutation($pid: ID!, $v: [ProductVariantsBulkInput!]!) {
                productVariantsBulkUpdate(productId: $pid, variants: $v) { userErrors { message } } }""",
                      {"pid": gid, "v": vs})["productVariantsBulkUpdate"]
            if r["userErrors"]:
                raise ShopifyError(str(r["userErrors"]))
        c.delete_media(gid, [old])
        ids[ids.index(old)] = new
        st["uploaded"][k] = new
        print("   replaced", k)
    moves = [{"id": m, "newPosition": str(n)} for n, m in enumerate(ids)]
    r = c.gql("""mutation($id: ID!, $moves: [MoveInput!]!) {
        productReorderMedia(id: $id, moves: $moves) { job { id } mediaUserErrors { message } } }""",
              {"id": gid, "moves": moves})["productReorderMedia"]
    if r["mediaUserErrors"]:
        raise ShopifyError(str(r["mediaUserErrors"]))
    c._wait_for_job((r.get("job") or {}).get("id"))
    st["order"] = ids
    STATE.write_text(json.dumps(state, indent=1))


if __name__ == "__main__":
    main()
