# Printify editor redesign breaks the date-layer automation (19 Aug 2026)

Found during the Manhattan / Mexico City / Oakland / Rome sweep. All four
"With Date" drafts failed with the same error:

    Locator.wait_for: Timeout 30000ms exceeded.
    waiting for get_by_role("heading", name="Variants and layers") to be visible

## Mechanism

Two separate things, one masking the other.

1. **The info modal opens over the editor.** Printify now shows the
   "Important product information" dialog on editor load. `open_product()`
   waited for the variants panel heading *before* calling
   `_close_info_modal_if_present()`, and while the modal is up the editor
   underneath it is not rendered, so the wait could never succeed. Fixed by
   dismissing the modal first, then waiting. Verified live: the dialog count
   goes 1 to 0 on the close click.

2. **The variants panel no longer exists.** With the modal dismissed, the
   string "Variants and layers" is absent from the page entirely, and
   `get_by_role("heading")` returns an empty list. The editor has been
   rebuilt around an icon rail on the left (Upload, AI, Personalize, Add
   text, My library, Graphics, My templates, Shutterstock, Fiverr), an
   Edit / Preview toggle at top right, Front side / Back side pills at the
   bottom centre, and Save product at bottom right. There is no right-hand
   panel and no visible per-colorway swatch list.

Fix 1 is committed. Fix 2 is not attempted here: the driver's whole flow
(enumerate colorway groups, select a light swatch to edit the default design,
walk each dark swatch, add the personalization layer per group) is built on a
panel that no longer exists, so it needs a fresh discovery pass in the new
editor rather than a selector swap.

## Current state

`config/date_layer.json` selectors from the 18 Aug session are stale except
`info_modal`, `info_modal_close_button`, `save_button`, and `login_form_marker`,
which still resolve. The geometry values (font, size, box, scale, colors) are
API-side facts and are unaffected.

Until the driver is rewritten, the manual editor flow is the only route for
date layers, and `scripts/publish_drafts.py` correctly holds unverified dated
drafts back.
