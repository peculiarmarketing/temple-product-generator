---
name: cc1566-temple-description-builder
description: Builds and publishes the complete Shopify product description for a Peculiar People CC1566 temple crewneck sweatshirt, combining the fixed sweatshirt intro, a source-verified temple facts section, and the fixed CC1566 size guide, written directly to the matching Shopify sweatshirt product rather than printed in chat. Use when the user names a Latter-day Saint temple and the garment is the crewneck, the sweatshirt, the fleece, or CC1566 or 1566, or says anything like "now do Logan on the crewneck", "build the sweatshirt page for San Antonio", or "next one" while the sweatshirt is in play. For the CC1717 tee use cc1717-temple-description-builder, and for the CC1567 hoodie use cc1567-temple-description-builder. Shipping tee measurements on a sweatshirt page, or publishing to the wrong product, is the failure this prevents. Always use this skill rather than answering from memory, because every fact has to clear a source hierarchy.
---

# CC1566 Temple Description Builder

Produces the complete Shopify product description for a Peculiar People temple crewneck sweatshirt: one HTML5 block the user pastes straight into the product description field.

This is the CC1566 sibling of `cc1717-temple-description-builder`. The temple research is identical between them. Only two things change: the intro section describes a sweatshirt instead of a tee, and the size guide carries CC1566 measurements and the CC1566 video.

Every output has exactly three sections in this order:

1. **The Sweatshirt** — fixed. Identical on every CC1566 product. Copied verbatim from `assets/product-intro.html`.
2. **Size Guide** — fixed. Identical on every CC1566 product. Copied verbatim from `assets/size-guide.html`.
3. **Temple facts** — the only part that varies. Researched and verified per temple.

## Garment check before anything else

Confirm the garment before starting. If the user named a temple without naming a garment, and nothing earlier in the conversation establishes the sweatshirt, ask which garment rather than guessing. A tee page carrying sweatshirt measurements is a return; a sweatshirt page carrying tee measurements is a return.

The tee runs S through 4XL. This sweatshirt runs **S through 3XL only**. If the user's variant list, Printify product, or size-split print areas include a 4XL for a CC1566, that is an error worth raising.

## The fixed sections

Read `assets/product-intro.html` and `assets/size-guide.html` and reproduce them exactly. Do not rewrite, reword, reformat, re-indent, or "improve" them.

If the user asks to change the sweatshirt copy, the size guide, or the video URLs, edit the asset file itself so the change propagates to every future product. Never make a one-off change in a single output.

### What the intro is, so it does not get rewritten by accident

The intro is **founder-voice narrative copy in Evan's own words, signed `- Evan`**. It is not product description and it is not a spec paragraph. It opens on why someone wears a temple design, moves through gospel conversations being hard to start, lands on "the new white shirt and tie," gives the reason the company exists, and only then closes with a single line about the fabric. The garment beat is last and it is one sentence.

This ordering is deliberate and has already been through several rounds. If a future pass makes the intro sound like it is selling a blank, it is wrong. Specifically, do not:

- open on weight, hand feel, or fabric construction
- explain what garment-dyeing is or how it works
- add sensory or benefit copy about the print quality
- move, restyle, or drop the `- Evan` signature
- change "the new white shirt and tie," which is the missionary reference and not a garment word

The `<strong>Weight:</strong>`, `<strong>Fabric:</strong>`, `<strong>Details:</strong>` and `<strong>Fit:</strong>` paragraphs below the narrative carry all the technical detail. That is why the prose does not need to.

### The one line that differs from the tee

The narrative is identical across all three garment assets except the garment noun and the closing fabric sentence. The tee says "premium heavyweight ringspun cotton." This sweatshirt says **"premium heavyweight fleece with a ringspun cotton face,"** because the CC1566 is an 80/20 cotton and polyester blend and the tee's wording would contradict the fabric spec three lines below it on the same page.

Do not sync this line back to the tee's wording. If the intro copy is ever revised, revise all three assets in the same pass and keep this sentence garment-accurate in each.

### The video URLs

`assets/size-guide.html` carries the two live Shopify CDN URLs for the CC1566 size guide video, WebM first and MP4 second. They are set and need no further action.

