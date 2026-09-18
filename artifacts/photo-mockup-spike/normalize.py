#!/usr/bin/env python
"""Put every gallery image on the same gray and the same 1:1 crop.

Per Evan, 18 Sep 2026. The Salt Lake galleries shipped with the on-model shots on
a light gray studio backdrop and everything else on pure white, and with the
fabric close-ups at 2048x2731 while everything else was square. This module is
the fix, and it lives in the pipeline so every temple from here on comes out
right rather than being corrected by hand.

Two operations, both lossless where it counts:

  gray_background()  white backdrop -> the garment's own gray
  square_crop()      pure pixel slice to 1:1, never a resample, never an upscale

WHAT MUST NOT HAPPEN, AND WHY THE FILL IS REGION-BASED. The flat BACK mockups
carry the temple printed in near-white ink INSIDE the garment silhouette. A
colour key on "white" punches holes straight through the artwork and shows gray
through the temple. Measured on the Salt Lake hoodie flats: 9,733 white pixels on
the black back and 9,911 on the coffee back are print, not background. So only
white that is CONNECTED TO THE IMAGE BORDER counts as background. Everything
enclosed by garment is left alone.

THE EDGE, AND WHY THERE IS NO HALO. An antialiased edge pixel is a blend of the
garment colour C over the white backdrop:

    P = (1 - b) * C + b * 255

for background fraction b. Replacing white with gray G wants
(1 - b) * C + b * G, which rearranges to

    out = P + b * (G - 255)

so only b is needed and C never has to be known. The white contribution is
subtracted rather than painted over, which is what keeps a white fringe from
being left behind. b is recovered per pixel from the local garment darkness, so
a dark navy edge and a mid coffee edge are each solved correctly.

NO SCIPY IN THIS VENV (same constraint composite.py works under), so the
connected-region fill is a hand-rolled scanline flood fill and the dilation is
numpy shifts. About half a second per image.

THE ART CLOSEUP IS EXEMPT. Slot 3 stays on white so the design reads clearly.
Nothing here is ever pointed at it.

    ./.venv.nosync/bin/python artifacts/photo-mockup-spike/normalize.py --selftest
    ./.venv.nosync/bin/python artifacts/photo-mockup-spike/normalize.py --contact-sheet
"""
import json
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
FINAL_SET = HERE / "final-set"
GRAYS_CACHE = HERE / "backdrop_grays.json"

WHITE = 250          # a BORDER pixel this bright certainly seeds the backdrop
LOOSE = 228          # the backdrop grows through anything this bright
BAND_FLOOR = 200     # below this a pixel is definitely garment, never background
SNAP = 0.85          # a band pixel this close to pure backdrop is snapped to it
FEATHER = 2          # px of antialias band solved around the background edge
RING_LIMIT = 214     # interior-ring p99 above this cannot be keyed off white
MIN_SEPARATION = 20  # the garment must stand this far off its backdrop
SEPARATION_FLOOR = 140  # never darken a backdrop past this chasing separation

# WHY TWO THRESHOLDS. The fabric close-ups are JPEG. Right beside a dark cutout
# edge the backdrop carries ringing down to about 228, so a single strict mask
# leaves a one-to-two pixel necklace of not-quite-white pixels sitting on the new
# gray. Solving those as partial coverage makes it worse, not better: the linear
# model reads a ringing 246 as 96% background and carries the missing 9 levels
# through, which measured as a rim 7 to 17 levels DARKER than the backdrop.
#
# So the seed is strict and the growth is loose. Only a border pixel at 250+ can
# start the backdrop, but once started it spreads through anything at 228+. That
# absorbs the ringing into the backdrop proper, where it resolves to exactly the
# target gray. Measured: it removes ~80% of the rim and grows the background by
# 0.02-0.06%, which is the ringing and nothing else. The palest garment interior
# ring in the live set is 214 (crew Flower Gray), so 228 clears real fabric by 14
# levels and the region constraint means a leak would need a connected path of
# 228+ pixels running from the frame edge into the garment.


