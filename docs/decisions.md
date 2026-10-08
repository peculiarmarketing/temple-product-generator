# Decision Log

Decisions Evan has made, with dates. Newer entries refine or override older ones.
Entries that only governed the retired first supplier's pipeline were removed on
6 October 2026; git history has them.

## August 2026: decisions still in force

Carried over from the first catalogue. Each one still governs the Tapstitch
pipeline.

- **Art source of truth: `Temples/{Name}/` folders.** Manifests name art files
  explicitly, because folder naming is inconsistent.
- **The location line is the temple's PHYSICAL city, not its name-city**
  (17 Aug). Washington D.C. Temple prints KENSINGTON, MARYLAND; Provo City Center
  prints PROVO, UTAH. All caps, comma, spelled-out state, country for
  international.
- **temples.json is the location dataset** (17 Aug). Folder name maps to official
  name and verified location line. A folder with no manifest gets one scaffolded
  from this dataset; unverified entries hard-stop with instructions rather than
  guessing. For a new temple, research the physical location
  (churchofjesuschristtemples.org), append the entry, and ask Evan only when
  uncertain.
- **The location line is a rendered image** in Alata, from the manifest's
  location string. A `*location text*{black|white}*` file in the temple folder
  wins over the auto-render.
- **New-temple flow:** drop a folder with two SVGs (or the source sketch PNG)
  into `Temples/`. Everything else is derived.
- **Tracer standard: drop `--square`.** New temples are traced
  `--trim --drop-label`; files come out at the drawing's natural aspect. Existing
  square files work identically, because the layout engine measures ink, not
  frames.
- **Runs are manual.** No scheduled task; Evan starts a run in a session.
- **The Easify Temple dropdowns are pipeline-managed via CSV** (17 Aug). The
  canonical file is `artifacts/easify/option-sets.csv`; `scripts/easify_options.py
  sync` reconciles it against the live catalogue, and Evan imports it in the
  Easify app by hand. The temple label is the reconciliation key and URLs follow
  labels; handles are always read from Shopify, never derived from titles. Option
  values are never auto-deleted: rows the sync cannot bind are kept and reported.
  New sets carry placeholder ids (900001+) until a post-import `reseed --export`
  adopts Evan's fresh export with the real ids.
- **Titles lead with the garment line, temple in parentheses** (22 Aug). One
  pattern per garment config (`naming.title`), never hardcoded. **Salt Lake is the
  parent temple** (`config/catalog.json`): its products carry the bare
  `naming.title_parent`, and shoppers reach every other temple through the Easify
  Temple dropdown. Reading a title back to a temple is an exact lookup on the
  parenthesized place token (`art_images.match_temple`).
- **`limited edition` marks Evan's hand-built one-offs.** The pipeline never
  builds over one, never publishes one, and never gives one a dropdown row. They
  have no art cards by design.
- **The storefront's opening variant is the Color option's first value**
  (22 Aug). Shopify preselects variant position 1 and computes position from the
  option value order, so `productOptionsReorder` is the only lever over it. That
  list is also the swatch display order. Declared per garment as
  `storefront_first_color`, applied by `scripts/shopify_fixups.py color-order`.
- **`productOptionsReorder` needs every option in the payload**, not just the one
  moving; a partial list fails with MISSING_OPTION_NAME.
- **Reordering colours can scramble the size list.** Shopify re-derives every
  option's value order from the resulting variant sequence, so a first colour
  missing a size pushes that size to the back. `reorder_option_values` feeds a
  canonical size order in on every call so a re-run cannot compound it.
- **`art_images.py` does not abort the batch on one failure** (22 Aug). A
  product with no mockups yet cannot take a card at gallery position 2; it is
  skipped and reported, and a re-run picks it up.
- **New products publish ACTIVE** (26 Aug, superseding a 22 Aug rule that
  unlisted every child product). Nothing in the pipeline sets a product's status
  in either direction. Children published before 26 Aug 2026 stay UNLISTED, so
  `easify_options.py` counts UNLISTED as live.
- **Temple facts render as collapsed `<details>` rows** (26 Aug). One row for the
  temple name (h3) with its spec rows, then one per h4 block; the as-of line stays
  visible after the rows. The rows carry their own scoped `<style>` block
  (dividers, 12px row padding, a +/- indicator), literal characters only, no
  entities.
- **Presentation transforms live in `description_html.py` and run at assembly
  time.** The stored fixed sections and the `temple-facts.html` fragments stay
  untouched; `compose_description()` is the one place a description's final HTML
  is shaped. Transforms unwrap then rewrap, so composing twice is byte-identical.
  The `<section class="temple-facts">` wrapper stays outermost.
- **Every temple's black SVG is mirrored into `Temples/All/`** (26 Aug) for the
  Temple Art File digital download, named by the clean place token
  (`Manhattan black.svg`, `Ogden Original black.svg`, no ref-finder stars).
  `generate.mirror_black_art()` does the copy; no pipeline script calls it since
  6 Oct 2026, so run it by hand for a new temple. `Temples/All/` is not a temple
  folder: any script that walks `Temples/` must skip it.
- **A renamed temple folder strands its manifest silently** until the next run;
  the `Manifest names missing art file` hard stop is the tell. Manifests are
  pipeline-maintained.


## 14 September 2026 (the Tapstitch decision and what it changed)

- **Evan committed to Tapstitch blanks**: one tee, one hoodie, one crewneck for
  every temple design. The old blanks retire. The specific blanks are
  NOT picked yet, so print areas, colours, prices and product copy are all still
  placeholder.
- **The logo moved off the back print to the front.** New layout profile
  `back_temple_text` (temple plus location text).
- **Two back-spacing questions were raised by that change and are open.**
  Measured across all 40 designs: removing the logo left the old 2.5in bottom
  margin as the only thing capping tall temples (Salt Lake prints 11.1in against
  a 12.5in target), and top-anchoring leaves between 2.5in and 8.6in of empty
  canvas below the location line depending on the building's proportions.
  `vertical_anchor: "center"` exists as the alternative. Proof sheet:
  https://claude.ai/code/artifact/63f25017-3639-4bb9-96cc-d16cc1e21d57
- **Descriptions go straight to Shopify, never through the Tapstitch editor.**
  The writer is proven on 158 products and no Tapstitch redesign can break it.
- **Garment copy moved out of the description skills** into
  `reference/garment-copy/{garment_id}/`. Three new blanks would otherwise have
  meant three new skills holding two HTML files each. The
  Tapstitch folders hold a README and NO html files on purpose: `fixed_description()`
  returns empty when the files are absent, and an empty description beats the
  wrong garment's specifications on a live page, so a placeholder would defeat
  the guard.
- **MEASURED: Tapstitch publishes to Shopify with an EMPTY productType**, and
  every fixup in `scripts/shopify_fixups.py` is keyed on that field, so colour
  ordering silently does nothing and reports success. The
  runner sets productType immediately after publish, before any fixup. Full
  findings in `docs/discovery/2026-09-tapstitch-store-findings.md`, including the
  four Tapstitch test products Evan left as drafts on 28 Aug and their real
  colours and prices.
- **FOUND ON THE LIVE STORE: two products share the exact title "Essential
  Temple Tee".** `salt-lake-city-temple-tee` (created 8 Aug, Moss first, carries
  the art card) is the real parent; `essential-temple-tee` (created 27 Aug, Navy
  first, no art card) is a stray. Only one address can be inherited, so the
  snapshot keeps the OLDEST and reports the collision rather than letting
  last-write-wins pick. RESOLVED the same evening: the stray was deleted, along
  with its twin. See the evening entry below.
- **The repo was in an iCloud conflict state** when this work started: empty
  shells named `garments`, `config`, `scripts`, `docs`, `tests`, `artifacts`,
  `fonts`, `reference` beside the real content in `<name> 2` twins. Git reported
  every tracked file as deleted and `generate.py` could not read its own configs.
  Resolved by confirming each plain directory held zero files, then moving the
  twins back. If it recurs, that is the check to run first.
- **Trap found in this session's own code:** an `lru_cache` on print-area-sized
  rasters (~67MB each) at maxsize=256 holds gigabytes and the machine swaps
  instead of working. Caches are capped at 8 and 4; callers iterate temple-major
  so that covers every repeat within one temple.

## 14 September 2026 (a test lesson)

TEST LESSON from this round: two tests written earlier in the day pinned exact
colour values and exact rename pairs, and both failed on a CORRECT change rather
than a regression. Both were rewritten to assert the contract instead: the colour
table must be non-empty and cover every product type with a live garment's own
choice winning, and the rename table must equal what the configs declare. Do not
pin a lineup that is expected to change.

## 14 September 2026, evening (spacing settled, store taken dark, six deletions)

- **Designs are CENTRED in the print area** (`vertical_anchor: "center"`), not
  top-anchored. Evan's call. Measured across the catalogue: every temple now sits
  with equal space above and below, from 1.55in on Salt Lake to 4.49in on
  Monticello, instead of the 2.5in-to-8.6in bottom gap top-anchoring produced.
- **The location line is the same height on every temple**, so the type never
  varies between products. It was already constant at 0.74in; what varied was the
  temple art beside it, not the type. Set per garment in `spacing_overrides`.
