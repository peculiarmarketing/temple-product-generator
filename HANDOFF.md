# (9 Oct 2026) Map on-model photos: live and locked

- Evan approved everything. All 68 shots are live on the six map listings and verified. The Be Peculiar EN and ES sweatshirts have the loose, long refit live too.
- Placement is locked for every future map product: `artifacts/onmodel-maps/LOCK.md`. To add a new city, run `fetch`, then `check <city>`, then `build <city>`, show Evan the review sheets, and finish with `scripts/onmodel_maps_apply.py --place <city> --apply`.
- Still open: white ink is nearly invisible on the Cream tee and faint on Pink and Light Blue. This is a product question for Evan, not a compositing fault.
- Risk: the base photos (gitignored, 324 MB) only exist as Higgsfield CDN files. If those links ever stop working, the lock cannot be rebuilt. A copy in Drive would remove that risk.

# (8 Oct 2026, late night) Map on-model photos: built, waiting on Evan's review

The six map products (Nauvoo and Salt Lake City on tee, sweatshirt, hoodie) had
only flat lays. 68 on-model shots are built (front and back, every colour) in
`artifacts/onmodel-maps/` and sent to Evan; nothing is on the store yet.
- New stock models per garment (Burst, `models.json`), front and back bases and
  every colour made on Higgsfield gpt_image_2_5 sunburst at 4k (2880px), pose and
  framing varied per colour (`gen/recolour_spec.json`). 34 bases, 144.5 credits.
- Placement from Tapstitch's own flats of the map products, carried by
  collar-to-hem length (`composite_maps.py` docstring, `flat_geometry.json`).
- Full fold at the temple settings (Evan's choice). Output 5000px.
- White ink nearly vanishes on the Cream tee, faint on Pink and Light Blue: a
  product question flagged to Evan, true to the print, not a compositing fault.
- Next, on approval: `scripts/onmodel_maps_apply.py` (to write) uploads, binds
  variants to the back shots, orders galleries, verifies. Finals are gitignored;
  rebuild with `python composite_maps.py build` (bases re-download from
  `gen/jobs.json`).

# (8 Oct 2026, night) Salt Lake parent descriptions fixed; homepage collection tabs live

- The Salt Lake temple hoodie and sweatshirt descriptions were rebuilt with their
  collapsible rows (an old admin-editor save had stripped them). Words unchanged.
  Every garment product now has rows (148 of 148). `scripts/rebuild_parent_descriptions.py`.
- Homepage "Shop by garment" is four tabs: Hoodies, Tees, Sweatshirts, All Products
  (`sections/pp-collection-tabs.liquid`, `scripts/home_collection_tabs.py`, revert
  available). Tees, Sweatshirts, Hoodies and Jackets are now published; card order by
  `scripts/collection_order.py`. Verified on the live site, desktop and mobile.
- Details: `docs/decisions.md`, "8 October 2026, night".

# (8 Oct 2026, evening) v2 on-model photos: what was built

Evan asked for the full replace so he can preview in Shopify. `scripts/onmodel_v2_apply.py --apply` ran;
`--verify` passes on all seven (order, alts, every variant bound to a v2 shot, still DRAFT). Media ids:
`artifacts/onmodel-v2/applied.json`. Still DRAFT; going ACTIVE waits on Evan. Then Phase 2 below.

What was built: The four fixes from Evan's v1 review are done
in `artifacts/onmodel-v2/` (read `review/` first):

- **Placement** from chest width, measured on Tapstitch's own flats
  (`flat_geometry.json`), checked side by side per colour (`review/placement_*.jpg`).
- **Sharpness**: no fold warp or displacement; flat ink, shade only, texture 0.1.
  Blanks are 4096px (tee, crew, bomber: Higgsfield 4K upscale of the approved v1
  photos, pixel-aligned; hoodie: new kie.ai 4K then the same upscale). Finals are
  5000px JPEG q95 (`composite_front_v2.py build`). Every print correlates with its
  design file at r >= 0.99 (`review/verify.json`); 100% crops in `review/zoom_*.png`.
- **Close-up cards** on the lead colour, from the vector design files: `cards/`.
- **Bomber**: Evan chose "zipped main shots plus one unzipped-over-white-tee
  lifestyle shot" (navy only): `bomber_navy-blue_open`.
- **Hoodie fit**: new base from the v1 model with the temple hoodie on-model as fit
  reference, "boxy" removed (`build_front_bases_v2.py`), all seven colours
  regenerated from it. Tee matches its temple shot; sweatshirt is close (temple one
  a little roomier), flagged to Evan.

On approval: upload the 45 finals + 8 cards with `ShopifyClient.upload_media_image`
(staged upload, no git needed), delete the v1 on-model media (alts "... on model -
<Colour>"), order on-model first with the lead colour in slot 1, then cards, then
Tapstitch flats; bind each colour's variants to its new on-model shot (bomber: the
back shot); read back. Products stay DRAFT. Then Phase 2 below.

# STATUS (8 Oct 2026, night): tee colour rollout DONE; v2 on-model photos on the drafts

**Tee colours, done.** Pink, Light Blue and Cream are live on all 45 temple tees
and the Nauvoo and Salt Lake City map tees. `scripts/tee_colours_rollout.py
--verify` passes on all 47 (read-only). Each was a swap: old listings are DRAFT
at `<handle>-retired-2026-10-08`; ids and timestamps in
`artifacts/tapstitch/tee-colours-rollout.json`; the ledger carries the new
template and store product ids. Swatches for the new names were pushed to the
live theme first (backup in artifacts/swatches/). Process and reasons:
`docs/decisions.md`, "8 October 2026, evening"; how to add any future colour:
the skill's "Adding a colour to a garment".

**Pipeline, for every new product from here:** `garments/tee.json`,
`config/tapstitch.json`, `colour_names`, gallery `ORDER` carry eight tee colours,
so `sweep.py` and `map_run.py` build them; `composite_catalog.py` reads the new
colours' blank photos from `artifacts/onmodel-front/blanks/back_tee_*.jpg` when
the Mac's `colourway-photos/` lacks them, and the sweep preflight checks every
colour has a blank. The map line (branch claude/happy-volta-gmsrac) is merged in.

**Still open, Evan:**
- Re-import `artifacts/easify/option-sets.csv` in Easify: every swapped tee
  (and the hoodies, and both map tees) lacks its dropdown until then. The CSV is
  keyed by handle, which the swaps kept, so it is ready as it is. `easify_options
  .py sync` needs the Mac's Temples/ folder for the temple sets (it refuses to run
  without it, correctly); `--maps-only --report-only` showed no changes.
