---
name: cc1717-temple-description-builder
description: Builds and publishes the complete Shopify product description for a Peculiar People CC1717 temple tee, combining the fixed intro, a source-verified temple facts section, and the fixed size guide, written directly to the matching Shopify tee product rather than printed in chat. Use whenever the user names a Latter-day Saint temple and wants a product description, product page, listing copy, or facts block, or says anything like "now do the Logan temple", "build the page for San Antonio", "next one", or just names a temple while the tee is in play. For the CC1566 crewneck use cc1566-temple-description-builder, and for the CC1567 hoodie use cc1567-temple-description-builder. Also use it when reviewing existing temple copy, which may contain folklore. Always use this skill rather than answering from memory, because every fact has to clear a source hierarchy and a wrong product match publishes the wrong temple history to a live listing.
---

# CC1717 Temple Description Builder

Produces the complete Shopify product description for a Peculiar People temple tee: one HTML5 block the user pastes straight into the product description field.

Every output has exactly three sections in this order:

1. **The Tee** — fixed. Identical on every product. Copied verbatim from `assets/product-intro.html`.
2. **Size Guide** — fixed. Identical on every product. Copied verbatim from `assets/size-guide.html`.
3. **Temple facts** — the only part that varies. Researched and verified per temple.

Sections 1 and 2 are not written, they are copied. Section 3 is the work.

The purpose of section 3 is not to write interesting copy. It is to make sure that **nothing untrue ships**. Latter-day Saint temple history is unusually saturated with folklore that circulates as fact, repeated on tour company sites, state agency pages, church-adjacent blogs, and in casual conversation among members. Much of it is charming. Some of it is decades old. Almost none of it is sourced. The audience for this brand will recognize a repeated myth instantly, and one such error costs more credibility than ten good facts earn.

So the governing instinct is: **when a fact cannot be tiered, it does not ship.** An omitted fact is invisible. A wrong fact is a review.

## The fixed sections

Read `assets/product-intro.html` and `assets/size-guide.html` and reproduce them exactly. Do not rewrite, reword, reformat, re-indent, or "improve" them. Do not fix the odd `</source>` placement in the size guide — that is what Shopify's editor produces after a paste round-trip, and matching it keeps every product page in the catalog byte-identical.

If the user asks to change the tee copy, the size guide, or the video URLs, edit the asset file itself so the change propagates to every future product. Never make a one-off change in a single output.

### What the intro is, so it does not get rewritten by accident

The intro is **founder-voice narrative copy in Evan's own words, signed `- Evan`**. It is not product description and it is not a spec paragraph. It opens on why someone wears a temple design, moves through gospel conversations being hard to start, lands on "the new white shirt and tie," gives the reason the company exists, and only then closes with a single line about the fabric. The garment beat is last and it is one sentence.

This ordering is deliberate and has already been through several rounds. If a future pass makes the intro sound like it is selling a blank, it is wrong. Specifically, do not:

- open on weight, hand feel, or fabric construction
- explain what garment-dyeing is or how it works
- add sensory or benefit copy about the print quality
- move, restyle, or drop the `- Evan` signature
- change "the new white shirt and tie," which is the missionary reference and not a garment word

The `<strong>Weight:</strong>` and `<strong>Fit:</strong>` paragraphs below the narrative carry all the technical detail. That is why the prose does not need to.

### The one line that differs between garments

The closing fabric sentence is garment-accurate, not shared. The tee says "premium heavyweight ringspun cotton." The CC1566 and CC1567 say "premium heavyweight fleece with a ringspun cotton face," because those two are an 80/20 cotton and polyester blend and the tee's wording would contradict the fabric spec three lines below it on the same page.

Everything else in the narrative is identical across the three assets except the garment noun. If the copy is ever revised, revise all three assets in the same pass, keep the fabric line garment-accurate, and do not "sync" the fleece wording back to the tee's.

## The source hierarchy

Every published claim in the temple section must clear one of these three tiers. Record which tier it cleared.

**Tier 1 — Official.** Anything on `churchofjesuschrist.org`, including `newsroom.churchofjesuschrist.org` and the temple pages. A single Tier 1 source is sufficient on its own. This is the source of truth: where Tier 1 conflicts with anything else, Tier 1 wins, and the conflict is worth noting in the ledger.

`thechurchnews.com` (Church News, including the Almanac temple pages) is Church-affiliated and counts as Tier 1 for factual reporting. Treat `deseret.com` as strong but not official — it is Church-owned but editorially independent, so it lands in Tier 3 as a corroborating source rather than a source of truth.

**Tier 2 — ChurchofJesusChristTemples.org.** Unofficial but meticulous and widely regarded as the definitive temple reference. A single Tier 2 source is sufficient on its own for the standard spec fields (dates, dimensions, architect, materials, room counts, temple number). For narrative and trivia claims, prefer Tier 1 or add corroboration.