# --------------------------------------------------------------------------
# the gray


def backdrop_gray(garment, refresh=False):
    """The light gray of THIS garment's own on-model shots, as (r, g, b) ints.

    Measured rather than hardcoded. The studio backdrop is not one colour across
    the three garments: the hoodie set sits near #C5C5C7, the tee near #C0C0C4
    and the crew near #BBBCC1, because crew_black came off the older pipeline.
    Evan's call is that each product matches its own model shots, so a product
    page is internally consistent. Measuring keeps that true for any garment
    added later without another constant to maintain.

    Sampled from the left and right margin strips, where the model never reaches.
    A mean, because the backdrop is a lit wall that falls from about #C8C7CB at
    the top to #BABABD at the bottom and the mean is the single number that reads
    closest to the whole. The darkest and lightest 5% are trimmed first so a
    stray sleeve or a blown highlight cannot drag it.
    """
    cache = json.loads(GRAYS_CACHE.read_text()) if GRAYS_CACHE.exists() else {}
    if not refresh and garment in cache:
        return tuple(cache[garment])
    shots = sorted(FINAL_SET.glob(f"{garment}_*.jpg"))
    if not shots:
        raise SystemExit(f"no model shots in {FINAL_SET} for garment {garment!r}; "
                         "cannot measure its backdrop gray")
    strips = []
    for f in shots:
        a = np.asarray(Image.open(f).convert("RGB"), dtype=np.float64)
        w = a.shape[1]
        strips.append(np.concatenate([a[:, :90], a[:, w - 90:]], axis=1).reshape(-1, 3))
    allpx = np.concatenate(strips)
    lum = allpx.min(axis=1)
    lo, hi = np.percentile(lum, [5, 95])
    keep = allpx[(lum >= lo) & (lum <= hi)]
    gray = tuple(int(round(v)) for v in keep.mean(axis=0))
    cache[garment] = list(gray)
    GRAYS_CACHE.write_text(json.dumps(cache, indent=1, sort_keys=True) + "\n")
    return gray


def separated_gray(img, gray, min_sep=MIN_SEPARATION):
    """Darken `gray` if the garment would otherwise vanish into it.

    Found on the crew, 18 Sep 2026. Flower Gray is the one garment whose flat lay
    sits at almost exactly its own backdrop brightness: body RGB 183 against a
    backdrop of 189, six levels apart, so the sleeves and hem melt into the
    background and the sweatshirt loses its silhouette. The hoodie (navy, 45) and
    the tee (black, 24) each had over 150 levels of separation, which is why
    neither showed it.

    Note what the pale-garment guard does NOT do. It measures the edge ring and
    asks whether the key would EAT the garment. That is a different question from
    whether the result is legible, and on the crew it answered 214 against a
    limit of 214 and passed. A garment can key perfectly and still be invisible.

    Returns (gray, report). Only ever darkens: lightening moves toward white,
    which is what this whole change is getting away from.
    """
    a = np.asarray(img.convert("RGB"), dtype=np.float32)
    mn = a.min(axis=2)
    bg = border_fill(mn)
    body = ~bg
    for _ in range(25):                       # well inside, so edges cannot skew it
        nxt = body.copy()
        nxt[1:, :] &= body[:-1, :]
        nxt[:-1, :] &= body[1:, :]
        nxt[:, 1:] &= body[:, :-1]
        nxt[:, :-1] &= body[:, 1:]
        body = nxt
    if not body.any() or not bg.any():
        return tuple(gray), {"separation": None}
    lum = float(a[body].mean())
    want = float(np.mean(gray))
    sep = abs(want - lum)
    rep = {"body_luma": lum, "backdrop_luma": want, "separation": sep, "adjusted": False}
    if sep >= min_sep:
        return tuple(gray), rep
    target = max(SEPARATION_FLOOR, lum - min_sep)
    scaled = tuple(int(round(c * target / want)) for c in gray)
    rep.update(adjusted=True, gray=scaled, new_separation=abs(np.mean(scaled) - lum))
    return scaled, rep


