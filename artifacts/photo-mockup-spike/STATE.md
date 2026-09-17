# Where this stands, 17 September 2026 (evening)

Read this first in a new conversation. Nothing here has touched the live store.

All 13 on-model photos were rebuilt this evening on a different image API. The
whole set in `final-set/` is current and came out of one build.

## What exists

- `colourway-photos/` : the 13 garment photos, one per garment and colour. These
  are what get composited. 11 of the 13 were regenerated on kie.ai this evening;
  `crew_black` is the one survivor of the older pipeline (see Open items).
- `final-set/` : those 13 with the Salt Lake temple composited. All written in
  the same 16-second run, so they all carry the geometry below.
- `bases/` : `base1_*` are the reference photos the colourways were generated
  from. **`base1_tee_darkgray.png` and `base1_hoodie_gray.png` are the new
  Sunburst bases; `base1_crew_gray.png` is still the old one** and is stale as a
  reference, though the crew landmarks measured off it are still correct.
- `kie_client.py` : the kie.ai API client.
- `build_colourways.py` : generates every colourway from its garment's base in
  one parallel batch. This is the script to reuse for a new temple or colour.
- `composite.py` / `composite_set.py` : the warp-and-shade engine and the runner
  that places the print at true physical size. Unchanged today.
- `print_geometry.json` : all placement numbers, in inches.
- `tapstitch-on-model/` : real Tapstitch model photos, for fit comparison.

Cleaned out on 17 Sep 2026 and gone for good: `source-photos/` (JPEG copies of
the superseded old set), the three `base2_*` lifestyle shots, and twelve loose
diagnostic images nothing referenced. The folder went from 127 MB to 94 MB.

## Generating photos: kie.ai GPT Image 2.5 Sunburst

`KIE_API_KEY` lives in the `.env` one level **above** the repo, in the
`1. Peculiar People` folder. `kie_client.py` finds it there; never paste it into
a prompt or a file.

- Endpoint pattern: `POST /api/v1/jobs/createTask`, poll
  `GET /api/v1/jobs/recordInfo?taskId=`. Auth is `Bearer`.
- **Sunburst**, not Flare. Flare is the fast default; Sunburst is the premium
  variant and is visibly more photographic on this subject.
- 2K, 1:1. Costs 10 credits (~$0.05) per image. 2K matches the 2048x2048 the
  compositor expects. 4K exists at 16 credits if ever needed.
- Reference images are passed as **URLs**, not uploads. Tapstitch catalogue
  images are already public URLs. For a local file, get a presigned URL from the
  Higgsfield `media_upload` tool, PUT the bytes with curl, then use the
  cloudfront `url` it returns.
- The CDN that serves results rejects urllib's default user-agent. Download with
  `curl`.

### The two-generation rule, which is the important one

Each colourway is **one** generation from its base, and each base is **one**
generation from the Tapstitch reference photo. Never deeper.

Earlier today colourways were generated from other colourways, stacking three
and four passes deep. The subject drifts: hair goes from photographic to drawn
ringlets, ears change shape. It is not blur, so **sharpness metrics do not catch
it**. Measured edge acutance actually went up while the images got worse.
Judge it by looking at the hair. `genloss_hair.jpg` shows four generations of the
same man side by side.

Two is the floor, not one, because model consistency comes from the chaining.
The Tapstitch photo is Tapstitch's own model, so generating each colourway
straight from it would give thirteen different strangers.

## The sizing chain, which is physical rather than ratio-based

Print files are **300 dpi at final size**. Salt Lake's ink measures
**11.98 x 14.87 in** with the location text **0.70 in** tall, identical on all
three garments.

`px_per_inch = (hem - collar) / length_in`, and art is drawn at
`px_per_inch / 300 * scale_nudge` of file size. `length_in` is the size-guide
Length for the size the model wears; **size L is assumed** and is correct.

Rendered width in garment inches is `11.98 * scale_nudge` and does **not**
depend on px_per_inch. px_per_inch only decides how many pixels that is. So a
wrong landmark changes the apparent size on screen without changing the number
the script prints, which is exactly how the hoodie went wrong this evening.

### Current settings

| | collar | hem | centre | px/in | design | top below collar |
|---|---|---|---|---|---|---|
| tee | 470 | 1637 | 1022 | 41.16 | 11.14 in (x0.93) | 6.2 in |
| crew | 430 | 1830 | 998 | 49.38 | 10.55 in (x0.88) | 6.0 in |
| hoodie | 565 | 1630 | 1020 | 36.56 | 12.70 in (x1.06) | 5.6 in |

All three now sit inside Tapstitch's real back-print range of 5.5 to 6.6 in
below the collar. **The old open item about the photos showing the print higher
than it actually prints is closed.**

## Landmarks: the trap that cost the most time

`collar` is the top of the garment at centre back, `hem` its bottom edge. Both
are measured on the base photo and must be re-measured whenever a base changes.

- **tee**: the top of the ribbed collar band. Visible, easy.
- **crew**: the top of the ribbed collar band. The current marks (430/1830) are
  known to be slightly generous at both ends: roughly 30px high at the collar
  and 30px low at the hem, which inflates the span about 4.5%. `scale_nudge`
  absorbs it. Fixing the marks properly would let the nudge go back toward 1.0.
