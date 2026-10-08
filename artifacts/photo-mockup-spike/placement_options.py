#!/usr/bin/env python
"""Placement options for Evan to pick from, in real inches (8 Oct 2026).

Scale comes from the model's chest width and the size chart (size L chest,
pit to pit), so px/in = chest_px / CHEST_IN. Each option sets the print width
and how far its top sits below the collar.

  python placement_options.py tee_black en
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from composite_front_v2 import ART, OUT_PX, V2, composite, place, geo_key  # noqa: E402

CHEST_IN = {"tee": 21.65, "crew": 25.20, "hoodie": 27.56}     # size L, size guides
PRINT_IN = {"en": 9.95, "es": 9.95}                           # Tapstitch print width (prints.json)
OPTIONS = [  # (label, width in, top below collar in); None = current v2
    ("Current", None, None),
    ("A", 9.95, 3.0), ("B", 9.95, 4.0), ("C", 9.95, 5.0),
    ("D", 11.0, 3.0), ("E", 11.0, 4.0), ("F", 11.0, 5.0),
]
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def render(name, art, tile=900):
    lm = json.loads((V2 / "landmarks.json").read_text())[name]
    g = name.split("_")[0]
    im = Image.open(V2 / "blanks" / f"{name}.jpg").convert("RGB")
    k = OUT_PX / im.width
    photo = np.asarray(im.resize((OUT_PX, OUT_PX), Image.LANCZOS), dtype=np.float64)
    chest = (lm["chest"][1] - lm["chest"][0]) * k
    ppi = chest / CHEST_IN[g]
    cx, cy = lm["collar"][0] * k, lm["collar"][1] * k
    tiles, fulls = [], []
    for label, w_in, top_in in OPTIONS:
        if w_in is None:
            left, top, w = (v * k for v in place(lm, geo_key(name, art), art))
            w_in, top_in = w / ppi, (top - cy) / ppi
        else:
            w, top = w_in * ppi, cy + top_in * ppi
            left = cx - w / 2
        out = composite(photo, ART[art], left, top, w)
        # crop: collar region down to mid-torso, square
        side = chest * 1.25
        box = (cx - side / 2, cy - side * 0.18, cx + side / 2, cy + side * 0.82)
        f = Image.fromarray(out).resize((tile, tile), Image.LANCZOS)
        ImageDraw.Draw(f).text((14, 10), label, fill=(200, 0, 0), font=ImageFont.truetype(FONT, 44))
        fulls.append(f)
        t = Image.fromarray(out).crop(tuple(round(b) for b in box)).resize((tile, tile), Image.LANCZOS)
        d = ImageDraw.Draw(t)
        d.rectangle([0, 0, tile, 64], fill=(255, 255, 255))
        d.text((14, 10), f"{label}: {w_in:.1f} in wide, top {top_in:.1f} in below collar",
               fill=(0, 0, 0), font=ImageFont.truetype(FONT, 30))
        tiles.append(t)
    cols = 3
    rows = (len(tiles) + cols - 1) // cols
    S = Image.new("RGB", (cols * tile, rows * tile), "white")
    # current alone on the first row, centred; options below
    S = Image.new("RGB", (cols * tile, (1 + (len(tiles) - 1 + cols - 1) // cols) * tile), "white")
    S.paste(tiles[0], (tile, 0))
    for i, t in enumerate(tiles[1:]):
        S.paste(t, ((i % cols) * tile, (1 + i // cols) * tile))
    out = V2 / "review" / f"options_{name}_{art}.jpg"
    S.save(out, quality=90)
    F = Image.new("RGB", (4 * tile, 2 * tile), "white")
    for i, f in enumerate(fulls):
        F.paste(f, ((i % 4) * tile, (i // 4) * tile))
    F.resize((F.width // 2, F.height // 2), Image.LANCZOS).save(
        V2 / "review" / f"options_{name}_{art}_full.jpg", quality=90)
    print("wrote", out.name, f"ppi {ppi:.1f}")


if __name__ == "__main__":
    render(sys.argv[1], sys.argv[2])
