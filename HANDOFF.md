# Tapstitch migration: where this stands

**Last worked: 15 September 2026, night.** Read this first if you are picking the
migration up on another machine, or in a new session.

**The headline: the migration works end to end and one product is LIVE.** The
Tapstitch editor turned out to be a JSON API, it is now driven from Python
(`tapstitch_api.py`), and a real tee was published to the storefront through it.
What is left is copy, the other two blanks, and one unsolved geometry question.

---

## For Evan, in one minute

**Your store is dark except for two things.** All 160 temple listings are still
hidden (drafted, not deleted). A visitor can buy the Temple Art File download —
and, since the night of 15 September, **one live tee**: "Essential Heavyweight
Temple Tee", ACTIVE, 30 variants at $44.99, carrying the Salt Lake back print.
It was published deliberately, as the end-to-end test of the new route. It is
real and purchasable. Draft it if you do not want it sold.

Note what that product is NOT: its title names no temple, and its handle
(`essential-heavyweight-temple-tee`) inherited nothing from a predecessor. The
real run needs both — the catalogue naming pattern is "Essential Temple Tee
(West Jordan)", and `delete_old_listing` exists so each replacement takes over
its predecessor's URL and does not break the Easify dropdown. This test did not
exercise that.

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

**Two things are waiting on you:**

1. **The tee's `product-intro.html`.** It is the single thing between here and
   descriptions working for every future temple. `fixed_description()` returns
   EMPTY for the tee until it exists, by design. The CC1717 intro could not be
   reused: it claims garment-dyed ringspun cotton at 6.x oz, and RT0063 is 7.7
   oz (260 gsm) and not garment-dyed, so copying it would publish false claims.
   This is new outward-facing prose, so it goes through the `humanizer` then
   `structural-humanizer` passes before it ships.
2. **Whether the size guide gets a new video** or the branded chart images in
   `Important Elements/`. This is now ONLY about the video — the measurements are
   settled and written. The CC1717 section embeds a per-blank video showing the
   wrong garment, so it was omitted rather than reused.

**And one thing that will fail quietly if ignored:** the design placement numbers
were copied from watching one tee, not derived from the print area. They are
right for the tee and unknown for the crew and hoodie. Work out the
canvas-to-print-area mapping before generating placement for those two, or they
will misprint without erroring.

**And one small thing to look at when you next see a mockup:** Flower Gray on the
crew is set to print white like everything else, on the assumption it is as dark
as the colourways it replaced. If it is not, its ink becomes black and the black
art files have to be built for it. Every other colourway on every line is dark
enough that white is certain.

**Worth a second look on price:** the crew blank costs more than the hoodie blank
($16.57 against $14.92) and their all-in costs are within $0.57 of each other,
but the crew sells for $10.00 less. That is $9.43 less gross on a garment that
costs the same to make. Prices are unchanged and this is flagged, not decided.

**Nothing else needs you.** The five untraced temples (Albuquerque, Billings,
Burley, Lehi, Provo Rock Canyon) already have your sketches in their folders and
can be traced whenever.

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
| Editor automation (click path) | `_selectors_superseded_by_api` | RETIRED 15 Sep 2026. There is no click path any more. |
| Catalogue runner | `scripts/tapstitch_publish.py` | Still unwritten. This is the next build. |

Run `./.venv.nosync/bin/python scripts/tapstitch_publish.py check` any time for
the live blocker list.

## What is blocked

**On copy, not on Tapstitch.** The API route is finished and proven:
`create_template` -> signed OSS upload -> `save_design` -> `distribute`, all run
against the live account, ending in a real published product. See
`docs/discovery/2026-09-tapstitch-editor-api.md` for payloads and every trap.

1. **The tee intro** (above). Blocks descriptions for all temples.
2. **The crew and hoodie are unexercised.** Only the tee (RT0063, DTG) has been
   through the route. The two fleece blanks print DTF, and their Tapstitch
   `productId`, colour codes and measurements are all unknown. Capture one
   hand-built design per blank the same way the tee was done.
3. **The catalogue runner does not exist yet.** `tapstitch_api.py` is the
   library; nothing drives it over 135 rows, handles the handle inheritance, or
   sequences the Shopify fixups.

### The one that will fail QUIETLY

Everything else on this list errors or returns empty when it is wrong. This one
does not:

**The design placement numbers were copied, not derived.** `left: 344, top: 358`
on a 700x700 canvas came from watching one tee. They are correct for the tee and
UNKNOWN for the crew and hoodie, which have different print areas. Generate
placement for those two without first working out the canvas-to-print-area
mapping and the art will be misplaced on the garment, with no error anywhere —
just wrong shirts. Do that mapping before the first fleece product.

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

`delete` is the only operation with no undo. It needs `--handle` and a matching
`--confirm-handle`, and it is pinned to the product id in the snapshot rather than
whatever the handle resolves to now, because the Tapstitch replacement inherits
the old handle by design.

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
4. Then either the tee intro, or a capture run on the crew to start the second
   blank. `scripts/tapstitch_capture.py --minutes 30`, build one design by hand,
   and it records the ids, colour codes and geometry the way the tee's were got.

## Not yet reviewed

The work up to and including the store pull-down went through the full review
loop (six specialists plus a final judge, all signed off). **Changes made after
that review have not been through it**, and that now includes everything from
15 September: `tapstitch_api.py`, `scripts/tapstitch_capture.py`, the retired
selector block, and the tee size guide. The API client has been exercised against
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