**Tier 3 — Corroboration.** Anything not found on Tier 1 or Tier 2 needs **at least three independent sources** before it can ship.

The word doing the work there is *independent*. Three sites that all reproduce the same Wikipedia paragraph are one source wearing three hats. Before counting a source, ask whether it plausibly did its own research or has a primary citation. Signs of genuine independence: it cites a journal, letter, or archival record; it is a university or historical-society publication; it contains details the other sources lack. Signs of dependence: identical phrasing to another source, no citations, aggregator or travel-listing format, AI-generated feel.

Never count these toward the three: Wikipedia, travel and tour-booking sites, Pinterest, content farms, AI-summary pages, or any site whose text closely matches another source.

**Tier 4 — Omit.** Everything else. Includes anything sourced only to folklore, only to a plaque, only to a blog, or only to "everyone knows."

## Workflow

**1. Establish the spine from Tier 1 and Tier 2 first.** Before searching broadly, fetch the temple's page on `churchofjesuschristtemples.org` and its official page under `churchofjesuschrist.org`, plus the Church News Almanac entry if one exists. These supply most spec fields in one pass and give the correct official temple name and dedication chronology. Use `web_fetch` on the actual pages rather than working from search snippets — snippets truncate and sometimes stitch together text from unrelated sections.

**2. Read `references/special-cases.md`.** Some temples break the standard field set and will produce false implications if run through it unchanged. Check before writing anything.

**3. Research the narrative material.** Construction difficulties, symbolism, local design motifs, human stories, superlatives. This is where the value is and also where the folklore lives. Search deliberately for the primary source behind any striking claim: a journal entry, a letter, a conference address, a dedicatory prayer. A story with a citation is worth three without one.

**4. Screen against `references/known-myths.md`.** Read that file and check every candidate fact against it. If a claim appears there, it does not ship regardless of how many sites repeat it — several of the listed myths appear on government and university pages. Where the file gives a corrected version, use the correction.

**5. Tier every claim and drop the failures.** Do not soften an unverifiable claim into a hedge ("some say", "it is believed that") to keep it. Hedged folklore is still folklore on a product page. Drop it.

**6. Flag volatile fields.** Some facts expire: renovation status, open-house and rededication dates, "the Nth temple" counts, and any superlative. A temple that was the largest in 1974 may not be now. Mark these in the ledger under Volatile so the user knows what to re-check before a reprint.

**7. Assemble the fragment.** Intro, size guide, temple section, with the as-of line dated to today.

**8. Resolve the product and publish.** See **Publishing to Shopify**. Then report the write and print the ledger.

## Output format

One HTML5 fragment containing all three sections in order. It is not printed in chat; it is written to the product's Shopify description field. See **Publishing to Shopify** below for how the product is resolved and written.

A fragment, not a document. No `<!DOCTYPE>`, `<html>`, `<head>`, or `<body>`. No `<style>` blocks and no `<script>`.

No inline `style` attributes in the temple section. The one exception lives in `assets/size-guide.html`, on the `<video>` element, and it is there to fix a specific theme bug rather than to style anything: when a video carries `width` and `height` attributes, some Shopify themes scale the width down to the container while leaving the height at its literal pixel value, which letterboxes a square video inside a tall box with dead space above and below. The inline rule pins the aspect ratio so the element scales as a square. Leave it in place, and do not add inline styles anywhere else.

**The markup has to look right with zero custom CSS.** This is the constraint that shapes the temple section. Shopify themes style a small, predictable set of tags well — paragraphs, headings, lists, `<strong>`, `<em>` — and frequently style nothing else at all. A definition list is semantically the correct element for a spec panel and is the wrong choice here: many themes ship no `dl`/`dt`/`dd` rules, so the term and its value run together into an unreadable line. Shopify's editor also sanitizes pasted markup and may discard wrapper elements it doesn't expect. So the spec panel uses paragraphs with a bolded label and a line break.

**Heading levels are fixed.** Section titles ("The Tee", the temple name, "Size Guide") are `<h3>`. Subsections inside them ("Construction Story", "Symbolism & Design", "Changes Over Time", "Trivia", "Measurements") are `<h4>`. Never use `<h1>` or `<h2>`: the product title is the page's `<h1>`, and the theme sizes `<h2>` too large for a description block. Keep every heading in the output at the same level as its counterpart in the other sections, so all three read as siblings.

Escape entities properly: `&amp;` for an ampersand, `&ndash;` or the literal character for date ranges. Never `&mdash;`, per the em dash rule below.

Omit any spec row where nothing cleared the source hierarchy. Delete the whole paragraph rather than writing "unknown" or leaving a label with no value.

