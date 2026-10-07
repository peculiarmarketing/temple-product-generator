#!/usr/bin/env python
"""Put the one-quarter lift on every live product, in place. Evan, 7 Oct 2026.

The back print files were rebuilt with `space_above_frac: 0.25` and the on-model
photos re-composited with fold option C (artifacts/photo-mockup-spike/
composites-lift/). This pushes both to the live catalogue without making new
products.

WHY IN PLACE WORKS. Proved on the Monticello tee, 7 Oct 2026. Re-saving a
template's design gives it a new commitId, and Tapstitch moves the EXISTING
store product onto that commit: every variant's productionItems.commitId changed
with it, so an order prints the new design. No swap, no new Shopify product, the
Easify dropdown keeps its binding. `check()` reads that back on every product
rather than trusting the one observation.

WHAT THE SAVE BREAKS, and what fixes it. About two minutes after the save,
Tapstitch re-sends the product's images to Shopify. Measured on the pilot: the
gallery went to 0 images for about six seconds, then the same 11 images came back
in the same order with NEW media ids and NO alt text. Variant images, colour
order, title, type and description were untouched. Alt text is what every
gallery script keys on, so it is restored here by matching each returned image
to the thumbnail taken just before the save. Pixels decide, not position.

THE SEQUENCE, per product:

    snapshot  read the product (alts, image thumbnails, title, type, tags,
              description, colour order) and find its Tapstitch store product by
              the Shopify id it is bound to. Nothing written.
    save      upload the lifted back print and the unchanged front logo, save
              the design on the existing template. LIVE: orders print it now.
    resync    wait for Tapstitch's re-send (new media ids, same count, all READY).
    restore   put every alt back by pixel match. Stops on any doubt, before
              writing a single alt.
    gallery   Tapstitch's new flat lay from the saved design becomes the archive
              copy, the old back flat and on-model backs are marked superseded,
              build_product_gallery.py --add and --reface upload the new ones and
              rebind each colour, every superseded photo is deleted, --prune
              orders the gallery: the on-model back in the flat-lay colour first,
              because slot 1 is the collection thumbnail.
    verify    read back: the store product prints the new commit, no blank or
              superseded alt, the gallery in build_product_gallery's order, every
              sold colour bound to its own NEW on-model back (pixel-checked
              against the composite), and title, type, tags, description and
              colour order as snapshotted.

Each finished step is written to artifacts/tapstitch/relift-rollout.json the
moment it completes, so a re-run resumes where it stopped. A batch saves all its
designs first and then works through them, so the re-send waits overlap.

HOODIES share their template with the retired DRAFT hoodie from the Eden Green
swap, so that draft gets the new design and a re-send too. It is not for sale and
nothing here touches it.

  python scripts/relift_rollout.py                         plan only
  python scripts/relift_rollout.py --apply --temple Monticello --garment tee
  python scripts/relift_rollout.py --apply --limit 30      batches of five
  python scripts/relift_rollout.py --verify                read-only check of finished rows
"""
import argparse
import hashlib
import io
import json
import subprocess
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

import art_images                                            # noqa: E402
import build_product_gallery as gallery                      # noqa: E402
import colour_names                                          # noqa: E402
import generate                                              # noqa: E402
import ledger                                                # noqa: E402
import tapstitch_api as T                                    # noqa: E402
import tapstitch_run as R                                    # noqa: E402
from build_garment_catalog import temple_of                  # noqa: E402
from shopify_client import ShopifyClient                     # noqa: E402

STATE_PATH = ROOT / "artifacts/tapstitch/relift-rollout.json"
THUMBS = ROOT / "artifacts/tapstitch/relift-thumbs"
COMPOSITES = ROOT / "artifacts/photo-mockup-spike/composites-lift"
GARMENTS = ("tee", "crew", "hoodie")
SUPERSEDED = gallery.SUPERSEDED
RESYNC_TIMEOUT_S = 15 * 60
POLL_S = 20
# All three are mean absolute difference between 32x32 grey thumbnails, 0-255.
# The same image after Tapstitch's re-send measured 0.26 to 0.29 on the Monticello
# crew and hoodie. Two different on-model backs of one garment differ by far more
# than 12, since the temple and the colourway both change.
MATCH_MAX = 12.0
# A live on-model back against the composite it was uploaded from: the only
# difference is Shopify's re-encode, so anything past 6 is a different picture.
COMPOSITE_MATCH_MAX = 6.0
# RGB distance from a Tapstitch back mockup's median fabric colour to the
# flat-lay colour's measured hex. Tapstitch's five tee colours sit 40+ apart, so
# under 40 is the right colour and over it is the wrong one or none.
FLAT_COLOUR_MAX = 40.0

