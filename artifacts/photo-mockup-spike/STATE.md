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
- `normalize.py` : puts every gallery image on the garment's gray and crops it to
  1:1. Read the section below before changing a threshold in it.
- `backdrop_grays.json` : the measured per-garment backdrop gray.
- `flat-originals/` : the white Tapstitch flats as downloaded, archived before
  anything deletes them from Shopify.
- `tapstitch-on-model/` : real Tapstitch model photos, for fit comparison.

Cleaned out on 17 Sep 2026 and gone for good: `source-photos/` (JPEG copies of
the superseded old set), the three `base2_*` lifestyle shots, and twelve loose
diagnostic images nothing referenced. The folder went from 127 MB to 94 MB.

## One backdrop, one shape (18 September 2026)

Evan's call after seeing the three Salt Lake galleries side by side: every image
in a gallery sits on the same light gray and every image is 1:1. The on-model
shots already were. Tapstitch's flat lays and the `-D-` fabric close-ups arrived
on pure white, and the close-ups arrived at 2048x2731. `normalize.py` fixes both
at upload, so this is pipeline behaviour rather than a Salt Lake touch-up.

**The temple art closeup in slot 3 stays white.** Deliberate, so the design reads
clearly. Nothing is ever pointed at it.

### The gray is measured, not hardcoded

`backdrop_gray(garment)` reads the left and right margin strips of that garment's
own `final-set/` shots, trims the darkest and lightest 5% and takes the mean.
Currently hoodie `#C6C6C8`, tee `#C1C1C5`, crew `#BDBDC2`; cached in
`backdrop_grays.json`, re-measured with `--grays`.

Per garment, not one value for the set. The crew sits about 10 levels darker
than the hoodie because `crew_black` came off the older pipeline, and Evan's
instruction was that the crew's flats match the crew's own shots. Measuring makes
that fall out rather than being a special case, and a new garment needs no new
constant. A product page is then internally consistent, which is the only
comparison anyone actually makes.

Flat fill, not a synthesized gradient. The real backdrop falls from about
`#C8C7CB` at the top to `#BABABD` at the bottom, but the flat lays are overhead
shots and a studio wall falloff painted onto one reads as a mistake.

### The fill has to be region-based. This is the important one.

The flat BACK mockups carry the temple printed in near-white ink INSIDE the
garment silhouette. A colour key on "white" punches holes through the artwork and
shows gray through the temple. Measured on the hoodie flats: 7,800 to 9,400
pixels per image are print, not background.

So only white **connected to the frame border** is background. Seeds are strict
white on the four edges; anything enclosed by garment is never reached. Verified
per image by `--selftest`, which counts the enclosed near-white before and after
and fails if any of it was eaten.

### Two thresholds, because the sources are JPEG

Seed at 250, grow through 228. Right beside a dark cutout edge the backdrop
carries JPEG ringing down to about 228, and a single strict mask leaves a one to
two pixel necklace of not-quite-white pixels sitting on the new gray.

Solving those as partial coverage makes it worse rather than better: the linear
model reads a ringing 246 as 96% background and carries the missing nine levels
through, which measured as a rim **7 to 17 levels darker** than the backdrop.
Growing the fill through 228 absorbs the ringing into the backdrop proper, where
it resolves to exactly the target. It removes about 80% of the rim and grows the
background by 0.02 to 0.06%, which is the ringing and nothing else. The palest
garment edge ring in the live set is 214 (crew Flower Gray), so 228 clears real
fabric by 14 levels, and a leak would need a connected path of 228+ pixels
running from the frame edge into the garment.

### The edge identity, and why there is no halo

An antialiased edge pixel is the garment colour C over the white backdrop,
`P = (1-b)*C + b*255`. Replacing white with gray G wants `(1-b)*C + b*G`, which
rearranges to

    out = P + b*(G - 255)

so only b is needed and **C never has to be known**, which means it can never be
reconstructed wrongly. b comes from the local garment darkness: the darkest
confidently-garment pixel within a few px sets the scale.

**The band must have no brightness floor.** An earlier cut excluded band pixels
below 200 as "definitely garment". A pixel that is 20% backdrop over a black
garment reads about 60, so it was excluded, and its backdrop fifth stayed WHITE
against a gray surround: a one-pixel light fringe, exactly the halo this exists
to prevent. The band is held to 2px instead, because real antialiasing is one to
two pixels and a wider band risks reading a specular highlight as coverage.

Profile across a black flat's edge, before and after, target 198:

    before   255  255  255  255  243   60    9   22   21
    after    198  198  198  198  198   47    8   22   21

Monotonic into the garment, no overshoot, no undershoot.

### The crop is a pixel slice

`square_crop` takes a window of `min(w, h)` centred on the **content** bbox, not
the frame, clamped to the frame. No resampling, no upscaling, ever.

Centring on content matters. A plain centre crop of a 2048x2731 close-up takes
341px off the top and clips the point of the hood. Centring on content takes 0 to
152px and only off a garment that already bleeds past the frame edge. Two of the
nine are fully contained, three are full-bleed macros, and the rest lose under 7%
of content height symmetrically.