These are **not** the CC1717 URLs. The two garments have separate videos showing different measurements, and the hashes look alike at a glance. If the video ever needs replacing, edit the asset file so the change reaches every product; never paste a different URL into a single output. If a `PLACEHOLDER_` token ever reappears in the asset, produce the block anyway but open the response with a one-line warning that the video will not play, and do not substitute the tee URLs to fill the gap.

### Why the inline style on the `<video>` element stays

When a video carries `width` and `height` attributes, some Shopify themes scale the width down to the container while leaving the height at its literal pixel value, which letterboxes a square video inside a tall box with dead space above and below. The inline rule pins the aspect ratio so the element scales as a square. The CC1566 video is square (2880 x 2880 at source), so the same rule applies unchanged. Leave it in place, and do not add inline styles anywhere else.

## Where the CC1566 numbers come from

The measurements in `assets/size-guide.html` are the manufacturer body specs, confirmed against two independent sources: the S&S Activewear spec table for style 1566, and the size guide video itself. They agree exactly.

Garment specs, for reference when a customer question comes in:

- 9.5 oz/yd&sup2; (US), 80/20 ring-spun cotton/polyester, 30 singles
- Three-end heavyweight fleece, 100% ring-spun U.S. cotton face
- Garment-dyed and preshrunk during the dye and wash processes
- 1x1 rib collar, cuffs and waistband; rolled forward shoulder; side seams; back neck patch; twill-taped back neck
- Manufacturer tolerances: body length plus or minus 1 inch, chest plus or minus 3/4 inch, sleeve plus or minus 1 inch

The published table omits tolerances on purpose. A garment-dyed product page that lists tolerances invites measuring rather than buying. If a customer disputes a measurement, the tolerances above are the answer.

## The temple facts section

The research protocol, the source hierarchy, the myth screen, the conflict rules, and the ledger format are **identical to the tee skill and are not restated here**, so that a correction only has to be made once.

Before writing any temple content, read:

- `/mnt/skills/user/cc1717-temple-description-builder/SKILL.md`, sections **The source hierarchy** through **Batch consistency**, and follow them exactly
- `/mnt/skills/user/cc1717-temple-description-builder/references/known-myths.md` — folklore that must never ship, with corrections. Read this every time.
- `/mnt/skills/user/cc1717-temple-description-builder/references/special-cases.md` — temples that break the standard field set. Check before writing.

Those three files are the canonical copies. If they cannot be found, say so and stop rather than reconstructing the rules from memory; a half-remembered source hierarchy is how folklore ships.

The short version, which does not replace reading the files: Tier 1 is churchofjesuschrist.org and thechurchnews.com and is sufficient alone. Tier 2 is churchofjesuschristtemples.org and is sufficient alone for spec fields. Tier 3 needs three genuinely independent sources. Everything else is omitted. An omitted fact is invisible; a wrong fact is a review.

## Output format

One HTML5 fragment containing all three sections in order. It is not printed in chat; it is written to the product's Shopify description field. See **Publishing to Shopify** below for how the product is resolved and written.

A fragment, not a document. No `<!DOCTYPE>`, `<html>`, `<head>`, or `<body>`. No `<style>` blocks and no `<script>`. No inline `style` attributes anywhere except the `<video>` element in the size guide asset.

**Heading levels are fixed.** Section titles ("The Sweatshirt", the temple name, "Size Guide") are `<h3>`. Subsections ("Construction Story", "Symbolism & Design", "Changes Over Time", "Trivia", "Measurements") are `<h4>`. Never `<h1>` or `<h2>`.

**No em dashes.** Not the literal character, not `&mdash;`, not `&#8212;`, not in the markup and not in the ledger. Scan the output before returning it. En dashes in date ranges are fine. The fixed asset files are exempt from the scan and are reproduced as they are.

### Full assembly

