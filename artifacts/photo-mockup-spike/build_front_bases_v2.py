#!/usr/bin/env python
"""v2 on-model bases for the Be Peculiar line and the seal bomber (Evan's review, 8 Oct 2026).

Differences from build_front_bases.py (v1):
  - Hoodie FIT: the base is regenerated from the v1 hoodie photo (same model) with
    a temple hoodie on-model shot as a fit reference: longer body, hem at the
    hips, sleeves bunching at the cuffs. "boxy" is gone from the prompt.
  - Resolution: asks kie.ai for 4K; whatever comes back is upscaled to RES px
    (Lanczos) before compositing, so the print is rendered at high resolution.
  - Bomber: one extra unzipped-over-a-white-tee lifestyle shot (Evan, 8 Oct:
    main front stays zipped).

  python build_front_bases_v2.py base <spec.json> <outdir>      # spec: {name: {prompt_key, refs:[urls]}}
  python build_front_bases_v2.py recolour <spec.json> <outdir>  # same shape as v1 recolour spec
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kie_client as kie  # noqa: E402
from build_front_bases import GARMENT as V1_GARMENT, GRAY, POSES  # noqa: E402

RES = "4K"
GARMENT = dict(V1_GARMENT)
GARMENT["hoodie"] = (
    "fleece hooded sweatshirt",
    "a relaxed oversized fit with dropped shoulders; the body is LONG, the ribbed waistband "
    "sitting low on the hips, below the top of the trousers, covering the belt line; the "
    "sleeves are long and full, bunching and stacking in soft folds above the ribbed cuffs at "
    "the wrists; a front kangaroo pocket, the hood down and resting behind the neck, no "
    "drawstrings, heavyweight brushed fleece")

FIT_NOTE = {
    "hoodie": ("The THIRD reference image is a real photo of this exact hoodie on a model, seen "
               "from the back. Match its fit exactly: the same body length relative to the "
               "torso, the waistband sitting low on the hips in the same place, the same "
               "fullness, and the sleeves bunching at the cuffs the same way. The body must be "
               "clearly long, never cropped, and the sleeves must not look longer than the body. "
               "Take nothing else from the third image: not its model, view, print or colour."),
}


def hoodie_base_prompt(colour_words):
    noun, cut = GARMENT["hoodie"]
    return (
        f"Photorealistic apparel catalog photograph, square 1:1, shot from directly in front, "
        f"the body square to the camera, the head level and looking straight into the lens with "
        f"a calm neutral expression. Use the FIRST reference image for the person only: the same "
        f"man, the same face, hair, build, skin tone, arms and hands, in the same relaxed upright "
        f"stance with arms hanging naturally at his sides. He wears a {noun} with {cut}, worn "
        f"naturally in his size, with dark plain trousers. The {noun} is {colour_words}; take "
        f"its exact colour and fabric from the SECOND reference image, a flat photo of the real "
        f"garment, and take nothing else from that image. {FIT_NOTE['hoodie']} The front of the "
        f"garment is completely blank: no print, logo, lettering, graphic or tag anywhere on it. "
        f"FRAMING: from just above the top of the head down to mid-thigh, so the whole hoodie "
        f"and the top of the trousers below its waistband are in frame, the man centred. "
        f"BACKDROP: a seamless plain light neutral studio gray, flat colour {GRAY['hoodie']}, no "
        f"gradient, no props, soft even studio lighting from the front left, a soft natural "
        f"shadow. Smooth evenly dyed fabric with natural folds at the sides and sleeves, the "
        f"chest panel broad and flat. No accessories. Sharp focus, true-to-life colour, no "
        f"stylization.")


def fit_prompt(garment, colour_words):
    """Re-dress the existing model so the garment fits like the temple on-model shot."""
    noun, cut = GARMENT[garment]
    return (
        f"Reproduce the FIRST reference image almost exactly: the same man, face, hair, pose, "
        f"framing, crop, backdrop and lighting. Keep the {noun} the same colour ({colour_words}) "
        f"and completely blank. Change only its FIT to match the SECOND reference image, a real "
        f"photo of this exact garment on a model seen from the back: the same body length "
        f"relative to the torso, the hem in the same place on the hips, the same fullness and "
        f"the same sleeve length and drape. Take nothing else from the second image. Sharp "
        f"focus, true-to-life colour.")


def extend_prompt(note):
    """Zoom the camera out and lengthen the hoodie body on an existing base."""
    return (
        "Reproduce the FIRST reference image: the same man, face, hair, hoodie, colour, "
        "backdrop and lighting. Two changes only. 1) FRAMING: the camera is further back, so "
        "the top of his hair sits just below the top edge of the frame and the frame ends at "
        "mid-thigh; the trousers are clearly visible for a good hand's length below the "
        "hoodie's waistband, and both hands are fully in frame. 2) FIT: match the SECOND "
        "reference image, a real photo of this exact hoodie on a model from the back: the body "
        "is long, the ribbed waistband sits low on the hips, a little BELOW the level of the "
        "ribbed cuffs, and the sleeves stack in soft folds above the cuffs. " + note +
        " The hoodie stays completely blank, no print or logo. Photorealistic, sharp focus, "
        "true-to-life colour.")


def unzipped_prompt(colour_words):
    return (
        "Reproduce the FIRST reference image closely: the same man, the same face, hair, build, "
        "framing, crop, backdrop and lighting, and the same bomber jacket in every structural "
        f"respect, {colour_words}, with its white shoulder piping and striped ribbed trim. "
        "Change only this: the jacket is now worn UNZIPPED and hanging open, over a plain white "
        "crew-neck t-shirt with no print. The two open front panels hang naturally and flat at "
        "either side of the white tee, the left chest panel (on the viewer's right) facing the "
        "camera squarely and flat, without folds, so a small chest logo could sit on it. A "
        "relaxed natural stance, the torso square to the camera. The jacket stays completely "
        "plain, no print or logo. Sharp focus, true-to-life colour.")


def recolour_prompt(garment, colour_words, rgb, pose):
    noun = GARMENT[garment][0]
    keep = (" Keep the white piping and the two white stripes in the ribbed collar, cuffs and "
            "hem exactly white." if garment == "bomber" else "")
    fit = (" Keep the hoodie's fit exactly: the same long body with the waistband low on the "
           "hips, and the same sleeve bunching at the cuffs." if garment == "hoodie" else "")
    return (
        f"Reproduce the FIRST reference image almost exactly: the same man, the same face, "
        f"framing, crop, backdrop and lighting, and the same {noun} in every structural "
        f"respect, the same length and fit. Change the colour of the {noun}, and change the "
        f"pose VERY slightly so this reads as a separate photo from the same shoot: {pose}. The "
        f"shoulders stay square to the camera and the torso upright and untwisted, the chest "
        f"panel flat and facing the lens.{fit} "
        f"It is now {colour_words}, approximately RGB {rgb[0]},{rgb[1]},{rgb[2]}. Take the exact "
        f"colour and fabric look from the SECOND reference image, a flat photo of the real "
        f"garment in this colour; take nothing else from it, not its print, framing or shape."
        f"{keep} The garment stays completely blank, no print or logo. Smooth, evenly dyed "
        f"fabric. Sharp focus, true-to-life colour.")


def run(jobs, out, resolution=RES):
    out.mkdir(parents=True, exist_ok=True)
    ids = {}
    for name, (prompt, refs) in jobs.items():
        r = kie.create(prompt, refs, resolution=resolution, aspect_ratio="1:1")
        tid = (r.get("data") or {}).get("taskId")
        if not tid:
            print(name, "REJECTED", json.dumps(r)[:300])
            continue
        ids[name] = tid
        print("submitted", name, tid)
        time.sleep(0.4)
    urls = {}
    for name, tid in ids.items():
        try:
            u = kie.result_urls(kie.wait(tid, timeout=1200, every=10))
            urls[name] = u[0] if u else None
        except Exception as e:
            urls[name] = None
            print(name, "FAILED", e)
    prev = json.loads((out / "urls.json").read_text()) if (out / "urls.json").exists() else {}
    prev.update(urls)
    (out / "urls.json").write_text(json.dumps(prev, indent=1))
    return urls


def build_jobs(spec):
    jobs = {}
    for i, (n, j) in enumerate(spec.items()):
        kind = j["kind"]
        if kind == "hoodie_base":
            p = hoodie_base_prompt(j["colour_words"])
        elif kind == "fit":
            p = fit_prompt(j["garment"], j["colour_words"])
        elif kind == "extend":
            p = extend_prompt(j.get("note", ""))
        elif kind == "unzipped":
            p = unzipped_prompt(j["colour_words"])
        elif kind == "recolour":
            p = recolour_prompt(j["garment"], j["colour_words"], j["rgb"],
                                POSES[j.get("pose", i) % len(POSES)])
        else:
            raise SystemExit(f"unknown kind {kind}")
        jobs[n] = (p, j["refs"])
    return jobs


if __name__ == "__main__":
    spec = json.load(open(sys.argv[1]))
    print(json.dumps(run(build_jobs(spec), Path(sys.argv[2])), indent=1))