- **hoodie**: **this one is invisible and it has now gone wrong twice, in
  opposite directions.** The neckline is under the hood. Do not use the top of
  the garment silhouette. That is the top of the *hood*. Measure where the
  hood's outer edges meet the shoulders, which is where the silhouette width
  jumps sharply. On the current base the hood runs from ~390, its edges meet the
  shoulders at **565**, and its point at centre back is at ~720. The print top
  lands at ~770 and clears the hood by about 1.4 in.

  This morning the mark sat 3.2 in *below* the neckline, buried in the hood, and
  the "2.4 in" setting was really 5.6 in. This evening it sat at 400, the top of
  the hood, which inflated the scale 13% and printed the temple over the hood.
  Always check the print's top against the hood's point before shipping.

An automatic gradient detector finds the crew and tee collars reliably. It does
**not** find the hoodie's, and it fails on light garments. Verify by eye with a
labelled ruler crop before trusting a number.

## The fabric rule that works

Two parts, and both matter:

1. The garment drapes like real cloth **everywhere** ,  relaxed folds in the
   sleeves, creasing at the waistband, drape down the outer sides. Asking for a
   uniformly flat garment gives something that reads as cardboard.
2. **Except** the central back panel, which stays flat: the rectangle from just
   below the collar to about two thirds of the way to the hem, across the middle
   two thirds of the width. Every fold is pushed out to the sides, armholes and
   hem. Nothing creases across the middle.

Separately, name the failure to avoid mottling: *no mottling, no cloudiness, no
blotches, no patchiness, no stone-wash, no acid-wash, dyed one consistent colour
edge to edge*. Without that the fleece comes back looking stone-washed. Asking
for "texture" or "gentle undulations" is what produced the blotchy set.

**Exception: heather grey is real.** The crew's Flower Gray is a marl and its
speckle is a property of the garment. Tell it to keep the heather and move only
the folds, or you get a flat solid grey that is not the product.

Sleeves on the hoodie sit between two failure modes. Asked for bunching it makes
stacked rings; asked for smooth it makes an ironed tube. The wording that lands
is: smooth down the arm, then two or three soft relaxed folds easing into the
cuff. And the body is **longer than the sleeves**: cuffs end above the
waistband with the hands visible below. Give it an arms-down reference or it
invents the proportion.

## Colour: name the number

Adjectives overshoot. "Soft pale mauve" landed 30 away from the real swatch,
"muted dusty mauve, mid-tone" landed 58 away in the other direction. What works:

1. **Put the RGB in the prompt.** `true_colors_all.json` holds the measured
   Tapstitch values. Naming the number took the tee grey from 30 away to 4.
2. **Upload a real mockup as a colour reference** for anything stubborn. That
   took the mauve to a distance of 2 in a single pass, after two failed
   description attempts. Say explicitly that the reference is a colour swatch
   only and its print must be ignored, or the graphic leaks into the output.

Current accuracy, distance from the true swatch on a 0-255 scale: nothing is
worse than 21, and eight of thirteen are under 16. The old set had outliers at
41 and 45.

**Do not post-correct colour in software.** It was tried and rejected: it shifts
midtones but not deep shadows or highlights, which compresses the tonal range and
makes the garment look like a recolour. See `hoodie_diagnose.jpg`. Regenerate
instead ,  at 10 credits it is cheaper than the compromise.

## Still true from before

**No masking anywhere.** Every masking approach failed somewhere: hoods left
grey, hems cut mid-garment, colour bleeding into the backdrop, arm gaps painted
as bright slivers, torn edges on low-contrast heather. Generating each colourway
removes the need entirely.

**The fold-follow warp is on at 3.** `composite_set.py --displace`. It shifts the
art along the photo's own luminance gradient. Raising it to 28 was tried and
moves the art only 0.5 to 1.4 px inside the print area, because the gradient is
normalised against the whole image and the garment's silhouette edges dominate.
It is effectively inert at any setting. Making it do real work would mean
normalising within the print area and band-passing out the body's broad
shading, a change to `composite.py`, not a dial.

## Open items

1. **Colour lineup is closed.** The 13 colours are final: 5 tee, 2 crew, 6
   hoodie. Crew Oat Gray (6672) will not be produced, so no black art is
   needed. The **white** print on Flower Gray is final and approved - do not
   revisit it as a contrast problem.
2. **`crew_black` is the last image from the old pipeline.** The Sunburst
   version measured worse (colour 15 from true against 7, mid-panel 2.32
   against 2.05), so the old one was kept deliberately. Revisit only if set
   consistency matters more than those numbers.
3. **`base1_crew_gray.png` is stale** as a reference photo, though the landmarks
   taken from it still hold. Regenerate it if the crew is ever rebuilt.
4. **Second and third temples (Manti, Rome)** ran cleanly through the old
   geometry and confirmed per-temple repeatability. They have not been rerun
   under any of the current numbers.
5. **The crew's landmarks are compensated rather than fixed** (see Landmarks).
6. **Earrings** were a problem on older bases. The current tee and hoodie
   prompts say "no accessories, no jewellery" and the issue has not recurred.

## What the credits cost

kie.ai: 200 credits of 1070, about **$1.00**, for the entire 13-image rebuild
including every retry. The previous pipeline charged 3 credits an image and the
whole day's iteration there came to 84 credits from a 251 balance. Cost is no
longer a reason to accept a colour that is nearly right.
