# Tapstitch Migration Plan (draft, pending sample verdict)

**Date:** 27 Aug 2026
**Status:** ON HOLD. Evan ordered Tapstitch samples and will judge the blanks first. Nothing gets built until he approves. If the samples disappoint, this doc is dead and Printify stays.

## Context

Evan is considering moving Peculiar People printing from Printify to Tapstitch because Tapstitch has better heavyweight blanks. The question this doc answers: if we switch, can we automate product creation the way the Printify pipeline does, given that Tapstitch has no API?

## What we verified (27 Aug 2026)

- **Tapstitch has no public API.** Their integrations (Shopify, Etsy, Wix) only sync orders and fulfillment. Product and design creation happens only in their web editor. Confirmed by web search; re-verify before building in case this changes.
- **The Tapstitch editor has no position field.** Each design element has size and scale fields only. Placement is drag-only in the UI.
- Groundwork already exists: Salt Lake black/white transparent PNGs (3612x4096) were exported for Tapstitch on 27 Aug 2026 (see decisions.md and the memory notes). Trap learned there: rasterized PNGs carry black RGB under fully transparent pixels, and Tapstitch's previewer smears it into gray halos around white-ink art. Fix is a matte pass that sets every pixel's hidden color to the ink color. Any white or light PNG export needs this.

## The agreed approach: bake placement into the file, not the editor

The core insight: we control art generation, so the design file itself can carry all the placement. The editor is reduced to a dumb drop zone.

1. **One canvas template per garment print area.** Pick a canvas that exactly matches the print area's proportions (for example 4500x5400 for a typical front print). Transparent background. A tee front and a hoodie front get separate templates because their print areas differ.
2. **Composite per temple.** Place the temple art at a fixed spot on the canvas (centered horizontally, fixed top edge). Measure the lowest non-transparent pixel of that specific temple's art, then draw the location text a fixed number of pixels below it. Tall skinny temple or short wide one, the text always hugs the building the same way. This is the same pixel-work family as the existing tracer health checks and the Tapstitch matte fix.
3. **Result: one flattened PNG per temple per print area** where everything is already in final position relative to the canvas edges.
4. **Editor job becomes identical every run:** upload one file, center it at full size, same size value every time. Because the file is the exact shape of the print area, "centered at full size" aligns the canvas edges with the print area edges, and everything inside lands exactly where we put it.

### Why not position two elements inside the editor?

Playwright can do it (it is a real program: it can measure images, compute coordinates, and drag per temple). But drag automation on a canvas editor is the flakiest kind of browser automation: snap guides grab elements, drags miss by a few pixels, and the only verification is screenshot comparison. Flattening moves the hard part (placement) onto the Mac where every file can be checked before it touches Tapstitch, and leaves the browser doing only boring, identical clicks. That is the version that stays reliable.

## Browser automation model

- **Playwright drives the editor** for the repetitive steps: log in (see below), new product, upload file, set size, save. Roughly a minute or two per product; fine for a one-time catalog migration plus occasional new temples.
- **Login:** the script reuses a browser profile Evan logged into once by hand, so it never touches his password. Same pattern as the Printify date-layer setup (real Chrome, dedicated profile, attach over CDP) in `docs/discovery/2026-08-date-layer-editor-notes.md`.
- **Ongoing cost:** browser automation breaks when Tapstitch redesigns the editor. Maintainable, not set-and-forget. This is the price of no API.

## First steps when samples arrive and Evan approves

1. **Manual check (5 minutes):** confirm the Tapstitch editor defaults an upload to centered at full size, or that the size field can hit that exactly. The whole flattened-file approach leans on this.
2. **Watch the editor's network traffic once** while saving a design by hand. Even without a public API, the editor talks to Tapstitch's servers to save designs, and that traffic usually carries exact positions and upload references. It may allow a sturdier or faster path than UI clicks, and it will tell us how the flattened file maps onto their design storage.
3. **Prototype one temple end to end** (flattened PNG through published product) before touching the rest of the catalog.

## Discussion notes (Q&A from the 27 Aug session)

- *Can Playwright vary run to run?* Yes. It is scripted code, not a recording. It can loop over all temples, read pixel data, branch, and compute coordinates fresh each run.
- *Can it place text a few pixels below the temple even though temples end at different heights?* Yes, but the measurement should happen locally on the PNG before upload, not by reading the editor screen. Better still, bake it into the file (the approach above) so the editor never positions anything.
- *Is there a better way than Playwright?* Not for creation, since there is no API. The flattened-file design minimizes how much Playwright has to do. The network-traffic investigation (step 2 above) is the one thing that could upgrade the approach.
