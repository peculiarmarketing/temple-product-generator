# Spec overlay v3: four people in a studio (9 Oct 2026)

Replaces the three-friends spec photo (spec-v2). Evan's brief: a relaxed studio
shot, one person on a stool or chair and the others sitting, ages about 18 to 30,
each person in a different product (bomber, hoodie, crewneck, tee), each with a
different front design.

## Stock search (dropped)

Three rounds on Pexels and Unsplash: `candidates.jpg`, `candidates-round2.jpg`,
`candidates-round3.jpg`. Nothing had the pose. Evan then supplied a reference
(dark cyclorama studio, one spotlight pool, four people on a stool, a chair and
the floor) and asked for a generated version instead.

## Generated base, round 1

Prompt: `prompt-v1.txt`, with Evan's reference uploaded as an image reference
(Higgsfield media e6f88d33). Every garment a plain blank; prints go on later at
measured placement, as in spec-v2. Colours: bomber forest green, hoodie navy
(lead), crewneck heather gray (lead), tee black (lead).

| File | Model | Output size | Job |
|---|---|---|---|
| render/gpt-4k-a.png | GPT Image 2.5 Sunburst, high, 4k, 3:2 | 3504x2336 | 77ebb43e |
| render/gpt-4k-b.png | same | 3504x2336 | a696183e |
| render/gpt-2k.png | GPT Image 2.5 Sunburst, high, 2k, 3:2 | 2048x1360 | f73ad790 |
| render/nb-4k-a.png | Nano Banana 2.1, 4k, thinking high, 3:2 | 5056x3392 | f97e82b7 |
| render/nb-4k-b.png | same | 5056x3392 | 20bbdd55 |

Findings:
- 4k adds pixels, not realism. GPT 4k and 2k look the same; 4k gives about 1.7x
  the pixels on each chest. That matters for the print composite, not the look.
- GPT drew the bomber as satin with piping down the zip (wrong). Nano Banana got
  the fleece, striped rib and shoulder piping right; nb-4k-a used snaps instead
  of a zip, nb-4k-b has the zip.
- GPT matches the reference's dark, moody light; Nano Banana is brighter and
  frames the group larger (about 960 px across the bomber chest).

## Round 2 (Evan picked GPT Image 2.5 Sunburst 4k)

Evan's changes: faces less shiny, garments flat on the chest for compositing, no
hoodie drawcords, colours bomber forest green, hoodie navy, sweatshirt black, tee
maroon. Prompt: `prompt-v2.txt`. References: the setting image plus the four
plain blanks behind the live on-model photos (`artifacts/onmodel-front/blanks/`),
cropped to the garment so faces are not copied: `refs/*-garment.jpg`
(Higgsfield media ff0bbe35 bomber, fb6c3bfa hoodie, 4e3858c5 crew, 18c3f177 tee).

| File | Quality | Job |
|---|---|---|
| render/v2-a.png | high | 86240f25 |
| render/v2-b.png | high | e20a51ce |
| render/v2-c.png | high | 3a187e22 |
| render/v2-d-xhigh.png | xhigh (7 credits vs 4.25) | 880b69cc |

All four: right colours and fabrics, the bomber now matte fleece with piping on
the shoulders only, no hoodie drawcords, chests square to camera and clear.
xhigh looks no better than high. Shine is reduced but still visible on the
front-row woman in each.

## Round 3: four distinct people, Higgsfield vs kie.ai

Evan: the two women looked alike, and so did the two men. `prompt-v3.txt` gives
each person a distinct face, skin tone, hair and build, and asks harder for
matte skin. Same five references.

| File | Service | Size | Job / task |
|---|---|---|---|
| render/hf-v3-a.png | Higgsfield | 3504x2336 | 4ce93d4e |
| render/hf-v3-b.png | Higgsfield | 3504x2336 | 93fda787 |
| render/hf-v3-c.png | Higgsfield | 3504x2336 | e349336b |
| render/kie-v3-a.png | kie.ai (`kie_run.py`) | 3520x2336 | cdc1d962 |
| render/kie-v3-b.png | kie.ai | 3520x2336 | 45845453 |
| render/kie-v3-c.png | kie.ai | 3520x2336 | b927acb8 |

Cost: Higgsfield 4.25 credits per image; kie.ai 16 credits per image (1048.5 to
1000.5 for three). Same model, so output quality is indistinguishable.

