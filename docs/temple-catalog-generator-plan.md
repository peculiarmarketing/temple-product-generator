# Peculiar People: Temple Catalog Generator Plan

Hand this document to a fresh Claude session. It contains everything needed to execute without re-deriving context. Work phase by phase. Do not start a phase until the previous phase's gate has passed and been confirmed by Evan.

**Revision 2, 17 August 2026.** Changes from revision 1 are marked **[R2]** where they alter an instruction. The largest change is that Phase 1 is now much smaller: Printify's OpenAPI specification answered most of what Phase 1 was designed to discover, so Phase 1 is a confirmation of write behavior rather than a schema investigation.

---

## 1. Context the executing session needs

**Business.** Peculiar People (peculiarpeopleco.com) sells garment-dyed heavyweight apparel with original hand-drawn line illustrations of Latter-day Saint temples. Fulfilled print-on-demand via Printify (shop ID 23119809), sold via Shopify. Evan is the sole operator.

**Garments.**
- CC1717 tee (Comfort Colors, 6.1 oz)
- CC1566 crewneck sweatshirt
- CC1567 hoodie (identical body block to CC1566)
- Personalizable tee (temple plus a text line for a sealing date, mission call date, etc.)
- Possibly personalizable crew and hoodie later
- Possibly a front-logo variant of each later

**Design structure on every product.** Back print. From the top of the print area down: temple illustration, then a location text line, then brand logo. On the personalizable product, an additional text line for the customer's date. Dark colorways get the white SVG, light colorways get the black SVG.

**The location line is different for every temple.** It is the temple's city and state or country in caps, e.g. "LOGAN, UTAH", "SAN ANTONIO, TEXAS", "ROME, ITALY". It is a per-temple input carried in the manifest, never hardcoded. It also varies in length, so its rendered width varies; the layout must center it. **[R2]** Printify supports native text layers with a documented schema (see Phase 1), so the location line is most likely a native text layer rather than a rendered SVG image, which removes the fixed-cap-height rendering problem. Confirm with Evan the exact format (comma, spelled-out state vs abbreviation, country handling for international temples) and treat it as a fixed rule.

**The problem.** Every temple times every garment is a separate Shopify product. This is architecturally correct (Printify variants are size and color only, driven by the blueprint) but the count grows fast: 50 temples times 5 products is 250, and more garments or a front-logo line doubles it. Each product is currently authored by hand, including manually assigning white art to 2 to 4 dark colorways per product. The fix is not to reduce the count but to generate each product from a template.

**Layout decision already made.** Everything anchors to the top of the print area. Taller temples push the location text and logo further down. Wider temples leave more room below. Text and logo sit at fixed offsets below the lowest ink pixel of the temple, never at fixed absolute positions, because SVGs vary in aspect ratio and fixed positions caused overlap on wide temples.

### API access, credentials, and limits **[R2, new section]**

The generator talks to Printify over the REST API directly, not through the Printify MCP connector. Two reasons: the MCP connector exposes no product-create tool, and its call allowance is metered monthly and has already been exhausted once. The API is also what the production generator will use, so exploration and production share one code path.

Prerequisites before Phase 1 can run:

1. **Network access to `api.printify.com`.** In a sandboxed Claude environment this host must be in the network egress allowlist or every request returns 403 with `x-deny-reason: host_not_allowed`. In Claude Code this is usually not a constraint, but verify with a `GET /v1/shops.json` before assuming.
2. **A Printify Personal Access Token.** Generated at My Profile then Connections. Printify displays it once only. Required scopes: `shops.read`, `catalog.read`, `products.read`, `products.write`, `uploads.read`, `uploads.write`, `print_providers.read`. Orders and webhooks scopes are not needed. Tokens expire after one year.
3. **A User-Agent header on every request.** Printify's documentation requires it. Set it to something identifying, e.g. `peculiar-people-generator`.

Base URL is `https://api.printify.com/v1/`. Auth is `Authorization: Bearer {token}`. Content type is `application/json;charset=utf-8`.

**Rate limits, which constrain Phase 4 and Phase 5 directly:**

