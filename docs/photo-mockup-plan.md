# On-Model Photo Mockups

**Status:** proven by spike, not built. Evan approved building after the hoodie probe passed.
**Date of spike:** 17 September 2026.
**Artifacts:** `artifacts/photo-mockup-spike/` (prototype script plus every proof image).

## The problem

Product listings show flat mockups of the design. Buyers cannot judge fit or
quality from a flat mockup. Shooting on-model photos per product is impossible:
roughly 95 temples times 3 garments is about 285 products, across 13 garment and
colour combinations.

Evan's first idea was generic fit photos uploaded to every listing with a
disclaimer. The chosen approach is better: composite each temple's real print
file onto a photo of a blank garment, so every listing shows its own temple on a
body, with no disclaimer needed.

## The mechanism

Three pieces of information come off one photo of a blank garment. The art is
never redrawn. Pixels are only moved and shaded, so lettering cannot be mangled
the way a generative model mangles it.

1. **The quad.** Four corners of the print area, marked once per photo.
2. **The fold map.** Photo luminance, blurred. Its *slope* shifts each art pixel
   sideways, so the art bends along the folds instead of sitting flat.
3. **The shading.** A local-over-broad luminance ratio multiplied over the ink.
   This is what makes the ink read as printed *into* the fabric rather than
   pasted on. A light knit-texture pass is added on top.

Prototype: `artifacts/photo-mockup-spike/composite.py`. Pure numpy and Pillow.
No OpenCV or SciPy, because the project venv has neither.

### Settings that worked

| Setting | Value | Notes |
|---|---|---|
| `--displace` | 3.0 | at roughly 2000px render width. Scales with `--upscale`. |
| `--shade-gain` | 1.0 | |
| `--texture-gain` | 0.35 | knit showing through the white ink |
| `--opacity` | 0.93 | near-opaque white, a hint of fabric reads through |
| blur sigmas | broad 22, folds 5, detail 1.6, gradient 7 | all scale with render size |

Render time is under 10 seconds at 2200x2920 on Evan's laptop. The full catalogue
is well under an hour and parallelises.

### Two traps already hit and fixed

- **Pillow cannot Gaussian-blur a float (`mode="F"`) image.** `composite.py`
  ships its own separable blur.
- **Point-sampling a 4386px print file down to a few hundred pixels drops thin
  lines between samples.** `load_art()` LANCZOS-downscales the art to about 3x
  its on-screen size first.

## Where the blank-garment reference photos come from

**Evan's own Shopify listings.** Every live product already carries Tapstitch's
mockups: for the hoodie, 6 back views with the print and 6 blank fronts, at
1400x1400. These show the real oversize boxy cut, hood shape, kangaroo pocket,
drop shoulders, ribbed cuffs and the exact colours. Nothing better exists,
because it is the garment actually shipped.

Pull them with the Shopify `get-product` tool, then `media_import_url` the CDN
URL to get a `media_id`, then pass it to `generate_image` with role
`image_references`.

Parent hoodie product used in the spike:
`gid://shopify/Product/15302513459572` (handle `cloud-temple-hoodie`).

## The Tapstitch public image library

Bigger than expected, and mostly unused. The public catalogue product page carries
a **Download gallery** button. Reached from `urls.catalog_search`
(`https://www.tapstitch.com/collections/all?q={sku}`, sku is the `silSn`) which
links to `https://www.tapstitch.com/custom/{sku-lowercase}-{slug}`. The hoodie is
`https://www.tapstitch.com/custom/r00286-oversize-fleeced-hoodie`.

Files sit on `files.tapstitch.com` and the filename suffix is the whole key:

| Suffix | What it is | Count (hoodie) | Native size | Pull it? |
|---|---|---|---|---|
| `-(n)` | flat lay, blank garment, per colour | 2 per colour | 2048x2731 | **Yes**, as compositing bases |
| `-M-(n)` | on-model, male | 5 | 2048x2731 | Maybe, as compositing bases |
| `-F-(n)` | on-model, female | 5 | 2048x2731 | Maybe, as compositing bases |
| `-D (n)` | **detail / fabric closeups** | 6 | 2048x2731 | **Yes** |

