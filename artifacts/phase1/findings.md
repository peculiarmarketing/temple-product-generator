# Phase 1 Findings: Printify API Round-Trip

Date: 17 August 2026. Reference product: Provo Temple Tee - With Date (6a80d9ee8ec477a3bb096ece, blueprint 706, provider 99). Test product created and deleted: 6a832761d3fd96b96e0e61ba.

## 1. Round-trip: CLEAN for everything the API accepts

POST with only the writable keys created a product where all five print area groups survived with identical variant_ids per group, white art stayed on the four dark colorway groups, black art stayed on the light group, every x/y/scale/angle matched exactly, and all 423 variants kept their price and is_enabled flags. Full diff in `roundtrip_diff.md`. Evan confirmed visually in the Printify editor that the shirt and design were correct.

Two POST validation rules the spec did not document, both now handled in `printify_client.writable_product_body()`:

- GET responses include unused placeholder positions with an empty images array (the front position on this back-print product). POST rejects them with "images field is required". Unused positions must be omitted entirely.
- The groups-by-colorway structure posted from a GET body works as-is. Groups did not flatten. The spec's flatten contingency is NOT triggered.

## 2. Text layers: NOT writable via the API. Contingency triggered.

The OpenAPI specification documents a text layer schema, but in practice both POST create and PUT update reject any text/svg layer with error 8253 "Provided images do not exist". The server validates every images[].id against the media library before considering layer type, and a text layer's id is a layer instance UUID, not a library asset. Verified three ways: original UUIDs rejected, omitting id rejected ("id field is required"), fresh UUIDs rejected. The documented schema describes what GET returns, not what writes accept.

Consequence per the spec's own contingency: the location line ("PROVO, UTAH") and any other text become SVG or PNG image layers rendered by the generator in Phase 2. The Alata tabular figures question disappears for location text.

The personalization date line is a harder problem, covered in section 6.

## 3. SVG upload: accepted, but rasterized server-side

`POST /v1/uploads/images.json` accepted San Antonio black.svg (907 KB base64). The library entry comes back as mime_type image/png at 1978x1978, the SVG's declared pixel size. Two implications:

- No upload rejection, so the generator does not strictly need a rasterize step for uploads. But Printify rasterizes at the SVG's declared dimensions, roughly 2048 px, which is below print resolution for a large back print. Phase 2 should decide whether the generator rasterizes locally at print-area-native resolution and uploads PNG instead, for quality. The existing hand-built products carry the same roughly 2048 px art, so generated products would match current live quality either way.
- Uploads are content-deduplicated. Re-uploading identical art returns the existing asset id. Generator uploads are therefore idempotent.

Cleanup note: the test upload deduplicated to the existing "San Antonio black.svg" asset from 12 August, and the archive call archived that shared asset. The live San Antonio product is unaffected (archived assets keep working), but the file now sits in the Archived tab of My Library. Restore it from there if you want it visible again.

## 4. product_type: PASS for all three garments

Shopify derives it exactly right at publish: tee is `T-Shirt`, sweatshirt is `Sweatshirt`, hoodie is `Hoodie` (checked via public storefront JSON on provo-temple-tee-with-date, nauvoo-temple-sweatshirt-front-logo, copy-of-nauvoo-temple-hoodie). No post-publish correction step needed. The description skills will see generated products on this axis.

## 5. Publish availability: assessed, not proven

Store is on Pause and Build (Evan confirmed). The storefront is live, publicly readable, and the latest product published 15 August 2026. No test publish was performed per the spec. Confidence is high but live proof waits for Phase 3's template test.

## 6. New findings outside the spec's contingency list

These three product properties are read-only via the API and were lost or defaulted on the created copy. Evan spotted all three in the editor:

| Property | Where it lives | Behavior on API create |
|---|---|---|
| Mockup selection | `images[]` with is_selected_for_publishing / is_default | Copy got 32 default mockups, front camera as default. A PUT of curated flags returns 200 but is silently ignored. |
| Personalization config | `sales_channel_properties.personalisation` (layer, instructions, strategy pstudio) | Absent on the copy. Not in the writable surface. |
| Shipping options (express/economy) | top-level read-only booleans | Not carried over. |

Consequence: an API-only generator produces products needing per-product UI touch-up for mockups, personalization, and shipping. That is the wrong workflow at 250 products.

**Proposed Phase 3 flow change to test (Evan's suggestion):** duplicate the template product in the Printify UI (duplication should carry mockup selections, personalization, and shipping), then the generator PUTs the design swap (new art ids, positions, title) onto the duplicate. Open question to answer in Phase 3: does a print_areas PUT preserve those settings, or does changing the design reset mockups? If it preserves them, onboarding a temple becomes: one UI duplicate per garment (seconds each), then the generator does the rest. Alternatively test one API-created product to measure how long the UI touch-up actually takes; if mockup selection is quick, API-only may still win.

## 7. Artifact index

All under `artifacts/phase1/`: shops.json, candidates.json, reference_product.json, reference_notes.json, post_body.json, create_response.json, created_product.json, roundtrip_diff.md, put_text_response.json, mockup_put_probe.json, upload_response.json, deletion.json, shopify_product_type.json, publish_check.json.

## 8. Cleanup confirmation

Test product deleted, GET returns 404 (deletion.json). Test upload archived (see section 3 note about the shared asset).

## 9. On-record note for Phase 3/4 manifest design

Temple folder and file naming in `../Temples/` is inconsistent: "Cody/Cody Wyoming Temple black.svg" vs "Logan/Logan black.svg" vs "St. George/St George black.svg", one file with a trailing space. The manifest schema must carry explicit art file names per temple and never derive them from the folder name. Also on record: the live title collisions now include "Copy of Nauvoo Temple Hoodie" alongside the known Provo and Nauvoo collisions, and the live catalog already contains a front-logo sweatshirt (nauvoo-temple-sweatshirt-front-logo), so the front-logo garment line is not hypothetical.

## Gate verdict

The core bet of the plan holds: product structure, art assignment per colorway group, positions, and variants round-trip cleanly through the API, and product_type derives correctly. The plan's text layer contingency is triggered (render text as images). The genuinely new information is the read-only trio (mockups, personalization, shipping), which argues for testing the UI-duplicate-plus-API-update flow at the start of Phase 3.