- 600 requests per minute globally, per account.
- 100 requests per minute for Catalog endpoints, on top of the global limit.
- **200 publish requests per 30 minutes.** This is the binding constraint on any bulk run. A backfill of 50 temples times 5 garments is 250 publishes and cannot complete in one window. The generator needs to either throttle publishes or batch them across windows, and Phase 5 must plan around it.
- Error responses may not exceed 5% of total requests. A generator that retries aggressively on failure can trip this.

**Voice and formatting rules for anything Evan-facing.** No em dashes anywhere. Direct, plain, no brand-speak. Complete copy-ready outputs, not partial edits. Explain the mechanism of a failure before fixing it.

**Working style.** Evan prefers direct execution over proposal-and-confirm. When something needs to be built, build it. But every phase gate below is a real stop: report results, get confirmation, then proceed.

**Existing skills and how they fit.** Read each SKILL.md before touching anything.

- `temple-svg-tracer` (`/mnt/skills/user/temple-svg-tracer/`). Converts sketch PNGs into black and white transparent SVG pairs. Current catalog standard flags: `--trim --square --no-label-group`. The `--square` flag pads every SVG to 1:1, which contributed to the layout problem: a wide temple gets large empty bands top and bottom, so text and logo placed at fixed positions either overlap the temple or float far below it. See Phase 2 for the two options. **[R2] Correction to revision 1:** dropping `--square` does not make the layout math trivial. `--trim` leaves a margin of 2 percent of the drawing's longest side by default, and the tracer's own verification section treats ink touching the frame as the failure mode that loses linework, so `--margin 0` is not a safe workaround. `ink_bbox` is required under both options. The real choice is whether catalog files carry dead space and whether the tracer's SKILL.md changes, not how much math the generator does.
- `cc1717-temple-description-builder`, `cc1566-temple-description-builder`, `cc1567-temple-description-builder`. Each builds a source-verified Shopify description for a named temple and writes it directly to the matching Shopify product. They already run as a scheduled event and are working. **They do not change.** **[R2]** How they locate their target product is now known and documented in Phase 3; that investigation is complete and should not be repeated.
- `temple-fact-checker` is the research layer under the description skills. Not touched.
- New skill to build: `temple-product-generator` (Phase 4). Sits upstream of the description skills.
- Printify REST API via Personal Access Token. **[R2]** The Printify MCP connector is not the integration path; see the API section above.
- Shopify MCP connector. **[R2]** This is the only path for anything Shopify-side, notably `product_type`, which Printify's API does not expose.
- Alata is the built-in Printify font used for text layers. Whether it has tabular lining figures is unverified.
- Size-split print area groups are already configured on existing products via API (physical inch consistency across garment sizes). The Printify UI cannot create these; the API can.
- Known open bug: Printify personalization panel's character limit field does not render. A support ticket was recommended and may not have been filed.
- Store was on Pause and Build plan as of recent sessions.

---

## 2. Target end state

A skill (working name `temple-product-generator`) that:

1. Reads a temple folder containing: black SVG, white SVG, and a small manifest (temple slug, official temple name as the description skills expect it, per-garment place tokens, location line in the fixed caps format, and which garments to generate).
2. Computes layer positions per garment from the SVG's ink bounding box using the top-anchor rule.
3. Clones the correct template product per garment, swaps in the two image IDs, writes computed positions into every print area group, sets title and handle, and POSTs it to Printify.
4. Publishes each product to Shopify.
5. Writes a status file back to the folder listing created product IDs, or the failure reason.
6. Runs as a scheduled morning event that watches a designated folder for new temple subfolders, so the existing description event can pick up the new products afterward.

**Modularity requirement (non-negotiable design constraint).** The system is two independent lists that the generator crosses: temples and garments. Adding a temple must never require touching code or garment config. Adding a garment (a new tee, a different hoodie, pants, a front-logo variant, a personalizable crew) must never require touching temple files or the layout code. Everything garment-specific lives in one config file per garment, `garments/{garment_id}.json`, and the generator iterates over whatever garment configs exist. Concretely, a garment config holds:

- `template_product_id`: the Printify template product to clone.
- `print_area`: which placeholder position (back, front, leg, etc.), its physical width and height in inches, and its normalized coordinate mapping.
- `layout_profile`: which stacking rule applies. Start with one profile, `back_stack` (temple, location, logo, top-anchored). A front-logo variant adds a second print area with a `front_logo_only` profile. Pants or a sleeve would add a profile that fits its area. Profiles are functions in `layout.py`, selected by name from the config; adding a profile is the only code change a genuinely new layout requires.
- `spacing`: the constants for that garment (top margin, target temple width, gaps, bottom margin, overflow rule). Defaults inherit from a shared `spacing_defaults.json`; a garment overrides only what differs. This matters because fleece and tees may want different temple widths and because a leg print is a different shape entirely.
- `personalized`: whether this garment carries a customer text line and where it sits in the stack.
- `art_variants`: which art file each colorway group receives. Default is `black` for light groups and `white` for dark, but a garment could later ask for a fleece-weight variant (heavier minimum stroke) by naming `black_fleece` here, and the temple folder would then be expected to contain that file. Missing file is a hard error, not a silent fallback.
- `naming`: title and handle pattern with `{place_token}` and `{location}` placeholders, so the description skills can find the product. **[R2]** The token is the place token, not the official temple name. See Phase 3.
- **`product_type` [R2, new field].** The exact Shopify product type string this garment must carry: `T-Shirt`, `Sweatshirt`, or `Hoodie`. This is the field all three description skills discriminate on. Printify's API does not accept or expose it, so it is set Shopify-side and must be verified after publish. A generated product with a wrong or missing `product_type` is invisible to its description skill no matter how correct the title is.
- `description_skill`: which description skill handles this garment, or `none` if it needs a new one. This is informational for Evan, but it makes the gap visible when a new garment is added.

The manifest for a temple stays garment-agnostic: slug, official name, **per-garment place tokens [R2]**, location line, list of art files present, and optionally a `garments` filter (default: all configs present). Onboarding a new garment is then: build one template product in Printify, write one JSON config, run the generator on one temple, review, done. The SKILL.md must include a checklist for exactly that.

---

## 3. Phases

### Phase 1: Prove the API round-trip

**Purpose.** Everything downstream depends on Printify's API preserving the product configuration on POST.

**[R2] What is already known, and must not be re-investigated.** Printify's OpenAPI specification (`https://developers.printify.com/openapi.json`) documents the following. Treat these as established:

**The writable surface.** `POST /v1/shops/{shop_id}/products.json` and `PUT /v1/shops/{shop_id}/products/{product_id}.json` accept exactly: `title`, `description`, `safety_information`, `blueprint_id`, `print_provider_id`, `variants[]` (each with `id`, `price`, `is_enabled`), and `print_areas[]`. Required on create: `title`, `blueprint_id`, `print_provider_id`, `variants`, `print_areas`. Nothing else is accepted, so "strip server-generated fields" means keep only these keys. Everything else in a GET response (`id`, `images`, `views`, `created_at`, `updated_at`, `sales_channel_properties`, `user_id`, `shop_id`, `is_locked`, the express and economy shipping booleans) is read-only.

**Print area structure.** Each entry in `print_areas[]` is `{variant_ids: [int], placeholders: [{position, images: []}], background}`. Size-split groups are expressed as multiple entries in this array, each with its own `variant_ids`. This is why the API can create them and the UI cannot.

**Layer schema, image and text in the same array.** Both kinds of layer live in `placeholder.images[]`. An image layer carries `id`, `x`, `y`, `scale`, `angle`. A text layer carries:

```json
{
  "id": "0bd183ab-7bd0-e327-8329-7f77ee2a3f51",
  "type": "text/svg",
  "x": 0.5, "y": 0.5, "scale": 0.7444, "angle": 0,
  "font_family": "ABeeZee",
  "font_size": 200,
  "font_weight": 400,
  "font_color": "#ffffff",
  "font_style": "normal",
  "input_text": "Text example",
  "text_align": "left"
}
```

This means the location line and the personalization date line can both be native text layers positioned exactly like image layers, with no upload step and no rendered SVG. The revision 1 contingency for rendering text as an image is probably unnecessary. Note the schema shows no character-limit field, so the personalization constraint may not be expressible via API at all.

