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