PRODUCT_Q = """query($h:String!){productByHandle(handle:$h){id title productType tags
  descriptionHtml status options{name values}
  media(first:60){nodes{id alt status ... on MediaImage{image{url}}}}
  variants(first:100){nodes{id title media(first:1){nodes{id}}}}}}"""


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_state():
    return json.loads(STATE_PATH.read_text()) if STATE_PATH.exists() else {"products": {}}


def save_state(st):
    st["updated_at"] = now()
    STATE_PATH.write_text(json.dumps(st, indent=2, sort_keys=True) + "\n")


def key(row):
    return f"{row['temple']}|{row['garment']}"


def fetch_image(url):
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
    r.raise_for_status()
    return Image.open(io.BytesIO(r.content))


def grey_thumb(img, size=32):
    return np.asarray(img.convert("L").resize((size, size), Image.LANCZOS), dtype=np.float32)


def thumb(url):
    """A Shopify image as a grey thumbnail, fetched small to keep the run quick."""
    return grey_thumb(fetch_image(url.split("?")[0] + "?width=160"))


def local_thumb(path):
    return grey_thumb(Image.open(path))


def fetch(sc, handle):
    p = sc.gql(PRODUCT_Q, {"h": handle})["productByHandle"]
    if not p:
        raise SystemExit(f"no product at handle {handle}")
    return p


def fingerprint(p):
    """The fields a re-send must not change."""
    return {"title": p["title"], "productType": p["productType"],
            "tags": sorted(p["tags"]), "status": p["status"],
            "description_sha": hashlib.sha256(p["descriptionHtml"].encode()).hexdigest(),
            "options": json.loads(json.dumps(p["options"]))}   # a copy, not the live list


def production_commits(store_product):
    """{(templateId, commitId)} every variant of a store product is printed from."""
    return {(pi["templateId"], pi["commitId"])
            for v in store_product["variants"] for pi in v.get("productionItems", [])}


# ---------------------------------------------------------------- steps

def resolve_ids(s, row, rec):
    """The template and store product behind this Shopify product, read from
    Tapstitch by the Shopify id, and cross-checked against the ledger."""
    sp = T.store_product_for(s, rec["product_id"], rec["title"])
    tids = {t for t, _ in production_commits(sp)}
    if len(tids) != 1:
        raise SystemExit(f"{key(row)}: store product prints from {sorted(tids)}, "
                         "expected one template")
    tid = tids.pop()
    if row.get("tapstitch_template_id") and row["tapstitch_template_id"] != tid:
        raise SystemExit(f"{key(row)}: ledger says template {row['tapstitch_template_id']}, "
                         f"Tapstitch prints from {tid}. Stopping.")
    rec.update(template_id=tid, store_product_id=sp["uniqueId"])
    if not row.get("tapstitch_template_id"):
        # The Salt Lake tee predates the ledger recording ids. Record them now so
        # the next script does not have to find them again.
        data = ledger.load()
        ledger.set_state(data, row["temple"], row["garment"], row["state"],
                         tapstitch_template_id=tid,
                         tapstitch_store_product_id=sp["uniqueId"], problems=[])
        ledger.save(data)


def step_snapshot(s, sc, row, rec):
    p = fetch(sc, row["shopify_handle"])
    THUMBS.mkdir(parents=True, exist_ok=True)
    media = []
    for m in p["media"]["nodes"]:
        if not (m.get("image") or {}).get("url"):
            raise SystemExit(f"{key(row)}: media {m['id']} has no image, not snapshotting")
        if not m.get("alt"):
            raise SystemExit(f"{key(row)}: media {m['id']} already has no alt text; "
                             "the gallery is not in a known state, fix it first")
        f = THUMBS / f"{m['id'].split('/')[-1]}.npy"
        np.save(f, thumb(m["image"]["url"]))
        media.append({"id": m["id"], "alt": m["alt"], "thumb": f.name})
    rec.update(product_id=p["id"], title=p["title"], fingerprint=fingerprint(p),
               media=media)
    resolve_ids(s, row, rec)
    rec["snapshot_at"] = now()


def step_save(s, row, rec):
    cfg = generate.load_garment_config(row["garment"])
    tid = rec["template_id"]
    pngs = R.print_files(row["temple"], row["garment"], R.ink_color(cfg))
    before = T.get_template(s, tid)["commitId"]
    rec["save_started_at"] = now()
    R.save_design(s, tid, row["garment"], cfg, pngs, lambda m: None)
    after = T.get_template(s, tid)["commitId"]
    if after == before:
        raise SystemExit(f"{key(row)}: design saved but the commit did not change")
    rec.update(commit_before=before, commit_after=after, saved_at=now())