**Coordinate semantics, confirmed.** `x` and `y` are the layer's center as a fraction of the print area, 0 to 1. `scale` is a float relative to the print area (the spec's example uses `1.01`, meaning slightly overfilled). `angle` is degrees. `layout.py` can be written against this without waiting for a live product.

**Uploads.** `POST /v1/uploads/images.json` takes `file_name` plus either `url` or `contents` (base64). Printify recommends URL for files over 5MB and notes base64 may be deprecated eventually. Sandbox files are not publicly reachable, so base64 is the path unless the environment can serve a URL.

**Publish.** `POST /v1/shops/{shop_id}/products/{product_id}/publish.json` with boolean flags `title`, `description`, `images`, `variants`, `tags`, `keyFeatures`, `shipping_template`. Companion endpoints exist for `publishing_succeeded.json`, `publishing_failed.json`, and `unpublish.json`.

**Steps [R2, reduced scope].**
1. Confirm API access: `GET /v1/shops.json` returns and includes shop 23119809.
2. Ask Evan for one existing, correctly configured CC1717 product ID (a temple with both black and white art assigned and size-split groups in place).
3. `GET /v1/shops/23119809/products/{id}.json`, save to disk, and record only what the spec cannot tell you: how many groups exist and which `variant_ids` are in each, which image ID is black art and which is white and which groups they sit in, whether any text layers are present and what their actual field values are, and the real `scale` values in use.
4. Build a POST body using only the writable keys listed above. Change the title to add "API TEST" and change the handle. POST to `/v1/shops/23119809/products.json`.
5. GET the created product back and open it in the Printify editor. Verify: size-split groups survived with the same `variant_ids` per group; white art is still on the same dark colorways; positions match per group; text layers, if any, kept font, size, and color. **This is the actual point of Phase 1: the spec documents the schema, but a documented schema is not verified write behavior.**
6. **[R2, new] Test SVG upload directly.** Upload one temple SVG via `POST /v1/uploads/images.json` and check the response `mime_type` and dimensions. Printify's own help documentation says SVG is accepted up to 20MB, but at least one recent third-party source claims the uploader now takes PNG and JPG only. The sources conflict and the disagreement breaks along a time axis, which suggests a real policy change. If SVG is rejected or silently rasterized at the wrong resolution, the generator needs a rasterize step, and that step should share the same rasterization function `ink_bbox` already needs. Record the answer explicitly.
7. Delete the test product.
8. **[R2, new] Verify `product_type`.** Using the Shopify connector, read an existing published CC1717 product and confirm its `product_type` is exactly `T-Shirt`. Repeat for one CC1566 (`Sweatshirt`) and one CC1567 (`Hoodie`). Printify derives this from the blueprint at publish time and the API neither accepts nor returns it. If the derived value does not match, every generated product will be invisible to its description skill, and the generator needs a Shopify-side correction step after publish.
9. Confirm publish is possible: check whether the shop's current Shopify plan blocks the publish endpoint. Do not publish the test product; check plan status, or unpublish immediately if a live test is unavoidable.

**Gate.** Report to Evan: does the configuration round-trip cleanly? Do text layers post and return intact? Does SVG upload work, or is rasterization required? Does `product_type` derive correctly for all three garments? Is publish available?

**Contingencies.**
- If per-variant image groups flatten on POST: the generator constructs groups from scratch instead of copying. Document the exact group schema needed. Plan still works, more code.
- If native text layers do not post cleanly despite the documented schema: location text and logo become SVG image layers rendered by the generator. Only the personalization date field stays a native text layer. This also removes the Alata tabular-figures question for location text.
- **[R2]** If SVG upload is rejected: add `rasterize(svg_path, dpi)` to `layout.py` and upload PNG. Layout math targets pixels rather than vector units. Decide the DPI from the print area's pixel dimensions, which the catalog variants endpoint reports per size.
- **[R2]** If `product_type` does not derive correctly: the generator gains a post-publish Shopify update step, and the plan gains a second API dependency. Tell Evan before building it.
- If publish is blocked by plan: generator creates as unpublished draft, and publish becomes a manual step or waits for a plan change. Ask Evan.

