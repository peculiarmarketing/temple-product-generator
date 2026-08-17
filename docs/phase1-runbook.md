# Phase 1 Runbook

Purpose: prove the Printify API round-trip per the spec's Phase 1. All commands run from the project root:

```
./.venv.nosync/bin/python scripts/phase1.py <subcommand>
```

Every step saves its raw response into `artifacts/phase1/` and stops loudly on failure.

## Preconditions (Evan)

1. Printify Personal Access Token in `.env`. Scopes: shops.read, catalog.read, products.read, products.write, uploads.read, uploads.write, print_providers.read.
2. Confirm current Shopify plan status (context for step 9).

## Steps

| # | Spec step | Command | Notes |
|---|---|---|---|
| 1 | 1 | `shops` | Asserts shop 23119809 is reachable. Hard stop on 401/403. |
| 2 | 2 | `list-candidates` | Lists CC1717 tee candidates. Evan confirms which product to use as reference. |
| 3 | 3 | `fetch --product-id ID` | Saves the reference product and a structural summary. |
| 4 | 4 | `create-test` | POSTs a copy titled "... API TEST" using only writable keys. Never published. |
| 5 | 5 | `verify` | Structural diff of GET-back vs posted body. Then Evan eyeballs the API TEST product in the Printify editor BEFORE deletion. |
| 6 | 6 | `upload-test` | Base64 SVG upload probe (San Antonio black). Records mime_type and dimensions, then archives the upload. |
| 7 | 7 | `delete-test` | Deletes the test product and confirms it is gone. |
| 8 | 8 | `product-type` | Public storefront JSON check: T-Shirt / Sweatshirt / Hoodie exactly. |
| 9 | 9 | `publish-check` | Evidence-based assessment only. No publish call in Phase 1. |

Then assemble `artifacts/phase1/findings.md` (the gate report) and stop for Evan's gate review.

## Hard stops

401/403 at step 1, scope errors on first write, POST rejected after reasonable debugging, delete failure at step 7 (an API TEST product would remain in the shop), second consecutive 429.

## Record and proceed

Groups flattening on POST, text layer mutation, SVG upload rejection, product_type mismatch, publish uncertainty. Each is recorded in findings.md with its downstream impact.
