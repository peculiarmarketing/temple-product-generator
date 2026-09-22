#!/usr/bin/env python
"""Build one product's gallery to the agreed layout. THE process, per Evan, 17 Sep 2026.

Gallery, in order. Evan, 18 Sep 2026, superseding the on-model-first order:

  1  flat back mockup, flat colour       the design, read clearly. THE THUMBNAIL.
  2  flat front mockup with chest logo
  3  temple art closeup                  the design card
  4+ on-model back, every colour         lead first, each bound to its variant
  .. fabric and construction details     captioned with the colourway shown

Slot 1 is what Shopify features, so it is the image on collection pages and in
search. The flat lay is there deliberately: it shows the temple bigger and
flatter than a worn shot does, which is what survives being shrunk to a grid
thumbnail.

Runs in stages so the destructive ones are never a surprise:

  --report   classify what is on the product now and print the plan. Changes nothing.
  --add      upload on-model backs and fabric details, bind variants. Additive only.
  --reface   re-upload the lead flat mockups on the garment's gray. Additive only.
  --prune    delete the surplus and superseded flat mockups, then order the gallery.

ONE BACKDROP, ONE SHAPE. Per Evan, 18 Sep 2026. The on-model shots sit on a light
gray studio backdrop; Tapstitch's flat mockups and the fabric close-ups arrive on
pure white, and the close-ups arrive at 2048x2731 rather than square. Everything
this uploads now goes through normalize.py first, which puts it on that garment's
own gray and crops it to 1:1 at native resolution. The one deliberate exception
is the temple art closeup in slot 3, which stays on white so the design reads
clearly; nothing here is ever pointed at it.

The flat mockups exist only on Shopify, because Tapstitch publishes them straight
to the store and they never touch local disk. --reface is the stage that pulls
them down, recolours them and puts them back.

`--add` is safe to re-run: every image this uploads carries a deterministic alt
text and anything already present is skipped. `--prune` refuses to touch a media
item that is still bound to a variant, which is the failure that would blank a
variant on the storefront.

THE CLASSIFIER. Tapstitch's flat mockups reach Shopify with no alt text, so which
one is "Black front" has to be worked out from the pixels. Two signals:
  colour  - mean garment colour matched against true_colors_all.json
  side    - the back carries the temple print, the front a small chest logo, so
            the back has several times more near-white ink
Both are printed in --report so a human can check before anything is deleted.
"""
import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "artifacts/photo-mockup-spike"))
import colour_names  # noqa: E402
import normalize  # noqa: E402
from PIL import Image  # noqa: E402
from shopify_client import ShopifyClient  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SPIKE = ROOT / "artifacts/photo-mockup-spike"
# The measured fabric colours are read through colour_names.true_rgb, which
# knows that true_colors_all.json predates the 18 Sep 2026 renames and still
# keys the tee's Charcoal under "Dark Gray".
ORIGINALS = SPIKE / "flat-originals"


def originals_dir(temple):
    """Where this temple's white flat originals live.

    TEMPLE SCOPED, and that is not optional. These files were pooled in one
    directory until 18 Sep 2026, so --reface's fallback answered a request for
    Boise's Black flat with Salt Lake's, and published a flat lay reading "SALT
    LAKE CITY, UTAH" onto the Boise product under a "Boise Temple" alt. The
    fallback now looks in one temple's directory and nowhere else.
    """
    return ORIGINALS / re.sub(r"[^A-Za-z0-9]+", "-", temple).strip("-").lower()

LEAD = {"hoodie": "navy-blue", "tee": "black", "crew": "gray"}
# Which colourway the two flat lays show, independent of the lead colour used for
# the on-model run. Per Evan, 18 Sep 2026:
#   crew   Black,  because its lead Flower Gray is a light heather that will not
#          separate from any light gray backdrop
#   tee    Maroon, chosen on how it reads as the collection thumbnail
#   hoodie defaults to its lead, Navy Blue
# Changing one of these means the previous flat lays have to be replaced, which
# --prune handles: a flat lay in the wrong colour is dropped even though it
# carries alt text, unlike the unlabelled Tapstitch ones.
FLAT = {"crew": "black", "tee": "maroon"}
ORDER = {
    "hoodie": ["navy-blue", "gray", "black", "coffee", "mauve", "royal-blue", "eden-green"],
    "tee": ["black", "dark-gray", "navy-blue", "maroon", "coffee"],
    "crew": ["gray", "black"],
}
# The slug-to-name map lives in colour_names, not here. It used to be two local
# dicts that both said "gray": "Gray", which cannot be right: crew_gray.jpg and
# hoodie_gray.jpg are different colours, and a colour name on this store buys one
# swatch hex for every product that uses it. Every alt text below therefore takes
# a garment.