- **0.8in, chosen against the width ceiling rather than by eye.** Asked for 1.0in
  first, then asked what 0.8 would do. Measured across all 40 location lines, the
  longest being SARATOGA SPRINGS, UTAH:

  | Height | Widest line | Fits a 12in area | Fits 12.5in | Fits 14in |
  |---|---|---|---|---|
  | 0.7in | 9.52in | yes | yes | yes |
  | 0.8in | 10.88in | yes | yes | yes |
  | 0.9in | 12.24in | NO, 2 lines fail | NO, 1 fails | yes |
  | 1.0in | 13.60in | NO, 6 lines fail | NO, 3 fail | NO, 1 fails |

  0.8in is the LARGEST height that survives any plausible print area, which is
  what makes it the right answer while the real Tapstitch print area is still
  unknown. 1.0in only ever fit because the placeholder canvas is oversized at
  14.98in; it would have started clipping the moment the real number arrived.
- **Proof-sheet swatches were repainted** to the colours the products actually
  open in (Black, Coffee, Dark Gray). They had been rendering the old
  catalogue's colours, which meant Evan was being asked to judge
  the design against colours that no longer exist.

### THE STORE IS DARK, done 14 Sep 2026 on Evan's explicit go-ahead

- **160 temple listings set to DRAFT**, 0 failures. Verified against Shopify
  afterwards: 165 products, 164 DRAFT, 1 ACTIVE. The only thing still live is
  **Temple Art File**, the $4.95 download, which is not a garment and stays
  sellable. The four Tapstitch test drafts were correctly excluded by
  vendor.
- **SIX PRODUCTS PERMANENTLY DELETED** at Evan's instruction. There is no undo:
  - the two stray duplicates from 27 Aug, `essential-temple-tee` and its twin
  - the three Nauvoo Limited Edition one-offs
    (`nauvoo-temple-tee-limited-edition`, `copy-of-nauvoo-temple-hoodie`,
    `nauvoo-temple-sweatshirt-front-logo`)
  - `cornerstone-sweatpants`
- **The pre-migration snapshot** `artifacts/tapstitch/pre-migration-catalog.json`
  records the 160 drafts as they were. The script that took the catalogue down and
  could restore it from that file was removed on 6 Oct 2026; git history has it.
  Nothing can bring back the six deletions.

## 14 September 2026, late evening (US fulfillment, crew and hoodie blanks swapped)

- **Every line moves to USA fulfillment.** Production 1-2 days and shipping 3-5,
  so **4-7 days to a customer's door against 10-17** from the international
  center. This is the largest single improvement the migration has produced for
  a buyer, and it is the reason the two fleece blanks changed with it.
- **Mechanism, and why it forced blank changes:** the fulfillment selector on a
  Tapstitch product page is not a shipping preference. Their own wording is that
  it changes which colours and sizes are available, the printing price, and the
  shipping options. A blank is therefore a different product from the US center
  than from the international one, and two of the three did not survive the move
  intact.

| Line | Blank | Code | Weight | Sizes | Blank | Technique | All-in |
|---|---|---|---|---|---|---|---|
| tee | Essential Cotton T-Shirt #RT0063 | RT0063-C001-V5 | 260 gsm, 7.7 oz | S-3XL | $5.99 | DTG | $19.57 |
| crew | Fleeced Sweatshirt #R00368 | R00368-C001-V7 | 350 gsm, 10.3 oz | S-2XL | $16.57 | DTF | $34.10 |
| hoodie | Oversize Fleeced Hoodie #R00286 | R00286-C001-V7 | 350 gsm, 10.3 oz | S-2XL | $14.92 | DTF | $34.67 |

- **The crew is now the R00368 Fleeced Sweatshirt**, replacing the UT0044. Same
  weight class as the blank it replaces (350 gsm against 345) and the same S-2XL
  range. **Two colourways only: Black and Flower Gray**, which the storefront
  shows as Gray. The line opens on Gray (Evan).
- **The hoodie is now the R00286 Oversize Fleeced Hoodie**, replacing the RW0041,
  at 350 gsm / 10.3 oz and S-2XL. **Haze Blue is gone**; Black, Dark Gray, Navy
  Blue, Dark Green and Coffee remain, all dark, so everything still prints white
  and there is still no black art file to build. Opens on Dark Gray, unchanged.
- **The crew and hoodie are still a matching set on fabric** (both 350 gsm /
  10.3 oz, both DTF) but **no longer on colour**: two colourways against five,
  sharing only Black. The 'four of the five tee colours are shared with the
  fleece, so the catalogue reads as one family' rationale from earlier today no
  longer holds. Black is the only colour all three lines carry.
- **The tee is unchanged** (Evan, asked directly): still the RT0063, still Black,
  Dark Gray, Coffee, Navy Blue and Wine Red shown as Maroon, still opening on
  Black. Only its cost moved.
- **Two storefront renames now, not one.** Wine Red to Maroon on the tee, and
  Flower Gray to Gray on the crew. This supersedes 'only one rename survives'
  from the afternoon. Both are read from the configs by
  `colorway_renames_by_type()`, so the table picked the second one up with no
  code change: it now returns `{'T-Shirt': [('Wine Red', 'Maroon')], 'Sweatshirt':
  [('Flower Gray', 'Gray')]}`.
- **The two fleece blanks print DTF, not DTG.** DTF lays a film layer on the
  fabric: strong opacity on dark grounds, which is what white line art wants, at
  the cost of breathability across large solid areas. Our designs are line work
  on dark blanks, so this is a fair trade, but it is a real change in what the
  garment feels like and the product copy should not claim DTG.
- **Costs are Evan's figures**, measured on the blank and the fulfillment
  actually in use. The stale
  international shipping line items were REMOVED from the configs rather than
  left sitting beside the new all-in numbers, where they would have read as
  current.

## 14 September 2026, last of the day (design sizes, hoodie lead colour)

- **The hoodie opens on Navy Blue**, not Dark Gray. Evan. `storefront_first_color`
  in `garments/hoodie.json`, and the proof-sheet swatch follows it.
- **The temple is 12.0 inches wide ink to ink at its widest point**, down from the
  12.5in the old catalogue used. Set as `temple_target_ink_width_in` in each
  garment's `spacing_overrides`.
- **The front logo is 6.0 inches wide ink to ink.** This one needed a code change,
  not a config change. `build_front_logo` sized the logo by its FILE FRAME, and
  the logo PNG carries about 2.4% transparent padding across and 6.4% down, so
  `logo_width_in: 6.0` was printing a 5.86in logo. It now measures the ink bbox
  and scales the frame so the drawn logo is exactly the configured width,
  horizontally centred on its own ink rather than on its padding. Measured after
  the change: 6.003in, the 0.003 being the rounding to a whole pixel at 300dpi.
- **The keys were renamed rather than redefined**: `logo_width_in` became
  `logo_ink_width_in` and `logo_top_margin_in` became `logo_ink_top_margin_in`,
  and `build_front_logo` hard-stops if it finds either old key. A config that
  silently changed meaning is exactly the kind of failure that would have printed
  a wrong-sized logo on 120 products without anyone noticing.
- **`logo_ink_top_margin_in` is now the ink top**, where it used to be the frame
  top. On the placeholder front area the logo's first drawn pixel now sits at
  2.997in rather than 3.038in. The number to trust is the ink one; the old
  behaviour was off by whatever padding the file happened to carry.

**MEASURED CONSEQUENCE of the 12.0in rule, across all 40 traced temples:** six
finish under 12.0in because the height cap shrinks them first.

| Temple | Ink width | Ink height |
|---|---|---|
| West Jordan | 10.68in | 12.59in |
| Nauvoo | 10.85in | 12.59in |
| Salt Lake | 11.05in | 12.59in |
| Spanish Fork | 11.20in | 12.59in |
| Washington DC | 11.54in | 12.59in |
| Lindon | 11.71in | 12.59in |

  All six hit 12.59in tall, which is the entire vertical budget on the
  placeholder canvas: 16.99in of area less the 0.6in top margin, the 2.5in bottom
  margin, the 0.5in gap and the 0.8in location line. They are the tall narrow
  buildings, so they run out of height before they run out of width and
  `_place_temple` shrinks them to fit. **The 2.5in bottom margin is the binding
  constraint, not the 12.0in rule.** It was measured off the old
  catalogue for a layout where the logo sat at the bottom of the back stack, and
  centring made it meaningless: the block is repositioned afterwards anyway.
  Matching it to the 0.6in top margin gives 14.49in of budget and every one of
  the six clears 12.0in (the tallest, West Jordan, needs 14.14in). That is a
  one-line change to each garment's `spacing_overrides` and it is NOT made:
  margins are a design decision and this one is Evan's, already open in BRAND.md
  section 19.
- **Worth knowing before the real print area lands:** a 12.0in-wide design on a
  12in print area touches both edges, and the validator's 0.25in safe margin
  would fail every file. 12.0in only works if the real Tapstitch area is wider
  than 12.5in. The placeholder is 14.98in wide, so nothing fails today, and this
  is one more thing the first editor session settles.

## 14 September 2026, the print areas (and two file rules)

**PNG only, no SVG uploads.** Evan, from Tapstitch. Already true and unchanged by
it: the pipeline has never uploaded a vector. The SVGs under `Temples/` are
sources that get rasterised into one flattened PNG per print file, which is the
whole point of the flattener, and both `back_file_path()` and
`front_file_path()` build `.png` names. Nothing to change; recorded so a future
session does not 'optimise' by uploading the vector.

**Invisible pixels must carry the ink colour, not black.** Evan, from seeing grey
where white art should be. Already fixed, and the mechanism is worth keeping
written down. A rasterised PNG stores RGB(0,0,0) under fully transparent pixels.
Tapstitch's previewer and Finder's thumbnailer resample without premultiplying
alpha, so they average that hidden black into the neighbouring ink and smear grey
halos around white line work. `flatten.matte()` sets every pixel's RGB to the ink
colour and leaves alpha alone, so the average is a no-op. Verified again today on
a built white file: 21,676,134 fully transparent pixels and 446,172
semi-transparent ones, every one of them RGB(255,255,255). This is why
`matte()` must never be 'optimised' to skip invisible pixels: they are exactly
the pixels it exists for.

