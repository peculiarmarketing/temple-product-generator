# Pen-drawn temples on the storefront: design

Date: 23 September 2026. Status: draft for Evan's review.

## What we're building, and why

Two animated pieces for peculiarpeopleco.com, both built from the temple drawings
already in `../Temples/`:

1. **Homepage showcase.** The top banner draws a temple as if by pen, holds it, fades,
   and draws the next. The city line types in under each one, exactly as it prints on
   the shirt. One button: Find your temple.
2. **Product page drawing.** A band directly under the photos and Add to Cart that
   draws that product's own temple when the shopper scrolls to it.

Goal A is a first impression that looks like nobody else's store. Goal C is product
pages that feel premium. Both use the real art, so nothing about a building can be
invented or drift, which matters under the fact-integrity rules in BRAND.md.

Agreed in the mockup rounds (23 Sep 2026):

- Pen style: centre-line strokes in pen order, orange pen tip, about 8 seconds per
  drawing, gentle pacing. Once the city line has finished appearing, the finished
  drawing holds for 3 seconds before the loop moves on. Same everywhere. The last
  half second fades in the exact art, so every drawing finishes identical to the
  stored file.
- Background `#001A58`, with a subtle lift to `#0a2873` behind the temple. Never
  darker than `#001A58`.
- No "45 temples and counting" line.
- The art close-up stays at gallery position 2. The band adds to it and does not
  replace it.
- Designed for phones first (layouts below).

## How the right temple lands on every product page

Every live garment product already carries `peculiar.temple_name` (135 of 136
products; the one without is the Temple Art File, which gets no band). All garments
use the one default product template, `templates/product.json`.

- Each temple's drawing is stored once as two small files in the theme, named from
  the product's `temple:` tag, which every live garment carries (`temple:salt-lake`,
  `temple:washington-d-c`): `pp-temple-salt-lake.json` (pen strokes, city line) and
  `pp-temple-salt-lake.webp` (the finished art). The tag is used because the
  `temple_name` values are long and irregular (`Provo Utah Temple (1972–2024)`).
- The band is added to `product.json` once. On each page it reads the product's
  `temple:` tag and loads the matching drawing. `temple_name` supplies the heading.
- The city line comes from the temple's print manifest `location_line`, the exact
  line printed on the garment. It does not come from the `temple_city` metafield,
  which would print `Washington` where the shirt says `KENSINGTON, MARYLAND`.
- No label, or no drawing file yet: the band stays hidden. A shopper never sees an
  empty box or the wrong temple.
- Salt Lake's parent products (bare titles) work the same way, because they carry the
  label too.

## Where the files live

Theme assets, not Shopify Files. The pipeline's app has `write_themes` (added
18 Sep 2026, used by `scripts/swatches.py push`) but not `write_files`, so theme
assets are the path already proven here. 45 temples make 90 small files.

Measured on Manti: strokes 82 KB compressed, finished art 126 KB (lossless WebP,
840 px wide). About 210 KB per temple, roughly one product photo. Files load only
when the band is about to scroll into view. The homepage loads the first temple
straight away and the next one while the current one is showing.

## New tool: `scripts/web_drawings.py`

Modelled on `scripts/swatches.py`: same `check` and `push` shape, same readback
checks, same backup-before-write habit.

- `build [--temple X | --all]`: traces the centre lines and renders the finished art
  for each temple into `artifacts/web_drawings/`. Takes about 5 seconds per temple.
  The tracer comes from the mockup prototype: centre lines, scraps rejoined into
  continuous strokes, then patch strokes wherever art is still uncovered.
- `check`: fails if any live `temple:` tag has no drawing in the theme, if any
  drawing leaves more than 1% of its art uncovered before the final fade, or if any
  drawing is over the 250 KB budget.
- `push [--temple X | --all]`: uploads only changed files to the live theme, then
  reads them back and compares.

It joins the normal new-temple run. After a new temple publishes,
`web_drawings.py build --temple X && push --temple X` makes its band appear. The
publishing flow in the skill and README gains that one step.

## Theme pieces

All new files carry a `pp-` prefix, so none of them collide with shrine-theme-pro
files.

- `assets/pp-pen-draw.js`: the drawing engine from the mockup. It hides each stroke
  until the pen reaches it, fades in the exact art at the end, pauses when off
  screen, and skips straight to the finished drawing for shoppers whose phone is set
  to reduce motion.
- `sections/pp-temple-showcase.liquid`: the homepage banner. Headline, text, button
  label and link, and the list of temples are all editable in the theme editor.
- `sections/pp-temple-drawing.liquid`: the product band. It shows the drawing, the
  city line and the temple's name as its heading. It adds no other new copy. The
  temple facts stay in the description, where the fixed-section rules keep them
  byte-identical.

Phone layouts, as shown in round 3:

- **Homepage:** the drawing sits on top at up to 42% of the screen height, with the
  headline, text and a full-width button below it. All of it fits on the first screen
  of a 390 px phone.
- **Product page:** the band is full width under Add to Cart. Photos and buying come
  first.
- **Touch and text:** tap targets are at least 44 px, and the city line gets smaller
  letter spacing on phones so the longest line, `SARATOGA SPRINGS, UTAH`, fits
  without wrapping.

## Rollout: nobody sees it until Evan says so

1. **Push the new files to the live theme.** Nothing references them yet, so the
   store looks exactly the same.
2. **Create two preview-only page layouts:** `templates/index.pen-preview.json` and
   `templates/product.pen-preview.json`. Evan views them on the real site by adding
   `?view=pen-preview` to any address, on his phone and his computer. Customers
   never land on them. The first thing this step does is confirm that the homepage
   honours `?view=` the way product pages do. If it doesn't, the homepage preview
   moves to an unpublished copy of the theme instead.
