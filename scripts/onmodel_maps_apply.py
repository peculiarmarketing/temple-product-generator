#!/usr/bin/env python
"""Add the on-model photos to the six live map products (Nauvoo and Salt Lake City
on the tee, sweatshirt and hoodie), after Evan's review of artifacts/onmodel-maps.

Order per product, chosen so a variant never points at a missing image:

  1. upload each colour's back and front shot (staged upload), wait until READY
  2. bind each colour's variants to its back on-model shot (map listings lead with
     the back, as their flat lays already do)
  3. reorder: lead colour back, lead colour front, the other backs, the other
     fronts, then the map and logo close-ups, then the Tapstitch flats as they are
  4. read back: order, alts, every variant bound to its colour's back shot

Nothing is deleted: map products had no on-model images before.

  python scripts/onmodel_maps_apply.py            # plan only
  python scripts/onmodel_maps_apply.py --apply    # do it (live listings, Evan's go)
  python scripts/onmodel_maps_apply.py --verify   # read back only
  python scripts/onmodel_maps_apply.py --place provo --apply   # one city only

Every city with prints in artifacts/onmodel-maps/prints/ is covered; a new city's
listings follow the same handle pattern as the first two.
"""
import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from shopify_client import ShopifyClient, ShopifyError  # noqa: E402

MAPS = ROOT / "artifacts" / "onmodel-maps"
STATE = MAPS / "applied.json"
MODELS = json.loads((MAPS / "models.json").read_text())
WORD = {"tee": "tee", "crew": "sweatshirt", "hoodie": "hoodie"}
HANDLE_FMT = {"tee": "essential-heavyweight-map-tee-{}", "crew": "ultra-soft-map-sweatshirt-{}",
              "hoodie": "ultra-soft-oversized-map-hoodie-{}"}
PLACES = sorted({p.stem.rsplit("_", 2)[0] for p in (MAPS / "prints").glob("*_*_*.png")})
CITY = {p: p.replace("-", " ").title() for p in PLACES}     # salt-lake-city -> Salt Lake City
HANDLES = {(p, g): HANDLE_FMT[g].format(p) for p in PLACES for g in HANDLE_FMT}
CARD_PREFIXES = ("City map art close-up", "Coordinates logo close-up")

Q = """query($h: String!) { productByHandle(handle: $h) { id title status
  media(first: 100) { nodes { id alt status } }
  variants(first: 100) { nodes { id selectedOptions { name value } media(first: 1) { nodes { id } } } } } }"""


def colour_name(slug, values):
    for v in values:
        if v.lower().replace(" ", "-") == slug:
            return v
    raise SystemExit(f"no colour value for {slug} in {values}")


def plan_for(place, g, product):
    lead = MODELS["lead"][g]
    slugs = [k.split("_", 1)[1] for k in MODELS["colours"] if k.startswith(g + "_")]
    slugs = [lead] + [s for s in slugs if s != lead]
    values = sorted({o["value"] for v in product["variants"]["nodes"]
                     for o in v["selectedOptions"] if o["name"] == "Color"})
    if len(values) != len(slugs):
        raise SystemExit(f"{product['title']}: {len(values)} colours on the store, {len(slugs)} shot")
    items = []
    for view, what in [("back", "back print"), ("front", "front logo")]:
        for s in slugs:
            c = colour_name(s, values)
            items.append({"key": f"{g}_{view}_{s}", "colour": c if view == "back" else None,
                          "path": str(MAPS / "final" / f"{place}_{g}_{view}_{s}.jpg"),
                          "alt": f"{CITY[place]} map {WORD[g]}, {what} on model - {c}"})
    # lead back, lead front, then the rest of the backs, then the rest of the fronts
    backs, fronts = items[:len(slugs)], items[len(slugs):]
    return [backs[0], fronts[0]] + backs[1:] + fronts[1:]


def is_onmodel(alt):
    return " on model - " in (alt or "")