- Kiwi Size Chart for the bomber (`reference/garment-copy/bomber/size-chart.md`).

**Be Peculiar line and the seal bomber: LIVE (8 Oct 2026, night).** All seven set
ACTIVE on Evan's word, each storefront page serving with its v2 on-model gallery
(option F wordmark, black-on-white cards, re-angled unzipped bomber) and in its
garment collection, Temple Design Products and All Products.

# START HERE (8 Oct 2026, late): on-model photos v2 for the seven draft products, then the 45-tee colour rollout

A fresh session picks this up. The previous one ran out of context. Everything
below is pushed on branch `claude/magical-hamilton-7t4kx6` of this repo and of
the workspace repo (`peculiar-people-workspace-claude-projects-`). Both repos are
needed: clone the workspace for `project-sync/` and `designs/`. PR:
https://github.com/peculiarmarketing/temple-product-generator/pull/2 (open, not merged).

## Where things stand

Seven products are published from Tapstitch and finished on Shopify, all DRAFT.
Nothing goes ACTIVE without Evan's explicit word.

| # | Shopify product id | Title | Lead colour |
|---|---|---|---|
| 1 | 15350048260468 | Ultra-soft "Be Peculiar" Sweatshirt - Español | Black |
| 2 | 15350036955508 | Ultra-soft "Be Peculiar" Sweatshirt | Black |
| 3 | 15350048326004 | Ultra-soft Oversized "Be Peculiar" Hoodie - Español | Coffee |
| 4 | 15350048391540 | Ultra-soft Oversized "Be Peculiar" Hoodie | Gray |
| 5 | 15350048424308 | Essential Heavyweight "Be Peculiar" Tee - Español | Navy Blue |
| 6 | 15350048457076 | Essential Heavyweight "Be Peculiar" Tee | Black |
| 7 | 15350048522612 | Temple Seal Bomber Jacket | Navy Blue (back first) |

Done on all seven: product type, tags (`apparel:*`, `line:be-peculiar|seal`,
`language:es`; NEVER `garment:`/`temple:`/`country:`/`state:`, those feed the
temple collections and the homepage marquee), SEO, handles (`-espanol`; Shopify
drops the ñ), colour renames, lead colour first, alt text, Tapstitch flats,
and a first on-model set (v1, rejected, see below). Config and state:
`config/saved_designs.json`, `artifacts/tapstitch/saved-designs.json`. Decisions:
`docs/decisions.md`, 8 October 2026 section.