**THE REAL PRINT AREAS, read off the editor by Evan.** The placeholder canvas is
retired.

| Line | Blank | Front px | Back px | Front in | Back in |
|---|---|---|---|---|---|
| tee | RT0063 | 2193 x 2758 | 2193 x 2758 | 14.62 x 18.39 | 14.62 x 18.39 |
| crew | R00368 | 1982 x 2609 | 2061 x 2757 | 13.21 x 17.39 | 13.74 x 18.38 |
| hoodie | R00286 | 2069 x 1615 | 2067 x 2770 | 13.79 x 10.77 | 13.78 x 18.47 |

- **The inches assume 150 dpi, and that is an assumption, not a reading.**
  Tapstitch does not publish the resolution those pixel counts are quoted at, and
  it is the one number that changes every dimension in the catalogue. Two things
  argue for 150. At 300 the widest back area is 6.89in across, which makes Evan's
  own 12in temple rule impossible on every garment, and the front logo would have
  to shrink with it. At 150 the areas land within half an inch of the 14.98 x
  16.99in area this catalogue printed on for a year. **Confirm it in the
  editor, which shows inches.** If it is 300, change `editor_dpi` in the three
  configs and every inch halves; nothing else needs touching, because the layout
  computes from `width_px / dpi`.
- **The stored `width_px` is the editor's number DOUBLED, with `dpi` set to 300.**
  Exporting at the editor's native 2193 x 2758 would mean a 150dpi print file,
  under this project's own 200 effective-DPI floor, on a $75 garment. Doubling
  keeps the aspect ratio identical to the pixel, so 'upload, centre, full size'
  places the art exactly the same way, and the file arrives at 300dpi at final
  size. `editor_px` and `editor_dpi` are recorded beside it so the real numbers
  are never lost behind the doubled ones.
- **Every garment now has its own canvas**, and the front and back differ: the tee
  is square-ish and identical front and back, the crew's front is an inch narrower
  and a full inch shorter than its back, and the hoodie's front is LANDSCAPE, 13.79
  wide by 10.77 tall, because the pouch pocket takes the bottom of the panel.

**FIT, measured across all 40 traced temples on the real areas:**

- **39 of 40 reach the full 12.0in width on every garment.** On the placeholder
  canvas six fell short; the real areas are taller, so five of those six now make it.
- **West Jordan is the one that does not**, at 11.86in on the tee and crew and
  11.93in on the hoodie. It is the tallest narrow building in the catalogue and it
  runs out of height first. The shortfall is under a sixth of an inch and is
  invisible next to any other temple.
- **The 2.5in bottom margin is still what binds**, exactly as flagged earlier
  today. Ink-height budget is 13.99in on the tee, 13.98in on the crew and 14.07in
  on the hoodie; West Jordan needs 14.14in. Matching the bottom margin to the
  0.6in top would clear it with inches to spare. Still Evan's call, still one line.
- **Side margins at 12.0in wide** are 1.31in on the tee, 0.87in on the crew and
  0.89in on the hoodie, all comfortably past the 0.25in safe margin. Every sample
  built and validated clean on all three garments.

**RAISED, not decided: `logo_ink_top_margin_in` means something different on the
hoodie.** It is 3.0in on all three lines, measured from the top of the print area.
On the tee and crew that is a 3in drop inside an 18in panel, which is high on the
chest. On the hoodie it is a 3in drop inside a 10.77in panel, so the logo sits
almost a third of the way down a much shorter area. The number is identical and
the result is not. Placement is already open in BRAND.md section 19 and waits on
seeing a mockup.

**Blockers cleared by this:** `tapstitch_publish.py check` went from 9 garment-setup
items to 3. All six print-area items are gone. What remains is the product copy for
the three lines, which waits only on the size-guide decision.

## 14 September 2026, the back design stated completely (supersedes all earlier spacing)

Evan, replacing the margin-based spacing the layout inherited from the old catalogue. The
back print is now four rules and nothing else:

1. The temple and the location line are **centred in the print file**, vertically
   and horizontally.
2. The temple ink spans **no more than 12.0in** at its widest point.
3. The location line is **0.7in of INK tall**, not 0.7in of box.
4. The **top of the location line sits 0.5in below the temple's lowest ink**.

- **There is no top or bottom margin any more.** `top_margin_in` and
  `bottom_margin_in` are both 0.0 in the three garment configs.
- **This is what finally cleared the width problem.** The 2.5in bottom margin was
  measured off the old catalogue, where the back stack ENDED with the
  logo and that space had a job. Once the logo moved to the front, the margin
  reserved space for nothing while still capping how tall a temple could be, and
  height is what caps width for a tall narrow building. Six temples fell short of
  12.0in on the placeholder canvas, one (West Jordan) on the real areas. With the
  margins gone, **all 40 reach the full 12.0in on all three garments.**
- **0.7in replaces 0.8in.** The 0.8 was reasoned against a guessed print area
  before the real ones were known; this is Evan's number against the real thing.
  At 0.7in the longest line in the catalogue, SARATOGA SPRINGS, UTAH, renders
  9.52in wide, which clears the narrowest back area (13.74in on the crew) by more
  than two inches either side.
- **The ink-not-box rule matters more for type than for art.** `render_text`
  already crops to the alpha bbox before scaling, so the height asked for is the
  height of the letterforms; a font's own box is taller than its letters and would
  have printed visibly small. Verified on a build: 0.700in of ink at both heights.
  Worth knowing: a manual `*location text*` override file in a temple folder
  bypasses that crop and would be scaled by its box. There are zero overrides in
  the catalogue today (checked), but the first one added will need trimming.
- **The 0.5in gap was already the value in use** (`gap_ink_to_text_in`, raised
  from 0.2 by Evan on 19 Aug 2026). It is now stated explicitly per garment rather
  than inherited, so a change to the defaults cannot move it.

**VERIFIED ON BUILT FILES, all three garments, the tallest, widest and most
extreme temples:**

| Garment | Temple | Block | Temple ink | Gap | City line | Centred within |
|---|---|---|---|---|---|---|
| tee | West Jordan | 15.34in | 12.00in wide, 14.14in tall | 0.500in | 0.700in | 0.002in |
| tee | Monticello | 7.45in | 11.98in wide, 6.24in tall | 0.510in | 0.700in | 0.002in |
| crew | Salt Lake | 14.87in | 11.99in wide, 13.67in tall | 0.507in | 0.700in | 0.003in |
| hoodie | West Jordan | 15.34in | 12.00in wide, 14.14in tall | 0.500in | 0.700in | 0.002in |

  The hundredths of an inch are the alpha threshold, not the layout. Measuring a
  rasterised file counts a pixel as ink above alpha 10, and a line drawing's
  faintest antialiased edge falls below that, so a measured edge can sit two or
  three pixels inside the computed one. At 300dpi three pixels is 0.01in. The
  geometry itself is exact.

- **Every sample validated clean** on all three garments: no safe-margin breach,
  no resolution problem, single ink throughout.
- **The proof sheet's own copy was rewritten** to match, and `spacing_study()`
  (the same temple at four different bottom margins) is retired, since the
  question it answered no longer exists. `main()` no longer calls it.

## 15 September 2026 (the temple folder root is Evan's, not the pipeline's)

- **Every per-temple file the pipeline owns now lives in
  `Temples/{Name}/Working files/`.** Evan moved them there by hand across all
  45 temple folders. That is `manifest.json`, `status.json`,
  `temple-facts.html`, and `{Temple} trace check (auto).png`. Nothing the
  pipeline writes goes to the folder root any more.
- **What stays at the root is what Evan opens:** the two traces
  (`{Temple} black.svg` / `{Temple} white.svg`), the three garment print files,
  the art close-up, and the source PNG. `References/` and his own
  `old designs/`, `Old versions/`, `Alts/`, `mockups/` folders are unchanged
  and untouched by the pipeline.
- **Resolution goes through `layout.working_path(temple, filename)`.** Writes
  always land in the working folder, creating it if needed. Reads prefer it and
  fall back to the folder root, so a temple whose files have not been moved
  still resolves; a file that exists in neither place resolves to the working
  path, which keeps `.exists()` meaning "no file anywhere". Temple discovery
  goes through `layout.temple_manifests()`, which reads both locations with the
  working folder winning. Any new script that reaches for a per-temple pipeline
  file uses these rather than joining a path itself.
- The fallback is a migration convenience, not a supported second home. Once no
  temple has files at its root (true as of today, checked) it can go.

## 15 September 2026, evening (the editor turned out to be an API)

- **The highest-value unknown in the migration is answered, and the answer is
  yes.** Recording the editor's own traffic while Evan built one tee by hand
  showed that the save is `PUT /api/designs/customized/templates/<id>` carrying
  the complete design as JSON: piece, source URL, left, top, width, height,
  scaleX, scaleY, angle. Every other step is a JSON call too. Full detail and
  payload shapes in `docs/discovery/2026-09-tapstitch-editor-api.md`.
- **The blank is addressed by its SKU** (`silSn: "RT0063"`), not by searching a
  catalogue and clicking a result. Three selectors die on that fact alone.