# --------------------------------------------------------------------------
# region tools, hand-rolled because there is no scipy


def border_fill(mn, seed_level=WHITE, mask_level=LOOSE):
    """Bool mask of backdrop: white reachable from the frame edge. Scanline fill.

    This is the whole reason the temple print survives. Seeds are strict-white
    pixels on the four edges only, so white enclosed by garment is never reached
    no matter how bright it is.
    """
    return _fill(mn >= mask_level, mn >= seed_level)


def border_region(img, tol=14):
    """Bool mask of backdrop of ANY flat colour, not just white.

    Added 18 Sep 2026 after a live mistake. Once a flat lay has been recoloured
    onto the gray, border_fill finds nothing, because the gray is nowhere near
    white. Anything that then asks "which pixels are garment" by brightness
    counts the whole backdrop as garment: build_product_gallery's colour
    classifier did exactly that, matched every flat at a distance of 184, and the
    fallback it triggered published the Salt Lake flat lay onto the Boise product.

    Samples the frame edge for the backdrop colour and fills from the border
    through anything within `tol` of it, so it works on white and on gray.
    """
    a = np.asarray(img.convert("RGB"), dtype=np.float32) if hasattr(img, "convert") \
        else np.asarray(img, dtype=np.float32)
    h, w = a.shape[:2]
    edge = np.concatenate([a[:4].reshape(-1, 3), a[-4:].reshape(-1, 3),
                           a[:, :4].reshape(-1, 3), a[:, -4:].reshape(-1, 3)])
    ref = np.median(edge, axis=0)
    close = np.abs(a - ref).max(axis=2) <= tol
    seed = np.zeros_like(close)
    seed[0, :] = seed[-1, :] = True
    seed[:, 0] = seed[:, -1] = True
    return _fill(close, close & seed)


def _fill(mask, seed_ok):
    """Everything in `mask` reachable from a border pixel that is also seed_ok."""
    white = mask
    h, w = white.shape
    out = np.zeros_like(white)
    stack = deque()
    seed = white & seed_ok
    for x in range(w):
        if seed[0, x]:
            stack.append((0, x))
        if seed[h - 1, x]:
            stack.append((h - 1, x))
    for y in range(h):
        if seed[y, 0]:
            stack.append((y, 0))
        if seed[y, w - 1]:
            stack.append((y, w - 1))
    while stack:
        y, x = stack.pop()
        if out[y, x] or not white[y, x]:
            continue
        xl = x
        while xl > 0 and white[y, xl - 1] and not out[y, xl - 1]:
            xl -= 1
        xr = x
        while xr < w - 1 and white[y, xr + 1] and not out[y, xr + 1]:
            xr += 1
        out[y, xl:xr + 1] = True
        for ny in (y - 1, y + 1):
            if 0 <= ny < h:
                seg = white[ny, xl:xr + 1] & ~out[ny, xl:xr + 1]
                idx = np.flatnonzero(seg)
                if len(idx):
                    for run in np.split(idx, np.flatnonzero(np.diff(idx) != 1) + 1):
                        stack.append((ny, xl + int(run[0])))
    return out


def _dilate(mask, r):
    """Square dilation by r px, as r passes of a 4-neighbour max. numpy shifts."""
    out = mask.copy()
    for _ in range(r):
        nxt = out.copy()
        nxt[1:, :] |= out[:-1, :]
        nxt[:-1, :] |= out[1:, :]
        nxt[:, 1:] |= out[:, :-1]
        nxt[:, :-1] |= out[:, 1:]
        out = nxt
    return out


