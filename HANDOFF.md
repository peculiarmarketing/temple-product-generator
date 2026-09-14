# Tapstitch migration: where this stands

**Last worked: 14 September 2026.** Read this first if you are picking the
migration up on another machine, or in a new session.

---

## For Evan, in one minute

**Your store is dark.** All 160 temple listings are hidden (drafted, not deleted).
The only thing a visitor can buy is the Temple Art File download. Six products
were deleted permanently at your instruction: two stray duplicate listings, the
three Nauvoo Limited Editions, and Cornerstone Sweatpants.

**The blanks are chosen and everything about them is recorded**: the Essential
Cotton T-Shirt RT0063, the Boxy Fleece Crewneck UT0044, and the Oversized Boxy
Fleece Hoodie RW0041. Colours, prices, sizes, costs, and which colour each
product page opens on are all set.

**The designs are settled**: temple and city line on the back, logo on the front,
centred in the print area, city line 0.8 inches tall on every temple. You can see
all 40 at https://claude.ai/code/artifact/63f25017-3639-4bb9-96cc-d16cc1e21d57

**Two things are waiting on you:**

1. **One session with the Tapstitch editor open.** It unblocks four things at
   once, and nothing else can move until it happens. Details below.
2. **Whether the size guide is a new video or the branded chart images** already
   in your `Important Elements` folder. That is the only thing stopping the
   product descriptions being written.

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
| Description plumbing | `generate.fixed_description`, `reference/garment-copy/` | Done. Copy not written. |
| Browser session | `browser_session.py`, `scripts/tapstitch_login.py` | Written, never exercised. |
| Editor automation | `config/tapstitch.json`, `scripts/tapstitch_publish.py` | Config scaffolded, 18 nulls. Editor half unwritten. |

Run `./.venv.nosync/bin/python scripts/tapstitch_publish.py check` any time for
the live blocker list.

## What is blocked

**On one Tapstitch editor session** (the big one, unblocks four things):

1. The six print areas (front and back for each line). They exist only inside
   their editor. Every print file today is built on a PLACEHOLDER canvas of
   4494x5097 at 300dpi, marked `"tbd"` in each garment config. Everything
   rebuilds when the real numbers land.
2. The 18 null values in `config/tapstitch.json`.
3. Confirming the colour swatch names match `colorways` in `garments/*.json`.
   Evan supplied those names and the tee's came across from a blank that is no
   longer used, so a spelling may differ. A mismatch fails SILENTLY: the
   storefront rename finds nothing to rename and the colour reorder cannot find
   its lead colour.
4. **Before writing a single selector**, open the network tab and save a design by
   hand. If that save call carries positions and upload references, a direct call
   replaces the whole click path and most of item 2 disappears. This is the
   highest-value thing to do first and it is easy to skip.

**On a decision:** whether the size guide is a new video per blank or the branded
chart images in `Important Elements/`. Blocks the three product copy files.

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

## Not yet reviewed

The work up to and including the store pull-down went through the full review
loop (six specialists plus a final judge, all signed off). **Changes made after
that review have not been through it**: the blank specs and colour configs, the
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
