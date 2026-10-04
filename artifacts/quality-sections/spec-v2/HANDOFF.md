# Handoff: rebuild the homepage spec overlay

Start here in a fresh session. Branch: `claude/homepage-quality-sections` in
temple-product-generator. Read the workspace `CLAUDE.md` and `BRAND.md` first;
the house rules there apply (no em dashes anywhere Evan-facing, new copy gets
the humanizer pass then the structural-humanizer pass, never print the Printify
token).

## Where things stand

- All homepage work lives on the unpublished theme **"Claude Code V3 zoom
  preview"** (`gid://shopify/OnlineStoreTheme/194273870196`). Preview:
  https://peculiarpeopleco.com/?preview_theme_id=194273870196
- The live theme is **"Claude Code V2"** (`gid://shopify/OnlineStoreTheme/194242150772`).
  Never write to it. The Shopify connector blocks it anyway. Publishing is Evan's
  call, done by hand in Shopify admin.
- On 4 Oct 2026 every V3 file was compared to V2 by checksum: the only
  differences are the homepage work (`templates/index.json`,
  `sections/pp-zoom-dive.liquid`, `assets/pp-quality.js`, `assets/pp-quality.css`).
  Publishing V3 loses nothing from V2.
- The dive (story frames plus collar zoom) is finished and Evan is happy with
  it. Details in `../zoom-v2/README.md` (Rounds 5 and 6) and `../zoom-v2/NEXT.md`.
- The "What you get" section is hidden on V3 (`"disabled": true`, content kept).
  It held the only homepage mention of the free replacement promise (damaged,
  misprinted or wrong item replaced free within 30 days, nothing shipped back).
  Evan has not decided whether to put that line somewhere else.

## The task: spec overlay (section `pp_spec_overlay`, type `pp-spec-overlay`)

Current state: the Nauvoo hoodie studio mockup, back view, four callouts
(350 GSM fleece; temple up to 12 in; printed in the USA / 4 to 7 days; city
line). Screenshots: `current-desk.jpg`, `current-mob.jpg`. Files:
`theme/sections/pp-spec-overlay.liquid`, styles in `theme/assets/pp-quality.css`
(`.pp-spec*`), line drawing in `theme/assets/pp-quality.js`.

What Evan asked for (4 Oct 2026):

1. **Photo:** a real group photo of **three people**, one in the **tee**, one in
   the **hoodie**, one in the **crewneck sweatshirt**. Keep the real people and
   background; only the garments are re-rendered with GPT Image 2.5 (sunburst).
2. **Layout:** lines to text, like the original draft. Not dots with a list
   under the photo.
   - Desktop: photo in the middle, labels left and right, a thin line from each
     label to that person's garment, drawn in on scroll (already how desktop works).
   - Phone (proposed, not yet confirmed): drop the numbered dots and list; photo
     full width, two labels above and two below, each joined to its garment by
     a line. This needs new CSS and line-drawing code for the phone layout.
3. **Callouts:** remove the print-size lines (no "up to 12 in", no logo size,
   no city line). Keep the shipping info. Add lines about the cotton and fleece,
   and a line about being designed and printed in the US.

Draft callouts shown to Evan (not yet approved, still need both humanizer passes
before shipping):

| # | Small caps | Line |
|---|---|---|
| 1 | Tee · 260 GSM | Heavyweight cotton, soft from the first wear. |
| 2 | Hoodie · 350 GSM | Heavy fleece, 10.3 oz. |
| 3 | Crewneck · 350 GSM | The same fleece as the hoodie, so the pair feels the same. |
| 4 | Designed and printed in the USA | Printed when you order, and it arrives in 4 to 7 business days. |

Answers from Evan (4 Oct 2026):
- **Sourcing:** unknown. Omit any source location or "premium sourced" claim;
  the cotton and fleece lines lean on the weights only.
- **Designed and printed in the USA:** confirmed true. Callout 4 can say it.
- **Photo:** not picked yet. Evan did not like A, B or C (`group-options.jpg`).
  Round 2 is D to I (`group-options-2.jpg`, table below). If none of those
  work either, keep searching (method below).

## Photo options (Pexels, free for commercial use and editing)

| Option | Pexels ID | Who wears what (proposed) |
|---|---|---|
| A (recommended) | 6140643 | Three walking toward camera, laughing. Woman left: crewneck. Man middle (red tee): tee. Man right (jacket): hoodie. |
| B | 6140614 | Same three, same shoot, mid-stride; the woman is partly behind the left man. |
| C | 6147395 | Different trio with books. Left man: tee. Middle man: hoodie. Woman: crewneck. |

Round 2 (sent after Evan passed on A to C):

