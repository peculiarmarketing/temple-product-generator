#!/usr/bin/env python
"""Pink, Light Blue and Cream for the 45 temple tees (Evan, 8 Oct 2026).

Same recipe as build_colourways.py, same man as the other five tee colours: one
generation from the live Charcoal on-model shot, the print removed, the colour
changed, a slight new pose. The temple is composited afterwards by
composite_catalog.py with the tee's existing landmarks.
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_colourways as bc  # noqa: E402
import kie_client as kie  # noqa: E402

BASE = ("https://cdn.shopify.com/s/files/1/0923/2957/4772/files/"
        "tee_dark-gray_bf9bc9f7-42f1-4674-a5c3-c6e164fc9130.jpg?v=1791401504")
NEW = {  # slug: (words, measured Tapstitch RGB, Tapstitch flat of the blank back)
    "pink": ("a soft light pink, a gentle dusty rose pink cotton, clearly pink rather than peach or lilac",
             (225, 170, 180)),
    "light-blue": ("a soft light sky blue, a pale clear blue cotton, clearly blue rather than grey or lilac",
                   (170, 202, 238)),
    "cream": ("a pale warm cream, a light apricot off-white cotton, clearly warmer than white",
              (242, 225, 201)),
}
SAMPLE = json.load(open(sys.argv[1]))   # {slug: url of Tapstitch's blank back in that colour}
OUT = Path(sys.argv[2])


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    jobs = {}
    for i, (slug, (words, rgb)) in enumerate(NEW.items()):
        bc.COLOURS["tee"][slug] = words
        bc.SWATCH["tee"][slug] = slug
        bc.TRUE.setdefault("tee", {})[slug] = list(rgb)
        bc.COLOUR_REF.setdefault("tee", {})[slug] = SAMPLE[slug]
        p = bc.prompt_for("tee", slug, bc.POSES[(i + 3) % len(bc.POSES)])
        p = p.replace("Reproduce the reference image almost exactly",
                      "Reproduce the FIRST reference image almost exactly, removing the printed "
                      "artwork from the back entirely")
        r = kie.create(p, [BASE, SAMPLE[slug]], resolution="2K", aspect_ratio="1:1")
        jobs[f"tee_{slug}"] = (r.get("data") or {}).get("taskId")
        print("submitted", slug, jobs[f"tee_{slug}"]); time.sleep(0.4)
    urls = {}
    for name, tid in jobs.items():
        u = kie.result_urls(kie.wait(tid, timeout=900, every=8))
        urls[name] = u[0] if u else None
    (OUT / "urls.json").write_text(json.dumps(urls, indent=1))
    print(json.dumps(urls, indent=1))


if __name__ == "__main__":
    main()
