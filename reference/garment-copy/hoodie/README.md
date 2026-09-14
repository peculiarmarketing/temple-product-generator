# Garment copy: hoodie

**AWAITING BLANK SELECTION. Do not create the HTML files until the blank is picked.**

`generate.fixed_description()` needs two files in this folder:

- `product-intro.html` - the founder intro for this garment
- `size-guide.html` - the size guide section

They are deliberately absent. While they are absent `fixed_description()` returns
an empty string, which is the safe behaviour: an empty description beats
publishing the wrong garment's specifications to a live page. A placeholder file
would defeat that guard, which is why this is a README and not a stub HTML file.

## When Evan picks the hoodie blank

1. Write the intro and the size guide from the real blank's specifications.
2. The size guide needs a decision: the retiring Comfort Colors guides embed a
   per-blank video (`Important Elements/cc17*-size-guide.mp4`). A new blank needs
   either a new video or the branded size-chart images already in
   `Important Elements/` (Signature Heavy Tee, Covenant Crew, Foundation Hoodie,
   Summit Hoodie, made Aug 2025). Evan's call.
3. New outward-facing prose goes through the `humanizer` then
   `structural-humanizer` passes before it ships (project CLAUDE.md).
4. Once written these are stored assets: copied byte-identical at assembly, never
   touched again by an editing pass.