Swatches for Pink, Light Blue, Cream, Forest Green, Purple are only in the
UNPUBLISHED theme "Claude Code V3" (gid://shopify/OnlineStoreTheme/194273870196).
Live theme is "Claude Code V2". Evan publishes V3 before the products go live.

## Evan's review of the v1 on-model photos (8 Oct): fix all four

1. **Tee and sweatshirt logos sit too low.** Match the distance from the collar
   on Tapstitch's own flat lays. MECHANISM: `composite_front.py place()` positions
   the print as a fraction of the collar-to-hem span measured on Tapstitch's flat
   (`prints/front_geometry.json`, `collar_to_hem_in`). The generated tee and crew
   are cut shorter/boxier than Tapstitch's flats, so the same fraction lands lower
   on the body. FIX: scale from chest width instead (armpit to armpit on the flat
   vs on the photo), or place by measured inches below the collar using a
   chest-width px/in; then verify by putting each composite side by side with the
   Tapstitch flat of the same design and colour at the same scale.
   Tapstitch flats: the store product's own flat images, or the prefill mockups
   (`T.store_product_prefill(s, store_id, template_id)["mockups"]`).
2. **Designs distorted and illegible, worst on the jacket, especially zoomed.**
   MECHANISMS, all three real:
   - `composite.build()` is called with the temple settings: `displace=3.0`,
     `fold_strength=220`, fold band 4-20, `texture_gain=0.35`. Built for thick
     temple line art, it bends and noises thin lettering. For text: `flat=True` or
     displace 0 and fold_strength 0, texture_gain about 0.1, keep the shade map.
   - Resolution: photos are 2048px. The wordmark is ~380px wide, so the verse line
     is ~4px tall; the bomber chest logo is ~130px. Unreadable at any setting.
     Generate at kie.ai "4K" if the model accepts it (check `kie_client.create`
     resolution values), or upscale the blank 2x (Lanczos, or Higgsfield
     `upscale_image`) BEFORE compositing, so the print is rendered at the higher
     resolution, and save the final as PNG or JPEG q95+.
   - Add a design close-up to each gallery, like the temple products' "Temple line
     art close-up" card in slot 3 (`scripts/art_images.py` has the card style):
     the full-resolution design on the garment colour, plus optionally a tight
     chest crop from the high-res composite.
3. **Jacket: zipped vs unzipped over a plain white tee.** Ask Evan. Recommendation
   given: keep the main front shot zipped (the chest logo sits flat and legible
   and matches Tapstitch); add one unzipped-over-white-tee shot as an extra
   lifestyle image only if he wants it.
4. **Hoodie fit is wrong.** Too boxy, body shorter than the arms. It must fit like
   the temple hoodie on-model shots: longer body, sleeves bunching at the cuffs.
   MECHANISM: the hoodie base was generated from the stock photo plus the
   Tapstitch flat only, with a prompt saying "oversized boxy", and no fit
   reference. FIX: regenerate the hoodie base with a temple hoodie on-model shot
   as an extra reference image ("match this fit, body length and sleeve bunching
   exactly"), e.g. the live Salt Lake hoodie on-model back shot (find its URL with
   a product media query) or `artifacts/photo-mockup-spike/final-set/hoodie_*.jpg`
   (needs a public URL for kie: push it and use raw.githubusercontent.com). Drop
   "boxy" from `GARMENT["hoodie"]` in `build_front_bases.py`. Then regenerate the
   six other hoodie colours from the new base. Check the tee and crew fit against
   the temple on-model shots the same way.

After the fixes: show Evan the review sheets FIRST, then on approval replace the v1
on-model media on all seven products (delete the old on-model media ids, add
the new, reorder, rebind variants, read back). Do not set ACTIVE until he says so.

## How the on-model pipeline works (files in artifacts/photo-mockup-spike/)

- `build_front_bases.py`: stock model (Shopify Burst, licensed for commercial use
  and adaptation) to blank base, one per garment, then `recolour` mode for each
  colour from the base with a slight pose change (`POSES`, Evan wants every
  colour a slightly different stance). Uses kie.ai (`KIE_API_KEY` env secret is
  set; about 840 credits left, ~$0.10/image). Models: tee `white-tshirt-template`,
  crew `portrait-of-male-model`, hoodie `man-in-white-tank-top-stands-for-camera`,
  bomber `man-in-blue-jacket` (Burst slugs, images at
  `https://burst.shopifycdn.com/photos/<slug>.jpg?width=2400`). Faces are shown;
  Evan said that is fine (do NOT crop at the chin).
- `composite_front.py detect|build`: base landmarks are by hand in `BASE_LM`
  (re-mark them if a base is regenerated: ruler crops, as done 8 Oct); each colour
  is registered to its base by phase correlation, with a >40px guard.
- Print art: `artifacts/onmodel-front/prints/art_en.png`, `art_es.png` (rendered
  from the workspace `designs/be-peculiar/trace/{english,spanish} white.svg`),
  `seal.png` (thin seal), `chest.png`. All matched against Tapstitch's uploaded
  previews at r >= 0.977.
- Blanks: `artifacts/onmodel-front/blanks/*.jpg` (the only copies; regenerate if
  replaced). `back_tee_*.jpg` are the three new temple-tee colours.
- Upload route that works with the Shopify connector: push the image to this
  public repo, then `productUpdate(product:{id}, media:[{originalSource:
  "https://raw.githubusercontent.com/peculiarmarketing/temple-product-generator/<branch>/<path>",
  alt, mediaContentType: IMAGE}])`, then `productReorderMedia` and
  `productVariantsBulkUpdate` with `mediaId`. Variant ids on these products run
  in steps of 32768 in Tapstitch's original colour order (query them to be sure).

## Gotchas this session hit

- `pkill -f "<pattern>"` and `pgrep -f "<pattern>"` match the calling shell's own
  command line: two commands killed themselves (exit 144) and one waiter never
  ended. Use the background task id, or a pid file.
- The permission classifier once blocked a plain Shopify read; the
  `search_products` tool worked as a fallback.
- Tapstitch `distribute` publishes ACTIVE; set DRAFT immediately (done for all).
- The connector cannot write the live theme; it can write an unpublished one.
  `settings_data.json` round trip: the API returns it pretty-printed, Shopify
  stores it compact with `/` escaped; md5 of
  `json.dumps(d, separators=(",",":"), ensure_ascii=False).replace("/","\\/")`
  equals `checksumMd5`.

## Then: Phase 2, the 45-tee colour rollout (needs the Shopify Admin token)

Evan added `SHOPIFY_STORE_DOMAIN`/`SHOPIFY_ADMIN_TOKEN` as cloud secrets on 8 Oct;
check `env` in the new session. Add Pink (8082), Light Blue (8083, Tapstitch
"Blue") and Cream (8087, Tapstitch "Apricot") to every live temple tee: an Eden
Green style swap (see `scripts/eden_green_rollout.py`, generalise it to a garment
plus a colour list), and to `garments/tee.json` colorways, `config/tapstitch.json`
`api.blanks.tee.colorCodes`, and `colour_names.NAMES["tee"]` for future sweeps.
On-model backs: `blanks/back_tee_{pink,light-blue,cream}.jpg` (the existing tee
model) composited with `scripts/composite_catalog.py`; temple print files come
from the Mac's Temples folder or each tee template's back piece on Tapstitch.
Swapped products lose their Easify Temple dropdown until Evan re-imports
`artifacts/easify/option-sets.csv`. White ink on these three colours is Evan's
knowing choice (contrast 1.98 / 1.69 / 1.28).

---

# Be Peculiar line and seal bomber: in flight 8 October 2026

Seven hand-saved Tapstitch designs, driven by `scripts/publish_saved_design.py`
(decisions in `docs/decisions.md`, 8 October). State per product:
`artifacts/tapstitch/saved-designs.json`.

- All seven are built as Tapstitch store products (not public).
- All seven are distributed and finished on Shopify as DRAFT (Evan approved #2 and
  gave the go, 8 Oct): product type, tags, SEO, handle (Shopify drops the ñ, so the
  Español handles are set to `-espanol`), colour renames, lead colour, alt text.
  The bomber's variants are bound to their back images so the page opens on the seal.
- On-model photos are in (8 Oct): every colour on a real stock model (Shopify
  Burst), one model per garment, slight pose change per colour, prints
  composited by `artifacts/photo-mockup-spike/composite_front.py`. Gallery: the
  on-model shots first (slot 1 = the lead colour), then Tapstitch's flats; each
  colour's variants bound to its on-model shot. Sources: `artifacts/onmodel-front/`
  (blanks are the only copies; finals are what Shopify fetched from GitHub raw).
- Still DRAFT. Going ACTIVE waits on Evan's word, and should follow publishing the
  "Claude Code V3" theme, which holds the swatches for Pink, Light Blue, Cream,
  Forest Green and Purple (the live V2 does not).
- All seven go ACTIVE together on Evan's word.
- The five new swatches are only in the unpublished "Claude Code V3" theme.
- Manual for Evan: the bomber's Kiwi size chart (`reference/garment-copy/bomber/size-chart.md`).
- Phase 2, not started: Pink, Light Blue and Cream on all 45 live tees (an Eden
  Green style swap) and in `garments/tee.json` for future sweeps. Evan added the
  Shopify Admin token as a cloud secret on 8 Oct; it reaches a NEW session, not
  the one that was running. The three back-view blanks on the existing tee model
  are ready: `artifacts/onmodel-front/blanks/back_tee_{pink,light-blue,cream}.jpg`
  (copy to `photo-mockup-spike/colourway-photos/` as `tee_<slug>.png` for
  composite_catalog.py). Temple print files: the Mac's Temples/ folder, or each
  tee template's back piece on Tapstitch.

# The sweep: built 7 October 2026, not yet run on a real new temple

"Run a sweep" now takes a folder holding only the design PNG to a temple that is
complete on the live site (Evan, 7 Oct 2026; decisions in `docs/decisions.md`
under the same date). Driver: `scripts/sweep.py` (`scan`, `run`, `verify`).
The skill does the research (location into `temples.json`, the facts fragment
with both humanizer passes), then runs `sweep.py run --all-ready`.

New over the old hand sequence: the approval is recorded by the sweep; products
get their `temple:` / `garment:` / `country:` / `state:` tags (Tapstitch publishes
none, and nothing in the repo added them before); the on-model gallery runs for
every new temple; the drawing, stroke file and city line go straight into the
live theme through the app token; the black SVG is copied to `Temples/All/`; the
temple becomes a sold-out option on the Temple Art File; then `verify` reads the
whole thing back from the store.

**What has not run live yet, so watch the first sweep:**

- The tag step, the Art File variant create and the option reorder. The
  mutations validate against the Admin schema and the tag rule reproduces all 45
  live tees, but neither has written to the store.
- The theme upload of a single temple's files. `swatches.py push` proves the
  token can write the published theme; this exact upload has not run.
- `pen_strokes.py` on a brand-new temple. It needs opencv, scipy and
  scikit-image, now in `requirements.txt`; run `pip install -r requirements.txt`
  once. The sweep's preflight stops if they are missing.
- Whether Tapstitch re-sends a new product's images after the gallery build (it
  does after a design re-save, see below). `verify` would show it as images with
  no alt text; re-running the sweep rebuilds the gallery.

