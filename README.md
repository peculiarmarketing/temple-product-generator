# Temple Product Generator

Generates Peculiar People temple products, one product per temple per garment.

**Two channels as of 14 September 2026.** The catalogue is moving from Printify
to Tapstitch blanks (Evan's decision; see `docs/tapstitch-migration-plan.md`).
The Printify pipeline stays on disk as the fallback and is not deleted until
Tapstitch is proven on real orders. Garment configs carry a `channel` field and
the two paths never touch each other's garments.

The authoritative spec for the Printify pipeline is
`docs/temple-catalog-generator-plan.md` (Revision 2). Work proceeds phase by
phase; a phase does not start until the previous phase's gate has been confirmed
by Evan.

## Status

| Phase | State |
|---|---|
| 1. Prove the API round-trip | Done, gate passed. Report: artifacts/phase1/findings.md |
| 2. Layout math | Done, gate passed 17 Aug 2026. Previews: artifacts/phase2-previews/. Decisions: docs/decisions.md |
| 3. Templates and generator | Done, gate passed (Logan rehearsal; San Antonio full set generated) |
| 4. Skill and manual trigger | Done. Project skill in ../.claude/skills/; no schedule by Evan's choice |
| 5. Backfill | Closed: Evan decided no backfill. --in-place available for one-offs |

## Setup

```
uv python install 3.12.8
uv venv --python 3.12.8 --seed .venv.nosync
./.venv.nosync/bin/pip install -r requirements.txt
```

Put the Printify Personal Access Token in `.env` (see the placeholder comments in that file). `.env` is gitignored and must never be committed.

## Layout

Shared by both channels:

- `layout.py`: the layout engine. Positions everything from the temple's INK, never its SVG frame.
- `generate.py`: temple manifests, art detection, description assembly. Also the Printify pipeline.
- `description_html.py`, `shopify_client.py`: description assembly and the Shopify Admin API.
- `reference/garment-copy/{garment_id}/`: each garment's product intro and size guide.
- `config/swatches.json` and `scripts/swatches.py`: the colour swatch registry, one hex
  per storefront colour name. The live theme paints a swatch only for names it has been
  given a hex for, and a name it does not know renders a white circle on the product
  page. `swatches.py render` prints the block to paste into the theme; `swatches.py
  check` verifies the live store (and the live theme, given a `read_themes` token)
  against the registry. The publish path enforces it; see docs/decisions.md, 18 Sep.

Printify only:

- `printify_client.py`: the Printify REST client.
- `scripts/phase1.py`, `artifacts/phase1/`: Phase 1 driver and its gate report.
- `scripts/add_date_layer.py`, `scripts/printify_login.py`: the date-layer browser automation.

Tapstitch only:

- `flatten.py`: composites one temple into one flattened, print-area-shaped PNG, and validates it.
- `ledger.py`: the migration ledger, one row per temple per garment.
- `browser_session.py`, `scripts/tapstitch_login.py`: the dedicated-Chrome session, on port 9223.
- `config/tapstitch.json`: the API endpoints, blanks, timings and post-publish switches.
- `scripts/tapstitch_build.py`: build every print file from a scan of the Temples folder.
- `scripts/tapstitch_preview.py`: the proof sheet Evan reviews before anything uploads.
- `scripts/tapstitch_status.py`: where the migration has got to.
- `scripts/tapstitch_publish.py`: `check` (what is blocking a run) and `finish` (the Shopify half for a product published by hand).
- `scripts/tapstitch_run.py`: the catalogue runner. Plans by default; `--apply` builds in Tapstitch, `--publish` reaches the storefront.
- `scripts/store_pulldown.py`: take the Printify catalogue off the storefront.

Reserved at project root for later phases (do not create early): `layout.py`, `preview.py`, `generate.py`, `garments/`, `spacing_defaults.json`. Temple manifests will live in the existing `../Temples/{Name}/` folders.

The venv is named `.venv.nosync` so iCloud Drive does not sync interpreter files. If it is ever lost, recreate it from `requirements.txt`.

## Tapstitch sequence

```
scripts/store_pulldown.py snapshot            # record the catalogue. Always first.
scripts/store_pulldown.py draft                # dry run by default; read it with Evan
scripts/store_pulldown.py draft --apply        # the real thing. Evan initiates this.
scripts/tapstitch_build.py --report-only       # validate every design, write no files
scripts/tapstitch_preview.py                   # the proof sheet, for Evan's gate
scripts/tapstitch_build.py                     # write the print files, once blanks are picked
scripts/tapstitch_publish.py check             # what is still blocking a run
scripts/tapstitch_run.py                       # plan: what would be built, what is blocked
scripts/tapstitch_run.py --apply --publish --limit 1   # one product, watched. LIVE.
scripts/web_marquee.py check                   # every live temple on the homepage marquee
```

**Every new temple must be added to the homepage marquee.** The marquee on the
homepage (`theme/sections/pp-temple-marquee.liquid`) shows a temple only once
the theme has its art (`assets/pp-temple-<slug>.webp`), its stroke file
(`assets/pp-temple-<slug>.json`, built by `scripts/pen_strokes.py`) and its city
line (`snippets/pp-temple-city.liquid`). Without them the temple is left off with
no error. `tapstitch_run.py --publish` runs `scripts/web_marquee.py check` on
the way out and lists what each new temple is missing; `web_marquee.py sync`
regenerates the city-line snippet and prints the `shopify theme push` command
for the rest. A temple is not finished until that check is clean.

## Printify end-of-run sequence

1. Run the sweep or a targeted generate (`generate.py --sweep` or `--temple ...`) to produce drafts.
2. (Optional) `scripts/add_date_layer.py` adds date layers to With Date drafts via the browser; skipping it means adding layers by hand as before.
3. `scripts/publish_drafts.py` publishes base drafts and verified dated drafts; economy-off drafts are held until Evan flips Economy on in the Printify UI.
