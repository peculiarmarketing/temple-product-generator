# The Tapstitch editor is an API, not a click path

**Captured 15 September 2026** by recording the editor's own network calls while
Evan built one design by hand (`scripts/tapstitch_capture.py`). This answers the
first item in `config/tapstitch.json`'s checklist, which was the highest-value
unknown in the migration:

> BEFORE writing a single selector: open the network tab and save a design by
> hand. The save call almost certainly carries exact positions and upload
> references.

**It does.** Every step of product creation is a plain JSON HTTP call. No step
observed needs a selector, a click, or the editor's UI at all.

The raw capture is at `artifacts/tapstitch/network/capture-20260915-192710.jsonl`
(gitignored, redacted at capture time).

## The sequence, end to end

The run was: dashboard -> catalogue search -> editor -> design -> save ->
add to store -> details -> price -> save as draft.

| # | Call | Carries |
|---|---|---|
| 1 | `POST /api/services/user/service/template` | `{"silSn":"RT0063","productId":"1529865635893596160","colorCode":8079,"specialProcessTags":["DTG"],"productSource":1,"resourceCode":-1,"addToProductList":false}` |
| 2 | `GET /api/designs/user_cover_img/retrieve-upload-data?name=<filename>` | issues the signed OSS upload |
| 3 | `PUT https://ajmall-vc-public-bucket.oss-accelerate.aliyuncs.com/tapstitch/material/custom_printing/<loginId>/<uuid>` | the PNG bytes |
| 4 | `POST /api/designs/user_cover_img/save` | multipart, registers it in the image library |
| 5 | `POST /api/designs/user/history/img` | `{"width":4386,"height":5516,"url":"https://files.tapstitch.com/.../<uuid>.png","uniqueId":…}` |
| 6 | `PUT /api/designs/customized/templates/<templateId>` | **the save** — the whole design, below |
| 7 | `POST /api/services/user/distribution/stores/<storeId>/products` | title, description HTML, prices, variants (~45KB) |

A draft edit is staged at
`POST /api/services/user/distribution/stores/products/edit/cache/<uuid>` and
`DELETE`d when the draft is committed.

## The save payload

```json
{"colorCode": "8079,8088,8084,8085,8081",
 "uniqueId": "1549714541104005120",
 "productId": "1529865635893596160",
 "designTools": "2d-layers", "printType": 1, "isUsedHd": false,
 "dimension": "inches", "specialProcessTags": ["DTG"],
 "config": [{"piece": "front",
             "canvasSize": {"width": 700, "height": 700},
             "objects": [{"src": "https://files.tapstitch.com/.../aff46a6e….png",
                          "left": 344, "top": 358,
                          "width": 556, "height": 700,
                          "scaleX": 0.4671428571, "scaleY": 0.4671428571,
                          "angle": 0, "zIndex": 3}],
             "embs": []},
            {"piece": "back", "…": "identical geometry, different src"}]}
```

## What this settles

- **The blank is addressed by SKU.** `silSn: "RT0063"` with the blank's
  `productId`. There is no need to search a catalogue or click a result, which
  retires `blank_search_input`, `blank_result_by_name` and
  `start_designing_button`.
- **The flattened-file approach is confirmed.** Both files registered at
  **4386 x 5516**, which is exactly `garments/tee.json`'s real back print area.
  Nothing was re-cropped and `scaleX == scaleY`, so nothing was distorted.
- **Front and back place identically.** The two objects differ only in `src`.
  Because every file is built to the print area's own shape, the editor drops
  each one in the same way, so `design_size_input` and
  `design_size_unit_toggle` look unnecessary too.
- **Colours are numeric codes, not swatch names.** `colorCode` is
  `"8079,8088,8084,8085,8081"` for the five tee colourways, and template
  creation takes a single `colorCode: 8079`. The API route therefore sidesteps
  the swatch-name mismatch. **It does not retire the check**: the Shopify-side
  rename in `scripts/shopify_fixups.py` still matches on NAMES, so
  `colorway_renames_by_type` still has to agree with what Tapstitch publishes.