Offline tests: `tests/test_sweep.py` (tag rule, scan buckets, Art File order, and
`verify` against the live Boise tee as a fixture). Still manual, printed at the
end of a run only when needed: the Easify CSV import, and attaching the Art File
download in the Digital Products app.

# One-quarter lift rollout: DONE 7 October 2026

Evan's call: back prints sit higher (one quarter of the spare height above the
design, three quarters below), on-model photos fold the print into the fabric's
creases (option C), and every product's first photo, the one collection pages
show, is the on-model back in the flat-lay colour (maroon tee, black crew, navy
hoodie). Decisions and reasons: `docs/decisions.md`, 7 October 2026.

**All 135 live products were updated in place** by `scripts/relift_rollout.py`
and pass `relift_rollout.py --verify` (read-only): Tapstitch prints every one
from its new design commit, and every gallery has the new flat back and
on-model backs, all alt text, its colour bindings and the new order. Per
product record: `artifacts/tapstitch/relift-rollout.json`. No product was
swapped, so Easify bindings are untouched.

**What the run met, for the next time a design is re-saved on live products:**
Tapstitch re-sends each product's images about two minutes after a save, from
its own stored list, with no alt text. On 39 products that list still named a
file Shopify no longer had (photos replaced since publishing), so one image per
product came back FAILED: 16 flat lays, 23 fabric details, 4 art cards. The
script deletes those and rebuilds them from local files, and `check()` proves
each came back. Use `relift_rollout.py` (or its steps) for any future in-place
design change; do not call `art_images.py push` while siblings are mid-update,
since it cards any product whose alts are blank.