def step_resync(sc, row, rec):
    """Wait for Tapstitch's re-send: every snapshot media id gone, same count back."""
    old = {m["id"] for m in rec["media"]}
    t0 = datetime.fromisoformat(rec["saved_at"]).timestamp()
    while True:
        p = fetch(sc, row["shopify_handle"])
        ids = {m["id"] for m in p["media"]["nodes"]}
        # FAILED is final too: see step_restore for what it means and how it is handled.
        ready = all(m.get("status") in ("READY", "FAILED") for m in p["media"]["nodes"])
        if ids and not (ids & old) and len(ids) == len(old) and ready:
            rec["resynced_at"] = now()
            return
        if time.time() - t0 > RESYNC_TIMEOUT_S:
            raise SystemExit(f"{key(row)}: no complete re-send within "
                             f"{RESYNC_TIMEOUT_S // 60} min of the save (have {len(ids)} "
                             f"images, {len(ids & old)} still old). Check the product.")
        time.sleep(POLL_S)


def rebuildable(row, name, alt):
    """Alt texts this rollout can upload again from local files: the fabric
    details (fabric-details/), every on-model back (composites-lift/) and the
    back flat lay (replaced from Tapstitch's new mockup anyway)."""
    g = row["garment"]
    return (alt in {a for _, a in gallery.detail_alts(g)}
            or alt.startswith(f"{name} Temple back print on model - ")
            or alt == gallery.flat_alt(name, g, "back", gallery.flat_colour(g)))


def step_restore(sc, row, rec):
    """Put the alts back, by pixels.

    FAILED IMAGES. Tapstitch re-sends from its own list of the product's image
    addresses, and on some products that list still names a file Shopify no
    longer has: the tall fabric details squared and replaced on 18 Sep 2026.
    Measured 7 Oct 2026 on the Albuquerque and Billings rows, one detail per
    product came back FAILED with "The file does not exist (404)". A failed image
    has no picture to match, so it is deleted, and the snapshot image it stood
    for is left without a match. That is only accepted for photos the gallery
    step uploads again from local files; anything else stops the run.
    """
    p = fetch(sc, row["shopify_handle"])
    name = temple_of(rec["title"])
    snap = [(m["alt"], np.load(THUMBS / m["thumb"])) for m in rec["media"]]
    nodes = p["media"]["nodes"]
    failed = [m["id"] for m in nodes if m.get("status") == "FAILED"]
    plan, used = [], set()
    for m in nodes:
        if m["id"] in failed:
            continue
        t = thumb(m["image"]["url"])
        best, i = min((float(np.abs(t - x).mean()), i) for i, (_, x) in enumerate(snap))
        if best > MATCH_MAX or i in used:
            raise SystemExit(f"{key(row)}: cannot match returned image {m['id']} "
                             f"(best {best:.1f} to {snap[i][0]!r}). Stopping before "
                             "writing any alt text.")
        used.add(i)
        plan.append((m["id"], snap[i][0], best))
    lost = [snap[i][0] for i in range(len(snap)) if i not in used]
    if len(lost) != len(failed):
        raise SystemExit(f"{key(row)}: {len(lost)} snapshot image(s) did not come back "
                         f"but {len(failed)} failed")
    if not all(rebuildable(row, name, a) for a in lost):
        raise SystemExit(f"{key(row)}: image(s) {lost} failed in the re-send and this "
                         "rollout cannot rebuild them. Stopping before writing any alt text.")
    for mid, alt, _ in plan:
        sc.update_media_alt(p["id"], mid, alt)
    if failed:
        sc.delete_media(p["id"], failed)
    rec.update(restored_at=now(), worst_match=round(max(b for *_, b in plan), 2),
               failed_in_resend=lost)


def new_flat(s, rec, garment):
    """Tapstitch's own back mockup of the saved design, in the flat-lay colour."""
    urls = T.get_template(s, rec["template_id"])["pictureUrlList"]["BackEndImage"]
    want = gallery.flat_colour(garment)
    ref = np.array(colour_names.true_rgb(garment, want), dtype=float)
    best = None
    for u in urls:
        im = fetch_image(u).convert("RGB")
        a = np.asarray(im, dtype=float).reshape(-1, 3)
        body = a[(a.min(axis=1) < 200) & (a.max(axis=1) > 5)]
        d = float(np.linalg.norm(np.median(body, axis=0) - ref))
        if best is None or d < best[0]:
            best = (d, im)
    if best is None or best[0] > FLAT_COLOUR_MAX:
        raise SystemExit(f"{rec['title']}: no Tapstitch back mockup in {want} "
                         f"(closest {best[0] if best else 'none'})")
    return want, best[1]


