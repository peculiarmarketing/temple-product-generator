#!/usr/bin/env python
"""Put new map art on a map product that is already live, in place. Evan, 9 Oct 2026.

Nauvoo and Salt Lake City went live on 8 Oct with the first art. The confirmed
art (numbered landmark markers, thin crowded patches, Salt Lake widened to
24.5 km) and the history section with its numbered On the Map list have to
reach those same listings. map_run.py cannot do it: for a product that already
has a Shopify handle it skips the design and the description.

How (the method of relift_rollout.py, proved 7 Oct on 135 products): saving a
new design on the product's existing Tapstitch template gives it a new commit,
and Tapstitch moves the live store product onto it, so orders print the new art
with no new listing and the Easify dropdown keeps its binding. Tapstitch then
re-sends the product's images to Shopify with new media ids and no alt text.

Per product:

    snapshot  read the product; thumbnail every image and keep its alt; find
              the Tapstitch template the live store product prints from.
    save      save the new back and front on that template (LIVE from here).
    resync    wait until every old image id is gone and the same number is back.
    gallery   images that pixel-match an old design card are deleted (the cards
              show the old art); any other non-mockup image gets its old alt
              back by pixel match; Tapstitch's mockups get their alts from
              map_run.fix_mockup_alts; the new cards go in at positions 2 and 3;
              variant images are rebound to the back mockups.
    text      the description is rewritten from map_run.description_for (the
              history section with the numbered list); tags, the place line and
              the map page template are re-applied (all idempotent).
    verify    the store product prints the new commit, no image lacks alt text,
              the description is the new one, title and status are unchanged.

State per place in artifacts/maps/<place>/refresh.json; a re-run resumes.

  python scripts/map_refresh.py nauvoo --garment tee        one product
  python scripts/map_refresh.py nauvoo salt-lake-city       all three garments each
  python scripts/map_refresh.py nauvoo --verify             read-only
"""
import argparse
import hashlib
import io
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import requests
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import generate                                  # noqa: E402
import map_run as M                              # noqa: E402
import tapstitch_api as T                        # noqa: E402
import tapstitch_variant_images                  # noqa: E402
from shopify_client import ShopifyClient         # noqa: E402

RESYNC_TIMEOUT_S = 20 * 60
POLL_S = 15
PRODUCT_Q = """query($h: String!) { productByHandle(handle: $h) {
  id title status productType tags descriptionHtml
  media(first: 100) { nodes { id alt status ... on MediaImage { image { url } } } } } }"""


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def thumb_of(img, size=32):
    return np.asarray(img.convert("L").resize((size, size), Image.LANCZOS), dtype=np.float32)