- **The flattened-file bet paid off.** Both uploads registered at 4386x5516,
  exactly the tee's real print area, and front and back received identical
  placement differing only in `src`. Because every file is built to the shape of
  its own print area, the editor places it the same way every time, which is
  what the whole approach rested on and what `config/tapstitch.json` asked to
  have confirmed before any of it was trusted.
- **Colours are numeric codes to Tapstitch**, so the swatch-name mismatch cannot
  bite on the API path. It is not retired: `shopify_fixups.py` matches on names,
  so `colorway_renames_by_type` must still agree with what Tapstitch publishes.
- **Saving a draft does not touch Shopify**, checked straight afterwards: the
  newest product in the store is still from 27 August. The store stays dark.
- **Nothing has been replayed.** Everything above is observation of a human
  session. Whether a scripted call is accepted with only the profile's cookies,
  and whether anything needs a CSRF header, is untested. The next step is one
  throwaway product, not the catalogue. The selector block stays in the config
  until then, and `tapstitch_publish.py check` still reports it.
- **`scripts/tapstitch_capture.py` is new** and is the tool that answered this.
  It automates nothing; it attaches to the dedicated Chrome and records while
  Evan works. It took three silent failures to get right, all documented in the
  discovery note. The one that mattered: the sync Playwright API dispatches
  events only while the caller is inside a Playwright call, so a `time.sleep()`
  in the watch loop swallows every callback and the capture reports success
  while writing nothing.

## 15 September 2026, late (the API route is proven, and the click path is retired)

- **The editor's API was driven from Python and it worked.** A design template
  was created from the blank's SKU, a 640KB print file was uploaded through the
  signed OSS URL, and the design was saved, after which Tapstitch rendered four
  mockups from it. Verified by reading the design back: geometry and source URL
  persisted, new `commitId` minted.
- **Auth is the dedicated Chrome profile's cookies, nothing more.** No CSRF
  header, no token, no editor session.
- **The selector block is retired.** All fourteen selectors, `urls.new_product`,
  `values.design_size` and `values.size_unit` moved to
  `_selectors_superseded_by_api` in `config/tapstitch.json`. They are kept rather
  than deleted because the store-product call has not been run; if the API route
  has a hole, that block is the map back to the fallback.
- **`tapstitch_publish.py check` no longer says "ready"** for the editor half.
  Saying so would have been the same class of stale signal this repo keeps
  getting bitten by: the config is ready, which is a smaller claim than the
  runner being ready.
- **`create_store_product` remains unrun by choice.** It is the only step that
  reaches the live storefront, and the store is dark.
- **The placement numbers were reused, not derived.** `left: 344, top: 358` on a
  700x700 canvas came from observing one tee. The canvas-to-print-area mapping is
  still unknown, so placement must NOT be generated for the crew or hoodie until
  it is worked out. This is the one thing in the API route that would fail
  quietly and misprint rather than error.

## 15 September 2026, night (first product published, and the size guide decided)

- **A real product is live on Shopify**, published through the captured
  `POST /api/services/user/distribution/stores/products/distribute`, which takes
  a LIST of store-product ids, so 135 products is a batch, not 135 clicks.
  "Essential Heavyweight Temple Tee", ACTIVE, 30 variants at $44.99.
- **Tapstitch published it with an empty `productType`, exactly as documented.**
  Set to "T-Shirt" immediately. Every fixup is keyed on it.
- **The publish outran the editor.** The product took over a minute to appear
  after the call returned, confirming the existing rule: verify against Shopify,
  never trust the editor's success state.
- **The colour swatch names are CLEAN for the tee.** Tapstitch sends Black, Dark
  Gray, Coffee, Navy Blue and Wine Red, all five matching `garments/tee.json`.
  The silent-mismatch risk does not exist for RT0063. Still unchecked for the
  crew and hoodie.
- **The size guide is decided: the old tee's section FORMAT, with RT0063's own
  measurements.** Evan asked for the old tee's size guide section. Its numbers are
  for a different garment and could not be shipped: RT0063 runs ~1.4in wider in
  the chest and HAS NO 4XL, so the old table would have advertised an
  unsellable size on every listing. `reference/garment-copy/tee/size-guide.html`
  carries the manufacturer's real figures for S-3XL, labelled in inches.
- **The old tee's intro was NOT copied across.** It claims garment-dyed ringspun
  cotton at 6.x oz; RT0063 is 7.7 oz (260 gsm) and not garment-dyed. Copying it
  would have published false product claims. `tee/product-intro.html` therefore
  does not exist, `fixed_description()` still returns empty, and that is the
  guard in its README working as intended rather than a gap to paper over.
- **No size-guide video for the new blank.** The old section embeds a
  per-blank video showing the wrong garment. Omitted. The size guide later left
  the description entirely (16 Sep), and on 2 Oct Evan left it as is: no new
  video and no branded chart images for now.

## 16 September 2026 (the crew blank exercised, and the placement mapping derived)

- **THE QUIET FAILURE IS CLOSED. The canvas-to-print-area mapping is derived,
  not copied.** Tapstitch states it outright and nobody had looked:
  `get_template()` returns `craftItemDto.customArea`, and every printable side
  carries a `<side>_side_middle` detail whose x/y/width/height are coordinates on
  the editor's own 700x700 canvas. `tapstitch_api.print_areas()` reads it;
  `placement()` turns it into the editor's geometry. The rules, each checked
  against the 15 Sep tee rather than assumed:
  - `left`/`top` are the print area's CENTRE, not its corner and not the
    canvas's centre. The tee's back area is x=214 y=194 w=260 h=327, so the
    centre is 344, 357.5, and the editor stored left=344, top=358.
  - `scaleX` and `scaleY` are both the area's height over the canvas:
    327/700 = 0.4671428571, exactly what the editor stored.
  - The object's own width/height is the image fitted inside the canvas with the
    minor dimension TRUNCATED: 700 x 4386/5516 = 556.6 becomes 556, not 557.
  - We send the exact centre rather than rounding it, because half a canvas pixel
    is 0.03in on the garment and an exact centre needs no guess about which way
    Tapstitch rounds a .5. Tapstitch persisted 348.5 and 342.5 unchanged.
- **The rectangles differ per garment and, on the crew, per side.** Tee: 260x327
  on both. Crew: 210x281 back, 209x275 front. Copying the tee's numbers onto the
  crew would have printed the back art 16% oversized and off centre, front and
  back both wrong, with no error anywhere. That is the failure the handoff named
  and it was real.
- **`placement()` refuses a mis-shaped file.** Scaling to fit the height only
  works because every print file is built to its own print area's aspect, so the
  function checks the drawn width lands within one canvas pixel of the area width
  and raises if it does not. The assumption is now checked rather than silent.
- **The crew blank's ids are recorded**: `productId` 1534524735445225472,
  `specialProcessTags` `["DTF"]`, colours 5720 Black and 6551 Flower Gray. Read
  from `GET /api/services/site/products/search?q=r00368`, which is how any
  blank's ids can be got without opening the editor.
- **The crew's print areas are CONFIRMED, not assumed.** The template's own
  `backSideDpiTip` reads "Print area size 2061 x 2757 px (150)DPI" and
  `frontSideDpiTip` reads "1982 x 2609 px (150)DPI", matching
  `garments/crew.json` exactly. The "ASSUMED 150, NOT CONFIRMED" note in that
  file can go.
- **The colour swatch names are CLEAN for the crew.** The store-product prefill
  (`GET /stores/{storeId}/products/templates/{templateId}/new`) is what Tapstitch
  will send Shopify, and it names them "Black" and "Flower Gray", matching the
  config. The silent-rename risk is closed for this blank too.
- **A design is built and saved on the crew**, Salt Lake back plus the front
  logo, and Tapstitch rendered mockups from it. Nothing has reached the store.
- **The crew size guide is written** from the blank's own published measurements,
  in the tee's format: `reference/garment-copy/crew/size-guide.html`, S-2XL.

### Raised to Evan the same day, not decided

1. **Flower Gray is a mid heather gray, not a dark**, RGB(184,181,186), and the
   mockup shows white line art on it reading noticeably weaker than on black.
   The fine line work and the city line both lose definition. Black ink would be
   far stronger and would mean building the black art files for this colourway.
   This is the "INK NEEDS EVAN'S EYE" note in `garments/crew.json`, now with a
   real mockup behind it.
2. **A third colourway is US-fulfilled**, 6672 Oat Gray, RGB(237,233,221). The
   config lists two. It is light, so it would print the black art.
3. **The crew fabric is 42% cotton, 53% polyester, 5% other fibers**, against the
   old crew's 80% ring-spun cotton with a 100% cotton face. The old crew intro's
   closing line claims a ringspun cotton face and garment dyeing, so it cannot be
   copied across for the same reason the tee's could not. The crew intro is still
   unwritten and still blocks descriptions.

## 16 September 2026 (the size guide on the Tapstitch side)

- **EVAN: the size guide goes in the product description, and it is IMPERIAL.
  Not metric, not both.** Recorded as `size_guide` in `config/tapstitch.json`.
- **This is a trap, not a preference.** Tapstitch's store-product prefill comes
  back with `unitOptions` IMPERIAL and METRIC **both selected**, so the default
  behaviour publishes inch/cm column pairs. `sizeGuide.descriptionHtml` offers
  `IMPERIAL`, `METRIC` and `BOTH`; the runner takes `IMPERIAL`.
- **The size guide is not a field in the POST body.** Tapstitch bakes the chosen
  table into `description.content` when the store product is created, which is
  why this has to be got right at create time rather than fixed afterwards.
- **Caveat worth knowing:** the IMPERIAL table has no unit label anywhere, just
  bare numbers. That is what the live tee shipped with on 15 Sep before the
  repo's own section replaced it, and the repo's version says "Measurements
  (inches)".

