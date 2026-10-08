# Spec overlay v2: three friends, lines to text (5 Oct 2026)

Built from `HANDOFF.md`. Live on the unpublished theme "Claude Code V3 zoom
preview" only: https://peculiarpeopleco.com/?preview_theme_id=194273870196

## What Evan confirmed this round

- Photo K (Pexels 7972658): man on the left in the **hoodie**, woman in the middle
  in the **tee**, woman on the right in the **crewneck**. All black.
- Their open overshirts come off, so each person wears only our garment.
- Phones: two labels above the photo, two below, each joined to its garment by a
  line. No numbered dots, no list.

## The photo

| Step | What | File |
|---|---|---|
| 1 | Pexels original, 3000x2000 upload | `render/k-original-pexels-7972658.jpg` (preview size) |
| 2 | GPT Image 2.5 sunburst, high, 2k, 3:2: plain black hoodie, tee and crew, overshirts removed. Four variants (two prompts, two each); picked job cf947649 | `render/contact-round1.jpg` |
| 3 | Her hair fell over the crewneck's chest in every variant (it does in the original too), which hid most of the logo. Second render from job cf947649 with that side of her hair behind her shoulder; picked job 492fffb9. Hoodie and tee areas unchanged (mean difference 2 to 3 of 255) | `render/contact-hair.jpg`, `render/k-blanks-h0.jpg` |
| 4 | Real logo laid on with `place_spec.py` (uses `zoom-v2/place_logo.py`) | `web/pp-spec-group-k.jpg`, close-ups `qa/logos-closeup.jpg` |

Whole renders only; no original pixels spliced back. The model drew plain blanks
and never the logo.

Logo placement, measured on zoomed grids (`grid.py`), same rule as the dive (0.73
of the collar's outer width, top 0.59 logo widths below the collar band):

| Garment | Centre front (px in 2048x1360) | Collar | Angle |
|---|---|---|---|
| Tee | 1155, 682 | 125 | 0 |
| Crewneck | 1663, 651 | 133 | 0 |
| Hoodie | 551, 614 (bottom of the hood opening) | 150 (hood opening) | 3 |

The hoodie's drawcords and any hair are as dark as the cloth, so `place_logo`
cannot tell them apart from the shirt. `place_spec.py` puts them back in front of
the print from the unprinted frame: cords from traced lines, hair from its colour
(warm brown against a slightly blue black).

The logo file is now kept at `zoom-v2/pp-logo-white.png` (the theme's header logo,
"Peculiar People Logo - White.png", the same art as the chest print).
`printlay.py` pointed at a file from an old session upload that no longer exists.

Shopify Files: `pp-spec-group-k.jpg` (gid://shopify/MediaImage/56490412933492), alt
"Three friends talking by a stone wall in the black Peculiar People hoodie, tee
and crewneck".

## The copy

| Small caps | Line | Points at |
|---|---|---|
| Hoodie · 350 GSM | Heavy fleece, 10.3 oz. | his hoodie (21, 65) |
| Designed and printed in the USA | We print yours after you order. It arrives in 4 to 7 business days. | just right of the crewneck's print (87, 53) |
| Tee · 260 GSM | Heavyweight cotton that's soft from the first wear. | her tee (50, 69) |
| Crewneck · 350 GSM | Same fleece as the hoodie. | the crewneck (86, 69) |

The print-size and city lines are gone. Weights match `garments/*.json` (tee
RT0063 260 gsm; hoodie R00286 and crew R00368 350 gsm / 10.3 oz, the same fabric).
No sourcing claim. Humanizer pass: callout 4 said "printed" twice and callout 3
had a padded clause; both cut. Structural pass: nothing to restructure; the four
lines already differ in shape. Both scanners clean.

## The section

- `sections/pp-spec-overlay.liquid`: new block setting "On phones" (above or below
  the photo); numbers removed; the photo keeps its own shape (was forced square);
  presets updated to this copy.
- `assets/pp-quality.css`: phones get a two-column grid (labels above, photo full
  width bleeding to the screen edges, labels below); desktop keeps the columns
  either side, with a wider middle (up to 680 px) for a landscape photo.
- `assets/pp-quality.js`: lines now draw on phones too, straight up or down from
  each dot to its label, kept inside the label's width. Desktop unchanged.

All four files confirmed on V3 by checksumMd5 against the local files.

## QA

`qa/desk.jpg` (1440x900) and `qa/mob.jpg` (390x844) from `tools/spec1.js` on the
V3 preview: no page errors, no sideways scroll at either width (`spec1.js` now
reports sideways scroll).

## Still open

- Desktop: the tee's line runs from the left column across his hoodie to reach
  her. Any line from the left side has to cross him. If Evan dislikes it, move the
  tee label to the right column and the crewneck's to the left, or point the tee
  line at her sleeve.
- The section has no heading. One could be added in the theme editor, after the
  two editing passes.