The page serves 1024px thumbnails; the file behind the URL is 2048x2731.

### Replace the flat lays (Evan's decision, 17 Sep 2026)

**This supersedes an earlier call the same day to skip them.** That call assumed
the current mockups were good enough. Evan reports the zoom quality on the live
site is poor, which changes the answer.

The numbers behind it:

- Current Shopify mockups: **1400x1400**.
- Tapstitch catalogue blanks: **2048x2731**. About 2.1x linear, 4.3x the pixels.
- Shopify's zoom wants 2048 or more, so 1400 sits under the threshold. This is a
  real cause of the poor zoom, not a guess.

**Colour coverage is complete.** Verified 17 Sep 2026 by switching the catalogue
colour picker from Navy to Black and watching both lays reload: every one of the
24 colours carries its own front AND back blank flat lay at 2048x2731. All six
colours Peculiar People sells are covered. Filenames are a numbered pair per
colour (Navy is `(25)`/`(26)`, Black is `(29)`/`(30)`), so the numbering is a
lineup, not a contract; match by eye on download.

### What re-creating them actually costs

The two sides are wildly different jobs, and this is the part worth knowing:

**Fronts: 13 composites, total.** `flatten.front_file_path(garment_id, color)` is
keyed per garment per colour and **not per temple**; its own docstring says so,
and `tests/test_tapstitch_placement.py` notes "the front carries only a 6in
logo". The print files already exist at
`artifacts/tapstitch/front-logo/{garment} white front print (auto).png`. So 13
front images serve all 285 products.

**Backs: about 1,235 composites.** 95 temples times 13 garment-and-colour
combinations (6 hoodie, 5 tee, 2 crew). At under 10 seconds each that is roughly
3 hours single-threaded and well under an hour parallelised. One-time backfill,
then 13 per new temple, which is a couple of minutes.

**Aspect ratio improves.** Current mockups are 1400x1400 square. The Tapstitch
lays and the on-model shots are both 3:4 portrait. Moving everything to 3:4 makes
the gallery *more* consistent than it is today, not less.

**All prints are white** (Evan, 17 Sep 2026). No black logo variant is needed for
the light colourways, and `{garment} white front print (auto).png` is the only
front file the job requires.

### Still unknown

Whether the **Download gallery** button grabs every colour or only the selected
one. Not tested.

## What gets replaced, exactly

Per hoodie product today: 12 flat mockups (6 back carrying the temple, 6 front
carrying the logo) plus 1 art closeup, so 13 images.

| Image | Fate |
|---|---|
| 6 back flat mockups | **Replaced** at 2048x2731, same count |
| 6 front flat mockups | **Replaced** at 2048x2731, same count |
| art closeup | Kept. It is a design card, not a mockup |
| on-model composites | **Added** |
| fabric detail shots | **Added** |

So yes: **every flat mockup on the site gets replaced**, not added to.

> **Counts below are superseded by "What each listing will hold".** That layout
> drops the per-colour flat mockups, because the per-colour on-model backs carry
> the colour better. The surviving flat mockups are 1 back (lead colour) and
> 1 front per product: about **285 flat backs** and 3 unique fronts, not 2,470.

**This is a destructive operation on a live store.** It deletes live media and
uploads replacements. It must be per-product and idempotent, it must run one
product first for review before any batch, and `tapstitch_variant_images.py` has
to run after it. Thousands of media calls will also take real time against
Shopify's rate limits, so stage it rather than firing it all at once.

## Guaranteeing exact proportions

Evan's stated priority, and the codebase already treats it as a known failure
mode. From `tapstitch_api.print_areas()`:

> The rectangles are NOT the same across garments, and on the crew not even
> across sides. The tee is 260x327 on both sides; the crew is 210x281 on the back
> and 209x275 on the front. Reusing one garment's numbers on another misplaces
> and misscales the art with no error anywhere.

**The rule: never measure placement by eye. Derive it.**

### The chain of truth that already exists