def _local_garment_min(mn, garment_mask, r=3):
    """For each pixel, the darkest confidently-garment min-RGB within r px.

    This is the local estimate of min(C) that turns an edge pixel's brightness
    into a background fraction. Without it, b would have to assume a garment
    darkness and would over- or under-correct on navy versus coffee.
    """
    big = np.where(garment_mask, mn, np.float32(np.inf))
    out = big.copy()
    for _ in range(r):
        nxt = out.copy()
        nxt[1:, :] = np.minimum(nxt[1:, :], out[:-1, :])
        nxt[:-1, :] = np.minimum(nxt[:-1, :], out[1:, :])
        nxt[:, 1:] = np.minimum(nxt[:, 1:], out[:, :-1])
        nxt[:, :-1] = np.minimum(nxt[:, :-1], out[:, 1:])
        out = nxt
    return out


# --------------------------------------------------------------------------
# the two operations


def gray_background(img, gray, feather=FEATHER, strict=True):
    """Replace the border-connected white backdrop with `gray`.

    Returns (image, stats). A full-bleed macro shot with no backdrop comes back
    untouched, which is correct: three of the nine fabric close-ups are fabric
    edge to edge and have no background to replace.
    """
    a = np.asarray(img.convert("RGB"), dtype=np.float32)
    mn = a.min(axis=2)
    bg = border_fill(mn)
    stats = {"bg_fraction": float(bg.mean()),
             "enclosed_white": int(((mn >= WHITE) & ~bg).sum())}

    if not bg.any():
        stats["note"] = "no border-connected white; full-bleed, left as is"
        return img.convert("RGB"), stats

    garment = mn < BAND_FLOOR
    # The guard measures the ring 2-6px INSIDE the backdrop boundary, because
    # that is the only population that can be wrongly swallowed. A whole-garment
    # median is the wrong statistic: a dark garment with a blown highlight at its
    # edge is the risky case and a median hides it.
    ring = _dilate(bg, 6) & ~_dilate(bg, 2)
    rp99 = float(np.percentile(mn[ring], 99)) if ring.any() else 0.0
    stats["ring_p99"] = rp99
    stats["garment_median"] = float(np.median(mn[garment])) if garment.any() else 255.0
    if rp99 > RING_LIMIT:
        msg = (f"the garment edge reaches min-RGB {rp99:.0f}, against a backdrop mask "
               f"at {LOOSE}. Keying this against white would eat the garment. "
               "Render this colourway on a non-white backdrop instead.")
        if strict:
            raise ValueError(msg)
        stats["warning"] = msg

    G = np.asarray(gray, dtype=np.float32)
    out = a.copy()
    out[bg] = G                                   # flat, clean, no JPEG noise

    # The antialias band: not background, but touching it. Deliberately NO
    # brightness floor. A pixel that is 20% backdrop over a black garment reads
    # about 60, and an earlier cut of this excluded it for being too dark, which
    # left its backdrop fifth still WHITE against a gray surround: a one-pixel
    # light fringe, exactly the halo this is meant to prevent. The band is kept
    # to 2px instead, because real antialiasing is one to two pixels wide and a
    # wider band risks reading a specular highlight as partial coverage.
    band = _dilate(bg, feather) & ~bg
    if band.any():
        cloc = _local_garment_min(mn, garment, r=feather + 2)
        cloc = np.where(np.isfinite(cloc), cloc, np.float32(0.0))
        denom = np.maximum(255.0 - cloc, 1.0)
        b = np.clip((mn - cloc) / denom, 0.0, 1.0)
        # Anything the model says is almost all backdrop IS backdrop. Carrying a
        # ringing pixel's missing levels through the blend is what left a dark
        # rim; snapping resolves it to the target gray exactly.
        b = np.where(b >= SNAP, 1.0, b)[band][:, None]
        out[band] = a[band] + b * (G - 255.0)     # out = P + b*(G - 255)
    stats["band_px"] = int(band.sum())

    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), "RGB"), stats


