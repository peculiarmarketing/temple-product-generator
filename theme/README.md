# Theme files for the pen-drawn temples

Copies of the Shopify theme assets behind the pen-drawing animation on the
homepage showcase (`sections/pp-temple-showcase.liquid`) and the product page
band (`sections/pp-temple-drawing.liquid`). Before 1 October 2026 these lived
only in the theme. The live theme is "Copy of shrine-theme-pro"
(`gid://shopify/OnlineStoreTheme/193770258804`), and for now only the
`pen-preview` templates use these assets.

- `assets/pp-pen-draw.js`, `assets/pp-pen-draw.css`: the animation.
- `assets/pp-temple-<slug>.json`: stroke files, version 2, built by
  `scripts/pen_strokes.py` from each temple's finished art
  (`pp-temple-<slug>.webp`, unchanged, kept in the theme).
- `../theme-backup/2026-09-23-original/`: the version 1 stroke files and the art
  as they stood before the rebuild, so the change can be undone.

## Rebuild one temple

    python scripts/pen_strokes.py ART.webp OLD.json theme/assets/pp-temple-<slug>.json --debug /tmp/<slug>-tiers.png

The debug image colours each stroke by tier: red outline, yellow inner
structure, blue openings, green small marks.

## Upload

The store connector used from Claude sessions cannot write to the live theme,
so uploads are done from a machine with Shopify CLI logged in to the store:

    cd temple-product-generator
    shopify theme push --path theme --theme 193770258804 --nodelete \
      --only 'assets/pp-pen-draw.js' --only 'assets/pp-temple-*.json'

`--nodelete` matters: without it a push removes every theme file that is not in
this folder. Upload the JS together with the JSON files: version 2 files under
the old script would draw every stroke at one pen width.