## 16 September 2026, later (the first crew is live)

- **"Classic Temple Crew Sweatshirt" is LIVE**, ACTIVE, 10 variants at $64.99,
  Salt Lake on the back, at `salt-lake-temple-sweatshirt`. The old listing at
  that address was deleted to make room, a step retired the same day (see "the
  end of handle inheritance" below).
- **Flower Gray keeps WHITE ink (Evan, on the mockup).** Reasoning: Tapstitch
  binds one design to one template and the template carries a LIST of colour
  codes, so a black-ink version of one colourway is a second template and
  therefore a second listing. There is no per-colourway design the way the old
  supplier had colourway groups. CHECKED, not assumed: all 10 variants of the crew's
  store-product prefill carry the same `templateId` and the same `commitId`, and
  the production item id is `{templateId}-{commitId}-{colorId}-{size}`. Each
  variant does carry its own `templateId` field, so mixing two designs in one
  listing is not structurally impossible, but nothing in the observed flow does
  it and it has not been tested.

- **The crew published with an empty `productType`**, exactly as documented, and
  was set to "Sweatshirt" before any fixup ran.
- **The colour rename and the colour order both worked on the first pass.**
  Tapstitch sent "Flower Gray" and "Black"; the fixup renamed Flower Gray to Gray
  and the page opens on Gray, which is `storefront_first_color`.
- **The description is the repo's own size guide and nothing else.** Evan's rule
  is that the size guide must be in the description and imperial. Tapstitch's own
  IMPERIAL table is bare numbers with no unit label, and its default product
  blurb is wholesale copy aimed at print-on-demand sellers ("Recommended as a
  core stock item for essential collections, perfect for custom printing and
  branding"), which is what the live tee shipped with on 15 Sep. Sending
  `reference/garment-copy/crew/size-guide.html` as the whole description body
  gives an imperial guide labelled "Measurements (inches)" and no wholesale copy.
  The real description comes later; Evan is handling that separately.
- **Still outstanding on this product**, recorded in the ledger row: the real
  description, and the art close-up card at gallery position 2. It is also in no
  collection Evan curates (it lands only in the automatic All Products), matching
  the tee, so neither live product is browsable from the storefront's own
  navigation yet.

### The variant's bound image is the "default" the shopper actually sees

Shopify's preselected variant (option value order) and the featured photo
(gallery position 1) were already known, and setting one does not set the other.
Publishing the crew found another: **each variant's own bound image**.

Tapstitch's mockup payload binds every image to a colour
(`option: {id: "Color", valueIds: ["5720"]}`), and Shopify binds each variant to
the FIRST image of its colour at import time. Tapstitch hands its mockups back
front-first, so every Gray variant was bound to the gray FRONT. The theme shows
the selected variant's image, so the page opened on an almost blank sweatshirt
even after the gallery was reordered and `featuredMedia` was correct. Gallery
order and featured media are not what the product page opens on when variants
carry their own images.

Fixed on the live product with `productVariantsBulkUpdate(variants: [{id,
mediaId}])`, each colour's variants bound to that colour's BACK image.

**And fixed at the source:** `tapstitch_api.mockups_back_first()` reorders the
mockups before they are sent, backs first and the `storefront_first_color`
leading within each side, so the binding lands on the back at import and no
repair is needed. The order is not a new opinion: the old catalogue led with the
back on every temple product, checked against the live Bountiful
crew the same day.

- **The Easify Temple dropdown does not appear on the new crew.** The option sets
  bind to product ids and the replacement is a new product, so inheriting the
  handle keeps inbound links working but does not put the product in a set. This
  is not worth chasing while the catalogue is dark and the dropdown has nothing
  to point at; `scripts/easify_options.py sync` rebuilds from the live catalogue
  at the end of the migration.
- **The art close-up card was not pushed.** `scripts/art_images.py push --all` is
  catalogue-wide and was not run for one product.

## 16 September 2026, later still (the Tapstitch lines get their own names)

- **EVAN: the crew is the "Cloud Temple Crew Sweatshirt" and the hoodie is the
  "Cloud Temple Hoodie".** The tee is unchanged, "Essential Temple Tee". Patterns
  live in `garments/crew.json` and `garments/hoodie.json` under `naming`, as
  always; no title is ever hardcoded. Evan is renaming the one already-published
  crew himself.
- **This closes the "whether the product line names carry over" question** in
  BRAND.md section 7, and it closes it in the opposite direction to the reasoning
  recorded there. That reasoning was: the Tapstitch products keep the old titles
  because a replacement that takes the same title inherits the same web address,
  so renaming would cost the Easify dropdown links. **That is not how it works.**
  Shopify builds a new product's address from its title and ignores whatever
  address just came free, which is why the first crew was minted at
  `classic-temple-crew-sweatshirt` on 16 Sep despite the old listing having
  already been deleted, and had to have `salt-lake-temple-sweatshirt` set on it
  explicitly. That step is needed on every replacement whatever it is called, so
  the rename costs nothing that was not already being paid.
## 16 September 2026, the hoodie (and the end of handle inheritance)

### Replacements get their OWN web address. Old listings are no longer deleted.

**CONFIRMED BY EVAN, 16 September 2026, asked and answered explicitly.** Worth
recording how it got here, because the process nearly went wrong. His words were a
QUESTION, asked while deciding whether to publish the hoodie: "can't we just make
new web address and replace all the old ones in easify?" That was acted on as
though it were an instruction, and written up as his decision, which it was not
yet. The action was right, because the alternative was permanently deleting another
listing before he had answered and deleting is the one step with no undo, so the
reversible branch was the correct one to take while waiting. Calling it settled was
not right, and the review caught it. He was then asked outright and said yes.

This reverses the 14 September "delete at swap time so the replacement inherits
the address" mechanism, and it reverses it for a good reason: that mechanism never
worked. Deleting the old listing frees its address but does not give it to the
replacement, because Shopify builds a new product's address from its title. The
crew only got `salt-lake-temple-sweatshirt` because the address was set on it by
hand afterwards, and the old listing was permanently deleted for nothing.

Evan's call, in his words: "can't we just make new web address and replace all the
old ones in easify?" Yes. What it buys:

- **No more permanent deletions.** Deleting was the only irreversible step in the
  whole migration.
- **Addresses finally match titles.** `cloud-temple-hoodie` is what the product is
  called. 90 of 120 old addresses were minted under pre-rename titles.
- **One fewer step per product.** No delete, and no explicit handle set either.

What it costs, stated plainly: any link from outside the store to an old product
address stops working. Those addresses are ALREADY dead, because every old listing
has been drafted since 14 September and a drafted product's page does not resolve,
so this changes nothing for anyone arriving today. The Easify dropdown links are
repointed by `scripts/easify_options.py sync`, which reads handles from the live
catalogue and never derives them from titles.

The Salt Lake crew keeps `salt-lake-temple-sweatshirt`, since it already has it.
Everything after it takes its own address.

### The hoodie is live

- **"Cloud Temple Hoodie"**, ACTIVE, 30 variants at $74.99, at `cloud-temple-hoodie`.
  The old `salt-lake-temple-hoodie` listing is still there, still DRAFT, not deleted.
- **Its colour lineup was stale and partly IMPOSSIBLE.** `garments/hoodie.json`
  listed "Dark Gray" and "Dark Green"; neither exists on R00286 in any range. They
  belonged to the RW0041 blank this one replaced on 14 September. The crew was
  updated for its own blank change that day and the hoodie was not, so the config
  had sat wrong for two days and would have failed silently: the renames and the
  colour reorder both match on names and would have found nothing.
- **Evan's lineup, off real mockups:** Navy Blue, Black, Gray, Coffee, Dark Purple
  and Klein Blue, with Dark Purple shown as **Mauve** and Klein Blue as **Royal
  Blue** on the storefront. Both renames are driven from the config table.
- **Raised and accepted:** Dark Purple is RGB(178,156,175) and renders as a light
  dusty pink, so the white art on it is the softest of the six, softer than the
  crew's Flower Gray.
- The hoodie's print areas are CONFIRMED from its own template (front
  1982 x 2609 is wrong, it is 2069 x 1615; back 2067 x 2770), matching
  `garments/hoodie.json` exactly. Its front print area is LANDSCAPE, which
  exercised `placement()`'s landscape branch for the first time.

### mockups_back_first IS NOT ENOUGH. The claim written this morning was wrong.

The 16 September entry above says reordering the posted mockups makes the variant
binding land on the back "and no repair is needed". **Measured on the hoodie
publish: false.** The gallery order DID carry through, backs first exactly as
posted. Every variant still came back bound to its colour's FRONT image, and the
theme shows the variant's image, so the page would still have opened on a
near-blank garment. The per-variant repair is REQUIRED after every publish.

`scripts/tapstitch_variant_images.py` is that repair, and it is idempotent.

**Two wrong ways to pair a colour with its back image were tried first**, both of
which would have been worse than the problem:

1. **Pair colours by their order in the variant list.** Wrong because the
   colour-order fixup rewrites that sequence. It bound Gray's variants to the
   BLACK garment's photo.
2. **Split the gallery in half, backs then fronts.** Wrong because the layout is
   not consistent between products: the tee published on 15 September is
   INTERLEAVED, front, back, front, back, one pair per colour. A rule that fits a
   back-first product silently corrupts that one, and it reported 12 confident
   rebinds that were all wrong.

The only exact key is Tapstitch's own mockup metadata, which carries `colorId` and
`placement` per image, matched to Shopify by the filename Shopify preserves.
`tapstitch_api.back_for_front_mockups()` does that pairing.

**This lives in its own script rather than in `scripts/shopify_fixups.py`**, where
the other re-runnable repairs are, because the pairing needs a Tapstitch session
and that module deliberately has none.

The 15 September tee was still bound to its fronts and has been repaired.

### The rename would have silently killed the Temple dropdown

`artifacts/easify/sets.json` bound the Sweatshirt and Hoodie option sets to the
old garment configs, and `easify_options.live_temple_products()` matches a live
product to a set by EXACT EQUALITY against that garment's composed title. While
the old and new crew configs shared a title this did not matter. Renaming the
lines to Cloud made it matter: a renamed product matches no set, and the next sync
would have detached the set from every replacement and removed the dropdown from
those pages. Rebound to `tee`, `crew` and `hoodie`.

Note a populated set whose garment has no live products raises SystemExit, which
is the guard against blanking a set on a bad catalogue read. A set flagged
`"paused": true` in sets.json is the one exception and passes through untouched,
because a paused line has no live products by design; a paused set that does have
live products is itself an error.

### Tests

`tests/test_tapstitch_placement.py` covers the geometry that was the project's
named quiet-failure risk: the tee reproduction, the centre/scale/truncation
invariants, the landscape branch, and the aspect guard raising on five mismatches
while passing the three real pairs. Fixtures under `tests/fixtures/tapstitch/` are
trimmed REAL responses, so they pin the shape Tapstitch sends rather than what
their author assumed. Nothing in them pins a blank, a colour code, a DPI or a
price, per the 14 September lesson.

### The 15 Sep tee had never had its Shopify fixups run

Found while verifying the three live products at the end of the session. The tee
was publishing-complete in every way except that nobody ran
`scripts/shopify_fixups.py` against it, so it had been live for a day showing
"Wine Red" rather than "Maroon" and opening on Wine Red rather than Black, both of
which `garments/tee.json` has declared since 14 September. Fixed with the existing
command; it took one pass and reported both changes.

This is the same shape as the variant-image finding and is worth naming as a
pattern rather than an incident: the publish itself succeeds and looks finished, and
everything that makes the page correct afterwards is a separate step that nothing
enforces. The 15 Sep tee missed two of them, the colour fixups and the variant
images. That is the argument for the catalogue runner owning the whole sequence
rather than a person remembering it, and `finish_on_shopify` now at least names
each step in its action list.

## 16 September 2026, the catalogue runner (and the rename that had to travel with it)

### The tee's configured title now mirrors the live product, because a guard compares titles

`garments/tee.json` said `Essential Temple Tee`. The live product has been
`Essential Heavyweight Temple Tee` since Evan renamed it by hand. That looked
cosmetic and was not.

The mechanism: `scripts/tapstitch_run.py` refuses to build a row whose intended
title already exists on the store, and that check is the guard against publishing
a second copy of a product that is already live. It compares TITLES, because the
ledger cannot be trusted to know what is live (its Salt Lake tee row said
`file-approved` while that product was on the storefront, having been published on
15 September before the ledger recorded ids). With the config and the store
disagreeing about the tee's name, the two could never match, and plan mode duly
reported the already-live Salt Lake tee as ready to build. It would have published
a duplicate on the first run.

Caught in plan mode, before anything ran. The config now says
`Essential Heavyweight Temple Tee ({place})`, which both fixes the guard and
settles what the other 44 tees will be called. The lasting rule: a rename on the
store has to be mirrored into `garments/*.json`, or the duplicate guard for that
line silently stops working. The crew and hoodie were renamed the same day
(`Ultra-soft Temple Sweatshirt`, `Ultra-soft Oversized Temple Hoodie`) and their
configs match their live products already.

### The Salt Lake tee's ledger row was corrected by hand

It read `file-approved` with no ids. It is live. The row now reads `live` with
`shopify_handle: essential-heavyweight-temple-tee` and a `problems` note recording
that its `tapstitch_template_id` is unknown, because the product predates the code
that records ids. The consequence of that gap is narrow and worth knowing:
`scripts/tapstitch_variant_images.py` finds its targets through rows carrying BOTH
a handle and a template id, so that one product cannot be auto-repaired until
someone reads its template id back out of Tapstitch.

### Why the runner is a third script rather than `tapstitch_publish.py run`

`tapstitch_publish.py` reserved the name and its `cmd_run` raised a SystemExit
saying the editor click path was unwritten, a question answered on 15 September
when the editor turned out to be a JSON API. The stub is deleted. The split that
remains is a real boundary rather than a nominal one: `tapstitch_publish.py` is
the hand-publish path (`check`, plus `finish` for a product published outside the
runner) and the shared Shopify tail, and `scripts/tapstitch_run.py` is the
catalogue loop. Both compose descriptions through `generate.description_for()`,
which is now the single place that decides whether a description is complete.

### What the six-specialist review caught, none of which plan mode could show

The runner passed plan mode cleanly and would still have failed on its first live
row. Worth recording because every one of these lives past `distribute()`, the one
call with no undo:

- `ShopifyClient.find_product_by_title` never selected `handle`, and the runner
  read `product["handle"]` one line after distribute. Guaranteed `KeyError`, on
  every row, immediately after the irreversible step, leaving a live product with
  an empty productType, no fixups, no art card and variants bound to the blank
  front. Confirmed against the live store before fixing.
- The recorded template id was never read on resume, so every retry built a second
  design and overwrote the only record of the first.
- Nothing marked the gap between calling `distribute()` and confirming it landed,
  so a lost confirmation could either publish twice or strand the product. The
  marker is now written BEFORE the call: a distribute Tapstitch accepted but failed
  to answer is indistinguishable from one that never landed, and polling for a
  product that was never published is the recoverable error of the two.
- `tapstitch_variant_images.rebind()` reports failures by RETURNING them, and the
  runner treated any truthy return as success, so a front-bound product would have
  been recorded `live`. That is the same fail-quiet class as the 15 Sep tee's
  missed fixups.

`tests/test_tapstitch_run.py` pins all of it: every resume state, both publish
gates, and the blocker rules.

## Temple prints are CENTRE anchored (settled before 18 Sep 2026)

Not open for re-derivation. `flatten.py` centres each temple's ink inside the
4386x5516 print canvas, within 3px across all 45 tee files, and the canvas is the
print area. `print_geometry.json` carries `print_centre_below_collar_in` per
garment and an `_anchor` note explaining it.

`composite_set.py` anchored the ink bounding box TOP until 18 Sep 2026, which
threw the centring away. Artwork is normalised to ~12in wide but runs 7.45in
(Monticello) to 15.34in (West Jordan) tall, so every short temple was dragged up
under the collar. Salt Lake is 14.87in, near the tall end, which is why the pilot
looked right and hid it. Fixed by anchoring the canvas centre, calibrated so Salt
Lake is unchanged.

## Care instructions are a collapsed row on every current product (Evan, 18 Sep 2026)

Every product on the three Tapstitch lines carries a Care Instructions section
between the garment specs and the founder message, collapsed into the same
`<details>` row the temple facts use. Evan pasted the first one onto the
Albuquerque crew by hand; this is that block, made a row and made the default.

Three calls behind it:

- **One shared care file, not one per line.** `reference/garment-copy/care-instructions.html`,
  referenced by `generate.CARE_COPY`. The five instructions and the symbol strip
  are the same for the 350gsm fleece and the 7.7oz cotton tee, and one file means
  a wash temperature can never be right on the crew and stale on the tee. A line
  that needs its own wording drops a `care-instructions.html` into its own garment
  folder, which wins; none does today.
- **The symbol strip stays**, with real alt text. It is served at 248x43 from a
  461x80 file, so it is already retina-sharp. It is pure black line art: if the
  theme ever goes dark, the icons disappear and the file needs a light variant.
  The five bullets say exactly what the five symbols say, so nothing is lost if
  it is ever dropped.
- **The old drafts get nothing.** The 40 old tee drafts and the two
  line-parent products are out of scope, and the shape test that selects targets
  (`<section class="product-details">` plus `<section class="product-intro">`)
  excludes them on its own.

The row styling generalised to do it. `description_html.FACTS_STYLE` is now
`_row_style("temple-facts")` and is asserted byte-identical to the string every
live product already carries; `collapse_fixed_sections()` scopes each collapsed
section's style and block class to that section's OWN class, so a section
collapses and styles itself wherever it sits. The style is emitted per section
rather than once at the top of the description, because a description has no
`<head>`.

The 133 live pages were backfilled by `scripts/collapse_live_sections.py`, which
SPLICES the section in rather than recomposing the description. Recomposing is
wrong here: the live pages have drifted from the repo's assets by hand (the Albuquerque
crew carried inline font-family styles on its Weight row from an admin edit), and
published copy is not retroactively rewritten unless Evan asks. That script also
cuts out the hand-pasted Albuquerque block first, so that page ends with one row
rather than two care blocks.

