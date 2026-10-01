# OPEN, 1 October 2026: upload the rebuilt pen drawings (needs the Mac)

The pen-drawing animation on the homepage showcase and product band now draws
each temple in drawing order: outline, inner structure, windows and doors one at
a time, small marks. Evan approved the samples and all 45 temples are rebuilt.
**They are not on the store yet.** The Claude store connector cannot write to
the live theme ("Copy of shrine-theme-pro", id 193770258804), so the upload
has to be done from the Mac.

To finish it:

1. Get this branch, which is not on `main` yet:
   `git fetch origin && git checkout claude/recent-website-changes-hbgeu4`
2. From `temple-product-generator/`, push only these files:

       shopify theme push --path theme --theme 193770258804 --nodelete \
         --only 'assets/pp-pen-draw.js' --only 'assets/pp-temple-*.json'

   Keep `--nodelete`. Without it the push deletes every theme file not in
   `theme/`. Upload the JS together with the JSON files.
3. Check `?view=pen-preview` on the homepage and on a product page.
4. Delete this section, and merge the branch to `main`.

No Mac: in Shopify admin, Online Store > Themes > "Copy of shrine-theme-pro" >
Edit code > assets, upload `theme/assets/pp-pen-draw.js` and the 45
`theme/assets/pp-temple-*.json` files, replacing the existing ones.

The animation is still preview-only after the upload. Making it live (adding
the sections to `templates/index.json` and `templates/product.json`) is a
separate decision for Evan. Two notes for that decision: the homepage showcase
breaks rule H14 in the 2 September store audit (nothing above the fold moves),
and its heading and text are new customer-facing copy that needs the humanizer
passes before it ships.

Details: `theme/README.md`. Rollback: `theme-backup/2026-09-23-original/`.

**Also found on 1 October and not in git:** the 22 to 24 September hoodie
rebuild (45 new hoodies with Royal Blue added, old ones drafted with
`-retired-2026-09-23` handles) and `scripts/web_drawings.py`, which made the
original drawing files. Both were run from a machine whose work was never pushed.
Commit them from that machine. The Easify option-set CSV below predates the
hoodie rebuild, so check that its hoodie rows point at the new handles before
you import it.

---

# Tapstitch migration: where this stands

**Last worked: 16 September 2026, third session.** Read this first if you are picking the
migration up on another machine, or in a new session.

**The headline: the catalogue is COMPLETE. 135 products are live**, all 45
temples across all three garment lines, and the migration ledger has no unbuilt
rows left. The Tapstitch editor turned out to be a JSON API, it is now driven
from Python (`tapstitch_api.py`), and the catalogue runner
(`scripts/tapstitch_run.py`) has published every ready row. All three blanks are
exercised, the geometry question is closed, and the product copy for all three
garments is written.

The store is no longer dark, and nothing is waiting on research. The last ten
temples were unblocked on 17 September: five of them (Logan, Provo, Kirtland,
Cody, Taylorsville) turned out to have researched facts ALREADY, published on
their old Printify listings and never saved back to the temple folder, and were
recovered from the live markup; five (Albuquerque, Billings, Burley, Lehi, Provo
Rock Canyon) were researched from scratch. Source ledger for all ten:
`artifacts/description-ledgers/2026-09-16-blocked-ten.txt`.

**One thing needs a person:**

1. `artifacts/easify/option-sets.csv` is WRITTEN AND WAITING TO BE IMPORTED into
   the Easify app by hand. Until that import happens, the Temple dropdown on all
   135 live pages still links to the old Printify addresses, which are drafted and
   therefore dead. This is the single highest-value manual step outstanding. The
   17 September sync added the last ten temples and repointed every row, so each
   of the three sets now carries 46 rows: one default plus 45 temples.
   After importing, export fresh from Easify and run `easify_options.py reseed
   --export <file>`: the "Tee - With Date" set still carries placeholder id
   900001 and that reseed has never been run, so whether Easify matches an
   existing set by title or creates a second one on each import is still the
   open question `docs/decisions.md:40` wanted closed.

That is the whole list. Every temple is published, so the sync no longer reports
any dropdown row pointing at a dead page.

