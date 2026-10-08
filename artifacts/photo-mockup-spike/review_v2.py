#!/usr/bin/env python
"""Review sheets for the v2 on-model photos (onmodel-v2/review/).

  python review_v2.py placement   # each final beside Tapstitch's flat of the same design and colour,
                                  # both scaled so the chest width is the same, with guide lines
  python review_v2.py sheets      # per product: every on-model shot plus the close-up cards
  python review_v2.py zooms       # 100% crops of every print on every final

Flats are the store products' own Tapstitch images (1400px), downloaded to
onmodel-v2/flats/ by download_flats().
"""
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

Image.MAX_IMAGE_PIXELS = None
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from composite_front_v2 import ART, FLAT, OUT_PX, V2, geo_key, jobs_for, place  # noqa: E402

OUT = V2 / "review"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def font(n):
    try:
        return ImageFont.truetype(FONT, n)
    except OSError:
        return ImageFont.load_default()


def flat_path(name, art):
    g, colour = name.split("_")[0], name.split("_")[1]
    if g == "bomber":
        side = "back" if name.endswith("_back") else "front"
        return V2 / "flats" / f"bomber_{colour}_{side}.png"
    return V2 / "flats" / f"{g}_{art}_{colour}.png"


def window(collar, chest, im, out_w=900):
    """A crop centred on the collar, 1.5 chest widths wide, 0.25 above to 0.85
    below, resized to out_w. Returns the crop and the scale used."""
    cx, cy = collar
    x0, x1 = cx - 0.75 * chest, cx + 0.75 * chest
    y0, y1 = cy - 0.25 * chest, cy + 0.85 * chest
    c = im.crop((round(x0), round(y0), round(x1), round(y1)))
    k = out_w / c.width
    return c.resize((out_w, round(c.height * k)), Image.LANCZOS)


def placement():
    OUT.mkdir(exist_ok=True)
    lm = json.loads((V2 / "landmarks.json").read_text())
    marks = FLAT["_marks"]
    rows = []
    for name, L in sorted(lm.items()):
        for art, fn in jobs_for(name):
            fin = V2 / "final" / f"{fn}.jpg"
            fp = flat_path(name, art)
            if not fin.exists() or not fp.exists():
                continue
            key = geo_key(name, art)
            m = marks[key.rsplit("_", 1)[0] if key.split("_")[0] in ("tee", "crew", "hoodie") else key]
            k = OUT_PX / 4096
            photo = window([v * k for v in L["collar"]], (L["chest"][1] - L["chest"][0]) * k,
                           Image.open(fin).convert("RGB"))
            flat = window(m["collar"], m["chest"][1] - m["chest"][0], Image.open(fp).convert("RGB"))
            h = max(photo.height, flat.height)
            row = Image.new("RGB", (1800 + 30, h + 50), "white")
            row.paste(flat, (0, 50))
            row.paste(photo, (930, 50))
            d = ImageDraw.Draw(row)
            # guides: collar (red) and ink top (yellow) at the flat's ratios, drawn across both
            y_collar = 50 + round(0.25 * 900 / 1.5)
            y_top = y_collar + round(FLAT[key]["d"] * 900 / 1.5)
            for y, col in ((y_collar, (255, 0, 0)), (y_top, (255, 200, 0))):
                d.line([(0, y), (row.width, y)], fill=col, width=2)
            d.text((8, 10), f"Tapstitch flat: {fp.stem}", fill=(0, 0, 0), font=font(24))
            d.text((938, 10), f"v2 on-model: {fn}", fill=(0, 0, 0), font=font(24))
            rows.append((fn, row))
    for g in ("tee", "crew", "hoodie", "bomber"):
        rs = [r for n, r in rows if n.startswith(g)]
        if not rs:
            continue
        W = max(r.width for r in rs)
        sheet = Image.new("RGB", (W, sum(r.height + 20 for r in rs)), "white")
        y = 0
        for r in rs:
            sheet.paste(r, (0, y))
            y += r.height + 20
        sheet.save(OUT / f"placement_{g}.jpg", quality=85)
        print("wrote", f"placement_{g}.jpg", len(rs), "rows")