def content_bbox(img, thresh=235):
    a = np.asarray(img.convert("RGB"))
    m = a.min(axis=2) < thresh
    ys, xs = np.where(m.any(axis=1))[0], np.where(m.any(axis=0))[0]
    if not len(ys) or not len(xs):
        h, w = a.shape[:2]
        return 0, 0, w - 1, h - 1
    return int(xs[0]), int(ys[0]), int(xs[-1]), int(ys[-1])


def square_crop(img):
    """Crop to 1:1 at native resolution. A pixel slice: no resample, no upscale.

    The window is centred on the content rather than on the frame. On the fabric
    close-ups a plain centre crop takes 341px off the top and clips the point of
    the hood; centring on content takes 0 to 152px and only off a garment that
    already bleeds past the frame edge.
    """
    w, h = img.size
    if w == h:
        return img.convert("RGB"), (0, 0, w, h)
    s = min(w, h)
    x0, y0, x1, y1 = content_bbox(img)
    if h > w:
        top = int(round((y0 + y1) / 2 - s / 2))
        top = max(0, min(h - s, top))
        box = (0, top, s, top + s)
    else:
        left = int(round((x0 + x1) / 2 - s / 2))
        left = max(0, min(w - s, left))
        box = (left, 0, left + s, h)
    return img.convert("RGB").crop(box), box


def normalize(path, garment, gray=None, strict=True):
    """Gray the backdrop, then crop to 1:1. Returns (image, stats)."""
    gray = gray or backdrop_gray(garment)
    img = Image.open(path)
    src = img.size
    img, stats = gray_background(img, gray, strict=strict)
    img, box = square_crop(img)
    stats.update({"src": src, "out": img.size, "crop_box": box, "gray": tuple(gray)})
    return img, stats


CACHE = HERE / "normalized"
FONT_PATH = HERE.parent.parent / "fonts" / "Alata-Regular.ttf"
NOTICE_HEIGHT = 0.072   # band height as a fraction of the image side
NOTICE_TEXT = 0.030     # cap height as a fraction of the image side


def stamp_notice(img, text, gray):
    """Black notice text on a backdrop-gray band across the bottom.

    Evan asked for black text at the bottom of the crew fabric shots. Set
    directly on the photo it would not read: the bottom strip of crew/D1 and
    crew/D2 is tan fleece at luma 109 and 124, and only crew/D3 happens to end on
    the gray backdrop. A band in the garment's own backdrop gray keeps the text
    black as asked, keeps it legible on all three, and matches the surrounding
    gallery rather than looking bolted on.

    Drawn AFTER the crop, so the band is never cropped off.
    """
    img = img.convert("RGB")
    w, h = img.size
    band = int(round(h * NOTICE_HEIGHT))
    out = img.copy()
    d = ImageDraw.Draw(out)
    d.rectangle([0, h - band, w, h], fill=tuple(gray))
    size = max(10, int(round(h * NOTICE_TEXT)))
    font = ImageFont.truetype(str(FONT_PATH), size)
    x0, y0, x1, y1 = d.textbbox((0, 0), text, font=font)
    d.text(((w - (x1 - x0)) / 2 - x0, h - band + (band - (y1 - y0)) / 2 - y0),
           text, font=font, fill=(0, 0, 0))
    return out


