# Editor panel is collapsed, not gone (19 Aug 2026)

Found during the Manhattan / Mexico City / Oakland / Rome sweep. All four
"With Date" drafts failed with the same error:

    Locator.wait_for: Timeout 30000ms exceeded.
    waiting for get_by_role("heading", name="Variants and layers") to be visible

## Mechanism

Three things stacked on top of each other, and each one hid the next.

1. **First-login onboarding.** This was the dedicated Chrome profile's first
   visit to the editor, so Printify ran its walkthrough prompts. The right
   answer is "Explore on my own" (Evan). Once dismissed it does not come
   back, which is why the driver treats it as optional.

2. **The info modal opens over the editor.** Printify shows the "Important
   product information" dialog on editor load. `open_product()` waited for
   the variants panel heading *before* calling
   `_close_info_modal_if_present()`, and while the modal is up nothing
   underneath it can be reached. Fixed by dismissing first, then waiting.

3. **The variants panel is collapsed by default.** This is the part that
   produced a wrong diagnosis on the first pass. With the modal dismissed,
   "Variants and layers" is absent from the DOM and `get_by_role("heading")`
   returns an empty list, which looks exactly like a removed panel. It is
   not removed; it is behind the pencil-and-ruler toggle at the top right,
   and its contents are only mounted once it is open.

## The toggle

The toggle is icon-only with no `aria-label` and no `title`, so
`get_by_role("button", name=...)` finds nothing. It is matchable on its
Material Symbols ligature text:

    button.icon-only-button:has-text("design_services")

Clicking that locator did not open the panel in testing; it surfaced the
button's own tooltip, which is where the keyboard shortcut came from:

    Shift+Meta+L        (shown in the tooltip as "Edit tools ⇧⌘L")

The shortcut opens the panel reliably. The driver presses it first and falls
back to clicking the toggle, then waits for the heading as before.

## Result

`open_product()` now runs: dismiss onboarding, close info modal, open the
edit tools panel, wait for the panel heading, switch to the back side. All
four dated drafts were added and verified on the first run after the fix.

The rest of `config/date_layer.json` was never stale. The geometry values
(font, size, box, scale, colors) are API-side facts and were unaffected
throughout.