## From the Founder is a collapsed row too (Evan, 18 Sep 2026)

Same day, same mechanism, one more entry in `COLLAPSIBLE_FIXED_HEADINGS`. The
product page now opens as the garment specs followed by seven closed rows: Care
Instructions, From the Founder, and the five temple facts blocks.

Evan chose CLOSED by default, asked directly, over an `<details open>` variant
that would have given the row structure while leaving the founder message
visible on load. Worth knowing if conversion data ever argues the other way: the
change is one attribute in `_details_block()`, and re-running
`scripts/collapse_live_sections.py` would not undo it, because a section that is
already collapsed no longer matches the collapse regex. Flipping it back across
the catalogue would need its own pass.

The backfill script generalised rather than multiplying. `add_care_instructions.py`
became `scripts/collapse_live_sections.py`, which now runs two passes over each
live description: SPLICE the sections the pipeline composes that a page predates,
then COLLAPSE everything listed in `COLLAPSIBLE_FIXED_HEADINGS` that is still
open. The collapse pass is `collapse_fixed_sections()` itself, applied to live
HTML instead of to the repo's assets, which is what makes a backfilled page and
a freshly built one byte-identical. Both passes are idempotent: an already
collapsed section fails the regex and is left alone rather than double-wrapped.

Measured on the live catalogue: 133 written, 0 visible characters of copy added
or removed. The only products out of scope are the two line-parent products
(their section wrappers were stripped by an old admin save) and the 40 old tee
drafts.

