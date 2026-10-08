#!/usr/bin/env python
"""Front-view (and bomber back-view) on-model bases for the non-temple lines.

Evan, 8 Oct 2026: real stock models (Shopify Burst, free for commercial use) in
a plain standing stance, re-dressed in our blank, on the studio gray the store
already uses, a different model per garment type, framed like the store's existing
shots (top of the head to mid-thigh). The print is composited afterwards
with composite.py, never drawn by the image model, so the wordmark and the small
verse line stay exact.

One generation from the stock photo per colour. The second reference is
Tapstitch's own flat of the blank in that colour (its print-free back), used as
the colour and fabric sample.
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kie_client as kie  # noqa: E402

BURST = "https://burst.shopifycdn.com/photos/{}.jpg?width=2400"
MODELS = {
    "tee": "white-tshirt-template",
    "crew": "portrait-of-male-model",
    "hoodie": "man-in-white-tank-top-stands-for-camera",
    "bomber": "man-in-blue-jacket",
}
GRAY = {"tee": "#C1C1C5", "crew": "#BDBDC2", "hoodie": "#C6C6C8", "bomber": "#C1C1C5"}
GARMENT = {
    "tee": ("heavyweight cotton t-shirt", "an oversized boxy cut with dropped shoulders, roomy "
            "short sleeves ending just above the elbow, a ribbed crew collar, the hem at the "
            "upper thigh, heavyweight 260gsm cotton that drapes with soft weight"),
    "crew": ("fleece crewneck sweatshirt", "a relaxed loose cut with dropped shoulders, long "
             "sleeves gathering softly into ribbed cuffs, a ribbed crew collar and a ribbed "
             "waistband sitting at the hip, heavyweight brushed fleece"),
    "hoodie": ("fleece hooded sweatshirt", "an oversized boxy cut with dropped shoulders, roomy "
               "wide sleeves gathering into ribbed cuffs, a front kangaroo pocket, a wide ribbed "
               "waistband, the hood down and resting behind the neck, no drawstrings, "
               "heavyweight brushed fleece"),
    "bomber": ("zip-up bomber jacket", "a loose cut with dropped shoulders, a short stand "
               "collar, a full-length front zip worn ZIPPED UP to the chest, white contrast "
               "piping along the tops of the shoulders, striped ribbed trim at the collar, "
               "cuffs and hem (two white stripes), two side welt pockets, heavyweight fabric"),
}


def prompt_for(garment, colour_words, view="front"):
    noun, cut = GARMENT[garment]
    side = ("from directly in front, the body square to the camera, the head level and "
            "looking straight into the lens with a calm neutral expression" if view == "front" else
            "from directly behind, the back square to the camera, the head level and facing "
            "straight away from the camera")
    blank = ("The front of the garment is completely blank: no print, logo, lettering, graphic "
             "or tag anywhere on it." if garment != "bomber" else
             "The jacket is completely plain: no print, logo, patch, lettering or graphic "
             "anywhere on it.")
    return (
        f"Photorealistic apparel catalog photograph, square 1:1, shot {side}. Use the FIRST "
        f"reference image for the person only: the same man, the same face, hair, build, skin "
        f"tone, arms and hands, standing in the same relaxed upright stance with arms hanging naturally at his "
        f"sides. Re-dress him: he now wears a {noun} with {cut}, worn naturally in his size, "
        f"with dark plain trousers. The {noun} is {colour_words}; take its exact colour and fabric "
        f"from the SECOND reference image, a flat photo of the real garment in this colour, and "
        f"take nothing else from that image. {blank} "
        f"FRAMING: from just above the top of the head down to mid-thigh, the man centred, the "
        f"garment filling most of the frame. BACKDROP: a seamless plain light neutral studio gray, flat colour {GRAY[garment]}, "
        f"no gradient, no props, soft even studio lighting from the front left, a soft natural "
        f"shadow. Smooth evenly dyed fabric with natural folds at the sides and sleeves, the "
        f"chest panel broad and flat. No accessories, no jewellery. Sharp focus, true-to-life "
        f"colour, no stylization.")


def run(jobs, out):
    out.mkdir(parents=True, exist_ok=True)
    ids = {}
    for name, (prompt, refs) in jobs.items():
        r = kie.create(prompt, refs, resolution="2K", aspect_ratio="1:1")
        ids[name] = (r.get("data") or {}).get("taskId")
        print("submitted", name, ids[name]); time.sleep(0.4)
    urls = {}
    for name, tid in ids.items():
        try:
            u = kie.result_urls(kie.wait(tid, timeout=900, every=8))
            urls[name] = u[0] if u else None
        except Exception as e:
            urls[name] = None; print(name, "FAILED", e)
    (out / "urls.json").write_text(json.dumps(urls, indent=1))
    return urls


# Evan, 8 Oct 2026: every colour a slightly different moment, so a gallery scrolls
# like separate photos. The torso stays square and upright so the print still
# lands where the landmarks say; only weight, arms and head shift.
POSES = [
    "his weight rests a little more on his LEFT leg and his arms hang a fraction further forward",
    "his weight rests a little more on his RIGHT leg and his arms hang a fraction further from his sides",
    "he stands evenly on both feet, fingers relaxed and slightly curled, shoulders a shade lower",
    "his weight rests a little more on his LEFT leg and his head is turned just a few degrees to his left",
    "his weight rests a little more on his RIGHT leg and one shoulder sits marginally lower",
    "he stands evenly on both feet with his arms hanging a fraction further back",
    "his weight shifts slightly to his RIGHT leg and his left hand rests a little closer to his thigh",
    "he stands evenly, his chin a touch lower and his hands hanging a little wider apart",
]


def recolour_prompt(garment, colour_words, rgb, pose):
    noun = GARMENT[garment][0]
    keep = (" Keep the white piping and the two white stripes in the ribbed collar, cuffs and "
            "hem exactly white." if garment == "bomber" else "")
    return (
        f"Reproduce the FIRST reference image almost exactly: the same man, the same face, "
        f"framing, crop, backdrop, lighting and shadows, and the same {noun} in every structural "
        f"respect. Change the colour of the {noun}, and change the pose VERY slightly so this "
        f"reads as a separate photo from the same shoot: {pose}. The shoulders stay square to "
        f"the camera and the torso upright and untwisted, the chest panel flat and facing the "
        f"lens. "
        f"It is now {colour_words}, approximately RGB {rgb[0]},{rgb[1]},{rgb[2]}. Take the exact "
        f"colour and fabric look from the SECOND reference image, a flat photo of the real "
        f"garment in this colour; take nothing else from it, not its print, framing or shape."
        f"{keep} The garment stays completely blank, no print or logo. Smooth, evenly dyed "
        f"fabric. Sharp focus, true-to-life colour.")


def recolour(spec_path, out):
    """spec: {name: {garment, base_url, colour_words, rgb, sample_url}}"""
    spec = json.load(open(spec_path))
    jobs = {n: (recolour_prompt(j["garment"], j["colour_words"], j["rgb"], POSES[i % len(POSES)]),
                [j["base_url"], j["sample_url"]]) for i, (n, j) in enumerate(spec.items())}
    return run(jobs, Path(out))


if __name__ == "__main__" and sys.argv[1] == "recolour":
    print(json.dumps(recolour(sys.argv[2], sys.argv[3]), indent=1))
elif __name__ == "__main__":
    spec = json.load(open(sys.argv[1]))   # {name: {garment, colour_words, sample_url, view}}
    jobs = {n: (prompt_for(j["garment"], j["colour_words"], j.get("view", "front")),
                [BURST.format(MODELS[j["garment"]]), j["sample_url"]]) for n, j in spec.items()}
    print(json.dumps(run(jobs, Path(sys.argv[2])), indent=1))