```html
[verbatim contents of assets/product-intro.html]

[verbatim contents of assets/size-guide.html]

<section class="temple-facts">
<h3 class="temple-facts__name">[Official Temple Name]</h3>
<p class="temple-spec__row"><strong>Location</strong><br>[City, State/Country. One line on the site: acreage, placement, what it overlooks.]</p>
<p class="temple-spec__row"><strong>Temple Number</strong><br>[Nth dedicated temple. Note if the count is of operating temples specifically.]</p>
<p class="temple-spec__row"><strong>Announced</strong><br><time datetime="YYYY-MM-DD">[Date]</time>, by [whom]. [One line of context.]</p>
<p class="temple-spec__row"><strong>Groundbreaking</strong><br><time datetime="YYYY-MM-DD">[Date]</time>. [Who broke ground; note separately who dedicated the site if different.]</p>
<p class="temple-spec__row"><strong>Dedicated</strong><br><time datetime="YYYY-MM-DD">[Date(s)]</time>, by [whom], in [N] sessions. [Notable circumstances.]</p>
<p class="temple-spec__row"><strong>Rededicated</strong><br><time datetime="YYYY-MM-DD">[Date(s)]</time>, by [whom]. [Delete this paragraph entirely if never rededicated.]</p>
<p class="temple-spec__row"><strong>Architecture</strong><br>[Architect or firm. Design style. Exterior material, precise about stone type. Floor area, height, tower or spire count.]</p>
<p class="temple-spec__row"><strong>Ordinance Rooms</strong><br>[Instruction rooms, sealing rooms, baptistries.]</p>
<p class="temple-spec__row"><strong>First Temple President</strong><br>[Name, years served.]</p>
<h4>Construction Story</h4>
<ul class="temple-facts__list">
<li>[2 to 5 items. The difficulties, delays, logistics, money, labor.]</li>
</ul>
<h4>Symbolism &amp; Design</h4>
<ul class="temple-facts__list">
<li>[2 to 5 items. Stonework, art glass, local motifs, inscriptions, what the design refers to.]</li>
</ul>
<h4>Changes Over Time</h4>
<ul class="temple-facts__list">
<li>[Renovations with dates, additions, what was altered. Delete this heading and list for a temple with no renovation history.]</li>
</ul>
<h4>Trivia</h4>
<ul class="temple-facts__list">
<li>[2 to 4 items. Firsts, superlatives, surprising details, memorable moments.]</li>
</ul>
<p class="temple-facts__asof"><em>Temple facts verified as of <time datetime="YYYY-MM-DD">Month D, YYYY</time>.</em></p>
</section>
```

Omit any spec row where nothing cleared the source hierarchy. Delete the whole paragraph rather than writing "unknown". There is no "Look Closer" line. Tier markers go in the ledger only, never in the markup.

### The ledger

After publishing, output the ledger as plain text, in the same format the tee skill uses. It is the only view the user gets of the research, since the markup now goes straight to Shopify:

```
SOURCE LEDGER - [Temple Name] (CC1566)

VERIFIED
[T1] claim - url
[T2] claim - url
[T3] claim - url, url, url

CONFLICTS RESOLVED
claim - what disagreed, which won, why

VOLATILE (re-check before reprint)
claim - why it may change

OMITTED
claim - reason it failed
```

## Reusing research across garments

If the same temple already has a published CC1717 page, the temple facts section is reusable verbatim. Ask for it, or pull it, rather than re-researching. Re-researching risks producing two subtly different accounts of the same building in the same catalog, which is worse than either account alone.

When reusing, still check the Volatile lines in that temple's original ledger. Renovation status, open-house dates, and "Nth temple" counts expire.

### The as-of line

The temple section ends with a dated line, immediately before the closing `</section>`:

```html
<p class="temple-facts__asof"><em>Temple facts verified as of <time datetime="2026-08-13">August 13, 2026</time>.</em></p>
```

It exists because a large share of this catalog is time-sensitive: temples under construction, scheduled dedications, "the Nth temple" counts, nearest-temple claims, open house dates. A reader who lands in December on a page describing an October dedication in the future tense should be able to see that the page was written in August, rather than concluding the brand does not check its facts. The line converts a stale page from an error into a dated record.

The date is **when the research was done**, not when the product was created or last edited in Shopify.

Spell the date out in the same style as the rest of the section so the block reads consistently, and keep the `datetime` attribute in ISO form. Re-date it whenever the facts are actually re-verified, and only then. Bumping the date without rechecking that temple's Volatile lines is worse than leaving it stale, because it turns an honest timestamp into a false claim.