`tee/D1` is the one clamped case: its subject sits in the bottom 1,646px, so it
ends bottom-flush with gray above. The rule is still right, it is the only crop
that keeps all the content, but it is the one frame where a hand-picked offset
might compose better.

### A garment can key perfectly and still be invisible

Found on the crew, and it is a separate failure from the one below. Flower Gray
is the one garment whose flat lay sits at almost exactly its own backdrop
brightness: body RGB 183 against a backdrop of 189, **seven levels apart**. The
key worked fine; the sweatshirt simply melted into the background and lost its
sleeves and hem. The hoodie (navy, 63) and the tee (black, 42) each had over 135
levels of separation, which is why neither showed it.

The pale-garment guard did NOT catch this. It reported an edge ring of 214
against a limit of 214 and passed, because it asks whether the key would EAT the
garment, which is a different question from whether the result is legible.

`separated_gray()` is the answer: if the garment body sits under
`MIN_SEPARATION` (20) from its backdrop, the backdrop is darkened until it does
not. Only ever darkened, because lightening moves back toward the white this
whole change is getting away from, and never past `SEPARATION_FLOOR` (140).

Applied to the flats only, via `for_upload(..., separate=True)`. The fabric
close-ups have not needed it; the crew's are coffee against a 189 backdrop.

**Both flats of a product share one gray.** The crew's back and front measure a
few levels apart and solving each independently put them on two different grays.
`build_product_gallery.py --reface` takes the darkest answer across the pair.

**Nothing currently triggers it, and that is the better fix.** Darkening the
crew's backdrop to 158 worked but left a visible step between slot 1 and slot 2.
Evan's answer was to change the subject instead: the crew's flat lays now show
**Black**, not Flower Gray. A black flat separates by 157 and 183, so it sits on
the crew's own `#BDBDC2` like everything else and the step is gone. The rule
stays in place as the guard for the next pale garment.

### Which colourway the flats show

`FLAT` in `build_product_gallery.py`, defaulting to `LEAD[garment]`. The crew is
the one override: lead Flower Gray for the hero on-model shot at slot 1, Black
for the two flat lays. Evan, 18 Sep 2026.

The crew's Black flats had been pruned off that product in an earlier session, so
there was nothing live to pull. `--reface` therefore takes its source from the
live product if it is there and from `flat-originals/` if it is not, and fails
loudly naming both if neither has it. This is the second time the archive has
been the only surviving copy; keep it tracked.

### Stamping a notice on detail shots

The crew's `-D-` shots are a coffee garment, which the crew is not sold in. A
`_notice` key in that garment's `captions.json` gets stamped across the bottom of
every detail shot for it. Keys beginning with `_` are directives, not images, and
both upload paths filter them out.

Currently: `"*Pictured color not currently sold"` on the crew only.

Black text on a band in the garment's backdrop gray, not straight onto the photo.
The bottom strip of crew/D1 and crew/D2 is tan fleece at luma 109 and 124, where
black text does not read; only crew/D3 happens to end on the backdrop. The band
keeps the text black as asked and legible on all three, and it is drawn after the
crop so it can never be cropped off.

### Pale garments will break this, and the guard says so

The technique needs the garment to be far from white. The guard measures the 99th
percentile of the ring 2 to 6px **inside** the backdrop boundary, which is the
only population that can be wrongly swallowed, and raises above 214. A whole-
garment median is the wrong statistic: a dark garment with a blown highlight at
its edge is the risky case and a median hides it.

A white, oat or cream colourway will trip this, and that is the intent. Render
that colourway on a non-white backdrop rather than lowering the number.

### PNG out, not JPEG

The close-ups arrive as JPEG. Re-encoding after a recolour stacks a second lossy
generation on an image whose whole point is that it lost no quality. Shopify
re-encodes to WebP for delivery, so the bigger upload costs nothing.

Normalized files are derived at upload and never committed: they are a pure
function of tracked inputs plus `backdrop_grays.json`, and changing a gray would
strand every one of them.

### Where it is wired in

- `normalize.py` : the module. `--selftest` proves it on all 20 local images,
  `--contact-sheet DIR` writes before/after sheets and a 400% edge zoom.
- `scripts/build_product_gallery.py` : `--add` normalizes fabric details on the
  way up. New `--reface` stage pulls the live flats down, recolours them and
  re-uploads them, and replaces any fabric detail still in the old tall shape.
- `scripts/upload_fabric_details.py` : same hook. It also now reads
  `captions.json` instead of its own hardcoded list, which only covered the
  hoodie and disagreed with `build_product_gallery.py` about the other two.

### Two traps in the Shopify half

1. **Archive the original before pruning.** `--reface` writes every downloaded
   flat to `flat-originals/` first. `.flatcache/` is gitignored as a
   self-regenerating cache, and it will NOT regenerate once `--prune` has deleted
   the source from Shopify.
2. **"No alt text means it is a flat mockup" stopped being true.** A refaced flat
   carries deterministic alt text, so it leaves the classifier's view. Slots 2
   and last are now found by alt first, with the classifier as fallback; relying
   on the classifier alone would have silently rebuilt the gallery with slot 2
   and the last slot missing. `--prune`'s drop set is also wider now, since a
   superseded white flat joins it, so the variant-binding guard is the only thing
   between a re-run and a blanked variant.

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