def thumb(url):
    r = requests.get(url.split("?")[0] + "?width=160", headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
    r.raise_for_status()
    return thumb_of(Image.open(io.BytesIO(r.content)))


def corr(a, b):
    a, b = a - a.mean(), b - b.mean()
    d = np.sqrt((a * a).sum() * (b * b).sum())
    return float((a * b).sum() / d) if d else 0.0


def fetch(sc, handle):
    p = sc.gql(PRODUCT_Q, {"h": handle})["productByHandle"]
    if not p:
        raise SystemExit(f"no product at handle {handle}")
    return p


def is_card(alt):
    return (alt or "").startswith((M.MAP_ALT, M.LOGO_ALT))


def is_mockup_alt(alt, city):
    return (alt or "").startswith(f"{city} map ")


def refresh(s, sc, name, p, garment, st, note):
    cfg = generate.load_garment_config(garment)
    handle = M.load_state(name)[garment]["shopify_handle"]
    rec = st.setdefault(garment, {"handle": handle})
    city, _ = M.city_state(p)
    save = lambda: M.OUT.joinpath(name, "refresh.json").write_text(json.dumps(st, indent=2) + "\n")

    if "snapshot_at" not in rec:
        prod = fetch(sc, handle)
        if prod["status"] != "ACTIVE":
            raise SystemExit(f"{handle} is {prod['status']}, expected ACTIVE")
        media = []
        for m in prod["media"]["nodes"]:
            if not (m.get("image") or {}).get("url"):
                raise SystemExit(f"{handle}: media {m['id']} has no image; not starting")
            media.append({"id": m["id"], "alt": m["alt"] or "", "thumb": thumb(m["image"]["url"]).tolist()})
        sp = T.store_product_for(s, prod["id"], prod["title"])
        tids = {pi["templateId"] for v in sp["variants"] for pi in v.get("productionItems", [])}
        if len(tids) != 1:
            raise SystemExit(f"{handle}: store product prints from {sorted(tids)}, expected one template")
        rec.update(product_id=prod["id"], title=prod["title"], media=media,
                   template_id=tids.pop(), store_product_id=sp["uniqueId"], snapshot_at=now())
        save()
        note(f"snapshot: {len(media)} images, template {rec['template_id']}")

    if "saved_at" not in rec:
        paths, _ = M.print_files(name, p, garment, cfg)
        before = T.get_template(s, rec["template_id"])["commitId"]
        rec["save_started_at"] = now(); save()
        M.save_design(s, rec["template_id"], garment, cfg, [Path(x) for x in paths], note)
        after = T.get_template(s, rec["template_id"])["commitId"]
        if after == before:
            raise SystemExit(f"{handle}: design saved but the commit did not change")
        rec.update(commit_before=before, commit_after=after, saved_at=now())
        save()
        note(f"design saved: commit {before} -> {after} (orders print the new art)")

    if "resynced_at" not in rec:
        old = {m["id"] for m in rec["media"]}
        t0 = datetime.fromisoformat(rec["saved_at"]).timestamp()
        while True:
            prod = fetch(sc, handle)
            ids = {m["id"] for m in prod["media"]["nodes"]}
            ready = all(m.get("status") in ("READY", "FAILED") for m in prod["media"]["nodes"])
            if ids and not (ids & old) and len(ids) == len(old) and ready:
                break
            if time.time() - t0 > RESYNC_TIMEOUT_S:
                raise SystemExit(f"{handle}: no complete re-send within {RESYNC_TIMEOUT_S // 60} min "
                                 f"({len(ids)} images, {len(ids & old)} still old)")
            time.sleep(POLL_S)
        rec["resynced_at"] = now(); save()
        note("Tapstitch re-sent the images")

    if "gallery_at" not in rec:
        prod = fetch(sc, handle)
        olds = [(m, np.array(m["thumb"], dtype=np.float32)) for m in rec["media"]
                if not is_mockup_alt(m["alt"], city)]
        deletes, restores = [], []
        for m in prod["media"]["nodes"]:
            if m.get("alt"):
                continue
            t = thumb(m["image"]["url"])
            best = max(olds, key=lambda o: corr(t, o[1]), default=None)
            if best is None or corr(t, best[1]) < 0.97:
                continue                       # a Tapstitch mockup: fix_mockup_alts names it
            if is_card(best[0]["alt"]):
                deletes.append(m["id"])
            else:
                restores.append({"id": m["id"], "alt": best[0]["alt"]})
        if deletes:
            e = sc.gql("""mutation($p: ID!, $m: [ID!]!) { productDeleteMedia(productId: $p, mediaIds: $m) {
                mediaUserErrors { message } } }""", {"p": rec["product_id"], "m": deletes}
                )["productDeleteMedia"]["mediaUserErrors"]
            if e:
                raise SystemExit(f"{handle}: deleting old cards: {e}")
        if restores:
            e = sc.gql("""mutation($f: [FileUpdateInput!]!) { fileUpdate(files: $f) {
                userErrors { message } } }""", {"f": restores})["fileUpdate"]["userErrors"]
            if e:
                raise SystemExit(f"{handle}: restoring alts: {e}")
        note(f"old cards deleted: {len(deletes)}; other alts restored: {len(restores)}")
        note(M.fix_mockup_alts(sc, s, rec["product_id"], name, p, garment, rec["template_id"]))
        note(M.push_art_cards(sc, rec["product_id"], name, p))
        rebound = tapstitch_variant_images.rebind(sc, s, handle, rec["template_id"])
        if rebound is not None and "rebound" not in rebound:
            raise SystemExit(f"{handle}: variant image repair did not run: {rebound}")
        note(rebound or "variant images already on the back")
        rec["gallery_at"] = now(); save()

    if "text_at" not in rec:
        html = M.description_for(name, p, cfg)
        e = sc.gql("""mutation($i: ProductInput!) { productUpdate(input: $i) { userErrors { message } } }""",
                   {"i": {"id": rec["product_id"], "descriptionHtml": html, "templateSuffix": "map"}}
                   )["productUpdate"]["userErrors"]
        if e:
            raise SystemExit(f"{handle}: description: {e}")
        note(M.add_tags(sc, rec["product_id"], M.tags_for(name, garment, name == "salt-lake-city")))
        note(M.set_place_line(sc, rec["product_id"], p))
        rec.update(description_sha=hashlib.sha256(html.encode()).hexdigest(), text_at=now())
        save()
        note("description rewritten (history with numbered On the Map list)")
    note(verify(s, sc, name, p, garment, rec))


def verify(s, sc, name, p, garment, rec):
    prod = fetch(sc, rec["handle"])
    problems = []
    sp = T.store_product_for(s, rec["product_id"], rec["title"])
    commits = {pi["commitId"] for v in sp["variants"] for pi in v.get("productionItems", [])}
    if commits != {rec.get("commit_after")}:
        problems.append(f"store product prints {sorted(commits)}, expected {rec.get('commit_after')}")
    blank = [m["id"] for m in prod["media"]["nodes"] if not m.get("alt")]
    if blank:
        problems.append(f"{len(blank)} image(s) without alt text")
    if hashlib.sha256(prod["descriptionHtml"].encode()).hexdigest() != rec.get("description_sha"):
        # Shopify may normalise the HTML; compare the numbered list's presence instead
        if "site-history__map" not in prod["descriptionHtml"]:
            problems.append("description lacks the numbered On the Map list")
    if prod["title"] != rec["title"] or prod["status"] != "ACTIVE":
        problems.append(f"title/status changed: {prod['title']!r} {prod['status']}")
    cards = [m for m in prod["media"]["nodes"] if is_card(m.get("alt"))]
    if len(cards) != len(M.art_cards(name, p)):
        problems.append(f"{len(cards)} design cards, expected {len(M.art_cards(name, p))}")
    return "verified" if not problems else "PROBLEMS: " + "; ".join(problems)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("places", nargs="+")
    ap.add_argument("--garment", action="append", choices=M.GARMENTS)
    ap.add_argument("--verify", action="store_true", help="read-only check of finished products")
    a = ap.parse_args()
    s, sc = T.session(), ShopifyClient()
    for name in a.places:
        p = M.place_cfg(name)
        if p.get("status") != "live":
            raise SystemExit(f"{name} is {p.get('status')!r}; map_refresh is for maps already live")
        f = M.OUT / name / "refresh.json"
        st = json.loads(f.read_text()) if f.exists() else {}
        for g in a.garment or M.GARMENTS:
            note = lambda msg, g=g: print(f"  [{name} {g}] {msg}", flush=True)
            if a.verify:
                note(verify(s, sc, name, p, g, st.get(g, {})))
            else:
                refresh(s, sc, name, p, g, st, note)


if __name__ == "__main__":
    main()
