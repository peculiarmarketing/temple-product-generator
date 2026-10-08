"""Publish a city map design (the back street map, the coordinates front) on the
tee, crewneck and hoodie, through the same Tapstitch route as the temples.

The art comes from the workspace's designs/city-map-back/ (build_map_back.py and
web_map_drawing.py); this script only places it and publishes. It runs the same
sequence as scripts/tapstitch_run.py's run_row and calls the same functions:

    print files -> create_template -> save_design -> create_store_product
    -> distribute (LIVE, no undo) -> wait for Shopify and the import
    -> finish_on_shopify (product type, colour renames, swatch gate)
    -> variant images onto the back -> tags, place line, collection

What differs from a temple, all decided by Evan on 8 Oct 2026:

  - Title: the garment's line name with "Temple" swapped for "Map", place in
    brackets: "Essential Heavyweight Map Tee (Nauvoo)". The theme cuts the title
    at " (" and shows the place line from the `peculiar.temple_city` and
    `temple_state` metafields underneath, the same as a temple product, so
    those two are written and `temple_name` is not.
  - Description: the same fixed product-details sections, no temple facts, and
    a Church history section (`site-history`) for a Church history site, from
    designs/city-map-back/history/<place>.html.
  - Tags: map:<place> and line:map, and NOT garment:, country: or state:. The
    temple collections are smart collections on those three (temple-tees,
    temple-crewnecks, temple-hoodies, all-temples), and the homepage marquee
    reads temple-tees, so a garment: tag would put a map in the temple marquee.
  - No art card, Temple Art File option, Easify row or marquee entry: those
    are temple-only.
  - On-model gallery: not run. The blank colourway photos it composites onto
    are on the Mac only (artifacts/photo-mockup-spike/colourway-photos is
    gitignored); the product keeps Tapstitch's own mockups until it runs there.

Placement. The back map is 13.5 x 18 in, which leaves the crewneck 0.12 in a
side, inside flatten.validate()'s 0.25 in safe margin. So each garment scales
the map to the largest size that keeps the 0.25 in margin (13.2 to 13.4 in
wide; line weights change by under 2 percent), centred across, with a quarter
of the spare height above and three quarters below, as the temples sit. The
front is the coordinates logo placed exactly as flatten.build_front_logo()
places the plain logo: 6.0 in of ink wide, ink top 3.0 in down, centred on ink.

State is kept per place in artifacts/maps/<place>/state.json and every id is
written the moment Tapstitch returns it, so a stopped run resumes without a
second template or a second distribute (the same rules as tapstitch_run.py).

  python scripts/map_run.py nauvoo                     # build print files, plan
  python scripts/map_run.py nauvoo --apply             # Tapstitch products, not public
  python scripts/map_run.py nauvoo --apply --publish   # LIVE
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import numpy as np
from PIL import Image

import flatten
import generate
import tapstitch_api as T
import tapstitch_variant_images
from description_html import _details_block, _row_style, _unwrap, compose_description
from shopify_client import ShopifyClient
from tapstitch_publish import finish_on_shopify
from tapstitch_run import (BLANKS, STORE_ID, ink_color, lead_color_id, save_design,
                           wait_for_import, wait_for_shopify)

Image.MAX_IMAGE_PIXELS = None
GARMENTS = ("tee", "crew", "hoodie")
OUT = ROOT / "artifacts" / "maps"
COLLECTION = {"title": "Church History Maps", "handle": "church-history-maps",
              "tag": "line:map"}
SAFE_IN = flatten.DEFAULT_SAFE_MARGIN_IN


def maps_dir():
    """designs/city-map-back in the workspace. On the Mac this repo sits inside
    the workspace; in a cloud session the two are sibling clones."""
    for base in (ROOT.parent, *ROOT.parent.glob("peculiar-people-workspace*")):
        d = base / "designs" / "city-map-back"
        if (d / "places.json").exists():
            return d
    raise SystemExit("designs/city-map-back not found beside this repo")


def place_cfg(name):
    places = json.loads((maps_dir() / "places.json").read_text())
    if name not in places:
        raise SystemExit(f"{name!r} is not in places.json")
    return places[name]


def art_paths(name, p):
    out = maps_dir() / "out" / name
    swing = p.get("swing", 0.10 if p.get("busy") else 0.40)
    tag = f"{name}-{p['width_km']:g}km-{p['line_mm']:g}mm-hand{round(swing * 100)}"
    back = out / f"{tag}-print-300dpi.png"
    front = out / (f"{name}-front-6in-300dpi.png" if p.get("temple")
                   else f"{name}-front-plain-6in-300dpi.png")
    web = out / "web"
    for f in (back, front):
        if not f.exists():
            raise SystemExit(f"missing {f}; run build_map_back.py {name} first")
    return back, front, web


def city_state(p):
    city, region = (s.strip().title() for s in p["label"].rsplit(",", 1))
    return city, region


# ------------------------------------------------------------- print files

def ink_box(img):
    a = np.asarray(img.getchannel("A"))
    ys, xs = np.nonzero(a > 8)
    return xs.min(), ys.min(), xs.max() + 1, ys.max() + 1


def build_back(src, cfg):
    area = cfg["print_area"]
    dpi, W, H = area["dpi"], area["width_px"], area["height_px"]
    room_w, room_h = W - 2 * SAFE_IN * dpi, H - 2 * SAFE_IN * dpi
    s = min(room_w / src.width, room_h / src.height)
    w, h = round(src.width * s), round(src.height * s)
    art = src.resize((w, h), Image.LANCZOS)
    spare = room_h - h
    above = cfg.get("spacing_overrides", {}).get("space_above_frac", 0.25)
    x = round((W - w) / 2)
    y = round(SAFE_IN * dpi + spare * above)
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    canvas.alpha_composite(art, (x, y))
    return canvas, {"width_in": round(w / dpi, 3), "height_in": round(h / dpi, 3),
                    "top_in": round(y / dpi, 3), "scale": round(s, 4)}


def build_front(src, cfg):
    area = cfg["front_print_area"]
    dpi, W, H = area["dpi"], area["width_px"], area["height_px"]
    l, t, r, b = ink_box(src)
    s = area["logo_ink_width_in"] * dpi / (r - l)
    w, h = round(src.width * s), round(src.height * s)
    art = src.resize((w, h), Image.LANCZOS)
    x = round(W / 2 - (l + r) / 2 * s)
    y = round(area["logo_ink_top_margin_in"] * dpi - t * s)
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    canvas.alpha_composite(art, (x, y))
    return canvas, {"ink_width_in": round((r - l) * s / dpi, 3),
                    "ink_top_in": round((y + t * s) / dpi, 3)}


def print_files(name, p, garment_id, cfg):
    """Write (back, front) for one garment and validate both. Returns paths."""
    color = ink_color(cfg)
    back_src, front_src, _ = art_paths(name, p)
    d = OUT / name
    d.mkdir(parents=True, exist_ok=True)
    out, report = [], {}
    for key, src_path, build, area_key in (
            ("back", back_src, build_back, "print_area"),
            ("front", front_src, build_front, "front_print_area")):
        with Image.open(src_path) as im:
            raw, geo = build(im.convert("RGBA"), cfg)
        img = flatten.matte(raw, flatten.INK_RGB[color])
        problems = flatten.validate(img, cfg, {}, color, area_key=area_key, pre_matte=raw)
        if problems:
            raise SystemExit(f"{name} {garment_id} {key}: " + "; ".join(problems))
        path = d / f"{name} {garment_id} {color} {key} print (map).png"
        img.save(path)
        out.append(path)
        report[key] = geo
    return out, report


# ------------------------------------------------------------- copy

def title_for(name, p, garment_cfg):
    city, _ = city_state(p)
    line = garment_cfg["naming"]["title_parent"].replace("Temple", "Map")
    if line == garment_cfg["naming"]["title_parent"]:
        raise SystemExit(f"{garment_cfg['garment_id']}: no 'Temple' in the line name to swap")
    return f"{line} ({city})"


def history_section(name):
    """The Church history fragment, collapsed into rows like the temple facts:
    one row for the place name with its spec rows, one per h4 block."""
    path = maps_dir() / "history" / f"{name}.html"
    if not path.exists():
        return None
    frag = path.read_text().strip()
    m = re.match(r'^(<section class="site-history">)\n?(.*)(</section>)\s*$', frag, re.S)
    if not m:
        raise SystemExit(f"{path}: not a <section class=\"site-history\"> fragment")
    open_tag, body, close_tag = m.groups()
    body = _unwrap(body)
    asof = re.search(r'<p class="site-history__asof">.*?</p>\s*$', body, re.S)
    tail = asof.group(0).strip() if asof else ""
    body = body[:asof.start()] if asof else body
    blocks = []
    for chunk in (c for c in re.split(r'(?=<h4[^>]*>)', body) if c.strip()):
        h = re.match(r'\s*(<h([34])[^>]*>.*?</h\2>)', chunk, re.S)
        if not h:
            raise SystemExit(f"{path}: a block does not open with an h3 or h4")
        blocks.append(_details_block(h.group(1), chunk[h.end():].strip(), "site-history"))
    return "\n".join([open_tag, _row_style("site-history")] + blocks
                     + ([tail] if tail else []) + [close_tag])


def description_for(name, p, garment_cfg):
    fixed = generate.fixed_description(garment_cfg)
    if not fixed:
        raise SystemExit(f"garment copy missing ({garment_cfg['garment_copy']})")
    html = compose_description(fixed)
    if p.get("history"):
        hist = history_section(name)
        if not hist:
            raise SystemExit(f"{name} is a Church history site with no "
                             f"history/{name}.html; refusing to publish without it")
        html += "\n\n" + hist
    return html


def tags_for(name):
    return [f"map:{name}", COLLECTION["tag"]]


# ------------------------------------------------------------- state

def load_state(name):
    f = OUT / name / "state.json"
    return json.loads(f.read_text()) if f.exists() else {}


def save_state(name, state):
    f = OUT / name / "state.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(state, indent=2) + "\n")


# ------------------------------------------------------------- shopify extras

def set_place_line(client, product_id, p):
    city, region = city_state(p)
    mf = [{"ownerId": product_id, "namespace": "peculiar", "key": "temple_city",
           "type": "single_line_text_field", "value": city},
          {"ownerId": product_id, "namespace": "peculiar", "key": "temple_state",
           "type": "single_line_text_field", "value": region}]
    errs = client.gql("""mutation($m: [MetafieldsSetInput!]!) { metafieldsSet(metafields: $m) {
        userErrors { field message } } }""", {"m": mf})["metafieldsSet"]["userErrors"]
    if errs:
        raise SystemExit(f"metafieldsSet: {errs}")
    return f"place line {city}, {region}"


def add_tags(client, product_id, tags):
    errs = client.gql("""mutation($id: ID!, $t: [String!]!) { tagsAdd(id: $id, tags: $t) {
        userErrors { message } } }""", {"id": product_id, "t": tags})["tagsAdd"]["userErrors"]
    if errs:
        raise SystemExit(f"tagsAdd: {errs}")
    return "tags " + ", ".join(tags)


def ensure_collection(client):
    """The smart collection every map product joins by its line:map tag,
    published to every sales channel the temple collections are on."""
    c = client.gql("query($h: String!) { collectionByHandle(handle: $h) { id } }",
                   {"h": COLLECTION["handle"]})["collectionByHandle"]
    if c:
        return c["id"], "collection exists"
    r = client.gql("""mutation($i: CollectionInput!) { collectionCreate(input: $i) {
        collection { id } userErrors { message } } }""",
        {"i": {"title": COLLECTION["title"], "handle": COLLECTION["handle"],
               "ruleSet": {"appliedDisjunctively": False, "rules": [
                   {"column": "TAG", "relation": "EQUALS", "condition": COLLECTION["tag"]}]}}}
    )["collectionCreate"]
    if r["userErrors"]:
        raise SystemExit(f"collectionCreate: {r['userErrors']}")
    cid = r["collection"]["id"]
    pubs = client.gql("""query { collectionByHandle(handle: "temple-tees") {
        resourcePublications(first: 20) { nodes { publication { id } } } } }"""
    )["collectionByHandle"]["resourcePublications"]["nodes"]
    ids = [{"publicationId": n["publication"]["id"]} for n in pubs]
    if ids:
        e = client.gql("""mutation($id: ID!, $p: [PublicationInput!]!) {
            publishablePublish(id: $id, input: $p) { userErrors { message } } }""",
            {"id": cid, "p": ids})["publishablePublish"]["userErrors"]
        if e:
            raise SystemExit(f"publishablePublish: {e}")
    return cid, f"collection created and published to {len(ids)} channel(s)"


def upload_drawing(client, name):
    """The band's files into the published theme: this map's stroke file and
    art, plus the band section that reads map: tags. Copied into theme/ first so
    the repo holds what the theme holds; checked by read-back like the sweep's
    drawing step."""
    import hashlib
    import shutil
    import web_drawings as WD
    _, _, web = art_paths(name, place_cfg(name))
    theme_dir = ROOT / "theme"
    for ext in ("json", "webp"):
        shutil.copyfile(web / f"pp-map-{name}.{ext}", theme_dir / "assets" / f"pp-map-{name}.{ext}")
    names = [f"assets/pp-map-{name}.json", f"assets/pp-map-{name}.webp",
             "sections/pp-temple-drawing.liquid"]
    files = {n: (theme_dir / n).read_bytes() for n in names}
    md5 = lambda b: hashlib.md5(b).hexdigest()
    theme = WD.main_theme_id(client)
    remote = WD.remote_checksums(client, theme, names)
    todo = {n: b for n, b in files.items() if remote.get(n) != md5(b)}
    if not todo:
        return "theme already has the drawing"
    WD.upsert_theme_files(client, theme, todo)
    after = WD.remote_checksums(client, theme, list(todo))
    wrong = [n for n in todo if after.get(n) != md5(todo[n])]
    if wrong:
        raise SystemExit(f"theme read-back mismatch on {wrong}")
    return "uploaded " + ", ".join(sorted(todo))


# ------------------------------------------------------------- run

def run_garment(s, client, name, p, garment_id, publish, state, note):
    cfg = generate.load_garment_config(garment_id)
    st = state.setdefault(garment_id, {})
    title = title_for(name, p, cfg)

    if not st.get("shopify_handle"):
        if not st.get("store_product_id"):
            if not st.get("store_product_id") and client.find_product_by_title(title):
                raise SystemExit(f"a product titled {title!r} already exists on the store")
            pngs = [Path(x) for x in st["print_files"]]
            if not st.get("template_id"):
                st["template_id"] = T.create_template(s, BLANKS[garment_id])
                save_state(name, state)
                note(f"template {st['template_id']}")
            else:
                note(f"reusing template {st['template_id']}")
            save_design(s, st["template_id"], garment_id, cfg, pngs, note)
            prefill = T.store_product_prefill(s, STORE_ID, st["template_id"])
            payload = T.store_product_payload(
                prefill, title, int(round(cfg["price_usd"] * 100)),
                description_for(name, p, cfg), lead_color_id(cfg))
            payload["tags"] = tags_for(name)
            st["store_product_id"] = T.create_store_product(s, STORE_ID, payload)
            save_state(name, state)
            note(f"store product {st['store_product_id']} ({title!r})")
        if not publish:
            note("stopped before distribute: --publish not given")
            return
        already = client.find_product_by_title(title)
        if already:
            note(f"already on the store at {already['handle']}: skipping distribute")
        elif st.get("distribute_started_at"):
            note(f"distribute already attempted {st['distribute_started_at']}: polling")
        else:
            st["distribute_started_at"] = datetime.now().isoformat(timespec="seconds")
            save_state(name, state)
            T.distribute(s, [st["store_product_id"]])
        st["shopify_handle"] = wait_for_shopify(client, title)
        save_state(name, state)
        note(f"live at {st['shopify_handle']}")

    handle = st["shopify_handle"]
    note(wait_for_import(client, handle))
    for a in finish_on_shopify(client, name, garment_id, handle,
                               write_description=False, push_art_card=False):
        if "tapstitch_variant_images" not in a:
            note(a)
    rebound = tapstitch_variant_images.rebind(client, s, handle, st["template_id"])
    if rebound is not None and "rebound" not in rebound:
        raise SystemExit(f"variant image repair did not run: {rebound}")
    note(rebound or "variant images already on the back")
    pid = client.find_product_by_handle(handle)["id"]
    note(add_tags(client, pid, tags_for(name)))
    note(set_place_line(client, pid, p))
    st["state"] = "live"
    save_state(name, state)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("place")
    ap.add_argument("--garment", action="append", choices=GARMENTS)
    ap.add_argument("--apply", action="store_true", help="Tapstitch writes (not public)")
    ap.add_argument("--publish", action="store_true", help="distribute: LIVE, no undo")
    a = ap.parse_args()
    if a.publish and not a.apply:
        raise SystemExit("--publish needs --apply")
    name, p = a.place, place_cfg(a.place)
    garments = a.garment or list(GARMENTS)
    state = load_state(name)

    for g in garments:
        cfg = generate.load_garment_config(g)
        paths, geo = print_files(name, p, g, cfg)
        state.setdefault(g, {})["print_files"] = [str(x) for x in paths]
        print(f"{g}: {title_for(name, p, cfg)!r}  back {geo['back']}  front {geo['front']}")
        try:
            description_for(name, p, cfg)
        except SystemExit as e:
            if a.apply:
                raise
            print(f"  NOT READY: {e}")
    save_state(name, state)
    if not a.apply:
        print("plan only: --apply builds the Tapstitch products, --publish puts them live")
        return

    s, client = T.session(), ShopifyClient()
    for g in garments:
        def note(msg, g=g):
            print(f"  [{g}] {msg}", flush=True)
        run_garment(s, client, name, p, g, a.publish, state, note)
    if a.publish:
        print(f"  {upload_drawing(client, name)}")
        cid, msg = ensure_collection(client)
        print(f"  {msg}")


if __name__ == "__main__":
    main()
