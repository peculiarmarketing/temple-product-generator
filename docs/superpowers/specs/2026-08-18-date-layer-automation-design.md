# Date Layer Automation (With Date products) - Design

Date: 18 Aug 2026
Status: Approved design, awaiting Evan's spec review
Owner: Evan

## Problem

Printify text layers are UI-only. Any API write to `print_areas` wipes them, and
they cannot be posted or updated (error 8253, confirmed in Phase 1 findings).
The UI duplicate carries the personalization config, but the generator's design
PUT rewrites `print_areas`, which destroys the date text layer. Every With Date
draft therefore comes out of the pipeline missing its text layer, and Evan must
open each one in the Printify editor, re-add the layer, re-enable
personalization, and publish by hand. That manual step is the last recurring
per-product chore in the pipeline.

## Options considered

1. **Order-level rendering.** Drop Printify personalization entirely. Customer
   enters the date in an Easify text field, a script renders the date into the
   print file per order and places the order via the Printify Orders API.
   Rejected for now: most moving parts, takes over order fulfillment for
   personalized items. Remains the long-term option if With Date should ever
   fold into base products.
2. **Live browser driving by Claude.** Rejected: token cost recurs per product
   and scales with the catalog.
3. **Replay the editor's internal save call.** Rejected: smallest script if the
   payload is clean, but unbounded reverse-engineering risk, session-cookie
   auth, and unofficial-endpoint gray area against Printify's terms.
4. **Playwright script (CHOSEN).** Deterministic UI automation of the exact
   manual flow. Bounded effort, official ground (does only what a human does in
   the editor), zero recurring token cost. The editor's numeric Position
   left/top, Width/Height, Scale, and Rotate fields remove the only fragile
   part (canvas dragging); the script fills labeled form fields.

## What we are building

`scripts/add_date_layer.py`: a standalone Playwright script that

- logs into Printify with a saved browser session,
- finds unpublished With Date drafts missing their date text layer,
- adds the text layer with Evan's standard settings,
- positions it via the editor's numeric position fields,
- enables personalization on the layer,
- saves, and never publishes.

Evan's remaining manual work per With Date product: review in Printify,
publish. The script runs only when Evan initiates it, like every other pipeline
step.

## Position computation

The date line sits a fixed distance below the divider. The divider is an image
layer, and image layers are readable via API GET. The script reads the
divider's position from the product itself, adds a fixed offset (measured once
from a hand-built reference product), and converts to the percent units the
editor's position fields use. No generator changes needed, and it works on any
With Date product, old or new.

Fallback if GET proves unreliable for this: `generate.py` emits the date-line
coordinates to a sidecar file at generation time. This is the only case in
which any existing script would change, and it would be an additive output
only.

## Settings capture

Font, size, colors, placeholder text, and personalization config are captured
once from an existing published With Date tee (the canonical hand-built
standard) during discovery and stored in a small config file the script reads.
Dark colorway groups get white text, light groups get black, keyed off which
art asset each print-area group carries.

## Phases and gates

Phase gates are real stops. Each gate is Evan's explicit confirmation.

### Phase 0: Discovery

One supervised browser session on the Brigham City Tee - With Date draft (the
one currently awaiting its layer). Claude drives the editor and performs the
manual flow Evan would have done anyway, recording UI steps and network
traffic. Nothing publishes. This phase answers:

- Is the text layer added once per product or once per colorway/size group?
- What are the Position field percent values relative to, and which corner of
  the layer do they anchor?
- Does API GET expose text layers (cheap verification path if yes)?
- Full settings inventory from the reference product (font, size, colors,
  placeholder, personalization config, character limit behavior given the
  known Printify bug where the character limit field does not render).

Gate: Evan confirms the captured settings are canonical.

### Phase 1: Login and session persistence

Playwright installed in the project venv (`.venv.nosync`). One headed login
where Evan types credentials himself; the session is saved to a gitignored
storage-state file treated with the same discipline as `.env`.

Gate: the script opens a product editor page logged in, on two different days,
proving the session persists.

### Phase 2: One product end to end

Implement the add-layer flow per discovery notes. Run on one draft. Verify
against the reference product: API diff if text layers are readable via GET,
screenshot comparison if not.

Gate: Evan compares the result to his hand-built standard in the editor and
publishes it himself.

### Phase 3: Batch and integration

Process all With Date drafts awaiting layers, idempotently (drafts that
already have a layer are skipped). Document the script as an optional step in
the end-of-run sequence. Update `docs/decisions.md`.

Gate: one full sweep where Evan's only With Date work is review and publish.

## Reversibility (hard requirement)

The pipeline works today and must not be put at risk.

- **Isolation by construction.** Zero edits to existing code. `generate.py`,
  `publish_drafts.py`, `art_images.py`, and `easify_options.py` are untouched.
  The single allowed exception is the position fallback above (an additive
  sidecar output from `generate.py`), used only if API GET proves unreliable,
  and gated by Evan like any other change. If the new script is never run, the
  pipeline behaves byte-for-byte as it does today. Playwright is additive in
  the venv; no existing script imports it.
- **Off switch is "don't run it."** The script runs only when Evan invokes it.
  The docs list it as an optional step, with the manual editor flow remaining
  the documented standing fallback. Turning it off needs no config change and
  no revert.
- **Hard scope limits.** The script refuses to touch anything except
  unpublished With Date drafts missing their date layer. Published products,
  base garments, and drafts that already have a layer are rejected by gate
  checks before any browser action. It adds layers; it never deletes or moves
  anything else.
- **Rollback is boring.** Worst realistic failure is a misplaced layer on a
  draft, fixed in the editor like a manual mistake, and unreachable by the
  store because of the publish gate. Full removal is a git revert plus
  deleting the gitignored session file. No other state exists.
- **The publish gate stays.** The existing decision that With Date products
  are never published via API is doing real safety work here and is not
  changed by this design. Any future relaxation is a separate decision for
  Evan after the automation has earned trust.

## Security constraints

- The Playwright storage-state file holds Evan's Printify auth cookie:
  gitignored, never committed, never printed, same discipline as the API
  token in `.env`.
- Credentials are typed by Evan in a headed browser during Phase 1 login.
  They never appear in code, config, or logs.

## Risks

- **Printify editor redesign breaks the script.** Failure mode is visible: the
  script errors and stops. The fix is a repair session against the new UI.
  The manual flow always remains available in the meantime.
- **Character limit field bug.** Printify's personalization panel has a known
  bug where the character limit field does not render. Discovery records the
  actual behavior; the script matches whatever the manual flow can achieve,
  not more.
- **Session expiry.** The saved session will eventually expire; the script
  detects a logged-out state and stops with a clear message telling Evan to
  re-run the headed login. It never attempts to enter credentials.

## Success criteria

- A sweep's With Date drafts get their date layers added by one script run,
  each layer matching the hand-built standard (same font, size, colors,
  placeholder, personalization config, and position relative to the divider).
- Evan's per-product With Date work is reduced to review and publish.
- The existing pipeline's behavior is unchanged when the script is not run.