3. **Evan approves.** Only then do the edits to the real page layouts happen:
   - Homepage: the showcase goes in first, and the current slideshow banner is
     switched off, not deleted.
   - Product page: the band goes in right after the main product section.
   Both files are backed up first, and the edit is checked so that nothing else in
   them moved (the same safeguard as `swatches.py push`).
4. **Undo:** restore the two backed-up files. That's one command.
5. **Shop collection:** created, and the art file tagged, whenever Evan confirms.
   Its contents can be checked on the store before anything links to it. The
   button switches to it after the Easify import and hoodie tag (see above).

Don't make these edits while the theme editor is open on the live theme. The
editor saves whole files, and whichever save lands last wins.

## Testing

- Unit tests for the tracer on one real temple: the output is the same every run,
  it leaves under 1% uncovered, and it comes in under budget.
- `web_drawings.py check` passes against the live store before any template edit.
- Evan reviews the `?view=pen-preview` pages on a real phone and a desktop browser:
  Salt Lake parent, one other Utah temple, Washington DC (city line differs from the
  name), and Saratoga Springs (the longest city line).
- Page-speed spot check on the product page before and after, on a phone profile.
  The band must not delay the photos or Add to Cart.

## Decided by Evan, 23 Sep 2026

1. **Homepage wording:** keep the current banner's headline, text and button label
   for now. The showcase copies them over word for word, so no new copy is written
   and no humanizer pass is needed. Revisit later.
2. **Homepage temples, in this order:** Salt Lake, Kirtland, Nauvoo, Logan, Mexico
   City, Rome. All six have white SVGs and verified location lines:
   `SALT LAKE CITY, UTAH`, `KIRTLAND, OHIO`, `NAUVOO, ILLINOIS`,
   `LOGAN, UTAH`, `MEXICO CITY, MEXICO`, `ROME, ITALY`. The list stays editable in
   the theme editor.
3. **The button goes to a new "one of each" collection**, not All Temples, which is
   cluttered. That new collection is covered in the next section.

## The button's destination: a new Shop collection

What Evan asked for: one card per garment (the Salt Lake parent, whose Temple
dropdown reaches every other temple), plus anything that isn't a single temple's
design. That covers the Temple Art File today and future non-temple designs.

No existing collection does this. The plan:

- **A new automated collection** titled "Shop" (the name can change), handle `shop`.
  It includes any product tagged `listing:parent` OR `listing:standalone`.
- **`listing:parent` is already on the Salt Lake tee and crew.** The Salt Lake hoodie
  (`cloud-temple-hoodie`) gets it in the existing post-Easify step from HANDOFF.md.
- **`listing:standalone` is a new tag** for products with no temple dropdown: the
  Temple Art File now, and any future non-temple design. It's kept separate from
  `listing:parent` so the planned parents-only All Temples collection doesn't pick up
  the art file.

**Dependency.** Until the Easify re-import, the hoodie parent isn't tagged, so Shop
would show the tee, the crew and the art file, with no hoodie. So the button goes
live with Shop only after the Easify import and the hoodie tag. If the showcase is
approved before then, the button points at Temple Tees for the time being, and the
switch is one field in the theme editor.

Creating the collection and tagging the art file are live store changes. They run
only with Evan's confirmation, like the other rollout steps.

## Round 2 changes (Evan, 23 Sep 2026, after the first preview)

These replace the matching earlier decisions.

- **Background:** flat store black `#121212` for the homepage banner and the product
  band, matching the header. This replaces navy with a lifted centre.
- **Pen tip:** white. Orange is reserved for Add to Cart.
- **No dots:** the six temples flow one into the next like a single video.
- **Buttons:** Add to Cart is the only orange (`#F58000`) button on the storefront, on
  the product page and in the sticky bar. It replaces the product page's blue
  `#0035B2`. The other orange buttons (the homepage before/after section and the
  "suggest a temple" form) become navy `#001A58`. The banner button is navy with a
  thin white border, because plain navy on black is nearly invisible. Checkout's Pay
  button stays orange.
- **Product page slider labels:** `THE TEMPLE` and `THE DRAWING`, in capitals like
  before, replacing `REFERENCE` and `FINAL DRAWING`.
- **Homepage extras (Evan, later the same day):** the homepage before/after slider labels
  in capitals too (`THE TEMPLE` / `THE DRAWING`), and the grey "What you get" cards
  become navy with white text (the theme's `accent-1` card scheme).
- **Collections:** one collection, "Temple Design Products" (handle
  `temple-design-products`), replaces the Shop idea. It holds the Salt Lake tee,
  sweatshirt and hoodie plus the Temple Art File: tag `listing:parent` OR
  `listing:standalone`. Every other temple is reached through the Temple dropdown on
  the product page. The Easify import is done, so the Salt Lake hoodie
  (`cloud-temple-hoodie`) gets `listing:parent` now.
- **Homepage:** the banner button and "The temples" row point to the new collection.
  The "Browse" row (garment cards plus the dead state-collection cards Evan deleted)
  is switched off.
- **Evan, in Shopify admin:** publish the new collection to the Online Store; point the
  menus at it; delete Temple Tees, Temple Crewnecks, Temple Hoodies and All Temples;
  redirect their old addresses to the new collection. The app token can do none of
  these: it has no menu or publication scope, and deleting store data stays with Evan.
- All of this ships through the same preview (`?view=pen-preview`), then golive.

## Out of scope

- The character-art version for social posts (possibly Bailee's, later).
- Any change to descriptions, product photos or the art close-up cards.
- Removing the old slideshow section: it is only switched off.