Open: the sneakers carry faint brand marks (a swoosh-like side panel in hf-v3-a,
an "N" in kie-v3-a and kie-v3-c). They must be cleaned before publishing, or the
next round must ask for unbranded plain white canvas sneakers.

## Round 4: tee wearer changed to a white man (kie.ai)

Evan: make the man in the maroon tee white; run on kie.ai. `prompt-v4.txt` is v3
with that one person changed (ruddy fair skin, auburn hair, short ginger beard)
and the sneakers asked for as plain unbranded white canvas.

| File | Task | Sneakers |
|---|---|---|
| render/kie-v4-a.png | 330646f1 | clean, no marks |
| render/kie-v4-b.png | 30ac71e2 | red sole pinstripe (reads as Converse) |
| render/kie-v4-c.png | 2270d951 | faint emblem on the tee wearer's shoe |

## Round 4b: same prompt on GPT Image 2 and GPT Image 2.5 Flare (kie.ai)

`kie_run.py` now takes the kie model id as a fourth argument. prompt-v4, same
five references, 4K, 3:2. Every kie.ai model charged 16 credits per image
(952.5 to 856.5 for six).

| File | Model | Task |
|---|---|---|
| render/kie-v4-img2-a.png | gpt-image-2-image-to-image | 9ce8d3c5 |
| render/kie-v4-img2-b.png | gpt-image-2-image-to-image | b8446e61 |
| render/kie-v4-img2-c.png | gpt-image-2-image-to-image | 06cac5e5 |
| render/kie-v4-flare-a.png | gpt-image-2-5-flare-image-to-image | 6d14c030 |
| render/kie-v4-flare-b.png | gpt-image-2-5-flare-image-to-image | 90ac6e84 |
| render/kie-v4-flare-c.png | gpt-image-2-5-flare-image-to-image | 8976fd2f |

Findings: GPT Image 2 gives the warmest, most natural expressions (img2-a has
real smiles) and the truest garment colours. Flare reads flatter and greyer, and
draws the hoodie as a faded vintage wash, lighter than the navy blank.

**Picked (Evan, 9 Oct):** `render/kie-v4-img2-c.png`, copied to `base/spec-v3-base.png`.

**Shoes (Evan, 9 Oct):** keep the original render; the cleaned-shoe version (`base/spec-v3-blanks.png`) is not used.

## Prints on (9 Oct)

`place_v3.py` lays the four real designs on `base/spec-v3-base.png` with
`composite()` from `photo-mockup-spike/composite_front_v2.py` (flat, no warp,
photo's light and shade, light knit texture). spec-v2's `place_logo.py` was not
used: its cloth mask only finds dark, unsaturated fabric (black), so it would
miss the green and maroon.

| Garment | Design (`art/`) | Left, top, width (px in 3504x2336) |
|---|---|---|
| Bomber, forest green | `bomber-chest-print.png` (onmodel-front/prints/chest.png) | 1402, 564, 67 |
| Hoodie, navy | `wordmark-print.png` (onmodel-front/prints/art_en.png) | 1886, 624, 188 |
| Sweatshirt, black | `coords-salt-lake-white.png` (built by city-map-back `front()`, 40.7704 N 111.8919 W) | 1156, 1367, 135 |
| Tee, maroon | `box-logo-white.png` (Important Elements, white) | 2275, 1299, 96 |

Landmarks were read off `qa/grid-*.jpg`; the rules are in the docstring of
`place_v3.py`. Output: `web/pp-spec-group-v3.png` and `.jpg` (q95, 3504 px).
Checks: `qa/printed-band.jpg`, `qa/prints-closeup.jpg`, `qa/web-size-2048.jpg`.
Not yet uploaded to Shopify Files or the theme.

## Alignment passes (Evan, 9 Oct)

All in `place_v3.py` (`ADJUST`, `SCALE`, `WARP`):
1. Bomber turned 12.3 deg so the box's left border is parallel to the zip
   (measured from the zip teeth). Hoodie down 15 px (about an inch). Crew 8 px
   right, tilted up to the right. Tee 8 px right, 12 px down, tilted low at the
   bottom left.
2. Tee logo 1.3x and 8 px further right. Crew 2 deg more counter-clockwise (3.5
   in all). Hoodie: the BE bends with the fold under it (3 px displacement from
   the fabric's shading, left 27% of the print only, verse line excluded). This
   is the only print in the photo that bends; the product photos keep prints
   flat.