def apply(c, place, g, state, do):
    handle = HANDLES[(place, g)]
    p = c.gql(Q, {"h": handle})["productByHandle"]
    gid = p["id"]
    items = plan_for(place, g, p)
    st = state.setdefault(handle, {"uploaded": {}})
    mine = set(st["uploaded"].values())
    stray = [m for m in p["media"]["nodes"] if is_onmodel(m["alt"]) and m["id"] not in mine]
    if stray:
        raise SystemExit(f"{p['title']}: on-model images this script did not upload: "
                         f"{[m['alt'] for m in stray][:3]}; refusing")
    rest = [m for m in p["media"]["nodes"] if m["id"] not in mine]
    cards = [m["id"] for m in rest if (m["alt"] or "").startswith(CARD_PREFIXES)]
    flats = [m["id"] for m in rest if m["id"] not in cards]
    print(f"\n{p['title']} ({p['status']}): {len(items)} on-model to add, "
          f"{len(cards)} close-ups and {len(flats)} flats kept in order")
    if not do:
        for i in items[:4]:
            print("   ", Path(i["path"]).name, "|", i["alt"], "| bind" if i["colour"] else "")
        print("    ...")
        missing = [i["path"] for i in items if not Path(i["path"]).exists()]
        if missing:
            print("    MISSING finals:", len(missing))
        return
    for i in items:
        if i["key"] in st["uploaded"]:
            continue
        mid = c.upload_media_image(gid, i["path"], i["alt"])
        st["uploaded"][i["key"]] = mid
        STATE.write_text(json.dumps(state, indent=1))
        print("   uploaded", i["key"])
    for i in items:
        c.wait_for_media_ready(st["uploaded"][i["key"]], timeout_s=300)
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
    order = [st["uploaded"][i["key"]] for i in items] + cards + flats
    moves = [{"id": m, "newPosition": str(n)} for n, m in enumerate(order)]
    r = c.gql("""mutation($id: ID!, $moves: [MoveInput!]!) {
        productReorderMedia(id: $id, moves: $moves) { job { id } mediaUserErrors { message } } }""",
              {"id": gid, "moves": moves})["productReorderMedia"]
    if r["mediaUserErrors"]:
        raise ShopifyError(str(r["mediaUserErrors"]))
    c._wait_for_job((r.get("job") or {}).get("id"))
    st["order"] = order
    STATE.write_text(json.dumps(state, indent=1))


def verify(c, place, g, state):
    handle = HANDLES[(place, g)]
    p = c.gql(Q, {"h": handle})["productByHandle"]
    st = state.get(handle, {})
    have = [m["id"] for m in p["media"]["nodes"]]
    alt = {m["id"]: m["alt"] for m in p["media"]["nodes"]}
    mine = set(st.get("uploaded", {}).values())
    problems = []
    if have != st.get("order"):
        problems.append(f"order differs ({len(have)} vs {len(st.get('order') or [])})")
    if any(m["status"] != "READY" for m in p["media"]["nodes"]):
        problems.append("media not READY")
    if any(not m["alt"] for m in p["media"]["nodes"]):
        problems.append("blank alt text")
    for v in p["variants"]["nodes"]:
        col = next(o["value"] for o in v["selectedOptions"] if o["name"] == "Color")
        mids = [m["id"] for m in v["media"]["nodes"]]
        a = alt.get(mids[0], "") if mids else ""
        if not mids or mids[0] not in mine or "back print on model" not in a or not a.endswith(f"- {col}"):
            problems.append(f"variant {v['id'].split('/')[-1]} ({col}) bound to {a or None}")
    print(f"{'OK ' if not problems else 'BAD'} {p['title']}: {len(have)} images, slot 1 = "
          f"{alt.get(have[0]) if have else None}")
    for pr in problems[:6]:
        print("     ", pr)
    return not problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--place", help="one city only, e.g. nauvoo")
    a = ap.parse_args()
    if a.place:
        for k in [k for k in HANDLES if k[0] != a.place]:
            del HANDLES[k]
        if not HANDLES:
            raise SystemExit(f"no prints for {a.place} in {MAPS / 'prints'}")
    c = ShopifyClient()
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    if a.verify:
        sys.exit(0 if all([verify(c, pl, g, state) for pl, g in HANDLES]) else 1)
    for pl, g in HANDLES:
        apply(c, pl, g, state, a.apply)
        if a.apply:
            time.sleep(1)
    if a.apply:
        print()
        sys.exit(0 if all([verify(c, pl, g, state) for pl, g in HANDLES]) else 1)


if __name__ == "__main__":
    main()
