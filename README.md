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
- `scripts/tapstitch_build.py`: build every print file from a scan of the Temples folder.
- `scripts/tapstitch_preview.py`: the proof sheet Evan reviews before anything uploads.
- `scripts/tapstitch_approve.py`: record Evan's approval, per temple.
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

```
scripts/tapstitch_build.py --report-only       # validate every design, write no files
scripts/tapstitch_build.py --temple T          # write the print files
scripts/tapstitch_preview.py --temple T        # the proof sheet, for Evan's gate
scripts/tapstitch_approve.py --temple T        # only after Evan approves
scripts/tapstitch_publish.py check             # what is still blocking a run
scripts/tapstitch_run.py --temple T            # plan: what would be built, what is blocked
scripts/tapstitch_run.py --apply --publish --temple T   # build and publish. LIVE, no undo.
scripts/easify_options.py sync                 # Temple dropdown CSV; Evan imports it by hand
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