**Revert path:** the centred print files are in
`artifacts/tapstitch/print-backup-centred-2026-10-07/` (gitignored, this Mac
only). Copying them back and re-running the rollout with `space_above_frac` at
0.5 would undo the lift the same way it was applied.

**Side effects to know:** the retired DRAFT hoodies share templates with the live
ones, so they also got the new design and a re-send (their alt text is blank;
not for sale, untouched otherwise). The Salt Lake tee's template and store
product ids are now in the ledger. The local allow rules added for the run were
narrowed on 7 Oct to `relift_rollout.py --verify` and `build_product_gallery.py
--report` (read-only).

# Pen-drawn temples: live since 2 October 2026

The pen-drawing animation draws each temple in drawing order: outline, inner
structure, windows and doors one at a time, then small marks. Stroke files
come from `scripts/pen_strokes.py`. Evan uploaded the 45 rebuilt
`pp-temple-<slug>.json` files and `pp-pen-draw.js` to the **"Claude Code V2"**
theme (`gid://shopify/OnlineStoreTheme/194242150772`) and published it. The
homepage showcase is on `templates/index.json` and the product band is on
`templates/product.json`. The old live theme (id 193770258804) is unpublished
and now named "Claude code original".

Details and the rebuild command: `theme/README.md`. Rollback: the unpublished
"Claude code original" theme still holds the version 1 files, and git history has
the old `theme-backup/` copies (removed 6 Oct 2026).

**Fixed 3 October 2026: the Salt Lake tee's chest logo image.** Its "chest logo
flat lay - Maroon" was a Manti back print (same 1,259,725-byte file as the Manti
tee's back; every other tee front is 1,071,804 bytes). The archive copy
`flat-originals/salt-lake/tee_maroon_front.png` was the same Manti back. The live
image was replaced with the standard chest logo flat lay, put back in slot 2 and
the wrong one deleted; it was bound to no variant. The archive copy is now the
standard front, identical to the other 44 temples', so a rebuild cannot
republish the Manti print. The Salt Lake crew and hoodie were checked and are
correct.

**Pushed 6 October 2026:** the 22 to 24 September hoodie rebuild (the Eden
Green rollout in the section below), found missing from git on 1 October, had
been committed on one Mac but never pushed. It is now on GitHub.
`scripts/web_drawings.py` came in with the branch merge below. The Easify option-set CSV below
predates the hoodie rebuild, so check that its hoodie rows point at the new
handles before you import it.


**Merged 6 October 2026: the 23 September `pen-drawn-temples` branch.** Now on
main: `scripts/web_drawings.py` (build, push and check the drawing files),
`scripts/pen_templates.py` (golive and revert for the two page layouts),
`scripts/design_collection.py`, `web_drawing.py`, the theme sections
`pp-temple-showcase` and `pp-temple-drawing`, the browser harness
`theme/dev/harness.html`, their tests, and the spec and plan under
`docs/superpowers/`. `pp-pen-draw.js` stays the 1 October version, which is the
one live. The branch planned to go live through `pen_templates.py golive`; the
drawings went live on 2 October through the Claude Code V2 theme instead. These
items from the branch plan may still be open, and nothing in git confirms them
either way:

- Done 6 October 2026: the "Temple Design Products" collection
  (`temple-design-products`) is published to the Online Store. The Claude Code
  V3 zoom preview theme's "Shop by garment" row reads it.
- Collections, 6 October 2026. Main menu "Shop" now goes to Temple Design
  Products with no sub-links. `temple-tees` is kept as the hidden marquee
  source: retitled "Marquee: designed temples", hidden from search, handle
  unchanged because the live marquee reads it by handle. Its `garment:tee` rule
  means every new temple's tee joins the marquee with no extra step. Redirects
  to Temple Design Products exist for `temple-crewnecks`, `temple-hoodies` and
  `all-products`. Still open, Evan in admin (the store connector refuses to
  unpublish): untick every sales channel on Temple Crewnecks, Temple Hoodies
  and All Products. All Temples stays until the live V2 homepage stops using
  it ("Find your temple" button and "The temples" row); then unpublish it and
  redirect `/collections/all-temples`. V3 no longer uses it: its "The temples"
  row is removed and its button points to Temple Design Products.
- Evan's call: the navy "LIMITED TIME" announcement bar sits between the black
  header and the black banner. Keep it or change it.
- The review sign-off on commits `67f5383..ff4a8f1` was never run.
- If the navy buttons and orange-only Add to Cart went live, BRAND.md section 8
  needs them.

---

# DONE 23 Sep 2026: the Eden Green hoodie rollout. Follow-ups below still open.

