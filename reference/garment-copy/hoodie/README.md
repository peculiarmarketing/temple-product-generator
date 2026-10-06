# Garment copy: hoodie

`generate.fixed_description()` assembles this folder's fixed sections in this
order, and `description_html.compose_description()` appends the temple's own
facts fragment after them:

1. `product-details.html` - fit, fabric and weight for this blank
2. `../care-instructions.html` - the shared care row (see below)
3. `product-intro.html` - the founder message, signed "- Evan"

`size-guide.html` is still here and is NOT used. Evan's 16 Sep 2026 call took
the size guide out of the description entirely. The file stays because it holds
the blank's real measurements, which is worth keeping; it is simply not assembled
any more.

THE GUARD: if either `product-details.html` or `product-intro.html` is missing,
`fixed_description()` returns an EMPTY string rather than a partial description.
An empty description beats the wrong garment's specifications on a live product
page, which is why a placeholder file would be worse than no file. Both are
present for this garment as of 16 Sep 2026.

CARE INSTRUCTIONS ARE SHARED. They do not live in this folder. All three current
lines assemble the one file at `reference/garment-copy/care-instructions.html`
(`generate.CARE_COPY`), because the five instructions and the symbol strip read
the same for the 350gsm fleece and the 7.7oz cotton tee, and one file means a
wash temperature can never be right on one line and stale on another. If THIS
line ever needs its own wording, drop a `care-instructions.html` in this folder
and it wins; nothing else changes. Unlike the two files above, a missing care
file does not degrade to an empty description: it hard-stops, because one shared
file cannot go missing for a single garment and blanking the catalogue would be
wildly out of proportion to a file that is simply not there.

`description_html.collapse_fixed_sections()` collapses BOTH the care section and
this folder's `product-intro.html` into `<details>` rows at assembly time, the
same as the temple facts. That is presentation, so it lives there and not in the
asset: both files on disk stay plain sections with plain `<h3>`s.

Which sections collapse is decided by `COLLAPSIBLE_FIXED_HEADINGS`, matching on
HEADING TEXT. Renaming this folder's `<h3>From the Founder</h3>` silently stops
it collapsing.

These files are stored assets: copied byte-identical at assembly and never touched
by an editing pass. New outward-facing prose goes through the `humanizer` then
`structural-humanizer` skills before it ships (project CLAUDE.md).
