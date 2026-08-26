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
