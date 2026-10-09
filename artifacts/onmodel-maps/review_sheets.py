"""Review sheets for Evan: one contact sheet per product, a placement check per
garment and view against Tapstitch's flat, and 100% crops of the finest art.

  python review_sheets.py                    # Nauvoo and Salt Lake City
  python review_sheets.py whitingham sharon  # named cities
"""

import json
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
FINAL = HERE / "final"
OUT = HERE / "review"
MODELS = json.loads((HERE / "models.json").read_text())
LEAD = MODELS["lead"]
GARMENT_NAME = {"tee": "tee", "crew": "sweatshirt", "hoodie": "hoodie"}


def colours(g):
    cs = [k.split("_", 1)[1] for k in MODELS["colours"] if k.startswith(g + "_")]
    return [LEAD[g]] + [c for c in cs if c != LEAD[g]]


def contact(place, g):
    cs = colours(g)
    T = 560
    sheet = Image.new("RGB", (len(cs) * T, 2 * T + 40), "white")
    d = ImageDraw.Draw(sheet)
    for i, c in enumerate(cs):
        for j, v in enumerate(["back", "front"]):
            p = FINAL / f"{place}_{g}_{v}_{c}.jpg"
            if p.exists():
                sheet.paste(Image.open(p).resize((T, T), Image.LANCZOS), (i * T, j * T))
        d.text((i * T + 8, 2 * T + 10), c, fill="black")
    sheet.save(OUT / f"sheet_{place}_{g}.jpg", quality=88)


def placement(place, g, v):
    """The lead colour's on-model shot beside Tapstitch's flat of the same product."""
    flat = Image.open(HERE / "flats" / f"{place}_{g}_{v}.png").convert("RGB").resize((900, 900))
    shot = Image.open(FINAL / f"{place}_{g}_{v}_{LEAD[g]}.jpg").resize((900, 900), Image.LANCZOS)
    out = Image.new("RGB", (1800, 900))
    out.paste(flat, (0, 0))
    out.paste(shot, (900, 0))
    out.save(OUT / f"placement_{place}_{g}_{v}.jpg", quality=88)


def crops():
    """100% crops: Salt Lake City's 0.5mm streets and the coordinates line."""
    log = json.loads((OUT / "build_log.json").read_text())
    for g in ["tee", "crew", "hoodie"]:
        name = f"salt-lake-city_{g}_back_{LEAD[g]}"
        x, y, w = log[name]["ink_px"]
        im = Image.open(FINAL / f"{name}.jpg")
        im.crop((x + int(w * 0.35), y + int(w * 0.25), x + int(w * 0.35) + 1000,
                 y + int(w * 0.25) + 1000)).save(OUT / f"zoom_{name}.jpg", quality=92)
        name = f"salt-lake-city_{g}_front_{LEAD[g]}"
        x, y, w = log[name]["ink_px"]
        im = Image.open(FINAL / f"{name}.jpg")
        im.crop((x - 60, y - 60, x + w + 60, y + int(w / 4.7) + 60)).save(
            OUT / f"zoom_{name}.jpg", quality=92)


if __name__ == "__main__":
    import sys
    for place in sys.argv[1:] or ["nauvoo", "salt-lake-city"]:
        for g in ["tee", "crew", "hoodie"]:
            contact(place, g)
            for v in ["back", "front"]:
                if (HERE / "flats" / f"{place}_{g}_{v}.png").exists():
                    placement(place, g, v)
    crops()
    print(sorted(p.name for p in OUT.glob("*.jpg")))
