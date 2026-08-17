# Decision Log

Decisions Evan has made, with dates. These override or refine the spec (docs/temple-catalog-generator-plan.md).

## 17 August 2026 (Phase 1 gate and Phase 2 gate)

- **Generator architecture: duplicate-then-edit.** Evan duplicates the template product in the Printify UI (carries mockup selections, personalization config, shipping options); the generator PUTs the design swap. Proven in the duplicate-flow experiment. API-only creation is rejected because mockups, personalization, and shipping are read-only via API and default wrong.
- **Text layers are UI-only.** Any API write to print_areas wipes them, and they cannot be posted or updated. Location line is a generator-rendered image (Alata font, from the manifest's location string). Manual override honored: a `*location text*{black|white}*` file in the temple folder wins over auto-render. The personalization date layer on With Date products is re-added by hand in the Printify editor after generation.
- **Resolution rule.** Uploads bump the SVG's declared width/height attribute to 4096 in memory (files on disk never modified). Proven to clear Printify's low-DPI warning. The live catalog's 2048 px assets are a Phase 5 backfill item.
- **Art source of truth: `Temples/{Name}/` folders.** Manifests name art files explicitly (folder naming is inconsistent).
- **Spacing constants** (see spacing_defaults.json): measured from the live catalog and approved via previews. Location text: 0.74 in tall on base products, 0.38 in on With Date. Divider on With Date: **2.0 in** (changed from the live products' 3.0 in at the Phase 2 gate so it does not read as an underline).
- **With Date logo placement:** auto-pick the emptier top corner, near the temple, never flush to the print area edge. Manifest override available per temple.
- **Sizing across shirt sizes: proportional** (design scales with the garment, matching the live catalog). Not physical-inch-consistent.
- **Tracer standard going forward: drop `--square`.** New temples are traced `--trim --drop-label`; files come out at the drawing's natural aspect. Existing square files stay and work identically (the layout engine measures ink, not frames). NOTE: the live tracer skill in claude.ai still documents `--square` in its examples; update it there on the next skill edit.
- Both text-size conventions and the base vs With Date layouts are separate layout profiles: `back_stack` and `back_stack_dated`.

## 17 August 2026 (Phase 3)

- **Location line rule: the temple's PHYSICAL city, not its name-city.** Confirmed from the live catalog: Washington D.C. Temple prints KENSINGTON, MARYLAND; Provo City Center prints PROVO, UTAH. Format: all caps, comma, spelled-out state, country for international.
- **temples.json is the location dataset.** Folder name maps to official name and verified location line. The 14 finished temples were extracted from the live products themselves. A folder with no manifest gets one scaffolded automatically from this dataset; unverified entries hard-stop with instructions rather than guessing. New temples: the Phase 4 skill researches the physical location (churchofjesuschristtemples.org as the reference), appends the entry, and asks Evan only when uncertain.
- **New-temple flow:** drop a folder with two SVGs into Temples/. Everything else (manifest, location text, layout, upload, product) is derived.
- **Dress rehearsal passed.** Generated Logan Temple Tee (from a UI duplicate of the live product) matched the hand-built one in the editor with all mockups preserved and high-resolution art. Evan approved.
- **Publishing stays manual for now.** The generator produces complete unpublished drafts; Evan clicks publish in Printify. Automated publish (with the 200-per-30-minutes throttle) is deferred to backfill planning.
- **Personalization-optional is parked.** Folding With Date into base would need a design that looks right with and without the date line; Evan is not designing that now.
## 17 August 2026 (Phases 4 and 5 closed)

- **Recurring runs are manual.** No scheduled task. Evan triggers the sweep in a session ("run the sweep"); the project skill handles it. Rationale: generation depends on duplicates Evan makes by hand and publishing is manual, so a schedule saves only the typing.
- **No catalog backfill.** Evan decided the existing hand-built products stay as they are. `--in-place` remains available as a tool for one-off regeneration if ever wanted, but there is no backfill campaign, which also retires the publish-throttle concern.
- **Catalog gaps found by the first coverage report:** seven missing With Date tees (Nauvoo, Provo City Center, Salt Lake, San Diego, Saratoga Springs, St. George, Washington DC). Evan is making seven With Date duplicates; one sweep fills all seven.

- **Descriptions are written to Printify pre-publish.** The pipeline session researches each temple once (same methodology, sources, and myth screening as the claude.ai description skills, which we hold verbatim in reference/skills/), saves the facts fragment to `Temples/{Name}/temple-facts.html`, and `scripts/write_description.py` applies fixed sections plus facts to all the temple's generated products. Products publish complete. With Date products get descriptions (the claude.ai skills never matched their titles). The claude.ai description event stays untouched; its post-publish overwrite of the same products is harmless churn until Evan retires it. Generator also sets fixed intro plus size guide at swap time so a draft never carries the donor temple's facts.

- **No designated template products; any duplicate works.** Evan clarified his "templates" are Printify editor design-templates (saved layer arrangements), which the generator replaces entirely. What the pipeline needs from a duplicate is only the API-invisible settings, and any product of the right garment carries them. The generator claims any unclaimed "Copy of ..." product matching the garment's blueprint and provider; "With Date" copies are reserved for the dated line (personalization config); "front logo" copies are ignored (tests). Evan's editor design-templates become unnecessary for generated products.