All 45 temple hoodies are live with seven colours, Eden Green (Tapstitch 6655)
included, and a full read-only `--verify` passed on all 45. Tapstitch cannot add a
colour to a listing, so each temple was a swap: a new Shopify product took the old
one's address, and the old one is DRAFT at `<address>-retired-<date>`. The driver
is `scripts/eden_green_rollout.py` (its docstring holds the sequence and traps);
per-temple ids and timestamps are in `artifacts/tapstitch/eden-green-rollout.json`.
Boise's wrong-temple photos were repaired along the way.

Re-check any time, read-only:

```bash
./.venv.nosync/bin/python scripts/eden_green_rollout.py --verify
```

A transient Shopify CDN 503 while it downloads an image shows as a failure;
re-run that temple alone before treating it as real (Ogden Original, 23 Sep).

Publishing from Claude needed a standing permission for exactly
`./.venv.nosync/bin/python scripts/eden_green_rollout.py --apply --publish`, which
Evan added to `.claude/settings.local.json` on his MacBook Air on 23 Sep. That
file is per machine and untracked.

**Decided (Evan, 22 Sep):** Eden Green stays third in the colour swatches, where
Tapstitch puts it. Do not reorder.

**Still open, Evan:** re-import `artifacts/easify/option-sets.csv` in
the Easify app. Easify binds the Temple dropdown to a product's internal id, so
every swapped hoodie is missing it until then. This is the single highest-value
manual step outstanding: the catalogue is complete (135 products live, all 45
temples on all three lines, no unbuilt ledger rows), and each of the three sets
carries 46 rows, one default plus 45 temples. After importing, export fresh from
Easify and run `easify_options.py reseed --export <file>`. That reseed has never
been run, and the CSV still carries one old, unused set under placeholder id
900001 (sync passes it through untouched), so whether Easify matches an existing
set by title or creates a second one on each import is still an open question.

**Waiting on that import: one product per garment for hoodies and All Temples.**
Evan's decision, 23 Sep: garment collections show only the parent (Salt Lake),
and shoppers reach every other temple through the Easify dropdown. Tees and
Sweatshirts already work this way: the Salt Lake tee and crew carry the tag
`listing:parent`, and `temple-tees` / `temple-crewnecks` require `garment:<x>`
AND `listing:parent`. Hoodies were held back because the Salt Lake hoodie has no
dropdown until the import, so it would be a dead end. After the import: tag
`cloud-temple-hoodie` with `listing:parent`, give `temple-hoodies` the same two
rules, and change `all-temples` to the single rule `listing:parent`. The homepage
"The temples" row reads all-temples, so it drops to the three parents; that is
intended. Utah, Idaho and California collections stay as they are (Evan).

