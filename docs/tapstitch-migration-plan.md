# Tapstitch Migration Plan

**Written:** 27 Aug 2026. **Updated:** 14 Sep 2026.
**Status:** APPROVED AND UNDER WAY. Evan judged the samples and committed to Tapstitch blanks on 14 Sep 2026. The approach below (bake placement into the file) survived contact and is what got built.

## What changed on 14 Sep 2026 (Evan's decisions)

- **Three lines, all on Tapstitch:** one tee, one hoodie, one crewneck, carrying every temple design. The old blanks retire.
- **The logo moves off the back to the front print.** The back is temple plus location text only. A new layout profile, `back_temple_text`, does this; the front logo file is generated from Evan's existing logo asset onto a front-print-area-shaped canvas.
- **The store goes dark, and nothing is deleted.** Every temple listing drafts and stays drafted. The original plan deleted each old listing as its replacement published so the replacement would inherit its address; that was RETIRED on 16 Sep 2026 (Evan, asked and confirmed) because it does not work. Shopify builds a new product's address from its title and ignores whatever address a deletion just freed, so the deletion bought nothing and destroyed an old listing for nothing, one product at a time. Replacements take their own address and `scripts/easify_options.py sync` repoints the dropdown links.
- **Descriptions are written straight to Shopify**, not typed into the Tapstitch editor. The existing writer is proven on 158 products and no Tapstitch redesign can break it.

## What is built (14 Sep 2026)

| Piece | File | State |
|---|---|---|
| Flattener | `flatten.py` | Done. 120 of 135 temple/garment pairs build clean, zero validator findings. The 15 gaps are 5 temples with no traced art. |
| No-logo back layout | `layout.py:back_temple_text` | Done, plus a `vertical_anchor` option for the centring question. |
| Build sweep | `scripts/tapstitch_build.py` | Done. |
| Proof sheet | `scripts/tapstitch_preview.py` | Done. https://claude.ai/code/artifact/63f25017-3639-4bb9-96cc-d16cc1e21d57 |
| Migration ledger | `ledger.py`, `scripts/tapstitch_status.py` | Done. 121 rows seeded with the handle each replacement inherits. |
| Store pull-down | `scripts/store_pulldown.py` (removed 6 Oct 2026, in git history) | Done AND RUN, 14 Sep 2026. 160 listings drafted, six deleted. The store is dark. |
| Description plumbing | `generate.fixed_description` + `reference/garment-copy/` | Repointed per garment. Copy for the new blanks is not written. |
| Browser session | `browser_session.py`, `scripts/tapstitch_login.py` | Written, never exercised. |
| Editor automation | `config/tapstitch.json`, `scripts/tapstitch_publish.py` | Config scaffolded with 18 nulls; the Shopify half works, the editor half waits on a live session. |

Blanks as they stand at the end of 14 Sep 2026: tee RT0063, crew R00368, hoodie
R00286, all on USA fulfillment, front and back print. The tee prints DTG and the
two fleece blanks print DTF. Three earlier choices were replaced the same day: the
RU0010 tee (too light), and the UT0044 crew and RW0041 hoodie (international
fulfillment). Full specs and costs in `docs/decisions.md` and BRAND.md section 7.

Still blocked on Evan: the 18 editor selectors, which are only readable inside
the Tapstitch editor and so come with the first live session; whether the size
guide is a new video or the branded chart images; and whether Flower Gray on the
crew is dark enough to print white. The print areas came in on 14 Sep and are no
longer blocking. Everything else on this list has been decided: spacing, sizes,
lead colours, prices, and the pull-down are all settled and done.

---

## Original plan, 27 Aug 2026



## Context

Evan is considering moving Peculiar People printing from the old print-on-demand supplier to Tapstitch because Tapstitch has better heavyweight blanks. The question this doc answers: if we switch, can we automate product creation the way the old pipeline does, given that Tapstitch has no API?

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
- **Login:** the script reuses a browser profile Evan logged into once by hand, so it never touches his password. Same pattern as `browser_session.py` (real Chrome, dedicated profile, attach over CDP).
- **Ongoing cost:** browser automation breaks when Tapstitch redesigns the editor. Maintainable, not set-and-forget. This is the price of no API.

## First steps when samples arrive and Evan approves

1. **Manual check (5 minutes):** confirm the Tapstitch editor defaults an upload to centered at full size, or that the size field can hit that exactly. The whole flattened-file approach leans on this.
2. **Watch the editor's network traffic once** while saving a design by hand. Even without a public API, the editor talks to Tapstitch's servers to save designs, and that traffic usually carries exact positions and upload references. It may allow a sturdier or faster path than UI clicks, and it will tell us how the flattened file maps onto their design storage.
3. **Prototype one temple end to end** (flattened PNG through published product) before touching the rest of the catalog.

## Discussion notes (Q&A from the 27 Aug session)

- *Can Playwright vary run to run?* Yes. It is scripted code, not a recording. It can loop over all temples, read pixel data, branch, and compute coordinates fresh each run.
- *Can it place text a few pixels below the temple even though temples end at different heights?* Yes, but the measurement should happen locally on the PNG before upload, not by reading the editor screen. Better still, bake it into the file (the approach above) so the editor never positions anything.
- *Is there a better way than Playwright?* Not for creation, since there is no API. The flattened-file design minimizes how much Playwright has to do. The network-traffic investigation (step 2 above) is the one thing that could upgrade the approach.
