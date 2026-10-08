# Temple Product Generator

Generates Peculiar People temple products on Tapstitch, one product per temple per
garment line: the tee (RT0063), the crew sweatshirt (R00368) and the hoodie
(R00286). Tapstitch is the only channel since the September 2026 migration
(`docs/tapstitch-migration-plan.md`). 135 products are live, all 45 temples on all
three lines.

Products are built from Python against Tapstitch's own JSON API, published to
Shopify, then finished on the Shopify side (product type, colour fixups, art card,
variant images). Settled decisions and the mechanism behind each are in
`docs/decisions.md`; work in flight is at the top of `HANDOFF.md`. The workspace
skill `temple-product-generator` drives the pipeline.

## Setup

```
uv python install 3.12.8
uv venv --python 3.12.8 --seed .venv.nosync
./.venv.nosync/bin/pip install -r requirements.txt
```

Put `SHOPIFY_STORE_DOMAIN` and `SHOPIFY_ADMIN_TOKEN` in `.env`. `.env` is gitignored
and must never be committed or printed. Tapstitch needs no token: Evan logs in once
with `scripts/tapstitch_login.py` and the session lives in a dedicated Chrome
profile. Full steps: `docs/new-machine-setup.md`.

In a cloud session there is no Chrome profile, so `tapstitch_api.session()` reads
the login cookies from the `TAPSTITCH_COOKIES` environment secret instead (the
Cookie header copied from DevTools on tapstitch.com, or a JSON cookie export). It
is a full login, not a read-only key, and it expires after a few days like the
profile's session. Check it with `python scripts/tapstitch_designs.py`, which
lists the Designs tab and stops with "Not logged in" if the cookies are stale.

The venv is named `.venv.nosync` so iCloud Drive does not sync interpreter files. If
it is ever lost, recreate it from `requirements.txt`.

## Layout

- `layout.py`: the layout engine. Positions everything from the temple's INK, never its SVG frame.
- `generate.py`: shared helpers. Temple manifests, art detection, product titles,
  and the fixed description sections (`description_for()`).
- `description_html.py`, `shopify_client.py`: description assembly and the Shopify Admin API.
- `flatten.py`: composites one temple into one flattened, print-area-shaped PNG, and validates it.
- `ledger.py`: the ledger, one row per temple per garment (`artifacts/tapstitch/ledger.json`).
- `tapstitch_api.py`: the Tapstitch JSON API client.
- `scripts/tapstitch_designs.py`: lists the Designs tab with when each design was saved and
  whether it reached the store; `--unpublished` shows only the ones that never did. Read-only.
- `browser_session.py`, `scripts/tapstitch_login.py`: the dedicated-Chrome session, on port 9223.
- `garments/{tee,crew,hoodie}.json`: blank, print areas, colourways, names, prices and costs per line.
- `config/tapstitch.json`: the API endpoints, timings and post-publish switches.
- `reference/garment-copy/{garment_id}/`: each line's product details and founder
  message, plus the shared `care-instructions.html`.
- `config/swatches.json` and `scripts/swatches.py`: the colour swatch registry, one hex
  per storefront colour name. The live theme paints a swatch only for names it has been
  given a hex for, and a name it does not know renders a white circle on the product
  page. `swatches.py render` prints the block to paste into the theme; `swatches.py
  check` verifies the live store (and the live theme, given a `read_themes` token)
  against the registry. The publish path enforces it; see docs/decisions.md, 18 Sep.
- `scripts/sweep.py`: the sweep. Finds new temple folders and takes each one from
  design PNG to complete on the live site; `verify` proves it. Start here.
- `scripts/tapstitch_build.py`: build every print file from a scan of the Temples folder.
- `scripts/tapstitch_preview.py`: the proof sheet, the record of what each temple shipped with.
- `scripts/tapstitch_approve.py`: record the approval, per temple (the sweep records its own).
- `scripts/tapstitch_status.py`: ledger counts and rows.
- `scripts/tapstitch_publish.py`: `check` (what is blocking a run) and `finish` (the Shopify half for one product).
- `scripts/tapstitch_run.py`: the catalogue runner. Plans by default; `--apply` builds in Tapstitch, `--publish` reaches the storefront.
- `scripts/shopify_fixups.py`, `scripts/tapstitch_variant_images.py`: the Shopify-side repairs, both idempotent.
- `scripts/easify_options.py`, `scripts/art_images.py`, `scripts/mirror_facts.py`,
  `scripts/web_marquee.py`: the Temple dropdown CSV, the art close-up cards, the git
  backup of the facts fragments, and the homepage marquee check.
- `theme/`: copies of the Shopify theme files behind the homepage and the pen-drawn
  temples (`theme/README.md`).

Temple manifests live in the `../Temples/{Name}/Working files/` folders, outside the repo.

## Run sequence

A new temple is one command once its research is in (the `temple-product-generator`
skill does the research when Evan says "run a sweep"):

```
scripts/sweep.py scan                          # every temple folder and what it still needs
scripts/sweep.py run --all-ready               # LIVE: build, publish and finish every ready temple
scripts/sweep.py verify --temple T             # read only: is this temple complete on the site
```

`run` takes each temple through build, proof, approve, publish, tags, gallery,
drawing, download and Art File option, then the Easify CSV and the facts mirror,
then `verify`. Every step skips what is already done, so re-running finishes a
temple that stopped anywhere. What stays manual is printed at the end: the
Easify CSV import, and attaching the Art File download. See `docs/decisions.md`,
7 October 2026.

The steps underneath, for one-off work:

```
scripts/tapstitch_build.py --report-only       # validate every design, write no files
scripts/tapstitch_build.py --temple T          # write the print files
scripts/tapstitch_preview.py --temple T        # the proof sheet
scripts/tapstitch_approve.py --temple T        # record the approval
scripts/tapstitch_publish.py check             # what is still blocking a run
scripts/tapstitch_run.py --temple T            # plan: what would be built, what is blocked
scripts/tapstitch_run.py --apply --publish --temple T   # build and publish. LIVE, no undo.
scripts/easify_options.py sync                 # Temple dropdown CSV; Evan imports it by hand
scripts/web_marquee.py check                   # every live temple on the homepage marquee
```

**Every new temple must be on the homepage marquee.** The marquee
(`theme/sections/pp-temple-marquee.liquid`) shows a temple only once the theme has
its art (`assets/pp-temple-<slug>.webp`), its stroke file
(`assets/pp-temple-<slug>.json`, from `web_drawings.py build` then
`scripts/pen_strokes.py`) and its city line (`snippets/pp-temple-city.liquid`), and
the tee carries `garment:tee` and `temple:<slug>` tags. Without them the temple is
left off with no error. `sweep.py run` does all of it and uploads the files to the
live theme itself; `web_marquee.py check` confirms it. A temple is not finished
until that check is clean.