### Phase 2: Layout math (no API calls)

**Purpose.** Compute layer positions deterministically from the SVG. All output is preview PNGs for Evan to eyeball. Nothing touches Printify.

**Inputs to collect from Evan first.**
- Print area dimensions in inches for each garment (back print area for CC1717, CC1566, CC1567). Read these from the Phase 1 JSON if present, otherwise from `GET /v1/catalog/blueprints/{blueprint_id}/print_providers/{print_provider_id}/variants.json`, which reports `placeholders[].width` and `height` in pixels per variant. Note these differ per size, which is exactly why size-split groups exist.
- Fixed spacing values: inches from temple ink bottom to top of location text; inches from location text baseline to top of logo; on personalizable products, where the date line goes (between location and logo, or below logo) and its spacing.
- Target temple width as a fraction of print area width, and top margin in inches.
- Logo file (SVG) and its intended physical width.
- Location text font and cap height.
- Overflow rule: when the full stack would breach the bottom margin, shrink the temple until it fits. Confirm this rule and confirm the bottom margin.

**Steps.**
1. Write a Python module `layout.py` with:
   - `ink_bbox(svg_path)`: rasterize the SVG (cairosvg or similar) and return the bounding box of non-transparent pixels as fractions of the SVG frame. This handles both trimmed and square SVGs; do not trust the frame. **[R2]** Required under both tracer options, because `--trim` still leaves a 2 percent margin.
   - **[R2] `rasterize(svg_path, dpi)`**: shared by the preview renderer, by `ink_bbox`, and by the uploader if Phase 1 showed SVG upload is not available. Write it once even if uploads accept SVG, because the preview needs it anyway.
   - `compute_stack(svg_paths, garment_config, temple_manifest)`: looks up `garment_config["layout_profile"]`, dispatches to that profile function, and returns a dict of layers per print area, each with x, y, scale in Printify's normalized 0 to 1 coordinates, plus physical inch positions for the preview. Profiles are registered in a dict so a new one is one function plus one entry.
   - `back_stack` profile: temple ink top sits at top margin. Scale to target width. Then location, then optional date line, then logo at configured gaps. If resulting stack height exceeds available height, reduce temple scale until it fits.
   - **[R2]** Printify's `x` and `y` are the layer's center and `scale` is relative to the print area. This is confirmed in the OpenAPI spec, so build against it. Sanity check the real values from the Phase 1 JSON, but do not treat the semantics as unknown.
2. Write `preview.py` that renders the stack on a rectangle sized to the print area, in inches at some DPI, so spacing can be judged.
3. Run on three temples spanning aspect ratios: a tall one (Salt Lake or similar), a wide one (San Antonio or similar), and a mid-range one. Produce preview PNGs for tee and hoodie for each. Produce one personalizable variant.
4. Decide the tracer change. Two options, pick one with Evan:
   - **Option A: drop `--square`.** New SVGs come out trimmed to the ink plus a 2 percent margin. Files carry no dead space and every catalog file frames consistently. Existing square catalog files still work because `ink_bbox` measures pixels, not frame. Update the tracer's SKILL.md default flags to `--trim --no-label-group` and note the date of the change.
   - **Option B: keep `--square`, change nothing.** Tracer untouched, no split in the catalog's file shapes, every SVG carries dead space.
   **[R2]** Both options require identical layout code. The recommendation is still A, but on the grounds of file cleanliness rather than simpler math, and B is the lower-risk choice if avoiding a skill change matters more than tidy files.
5. **[R2]** Verify how the location text will be produced against the Phase 1 finding. If native text layers posted correctly, the generator writes the location string into a text layer per product and no rendering is needed. If not, add `render_text_svg(text, cap_height_in)` to `layout.py`. Either path needs the per-temple string from the manifest.

**Gate.** Evan reviews the preview PNGs and either approves the spacing values or adjusts them. Confirm the overflow rule looks acceptable on the tall case. Confirm the personalization line position.

### Phase 3: Templates and generator

**Purpose.** Build one template product per garment and a generator that clones them.

