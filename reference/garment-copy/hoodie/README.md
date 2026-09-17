# Garment copy: hoodie

`generate.fixed_description()` assembles this folder's fixed sections in this
order, and `description_html.compose_description()` appends the temple's own
facts fragment after them:

1. `product-details.html` - fit, fabric and weight for this blank
2. `product-intro.html` - the founder message, signed "- Evan"

`size-guide.html` is still here and is NOT used. Evan's 16 Sep 2026 call took
the size guide out of the description entirely. The file stays because it holds
the blank's real measurements, which is worth keeping; it is simply not assembled
any more. A garment folder with no `product-details.html` falls back to the older
`product-intro.html` + `size-guide.html` shape, which is what the retiring
Printify garments (cc1566, cc1567, cc1717) still use.

THE GUARD: if either `product-details.html` or `product-intro.html` is missing,
`fixed_description()` returns an EMPTY string rather than a partial description.
An empty description beats the wrong garment's specifications on a live product
page, which is why a placeholder file would be worse than no file. Both are
present for this garment as of 16 Sep 2026.

Both files are stored assets: copied byte-identical at assembly and never touched
by an editing pass. New outward-facing prose goes through the `humanizer` then
`structural-humanizer` skills before it ships (project CLAUDE.md).