- **The Shopify store id inside Tapstitch is `1402569694703132672`**
  (type `shopify`, name `agv44k-jr`).
- **Saving a draft does not touch Shopify.** Checked immediately after: the
  newest product in the store is from 27 August 2026. The product stayed inside
  Tapstitch. The `save_draft_price` button does not publish.

## What is NOT settled — do not build on these

- **The canvas-to-inches mapping is unverified.** The object sits at
  `left: 344, top: 358` on a 700x700 canvas, not at 350/350. That is most likely
  the print area's centre rather than the canvas's, since a print area does not
  sit centred on a garment — but it was inferred, not measured. The replay
  reused the observed numbers rather than deriving them, so DO NOT generate
  placement for another garment until the mapping is worked out.
- **Only the tee (RT0063, DTG) was exercised.** The crew (R00368) and hoodie
  (R00286) print DTF and have their own print areas; their `specialProcessTags`
  and colour codes are unknown.
- **`create_store_product` has never been run.** It is the step that reaches the
  live storefront, and the store is dark.

## Replayed and confirmed, same evening

Steps 1, 2, 3 and 6 were driven from Python against the live account. Tapstitch
accepted the result and **rendered four mockups from it**, so it was processed as
a real design rather than stored and ignored. Verified by reading the design back
with `get_template`: the persisted `src` and geometry matched what was sent, and
a new `commitId` was minted.

`tapstitch_api.py` is that route as code.

**Auth is the profile's cookies and nothing else.** No CSRF header, no bearer
token, no editor session. 23 cookies lifted from the dedicated Chrome profile
authenticated every call.

**`srcDetails.srcId` is not required.** `srcDetails: {width, height}` is enough,
which is what lets step 4 — the multipart `user_cover_img/save` whose payload was
never captured — be skipped entirely.

### The traps, each of which fails silently or opaquely

- **`x-oss-meta-author` is part of what OSS signs.** Omit it from the upload PUT
  and you get a bare 403, with a signature that is fresh and otherwise correct.
  Its value is the `author` field that `retrieve-upload-data` returns.
- **The upload host and the reference host differ.** Bytes go to the
  `ajmall-vc-public-bucket…aliyuncs.com` bucket; a design must reference the same
  path on `files.tapstitch.com`.
- **A rejected call still returns HTTP 200.** The envelope's `code` is the truth.
- **A malformed save returns `code: 10001, "System error, please refresh and try
  again"`**, which names nothing. It means a required key is missing:
  `virtualConfig`, `mockupConfig`, or per-object `clipId`, `customAreaId`,
  `designPart`, `flipX`, `flipY`, `visible`.
- **And one self-inflicted trap worth naming**, because it cost a debugging
  cycle and looked exactly like a schema error: a `src` copied from truncated
  console output points at a file that does not exist, and produces the same
  opaque 10001. Keep full URLs in variables; never retype them from a log.

## How the capture was made to work

Three failed attempts, all of which printed "recording" and wrote nothing. Worth
knowing, because each failure is silent:

1. **Playwright page handles go stale.** Attaching `page.on("request")` once and
   holding it dies when Chrome swaps the tab's target, exactly as
   `browser_session.login()` already warned. Re-discover targets from Chrome's
   `/json`.
2. **Rebinding only on tab-set change is not enough.** Evan moved editor ->
   pool -> product -> editor inside ONE tab, so the set never changed. Attach a
   CDP session per target with `Network.enable`; it survives in-tab navigation.
3. **`time.sleep()` deafens the sync Playwright API.** Events are dispatched only
   while the caller is inside a Playwright call. The capture loop must wait with
   `page.wait_for_timeout()`. This was the root cause of all three failures and
   is the single most important line in the script.