**[R2] How the description skills locate their product. This is settled; do not re-investigate.** All three resolve on Shopify `product_type` plus an exact title match, and they match on title only, never on handle, because handles in the live catalog carry typos (the Washington D.C. hoodie lives at `washinton-d-c-temple-hoodie`).

| Skill | `product_type` | Title pattern |
|---|---|---|
| cc1717 | `T-Shirt` | `{place} Temple Tee` |
| cc1566 | `Sweatshirt` | `{place} Temple Sweatshirt` |
| cc1567 | `Hoodie` | `{place} Temple Hoodie` |

Three consequences the generator must handle:

1. **The title uses a place token, not the official temple name.** The facts section of a page is headed `Cody Wyoming Temple` while the product is `Cody Temple Tee`.
2. **The place token is not consistent across garments in the live catalog.** The tee is `Salt Lake City Temple Tee` while the fleece is `Salt Lake Temple Sweatshirt` and `Salt Lake Temple Hoodie`. The manifest therefore cannot carry one name and derive all titles from it. It needs either a per-garment token map or a single token applied to new products going forward, accepting that existing rows stay inconsistent. This is Evan's decision.
3. **The skills hard-stop when more than one title plausibly matches, and live collisions already exist.** `Provo Temple Tee` against `Provo City Center Temple Tee`; `Nauvoo Temple Tee` against `Nauvoo Temple Tee - Limited Edition`. The generator must check existing titles before creating, or it will manufacture exactly the ambiguity that halts the description run.

**Steps.**
1. Evan (or the session, via API, if Phase 1 showed groups can be posted from scratch) creates one template product per garment in Printify: correct blueprint and provider, all colorways enabled, size-split print area groups configured, black placeholder art in light groups and white placeholder art in dark groups, price, tags, and for the personalizable template the personalization text layer with its settings. Title them clearly, e.g. `TEMPLATE - CC1717 - do not publish`. Keep them unpublished.
2. Before building the generator, check two Printify things on the personalizable template:
   - Can the personalization field be optional at checkout? If yes, the personalizable tee can fold into the base tee and the product count drops by a third. Ask Evan whether to take that path.
   - The character-limit rendering bug: the OpenAPI schema shows no character-limit field on text layers, so the constraint may not be expressible via API at all. If the template cannot be saved correctly, file the Printify support ticket now. The generator can only copy what the template holds.
3. Write `generate.py`:
   - Input: a temple manifest and the set of garment configs in `garments/`. Image upload happens once per temple per art file via `POST /v1/uploads/images.json`; store returned IDs in the manifest under the art file's key. Rasterize first if Phase 1 showed SVG upload is unavailable.
   - **[R2] Title collision pre-check.** Before creating anything, list existing products and confirm no existing title would also plausibly match the intended title under the description skills' resolution rule. Abort that garment with a readable error rather than creating a colliding product.
   - For each garment config: GET its template JSON, replace each placeholder image ID with the temple's matching art ID per `art_variants`, write computed positions from `layout.py` into every group's image entries for every print area the config lists, set title and handle from the config's `naming` pattern, and POST as a new product using only the writable keys.
   - Publish each created product to Shopify (or leave draft per Phase 1 finding), then **[R2]** verify `product_type` on the Shopify side and correct it if Phase 1 showed it does not derive correctly.
   - Return created product IDs and any errors, keyed by garment id.
   - Write the first two garment configs (CC1717 and the personalizable tee) during this phase and prove they diverge only in config, not code. Add CC1566 and CC1567 as configs after, which should require zero code changes; if it does require code, that is a modularity bug to fix before Phase 4.
4. Test on one temple that already has a hand-built product. Open both in the Printify editor and compare: same colorway assignments, positions match the approved previews, mockups render correctly.
5. Delete the test outputs or keep them as the new canonical products if Evan approves.

**Gate.** Evan confirms one generated product set matches or beats the hand-built one. Confirm naming convention, place token policy, publish behavior, and whether personalizable folds into base.

### Phase 4: Skill and scheduled event