def gallery_cmd(stage, pid, garment, name, onmodel):
    out = subprocess.run([sys.executable, str(ROOT / "scripts/build_product_gallery.py"),
                          "--product-gid", pid, "--garment", garment, "--temple", name,
                          "--onmodel-dir", str(onmodel), f"--{stage}"],
                         cwd=ROOT, capture_output=True, text=True)
    if out.returncode:
        raise SystemExit(f"build_product_gallery --{stage} failed:\n{out.stdout[-1500:]}"
                         f"\n{out.stderr[-1500:]}")
    return out.stdout


def step_gallery(s, sc, row, rec):
    garment = row["garment"]
    name = temple_of(rec["title"])
    onmodel = COMPOSITES / garment / row["temple"]
    if not onmodel.is_dir():
        raise SystemExit(f"{key(row)}: no composites at {onmodel}")
    pid = rec["product_id"]

    colour, im = new_flat(s, rec, garment)
    arch = gallery.originals_dir(name) / f"{garment}_{colour}_back.png"
    arch.parent.mkdir(parents=True, exist_ok=True)
    im.save(arch)

    # Read from the product, not this run: a resumed run may find photos an
    # earlier attempt already marked.
    for m in fetch(sc, row["shopify_handle"])["media"]["nodes"]:
        a = m.get("alt") or ""
        if ("back print on model" in a or "back print flat lay" in a) \
                and not a.startswith(SUPERSEDED):
            sc.update_media_alt(pid, m["id"], SUPERSEDED + a)

    gallery_cmd("add", pid, garment, name, onmodel)
    gallery_cmd("reface", pid, garment, name, onmodel)

    p = fetch(sc, row["shopify_handle"])
    bound = {(v["media"]["nodes"] or [{}])[0].get("id") for v in p["variants"]["nodes"]}
    stale = [m["id"] for m in p["media"]["nodes"] if (m.get("alt") or "").startswith(SUPERSEDED)]
    if any(m in bound for m in stale):
        raise SystemExit(f"{key(row)}: a superseded photo is still bound to a colour "
                         "after --add; not deleting")
    if stale:
        sc.delete_media(pid, stale)
    gallery_cmd("prune", pid, garment, name, onmodel)
    rec["gallery_at"] = now()


def check(s, sc, row, rec):
    """Problems with a finished product, as a list. Empty means verified."""
    garment = row["garment"]
    name = temple_of(rec["title"])
    p = fetch(sc, row["shopify_handle"])
    probs = []

    sp = T.store_product_for(s, rec["product_id"], rec["title"])
    commits = production_commits(sp)
    if commits != {(rec["template_id"], rec["commit_after"])}:
        probs.append(f"Tapstitch prints from {sorted(commits)}, not the new design "
                     f"{rec['commit_after']}")

    nodes = p["media"]["nodes"]
    have = [m.get("alt") or "" for m in nodes]
    if any(not a for a in have):
        probs.append(f"{sum(1 for a in have if not a)} image(s) without alt text")
    if any(a.startswith(SUPERSEDED) for a in have):
        probs.append("superseded image(s) still on the product")
    if len(set(have)) != len(have):
        probs.append("two images share an alt text")
    art_alt = next((a for a in have if a.startswith(art_images.ALT_MARKER)), None)
    want = [a for a in gallery.gallery_order(name, garment, art_alt) if a in have]
    if have != want:
        probs.append(f"gallery is {have}, expected {want}")

    by_alt = {m.get("alt"): m["id"] for m in nodes}
    urls = {m["id"]: m["image"]["url"] for m in nodes}
    onmodel = COMPOSITES / garment / row["temple"]
    sold = set()
    for v in p["variants"]["nodes"]:
        slug = colour_names.slug_for(garment, v["title"].split(" / ")[0])
        sold.add(slug)
        target = by_alt.get(gallery.on_model_alt(name, garment, slug))
        cur = (v["media"]["nodes"] or [{}])[0].get("id")
        if not target or cur != target:
            probs.append(f"{v['title']}: not bound to its on-model back")
    for slug in sorted(sold):
        mid = by_alt.get(gallery.on_model_alt(name, garment, slug))
        f = onmodel / f"{garment}_{slug}.jpg"
        if mid and f.exists():
            d = float(np.abs(thumb(urls[mid]) - local_thumb(f)).mean())
            if d > COMPOSITE_MATCH_MAX:
                probs.append(f"on-model {slug} does not match the new composite ({d:.1f})")
    if gallery.flat_alt(name, garment, "back", gallery.flat_colour(garment)) not in by_alt:
        probs.append("no back flat lay")
    lead = gallery.on_model_alt(name, garment, gallery.flat_colour(garment))
    if not have or have[0] != lead:
        probs.append(f"slot 1 (the collection thumbnail) is not {lead!r}")

    fp = fingerprint(p)
    for k, v in rec["fingerprint"].items():
        if fp[k] != v:
            probs.append(f"{k} changed since the snapshot")
    return probs