def for_upload(src, garment, cache=None, strict=True, separate=False, gray=None,
               notice=None):
    """Normalize `src` and return a PNG path ready for upload_media_image().

    Derived at upload time and never committed. Nine normalized 2048x2048 PNGs
    run to tens of megabytes and are a pure function of tracked inputs, so
    caching them on disk buys nothing and changing a backdrop gray would strand
    every one of them. The cost is about a second per image inside an operation
    already dominated by the staged upload and wait_for_media_ready.

    PNG, not JPEG. The fabric close-ups arrive as JPEG; re-encoding them after a
    recolour would stack a second lossy generation on an image the whole point of
    which is that it lost no quality. Shopify re-encodes to WebP for delivery
    anyway, so the larger upload costs nothing downstream. upload_media_image
    guesses the MIME type from the filename, so callers need no other change.
    """
    src = Path(src)
    cache = Path(cache) if cache else (CACHE / garment)
    cache.mkdir(parents=True, exist_ok=True)
    sep = {}
    if separate and gray is None:
        gray, sep = separated_gray(Image.open(src), backdrop_gray(garment))
    img, stats = normalize(src, garment, gray=gray, strict=strict)
    stats["separation"] = sep
    if notice:
        img = stamp_notice(img, notice, gray or backdrop_gray(garment))
        stats["notice"] = notice
    out = cache / (src.stem + ".png")
    img.save(out, "PNG", optimize=True)
    return out, stats


# --------------------------------------------------------------------------
# verification


FLATS = HERE.parent / "tapstitch/removed-flat-mockups/hoodie-salt-lake"


def _cases():
    """(path, garment) for everything this module is ever pointed at."""
    out = []
    for g in ("crew", "hoodie", "tee"):
        out += [(p, g) for p in sorted((HERE / "fabric-details" / g).glob("D*.jpg"))]
    out += [(p, "hoodie") for p in sorted(FLATS.glob("*.png"))]
    return out


def selftest():
    """Prove the two things that could silently ruin an image.

    1. Nothing is resampled or upscaled.
    2. The recolour touches background only. Garment pixels come through
       byte-identical, and the near-white temple print inside a back flat
       survives intact, which is the hole-punching regression.
    """
    fails = 0
    print(f"{'image':42s} {'src':>11s} {'out':>11s} {'bg%':>6s} "
          f"{'print px':>9s} {'band':>6s}  checks")
    for path, garment in _cases():
        src = Image.open(path).convert("RGB")
        img, st = normalize(path, garment)
        sa = np.asarray(src, dtype=np.int16)
        oa = np.asarray(img, dtype=np.int16)

        notes = []
        # 1. square, at native resolution, never upscaled
        if img.size[0] != img.size[1]:
            notes.append("NOT SQUARE"); fails += 1
        if img.size[0] != min(src.size):
            notes.append(f"SIDE {img.size[0]} != min(src) {min(src.size)}"); fails += 1

        # compare in the cropped frame
        x0, y0, x1, y1 = st["crop_box"]
        sc = sa[y0:y1, x0:x1]
        mn = sc.min(axis=2)
        bgm = border_fill(mn)
        protected = (mn < BAND_FLOOR) & ~_dilate(bgm, FEATHER)

        # 2. garment pixels untouched
        diff = int((sc[protected] != oa[protected]).any(axis=-1).sum()) if protected.any() else 0
        if diff:
            notes.append(f"GARMENT ALTERED {diff}px"); fails += 1

        # 3. enclosed near-white (the temple print) preserved
        encl = (mn >= WHITE) & ~bgm
        before = int(encl.sum())
        after = int(((oa.min(axis=2) >= WHITE) & encl).sum())
        if before and after < before:
            notes.append(f"PRINT EATEN {before - after}/{before}px"); fails += 1

        # 4. background actually became the gray
        if bgm.any():
            corner = oa[bgm][:2000]
            want = np.asarray(st["gray"])
            if int(np.abs(corner.mean(axis=0) - want).max()) > 1:
                notes.append(f"BG {corner.mean(axis=0).round()} != {want}"); fails += 1
        elif diff == 0 and (sc != oa).any():
            notes.append("FULL-BLEED ALTERED"); fails += 1

        name = "/".join(str(path).split("/")[-2:])
        print(f"{name[:42]:42s} {'x'.join(map(str,src.size)):>11s} "
              f"{'x'.join(map(str,img.size)):>11s} {st['bg_fraction']*100:5.1f}% "
              f"{before:9,d} {st.get('band_px',0):6,d}  {'; '.join(notes) or 'ok'}")
    print(f"\n{'FAILED: ' + str(fails) + ' check(s)' if fails else 'ALL CHECKS PASS'}")
    return fails