There is no "Look Closer" line. Do not add one.

Tier markers in square brackets go in the **ledger only**, never in the markup.

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

The `<time>` elements are worth the small extra effort: they let search engines read the dedication and announcement dates as dates, which is what people are searching for when they type "when was the X temple dedicated." They are inert, so they cost nothing if the theme ignores them.

Class names are optional styling hooks. Nothing in the layout depends on them, so the block reads correctly whether or not any CSS is ever written.

### The ledger

After publishing, output the ledger as plain text. It is internal, never goes on the site, and exists so the user can spot-check the work and make the next reprint cheap. Now that the markup is written straight to Shopify, the ledger is the only thing the user sees of the research, so it carries more weight than it used to:

```
SOURCE LEDGER - [Temple Name]

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

## Writing the temple section

Facts clear the hierarchy; prose still has to be good. A few things that make the difference on a product page:

**Precision reads as authority.** "Quartz monzonite from Little Cottonwood Canyon" is better than "granite" and happens to also be correct. Name the architect. Give the actual dimension. The people buying an architectural drawing of a building are the people who want to know what the building is made of.

**One human moment beats five statistics.** The Construction Story should contain at least one thing a person would repeat out loud. Look for the detail with a name attached, a number that conveys scale, or a decision that cost someone something.

**Let the facts carry the reverence.** Do not add devotional language, testimony, or interpretation of the building's spiritual significance. The brand's voice is a knowledgeable admirer, not an institution. Nothing should read as though the Church produced or endorsed the page.

**Quote sparingly and attribute exactly.** A short quotation with a date and speaker is powerful. An unattributed quotation is a liability — a great deal of pseudo-scripture circulates under Brigham Young's and Joseph Smith's names. If the primary citation cannot be found, cut the quote and keep the idea in your own words.

**No em dashes.** Not in the markup, not in the ledger, not anywhere in the output. This covers the literal character, the `&mdash;` entity, and `&#8212;` equally. Em dashes render inconsistently across Shopify themes, break awkwardly on narrow mobile columns, and read as machine-written to a lot of people. Use a period, a comma, a colon, or a semicolon instead, and rewrite the sentence if none of those fit — a sentence that needs an em dash is usually two sentences.

This is easy to violate by accident, because an em dash is the natural reach when setting off an appositive or a dependent clause. Before returning any output, scan for the character and the entity and replace every instance. En dashes in date ranges are fine, literal (May 17–19, 1884) or as `&ndash;`, and so are hyphens. The fixed asset files are exempt from this scan: reproduce them verbatim regardless of what they contain.

## Handling conflicts

Sources will disagree, most often about construction duration, which depends on whether you count from site designation, groundbreaking, or cornerstone. When they do:

- Tier 1 wins outright.
- Between two Tier 2/Tier 3 sources, prefer the one with a primary citation.
- If both figures are defensible, publish both and label them — "40 years from groundbreaking; 46 from site dedication" — rather than picking one silently. Unlabeled conflicting numbers in the same block read as an error even when both are right.
- Note the conflict in the ledger regardless.

## Batch consistency

When running several temples, keep field order, date format, and level of detail identical across all of them. A series where one entry has ten bullets and the next has three looks unfinished. Match the depth of the thinnest well-sourced entry rather than padding the others.

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

This skill publishes to the **T-Shirt** product: `{Temple} Temple Tee`.

### Resolving the product

Product titles follow `{Temple} Temple {Garment}`, for example `Cody Temple Tee`. Two things make a naive lookup unsafe, and both already exist in the live catalog:

- **The product title is not the official temple name.** The facts section is headed `Cody Wyoming Temple`; the product is `Cody Temple Tee`. Search on the place token the user gave you, not on the official name research turned up.
- **The place token is not consistent across garments.** The tee is `Salt Lake City Temple Tee`, while the fleece is `Salt Lake Temple Sweatshirt` and `Salt Lake Temple Hoodie`. Resolve each garment independently and never derive one garment's title from another's.

Resolve like this:

1. Call `search_products` with `product_type:"T-Shirt"` plus the place token. `product_type` is the reliable garment discriminator; the title suffix is a convention that can drift, and `product_type` is what actually distinguishes CC1717 from CC1566 from CC1567 in this store.
2. Read every title returned. Take the one that reads exactly `{place} Temple Tee`.
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

- `references/known-myths.md` — folklore that must never ship, with corrections. Read this every time.
- `references/special-cases.md` — temples that break the standard field set. Check before writing.
- `assets/product-intro.html` — the fixed Tee section. Copy verbatim.
- `assets/size-guide.html` — the fixed Size Guide section. Copy verbatim.
- Shopify connector — `search_products`, `get-product`, `update-product`. The destination for every finished block. See **Publishing to Shopify**.