def on_model_alt(temple, garment, colour):
    return f"{temple} Temple back print on model - {colour_names.name_for(garment, colour)}"


def flat_alt(temple, garment, side, colour):
    """Alt text for a refaced flat mockup.

    Deliberately NOT prefixed "Temple back print on model - ", which is what
    bind_variants_to_onmodel.py matches variants against. A flat lay must never
    be mistaken for an on-model shot there.
    """
    what = "back print flat lay" if side == "back" else "chest logo flat lay"
    return f"{temple} Temple {what} - {colour_names.name_for(garment, colour)}"


def flat_colour(garment):
    return FLAT.get(garment, LEAD[garment])


def _captions(garment):
    d = SPIKE / "fabric-details" / garment
    return json.loads((d / "captions.json").read_text()) if d.exists() else {}


def detail_alts(garment):
    """(filename, alt) pairs. Keys starting with _ are directives, not images."""
    return sorted((k, v) for k, v in _captions(garment).items() if not k.startswith("_"))


def detail_notice(garment):
    """Text stamped across the bottom of every detail shot for this garment."""
    return _captions(garment).get("_notice")


def stale_details(media, caps):
    """Live fabric details still in the old tall shape, by alt -> [media ids].

    A detail that has been normalized is square. Anything carrying a caption alt
    at 2048x2731 predates this and is the thing being replaced. Shape is the
    right test here: the alt text is identical before and after, deliberately, so
    that the gallery ordering and every other script keep working unchanged.
    """
    want = {a for _, a in caps}
    out = {}
    for m in media:
        alt, im = m.get("alt"), m.get("image") or {}
        if alt in want and im.get("width") and im["width"] != im["height"]:
            out.setdefault(alt, []).append(m["id"])
    return out


def squared_details(media, caps):
    """Live fabric details already square, by alt -> media id."""
    want = {a for _, a in caps}
    return {m["alt"]: m["id"] for m in media
            if m.get("alt") in want
            and (m.get("image") or {}).get("width") == (m.get("image") or {}).get("height")}


def classify(url, garment, cache):
    """(colour_key, 'back'|'front', ink_fraction) for one flat mockup."""
    import urllib.request
    p = cache / (url.split("/")[-1].split("?")[0])
    if not p.exists():
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        p.write_bytes(urllib.request.urlopen(req, timeout=60).read())
    a = np.asarray(Image.open(p).convert("RGB"), dtype=float)
    h, w = a.shape[:2]
    # Middle 20% only. A wider box catches the white BACKGROUND these flat lays
    # sit on, which put the front at 4.6% ink and made it read as a back. Checked
    # against all 12 hoodie mockups: backs 12.3-22.8%, fronts 1.1-1.7%.
    mid = a[int(h * 0.40):int(h * 0.60), int(w * 0.40):int(w * 0.60)]
    flat = mid.reshape(-1, 3)
    ink = float((flat.min(axis=1) > 200).mean())          # near-white pixels


    # Colour comes from the MEDIAN of every garment pixel in the whole image, not
    # the mean of the centre. On a back the temple print covers a fifth of the
    # centre and drags the mean badly: all five tee backs read "Dark Gray" at
    # distances up to 57. The median over the whole garment ignores the print and
    # put every one of the ten tee mockups within 9 of its true swatch.
    #
    # The backdrop is excluded by REGION, not brightness. "min(RGB) <= 200" was
    # the old test, and it broke the moment a flat lay was recoloured onto the
    # gray: at 193 the backdrop passes that test, gets counted as garment, and
    # every flat on every catalogue tee matched at a distance of 184. That sent
    # --reface to its archive fallback, which published the Salt Lake flat lay
    # onto the Boise product on 18 Sep 2026. Caught on the first product; the
    # archive is now temple-scoped so the fallback cannot cross temples either.
    bg = normalize.border_region(Image.open(p))
    allp = a[~bg].reshape(-1, 3)
    body = allp[allp.min(axis=1) <= 200]                  # drops the near-white ink
    mean = np.median(body, axis=0) if len(body) else flat.mean(axis=0)
    best, bestd = None, 1e9
    for key in colour_names.NAMES.get(garment, {}):
        ref = colour_names.true_rgb(garment, key)
        if not ref:
            continue
        dist = float(np.linalg.norm(mean - np.array(ref, dtype=float)))
        if dist < bestd:
            best, bestd = key, dist
    return best, bestd, ink