| Option | Pexels ID | Notes |
|---|---|---|
| D (recommended) | 4767025 | Three friends laughing, arms around each other, street. Closest to "the shirt starts a conversation". |
| E | 175697 | Three men sitting on a step, graffiti door. Urban, relaxed. |
| F | 9071725 | Three guys sitting, laughing, in tees. "GAME" sign behind them would need cropping. |
| G | 12565305 | Three young men, arms around shoulders, outdoors. |
| H | 6150581 | Three cheering, already in a hoodie and crewneck. Studio wall, very loud energy. |
| I | 4148947 | Selfie on a forest path. The rest of that shoot is workout clothes. |

How the search was done: Yandex image search
(`https://yandex.com/images/search?text=...`, desktop browser User-Agent) with
queries like `site:pexels.com three friends arms around each other`, pulling
`images.pexels.com/photos/<ID>` out of the HTML, then contact sheets of
`?auto=compress&w=260` thumbnails. Check neighbouring IDs (plus or minus 8) for
other frames from the same shoot.

Download full size: `https://images.pexels.com/photos/<ID>/pexels-photo-<ID>.jpeg`
(consecutive IDs are usually the same shoot). Pexels asks that photos not imply
the person endorses the product: keep copy about the garment, never words put in
a person's mouth.

## How the dive's garment swap was done (repeat this)

Lessons Evan gave the hard way; do not re-learn them:
- **Whole renders only.** Splicing original pixels around a new shirt looked
  fake and edited. Use the model's whole render.
- **Fit and length** must match the real Tapstitch blanks: tee RT0063 (boxy,
  hits below the belt line), crew R00368, hoodie R00286 (oversize). Too short and
  too wavy were both rejected. Fabric reads heavy: few wrinkles.
- **Garment colour:** black on all three (Black is the only colour all three
  lines share).
- **Never let the model draw the logo.** Render plain blanks, then place the real
  logo PNG with `../zoom-v2/place_logo.py` (`place(frame, front, collar_w,
  angle_deg, bend, out)`): width 0.73 of collar width, top 0.59 logo widths
  below the collar band along the shirt's own slanted centre line, rotated to
  each garment's angle, bent with the fabric shading, hands and straps kept in
  front. Same proportions on every person. Measure each collar on a zoomed grid.
  Evan checks logo centring, tilt and distance from the collar closely.
- Hoodie front: the logo goes on the chest below the hood opening; measure the
  hood/neck opening the same way as a collar.
- Model: Higgsfield `gpt_image_2_5`, variant `sunburst`, quality high,
  resolution 2k, aspect matched to the photo (3:2 gives 2048x1360). Upload the
  original with `media_upload`, PUT with curl (`Content-Type`, `If-None-Match: *`),
  `media_confirm`; batch with `generate_image_batch` then `jobs_wait`. Make two
  variants per prompt and pick. Reference images used before: RT0063 front
  `47fa6d75-b3e1-4f8b-94ba-1b67409c2e68`, side `5270898a-55a1-47f4-81fb-f55200a71a25`.
  Higgsfield media IDs may not survive; re-upload if needed.
- Ask the model to keep faces, skin, hair, hands, background and lighting
  exactly as they are, relit only where the new garment changes the light.

## Deploy mechanics (V3 only)

- Images: `stagedUploadsCreate` (resource FILE, POST) then
  `../tools/stagepost.py` (stdin: `path content-type x-goog-date key signature
  policy`, one line per file) then `fileCreate` with alt text.
- Theme files: `.js` and `.json` go through a staged upload and
  `themeFilesUpsert` with a URL body. **Liquid must be sent as an inline TEXT
  body**; a URL body with text/plain is silently dropped. Upload a section's
  liquid before any template that uses its new settings. Always confirm each
  file with `checksumMd5` against `md5sum` of the local file.
- `templates/index.json` has a header comment that must be preserved: strip it
  with a regex, edit the JSON, write back `header + json.dumps(indent=2,
  ensure_ascii=False)`.
- Live QA: `../tools/live7.js` (whole dive sweep) and `../tools/spec1.js`
  (screenshots just the spec overlay at 1440x900 and 390x844). Run with
  `NODE_EXTRA_CA_CERTS=/root/.ccr/ca-bundle.crt node spec1.js <outdir>`. Check
  for page errors and sideways scroll on both widths.
- Commit and push to `claude/homepage-quality-sections`; update a README for
  the round with what changed and why.

## Other loose ends (not this task)

- The why chain section (`pp_why_chain`) now repeats the dive's opening message
  ("so someone asks"). Recommended: hide it or give it a new job. Evan has not
  decided.
- Old dive images still in Shopify Files once V3 is approved:
  `pp-dive-wall-2-collar.jpg`, `pp-dive-wall-3-dtg-print.jpg`,
  `pp-dive-story-1..4`.
- Shipping policy edit is still manual for Evan.
- Fleece prints DTF, the tee prints DTG. Do not say "direct to garment" about
  the hoodie or crew.
