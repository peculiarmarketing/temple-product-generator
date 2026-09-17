#!/usr/bin/env python
"""Generate every colourway from its garment's approved base, in one parallel batch.

Chain depth is the whole point. Each colourway is ONE generation from the base,
and the base is ONE generation from the Tapstitch reference photo. Two deep, not
the three or four that made the subject drift from photographic to rendered.

Model consistency is why the base is the reference rather than the Tapstitch
photo: Tapstitch's own model is a different person, so generating each colourway
straight from it would give a different stranger per colour.
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kie_client as kie  # noqa: E402

TRUE = json.load(open(Path(__file__).resolve().parent / "true_colors_all.json"))

# Colour wording plus the measured Tapstitch swatch. Naming the RGB took the tee
# grey from 30 away to 4, so every colour carries its number.
COLOURS = {
    "tee": {
        "dark-gray":  "a medium charcoal gray, a mid-tone neutral warm gray, clearly lighter than a deep charcoal and much lighter than black, with no blue cast",
        "black":      "a deep true black, a rich neutral black cotton, not charcoal and not faded, with the weave and soft fold shading still readable rather than crushed to a flat silhouette",
        "navy-blue":  "a dark navy blue, a deep muted indigo navy with a slight cool cast, clearly blue rather than black",
        "maroon":     "a deep maroon, a dark brick-red wine colour, clearly red rather than brown or purple",
        "coffee":     "a warm mid coffee brown, an earthy milk-chocolate brown with a warm reddish cast, clearly brown rather than grey or black",
    },
    "hoodie": {
        "gray":       "a medium sage gray with a faint warm olive-green cast, a clearly mid-tone gray, not washed out, nowhere near black or navy",
        "black":      "a deep true black, a rich neutral black fleece, not charcoal and not washed out, with the nap and fold shading still readable rather than crushed to a flat silhouette",
        "navy-blue":  "a dark navy blue, a deep muted slate navy with a slight cool grey-blue cast, clearly blue rather than black",
        "royal-blue": "a royal blue, a strong but not electric cobalt, clearly much brighter and bluer than navy yet slightly muted rather than neon",
        "mauve":      "a muted dusty mauve, a greyed mauve-taupe with a soft rose cast, a mid-tone and NOT a pale pastel pink",
        "coffee":     "a warm mid coffee brown, a rich earthy chocolate brown with a warm reddish cast, clearly brown rather than grey or black",
    },
}

SWATCH = {"tee": {"dark-gray": "Dark Gray", "black": "Black", "navy-blue": "Navy Blue",
                  "maroon": "Maroon", "coffee": "Coffee"},
          "hoodie": {"gray": "Gray", "black": "Black", "navy-blue": "Navy Blue",
                     "royal-blue": "Royal Blue", "mauve": "Mauve", "coffee": "Coffee"}}

POSES = [
    "his weight rests a little more on his LEFT leg and his arms hang a fraction further forward",
    "his weight rests a little more on his RIGHT leg and his arms hang a fraction further from his sides",
    "he stands evenly on both feet, fingers relaxed and slightly curled, shoulders a shade lower",
    "his weight rests a little more on his LEFT leg and his head is turned just a few degrees to his left",
    "his weight rests a little more on his RIGHT leg and one shoulder sits marginally lower",
    "he stands evenly on both feet with his arms hanging a fraction further back",
]

GARMENT = {
    "tee": ("t-shirt", "the same oversized boxy cut, the same drop shoulders, the same roomy short "
            "sleeves, the same ribbed crew collar, the same heavyweight cotton"),
    "hoodie": ("hooded sweatshirt", "the same oversized boxy cut, the same drop shoulders, the same "
               "roomy wide sleeves gathering softly into ribbed cuffs, the same wide ribbed waistband, "
               "the same hood shape, the same heavyweight fleece, the hood down and resting flat "
               "against the upper back, the cuffs ending above the waistband hem with both hands "
               "fully visible below them"),
}


def prompt_for(garment, colour, pose):
    noun, cut = GARMENT[garment]
    rgb = [int(v) for v in TRUE[garment][SWATCH[garment][colour]]]
    return (
        f"Reproduce the reference image almost exactly, changing only the colour and the pose "
        f"slightly. Photorealistic apparel catalog photograph shot from directly behind, square 1:1 "
        f"format. This is the EXACT SAME MAN as in the reference image, photographed again in the "
        f"same studio on the same day: the same build, the same height, the same shoulder width, the "
        f"same hair and haircut, the same skin tone, the same black trousers, the same framing from "
        f"above the top of the head down to mid-thigh, the same light neutral gray seamless studio "
        f"backdrop, the same soft even studio lighting from the front left. He wears the SAME {noun} "
        f"as in the reference in every structural respect: {cut}. "
        f"CHANGE THE COLOUR: the {noun} is {COLOURS[garment][colour]}, approximately RGB "
        f"{rgb[0]},{rgb[1]},{rgb[2]}. Match that colour closely. "
        f"KEEP THE FABRIC EXACTLY AS IN THE REFERENCE: the central back panel stays broad and flat, "
        f"with every fold, crease and wave pushed out to the outer sides, the armholes and sleeves, "
        f"and low near the hem. Nothing creases across the middle of the back. The surface is smooth, "
        f"even and uniformly dyed edge to edge: no mottling, no cloudiness, no blotches, no "
        f"patchiness, no speckling, no heathered or marled effect, no stone-wash, no acid-wash, no "
        f"vintage distressing. "
        f"The back is completely blank, with absolutely no print, graphic, logo, lettering or "
        f"decoration of any kind anywhere on it. "
        f"POSE: shoulders stay square to the camera and the torso upright and untwisted, but {pose} "
        f"than in the reference. "
        f"No accessories, no jewellery. Sharp focus, true-to-life color, no stylization.")


def main():
    bases = json.load(open(sys.argv[1]))          # {"tee": url, "hoodie": url}
    out = Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
    jobs = {}
    for garment, base_url in bases.items():
        for i, colour in enumerate(COLOURS[garment]):
            p = prompt_for(garment, colour, POSES[i % len(POSES)])
            r = kie.create(p, [base_url], resolution="2K", aspect_ratio="1:1")
            tid = (r.get("data") or {}).get("taskId")
            jobs[f"{garment}_{colour}"] = tid
            print(f"submitted {garment}_{colour}: {tid}")
            time.sleep(0.4)
    json.dump(jobs, open(out / "jobs.json", "w"), indent=1)
    print(f"\n{len(jobs)} submitted, waiting...\n")
    urls = {}
    for name, tid in jobs.items():
        try:
            d = kie.wait(tid, timeout=900, every=8)
            u = kie.result_urls(d)
            urls[name] = u[0] if u else None
            print(f"  {name:22s} {'ok' if u else 'NO URL'}")
        except Exception as e:
            urls[name] = None
            print(f"  {name:22s} FAILED {e}")
    json.dump(urls, open(out / "urls.json", "w"), indent=1)
    print(f"\n{sum(1 for v in urls.values() if v)}/{len(urls)} succeeded")


if __name__ == "__main__":
    main()