# --- design close-up cards ---------------------------------------------------
# Like the temple products' "Temple line art close-up" (layout.render_art_card):
# the design centred on a square, here on the garment's own colour (sampled from
# Tapstitch's flat) because every design is white ink. Rendered from the vector
# files (matched to the print files at r >= 0.994); the seal from its 3600px
# print file.
WS = HERE.parent.parent.parent / "peculiar-people-workspace-claude-projects-" / "designs"
CARD_PX = 4096
VECTOR = {"en": WS / "be-peculiar/trace/english white.svg",
          "es": WS / "be-peculiar/trace/spanish white.svg",
          "chest": WS / "jacket-chest-logo/final/chest-logo-a2-white.svg"}
CARDS = {   # card name -> (art, flat to sample the colour from, coverage)
    "card_tee_en": ("en", "tee_en_black", 0.86),
    "card_tee_es": ("es", "tee_es_navy-blue", 0.86),
    "card_crew_en": ("en", "crew_en_black", 0.86),
    "card_crew_es": ("es", "crew_es_black", 0.86),
    "card_hoodie_en": ("en", "hoodie_en_gray", 0.86),
    "card_hoodie_es": ("es", "hoodie_es_coffee", 0.86),
    "card_bomber_chest": ("chest", "bomber_navy-blue_front", 0.70),
    "card_bomber_seal": ("seal", "bomber_navy-blue_back", 0.86),
}


def garment_rgb(flat):
    import numpy as np
    a = np.asarray(Image.open(V2 / "flats" / f"{flat}.png").convert("RGB"), float)
    patch = a[800:1000, 560:840].reshape(-1, 3)      # body below the print, clear of ink
    return tuple(int(round(v)) for v in np.median(patch, 0))


def render_art(art, width):
    import io
    if art in VECTOR:
        import cairosvg
        png = cairosvg.svg2png(url=str(VECTOR[art]), output_width=width * 2)
        im = Image.open(io.BytesIO(png)).convert("RGBA")
    else:
        im = Image.open(ART[art]).convert("RGBA")
    im = im.crop(im.getchannel("A").getbbox())
    return im


