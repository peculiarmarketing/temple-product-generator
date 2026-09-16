# Decision Log

Decisions Evan has made, with dates. These override or refine the spec (docs/temple-catalog-generator-plan.md).

## 17 August 2026 (Phase 1 gate and Phase 2 gate)

- **Generator architecture: duplicate-then-edit.** Evan duplicates the template product in the Printify UI (carries mockup selections, personalization config, shipping options); the generator PUTs the design swap. Proven in the duplicate-flow experiment. API-only creation is rejected because mockups, personalization, and shipping are read-only via API and default wrong.
- **Text layers are UI-only.** Any API write to print_areas wipes them, and they cannot be posted or updated. Location line is a generator-rendered image (Alata font, from the manifest's location string). Manual override honored: a `*location text*{black|white}*` file in the temple folder wins over auto-render. The personalization date layer on With Date products is re-added by hand in the Printify editor after generation.
- **Resolution rule.** Uploads bump the SVG's declared width/height attribute to 4096 in memory (files on disk never modified). Proven to clear Printify's low-DPI warning. The live catalog's 2048 px assets are a Phase 5 backfill item.
- **Art source of truth: `Temples/{Name}/` folders.** Manifests name art files explicitly (folder naming is inconsistent).
- **Spacing constants** (see spacing_defaults.json): measured from the live catalog and approved via previews. Location text: 0.74 in tall on base products, 0.38 in on With Date. Divider on With Date: **2.0 in** (changed from the live products' 3.0 in at the Phase 2 gate so it does not read as an underline).
- **With Date logo placement:** auto-pick the emptier top corner, near the temple, never flush to the print area edge. Manifest override available per temple.
- **Sizing across shirt sizes: proportional** (design scales with the garment, matching the live catalog). Not physical-inch-consistent.
- **Tracer standard going forward: drop `--square`.** New temples are traced `--trim --drop-label`; files come out at the drawing's natural aspect. Existing square files stay and work identically (the layout engine measures ink, not frames). NOTE: the live tracer skill in claude.ai still documents `--square` in its examples; update it there on the next skill edit.
- Both text-size conventions and the base vs With Date layouts are separate layout profiles: `back_stack` and `back_stack_dated`.

## 17 August 2026 (Phase 3)

- **Location line rule: the temple's PHYSICAL city, not its name-city.** Confirmed from the live catalog: Washington D.C. Temple prints KENSINGTON, MARYLAND; Provo City Center prints PROVO, UTAH. Format: all caps, comma, spelled-out state, country for international.
- **temples.json is the location dataset.** Folder name maps to official name and verified location line. The 14 finished temples were extracted from the live products themselves. A folder with no manifest gets one scaffolded automatically from this dataset; unverified entries hard-stop with instructions rather than guessing. New temples: the Phase 4 skill researches the physical location (churchofjesuschristtemples.org as the reference), appends the entry, and asks Evan only when uncertain.
- **New-temple flow:** drop a folder with two SVGs into Temples/. Everything else (manifest, location text, layout, upload, product) is derived.
- **Dress rehearsal passed.** Generated Logan Temple Tee (from a UI duplicate of the live product) matched the hand-built one in the editor with all mockups preserved and high-resolution art. Evan approved.
- **Publishing stays manual for now.** The generator produces complete unpublished drafts; Evan clicks publish in Printify. Automated publish (with the 200-per-30-minutes throttle) is deferred to backfill planning.
- **Personalization-optional is parked.** Folding With Date into base would need a design that looks right with and without the date line; Evan is not designing that now.
## 17 August 2026 (Phases 4 and 5 closed)

- **Recurring runs are manual.** No scheduled task. Evan triggers the sweep in a session ("run the sweep"); the project skill handles it. Rationale: generation depends on duplicates Evan makes by hand and publishing is manual, so a schedule saves only the typing.
- **No catalog backfill.** Evan decided the existing hand-built products stay as they are. `--in-place` remains available as a tool for one-off regeneration if ever wanted, but there is no backfill campaign, which also retires the publish-throttle concern.
- **Catalog gaps found by the first coverage report:** seven missing With Date tees (Nauvoo, Provo City Center, Salt Lake, San Diego, Saratoga Springs, St. George, Washington DC). Evan is making seven With Date duplicates; one sweep fills all seven.

- **Descriptions are written to Printify pre-publish.** The pipeline session researches each temple once (same methodology, sources, and myth screening as the claude.ai description skills, which we hold verbatim in reference/skills/), saves the facts fragment to `Temples/{Name}/temple-facts.html`, and `scripts/write_description.py` applies fixed sections plus facts to all the temple's generated products. Products publish complete. With Date products get descriptions (the claude.ai skills never matched their titles). The claude.ai description event stays untouched; its post-publish overwrite of the same products is harmless churn until Evan retires it. Generator also sets fixed intro plus size guide at swap time so a draft never carries the donor temple's facts.

- **No designated template products; any duplicate works.** Evan clarified his "templates" are Printify editor design-templates (saved layer arrangements), which the generator replaces entirely. What the pipeline needs from a duplicate is only the API-invisible settings, and any product of the right garment carries them. The generator claims any unclaimed "Copy of ..." product matching the garment's blueprint and provider; "With Date" copies are reserved for the dated line (personalization config); "front logo" copies are ignored (tests). Evan's editor design-templates become unnecessary for generated products.

## 17 August 2026 (Easify option sets)

- **The Easify temple dropdowns are pipeline-managed via CSV.** The canonical option-sets CSV lives at `artifacts/easify/option-sets.csv` (committed); Evan's Easify app is downstream of it. `scripts/easify_options.py sync` reconciles it against the live Shopify catalog; Evan imports the file in the Easify app by hand, the same way publishing is manual.
- **The temple label is the reconciliation key; URLs follow labels.** A row whose label says Provo gets Provo's live URL, which is how the swapped Provo/Provo City Center links were corrected. Handles are always read from Shopify, never derived from titles (the Salt Lake tee lives at `salt-lake-city-temple-tee`).
- **Option values are never auto-deleted.** Rows the sync cannot confidently bind, or whose product left Shopify, are kept and reported. `option_set_products` is rebuilt from the live catalog each run.
- **The With Date tee line got its own new set** (Evan's choice), titled "Tee - With Date", cloned structurally from the Tee set. New sets carry placeholder ids (900001+) until the one-time post-import `reseed --export` adopts Evan's fresh export with the real ids.
- **Approved data fixes applied by the first sync:** Salt Lake and Washington D.C. tee URLs, the Provo/Provo City Center swap in Sweatshirt and Hoodie, and the "San Deigo" spelling in both.

## 18 August 2026 (auto-publish)

- **Base products auto-publish via API; dated products stay manual.** Evan reversed the "publishing stays manual" decision for non-personalizable products. `scripts/publish_drafts.py` publishes never-published drafts that pass every gate: not "Copy of", not "(front logo)", not With Date or personalizable (layers in sales_channel_properties), description carries the temple-facts section, Economy shipping enabled. With Date products keep the manual flow because Evan must re-add the date text layer first.
- **The publish API is sync flags only.** POST publish.json accepts seven booleans (title, description, images, variants, tags, keyFeatures, shipping_template), all true for first-time publishes. Shipping options and variant visibility are not API-settable; they ride the UI duplicate. `is_economy_shipping_enabled` is read-only via API and is verified as a publish gate. Variant visibility ("only show in stock variants") is a per-product Publishing settings choice in the Printify UI, not readable or writable via API.
- **Printify's publish status lags the real push.** The Shopify product goes live in 1 to 4 minutes, but the Printify product's `external` field and lock can take 10+ minutes to update. The script therefore confirms against Shopify by exact title (creds from .env) and treats that as authoritative.
- **Verified live on Brigham City (18 Aug 2026):** Tee (brigham-city-temple-tee, 52/52 variants), Sweatshirt (brigham-city-temple-sweatshirt, 36/36), Hoodie (brigham-city-temple-hoodie, 27 of 30 enabled variants on Shopify because exactly the 3 out-of-stock ones were hidden, proving the variant-visibility setting rides the duplicate through an API publish). All active, mockups and descriptions intact, art cards and Easify rows added by the normal post-publish steps.

## 18 August 2026 (date-layer automation)

- **Date layers are added by script.** `scripts/add_date_layer.py` drives the Printify editor via Playwright over CDP to add the personalization date text layer to unpublished With Date drafts, positioned from the divider layer read via GET plus the dated constants in `spacing_defaults.json`, settings from `config/date_layer.json` (canonical per Evan's 18 Aug gate). Runs only when Evan invokes it, never publishes, touches nothing else. The manual editor flow remains the fallback; the off switch is not running it. Editor click path and calibration live in `docs/discovery/2026-08-date-layer-editor-notes.md`; a Printify editor redesign means a repair session against that document. Session model: Evan logs into a real Chrome (dedicated profile, debug port 9222) once via `scripts/printify_login.py` because Cloudflare blocks automation-launched browsers; scripts attach over CDP.
- **Verified dated drafts publish via API (Evan's 18 Aug evening reversal of the never-publish-dated rule):** `publish_drafts.py` accepts dated or personalizable drafts when the full date-layer verification passes, then all pre-existing gates still apply. Unverified dated drafts stay held.
- **New drafts default Economy shipping OFF** (observed 18 Aug; contradicts the earlier belief that shipping rides the duplicate). The API field is read-only, so Evan flips Economy on in the UI before publish; the publish gate correctly holds economy-off drafts. UI automation of the toggle was designed (plan amendment Task 7) and deferred by Evan.

## 19 August 2026 (economy gate dropped)

- **Economy shipping is no longer a publish gate (Evan's 19 Aug decision, supersedes the 18 Aug hold-on-economy-off rule).** The Ephraim sweep held all four drafts on the economy gate, blocking unattended auto-publish. Evan chose to drop the gate rather than automate the toggle (Task 7 stays deferred): `publish_drafts.py` now publishes drafts with Economy off and prints a note ("eligible, note: economy shipping is off") for each one, so Evan can flip the toggle in the Printify UI whenever, post-publish. Consequence accepted: a product can be live offering only Standard shipping until he flips it. `is_economy_shipping_enabled` remains read-only via API.

## 22 August 2026 (catalog rename, parent products, Shopify fixups)

- **Product titles lead with the garment line, temple in parentheses.** New
  patterns, one per garment config (`garments/*.json`, key `naming.title`):
  `Pillar Temple Hoodie ({place})`, `Classic Temple Crew Sweatshirt ({place})`,
  `Essential Temple Tee ({place})`, `Essential Temple Tee – with personalizable
  date ({place})`. En dash, lowercase after it; that exact wording is
  canonical and supersedes the hyphen and Title Case variants Evan tried by
  hand on the Salt Lake and Layton products.
- **Salt Lake is the parent temple** (`config/catalog.json`, key
  `parent_temple`). Its four products carry the bare garment title with no
  parenthetical (`naming.title_parent`) and stay ACTIVE on Shopify. Every
  other temple's product is set to Shopify status UNLISTED, so the storefront
  shows one listing per garment line and shoppers reach the rest through the
  Easify Temple dropdown on the parent page. Unlisted products keep working
  URLs, so every dropdown link still resolves. `publish_drafts.py` unlists
  each newly published non-parent product automatically.
- **Title parsing runs backwards now.** The place token is parenthesized at
  the end, so reading a title back to a temple is an exact lookup rather than
  the longest-prefix guess the old `{place} Temple Tee` titles needed
  (`art_images.match_temple`). The nesting half of `check_title_collision` is
  retired for the same reason: parentheses make Provo vs Provo City Center
  structurally unambiguous, and the parent's bare title is a prefix of every
  child title by design, which the old rule would have flagged 117 times.
- **`limited edition` replaces `(front logo)` as the one-off marker.** Evan's
  hand-built one-offs are now `Essential Temple Tee – Limited Edition
  (Nauvoo)`, `Pillar Temple Hoodie – Limited Edition (Nauvoo)`, and `Classic
  Temple Crew Sweatshirt – Limited Edition (Nauvoo)`. The pipeline never
  claims one as a duplicate, never auto-publishes one, and never gives one a
  dropdown row.
- **The dated tee description opens with a Personalization section.** Evan
  wrote it; it is held verbatim at
  `reference/description-blocks/personalization-intro.html` and named by
  `description_prefix` in `garments/cc1717-dated.json`. This is a new
  directory on purpose: the vendored skill exports under `reference/skills/`
  stay verbatim.
- **Hoodie colorway "True Navy" is renamed to "Blue Jean" on Shopify.**
  Printify labels the CC1567 hoodie colorway True Navy, but it does not match
  the True Navy on the CC1717 tee or the CC1566 crew; it matches their Blue
  Jean. Evan's call: Printify has it wrong and the storefront should read Blue
  Jean. Shopify-only, so Printify order line items still say True Navy. Any
  Printify republish re-syncs variants and pushes the old name back, which is
  why `scripts/shopify_fixups.py hoodie-color` is re-runnable and part of the
  end-of-run sequence rather than a one-shot.
- **Moss is the default variant on the dated tees**, declared as
  `default_colorway` in `garments/cc1717-dated.json`. `publish_drafts.py`
  reports a wrong default before publishing and sets it right after, and
  `scripts/default_variant.py` does the same in bulk. The size is preserved:
  a product defaulting to "True Navy / L" moves to "Moss / L".
- **`is_default` is writable through the Printify API**, measured 22 Aug 2026
  against a live dated tee: the PUT was accepted and prices, enabled state and
  variant count all came back unchanged. The Revision-2 spec
  (`docs/temple-catalog-generator-plan.md`) listing it read-only was wrong, and
  `WRITABLE_VARIANT_KEYS` now includes it.
- **Printify's default variant does not drive Shopify's.** Measured the same
  day: the Salt Lake dated tee Evan had already set to Moss showed the same
  Shopify variant order (Brick / S first) as every product still defaulting to
  True Navy. Setting the Printify default moves Printify's own default, which
  mockup selection follows; the storefront is a separate lever.
- **The storefront's opening variant is the Color option's first value.**
  Shopify preselects variant position 1 and computes position from the option
  value order, so `productOptionsReorder` is the only lever over it. That list
  is also the swatch display order, so the chosen color moves to the front of
  the swatch row too. Declared per garment as `storefront_first_color`:
  **Moss** on both tee lines, **True Navy** on the crew, **Denim** on the
  hoodie. Applied by `scripts/shopify_fixups.py color-order`.
- **Reordering colors can scramble the size list, and Denim does.** Shopify
  re-derives every option's value order from the resulting variant sequence,
  so a first color missing a size pushes that size to the back. Shopify hides
  out-of-stock variants at publish time (the "only show in-stock variants"
  publishing setting), and Denim is missing S and 3XL on all 31 hoodies, so
  hoodie sizes now read M, L, XL, 2XL, S, 3XL. Evan was shown the effect and
  the three colors that are complete on every hoodie (Pepper, Blue Jean,
  White) and chose Denim anyway on 22 Aug 2026. It corrects itself if those
  Denim sizes come back in stock and the product is republished. Tees (Moss)
  and crews (True Navy) are complete everywhere and kept correct size order.
  `reorder_option_values` feeds a canonical size order in on every call so a
  re-run cannot compound the scrambling.
- **`productOptionsReorder` needs every option in the payload**, not just the
  one moving; a partial list fails with MISSING_OPTION_NAME.
- **The backfill wrote both sides directly, never republished.**
  `scripts/rename_catalog.py` PUTs the title to Printify and then to Shopify,
  addressing Shopify by the product id Printify stores in `external.id` rather
  than by title (two products shared the title "Nauvoo Temple Sweatshirt
  (front logo)"). A republish would re-sync images and variants along with the
  title and would flip the UNLISTED children back to ACTIVE. Shopify keeps a
  product's handle across a title change, so every existing link survived.
- **Known gap, pre-existing:** six hand-built dated tees (Cody, Kirtland,
  Logan, Manti, Provo, Taylorsville) have no description on Printify or
  Shopify and no local facts fragment. They are reported and skipped by
  `write_description.py --backfill-dated` until those temples are researched.
- **Follow-up outside this repo:** Evan's three claude.ai description skills
  resolve a Shopify product by the exact title `{place} Temple {Garment}` and
  hard-stop on zero matches, so they need their resolution step updated to the
  new titles.

## 22 August 2026 (republish costs, featured photos)

- **A republish is destructive to the Shopify-side work, measured not assumed.**
  Republishing one tee and one hoodie (Bountiful, 22 Aug 2026) kept the title
  and the UNLISTED status but **deleted the art close-up cards outright**,
  reverted the hoodie's Blue Jean colorway to Printify's True Navy, and
  reverted the Color option order so the pages stopped opening on the wanted
  color. It did **not** change the featured image. `scripts/republish.py`
  therefore runs the three repair passes itself after the pushes settle;
  republishing without them leaves the storefront worse than before.
- **Unclaimed "Copy of ..." drafts are never republished.** They have no
  Shopify counterpart, so publishing one creates a junk storefront product.
- **The featured photo is a third thing, separate from both defaults.** A dated
  tee can carry Printify `is_default` = Moss and open on the Moss variant on
  Shopify while its card still shows a Graphite shirt, because Printify's
  `images[]` leads with the Graphite mockup and `images` is not writable
  through the API. Fixed on the Shopify side by moving that colorway's mockup
  to gallery position 1 and reseating the art card at position 2
  (`scripts/shopify_fixups.py featured-photo`, keyed by
  `storefront_featured_color`). Mockup media carry no alt text from Printify,
  so the colorway is matched through its variants' image URLs.
- **Three separate "defaults", worth keeping straight:** Printify's
  `variants[].is_default` (drives Printify's own default, set by
  `scripts/default_variant.py`); Shopify's preselected variant (position 1,
  driven by the Color option value order, set by `color-order`); and the
  featured photo (gallery position 1, set by `featured-photo`). Setting one
  does not set the others. Evan's 22 Aug 2026 choice: featured photo follows
  the dated tee only (Moss).

## 22 August 2026 (republish aftermath, measured)

- **A full-catalog republish takes the storefront's images down for roughly 15
  minutes.** Pushing all 123 products at once made Shopify delete and re-ingest
  every mockup; products go full to empty to full as Printify's queue reaches
  them. Peak was 94 of 123 with zero media, including two of the four ACTIVE
  parent listings. Everything recovered by t+14m and the parents by t+4m.
  Stage a future run in batches so only a few products are dark at a time, or
  do it outside trading hours.
- **`art_images.py` no longer aborts the batch on one failure.** A product with
  no mockups yet cannot take a card at gallery position 2, and that exception
  used to raise straight out of the loop: it left 51 of 55 products uncarded.
  It now skips a product with no mockups (reported, re-run picks it up) and
  catches per-product failures, card rendering included.
- **Matching a colorway to its mockup: variant image URL first, garment colour
  second.** Some products carry no per-variant images on Shopify, so there is
  no URL linking Moss to a photo. The fallback reads Printify's own default
  mockup for the colorway and matches on the average colour of the image's
  centre third. Grayscale hashing does not work here (every mockup in a set is
  the same shirt in the same pose, so several tie at distance 0); colour
  separates cleanly, observed best 0.1 against next-best 32.3. Printify
  renames files on upload so filenames never match, and media ORDER is not
  reliable either: on the Provo dated tee the Moss mockup sat at Shopify index
  5, not the index 10 that position arithmetic predicted. `media_id_by_color`
  refuses an ambiguous match rather than risk featuring the wrong colorway.
- **Known gap:** the three Limited Edition one-offs have no art cards by design.
  Draper's was closed on 22 Aug 2026 by retracing from the new sketch.
- **A failed editor run is worth retrying before diagnosing.** The date-layer
  automation timed out on the font picker's Search field and looked like the
  editor redesign the discovery notes anticipate. It was not: Printify had not
  changed, and the identical command succeeded on the next attempt. On this
  machine the editor page needs longer to settle than the step allows. Retry
  first; only open a repair session if it fails twice.

## 23 August 2026 (publish ordering)

- **The default variant is written BEFORE the publish, not after.**
  `publish_drafts.py` used to call `fix_default_variant` after `publish_one`
  returned. Two things went wrong with that, both seen on the 23 Aug sweep.
  Printify locks a product while its publish is in flight, so the write raced
  the lock and failed with code 8252 (the Ogden Original dated tee stayed
  locked for over an hour). And when the write did land, it was by definition
  an edit Printify had not pushed to the store, so every dated tee sat badged
  "unpublished changes" in the Printify UI from the moment it went live.
  Clearing that badge means a republish, and a republish deletes the art cards
  and reverts the Shopify colorway and option order, so the badge is expensive
  to clear and worthless to leave. Writing `is_default` first lets the publish
  push carry it and the product lands clean.
  The dated tee is the only line affected either way, because it is the only
  garment declaring `default_colorway`. If the pre-publish write fails the
  product still publishes, on the donor's colorway; fixing it afterward needs
  `default_variant.py` and then `republish.py`, because once the product is
  live only a republish carries the change to Shopify.
- **`--report-only` cannot see a temple that has art but no SVGs.** The sweep's
  report path calls `detect_art_files` (SVGs only) while the real run calls
  `ensure_art_files`, which traces a source PNG first. Five folders with PNGs
  and no SVGs therefore read as "NO ART YET" in the report and generated
  normally in the run. The report is a lower bound on the work, not a preview
  of it.
- **`external.handle` sometimes comes back as a full URL.** On this shop
  Printify returned `https://agv44k-jr.myshopify.com/products/<handle>` rather
  than the bare handle, and the publish-time fixup looked it up literally and
  skipped the product ("no Shopify product with handle 'https://...'"). The
  Orem crew was the one hit; the catalog-wide `shopify_fixups.py all` pass
  caught it afterward by title. Strip the origin before using that field.

## 26 August 2026 (new products publish ACTIVE)

- **New products are no longer unlisted; they publish ACTIVE (Evan's 26 Aug
  decision, supersedes the 22 Aug unlist-the-children rule).** The unlist
  fixup is removed from `scripts/shopify_fixups.py` entirely: it is gone from
  `fix_published_product()` (so `publish_drafts.py` leaves each newly
  published product ACTIVE, which is how a Printify publish lands on Shopify)
  and gone from the `all`/standalone commands (so no catalog-wide pass can
  re-unlist anything). The parent-product concept is unchanged: Salt Lake's
  products still carry the bare garment titles and the Easify Temple dropdown
  still cross-links every temple.
- **Children published before 26 Aug 2026 stay UNLISTED.** Nothing in the
  pipeline sets a product's status in either direction anymore; flipping the
  existing children to ACTIVE would be a separate, Evan-initiated pass.
  `easify_options.py` therefore keeps counting UNLISTED as live.

## 26 August 2026 (collapsed temple facts, video guide fix)

- **Temple facts render as collapsed `<details>` rows (Evan's 26 Aug
  decision).** The facts block had grown to about six phone screens. Each
  block is now a collapsed row: the temple name (h3) with its spec rows, then
  one row per h4 block (Construction Story, Symbolism & Design, Changes Over
  Time where present, Trivia). Scope is facts only: Personalization, the
  garment intro, and the Size Guide stay open. The as-of line stays visible
  after the rows.
- **Presentation transforms live in `description_html.py` and run at
  assembly time.** The vendored skill assets (`reference/skills/*/assets/`)
  and the per-temple `Temples/*/temple-facts.html` fragments stay untouched;
  `compose_description()` is now the one place a description's final HTML is
  shaped, called from all three compose sites (generate.py and both
  write_description.py paths). Transforms are idempotent by unwrap-then-
  rewrap, so facts re-extracted from a live product re-collapse to identical
  bytes and `--normalize` converges. The `<section class="temple-facts">`
  wrapper stays outermost so the publish gate and FACTS_RE keep working.
- **The size-guide video gets `controls="controls"` and
  `preload="metadata"`.** The vendored tag is autoplay/loop/muted with
  `preload="none"`, no controls, no poster. Autoplay is a request browsers
  may decline (iPhones decline it in Low Power Mode), and with no controls
  the video sits as a frozen frame with no way to start it, which is exactly
  what Evan saw. Verified playing normally in desktop Chrome pre-fix, so the
  files were never broken. The transform edits only the opening `<video>`
  tag, so cc1717's deliberately odd `</source></video>` tail rides through.
- **Description backfill channel: Printify PUT, then a description-only
  publish (Evan's direction).** `write_description.py` gained `--only TEXT`
  and `--via-publish`; the latter replaces the direct Shopify
  `descriptionHtml` write with `POST publish.json` carrying
  `{"description": true}` and every other sync flag false, because the
  full-flag publish is the measured-destructive republish. Measured on the
  Vernal base tee, 26 Aug 2026: the description-only publish synced within a
  minute, kept the art card at gallery position 2, kept the color order, the
  handle, and the listing status. Drafts with no `external` id are PUT only;
  their description rides the first publish.
- **The Printify connector decodes HTML entities on push**, measured the
  same day on Vernal: `&sup2;` in the vendored size guide arrived on Shopify
  as a literal superscript two. Rendering is identical, but a byte compare
  would re-sync every product forever, so `--normalize` now compares the
  Shopify side entity-insensitively (html.unescape on both sides). The
  Printify side stays byte-exact.
- **Follow-up outside this repo, still open:** Evan's claude.ai description
  skills emit un-collapsed markup and the old video tag. They currently
  hard-stop on the new title patterns, so they cannot overwrite anything; if
  they are ever revived they need the same collapse and video treatment, and
  until then a `--normalize` run re-converges anything they touch.
- **The collapsed rows carry their own scoped `<style>` block** (Evan's
  iPhone review, same day: rows too far apart, no dividers, and the theme
  hides the default disclosure markers so nothing said the rows open).
  `FACTS_STYLE` ships inside the facts section: divider lines, 12px row
  padding, zeroed heading margins, and a +/− indicator on the right.
  Literal characters, no entities (the connector decodes them). Measured
  surviving the Printify PUT and the connector push intact on Vernal.
- **The size-guide measurements table is dropped at assembly; the video IS
  the size guide** (same review). `trim_size_guide()` keeps the h3 and the
  video and cuts everything after the video inside the section (the h4
  Measurements table and the width/length note). The vendored asset keeps
  its table; it just never reaches a product.

## 26 August 2026 (Temples/All mirror for the digital download files)

- **Every temple's black SVG is duplicated into `Temples/All/`** (Evan's
  direction, same day he built the Temple Art File product on Shopify: 40
  variants, $4.95 SVG download, delivery wired through a digital products
  app that wants one flat folder of files). The copy is named by the CLEAN
  place token, never the folder name: `Manhattan black.svg`,
  `Washington D.C. black.svg`, `Ogden Original black.svg`, no ref-finder
  stars. `mirror_black_art()` in generate.py does the copy; it runs per
  temple in every sweep (not report-only) and every `--temple` run, right
  after the manifest loads, and refreshes the copy when the source art is
  newer. The 40 existing temples were backfilled the same day.
- **`Temples/All/` is not a temple folder.** The sweep walk skips it by
  name (`ALL_ART_DIR`); nothing scaffolds a manifest for it. Any future
  script that walks `Temples/` must skip it too.
- Found while backfilling: Evan had renamed the misspelled `Manhatten`
  folder and its files to `Manhattan`, stranding the manifest's art
  filenames. The manifest was fixed to match (manifests are
  pipeline-maintained). A renamed folder strands its manifest silently
  until the next run; the `Manifest names missing art file` hard stop is
  the tell.

## 26 August 2026 (catalog description rollout, canonical comparison)

- **The collapsed-facts catalog rollout is complete: 158 of 162 products
  verified in sync on both stores.** Run via `write_description.py
  --normalize --via-publish` (interrupted once by a session restart and
  resumed; the pass is convergent so the resume was a plain re-run). One
  transient lock ("Product is disabled for editing", Printify error 8252,
  the Layton hoodie) resolved itself when its in-flight publish finished.
- **Descriptions are compared in canonical form (`canon()` in
  write_description.py), never byte-for-byte.** Both stores rewrite
  render-identical HTML, all measured 26 Aug 2026: the Printify connector
  decodes character entities on push, serializes the video tail as
  `</source></video>` (the tee asset carries that form natively, which is
  why only crews and hoodies drifted), collapses `<br />` to `<br>` (the
  six old hand-researched temples carry `<br />` in their facts), and
  whitespace after `<li>` is unstable across round trips (Logan). A save
  from the Printify editor UI decodes entities on the Printify side too
  (Evan's publish retries did this to the Saratoga Springs products).
  Canonicalization is comparison-only; stored bytes are never rewritten to
  match it.
- **RESOLVED same day: the Saratoga Springs publish failures were
  Printify's IP filter tripping on the word "Hardy".** All four products
  failed to publish (Evan's manual retries included; the reason showed only
  in the Printify UI banner). The trigger was the temple matron's maiden
  name, "Marie Ellen Hardy Sorensen", in the First Temple President row:
  Printify's intellectual-property screen apparently matches the brand Ed
  Hardy against listing text and blocks the publish. Fix (Evan's call):
  drop the maiden name from `Temples/Saratoga Springs/temple-facts.html`
  ("Marie Ellen Sorensen") and re-run `--normalize --via-publish --only
  "(Saratoga Springs)"`; publishes cleared immediately. TRAP for future
  descriptions: a publish that fails repeatedly with no API-visible cause
  may be the IP filter matching an innocent word (names especially) against
  a brand; check the UI banner and reword.


## 14 September 2026 (the Tapstitch decision and what it changed)

- **Evan committed to Tapstitch blanks**: one tee, one hoodie, one crewneck for
  every temple design. CC1717, CC1566 and CC1567 retire. The specific blanks are
  NOT picked yet, so print areas, colours, prices and product copy are all still
  placeholder.
- **The personalizable date tee is PAUSED, not migrated.** This closes the
  27 Aug open question about Tapstitch buyer personalization: rather than run a
  split catalogue to keep one line alive, the product waits. The split-catalogue
  lean in the migration plan is superseded.
- **The logo moved off the back print to the front.** New layout profile
  `back_temple_text` (temple plus location text). The existing `back_stack` and
  `back_stack_dated` are untouched so the Printify fallback still works.
- **Two back-spacing questions were raised by that change and are open.**
  Measured across all 40 designs: removing the logo left the old 2.5in bottom
  margin as the only thing capping tall temples (Salt Lake prints 11.1in against
  a 12.5in target), and top-anchoring leaves between 2.5in and 8.6in of empty
  canvas below the location line depending on the building's proportions.
  `vertical_anchor: "center"` exists as the alternative. Proof sheet:
  https://claude.ai/code/artifact/63f25017-3639-4bb9-96cc-d16cc1e21d57
- **Store pull-down is two steps, deliberately.** Every temple listing drafts
  now; each old listing is deleted only when its replacement publishes. Mechanism
  that forces this: a DRAFT or ARCHIVED Shopify product keeps its handle
  reserved, so a replacement under the same title would be minted at a '-1'
  handle and every Easify dropdown URL would break. Deleting at swap time lets
  the replacement inherit the exact address. `scripts/store_pulldown.py` has
  snapshot / draft / restore / delete, and snapshot must run first because the
  temple-to-handle mapping is only reliably readable while the catalogue is intact.
- **Descriptions go straight to Shopify, never through the Tapstitch editor.**
  The writer is proven on 158 products and no Tapstitch redesign can break it.
- **Garment copy moved out of the description skills** into
  `reference/garment-copy/{garment_id}/`. Three new blanks would otherwise have
  meant three new skills holding two HTML files each. The four Comfort Colors
  descriptions were verified byte-identical before and after the move. The
  Tapstitch folders hold a README and NO html files on purpose: `fixed_description()`
  returns empty when the files are absent, and an empty description beats the
  wrong garment's specifications on a live page, so a placeholder would defeat
  the guard.
- **MEASURED: Tapstitch publishes to Shopify with an EMPTY productType**, and
  every fixup in `scripts/shopify_fixups.py` is keyed on that field, so colour
  ordering and the featured photo silently do nothing and report success. The
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
  with its dated twin. See the evening entry below.
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

## 14 September 2026, later (the blanks)

Evan chose all three blanks. Specs below were read off the live Tapstitch product
pages the same day, not taken from the chat.

| Line | Blank | Code | Weight | Sizes | Blank cost |
|---|---|---|---|---|---|
| tee | Pure Cotton Unisex T-Shirt #RU0010 | RU0010-C001-V6 | 180 gsm, 5.3 oz | M-3XL | $2.99 |
| crew | Boxy Fleece Crewneck Sweatshirt #UT0044 | UT0044-P001-V3 | 345 gsm, 10.2 oz | S-2XL | $14.99 |
| hoodie | Essential Oversized Boxy Fit Fleece Hoodie #RW0041 | RW0041-P001-V3 | 345 gsm, 10.2 oz | S-2XL | $16.99 |

All three: DTG, international fulfillment, Special Line shipping (9-14 days),
front and back print at $2.99 per frame. Production 1-3 days, so 10-17 days to a
customer's door. The crew and hoodie are a matching set (same fabric, same colours).

- **Colours are now in the garment configs** as a `colorways` list, each entry
  carrying the Tapstitch name, the storefront name and which ink that colourway
  prints. Tee: Black, Charcoal Gray, Caramel Machiato, Wine Red, Grape Purple.
  Crew and hoodie: Black, Dark Gray, Haze Blue, Navy Blue, Dark Green, Coffee.
- **Three tee colours are renamed on the storefront** (Evan's call): Caramel
  Machiato to Caramel, Wine Red to Maroon, Grape Purple to Grape.
  `scripts/shopify_fixups.py` gained `colorway_renames_by_type()`, which reads
  those pairs from the configs rather than hardcoding them the way the older
  Printify hoodie rename does. Same caveat as that one: it is Shopify-only, so a
  variant re-sync from Tapstitch pushes the original names back, which is why it
  stays a re-runnable command in the end-of-run sequence. The renames run BEFORE
  the colour reorder, so a reorder asking for a storefront name finds it.
- **Ink per colourway is a first pass.** Everything is white except Caramel,
  which is set to black. Needs Evan's eye on a real mockup.
- **PRINT AREAS ARE STILL UNKNOWN.** Not on the public product pages; only inside
  the Tapstitch editor. They stay placeholders until the first live session, and
  `tapstitch_publish.py check` still names them as blocking.

THREE PROBLEMS WITH THE LINEUP, raised to Evan the same day:
1. The RU0010 tee is 180 gsm / 5.3 oz, LIGHTER than the Comfort Colors 1717 it
   replaces, when the stated reason for the whole migration was wanting heavier.
   The fleece at 345 gsm does deliver that; the tee does not.
2. The tee has NO SMALL (M-3XL) and Tapstitch's own page warns the sizing is
   smaller than standard.
3. Size ranges do not line up: tee M-3XL, fleece S-2XL. Only M, L, XL and 2XL
   exist across all three lines.

Also worth modelling before any multi-buy offer: per-additional-item shipping is
about $1.55 (tee), $4.80 (crew), $6.70 (hoodie). Multi-temple orders are one of
the three named AOV levers and this works against it.

## 14 September 2026, later still (tee swapped, prices, real costs)

- **The tee blank changed from RU0010 to RT0063** the same day it was chosen.
  Raised three problems with the RU0010: 180 gsm / 5.3 oz (LIGHTER than the
  Comfort Colors 1717 it replaces, defeating the stated reason for the migration),
  no Small, and a "sizing is smaller than standard" warning on Tapstitch's own
  product page. The RT0063 Essential Cotton T-Shirt is 260 gsm / 7.7 oz, runs
  S-3XL, has no sizing warning, and costs $5.99 rather than $2.99.
- **Colours settled.** Tee: Black, Dark Gray, Coffee, Navy Blue, Wine Red (shown
  as Maroon). Crew and hoodie: Black, Dark Gray, Haze Blue, Navy Blue, Dark Green,
  Coffee. Four of the five tee colours are shared with the fleece, so the
  catalogue reads as one family. Caramel, Charcoal Gray and Grape are gone with
  the RU0010.
- **Every colourway in the range is dark, so every design prints WHITE.** There is
  no light colourway and no second art file to manage. If a light colourway is
  ever added, its `ink` must be set to black and the black art files built.
- **Only one rename survives:** Wine Red to Maroon. Driven from the config, not code.
- **Storefront opens on:** tee Black, crew Coffee, hoodie Dark Gray (Evan).
- **Prices unchanged:** $44.99 tee, $64.99 crew, $74.99 hoodie.
- **Real unit costs are Evan's figures, not Tapstitch list arithmetic:** $20.57
  tee, $32.55 crew, $36.77 hoodie, including blank, both print sides, shipping,
  custom neck tag, hangtag, order insert and payment gateway fees. Recorded in
  each garment config under `costs_usd.all_in_per_unit`, which is the number to
  trust; the Tapstitch line items beside it do not sum to it.
  CAVEAT recorded and raised: the $20.57 was worked out while the tee was the
  RU0010. RT0063 adds about $3.80 per unit (blank +$3.00, shipping +$0.80), so the
  real tee cost is nearer $24 and the gross nearer $21, not $24.42.
- Against the $22 to $40 acquisition cost in BRAND.md section 16, a single tee
  does not pay for its own customer. Unchanged by the migration, but now arithmetic
  rather than an estimate.

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
  temple art beside it, not the type. Set per Tapstitch garment in
  `spacing_overrides`, so the retiring Printify profiles are provably untouched.
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
  open in (Black, Coffee, Dark Gray). They had been rendering the retiring
  Comfort Colors moss, navy and denim, which meant Evan was being asked to judge
  the design against colours that no longer exist.

### THE STORE IS DARK, done 14 Sep 2026 on Evan's explicit go-ahead

- **160 temple listings set to DRAFT**, 0 failures. Verified against Shopify
  afterwards: 165 products, 164 DRAFT, 1 ACTIVE. The only thing still live is
  **Temple Art File**, the $4.95 download, which is not a Printify product and
  stays sellable. The four Tapstitch test drafts were correctly excluded by
  vendor.
- **SIX PRODUCTS PERMANENTLY DELETED** at Evan's instruction. There is no undo:
  - the two stray duplicates from 27 Aug, `essential-temple-tee` and
    `essential-temple-tee-with-personalizable-date`
  - the three Nauvoo Limited Edition one-offs
    (`nauvoo-temple-tee-limited-edition`, `copy-of-nauvoo-temple-hoodie`,
    `nauvoo-temple-sweatshirt-front-logo`)
  - `cornerstone-sweatpants`
- **`restore --apply` is the way back** for the 160 drafts, reading
  `artifacts/tapstitch/pre-migration-catalog.json`. It cannot bring back the six
  deletions, and it will report them as failures if run, which is expected.
- Two fixes the run itself forced: the snapshot now records FULL product details
  for the products it leaves alone (it stored only a title and a reason, which
  made the four non-temple leftovers unreachable by the guarded delete path), and
  the delete message no longer claims a replacement is coming for a product that
  has none.

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
- **Costs are Evan's figures and they supersede the $20.57 caveat.** The tee's
  earlier number was worked out while the blank was still the RU0010 and was
  about $3.80 light for the RT0063; $19.57 is measured on the blank and the
  fulfillment actually in use, so that open caveat is closed. The stale
  international shipping line items were REMOVED from the configs rather than
  left sitting beside the new all-in numbers, where they would have read as
  current.

**MARGIN, and one thing worth a second look:**

| Line | Price | All-in | Gross | Change since this afternoon |
|---|---|---|---|---|
| tee | $44.99 | $19.57 | $25.42 | cost down $1.00, and down about $4.80 against the RT0063-corrected figure |
| crew | $64.99 | $34.10 | $30.89 | cost UP $1.55 |
| hoodie | $74.99 | $34.67 | $40.32 | cost down $2.10 |

  The crew is the one to look at. Its blank costs MORE than the hoodie's ($16.57
  against $14.92) and its all-in is within $0.57 of the hoodie's, while it sells
  for $10.00 less. That is $9.43 less gross on a garment that costs essentially
  the same to make and ship. Either the crew price rises or the gap is accepted
  deliberately; prices are unchanged for now and this is flagged, not decided.
  Against the $22 to $40 acquisition cost in BRAND.md section 16, the tee at
  $25.42 still does not reliably pay for its own customer.

**OPEN, all small, none blocking the editor session:**

1. **Is Flower Gray dark enough to print white?** Every colourway until now was
   obviously dark. Its `ink` is set to white on the assumption that it follows
   the rest, and if a real mockup says otherwise it becomes black and the black
   art files have to be built for that colourway. Needs Evan's eye.
2. **Does the RT0063 print DTG from the US center?** DTG is what its
   international page says, and both fleece blanks print DTF from the US. Confirm
   before any copy claims a technique.
3. **The US center's shipping service name** was not readable on the product
   page. `shipping_method` is null in all three configs rather than carrying the
   international 'Special Line', which no longer applies.
4. **Colour swatch spellings stay unverified** for all three blanks, and
   'Flower Gray' is the likeliest to differ. A mismatch still fails silently.

## 14 September 2026, last of the day (design sizes, hoodie lead colour)

- **The hoodie opens on Navy Blue**, not Dark Gray. Evan. `storefront_first_color`
  in `garments/hoodie.json`, and the proof-sheet swatch follows it.
- **The temple is 12.0 inches wide ink to ink at its widest point**, down from the
  12.5in the Printify catalogue used. Set as `temple_target_ink_width_in` in each
  Tapstitch garment's `spacing_overrides`, so `spacing_defaults.json` keeps 12.5
  for the retiring `back_stack` profiles and they are provably untouched.
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
  constraint, not the 12.0in rule.** It was measured off the live Printify
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
  16.99in Printify area this catalogue printed on for a year. **Confirm it in the
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

Evan, replacing the margin-based spacing the layout inherited from Printify. The
back print is now four rules and nothing else:

1. The temple and the location line are **centred in the print file**, vertically
   and horizontally.
2. The temple ink spans **no more than 12.0in** at its widest point.
3. The location line is **0.7in of INK tall**, not 0.7in of box.
4. The **top of the location line sits 0.5in below the temple's lowest ink**.

- **There is no top or bottom margin any more.** `top_margin_in` and
  `bottom_margin_in` are both 0.0 in the three Tapstitch garment configs.
  `spacing_defaults.json` keeps 0.6 and 2.5 for the retiring `back_stack`
  profiles, so the Printify layouts are provably untouched.
- **This is what finally cleared the width problem.** The 2.5in bottom margin was
  measured off the live Printify catalogue, where the back stack ENDED with the
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
  than inherited, so a change to the Printify defaults cannot move it.

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
- **The Printify path was moved too, though it is dormant.**
  `location_text_images()` renders `{Temple} location text {color} (auto).png`
  and used to drop it in the folder root; it now writes to the working folder.
  Only the Printify channel calls it and there are zero such files on disk (Evan
  cleared them in the move), so nothing changed in practice — but running the
  fallback would otherwise have littered the roots again. The override lookup
  (`layout.find_text_override()`) still scans the folder root, which is where
  Evan's own `*location text*` files go; its `(auto)` exclusion now only
  matters for leftovers from before this move.
- The fallback is a migration convenience, not a supported second home. Once no
  temple has files at its root (true as of today, checked) it can go.

## 15 September 2026, evening (the editor turned out to be an API)

- **The highest-value unknown in the migration is answered, and the answer is
  yes.** Recording the editor's own traffic while Evan built one tee by hand
  showed that the save is `PUT /api/designs/customized/templates/<id>` carrying
  the complete design as JSON — piece, source URL, left, top, width, height,
  scaleX, scaleY, angle. Every other step is a JSON call too. Full detail and
  payload shapes in `docs/discovery/2026-09-tapstitch-editor-api.md`.
- **The blank is addressed by its SKU** (`silSn: "RT0063"`), not by searching a
  catalogue and clicking a result. Three selectors die on that fact alone.
- **The flattened-file bet paid off.** Both uploads registered at 4386x5516,
  exactly the tee's real print area, and front and back received identical
  placement differing only in `src`. Because every file is built to the shape of
  its own print area, the editor places it the same way every time — which is
  what the whole approach rested on and what `config/tapstitch.json` asked to
  have confirmed before any of it was trusted.
- **Colours are numeric codes to Tapstitch**, so the swatch-name mismatch cannot
  bite on the API path. It is not retired: `shopify_fixups.py` matches on names,
  so `colorway_renames_by_type` must still agree with what Tapstitch publishes.
- **Saving a draft does not touch Shopify**, checked straight afterwards — the
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
  signed OSS URL, and the design was saved — after which Tapstitch rendered four
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
  a LIST of store-product ids — so 135 products is a batch, not 135 clicks.
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
- **The size guide is decided: the CC1717 section's FORMAT, with RT0063's own
  measurements.** Evan asked for the CC1717 size guide section. Its numbers are
  for a different garment and could not be shipped: RT0063 runs ~1.4in wider in
  the chest and HAS NO 4XL, so the CC1717 table would have advertised an
  unsellable size on every listing. `reference/garment-copy/tee/size-guide.html`
  carries the manufacturer's real figures for S-3XL, labelled in inches.
- **The CC1717 intro was NOT copied across.** It claims garment-dyed ringspun
  cotton at 6.x oz; RT0063 is 7.7 oz (260 gsm) and not garment-dyed. Copying it
  would have published false product claims. `tee/product-intro.html` therefore
  does not exist, `fixed_description()` still returns empty, and that is the
  guard in its README working as intended rather than a gap to paper over.
- **No size-guide video for the new blank.** The CC1717 section embeds a
  per-blank video showing the wrong garment. Omitted. The original decision — new
  video, or the branded chart images in `Important Elements/` — is still open,
  and now applies only to the video, since the measurements are settled.