## Publishing to Shopify

The assembled HTML is **not printed in chat**. It is written straight into the product's description field over the Shopify connector. Chat gets the ledger and a one-line confirmation of what was written where.

This skill publishes to the **Sweatshirt** product: `{Temple} Temple Sweatshirt`.

### Resolving the product

Product titles follow `{Temple} Temple {Garment}`, for example `Cody Temple Tee`. Two things make a naive lookup unsafe, and both already exist in the live catalog:

- **The product title is not the official temple name.** The facts section is headed `Cody Wyoming Temple`; the product is `Cody Temple Tee`. Search on the place token the user gave you, not on the official name research turned up.
- **The place token is not consistent across garments.** The tee is `Salt Lake City Temple Tee`, while the fleece is `Salt Lake Temple Sweatshirt` and `Salt Lake Temple Hoodie`. Resolve each garment independently and never derive one garment's title from another's.

Resolve like this:

1. Call `search_products` with `product_type:"Sweatshirt"` plus the place token. `product_type` is the reliable garment discriminator; the title suffix is a convention that can drift, and `product_type` is what actually distinguishes CC1717 from CC1566 from CC1567 in this store.
2. Read every title returned. Take the one that reads exactly `{place} Temple Sweatshirt`.
3. Hold the GID. Write with the GID, never with a title or handle.

Match on **title**, never on handle. Handles carry typos: the Washington D.C. hoodie lives at `washinton-d-c-temple-hoodie`.

### Stop conditions

Hard-stop and ask rather than guess when any of these is true:

- **Zero matches.** The product may not exist yet, or may be titled in a way the search missed. Do not create it. Say what was searched for and stop.
- **More than one plausible match.** This is not hypothetical. `Nauvoo Temple Tee` and `Nauvoo Temple Tee - Limited Edition` are separate live products. `Provo Temple Tee` and `Provo City Center Temple Tee` are different buildings whose titles are substrings of one another. Publishing the wrong one puts an entire page of the wrong temple's history on a live listing. List the candidates and ask which.
- **The garment was never established.** Publishing is destructive in a way that printing was not. Do not infer the garment from surrounding context when the user did not name it.

### Writing

Call `update-product` with the product GID and the complete assembled fragment as `descriptionHtml`. Send all three sections in a single call. The field is replaced wholesale, so writing only the temple section destroys the intro and the size guide.

Before writing, read the current description with `get-product`. If it is non-empty, report that in the confirmation line. The user should know whether this was a fill or an overwrite. Several pages in the catalog still carry an older intro that predates the current asset files; replacing it is correct, but it should not happen silently.

### What goes in chat

- One line per product: garment, exact product title, and whether the previous description was empty or was replaced.
- The ledger.
- Nothing else. No HTML, no code block, no preview of what was just published. If the user asks to see the markup, show it then.

### When the connector is unavailable

If the Shopify tools are not loaded, or the write fails, do not quietly fall back to printing the block as though the job were done. Say plainly that nothing was published, print the fragment in a code block so the work is not lost, and say that it still needs pasting by hand.

## Frontmatter constraints

The uploader validates the YAML frontmatter and rejects the skill if it fails. Two rules have already bitten this file, so check both before editing the `description`:

- **1024 characters maximum.** Longer is rejected outright with a validation error. Count it, do not estimate.
- **No `: ` (colon followed by a space) anywhere in the value.** The description is an unquoted YAML scalar, so a colon-space is read as a key separator and the whole block fails to parse. Use a comma or start a new sentence instead. Inner double quotes around trigger phrases are fine, and are why the value should not simply be wrapped in quotes to dodge the colon rule.

Also avoid a leading `'`, `"`, `[`, `{`, `-`, `#`, `|`, or `>` on the value, and keep it on one line.

## Reference files

- `assets/product-intro.html` — the fixed Sweatshirt section. Copy verbatim.
- `assets/size-guide.html` — the fixed CC1566 Size Guide. Copy verbatim. Video URLs are live.
- Research canon lives in the CC1717 skill. See **The temple facts section** above for paths.
- Shopify connector — `search_products`, `get-product`, `update-product`, scoped to `product_type:"Sweatshirt"`. See **Publishing to Shopify**.
