#!/usr/bin/env python
"""Download finished Higgsfield 4K upscales into onmodel-v2/blanks/ as JPEG q95.

  python fetch_upscales.py name=url [name=url ...]
Every result is checked against its source (downscaled to the source size, phase
correlation and mean abs difference) so an upscaler that moved or redrew the
photo is caught before landmarks are measured on it.
"""
import io
import json
import sys
from pathlib import Path

import numpy as np
import requests
from PIL import Image

V2 = Path(__file__).resolve().parent.parent / "onmodel-v2"
SRC = {"v1": V2.parent / "onmodel-front" / "blanks", "gen": V2 / "gen" / "src"}


def source(name):
    for p in (SRC["gen"] / f"{name}.png", SRC["v1"] / f"{name}.jpg"):   # v2 regenerations first
        if p.exists():
            return p


def main(pairs):
    log_p = V2 / "blanks" / "upscale_log.json"
    log = json.loads(log_p.read_text()) if log_p.exists() else {}
    for pair in pairs:
        name, url = pair.split("=", 1)
        im = Image.open(io.BytesIO(requests.get(url, timeout=120).content)).convert("RGB")
        src = Image.open(source(name)).convert("L")
        from skimage.registration import phase_cross_correlation
        a = np.asarray(im.convert("L").resize(src.size, Image.LANCZOS), float)
        b = np.asarray(src, float)
        shift = phase_cross_correlation(b, a, upsample_factor=4)[0].tolist()
        mad = float(np.abs(a - b).mean())
        if im.size != (4096, 4096):
            im = im.resize((4096, 4096), Image.LANCZOS)
        im.save(V2 / "blanks" / f"{name}.jpg", quality=95, subsampling=0)
        log[name] = {"url": url, "shift": shift, "mad": round(mad, 2)}
        print(name, im.size, "shift", shift, "mad", round(mad, 2))
    log_p.write_text(json.dumps(log, indent=1))


if __name__ == "__main__":
    main(sys.argv[1:])