**Also outstanding:** the storefront overhaul doc
(https://claude.ai/artifact/RhgF4QLwLjQhhKmYnMYrd2, rev 52) still says Boise is
finished; its "State as of" section needs the completed rollout.

---

# Tapstitch pipeline: reference

## Getting this machine ready

Full instructions are in `docs/new-machine-setup.md`. The short version:

```
uv python install 3.12.8
uv venv --python 3.12.8 --seed .venv.nosync
./.venv.nosync/bin/pip install -r requirements.txt
```

Then put the tokens in `.env` (gitignored, never committed, never printed):
`SHOPIFY_STORE_DOMAIN`, `SHOPIFY_ADMIN_TOKEN`.

### TRAP: check for iCloud duplicate folders before anything else

This bit this project once already. iCloud resolves a sync conflict by creating a
second copy of a directory and leaving the original empty, so you end up with an
empty `garments/` beside a full `garments 2/`. The code then cannot read its own
config and git reports every tracked file as deleted.

```bash
ls -d *\ 2 2>/dev/null   # anything listed here is the problem
git status --short | head
```

If it has happened: confirm each plain directory holds ZERO files
(`find garments -type f | wc -l`), then `rm -rf garments && mv "garments 2" garments`
for each pair. Do not merge them by hand without checking first.

---

## Mechanisms worth knowing

Run `./.venv.nosync/bin/python scripts/tapstitch_publish.py check` any time for
the live blocker list.

### The one that would have failed QUIETLY, now closed

**The placement mapping is derived.** `get_template()` returns
`craftItemDto.customArea`, in which every printable side states its own rectangle
on the editor's 700x700 canvas. `tapstitch_api.print_areas()` reads it and
`placement()` turns it into geometry: the object's centre is the rectangle's
centre, and the scale is the rectangle's height over 700. Checked against the
15 Sep tee, which it reproduces to within the half pixel the editor rounded away.
`placement()` also refuses a print file whose shape does not match its print area,
so the one assumption underneath it is checked rather than silent.

### THE VARIANT IMAGE IS THE ONE THE SHOPPER SEES

Run `scripts/tapstitch_variant_images.py` after every publish. It is not optional
and not a fallback.

Tapstitch attaches each mockup to a colour, and Shopify binds each variant to the
FIRST image of that colour at import. Tapstitch sends fronts first, and the front
of these garments is a 6in logo on a blank garment, so every variant lands bound to
an almost empty shirt. The theme shows the SELECTED VARIANT'S image, which is a
fourth thing called "default" and the only one anyone actually sees: the gallery
order and the featured image can both be right while the page still opens on the
blank front.

Posting the mockups back-first fixes the gallery and was confirmed to carry
through, but MEASURED 16 Sep on the hoodie, it does not change the binding. An
earlier note in this file claimed it did; that claim was wrong.

Do not try to work out which image is which by position. Two rules were tried and
both were confidently wrong: pairing colours by their order in the variant list
(the colour reorder rewrites that sequence, and it bound Gray to the black
garment's photo), and splitting the gallery in half (the 15 Sep tee's gallery is
interleaved, front/back per colour, so the rule corrupts it). The only exact key is
Tapstitch's own mockup metadata matched by filename.

#### FIXED 17 Sep 2026: the post-publish fixups could run before Shopify finished importing

**Found on the 16 Sep catalogue run, FIXED 17 Sep in commit 6a02113.** Kept here
because the mechanism explains several things in this file and is worth not
rediscovering. One product of the 102, the Saratoga Springs crew,
came out with its colour still named "Flower Gray" and all 10 variants bound to
the FRONT mockup, the near-blank logo garment. The run log reported success for
both steps. It was caught only by checking the live store by hand afterwards, and
repaired with `tapstitch_variant_images.py --handle ...` plus
`shopify_fixups.py all --handle ...`.

Mechanism: `wait_for_shopify` returns the moment
the product RECORD exists, but Tapstitch keeps pushing variants and media after
that. The ledger shows every row went distribute-to-live in 24 to 42 seconds,
against the "over a minute" the `wait_for_shopify` docstring measured on 15 Sep,
so all 102 rows ran their fixups inside that import window. Inside it,
`rebind()` sees variants with no media, so `bound` is None, so it queues no
update and returns None, and `finish_half` reads that None as "already on the
back". The rename lands and is then overwritten, most likely by that same
continuing import. Every row rolled the same dice; one lost.

Read the evidence precisely, because the fix depends on it. The rebind path
returning None on media-less variants, and finish_half reading that None as
success, are both confirmed from the code. That something later rewrote the
colour name is certain, since "Flower Gray -> Gray" only logs after
productOptionUpdate returned no errors. That the overwrite came from Tapstitch's
continuing import is INFERRED and has not been observed directly. So whoever
fixes this should measure the settle condition on the next publish (watch the
variant and media counts) rather than assume the window closes at a fixed time.

The dangerous part is that None means two different things: "every variant is
already correct" and "no variant has an image yet". Nothing reads the product
back before the ledger is set to `live`.

What was done. `wait_for_import()` polls until every variant carries an image and
the variant and media counts repeat, and `finish_half` runs it before ANY fixup.
The counts must be seen twice because an import that has delivered only its first
colourway looks finished; the deadline governs REACHING that state, not
confirming it. `rebind()` now separates "no variant carries an image yet" from
"all already on a back". `stale_colorways()` reads the colour values back after
the rename and raises if a Tapstitch name survived. Both failure paths leave the
product live and the row short of `live`, so the next run resumes at the Shopify
half rather than distributing again. Pinned in `tests/test_tapstitch_run.py`.

It costs about 15 seconds a product and is worth it: on the 17 Sep run every
product needed a real rebind, which is exactly the work the old code skipped
whenever it lost the race.

Audit anyway after any publish run.

#### TAPSTITCH DROPS CONNECTIONS AFTER A LONG BURST

Measured 17 Sep 2026, and it is the reason to publish in small batches. A
`--limit 29` run published 12 products at a steady 52 seconds each and then hit a
wall: 17 ConnectionError failures in a row against www.tapstitch.com, mostly
RemoteDisconnected and "Max retries exceeded", plus one Shopify read timeout. The
login session was still valid, and the same calls succeeded again minutes later,
so read it as rate limiting or a burst cutoff rather than an outage or an expired
session. Nothing in the run hung: the requests carry timeouts and the failures
were reported and counted.

It fails at the worst moment. The failures landed AFTER distribute and after the
Shopify fixups, inside rebind(), so three Kirtland products sat live on the
storefront with every variant bound to the blank front until the next run resumed
them. Nothing was lost and the resume path repaired all three, but that window is
customer-visible.

So: run long catalogues in batches of about five with a gap, not one large
--limit. Three five-row batches ran clean immediately after the failure. A retry
with backoff around the Tapstitch calls is the real fix and has not been written. It takes BOTH commands, because
the two symptoms need different checks and running one proves nothing about the
other:

- `scripts/tapstitch_variant_images.py --report-only` checks the image binding
  against Tapstitch's own mockup metadata. It caught this one and cleared the
  other 103. It does NOT see a reverted colour name.
- `scripts/shopify_fixups.py all --report-only` is what catches a reverted
  rename; it reports "maybe Flower Gray -> Gray" for any product still carrying
  the old name.

### THE SIZE GUIDE UNIT TRAP

Tapstitch bakes its own size-guide table into `description.content` at the moment
the store product is created, and **it defaults to BOTH unit systems**: the
prefill comes back with IMPERIAL and METRIC both selected, which produces inch/cm
column pairs. Evan's rule, 16 Sep 2026, is imperial only. The runner must take
`sizeGuide.descriptionHtml["IMPERIAL"]`, never `["BOTH"]`.

Know what that table is, though: the IMPERIAL variant carries **no unit label
anywhere**. It is bare numbers, "Chest 23.62", with nothing saying inches. That is
what the live tee shipped with on 15 Sep before the repo's own section replaced
it. `reference/garment-copy/*/size-guide.html` says "Measurements (inches)", which
is why the Shopify-side writer wins in the end.

## The one thing to be careful with

`artifacts/tapstitch/pre-migration-catalog.json` is **the only record of what the
store looked like before it went dark** on 14 Sep 2026. Never overwrite it. The
script that could restore the 160 old listings from it was removed on 6 Oct 2026
and is in git history; the six deleted products cannot come back at all. Old
listings stay DRAFT and are never deleted (Evan's confirmed 16 Sep decision,
`post_publish.delete_old_listing` is false).

## Reading order for a new session

1. This file.
2. `docs/decisions.md`, from the 14 September entries down. Everything settled,
   with the mechanism behind each choice.
3. `docs/tapstitch-migration-plan.md` for the approach and the status table.
4. `docs/discovery/2026-09-tapstitch-store-findings.md` for what the live store
   revealed, including the empty-productType trap.
5. `../BRAND.md` sections 6, 7, 8, 18, 19. Not in git; it syncs through iCloud.

## Review of 2 October 2026

The whole "not yet reviewed" list went through review on 2 October 2026: the
hoodie publish and blank configs, `tapstitch_variant_images.py`, the Easify
`sets.json` rebind, the hoodie size guide, `test_tapstitch_placement.py` and its
fixtures, the `post_publish` wiring, `tapstitch_capture.py` and the retired
selector block, `tapstitch_api.py`, the blank specs and colour configs,
`colorway_renames_by_type`, centring and spacing (the value is 0.7in, settled
in docs/decisions.md; "0.8in" was a stale label), the `kept`-records change, and
the test rewrites. Also reviewed: `scripts/pen_strokes.py` and
`theme/assets/pp-pen-draw.js`. Six reviewers, one per area, then a judge who
checked every finding against the code. Nothing touched Tapstitch or the store.

**Fixed (clearly broken):**
- `tapstitch_publish.py check` printed "blocked" for missing swatches and colour
  name drift but exited 0. It now exits 1.
- `tapstitch_capture.py` truncated a body before redacting it, so a JSON body
  over 200KB was no longer JSON and was written unredacted. It now redacts first.
  The console line also printed the unredacted URL.
- `pen_strokes.py` printed a leftover debug line on every run.

**Open, for a decision or live evidence (nothing here is broken today):**
- *Fails quietly:* `rebind()` returns "nothing to change" when a variant's
  front is not in the pairs or its back is not in the product's media, and the
  row goes live with the shopper on the near-blank front. It needs a check that
  every variant ends on a back; that needs real filenames from a publish.
- *Duplicate risk:* `create_store_product` is a POST with no "create started"
  marker. A lost response then a re-run makes a second store product inside
  Tapstitch. Add a marker like `distribute_started_at`, and never wrap this
  call in retries.
- *Evan's call:* the crew's `lead_colorCode` is Black while its storefront
  first colour is Heather Gray.
- *Second entry point:* `tapstitch_publish.py finish` skips the import wait,
  the rebind and the stale-colour check, and leaves the row in a state the
  runner never resumes. Retire it or make it call the runner's finish.
- *Unknown type:* `mockups_back_first` compares Tapstitch's `colorId` with an int;
  if it arrives as a string the lead-colour sort silently does nothing.
  Normalise both with `str()`.
- *Pen drawing script* (`pp-pen-draw.js`, live): an error inside an animation
  frame freezes the showcase; one bad temple hides the whole showcase rather
  than dropping that temple; no load timeouts; a failed load after a fade
  leaves the stage blank about 5s per retry; old iOS (before 15) collapses the
  drawing box; reduced motion still cycles the showcase. None is triggered by
  the current files. Fixing them means a theme upload.
- *Pen strokes:* 54 of 20,314 committed `lens` values are off by up to 0.22
  units (two different roundings); it crashes on art with no lines or one line
  weight; manti takes 43s. Fix at the next regeneration.
- Smaller: stale comments and docstrings (old colour names, "NOT yet
  replayed"), and a few vacuous or mislabelled tests (the Easify paused set, the
  landscape truncation case).

Several test files need the sibling `../Temples/` and `../Important Elements/`
folders, which a cloud session does not have; run them on the Mac.
`test_eden_green_rollout.py` fails on its "finished" seed check as of 6 Oct 2026
(it did before the cleanup too):

```bash
for t in tests/test_*.py; do ./.venv.nosync/bin/python "$t"; done
```

## Things that are easy to get wrong

- **The preview images are not in git** (`artifacts/tapstitch-previews/`,
  gitignored). Regenerate with `scripts/tapstitch_preview.py`, about seven
  minutes for the catalogue. The published artifact link is the shareable copy.
- **Memory does not travel between machines.** The notes under
  `~/.claude/projects/.../memory/` are local to whichever Mac wrote them. This
  file and `docs/decisions.md` are the portable record, which is why they are
  detailed.
- **`flatten.py`'s caches are deliberately tiny** (8 and 4). A print-area-sized
  raster is about 67MB; a 256-entry cache held gigabytes and the machine swapped
  instead of working. Callers iterate temple-major, so small is correct.
- **Tapstitch publishes with an EMPTY productType** and every Shopify fixup is
  keyed on it, so they silently no-op and report success. The runner sets it
  first, before any fixup.