1. Tapstitch states the print area outright in `craftItemDto.customArea`: every
   side carries a `<side>_side_middle` detail whose x/y/width/height are
   coordinates on a **700x700 canvas**. `tapstitch_api.print_areas()` reads it.
2. `tapstitch_api.placement()` then computes exactly how a print file sits inside
   that area: contain-fit with the minor dimension truncated, scale is the print
   area's height over the box height, positioned on the area's **centre**, not
   its corner.

So for a flat lay the only unknown is **where that 700x700 canvas sits on the
photo**. Solve it once per garment per side and every temple lands exactly right,
forever, with no per-temple judgement at all.

### Solving it without eyeballing

Take an existing Tapstitch mockup, whose placement is correct by construction,
and the blank flat lay of the same colour. Align the two garment silhouettes.
They are near-certainly the same base render with the print applied, so they
should align to within a pixel or two. The known ink position in the mockup then
pins the canvas onto the blank.

**If the silhouettes do not align, that is the warning, and the run stops.**

### The check that makes it safe

After compositing, re-measure the ink bbox on the output and compare it against
the bbox `placement()` predicts. Agreement within a tight tolerance, starting at
0.5% of garment width. Anything outside is held, not published. Same gate
philosophy as `tapstitch_preview.py`, and it catches silhouette misalignment for
free.

### The honest asymmetry

**Flat mockups can be pixel-exact**, because a correct Tapstitch mockup of the
same garment exists to calibrate against. They should be held to that standard.

**AI-generated on-model photos cannot.** There is no ground truth: the garment in
the photo is a different render of a different body. What is achievable there is
*proportional consistency with the real garment*, derived from ratios measured
off the real mockups, then reviewed on a proof sheet.

The shoulder-to-hem fractions recorded earlier in this document (0.190, 0.751,
0.561, 0.518) belong to that second category. **They were derived by eye during
the spike and must not be used for flat mockups**, where the exact route above
applies instead.

### Fabric closeups: the one catch

All six `-D-` shots for the hoodie are the **same mauve garment**. They show hood
construction, cuffs, seams and one pure fabric weave macro. Putting them
unchanged on the Black hoodie listing shows mauve fabric.

Three ways to handle it, in preference order:

1. **Caption and place last.** Alt text naming the colourway ("350gsm fleece,
   shown in Mauve"), sitting at the end of the gallery. Their job is to show weave
   and construction, not colour, and buyers read a detail shot that way. Cheapest
   and honest.
2. **Recolour for the dark colourways.** These are flat, evenly lit, single-colour
   surfaces with no background, so a hue and luminance shift is far easier here
   than on a full garment photo. Mauve to black, navy, coffee is workable. Mauve to
   gray is a luminance climb and will look muddy.
3. **Skip the ones that read as strongly coloured** and keep only the weave macro.

#### The third catch: the crew's shots are a colour the crew is not sold in

The crew's three `-D-` shots are a coffee garment. The crew ships in Flower Gray
and Black only, so option 1 above ("caption and place last") was doing more work
than the caption admitted. As of 18 Sep 2026 they also carry a stamped notice,
`*Pictured color not currently sold`, in black on a band in the backdrop gray.
Driven by a `_notice` key in that garment's `captions.json`.

#### The second catch, found 18 Sep 2026: backdrop and shape

The list above only ever considered colour. Once the Salt Lake galleries were
live it was obvious that the `-D-` shots differ from everything around them in
two more ways: they arrive on **pure white** while the on-model shots sit on a
light gray studio backdrop, and they arrive at **2048x2731** while everything
else is square. Scrolling the gallery, they flash white and break the grid.

Both are fixed at upload by `artifacts/photo-mockup-spike/normalize.py`. Three
of the nine shots are full-bleed fabric macros with no background at all and are
only cropped; the other six are cutouts on white and get the backdrop replaced.
See STATE.md for the mechanism and the reason the fill has to be region-based.

### Real versus AI on-model shots: the actual split

Counted 17 Sep 2026 by loading every on-model file for all three garments and
classifying the angle. **Only a back view is usable as a compositing base**,
because the print is on the back.

Colours sold, from the Shopify product options:

- **tee** (5): Black, Maroon, Navy Blue, Coffee, Dark Gray
- **crew** (2): Gray, Black
- **hoodie** (6): Navy Blue, Gray, Black, Coffee, Mauve, Royal Blue

| Garment | Colours sold | Tapstitch back on-model | Quality | AI needed |
|---|---|---|---|---|
| tee | 5 | **2**: Navy (M set, 4 variants), Coffee (F set, 2) | Square-on, arms down. Ideal. | 3 |
| crew | 2 | **0**. Only one on-model shot exists and it is a cropped front view | n/a | 2 |
| hoodie | 6 | **2**: Black (`M-(5)`), Mauve (`F-(5)`) | Three-quarter rear, raised arm crossing the back | 4 |
| **Total** | **13** | **4** | | **9** |

**So 4 of 13 from Tapstitch, 9 from AI.** If the hoodie's three-quarter shots are
rejected as heroes, which is a live risk given the raised arm, it becomes 2 real
and 11 AI.

Notes that matter:

- The tee set is newer (`v1783042839`) and far better organised than the
  hoodie's (`v1769156471`), with descriptive filenames like
  `RT0063-M-back-gallery-featured-back-standard-2.jpg`. The hoodie and crew use
  the older bare-numbered convention.
- Each model set is shot in **one colour only**. The M set and the F set are
  different colours, which is why coverage is 2 per garment at best and never
  more.
- The tee's four M back variants are all the same navy, different crops and
  stances, not different colourways.
- The F tee colour reads as Coffee but was judged by eye. Confirm against the
  real swatch before relying on it.

### Two different image sets, easily confused

The phrase "flat lay" got overloaded in discussion. To be unambiguous:

- **Flat mockups** (the garment alone, no person) **stay.** They get replaced at
  2048x2731. They are *already* uniform, because Tapstitch renders every
  colourway from the same base, so switching colour never changes the pose.
  Nothing to solve here, and nothing is being eliminated.
- **On-model photos** are the new addition, and they are the only set the
  uniformity question touches.

### How many different models

The moment that matters is narrow: **clicking a colour swatch on one product
page.** That is the only place a changing person reads as confusing, because the
shopper is comparing colours and the human underneath keeps moving. Everywhere
else variety is fine, and usually better.

| Scope | Rule | Why |
|---|---|---|
| Within one product's colour set | **One person, recoloured** | This is the swatch-click moment. Non-negotiable. |
| Across the three garments | **Different people, deliberately** | One base per garment already gives three, at no extra cost. |
| Extra lifestyle slots | As many as wanted | Outside the colour set, so nothing has to match. |

**What has to match is the studio, not the face.** Same framing, lighting,
background and crop. Different people in one consistent setup reads as a
deliberate lookbook; the same person across inconsistent setups reads as sloppy.
That is the real constraint, and it is a prompt-level decision.

### Uniformity kills the mixed-source plan (Evan's call, 17 Sep 2026)

**Requirement:** the per-colour on-model set has to look uniform. A shopper
clicking Black to Navy must not see a different person, a different pose or
different lighting.

That rules out using Tapstitch photos for the 4 covered colours and AI for the
other 9. It also rules out generating each colour separately: six AI generations
of "the same" person will not match each other's pose and lighting any better
than mixing sources would.

**The uniform method is one base photo per garment, recoloured to every colour.**
Same person, same pose, same light, by construction, because it is literally the
same photograph.

### Recolouring is proven against ground truth

Tested 17 Sep 2026. The hoodie's Gray back mockup was recoloured to the other
five colourways and compared against the real Tapstitch render of each.
**Navy, Black, Coffee, Mauve and Royal Blue all came out essentially
indistinguishable from the real thing.** See
`artifacts/photo-mockup-spike/recolour_vs_real.jpg`.

The target colours are not guessed. They are sampled as the median fabric
luminance from the real mockups, the white print excluded:

| Colour | Median RGB | Luminance |
|---|---|---|
| Black | 24, 24, 24 | 24 |
| Navy Blue | 38, 54, 69 | 54 |
| Coffee | 87, 64, 42 | 64 |
| Gray | 110, 113, 104 | 109 |
| Royal Blue | 55, 79, 192 | 109 |
| Mauve | 196, 163, 171 | 177 |

Stored at `artifacts/photo-mockup-spike/true_colors.json`.

**Base colour is load-bearing.** Recolouring *down* in luminance is clean;
recolouring far *up* mottles the fabric grain and washes out the print. Driving
the same test from the Black base (L24) produced good Navy and Coffee but visibly
degraded Gray, Royal Blue and Mauve. See
`artifacts/photo-mockup-spike/recolour_strip.jpg`.

**Rule: generate each garment's base in the lightest colourway that garment
offers**, then recolour downward. Hoodie base is Gray (L109). The tee's colours
are all dark, so its base is Dark Gray and every target is below it. Crew base is
Gray. Sample the tee and crew true colours the same way before building.

### This collapses the generation count

One base photo per garment, not one per garment-and-colour:

| | Was | Now |
|---|---|---|
| AI base photos | 9 to 13 | **3** |
| Credits, back views | ~60 | **~15 to 20** |

The Tapstitch on-model shots are then **not** part of the per-colour set at all.
They become standalone lifestyle images, placed where uniformity is not expected,
or dropped.

### Revised generation budget

Back views are the hero and the whole point, so they drive the budget:

| Line | Credits |
|---|---|
| 9 AI back blanks, 1.5 tries at high/2k | ~40 |
| Casting and exploration at low/1k | ~20 |
| **Back views only** | **~60** |
| Optional AI front views for the 9 uncovered colours | ~40 |

That is down from the earlier 110 to 150 estimate, because 4 combinations no
longer need generating at all.

### The find that may change the plan

`-M-(5)` and `-F-(5)` are **three-quarter rear views of real models** wearing the
blank garment, at 2048x2731, in black and mauve. Real people, real garment, real
photographs, already owned and offered for seller use.

The compositor maps the print through a homography quad, so a three-quarter view
is not a problem; that is what the quad is for. This means **the AI-generated
blanks may be reducible or unnecessary for some shots.**

Limits before treating this as a replacement:

- One or two colourways per garment, not all six.
- Three-quarter rear, not square-on, so the print is foreshortened and reads less
  clearly than a straight back view would as a hero image.
- Poses have raised arms, which is exactly the occlusion case that has no code yet.
- Confirm Tapstitch's terms of use. The Download gallery button exists so sellers
  can use these, but it has not been read.

## What each listing will hold

Two AI bases per garment (Evan, 17 Sep 2026). Base 1 carries the colour set.
Base 2 is a second person used for the lifestyle slot.

**Base colour is not lead colour.** The base is a production choice, always the
lightest colourway so recolouring runs downward. The lead is what the storefront
shows first.

| Garment | Colours | Recolour base | Lead colour |
|---|---|---|---|
| tee | 5 | Dark Gray | Black |
| crew | 2 | Gray | Gray |
| hoodie | 6 | Gray | Navy Blue |

### The gallery, in order

N is the number of colours that garment comes in.

**Reordered 18 Sep 2026, per Evan.** The flat lays now lead and the on-model run
follows the design card. Slot 1 is what Shopify features, so the flat back lay is
the collection-page and search thumbnail: it shows the temple bigger and flatter
than a worn shot, which is what survives being shrunk to a grid cell.

| Slot | Image | Count | Size | Backdrop | Source |
|---|---|---|---|---|---|
| 1 | **Flat back mockup, flat colour** | 1 | 1400² | gray | Tapstitch blank + temple, refaced. **The thumbnail.** |
| 2 | Flat front mockup with chest logo | 1 | 1400² | gray | Tapstitch blank + the 6in chest logo |
| 3 | Temple art closeup | 1 | 2048² | **white** | Existing `art_images.py` card, unchanged |
| 4... | On-model back, every colour | N | 2048² | gray | Base 1, recoloured, temple composited. Lead first, each binds to its variant. |
| last | Fabric and construction details | 3 | 2048² | gray | Tapstitch `-D-` shots, cropped square, captioned with the colourway |

The lifestyle shot that used to hold slot 4 is still not built, and the new order
no longer reserves a gap for it.

**Flat lay colour is independent of the lead colour.** `FLAT` in
`build_product_gallery.py`: crew Black, because its lead Flower Gray is a light
heather that will not separate from a light gray backdrop; tee Maroon, chosen on
how it reads as a thumbnail; hoodie defaults to its lead, Navy Blue. Changing one
means the old flat lays must be replaced, and `--prune` now drops a flat lay in a
retired colour even though it carries alt text.

**Every slot is 1:1 and every slot is on the garment's own light gray, with one
deliberate exception: the temple art closeup at slot 3 stays on white** so the
design reads clearly. That is Evan's call of 18 Sep 2026, made knowing its
neighbours had moved to gray.

The flats stay at their native 1400x1400 rather than being upscaled to match.
The aspect ratio is what the gallery grid cares about, Shopify scales for
display, and upscaling would soften real detail to no benefit. If they ever look
soft next to the 2048 images the fix is to re-pull them from Tapstitch at a
higher resolution, not to interpolate what we have.

### Totals, and the gallery does not grow

| Garment | Colours | Images now | Images today |
|---|---|---|---|
| tee | 5 | 12 | 11 |
| crew | 2 | 9 | 5 |
| hoodie | 6 | 13 | 13 |

The hoodie lands exactly where it is today. What changes is the mix: the
per-colour *flat* backs and fronts are dropped, because the per-colour
**on-model** backs now carry the colour information and carry it better. One flat
back and one flat front survive as clean reference views.

> **This changes what the variant binds to.** Today
> `tapstitch_variant_images.py` binds each colour variant to its flat back
> mockup. Under this layout each variant binds to its **on-model back** instead.
> That target has to change in the script, and swatch-click behaviour must be
> retested on one product before any batch.

### Per temple versus shared

| Scope | Images | Hoodie count |
|---|---|---|
| **Unique per temple** | On-model backs (N), flat back, lifestyle, art closeup | 9 |
| **Shared across all temples** | Flat front, 3 fabric details | 4 |

Across the catalogue that is about **2,090 per-temple composites** (9 hoodie,
8 tee, 5 crew, times 95 temples). Roughly 5 hours single-threaded, well under two
parallelised. After the backfill, about 22 composites per new temple.

### Generation cost for six bases

| Line | Credits |
|---|---|
| 6 bases (2 per garment) at high/2k, 1.5 tries | ~27 |
| Casting and exploration at low/1k | ~20 |
| **Total** | **~47** |

## Gallery composition

Adding images changes the gallery, and the gallery already has a load-bearing rule.

### The ordering rule that already exists

From `config/tapstitch.json`, `post_publish._set_variant_back_images_note`:
Shopify binds each variant to the FIRST image of its colour **at import**, and
Tapstitch sends fronts first, so every variant lands on a near-blank garment.
Posting back-first fixes the gallery but not the binding.
**`scripts/tapstitch_variant_images.py` must run after every publish, and now
after every image addition too.** It is idempotent.

Adding on-model and fabric images **post-publish**, the way `art_images.py`
already does, sidesteps import-time binding entirely. Run the rebind last anyway.

#### "No alt text means it is a flat mockup" no longer holds

That convention is what `build_product_gallery.py`'s pixel classifier was built
on, and as of 18 Sep 2026 it is only true of flats Tapstitch has just published.
Once a flat has been refaced onto the gray it is re-uploaded with deterministic
alt text, so it stops being invisible to that rule. Slots 2 and last are now
found by alt first and only fall back to the classifier. The classifier is a tool
for identifying Tapstitch's unlabelled uploads, not the source of truth for
gallery position.

### The implementation precedent

`scripts/art_images.py` is the pattern to copy exactly. It:

- finds each product on Shopify by exact title (presence there means Evan
  published it),
- recognises an already-attached image by an **alt-text marker**
  (`ALT_MARKER = "Temple line art close-up"`) so re-runs are idempotent,
- uploads and moves the image to **gallery position 2**,
- reports unpublished products as waiting.

Fabric closeups need their own alt marker, and differ in one way that makes them
simpler: they are **per garment, not per temple**, so the same handful of files
is reused across every product of that garment. No per-temple rendering step.

### Proposed order

1. On-model back, lead colour (the composited hero)
2. Temple line art closeup (existing, currently position 2)
3. Flat back mockup, lead colour
4. On-model back, remaining colours
5. Flat back mockups, remaining colours
6. Flat front mockups
7. Fabric and construction details

### Watch the gallery length

A hoodie product carries 13 images today: 12 Tapstitch mockups plus the art
closeup. Add 6 on-model and 4 fabric details and it becomes 23. That is a long
gallery and it buries the good images. Curating down, most likely by dropping
most of the flat front mockups, is a decision to make before pushing, not after.

## Calibrating print placement from Tapstitch's own renders

The back mockups carry Tapstitch's true print placement, so the print rectangle
can be measured rather than eyeballed.

> **These numbers are for the on-model photos only.** They were derived by eye
> during the spike. For flat mockups the exact 700x700 canvas route applies
> instead: see "Guaranteeing exact proportions" above.

Measured on the dark hoodie colorways (navy, black, coffee agree to within
0.002; light colorways need a different threshold and were not used):

| Quantity | Value |
|---|---|
| ink width | 0.248 of garment bbox width |
| ink top | 0.408 of garment bbox height |
| ink bottom | 0.818 of garment bbox height |
| ink centre x | 0.494 (dead centre) |

**Do not transfer those fractions straight to a worn photo.** A flat lay spreads
the hood out above the shoulders; a worn hood collapses behind the neck, so
garment-bbox height means something different in each. Re-anchor on
shoulder-line-to-hem, which is stable in both.

Flat lay landmarks (hoodie, `m02.png`, black back): shoulder line y approx 460
(where silhouette width jumps as the sleeves begin), hem y 1219, body width
approx 600, shoulder-to-hem 759.

Transferable fractions derived from those:

| Quantity | Value |
|---|---|
| ink top | 0.190 of shoulder-to-hem |
| ink bottom | 0.751 of shoulder-to-hem |
| ink height | 0.561 of shoulder-to-hem |
| ink width | 0.518 of body width |

**Trust the print file for aspect ratio, not the mockup measurement.** The
threshold used on the mockup misses faint outer strokes and understates width.
Tee and hoodie print files both carry the same 3595x4461 ink block, aspect
0.8059.

### Measuring silhouettes: one trap

White print is the same colour as the white mockup background, so a
"dark equals garment" mask punches the print out as a hole, and eroding then
eats the print region. Fill the silhouette first (row-span and column-span fill,
intersected), *then* erode, *then* look for ink.

## Print file reference

| Garment | Canvas | Ink bbox | Ink size |
|---|---|---|---|
| tee | 4386x5516 | x 396..3991, y 527..4988 | 3595x4461 |
| crew | 4122x5514 | not measured | |
| hoodie | 4134x5540 | x 270..3865, y 539..5000 | 3595x4461 |

All RGBA, pure white ink (255,255,255) on transparent. Built by `flatten.py` as
`{Temple} {garment} white back print (auto).png`. **Prints are back only.**

## Catalogue maths

13 garment and colour combinations, from `config/tapstitch.json`:

- **tee** 5 colours: 8079, 8088, 8084, 8085, 8081
- **crew** 2 colours: 5720 Black, 6551 Flower Gray
- **hoodie** 6 colours: 6674 Navy, 5720 Black, 6645 Gray, 6657 Coffee,
  6650 Mauve, 6654 Royal Blue

Two views each (back is the hero since the print is on the back, front shows the
fit) is 26 photos total. **Per-temple generation cost is zero.** All 285 products
draw from those same 26 photos. Temple number 96 costs nothing.

## Credit budget

Real numbers, checked 17 September 2026. Balance was 251.25 before the spike and
245.25 after, on the Ultimate plan.

| Model / setting | Credits |
|---|---|
| `gpt_image_2_5` quality low, 1k | 1 |
| `gpt_image_2_5` quality high, 2k | 3 |
| `soul_2` | 0.12 exact |

`gpt_image_2_5` defaults to quality `low` and resolution `1k`. **Set both
explicitly** or you get an 880px image, which is too small for a listing.

Observed hit rate on the hoodie was 2 keepers from 2 tries at high/2k with a
reference image. Budgeting 1.5 tries to be safe:

| Stage | Credits |
|---|---|
| exploration and casting at low/1k | ~30 |
| 26 finals at high/2k, 1.5 tries | ~78 to 117 |
| **Total** | **~110 to 150** |

Ways to spend less: iterate at 1k and only re-render keepers at 2k; try `soul_2`
at 0.12 credits for shots where cut fidelity matters less; recolour dark
neighbours in software instead of regenerating (navy, black, coffee and mauve are
close enough, gray and flower gray are not).

Spike spend was 7 credits total: 1 tee photo at low/1k, 2 hoodie photos at
high/2k.

## The prompt recipe that worked

Reference image attached with role `image_references`, aspect `3:4`,
quality `high`, resolution `2k`, count 2.

> Photorealistic apparel catalog photograph shot from directly behind. A young
> adult stands upright, seen from the back, wearing the exact hoodie shown in the
> reference image: the same oversized boxy cut, the same drop shoulders, the same
> roomy sleeves with ribbed cuffs, the same hood shape and proportions, and the
> same black color and heavyweight fleece fabric. The back of the hoodie is
> completely blank, with absolutely no print, graphic, logo, lettering or
> decoration of any kind anywhere on it. Hood down, resting naturally against the
> upper back. Shoulders square to the camera, arms relaxed down at the sides, calm
> upright posture. Framed from the top of the head down to mid-thigh. Soft even
> studio lighting from the front left, producing gentle relaxed fabric folds
> across the back and visible heavyweight fleece texture. Light neutral gray
> seamless studio backdrop. Sharp focus, true-to-life color, no stylization.

Load-bearing parts: naming the reference explicitly ("the exact hoodie shown in
the reference image") and listing the cut features one by one; the triple-negative
on any print; the calm square pose; the single soft light direction. **A relaxed
back with gentle folds is a prompt-level decision, and it is what keeps the warp
small and the location text crisp.**

## What the spike proved

- **Location text survives.** Letterforms are pixel-identical before and after
  the warp. Only the light across them changes. See `cmp_text_zoom.jpg`.
- **The failure mode is gentle.** The warp dial pushed to more than 4x the
  shipping setting makes the temple wavier and more contrasty, not broken. There
  is no cliff. See `cmp_dial.jpg`.
- **The hoodie is fine.** Hood shadow was the main worry and turned out to be a
  non-issue. Zero retries.

## What the spike did not prove

- Only tee and hoodie, only black, only white ink.
- **Light garments untested**: gray and mauve hoodie, flower gray crew. Both the
  ink contrast and the silhouette detection need rechecking there.
- **Crew untested entirely.**
- **Occlusion masking not built.** No arm or hair crossed the print area in
  either test pose. The outline step exists in the design but has no code.
- **Model consistency not solved.** 13 separate generations gives 13 different
  strangers. The image tool's Soul feature locks one person across shots and has
  not been tested.

## Build plan

1. Cast reusable people via Soul so the same faces carry the catalogue.
2. Pull Tapstitch blank references off the live Shopify products.
3. Generate back and front views for all 13 garment and colour combinations.
4. Mark the print quad per photo, roughly 5 minutes each, into a config file.
5. `photo_mockup.py` beside `flatten.py`, reading the existing flattened print
   file per temple.
6. Proof sheet and gate before upload, matching `tapstitch_preview.py`.
7. Push through the existing Shopify media code, pinned to the right colour
   variant, as `tapstitch_variant_images.rebind` already does.

## Open decisions

- **Disclosure.** The garment cut is matched to the real blank and the design is
  the real print file, so these are accurate product images on the same footing
  as any rendered mockup. The *people*, however, are AI. Brand call, not a legal
  one. Not yet decided.
- **One model or two.** Two roughly doubles the generation budget.
- **Whether these replace the flat Tapstitch mockups as the hero image, or sit
  after them in the gallery.**