# ---------------------------------------------------------------- driver

STEPS = ("snapshot_at", "saved_at", "resynced_at", "restored_at", "gallery_at", "verified_at")


def next_step(rec):
    return next((s for s in STEPS if not rec.get(s)), None)


def run_batch(s, sc, st, todo):
    # Phase 1: snapshot and save every product in the batch, so the re-send waits overlap.
    for r in todo:
        rec = st["products"].setdefault(key(r), {})
        if not rec.get("snapshot_at"):
            step_snapshot(s, sc, r, rec)
            save_state(st)
        if not rec.get("saved_at"):
            step_save(s, r, rec)
            save_state(st)
            print(f"  saved   {key(r)}  commit {rec['commit_after']}", flush=True)
    # Phase 2: per product, in save order.
    for r in todo:
        rec = st["products"][key(r)]
        if not rec.get("resynced_at"):
            step_resync(sc, r, rec)
            save_state(st)
        if not rec.get("restored_at"):
            step_restore(sc, r, rec)
            save_state(st)
            print(f"  alts    {key(r)}  restored (worst match {rec['worst_match']})", flush=True)
        if not rec.get("gallery_at"):
            step_gallery(s, sc, r, rec)
            save_state(st)
            print(f"  gallery {key(r)}", flush=True)
        probs = check(s, sc, r, rec)
        if probs:
            raise SystemExit(f"{key(r)}: verify failed: " + "; ".join(probs))
        rec["verified_at"] = now()
        save_state(st)
        print(f"  OK      {key(r)}", flush=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="write to Tapstitch and Shopify")
    ap.add_argument("--temple", action="append", help="ledger temple name, repeatable")
    ap.add_argument("--garment", choices=GARMENTS)
    ap.add_argument("--limit", type=int, help="at most this many unfinished products")
    ap.add_argument("--batch", type=int, default=5,
                    help="products saved together before their re-sends are worked "
                         "(default 5; Tapstitch drops connections after long bursts)")
    ap.add_argument("--verify", action="store_true", help="read-only check of finished rows")
    a = ap.parse_args(argv)

    st = load_state()
    rows = [r for r in ledger.load()["rows"] if r["state"] == "live" and r.get("shopify_handle")]
    if a.temple:
        rows = [r for r in rows if r["temple"] in a.temple]
    if a.garment:
        rows = [r for r in rows if r["garment"] == a.garment]
    rows.sort(key=lambda r: (r["temple"], GARMENTS.index(r["garment"])))

    if a.verify:
        s, sc = T.session(), ShopifyClient()
        bad = 0
        for r in rows:
            rec = st["products"].get(key(r), {})
            if not rec.get("verified_at"):
                continue
            probs = check(s, sc, r, rec)
            bad += bool(probs)
            print(f"{key(r):32s} {'OK' if not probs else '; '.join(probs)}")
        if bad:
            raise SystemExit(f"{bad} product(s) failed verify")
        return

    todo = [r for r in rows if next_step(st["products"].get(key(r), {}))]
    if a.limit is not None:
        todo = todo[:a.limit]
    print(f"{len(todo)} product(s) to work, of {len(rows)} selected")
    for r in todo:
        print(f"  {key(r):32s} next: {next_step(st['products'].get(key(r), {}))}")
    if not a.apply:
        print("\nPLAN ONLY. Add --apply to run.")
        return
    if not (a.temple or a.limit):
        raise SystemExit("--apply needs --temple or --limit, so a stray flag cannot run "
                         "the whole catalogue")

    sc = ShopifyClient()
    for i in range(0, len(todo), a.batch):
        run_batch(T.session(), sc, st, todo[i:i + a.batch])   # fresh cookies per batch
        print(f"batch done: {min(i + a.batch, len(todo))} of {len(todo)}", flush=True)


if __name__ == "__main__":
    main()