def fetch(sc, gid):
    return sc.gql("""
      query($id: ID!) { product(id: $id) {
        title status options { name values }
        media(first: 60) { nodes { ... on MediaImage { id alt image { url width height } } } }
        variants(first: 100) { nodes { id title
          media(first: 1) { nodes { ... on MediaImage { id } } } } } } }""",
        {"id": gid})["product"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--product-gid", required=True)
    ap.add_argument("--garment", required=True, choices=sorted(ORDER))
    ap.add_argument("--temple", default="Salt Lake",
                    help="the name used in alt text, i.e. how the PRODUCT titles it")
    ap.add_argument("--onmodel-dir",
                    help="directory of {garment}_{colour}.jpg on-model shots. Defaults "
                         "to final-set/, which holds Salt Lake. A catalogue run points "
                         "this at that temple's folder, whose name can differ from the "
                         "product's: 'Ogden (original)' on disk is 'Ogden Original' in "
                         "the title, and alt text has to follow the product.")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--report", action="store_true")
    g.add_argument("--add", action="store_true")
    g.add_argument("--reface", action="store_true")
    g.add_argument("--prune", action="store_true")
    args = ap.parse_args()

    onmodel = Path(args.onmodel_dir) if args.onmodel_dir else SPIKE / "final-set"
    if not onmodel.is_dir():
        raise SystemExit(f"no on-model directory at {onmodel}")

    sc = ShopifyClient()
    prod = fetch(sc, args.product_gid)
    media = prod["media"]["nodes"]
    lead = LEAD[args.garment]
    caps = detail_alts(args.garment)
    cache = SPIKE / ".flatcache" / args.garment
    cache.mkdir(parents=True, exist_ok=True)

    ours = {m.get("alt"): m["id"] for m in media if m.get("alt")}
    flats = [m for m in media if not m.get("alt")]
    art = [m for m in media if "line art" in (m.get("alt") or "").lower()]

    print(f"product : {prod['title']}  [{prod['status']}]")
    print(f"gallery : {len(media)} images, {len(flats)} unlabelled flat mockup(s)\n")

    if flats:
        print("classifying the unlabelled flat mockups:")
        print(f"  {'media':20s} {'colour':12s} {'dist':>5s} {'ink%':>6s}  side")
    # BACK vs FRONT IS DECIDED PAIRWISE, not against a fixed ink threshold.
    # Tapstitch publishes exactly two flats per colour, and the back carries the
    # temple while the front carries a small chest logo, so within a colour the
    # one with more near-white ink in the centre is the back. Full stop.
    #
    # The old test was "ink > 6%", tuned on the hoodie where backs ran 12.3-22.8%
    # and fronts 1.1-1.7%. On the catalogue tees backs measure 5.2-6.0% and
    # fronts exactly 0.00%, so every back read as a front and slot 2 would have
    # been built from the chest-logo shot. A ratio between the pair is stable
    # across garments; an absolute number is tuned to whichever one it was
    # measured on.
    measured = {}
    for m in flats:
        colour, dist, ink = classify(m["image"]["url"], args.garment, cache)
        measured[m["id"]] = (colour, dist, ink)
    by_colour = {}
    for mid, (colour, _d, ink) in measured.items():
        by_colour.setdefault(colour, []).append((ink, mid))
    seen = {}
    for colour, lst in by_colour.items():
        lst.sort(reverse=True)                       # most ink first
        for rank, (_ink, mid) in enumerate(lst):
            seen[mid] = (colour, "back" if rank == 0 and len(lst) > 1 else
                         ("back" if len(lst) == 1 and _ink > 0.03 else "front"))
    for m in flats:
        colour, dist, ink = measured[m["id"]]
        side = seen[m["id"]][1]
        star = "  <- KEEP" if colour == flat_colour(args.garment) else ""
        print(f"  {m['id'].split('/')[-1]:20s} {(colour_names.NAMES[args.garment].get(colour) or '?'):12s} "
              f"{dist:5.1f} {ink*100:6.2f}  {side}{star}")

    # A lead-colour flat is kept only until its refaced twin exists. Once the
    # gray version is on the product the white original is superseded and joins
    # the drop set, which is a WIDER blast radius than this script used to have:
    # the variant-binding guard below is now the only thing between a re-run and
    # a blanked variant, so it is checked before anything is deleted.
    fc = flat_colour(args.garment)
    superseded = {mid for mid, (c, sd) in seen.items()
                  if c == fc and flat_alt(args.temple, args.garment, sd, c) in ours}
    keep = {mid for mid, (c, sd) in seen.items() if c == fc} - superseded
    drop = [mid for mid in seen if mid not in keep]
    # A tall fabric detail is superseded once a square one with the same alt is
    # on the product. Matching on alt alone cannot tell them apart, which is why
    # shape is the test.
    sq = squared_details(media, caps)
    stale_drop = [mid for alt, ids in stale_details(media, caps).items()
                  if alt in sq for mid in ids]
    drop += stale_drop
    # A flat lay in a colour we no longer use. These carry alt text, so they are
    # invisible to the unlabelled-flat classifier above and would otherwise
    # survive a change to FLAT forever, leaving two flat lays in two colours.
    want_suffix = f"- {colour_names.name_for(args.garment, fc)}"
    wrong_colour = [m["id"] for m in media
                    if "flat lay" in (m.get("alt") or "")
                    and not (m.get("alt") or "").endswith(want_suffix)]
    drop += wrong_colour
    bound = {(v["media"]["nodes"] or [{}])[0].get("id") for v in prod["variants"]["nodes"]}
    bound.discard(None)
    clash = [m for m in drop if m in bound]

    print(f"\nkeep {len(keep)} white flat mockup(s) in {colour_names.name_for(args.garment, flat_colour(args.garment))}, "
          f"drop {len(drop)} ({len(superseded)} superseded flat(s), "
          f"{len(stale_drop)} superseded detail(s), "
          f"{len(wrong_colour)} flat lay(s) in a retired colour)")
    if clash:
        print(f"  BLOCKED: {len(clash)} of those are still bound to a variant. Run --add first.")
    print(f"art closeup present: {'yes' if art else 'NO'}")
    missing = [c for c in ORDER[args.garment] if on_model_alt(args.temple, args.garment, c) not in ours]
    print(f"on-model backs missing: {', '.join(missing) if missing else 'none'}")
    print(f"fabric details missing: {sum(1 for _, a in caps if a not in ours)} of {len(caps)}")
    refaced = {s_: (flat_alt(args.temple, args.garment, s_, flat_colour(args.garment)) in ours)
               for s_ in ("back", "front")}
    print("flats refaced onto the gray: " +
          ", ".join(f"{k} {'yes' if v else 'NO'}" for k, v in refaced.items()))
    stale = stale_details(media, caps)
    print(f"fabric details still white and 2048x2731: {len(stale)} of {len(caps)}")

    if args.report:
        print("\nREPORT ONLY. Nothing changed.")
        return

    if args.add:
        # Only the colours this product sells. ORDER is the whole line, and during
        # the Eden Green rollout (22 Sep 2026) most hoodies still sell six of its
        # seven: uploading the seventh would show a colour nobody can buy.
        sold = {colour_names.slug_for(args.garment, v) for o in prod["options"]
                if o["name"] == "Color" for v in o["values"]}
        for c in ORDER[args.garment]:
            alt = on_model_alt(args.temple, args.garment, c)
            if alt in ours or c not in sold:
                continue
            f = onmodel / f"{args.garment}_{c}.jpg"
            if not f.exists():
                raise SystemExit(f"missing {f}")
            mid = sc.upload_media_image(args.product_gid, f, alt)
            sc.wait_for_media_ready(mid)
            ours[alt] = mid
            print(f"  uploaded on-model {c}")
        for fn, alt in caps:
            if alt in ours:
                continue
            norm, st = normalize.for_upload(
                SPIKE / "fabric-details" / args.garment / fn, args.garment,
                notice=detail_notice(args.garment))
            mid = sc.upload_media_image(args.product_gid, norm, alt)
            sc.wait_for_media_ready(mid)
            ours[alt] = mid
            print(f"  uploaded detail {fn}  {st['src'][0]}x{st['src'][1]} -> "
                  f"{st['out'][0]}x{st['out'][1]} on {st['gray']}")
        prod = fetch(sc, args.product_gid)
        by_alt = {m.get("alt"): m["id"] for m in prod["media"]["nodes"] if m.get("alt")}
        ups = []
        for v in prod["variants"]["nodes"]:
            colour = v["title"].split(" / ")[0]
            key = colour_names.slug_for(args.garment, colour)
            target = by_alt.get(on_model_alt(args.temple, args.garment, key)) if key else None
            cur = (v["media"]["nodes"] or [{}])[0].get("id")
            if target and cur != target:
                ups.append({"id": v["id"], "mediaId": target})
        for i in range(0, len(ups), 25):
            sc.gql("""
              mutation($pid: ID!, $variants: [ProductVariantsBulkInput!]!) {
                productVariantsBulkUpdate(productId: $pid, variants: $variants) {
                  userErrors { message } } }""",
                {"pid": args.product_gid, "variants": ups[i:i+25]})
        print(f"  bound {len(ups)} variant(s) to their on-model back")
        print("\nADD complete. Run --report to check, then --prune.")
        return

    if args.reface:
        # The flat mockups live only on Shopify. classify() has already pulled
        # each one into .flatcache, so the bytes are on disk by the time we get
        # here.
        ORIGINALS.mkdir(parents=True, exist_ok=True)
        done = 0
        want = flat_colour(args.garment)

        # Where the two source flats come from, in order of preference:
        #   1. live on the product, already pulled into .flatcache by classify()
        #   2. the tracked archive in flat-originals/
        # The archive is not a nicety. The crew's flats show Black, but the Black
        # pair was pruned off that product in an earlier session, so the live
        # product carries no Black flat to pull. The archived bytes are the only
        # copy left, and they are what this rebuilds from.
        sources = {}
        for m in flats:
            colour, side = seen.get(m["id"], (None, None))
            if colour != want:
                continue
            src = cache / m["image"]["url"].split("/")[-1].split("?")[0]
            if src.exists():
                sources[side] = (src, True)      # True = came off the live product
        for side in ("back", "front"):
            if side in sources:
                continue
            arch = next(iter(originals_dir(args.temple).glob(
                f"{args.garment}_{want}_{side}.*")), None)
            if arch:
                sources[side] = (arch, False)
                print(f"  {side:5s}: not on the product, rebuilding from "
                      f"{arch.relative_to(ROOT)}")
        missing = [s_ for s_ in ("back", "front") if s_ not in sources]
        if missing:
            raise SystemExit(
                f"no source for the {args.garment} {want} flat {', '.join(missing)}: "
                f"not on the product and not in "
                f"{originals_dir(args.temple).relative_to(ROOT)}. "
                "Re-pull it from Tapstitch.")

        # ONE gray for both flats. A light garment needs its backdrop darkened to
        # stay visible (see normalize.separated_gray), but the back and the front
        # measure a few levels apart, so solving each independently would put the
        # two flats of the same product on two different grays. Take the darkest
        # answer across the pair and use it for both.
        flat_gray = normalize.backdrop_gray(args.garment)
        for side, (src, _live) in sorted(sources.items()):
            g, rep = normalize.separated_gray(Image.open(src),
                                              normalize.backdrop_gray(args.garment))
            if rep.get("adjusted"):
                print(f"  {side:5s}: garment sits {rep['separation']:.0f} levels "
                      f"off the backdrop, under {normalize.MIN_SEPARATION}. Darkening.")
                if sum(g) < sum(flat_gray):
                    flat_gray = g
        if tuple(flat_gray) != tuple(normalize.backdrop_gray(args.garment)):
            print(f"  flats go on {tuple(flat_gray)} instead of "
                  f"{normalize.backdrop_gray(args.garment)} so the garment reads\n")

        for side, (src, live) in sorted(sources.items()):
            alt = flat_alt(args.temple, args.garment, side, want)
            if alt in ours:
                print(f"  {side:5s} already refaced, skipping")
                continue
            # ARCHIVE BEFORE ANYTHING ELSE. --prune deletes the white original
            # from Shopify, and .flatcache is gitignored as a self-regenerating
            # cache which will NOT regenerate once the source URL is gone. This
            # tracked copy is then the only surviving original.
            if live:
                keep_at = originals_dir(args.temple) / f"{args.garment}_{want}_{side}{src.suffix}"
                keep_at.parent.mkdir(parents=True, exist_ok=True)
                if not keep_at.exists():
                    keep_at.write_bytes(src.read_bytes())
                    print(f"  archived original -> {keep_at.relative_to(ROOT)}")
            norm, st = normalize.for_upload(src, args.garment, gray=flat_gray,
                                            cache=SPIKE / "normalized" / args.garment)
            mid = sc.upload_media_image(args.product_gid, norm, alt)
            sc.wait_for_media_ready(mid)
            ours[alt] = mid
            done += 1
            print(f"  refaced {side:5s} {want:11s} {st['src'][0]}x{st['src'][1]} "
                  f"on {st['gray']}, {st['bg_fraction']*100:.0f}% background, "
                  f"edge ring p99 {st.get('ring_p99', 0):.0f}")
        # Fabric details already on the product keep their alt text, so --add
        # skips them by design. Replacing them is this stage's job too.
        squared = squared_details(media, caps)
        for fn, alt in caps:
            if alt not in stale or alt in squared:
                continue
            norm, st = normalize.for_upload(
                SPIKE / "fabric-details" / args.garment / fn, args.garment,
                notice=detail_notice(args.garment))
            mid = sc.upload_media_image(args.product_gid, norm, alt)
            sc.wait_for_media_ready(mid)
            done += 1
            print(f"  refaced detail {fn}  {st['src'][0]}x{st['src'][1]} -> "
                  f"{st['out'][0]}x{st['out'][1]} on {st['gray']}"
                  + (f'  notice "{st["notice"]}"' if st.get("notice") else ""))
        print(f"\nREFACE complete, {done} uploaded. Nothing deleted. "
              "Run --report to check, then --prune.")
        return

    # --prune
    if clash:
        raise SystemExit("refusing to prune: surplus mockups are still variant-bound.")
    if drop:
        res = sc.gql("""
          mutation($pid: ID!, $ids: [ID!]!) {
            productDeleteMedia(productId: $pid, mediaIds: $ids) {
              deletedMediaIds mediaUserErrors { message } } }""",
            {"pid": args.product_gid, "ids": drop})["productDeleteMedia"]
        if res["mediaUserErrors"]:
            raise SystemExit(str(res["mediaUserErrors"]))
        print(f"  deleted {len(res['deletedMediaIds'])} surplus flat mockup(s)")

    prod = fetch(sc, args.product_gid)
    by_alt = {m.get("alt"): m["id"] for m in prod["media"]["nodes"] if m.get("alt")}
    # SLOTS 2 AND LAST. Look these up by alt text first. The pixel classifier
    # only ever sees UNLABELLED media, so once a flat has been refaced it carries
    # an alt and drops out of `still` entirely: relying on the classifier here
    # would silently resolve both to None and rebuild the gallery with slot 2 and
    # the last slot missing. The classifier is a tool for identifying Tapstitch's
    # unlabelled uploads, not the source of truth for gallery position.
    still = {m["id"] for m in prod["media"]["nodes"] if not m.get("alt")}
    lead_back = by_alt.get(flat_alt(args.temple, args.garment, "back", flat_colour(args.garment))) or \
        next((m for m in still if seen.get(m, (None, None))[1] == "back"), None)
    lead_front = by_alt.get(flat_alt(args.temple, args.garment, "front", flat_colour(args.garment))) or \
        next((m for m in still if seen.get(m, (None, None))[1] == "front"), None)
    if not lead_back:
        raise SystemExit("no flat back mockup for slot 2, refaced or otherwise. "
                         "Refusing to reorder into a gallery that is missing it.")
    target = []
    if lead_back:
        target.append(lead_back)
    if lead_front:
        target.append(lead_front)
    if art:
        target.append(art[0]["id"])
    # ORDER already starts with the lead colour, so the on-model run keeps the
    # lead first without a special case.
    for c in ORDER[args.garment]:
        mid = by_alt.get(on_model_alt(args.temple, args.garment, c))
        if mid:
            target.append(mid)
    for _, alt in caps:
        if alt in by_alt:
            target.append(by_alt[alt])
    for idx, mid in enumerate(target):
        sc.move_media_to_position(args.product_gid, mid, idx)
    print("\nFINAL GALLERY:")
    for i, m in enumerate(fetch(sc, args.product_gid)["media"]["nodes"]):
        print(f"  {i+1:2d}. {m.get('alt') or '(flat mockup, lead colour)'}")


if __name__ == "__main__":
    main()