---

## For Evan, in one minute

**Your store is dark except for four things.** The remaining temple listings are
still hidden (drafted, not deleted). A visitor can buy the Temple Art File
download, and three garments:

- **"Essential Heavyweight Temple Tee"**, live since 15 September, ACTIVE, 30
  variants at $44.99, Salt Lake on the back. Its title names no temple and its
  handle (`essential-heavyweight-temple-tee`) inherited nothing, so it does not
  match the catalogue pattern and is best thought of as the route's first test.
- **"Ultra-soft Temple Sweatshirt"** (renamed from "Classic Temple Crew
  Sweatshirt" on 16 September), live since 16 September, ACTIVE, 10
  variants at $64.99, Salt Lake on the back, at `salt-lake-temple-sweatshirt`.
  This one IS the catalogue pattern: the parent title, and the predecessor's own
  web address, so the Easify dropdown link to it still resolves. The old Printify
  listing at that address was deleted to make room, which has no undo.

- **"Ultra-soft Oversized Temple Hoodie"** (renamed from "Cloud Temple Hoodie"
  on 16 September), live since 16 September, ACTIVE, 30 variants at
  $74.99, Salt Lake on the back, at `cloud-temple-hoodie`. Six colours: Navy Blue,
  Black, Gray, Coffee, Mauve and Royal Blue.

All three are real and purchasable. Draft them if you do not want them sold.

**You changed how replacements get their web address, and you confirmed it.**
The old plan deleted each old listing so its replacement could take over its
address. That never worked: Shopify builds a new product's address from its title
and ignores whatever address just came free, so the crew's address had to be set by
hand afterwards and its predecessor was destroyed for nothing. From now on each
replacement simply takes its own address (`cloud-temple-hoodie`), old listings stay
drafted rather than deleted, and the Temple dropdown links are repointed by the
Easify sync, which reads addresses from the live store. Nothing is permanently
deleted any more, which also keeps Printify intact as the way back. The one cost is
that old product addresses stay dead, and they have been dead since 14 September
anyway because those listings are drafted.

Six products were deleted permanently at your instruction: two stray duplicate
listings, the three Nauvoo Limited Editions, and Cornerstone Sweatpants.

**Everything fulfills from the USA now**, which is 4-7 days to a customer's door
against 10-17 from the international center. Two blanks changed with that switch,
because Tapstitch's fulfillment choice changes which colours and sizes a blank
even has.

**The blanks are chosen and everything about them is recorded**: the Essential
Cotton T-Shirt **RT0063** (tee, unchanged), the Fleeced Sweatshirt **R00368**
(crew, two colourways only, Black and Gray), and the Oversize Fleeced Hoodie
**R00286** (hoodie, five colourways, Haze Blue gone). Colours, prices, sizes,
costs, and which colour each product page opens on are all set. The two fleece
blanks print DTF rather than DTG.

**The designs are settled.** The back is the temple and the city line, centred in
the print file with no margins anywhere. The temple spans no more than 12 inches
at its widest, the city line is 0.7 inches tall, and its top sits 0.5 inches below
the temple's lowest point. The front is the logo at 6 inches wide. Every number is
ink to ink, the drawn artwork rather than the file around it. All 40 temples now
reach the full 12 inches on all three garments. The proof sheet at
https://claude.ai/code/artifact/63f25017-3639-4bb9-96cc-d16cc1e21d57 still shows
the older spacing and needs one regeneration.

**The real print areas are in**, so the placeholder canvas is gone and every
garment now has its own.

The 150 DPI reading is CONFIRMED, 15 September 2026, and did not need the editor
after all. Tapstitch's own API states it: a template's `backSideDpiTip` reads
"Print area size 2193 x 2758 px (150)DPI", which is exactly `editor_px` and
`editor_dpi` in `garments/tee.json`, and 14.62 by 18.39 inches.

**The descriptions are written, and their shape changed on 16 September.** Every
product page now reads: the product details (fit, fabric, weight), then the
founder message under a "From the Founder" heading, then the temple's history.
The size guide is no longer in the description at all, your call. The three live
products carry it already. The CC1717 intro could not simply be reused for the
tee: it claims garment-dyed ringspun cotton at 6.x oz, and RT0063 is 7.7 oz
(260 gsm) and not garment-dyed, so copying it would have published false claims.

**One thing is waiting on you:** whether the size guide gets a new video or the
branded chart images in `Important Elements/`. This matters less now that the
guide is out of the description; it is about where a size guide lives at all.

**Every temple now has a researched `temple-facts.html`, and the runner has no
blocked rows.** It still blocks any temple that lacks one, which is correct: the
history section is researched writing judged against a source hierarchy, not
something a script can generate. A NEW temple folder therefore stops the sweep
until someone does that research. That is a step in the workflow, not a bug, and
it is easy to mistake for one.

**The history files are now BACKED UP IN GIT, as of 17 September.** `Temples/`
is still not version controlled, so the fragments still live there as the source
of truth, but `scripts/mirror_facts.py` copies all 45 into
`artifacts/temple-facts/`, which is tracked. That gives the research version
history and a second physical location. It is the one part of this pipeline a
machine cannot regenerate: the five recovered on 17 September were retrievable
only because their old listings still exist as drafts.

The mirror is one way and `Temples/` stays authoritative; the script never writes
back. `--check` exits non-zero when the mirror is stale, and a `--apply` run of
the catalogue runner refreshes it on the way out. Run the script by hand after
editing a fragment outside a run, and commit the result.

Note while you are in there: fragments belong in the temple's `Working files/`
folder. `layout.working_path` reads from the folder root as a fallback, so a
fragment left at the root works and looks fine, which is how ten of them ended up
in the wrong place on 17 September. The mirror resolves through `working_path`
for exactly that reason.

**The thing that would have failed quietly is fixed.** The design placement
numbers used to be copied from watching one tee. They are now worked out from each
garment's own print area, which Tapstitch states in its own API, and the method
reproduces the tee exactly. It was a real risk, not a theoretical one: the crew's
back print area is 16% shorter than the tee's, so the copied numbers would have
printed the art oversized and off centre on every crew, with no error anywhere.

**The Flower Gray ink question is CLOSED: white, your call on 16 September, made
on a real mockup.** It was a real question, not a theoretical one. Flower Gray is
a mid heather, not a dark, and the white line art on it is visibly softer than on
black. You kept white knowing that, because black ink on one colourway would mean
a second listing rather than a second option: a Tapstitch design belongs to the
product, and the colours are just a list attached to it, so there is nothing like
Printify's per-colour designs. Every other colourway on every line is dark enough
that white is obvious. One colourway the config leaves out, 6672 Oat Gray, is
light and would have the same problem more severely.

**Worth a second look on price:** the crew blank costs more than the hoodie blank
($16.57 against $14.92) and their all-in costs are within $0.57 of each other,
but the crew sells for $10.00 less. That is $9.43 less gross on a garment that
costs the same to make. Prices are unchanged and this is flagged, not decided.

**Nothing else needs you.** Every temple in the catalog is traced, researched
and published.

---

## Getting this machine ready

Full instructions are in `docs/new-machine-setup.md`. The short version:

```
uv python install 3.12.8
uv venv --python 3.12.8 --seed .venv.nosync
./.venv.nosync/bin/pip install -r requirements.txt
```

Then put the tokens in `.env` (gitignored, never committed, never printed):
`PRINTIFY_TOKEN`, `SHOPIFY_STORE_DOMAIN`, `SHOPIFY_ADMIN_TOKEN`.

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

## What is done

| Piece | Where | State |
|---|---|---|
| Flattener (design to print file) | `flatten.py` | Done. 120 of 135 pairs validate clean. |
| No-logo back layout, centring | `layout.py` (`back_temple_text`) | Done. |
| Build sweep | `scripts/tapstitch_build.py` | Done. |
| Proof sheet | `scripts/tapstitch_preview.py` | Done. |
| Migration ledger | `ledger.py`, `scripts/tapstitch_status.py` | Done. 135 rows. |
| Store pull-down | `scripts/store_pulldown.py` | Done AND RUN. Store is dark. |
| Colour renames | `scripts/shopify_fixups.py` | Done, config-driven. |
| Description plumbing | `generate.fixed_description`, `reference/garment-copy/` | Done. Tee size guide written; tee intro still missing, so it returns EMPTY. |
| Browser session | `browser_session.py`, `scripts/tapstitch_login.py` | Done AND exercised 15 Sep 2026. |
| **Tapstitch API client** | `tapstitch_api.py` | **Done and proven against the live account, publish included.** |
| Traffic capture | `scripts/tapstitch_capture.py` | Done. Records the editor while you work; automates nothing. |
| Editor automation (click path) | deleted from `config/tapstitch.json` | RETIRED 15 Sep 2026, block DELETED 16 Sep. There is no click path any more; see `_selectors_note`. |
| Store product + publish | `tapstitch_api.store_product_prefill/store_product_payload/create_store_product` | Done and proven: a live crew and a live hoodie, 16 Sep 2026. |
| Variant image repair | `scripts/tapstitch_variant_images.py` | Done, idempotent, REQUIRED after every publish. |
| Geometry and payload tests | `tests/test_tapstitch_placement.py` | Done. Fixtures are trimmed real responses. |
| Catalogue runner | `scripts/tapstitch_run.py` | RUN 16 Sep 2026: 102 products published, 0 failures. See the post-run defect below. |
| Runner tests | `tests/test_tapstitch_run.py` | Done. Pins every resume state and both publish gates. |

Run `./.venv.nosync/bin/python scripts/tapstitch_publish.py check` any time for
the live blocker list.

## What is blocked

**On copy, not on Tapstitch.** The API route is finished and proven:
`create_template` -> signed OSS upload -> `save_design` -> `distribute`, all run
against the live account, ending in a real published product. See
`docs/discovery/2026-09-tapstitch-editor-api.md` for payloads and every trap.

1. **The tee intro** (above). Blocks descriptions for all temples. The crew is
   in the same position and its size guide IS written; only the intro is missing.
   Evan is handling descriptions separately as of 16 Sep.
2. **The crew is exercised; the hoodie is not.** The crew (R00368, DTF) has been
   through create -> upload -> save and Tapstitch rendered mockups from it. Its
   ids, colour codes, print areas and measurements are all recorded. The hoodie
   (R00286) has only its `productId` (1356935091779162112) and its DTF technique,
   both read from the catalogue search. It needs no capture session: the blank
   lookup is `GET /api/services/site/products/search?q=r00286` and its print areas
   come from a template of its own, the way the crew's did.
3. **The catalogue runner is `scripts/tapstitch_run.py`, WRITTEN 16 Sep 2026 and
   not yet run against the live account.** It drives the sequence the 16 Sep
   hoodie publish established: create_template -> upload -> save_design ->
   prefill -> payload -> create -> distribute -> wait for Shopify -> set
   productType -> fixups -> `tapstitch_variant_images.py` -> ledger. There is NO
   delete step and NO handle step. Both belonged to the retired
   inherit-the-address plan; the replacement takes its own address, which Shopify
   derives from its title with nothing to set.

   Run it with no flags for a plan (it writes nothing and opens no Tapstitch
   session). `--apply` permits the Tapstitch-side writes; `--publish` is needed
   as well before anything reaches the storefront, and it also demands a bound
   (`--limit` or `--temple`) because distribute() has no undo and there are about
   a hundred ready rows. THE FIRST LIVE RUN SHOULD BE
   `--apply --publish --limit 1`, watched.

   A six-specialist review on 16 Sep returned Fail before fixes and is worth
   reading for what it caught, because none of it was visible in plan mode: a
   guaranteed KeyError one line after the irreversible distribute (Shopify's
   title lookup did not select `handle`), a resume path that rebuilt and orphaned
   a template it had deliberately recorded, a missing marker between calling
   distribute and confirming it that could either publish twice or strand a live
   product unfinished, and a variant-image repair whose failures were returned as
   strings and recorded as success. All are fixed and pinned in
   `tests/test_tapstitch_run.py`.

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

### DELETING THE OLD LISTING DOES NOT MOVE ITS ADDRESS, WHICH IS WHY IT STOPPED

The 14 Sep plan says a replacement inherits its predecessor's web address once
the old listing is deleted rather than drafted. That holds only when the old
address matches the old title. **It usually does not**: the addresses were minted
under the pre-22-Aug titles and survived the catalogue rename, so the Salt Lake
crew was titled "Classic Temple Crew Sweatshirt" and lived at
`salt-lake-temple-sweatshirt`. 90 of the 120 rows that know their old address are
like that.

Watched happen on the 16 Sep publish: the old listing was deleted FIRST, and the
replacement was still minted at `classic-temple-crew-sweatshirt`, because Shopify
builds a new product's address from its title and ignores whatever just came free.
The crew's address was then set with `productUpdate(handle:)`.

**Evan's decision the same day, asked and confirmed: stop doing this.** Replacements take their own
address, old listings stay drafted, and the Easify sync repoints the dropdown. The
Salt Lake crew keeps the inherited address it already has; nothing after it
inherits one. `delete_old_listing` in `config/tapstitch.json` and the `delete`
command in `store_pulldown.py` are no longer part of the publish sequence.

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
store looked like before it went dark**, and the only way to put the 160 listings
back:

```bash
./.venv.nosync/bin/python scripts/store_pulldown.py restore --apply
```

`snapshot` refuses to overwrite it without `--replace` for exactly this reason. Do
not pass `--replace` while those listings are still drafted. It cannot restore the
six deleted products; nothing can.

`delete` is the only operation with no undo, and it is NO LONGER PART OF THE
PUBLISH SEQUENCE: replacements take their own address and old listings stay
drafted (Evan's confirmed 16 Sep decision, `post_publish.delete_old_listing` is
false). It still exists for a deliberate one-off. It needs `--handle` and a
matching `--confirm-handle`, and it is pinned to the product id in the snapshot
rather than to whatever the handle resolves to now, because a handle can be
reassigned to another product and the snapshot's id cannot.

## Reading order for a new session

1. This file.
2. `docs/decisions.md`, from the 14 September entries down. Everything settled,
   with the mechanism behind each choice.
3. `docs/tapstitch-migration-plan.md` for the approach and the status table.
4. `docs/discovery/2026-09-tapstitch-store-findings.md` for what the live store
   revealed, including the empty-productType trap.
5. `../BRAND.md` sections 6, 7, 8, 18, 19. Not in git; it syncs through iCloud.

## Where to pick up

In order, on a new session:

1. Read this file, then `docs/discovery/2026-09-tapstitch-editor-api.md`.
2. `./.venv.nosync/bin/python scripts/tapstitch_login.py --check` — the session
   lives in a dedicated Chrome profile and survives reboots, but not forever.
3. `./.venv.nosync/bin/python scripts/tapstitch_publish.py check` for the live
   blocker list.
4. Then the catalogue runner. All three garments are now proven end to end, so
   the runner is the 16 Sep sequence written down: prefill, payload, create,
   distribute, wait for Shopify, set productType, run the fixups, run
   `tapstitch_variant_images.py`, update the ledger.

## Not yet reviewed

The work up to and including the store pull-down went through the full review
loop (six specialists plus a final judge, all signed off). **Changes made after
that review have not been through it.** The 16 September morning work DID go
through the full loop
(six specialists plus the judge) and every finding was fixed and signed off, which
covers `print_areas`, `placement`, the store-product calls, the crew blank config
and the crew size guide. NOT yet reviewed: the hoodie publish and its blank config,
`scripts/tapstitch_variant_images.py`, the Easify `sets.json` rebind, the hoodie
size guide, `tests/test_tapstitch_placement.py` and its fixtures, and the
`post_publish` wiring in `finish_on_shopify`. Also still unreviewed from 15
September: `scripts/tapstitch_capture.py` and the retired selector block. The API client has been exercised against
the live account but never reviewed. Also: the blank specs and colour configs, the
`colorway_renames_by_type` mechanism in `scripts/shopify_fixups.py`, the centring
and 0.8in spacing, the `kept`-records change in `scripts/store_pulldown.py`, and
several test rewrites. Run `review-loop` over the delta before any of it drives
the live editor.

All six test files pass as of this commit:

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
