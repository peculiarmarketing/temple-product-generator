#!/usr/bin/env python
"""On-model backs for the three new tee colours (Pink, Light Blue, Cream), one temple.

The temple print is read from the product's own Tapstitch design (the back
piece's print file on Tapstitch's CDN), so this runs anywhere, without the Mac's
Temples/ folder. The blanks are the existing tee model recoloured on 8 Oct 2026
(artifacts/onmodel-front/blanks/back_tee_<slug>.jpg), one generation from the
same base as the five live colours, so print_geometry.json's tee landmarks hold.
Same settings as composite_catalog.py, so they match the live colours' photos.

  python scripts/tee_new_colour_composites.py <template_id> <outdir>
"""
import io
import json
import sys
from pathlib import Path

import numpy as np
import requests
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SPIKE = ROOT / "artifacts/photo-mockup-spike"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SPIKE))
import tapstitch_api as T  # noqa: E402
from composite import build, load_art  # noqa: E402
from composite_set import quad_for  # noqa: E402

Image.MAX_IMAGE_PIXELS = None
NEW = ("pink", "light-blue", "cream")
BLANKS = ROOT / "artifacts/onmodel-front/blanks"


def back_print(s, template_id, dest):
    cfg = json.loads(T.get_template(s, template_id)["config"])
    srcs = [o["src"] for c in cfg if c["piece"] == "back" for o in c["objects"]]
    if len(srcs) != 1:
        raise SystemExit(f"template {template_id}: {len(srcs)} back print files")
    r = requests.get(srcs[0], timeout=120)
    r.raise_for_status()
    dest.write_bytes(r.content)
    return dest, srcs[0]


def composite(art_path, outdir):
    geometry = json.loads((SPIKE / "print_geometry.json").read_text())
    geo, fold = geometry["tee"], geometry["fold"]
    quad, *_ = quad_for(art_path, geo["collar"], geo["hem"], geo["centre"], geo["length_in"],
                        geo["ink_top_below_collar_in"], geo.get("scale_nudge", 1.0),
                        geo.get("print_centre_below_collar_in"))
    art = load_art(str(art_path), quad)
    out = {}
    for slug in NEW:
        rgb = np.asarray(Image.open(BLANKS / f"back_tee_{slug}.jpg").convert("RGB"), dtype=np.float64)
        img, _ = build(rgb, art, quad, 3.0, fold["shade_gain"], 0.35, 0.93, scale=1.0,
                       fold_strength=fold["strength"], fold_band=fold["band_px"])
        p = Path(outdir) / f"tee_{slug}.jpg"
        Image.fromarray(img).save(p, quality=94)
        out[slug] = p
    return out


def main(template_id, outdir):
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    art, url = back_print(T.session(), template_id, outdir / "back_print.png")
    print("print", url)
    for slug, p in composite(art, outdir).items():
        print("wrote", p)


if __name__ == "__main__":
    main(*sys.argv[1:3])