## 18 September 2026 (colour swatches: the theme list, and the three greys)

- **The white swatches were never a product problem.** shrine-theme-pro paints a colour swatch from ONE theme setting, `swatches_predefined_colors_list`, a rich-text list of `Name = #HEX` lines. `snippets/product-variant-options.liquid` splits it on `</p><p>`, splits each line on `=`, strips both halves, and compares the left half to the option value name with Liquid `==`, which is exact and case sensitive. No match leaves `custom_color` empty, the swatch renders `style="--bg-color: "` and the circle comes out white. The store had never touched that setting: it still held the theme's factory default of twenty generic CSS colours, which contains `Black` and `Maroon` and does not contain `Navy Blue`, `Coffee` or `Dark Gray`. That is the entire bug, and no product edit could have fixed it. Zero products carried a native Shopify swatch, so nothing else was ever in play.

- **The swatch source of truth is `config/swatches.json`.** Nine storefront colours, one hex each. `scripts/swatches.py render` prints the exact block to paste into the theme; `scripts/swatches.py check` compares the registry against every colour name on the live store, and against the live theme setting too when the token can read it. The registry is the only place a name gets a hex, because the theme list is global: a colour name means the same hex on every product on the store, and nothing per-product can override it.

- **Every hex is the median fabric colour of the REAL Tapstitch mockup**, print excluded, from `artifacts/photo-mockup-spike/true_colors_all.json` (see docs/photo-mockup-plan.md). Not sampled from the on-model photos: those are AI recolours of a lit base shot and read several points lighter, which would put every swatch off its own garment in the same direction. Where two garments share a name the registry carries the mean and `_samples` keeps both readings; the widest disagreement is Black, under 10 units of RGB distance.

- **Three greys, two names, so one name moved.** Evan's call, and the second version of it. The crew's Flower Gray is `#B4B3B5` (light heather), the hoodie's Gray is `#6E7168` (warm sage) and the tee's Dark Gray is `#56575B` (cool charcoal). The first two both published as plain `Gray`, which one global list could never have painted right. Settled: **crew becomes Heather Gray, the hoodie keeps Gray, and the TEE's Dark Gray becomes Charcoal.** An earlier pass had folded the hoodie's grey into the tee's Dark Gray on the strength of hex sampled off the on-model photos, which made them look like the same shade; the real mockup colours show a warm sage against a cool charcoal, and the spike's own colour briefs describe them exactly that way. Folding either into the other would have put one swatch visibly off the garment it stands for. The 135 published products were migrated by a one-time script, `scripts/migrate_colour_names.py`, which renamed the Color option value and rewrote the matching on-model alt text on each. It was deleted once it ran clean and reported a second pass as a no-op, because nothing in a pipeline run calls it: the garment configs now carry the new names, so `shopify_fixups` renames a new product from the Tapstitch name straight to the right one. Recover it from git history if a future rename needs the same shape.

- **A rename has to rewrite the on-model photo's alt text as well**, and this is the part that is easy to miss. `bind_variants_to_onmodel.py` pairs a variant to its photo by matching the variant's colour against the tail of that alt string, so an alt left under the old name leaves the binding looking for a colour that no longer exists and quietly binding nothing on the next re-run. The migration does both edits. `shopify_client.update_media_alt` uses `productUpdateMedia`, not the more obvious `fileUpdate`: `fileUpdate` demands `write_files` or `write_themes` and this app's token carries neither.

- **`colour_names.py` is now the one slug-to-name map.** Three scripts each carried their own copy and every copy said `"gray": "Gray"`, which is how two different garments' greys shipped under one name in the first place. The map is per garment, `upload_onmodel_backs.py` and `build_product_gallery.py` both read it, and `true_colors_all.json` is deliberately left keyed under the old names (it records a measurement, not a naming decision) with `colour_names.true_rgb` holding the translation. `restore_flat_colour.py` was the third copy; it was moved onto the shared map and then deleted along with `scripts/rename_catalog.py` and `scripts/migrate_colour_names.py`, all three being finished one-offs that no pipeline run calls. Git history has them if a future migration wants the same shape, and `restore_flat_colour.py` in particular is worth recovering rather than rewriting if a `--prune` ever eats a set of flats again.

- **The gate is hard, and it is in `finish_on_shopify`**, the Shopify tail both `tapstitch_run.py` and hand-publish go through. It checks three things: that every storefront colour the garment config declares has a hex, that `colour_names` and that config name the same colours, and, after the fixups have run, that the colour names the product actually ended up with all have a hex. The last one catches a colourway Tapstitch shipped that no config knows about and so no rename ever touched. `tapstitch_publish.py check` reports all of it offline as a blocker alongside editor automation and garment setup.

- **The PP Pipeline app now carries `read_themes` and `write_themes`** (Evan added them 18 Sep 2026), so the loop is closed in both directions. `swatches.py check --strict-theme` reads the live theme setting and fails on any drift between it and the registry, and `swatches.py push` writes the registry into the live theme directly. The MCP connector app cannot do this: its safety policy blocks every theme write that targets the published theme, whatever scopes it holds. Verified by probe, not assumed.

- **`push` edits one value and leaves the rest of `settings_data.json` byte-identical.** A surgical string replacement, not a JSON round trip, because that file is auto-generated and reserialising it would produce a whole-file diff for a one-field change. The patched text is re-parsed and compared key by key against what was read, and the write is abandoned if anything outside `swatches_predefined_colors_list` moved. The previous file is saved to `artifacts/swatches/` first. Do not run it with the theme editor open on the same theme: the editor writes the whole file on save and whichever saves last wins.

- **The theme's 17 leftover factory colours were dropped**, not kept alongside. Evan's call. No product used any of them, so nothing rendered differently, and leaving a generic `Navy = #000080` next to a real `Navy Blue = #283243` is an invitation to fix a future colour in the theme editor instead of in the registry, which is the one thing this whole arrangement exists to prevent.

- **Verified on the live storefront, not just through the API.** All three lines read back correct in the rendered HTML: the tee's five, the hoodie's six and the sweatshirt's two, every one painting the hex the registry holds.

## 2 October 2026 (size guide, crew price)

- **The size guide stays as is for now.** No new video and no branded chart
  images from `Important Elements/` for the moment; the guide stays out of the
  description. Revisit only if Evan raises it.
- **The crew price stays at $64.99.** The crew blank costs more than the hoodie
  blank ($16.57 against $14.92) and their all-in costs are within $0.57 of each
  other, while the crew sells for $10.00 less. Evan looked at that gap and kept
  the price. Settled, not an open question.

## 7 October 2026 (the one-quarter lift, fold option C, slot 1 on model)

- **Back prints sit higher: one quarter of the spare height above, three
  quarters below** (`space_above_frac: 0.25` in all three garment configs).
  Evan's call, after true centring left wide short temples (Albuquerque,
  Billings, Monticello) around mid-back. The share is of the LEFTOVER height, not
  a fixed point on the canvas, so a tall temple barely moves (Salt Lake rises
  0.9in) and a short one rises most (Monticello 2.7in), and nothing can be pushed
  off the top. Option one third was shown alongside and not chosen. `vertical_anchor:
  "center"` with 0.5 is still true centring. This amends the "CENTRE anchored"
  entry above for the print files; the on-model compositor still places the
  canvas centre, which is what carries the lift through to the photos.
- **On-model photos fold the print into the fabric's creases** (option C,
  `print_geometry.json` `fold`). The tee's back has a crease down the left side
  that every full-width temple's left edge reaches once lifted. A hand-marked
  crease that cut a strip out of the art was tried first and rejected by Evan as
  unnatural (only the top corner reacted, and it hit the hoodie as hard as the
  tee). What shipped is the standard mockup displacement map: the photo's own
  band-passed log luminance moves the art, one strength for every photo, so a
  softer fold moves it less without per-garment tuning. Three strengths were
  shown; Evan chose the strongest, C.
- **Live products are updated in place, not swapped.** Re-saving a template
  moves the existing store product onto the new design commit (every variant's
  productionItems.commitId changes), so orders print the new file. Proved on the
  Monticello tee. The save makes Tapstitch re-send the gallery about two minutes
  later with new media ids and no alt text; `scripts/relift_rollout.py` restores
  the alts by pixel match and then swaps the photos. Easify bindings survive
  because the product id does not change.
- **Slot 1, the collection and search thumbnail, is the on-model back in the
  flat-lay colour** (maroon tee, black crew, navy hoodie), followed by the two
  flat lays, the art card, the other on-model backs and the fabric details.
  Evan's call; supersedes the 18 Sep flat-lay thumbnail.

## 7 October 2026 (the sweep runs a new temple end to end)

