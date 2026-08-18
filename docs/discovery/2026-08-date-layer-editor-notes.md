# Date Layer Editor Discovery Notes (18 Aug 2026)

Session: Evan performed his normal manual date-layer flow on the Brigham City
Tee - With Date draft while Claude observed via the CDP debug port and the
API. This document is the authority for the editor driver's click path; a
Printify editor redesign means a repair session against this document.

## Session model (how automation reaches the editor)

Playwright-launched browsers fail Printify's Cloudflare Turnstile login
challenge regardless of human input (automation fingerprint). The session
therefore lives in a real Google Chrome with a dedicated profile
(`.playwright.nosync/chrome-profile/`, gitignored) started with
`--remote-debugging-port=9222`. Evan logs in there once by hand; scripts
attach with `connect_over_cdp`. Managed by `scripts/printify_login.py`.
Caution for long-running connections: cross-origin navigations swap CDP
targets and stale a long-lived connection's page list; poll the
`http://localhost:9222/json` target list and attach short-lived.

## Editor facts

- Editor URL: `https://printify.com/app/editor/{product_id}` (no blueprint or
  provider in the URL).
- Print area banner confirms 4494 x 5097 px.
- Top-level buttons observed in the DOM: "Add text", "Personalize",
  "My library", "My templates", "Front side", "Back side", "Save product",
  undo/redo, zoom controls.
- An "Important product information" modal may cover the editor on open
  (close button, plus a "Hide this info in the future" checkbox).
- The "Variants and layers" panel shows color swatches of all selected
  colorways at the top. Clicking a swatch switches to that variant's design.
  Swatches with a blue dot carry a variant-specific design. The panel shows
  "Currently editing variant specific design" and a
  "Revert <Color> to default design" control when on one.
- The editor opens on Evan's default variant, graphite, which is a
  variant-specific design. To edit the default design, switch to a light
  swatch first.

## Evan's manual flow (recorded verbatim, 18 Aug 2026)

1. Click Add Personalization Text Layer (in the Personalize panel). The
   layer appears, named "Text", already wired for personalization.
2. Select the font: Alata.
3. On dark colorways (Graphite, Brick, Moss, True Navy) set the font color
   to white. (Correction during the session: Moss is white-text, Ice Blue is
   black-text.)
4. Open the text layer's settings panel.
5. Set Width to 7 in and Height to 0.91 in (these are exactly
   `date_zone_width_in` and `date_zone_height_in` from
   `spacing_defaults.json`; this is why every hand-made layer has the
   bit-identical API scale 0.4673 = 7.0 / 14.98).
6. Type the placeholder text, all caps: SEPTEMBER 25, 2024.
7. Center horizontally (mouse snap or the horizontal-center button).
8. Use the snap guide to align the top line of the text box with the divider
   layer, then
9. press the down arrow once; that one step gives the standard gap between
   divider and date text.

Where the controls live: clicking "Add personalizable text" creates the
layer; font and color are NOT in that panel. Selecting the layer opens a
floating top toolbar containing: a "Position" button (opens the
width/height/rotate/position panel used in steps 4-5 and the calibration),
the font family dropdown (set to Alata), a font size dropdown reading
"Auto" (size is never set by hand; the typed box dimensions drive the
rendered scale), bold/italic, text alignment, the font color control
(opens a picker with a hex input field where the driver types 000000 or
ffffff), duplicate, and delete.

Step 8-9 mechanics, measured live (Brigham City, second session pass): the
snap aligns the box top with the divider's TOP edge (Position top 78.93%).
One down-arrow press moves a layer exactly 1.00% of the print-area height
(0.17 in), landing at 79.93%, which leaves a 0.13 in gap below the
divider's bottom edge: exactly gap_divider_to_date_in from
spacing_defaults.json, and digit-identical to the formula's output. The
panel is titled "Buyer personalization"; the button is "Add personalizable
text". The text field shows a character counter (18/1024) on this layer.

Group flow: do a light colorway first with black font; that sets the default
design, which propagates to all non-specific variants. Then click each dark
swatch (variant-specific design) and repeat with white font. Five layer
instances total on the tee (1 default group + 4 dark groups).

Personalization prompt ("Please add a date (accepted format: Month DD,
YYYY)") is remembered by Printify; Evan does not retype it. But the
personalization layer itself must be re-created per draft: the
`sales_channel_properties.personalisation` block rides the UI duplicate,
while the editor still requires the layer to be added from scratch.

## Position field calibration (proven digit for digit)

With the Brigham City date layer selected, the panel read: Width 7 in,
Height 0.91 in, Rotate 0 deg, Position left 26.64 %, Position top 80.05 %.
Computing from the saved API values of the displayed group (group 4,
y = 0.827246 normalized center):

- left% = (x_norm * W_in - width_in / 2) / W_in * 100 = 26.64
- top%  = (y_norm * H_in - height_in / 2) / H_in * 100 = 80.05

Both match the panel exactly. Editor Position fields anchor the box's
TOP-LEFT corner as a percentage of the print area; box dimensions are the
typed inches. The driver types Position top (and uses horizontal centering
or Position left 26.64) instead of Evan's snap-and-nudge.

## Formula validation against real products

date_center_y_in = divider_y_norm * H_in + divider_height_in / 2
                   + gap_divider_to_date_in + date_zone_height_in / 2
(constants from spacing_defaults.json "dated"; H_in = 16.99)

- Taylorsville (hand-built reference, divider named '1.png'/'2.png'):
  predicted vs actual delta 0.0002 normalized.
- San Antonio (generator-made): deltas 0.0000 to 0.0023 across 5 groups.
- Brigham City (added live this session): deltas 0.0000 on groups 0 to 3,
  0.0012 on group 4. Hand wobble sits within the 0.005 verify tolerance.

## Canonical layer values (verify() targets)

From all three products, per group: name "Text", type text/svg, font Alata,
font_size 200, font_weight 400, text_align center, x 0.5, scale 0.4673,
input_text "SEPTEMBER 25, 2024", color #000000 on the default/light group
and #ffffff on dark groups. Dark groups are detected by the group's art
asset (white temple SVG), never by colorway names.

## Product structure notes

- Generator-made products name the divider 'divider black 2in.png' /
  'divider white 2in.png'; image layers in GET carry a `name` field, so
  divider matching by name works (the uploads-library fallback is not
  needed).
- Taylorsville (pre-generator hand-build) differs: divider is '1.png' /
  '2.png' and the location line is a native text layer. Only generator-made
  drafts are in the script's scope, so this is context, not a problem.
- The tee has 5 print-area groups: group 0 with 395 variants (default
  design), groups 1 to 4 with 7 variants each (Graphite, Brick, Moss,
  True Navy variant-specific designs). Drafts arrive with these groups
  already split (the duplicate carries them).
- Text layers ARE readable via GET with full styling fields; they remain
  unwritable via POST/PUT (settled Phase 1 finding, unchanged).

## Reference snapshots (committed)

- `artifacts/date-layer/reference-product.json`: Taylorsville, Evan's
  canonical hand-build.
- `artifacts/date-layer/brigham-city-after-manual.json`: Brigham City
  immediately after the session's manual flow; the exact target state the
  driver must reproduce on future drafts.