def contact_sheet(out_dir):
    """Before/after pairs plus a 400% edge crop, for a human to approve.

    Two sheets, because the ten flat mockups are near-identical and would bury
    the nine fabric shots in one long strip.
    """
    from PIL import Image, ImageDraw, ImageFontDraw
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []

    groups = {
        "fabric-details": [(p, g) for p, g in _cases() if p.suffix == ".jpg"],
        "flat-mockups": [(p, g) for p, g in _cases() if p.suffix == ".png"],
    }
    cell, pad, lab, cols = 260, 8, 18, 3
    for name, cases in groups.items():
        rows = (len(cases) + cols - 1) // cols
        gw = cell * 2 + pad
        sheet = Image.new("RGB", (cols * gw + pad * (cols + 1),
                                  rows * (cell + lab + pad) + pad), (238, 238, 240))
        d = ImageDraw.Draw(sheet)
        for i, (path, garment) in enumerate(cases):
            r, c = divmod(i, cols)
            x = pad + c * (gw + pad)
            y = pad + r * (cell + lab + pad)
            d.text((x, y + 4), f"{'/'.join(str(path).split('/')[-2:])[:44]}"
                               f"   before | after  {backdrop_gray(garment)}", fill=(40, 40, 40))
            for j, im in enumerate((Image.open(path).convert("RGB"),
                                    normalize(path, garment)[0])):
                t = im.copy()
                t.thumbnail((cell, cell), Image.LANCZOS)
                sheet.paste(t, (x + j * (cell + pad) + (cell - t.width) // 2,
                                y + lab + (cell - t.height) // 2))
        f = out_dir / f"{name}.jpg"
        sheet.save(f, quality=93)
        written.append(f)

    # 400% edge crops: proof there is no white fringe left at the garment edge
    picks = [(HERE / "fabric-details/hoodie/D2.jpg", "hoodie"),
             (FLATS / "black_back_56152188420468.png", "hoodie")]
    strip = Image.new("RGB", (len(picks) * (320 + pad) + pad, 320 + pad * 2), (238, 238, 240))
    for i, (path, garment) in enumerate(picks):
        after, st = normalize(path, garment)
        # Locate the edge on the SOURCE. On the output the backdrop is gray, so
        # a white-based fill there finds nothing, which is what crashed this.
        x0, y0, x1, y1 = st["crop_box"]
        src = np.asarray(Image.open(path).convert("RGB"))[y0:y1, x0:x1]
        bg = border_fill(src.min(axis=2))
        edge = _dilate(bg, 2) & ~bg
        ys, xs = np.where(edge)
        if not len(ys):
            continue
        # An actual band pixel. Taking the median of the y and the x lists
        # separately gives a point that is usually INSIDE the garment, which is
        # how an earlier cut of this produced a zoom of plain fabric instead of
        # the silhouette edge it is meant to prove.
        k = len(ys) // 2
        cy, cx = int(ys[k]), int(xs[k])
        z = after.crop((cx - 40, cy - 40, cx + 40, cy + 40)).resize((320, 320), Image.NEAREST)
        strip.paste(z, (pad + i * (320 + pad), pad))
    f = out_dir / "edge-400pct.png"
    strip.save(f)
    written.append(f)
    return written


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--contact-sheet", metavar="DIR", nargs="?", const=".")
    ap.add_argument("--grays", action="store_true", help="re-measure the per-garment grays")
    a = ap.parse_args()
    if a.grays:
        for g in ("hoodie", "tee", "crew"):
            print(g, backdrop_gray(g, refresh=True))
    if a.contact_sheet:
        for f in contact_sheet(a.contact_sheet):
            print("wrote", f)
    if a.selftest:
        raise SystemExit(selftest())