def cards():
    out = V2 / "cards"
    out.mkdir(exist_ok=True)
    for name, (art, flat, cov) in CARDS.items():
        rgb = garment_rgb(flat)
        ink = render_art(art, CARD_PX)
        k = CARD_PX * cov / max(ink.size)
        ink = ink.resize((round(ink.width * k), round(ink.height * k)), Image.LANCZOS)
        card = Image.new("RGB", (CARD_PX, CARD_PX), rgb)
        card.paste(ink, ((CARD_PX - ink.width) // 2, (CARD_PX - ink.height) // 2), ink)
        card.save(out / f"{name}.png", optimize=True)
        print("wrote", name, rgb, ink.size)


# --- product sheets and 100% zooms --------------------------------------------
PRODUCTS = {   # sheet -> (finals prefix filter, lead first, cards)
    "tee_en": (lambda f: f.startswith("tee_") and f.endswith("_en"), "tee_black_en", ["card_tee_en"]),
    "tee_es": (lambda f: f.startswith("tee_") and f.endswith("_es"), "tee_navy-blue_es", ["card_tee_es"]),
    "crew_en": (lambda f: f.startswith("crew_") and f.endswith("_en"), "crew_black_en", ["card_crew_en"]),
    "crew_es": (lambda f: f.startswith("crew_") and f.endswith("_es"), "crew_black_es", ["card_crew_es"]),
    "hoodie_en": (lambda f: f.startswith("hoodie_") and f.endswith("_en"), "hoodie_gray_en", ["card_hoodie_en"]),
    "hoodie_es": (lambda f: f.startswith("hoodie_") and f.endswith("_es"), "hoodie_coffee_es", ["card_hoodie_es"]),
    "bomber": (lambda f: f.startswith("bomber_"), "bomber_navy-blue_back",
               ["card_bomber_chest", "card_bomber_seal"]),
}


def finals():
    return sorted(p.stem for p in (V2 / "final").glob("*.jpg"))


def sheets(tile=760, cols=4):
    OUT.mkdir(exist_ok=True)
    for sheet, (keep, lead, cards_) in PRODUCTS.items():
        names = [f for f in finals() if keep(f)]
        names = ([lead] if lead in names else []) + [n for n in names if n != lead]
        items = [(n, V2 / "final" / f"{n}.jpg") for n in names] + \
                [(c, V2 / "cards" / f"{c}.png") for c in cards_]
        rows = (len(items) + cols - 1) // cols
        S = Image.new("RGB", (cols * tile, rows * (tile + 44)), "white")
        d = ImageDraw.Draw(S)
        for i, (n, p) in enumerate(items):
            im = Image.open(p).convert("RGB").resize((tile, tile), Image.LANCZOS)
            x, y = (i % cols) * tile, (i // cols) * (tile + 44)
            S.paste(im, (x, y + 44))
            d.text((x + 8, y + 8), ("1. " if i == 0 else f"{i + 1}. ") + n, fill=(0, 0, 0), font=font(26))
        S.save(OUT / f"sheet_{sheet}.jpg", quality=88)
        print("wrote", f"sheet_{sheet}.jpg", len(items))


def zooms():
    """The print region of every final at 100%: what a shopper sees at full zoom."""
    import json as _j
    OUT.mkdir(exist_ok=True)
    lm = _j.loads((V2 / "landmarks.json").read_text())
    k = OUT_PX / 4096
    crops = {}
    for name, L in sorted(lm.items()):
        for art, fn in jobs_for(name):
            p = V2 / "final" / f"{fn}.jpg"
            if not p.exists():
                continue
            left, top, w = (v * k for v in place(L, geo_key(name, art), art))
            a = Image.open(ART[art])
            a = a.crop(a.getchannel("A").getbbox())
            h = w * a.height / a.width
            m = 40
            crops[fn] = Image.open(p).convert("RGB").crop(
                (round(left - m), round(top - m), round(left + w + m), round(top + h + m)))
    groups = {}
    for fn, c in crops.items():
        g = "bomber_front" if fn.startswith("bomber") and not fn.endswith("_back") else \
            "bomber_back" if fn.startswith("bomber") else fn.split("_")[0] + "_" + fn.rsplit("_", 1)[1]
        groups.setdefault(g, []).append((fn, c))
    for g, items in groups.items():
        W = max(c.width for _, c in items) + 20
        H = sum(c.height + 50 for _, c in items)
        S = Image.new("RGB", (W, H), "white")
        d = ImageDraw.Draw(S)
        y = 0
        for fn, c in items:
            d.text((10, y + 10), f"{fn}  (100%, no scaling)", fill=(0, 0, 0), font=font(26))
            S.paste(c, (10, y + 46))
            y += c.height + 50
        S.save(OUT / f"zoom_{g}.png", optimize=True)
        print("wrote", f"zoom_{g}.png", len(items))


def verify():
    """Correlate each composited print with its design file at the same size.
    The ink is white on every garment, so the print's luminance lift over the
    blank photo should track the art's alpha almost exactly; a warp, blur or
    misplacement drops r well below 0.98."""
    import json as _j
    import numpy as np
    lm = _j.loads((V2 / "landmarks.json").read_text())
    k = OUT_PX / 4096
    rows = {}
    for name, L in sorted(lm.items()):
        blank = Image.open(V2 / "blanks" / f"{name}.jpg").convert("L").resize((OUT_PX, OUT_PX), Image.LANCZOS)
        for art, fn in jobs_for(name):
            p = V2 / "final" / f"{fn}.jpg"
            if not p.exists():
                continue
            left, top, w = (v * k for v in place(L, geo_key(name, art), art))
            a = Image.open(ART[art]).convert("RGBA")
            a = a.crop(a.getchannel("A").getbbox())
            W, H = round(w), round(w * a.height / a.width)
            box = (round(left), round(top), round(left) + W, round(top) + H)
            fin = np.asarray(Image.open(p).convert("L").crop(box), float)
            bl = np.asarray(blank.crop(box), float)
            alpha = np.asarray(a.getchannel("A").resize((W, H), Image.LANCZOS), float)
            r = float(np.corrcoef((fin - bl).ravel(), alpha.ravel())[0, 1])
            rows[fn] = round(r, 4)
    (V2 / "review" / "verify.json").write_text(_j.dumps(rows, indent=1))
    worst = min(rows.items(), key=lambda kv: kv[1])
    print(len(rows), "prints checked; lowest r", worst)
    return rows


if __name__ == "__main__":
    {"placement": placement, "cards": cards, "sheets": sheets, "zooms": zooms, "verify": verify}[sys.argv[1]]()