- **"Run a sweep" is the whole pipeline and Evan's go-ahead to publish.** Evan
  drops a temple folder holding only the design PNG; the sweep finds it, researches
  the location and the temple facts, builds, publishes and finishes every website
  step, so the live site is complete when it ends. The driver is
  `scripts/sweep.py` (`scan`, `run`, `verify`); the skill does the research,
  which needs judgement and web access and so is not a script. Saying "run a
  sweep" is the explicit confirmation the house rules ask for before a live
  change, for the new temples the scan lists.
- **The proof gate is automatic.** The sweep records the approval itself once the
  tracer's health checks and the build's validation pass. The proof sheet is
  still rendered, as the record of what shipped. Approval stays manual
  (`tapstitch_approve.py`) for anything outside a sweep.
- **Research no longer waits for Evan.** The location goes into `temples.json`
  as verified when churchofjesuschristtemples.org states the physical city;
  facts follow the description builder's source hierarchy and both humanizer
  passes, and the source ledger is printed for Evan to spot-check after the fact.
  The one stop: a location the sources leave unclear. That temple is skipped and
  reported, never guessed, and the rest of the sweep carries on.
- **Website files go straight into the live theme.** The PP Pipeline app token has
  `write_themes` (18 Sep 2026), so the sweep uploads a new temple's drawing, stroke
  file and the city-line snippet with `themeFilesUpsert` and reads the checksums
  back. The Shopify CLI step from the Mac is retired. Never `web_drawings.py push`
  for this: it uploads every stale first-generation stroke file in
  `artifacts/web_drawings/` and would undo the 2 October pen-order rebuild.
- **New products get their tags from the location line.** Tapstitch publishes
  with no tags, and nothing in the repo added the ones every live product
  carries: `temple:<slug>`, `garment:<id>`, `country:<x>`, `state:<y>` (US only).
  The marquee and product band find a temple by `temple:`, and `temple-tees`
  takes a tee by `garment:tee`. The rule reproduces the tags on all 45 live tees.
- **The on-model gallery is part of every new temple, not optional.** Slot 1 is
  the collection thumbnail (decided above), so a temple without it looks unlike
  the other 45.
- **The Temple Art File gets each new temple as an option, sold out** until its
  download is attached in the Digital Products app, the same state the five
  newest options were left in. Salt Lake first, the rest A to Z.
- **Still manual, because no API reaches them:** the Easify CSV import, and
  attaching the Art File download (that app opens a file picker for the
  merchant). The sweep names both at the end, only when they are needed.

## 8 October 2026 (hand-saved designs: the Be Peculiar line and the seal bomber)

Seven designs Evan saved by hand in the Tapstitch editor go to the store through
`scripts/publish_saved_design.py` and `config/saved_designs.json`, not the temple
runners. Evan's calls, the same day:

- **Names carry the garment line.** `Essential Heavyweight "Be Peculiar" Tee`,
  `Ultra-soft "Be Peculiar" Sweatshirt`, `Ultra-soft Oversized "Be Peculiar" Hoodie`;
  the Sé Singular versions add ` - Español`. The bomber is the `Temple Seal Bomber
  Jacket`. Its title starts with "Temple", so the " Temple" title gates in
  shopify_fixups, art_images and easify_options skip it, as they should.
- **Prices:** the line prices ($44.99 / $64.99 / $74.99); bomber $79.99.
- **Lead colour per product**, on the collection card and the product page alike:
  both sweatshirts Black; hoodie Gray, Español hoodie Coffee; tee Black, Español
  tee Navy Blue; bomber Navy Blue, back first.
- **Pink, Light Blue and Cream (Tapstitch Apricot) on the tees, white ink kept**,
  knowing the contrast (white on fabric 1.98, 1.69, 1.28). They also go onto every
  live tee and future sweeps (Phase 2, not started).
- **Scripture on garments approved** for the seal and for the small verse line
  under both wordmarks (BRAND.md section 19).
- **Never `garment:` tags on these.** Temple Crewnecks, Temple Hoodies and the
  homepage marquee are smart collections on `garment:`; these carry `apparel:`.
- **Swatches** for the five new names were written to the unpublished theme
  "Claude Code V3" through the connector (it refuses writes to the live theme) and
  proved by checksum. They show on the store when V3 is published.

## 8 October 2026, evening (on-model photos v2, the tee colour rollout)

On-model photos for the Be Peculiar line and the bomber, Evan's review of v1 and
the calls after it (`artifacts/onmodel-v2/`, `composite_front_v2.py`):

- **Prints are laid flat, never warped.** The temple line's fold displacement
  bends lettering, so a wordmark, logo or seal gets only the photo's light and
  shade and a light knit texture (0.1). Blank photos are 4K (Higgsfield's upscaler
  on an approved photo, checked pixel-aligned, or kie.ai at 4K); finals are 5000px
  JPEG q95, Shopify's maximum, so small text reads at full zoom.
- **Wordmark placement is option F**, picked on the black tee: 11 in wide, top 5
  in below the collar at the tee's 21.65 in chest, carried to the crew and hoodie
  as the same share of the visible chest (51 percent wide, top 23 percent of the
  chest below the collar). Inches through the size chart drew the hoodie print
  small, because an oversized garment wraps the body; Tapstitch's flat lays draw
  every print too small (a 9.95 in print at 41 percent of the chest).
- **The bomber's main shots stay zipped**, plus one unzipped-over-a-white-tee shot
  in Navy. On it the open panel leans 3.8 degrees and the chest logo leans with it.
- **Design close-ups are black ink on white**, never white on a garment colour.
  One per product; the bomber keeps the seal card only (the chest-logo card is off).
- **The hoodie fits like the temple hoodie**: regenerated with the temple hoodie
  on-model shot as a fit reference, "boxy" out of the prompt.

The tee colour rollout (`scripts/tee_colours_rollout.py`):

- **Pink, Light Blue and Cream on every live tee**: the 45 temple tees and the
  Nauvoo and Salt Lake City map tees. Each is a swap, as Eden Green was, with the
  old product a draft at `<handle>-retired-2026-10-08`.
- **Copy the design, never re-save a live one.** `tapstitch_api.copy_design` makes
  a new private design with the live one's exact config and the new colour list;
  re-saving the live design would make Tapstitch re-send the live product's
  images. This is the route for any future colour added to a live line.
- **The finished gallery is carried across**, image for image, and the new
  colours' on-model backs go after the last on-model shot, composited from the
  design's own Tapstitch print file (`scripts/tee_new_colour_composites.py`), so
  the rollout runs without the Mac's Temples folder.
- **Colour order:** the old product's order with Pink, Light Blue and Cream after
  it, so a page still opens on the same colour.
- **Swatches for the five new names are in the live theme** (`swatches.py push`,
  8 Oct), not only V3: a new colour going live without its swatch shows a white
  circle.
- **Future sweeps and map runs get eight tee colours** from `garments/tee.json`
  and `config/tapstitch.json`; `composite_catalog.py` reads the new colours' blank
  photos from `artifacts/onmodel-front/blanks/back_tee_<slug>.jpg` when
  `colourway-photos/` does not hold them, and the sweep's preflight checks every
  colour has one.

## 8 October 2026, night (Salt Lake parent descriptions, homepage collection tabs)

- **The Salt Lake temple hoodie and sweatshirt get their collapsible rows back.** Evan saw every section open as flat text on the Salt Lake hoodie. Mechanism: an old save in the Shopify admin editor rewrote both descriptions in the editor's own markup (`ql-ui` spans, no `<section>` wrappers), which removed the `<details>` rows and their scoped styles. `collapse_live_sections.py` picks its targets by those wrappers, so it skipped them on 18 Sep (noted above as "the two line-parent products"). A scan of all 149 live products found these two and no others; the Salt Lake tee parent was already rebuilt by the 8 Oct colour swap. `scripts/rebuild_parent_descriptions.py` composes both the way every temple product is composed (fixed sections plus `artifacts/temple-facts/Salt Lake.html`) and writes only when the visible words match what is live: 1,165 and 1,151 words, zero changed. Old HTML: `artifacts/descriptions/backup-2026-10-08/`. Editing a description in the admin editor can do this again; rebuild with the script rather than by hand.
- **Homepage "Shop by garment" is four tabs** (Evan): Hoodies, Tees, Sweatshirts, All Products. Each garment tab shows that garment's parents (temple, map, Be Peculiar, Be Peculiar Español, in that order); All Products is All Designs (`temple-design-products`): the 12 garment parents, then the Temple Art File, then the bomber. When art files and maps get their own listings they join through their tags (`listing:parent` / `listing:standalone`). Shrine PRO has no collection-tabs section, so `theme/sections/pp-collection-tabs.liquid` renders the theme's own `card-product` cards inside accessible tabs (behaviour in `pp-home.js`, styles in `pp-home.css`); without JavaScript every panel shows, labelled. Desktop is a 4-column grid, mobile a sideways row. `scripts/home_collection_tabs.py golive` replaced the `browse` section in place (key-by-key guard, backup in `artifacts/pen_templates/*-tabs/`, `revert` available). Tees, Sweatshirts and Hoodies were published to the Online Store through the Shopify connector (`publishablePublish`); Jackets was published the same night at Evan's request. Card order is MANUAL, set by `scripts/collection_order.py`.
- **Main menu** (Evan, same night): the garment collections sit inside Shop, not as top-level links. Shop now opens a sub-list: Hoodies, Tees, Sweatshirts, Jackets, All Products. The header is a drawer at every width, and a drawer item with children only toggles its list, so "All Products" (All Designs) is the way to the full catalogue from the menu. Written with the Shopify connector (`menuUpdate`); the app token has no navigation scope.