**Steps.**
1. Package `layout.py`, `generate.py`, the `garments/` config directory, `spacing_defaults.json`, the manifest schema, and a `SKILL.md` into `temple-product-generator` following the existing skill conventions in `/mnt/skills/user/`. Read `/mnt/skills/examples/skill-creator/SKILL.md` first. The SKILL.md must document: required temple folder contents, manifest fields, the garment config schema field by field (including `product_type`), spacing constants (with a note that these were approved in Phase 2 and should not be changed casually), the status file format, and a **"Adding a new garment" checklist**: build the template product in Printify, copy an existing garment config, fill in template ID, print area dimensions, layout profile, any spacing overrides, naming pattern, `product_type`, and description skill, then run the generator on one temple with `--garments {new_id}` and review before enabling it for the morning run. Also a shorter **"Adding a new layout profile"** note for the rare case a garment's print area doesn't fit an existing profile.
2. **[R2] Decide where the API token lives.** A scheduled run has no human to paste a token. It must be readable by the task from an environment variable or a file outside version control. Agree the location with Evan and document it in the SKILL.md. Never commit it.
3. Determine where the watched folder lives. If Google Drive, verify that scheduled tasks can access the Drive connector and can download SVG contents, not just list files. If not, agree on an alternative (an uploads folder the event can read, or a manual trigger).
4. Define the folder convention: one subfolder per temple, named by slug, containing `black.svg`, `white.svg`, `manifest.json`. The skill processes any subfolder without a `status.json` and writes `status.json` on completion or failure.
5. Run the skill manually on two or three new temples. Confirm the description event picks up the resulting products correctly on its next run.
6. Set up the scheduled morning event. Have it run before the description event so new products exist when descriptions are written. **[R2]** Cap the number of temples per run so a large backlog cannot exceed the 200 publishes per 30 minutes limit.

**Gate.** Two consecutive unattended morning runs succeed, or fail with a readable status file and no half-created products. Confirm the description event handles generated products.

### Phase 5: Backfill and QA

**Steps.**
1. Only after five or six generated products have been checked across sizes in mockups (and ideally one physical sample), regenerate existing hand-built products. This is one command per temple once trusted; do not rush.
2. Decide whether to regenerate in place (update existing product) or create new and retire old. Updating in place preserves Shopify URLs and any reviews; the generator needs a PUT path for that. `PUT /v1/shops/{shop_id}/products/{product_id}.json` accepts the same writable keys as create, so this is a small addition. Recommend adding it.
3. **[R2] Plan the backfill around the publish rate limit.** 200 publishes per 30 minutes means a full catalog backfill runs in windows, not in one pass. Build the throttle into the generator rather than discovering the limit through 429s, which also risks the 5 percent error-rate ceiling.
4. Keep the temple manifests and garment configs as the two sources of truth for the catalog. Adding a garment line later is one template product plus one config, then a re-run over the manifests filtered to that garment. Adding a temple is one folder. Neither should ever require editing the other.

---

## 4. Decisions Evan owns

Collect these before or during Phase 2. Do not guess them.

- Spacing values (ink bottom to text, text to logo, date line placement).
- Target temple width fraction and top margin.
- Overflow rule and bottom margin.
- Product naming convention for title and handle.
- **[R2] Place token policy:** per-garment token map in the manifest, or one token applied going forward while existing rows stay inconsistent.
- Whether personalizable products stay separate or fold into base (depends on Phase 3 finding).
- Where the watched folder lives.
- **[R2] Where the API token lives for scheduled runs.**
- Whether to drop `--square` from the tracer standard going forward (Option A vs B in Phase 2).
- Exact format of the location line (state spelled out or abbreviated, how international temples are written).

## 5. Things not to do

- Do not build the generator before Phase 1 passes. It is the cheapest test and the biggest risk.
- **[R2]** Do not re-derive the Printify request schema from scratch. It is in Phase 1 above, taken from the official OpenAPI specification. Verify write behavior, not field names.
- **[R2]** Do not re-investigate how the description skills find their products. It is documented in Phase 3.
- Do not use em dashes in any output shown to Evan.
- Do not modify the description skills; they already work.
- Do not publish test products to the live store.
- Do not regenerate the existing catalog until Phase 5.
- **[R2]** Do not commit the Printify token or paste it into any file under version control.
