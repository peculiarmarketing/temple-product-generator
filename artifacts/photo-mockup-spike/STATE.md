# Where this stands, 17 September 2026

Read this first in a new conversation. Nothing here has touched the live store.

## What exists

- `bases/` : 6 base photos, 2048x2048. Base 1 per garment drives the colour set,
  base 2 is a second person for the lifestyle slot.
- `colourway-photos/` : 13 photos, one per garment and colour. Generated, NOT
  recoloured. Each is the base photo fed back in as a reference, asking only for
  a colour change and a slight pose shift.
- `final-set/` : those 13 with the Salt Lake temple composited.
- `composite.py` : the warp and shading engine.
- `composite_set.py` : places the print at true physical size.
- `print_geometry.json` : all placement numbers, in inches.
- `tapstitch-on-model/` : 10 real Tapstitch model photos, for fit comparison.

## The sizing chain, which is now physical rather than ratio-based

Print files are **300 dpi at final size**. Salt Lake's ink measures
**11.98 x 14.87 in** with the location text **0.70 in** tall, identical on all
three garments. That was always correct in the files.

`px_per_inch = (hem - collar) / length_in`, and art is drawn at
`px_per_inch / 300` of file size. `length_in` is the size-guide Length, collar
to hem, for the size the model wears. **Size L is assumed.**

The earlier method scaled from ratios measured on a flat mockup and rendered the
temple 0.9% too wide on the tee, 6.9% on the crew and 9.1% on the hoodie. Evan
caught all three by eye. Ratios do not survive the move from a flat lay to a
worn garment; inches do.

## Two things deliberately NOT done

**Hoodie carries a scale_nudge of 1.06 and sits 2.4in below the collar**, on
Evan's instruction of 17 Sep 2026 (a teeny bit bigger, a tiny bit up). That
renders the hoodie temple at 12.70in rather than the true 11.98in, so the nudge
is a visible per-garment number in `print_geometry.json` rather than something
hidden in the maths. If a garment always needs a nudge, suspect `length_in`:
the hoodie reads 35.0 px/in against the tee's 44.1, which hints its model is not
wearing the assumed size L.

**No colour correction.** Three hoodies were post-corrected onto their exact
sampled colours and it made them look like recolours: the correction shifts
midtones but not deep shadows or highlights, which compresses the tonal range.
See `hoodie_diagnose.jpg`, corrected top row against untouched bottom row. The
uncorrected colours sit 29 to 40 away from the real garment on a 0-255 scale,
which is worth far less than the shading it cost. To close that gap, regenerate
those three with a better colour description rather than post-processing.

**No masking anywhere.** Every masking approach failed somewhere: hoods left
grey, hems cut mid-garment, colour bleeding into the backdrop, arm gaps painted
as bright slivers, torn edges on low-contrast heather. Generating each colourway
removed the need entirely.

## Open items

1. **Black crew: RESOLVED.** The cause was mine: I had the wrong crew base
   installed. Job `7da9d75b` was in `bases/`, while the correct looser base was
   `16bd6b6d`, which I had generated and then parked when Evan said to change
   only the hoodie. Both the base and the black regeneration now use
   `16bd6b6d`. Chest widths are 1057px grey against 1087px black, so the black
   is marginally wider rather than 14% narrower. That base also carries no
   earrings, which removes them from every crew listing.
2. **The print now sits 3.0 in below the collar, on Evan's instruction.**
   Tapstitch's real back print sits roughly 5.5 to 6.6 in down. **The photos
   therefore show the print higher than it actually prints.** Raise
   `ink_top_below_collar_in` back toward 5.5 to match the real garment.
3. **Assumed size L.** If the models read as a different size, change
   `length_in` in `print_geometry.json` and every dimension rescales.
4. **Landmarks are tied to the base photos.** Regenerate a base and its collar,
   hem and centre must be re-measured. Automatic detection fails on black
   colourways, where garment and trousers are the same brightness.
5. **Earrings** remain on both lifestyle bases. The crew colour set is now
   clear of them, since base `16bd6b6d` was generated without jewellery.
6. **Second and third temples** (Manti, Rome) ran cleanly through the old
   geometry and confirmed per-temple repeatability. They have not been rerun
   under the new physical sizing.
