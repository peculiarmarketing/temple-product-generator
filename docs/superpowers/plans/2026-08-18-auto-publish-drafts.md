# Auto-Publish Drafts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Auto-publish never-published Printify drafts to Shopify via the API, skipping personalizable (With Date) products, which stay manual.

**Architecture:** One new script, `scripts/publish_drafts.py`, following the repo's existing script conventions (load_config, PrintifyClient, print-based reporting, --report-only flag). Discovery filters the full product list down to safe candidates with a pure `eligibility()` function; publishing POSTs the seven all-true sync flags and polls until Printify populates `external` (the Shopify product id and handle). The workflow docs and skill then make this the standard post-sweep step.

**Tech Stack:** Python 3.12 (project venv at `.venv.nosync`), existing `printify_client.PrintifyClient`, Printify API v1, Shopify Admin API (verification only).

**Spec:** No separate spec doc. Requirements settled in the 18 Aug 2026 session with Evan, summarized here:

- Auto-publish all generated drafts EXCEPT personalizable/dated products (With Date line stays manual because Evan must re-add the date text layer first).
- The publish API accepts only seven sync-flag booleans (`title`, `description`, `images`, `variants`, `tags`, `keyFeatures`, `shipping_template`). All true for first-time publishes.
- Economy + Standard shipping is NOT API-settable (`is_economy_shipping_enabled` is read-only) but every product already inherits Economy enabled from its UI duplicate. The script verifies the flag and refuses to publish without it.
- Variant visibility (only show in-stock) is NOT API-settable or readable. It is a per-product Publishing settings choice in the Printify UI that rides the duplicate. Nothing to automate; noted in docs.
- Shop 23119809 is `sales_channel: "shopify"`, so API publish triggers Printify's own push to Shopify. First live publish doubles as the proof.
- Current eligible drafts: Brigham City Temple Tee (6a846399ec758ee59b0cff5f), Sweatshirt (6a84639996b4b7f9c10058c3), Hoodie (6a846399083625d2f909f046). Brigham City Temple Tee - With Date (6a84639bd5ded88aa1075c8c) must be excluded.

## Global Constraints

- No em dashes in anything Evan-facing (script output, docs, commit messages).
- Never publish a With Date / personalizable product via API, under any flag.
- Never print or commit the Printify or Shopify tokens (`.env` is gitignored).
- Write nothing outside `Claude Projects/` and `../Temples/`. Never touch Lease End files.
- Publish rate limit is 200 per 30 minutes (irrelevant at this scale, but no retry loops on publish).
- Repo commits push to Evan's personal GitHub via the `github-peculiar` SSH alias (the repo's configured origin).
- All commands run from the repo root with `./.venv.nosync/bin/python`.

---

### Task 1: publish_drafts.py with tested eligibility filter

**Files:**
- Create: `scripts/publish_drafts.py`
- Create: `tests/test_publish_drafts.py`

**Interfaces:**
- Consumes: `printify_client.load_config() -> (token, shop_id)`, `printify_client.PrintifyClient(token, shop_id)` with `_request(method, path, json=None)`.
- Produces: `eligibility(product: dict) -> tuple[bool, str]` (imported by the test), CLI `publish_drafts.py [--report-only] [--only SUBSTRING]`.

- [ ] **Step 1: Write the failing test**

```python
"""Offline tests for the publish eligibility filter. No network.

Run: ./.venv.nosync/bin/python tests/test_publish_drafts.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.publish_drafts import eligibility


def base_product(**overrides):
    p = {
        "title": "Logan Temple Tee",
        "external": None,
        "is_locked": False,
        "is_economy_shipping_enabled": True,
        "description": 'intro <section class="temple-facts">facts</section>',
        "sales_channel_properties": {"personalisation": {"strategy": "pstudio"}},
    }
    p.update(overrides)
    return p


def check(name, product, want_ok, want_reason_part):
    ok, reason = eligibility(product)
    assert ok == want_ok, f"{name}: expected ok={want_ok}, got {ok} ({reason})"
    assert want_reason_part in reason, f"{name}: expected reason with '{want_reason_part}', got '{reason}'"


check("clean draft", base_product(), True, "eligible")
check("already published", base_product(external={"id": "1", "handle": "x"}), False, "already published")
check("locked", base_product(is_locked=True), False, "locked")
check("unclaimed duplicate", base_product(title="Copy of Logan Temple Tee"), False, "unclaimed duplicate")
check("front logo test product", base_product(title="Nauvoo Temple Tee (front logo)"), False, "test product")
check("dated by title", base_product(title="Logan Temple Tee - With Date"), False, "dated")
check(
    "personalizable by layers",
    base_product(
        sales_channel_properties={
            "personalisation": {"layers": [{"personalisation_id": "text"}], "strategy": "pstudio"}
        }
    ),
    False,
    "personalizable",
)
check("missing facts section", base_product(description="just an intro"), False, "temple facts")
check("no description at all", base_product(description=None), False, "temple facts")
check("economy off", base_product(is_economy_shipping_enabled=False), False, "economy")
check("scp missing entirely", base_product(sales_channel_properties=None), True, "eligible")

print("all tests passed")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv.nosync/bin/python tests/test_publish_drafts.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.publish_drafts'` (the script does not exist yet). Note: `scripts/` has no `__init__.py`; if the import fails for that reason instead, add `scripts/__init__.py` is NOT the fix, use the same sys.path pattern the repo uses. The import line above works because `scripts` is a plain directory under the repo root and Python 3 treats it as a namespace package.

- [ ] **Step 3: Write the implementation**

```python
"""Publish eligible Printify drafts to the Shopify store via the API.

  python scripts/publish_drafts.py --report-only   # list what would publish and why
  python scripts/publish_drafts.py                 # publish everything eligible
  python scripts/publish_drafts.py --only "Brigham City Temple Tee"

Auto-publishes never-published products EXCEPT personalizable ones (the
With Date line): Evan re-adds the date text layer by hand, so those keep
the manual publish flow. Safety gates: a draft must carry the temple-facts
description section (proof the pipeline finished it) and Economy shipping
(inherited from its UI duplicate; read-only via API so it can only be
verified, not set). Publish settings the API cannot touch (mockup choices,
variant visibility, shipping options) ride the duplicate, so what the donor
product had is what goes live.
"""

import argparse
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from printify_client import PrintifyClient, PrintifyError, load_config

PUBLISH_FLAGS = {
    "title": True,
    "description": True,
    "images": True,
    "variants": True,
    "tags": True,
    "keyFeatures": True,
    "shipping_template": True,
}

POLL_INTERVAL_S = 5
POLL_TIMEOUT_S = 240


def eligibility(product):
    """(ok, reason) for auto-publishing one product dict from the API."""
    title = product.get("title", "")
    if product.get("external"):
        return False, "already published"
    if product.get("is_locked"):
        return False, "locked, a publish is already in progress"
    if title.startswith("Copy of"):
        return False, "unclaimed duplicate"
    if "(front logo)" in title.lower():
        return False, "test product"
    if "With Date" in title:
        return False, "dated product, Evan publishes by hand"
    personalisation = (product.get("sales_channel_properties") or {}).get("personalisation") or {}
    if personalisation.get("layers"):
        return False, "personalizable, Evan publishes by hand"
    if 'class="temple-facts"' not in (product.get("description") or ""):
        return False, "description has no temple facts section yet"
    if not product.get("is_economy_shipping_enabled"):
        return False, "economy shipping is off, fix the duplicate source in the Printify UI"
    return True, "eligible"


def all_products(client):
    products, page = [], 1
    while True:
        data = client._request("GET", f"/shops/{client.shop_id}/products.json?limit=50&page={page}")
        products.extend(data["data"])
        if not data.get("next_page_url"):
            break
        page += 1
    return products


def publish_one(client, product):
    pid = product["id"]
    client._request("POST", f"/shops/{client.shop_id}/products/{pid}/publish.json", json=PUBLISH_FLAGS)
    deadline = time.time() + POLL_TIMEOUT_S
    while time.time() < deadline:
        time.sleep(POLL_INTERVAL_S)
        fresh = client._request("GET", f"/shops/{client.shop_id}/products/{pid}.json")
        external = fresh.get("external")
        if external and not fresh.get("is_locked"):
            return external
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-only", action="store_true", help="list candidates, publish nothing")
    parser.add_argument("--only", help="restrict to products whose title contains this text")
    args = parser.parse_args()

    token, shop_id = load_config()
    client = PrintifyClient(token, shop_id)

    unpublished = [p for p in all_products(client) if not p.get("external")]
    if args.only:
        unpublished = [p for p in unpublished if args.only.lower() in p["title"].lower()]
    if not unpublished:
        print("No unpublished drafts found.")
        return

    to_publish = []
    for summary in unpublished:
        # The list endpoint trims some fields; judge from the full product.
        product = client._request("GET", f"/shops/{client.shop_id}/products/{summary['id']}.json")
        ok, reason = eligibility(product)
        marker = "PUBLISH" if ok else "skip"
        print(f"{marker:7}  {product['title']}  ({reason})")
        if ok:
            to_publish.append(product)

    if args.report_only:
        print(f"\nReport only. {len(to_publish)} draft(s) would be published.")
        return
    if not to_publish:
        print("\nNothing eligible to publish.")
        return

    failures = 0
    for product in to_publish:
        print(f"\nPublishing {product['title']} ...")
        try:
            external = publish_one(client, product)
        except PrintifyError as err:
            print(f"  FAILED: {err}")
            failures += 1
            continue
        if external:
            print(f"  Live on Shopify: handle {external.get('handle')} (id {external.get('id')})")
        else:
            print(f"  TIMED OUT after {POLL_TIMEOUT_S}s: Printify accepted the publish but has not "
                  "confirmed it. Check the product in Printify before retrying.")
            failures += 1

    if failures:
        sys.exit(f"\n{failures} publish(es) did not complete.")
    print(f"\nDone. {len(to_publish)} product(s) published.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv.nosync/bin/python tests/test_publish_drafts.py`
Expected: `all tests passed`

- [ ] **Step 5: Commit**

```bash
git add scripts/publish_drafts.py tests/test_publish_drafts.py
git commit -m "feat: auto-publish eligible drafts via API, dated products stay manual"
```

### Task 2: Live report-only dry run (read-only)

**Files:** none (verification only)

**Interfaces:**
- Consumes: `publish_drafts.py --report-only` CLI from Task 1.
- Produces: confirmed candidate list for Tasks 3 and 4.

- [ ] **Step 1: Run the report**

Run: `./.venv.nosync/bin/python scripts/publish_drafts.py --report-only`

Expected output lines, exactly these four products:
- `PUBLISH  Brigham City Temple Tee  (eligible)`
- `PUBLISH  Brigham City Temple Sweatshirt  (eligible)`
- `PUBLISH  Brigham City Temple Hoodie  (eligible)`
- `skip     Brigham City Temple Tee - With Date  (dated product, Evan publishes by hand)`
- `Report only. 3 draft(s) would be published.`

- [ ] **Step 2: Stop rule**

If ANY other product shows as PUBLISH, or the With Date draft is not skipped, stop and investigate before Task 3. The filter is wrong, not the data.

### Task 3: Single test publish (first live store write)

**Files:** none (runs the Task 1 script)

**Interfaces:**
- Consumes: `publish_drafts.py --only "Brigham City Temple Tee"` (matches the base tee AND the With Date tee; eligibility skips the dated one, which also proves the guard on a live run).
- Produces: a live Shopify product with an external handle, proving API publish carries the duplicate's settings.

- [ ] **Step 1: Publish the test product**

Run: `./.venv.nosync/bin/python scripts/publish_drafts.py --only "Brigham City Temple Tee"`
Expected: base tee publishes and prints a Shopify handle; With Date tee prints as skipped.

- [ ] **Step 2: Verify on Shopify (read-only Admin API)**

Run this check from the repo root:

```bash
./.venv.nosync/bin/python - <<'EOF'
import json
from pathlib import Path
from dotenv import dotenv_values
import requests

env = dotenv_values(Path(".env"))
domain, token = env["SHOPIFY_STORE_DOMAIN"], env["SHOPIFY_ADMIN_TOKEN"]

import printify_client as pc
client = pc.PrintifyClient(*pc.load_config())
prod = client._request("GET", f"/shops/{client.shop_id}/products/6a846399ec758ee59b0cff5f.json")
ext = prod["external"]
resp = requests.get(
    f"https://{domain}/admin/api/2024-01/products/{ext['id']}.json",
    headers={"X-Shopify-Access-Token": token},
)
resp.raise_for_status()
sp = resp.json()["product"]
print("status:", sp["status"])
print("variants:", len(sp["variants"]), "(printify enabled: ",
      sum(1 for v in prod["variants"] if v["is_enabled"]), ")")
print("images:", len(sp["images"]))
print("has facts section:", "temple-facts" in (sp["body_html"] or ""))
EOF
```

Expected: `status: active`, Shopify variant count equals Printify enabled count (52), images > 0, facts section true.

If `status` is `draft`, Printify's store connection is set to publish as hidden. Report this to Evan (he flips the Printify store setting or accepts drafts) before Task 4. If variant or image counts are off, explain the mechanism before touching anything.

- [ ] **Step 3: Report the result in chat before continuing**

One short summary: handle, status, variant count, image count. Continue only if all checks passed.

### Task 4: Publish the remaining eligible drafts

**Files:** none

**Interfaces:**
- Consumes: `publish_drafts.py` full run.
- Produces: all eligible drafts live.

- [ ] **Step 1: Full publish run**

Run: `./.venv.nosync/bin/python scripts/publish_drafts.py`
Expected: tee now reports `already published`; sweatshirt and hoodie publish with handles; With Date skipped.

- [ ] **Step 2: Spot-check both on Shopify**

Same check as Task 3 Step 2 but for product ids `6a84639996b4b7f9c10058c3` (sweatshirt) and `6a846399083625d2f909f046` (hoodie). Expected: active, variant counts match, images present.

### Task 5: Post-publish housekeeping (established pipeline steps)

**Files:**
- Modify (by the scripts themselves): `../Temples/Brigham City/` card render, `artifacts/easify/option-sets.csv`

**Interfaces:**
- Consumes: `scripts/art_images.py push --all`, `scripts/easify_options.py sync`.
- Produces: art close-up cards on the three new Shopify products, updated Easify CSV for Evan's manual import.

- [ ] **Step 1: Art cards**

Run: `./.venv.nosync/bin/python scripts/art_images.py push --all`
Expected: the three new Brigham City products get cards at gallery position 2; everything else reports as already carded.

- [ ] **Step 2: Easify dropdown sync**

Run: `./.venv.nosync/bin/python scripts/easify_options.py sync`
Expected: Brigham City rows added alphabetically to the Tee, Sweatshirt, and Hoodie sets; CSV rewritten. Tell Evan the CSV is ready for his manual Easify import.

### Task 6: Docs, decision record, and workflow wiring

**Files:**
- Modify: `docs/decisions.md` (append a dated entry)
- Modify: `../.claude/skills/temple-product-generator/SKILL.md` (workflow steps 4 and 5, commands table)

**Interfaces:**
- Consumes: outcomes of Tasks 2 to 5.
- Produces: the new publish step as the documented standard workflow.

- [ ] **Step 1: decisions.md entry**

Append under a new heading `## 18 August 2026 (auto-publish)`:

```markdown
- **Base products auto-publish via API; dated products stay manual.** Evan reversed the "publishing stays manual" decision for non-personalizable products. `scripts/publish_drafts.py` publishes never-published drafts that pass the gates: not "Copy of", not "(front logo)", not With Date or personalizable (layers in sales_channel_properties), description carries the temple-facts section, Economy shipping enabled. With Date products keep the manual flow because Evan must re-add the date text layer first.
- **The publish API is sync flags only.** POST publish.json accepts seven booleans (title, description, images, variants, tags, keyFeatures, shipping_template), all true for first-time publishes. Shipping options and variant visibility are not API-settable; they ride the UI duplicate. `is_economy_shipping_enabled` is read-only and verified as a publish gate. Variant visibility ("only show in stock variants") is a per-product Publishing settings choice in the Printify UI; not readable or writable via API.
- **Verified live on Brigham City (18 Aug 2026):** [fill in after Task 4: handles, active status, variant counts].
```

- [ ] **Step 2: SKILL.md updates**

In the commands table add:

```markdown
| Publish eligible drafts (skips dated) | `scripts/publish_drafts.py` (`--report-only` to preview) |
```

Rewrite workflow step 4 to:

```markdown
4. Run `scripts/publish_drafts.py`: base-garment drafts publish to Shopify automatically (gates: temple-facts description present, Economy shipping on, not personalizable). Evan then re-adds the personalization text layer on dated products and publishes THOSE by hand, and retires old products when a draft was a `--replace`ment.
```

And workflow step 5 to:

```markdown
5. Dated (With Date) products are never published via API. Base products auto-publish via `publish_drafts.py` since 18 Aug 2026; the Shopify listing goes live immediately, so run it only when Evan has said to publish (a sweep request implies it).
```

In "After every run", add `scripts/publish_drafts.py` before the art push in the listed sequence (publish, then art cards, then Easify sync).

- [ ] **Step 3: Commit and push**

```bash
git add docs/decisions.md docs/superpowers/plans/2026-08-18-auto-publish-drafts.md
git commit -m "docs: record auto-publish decision and verified results"
git push
```

(SKILL.md lives outside the repo; no commit for it.)

- [ ] **Step 4: Update memory**

Update the `temple-product-generator` memory file: publishing is no longer fully manual; base products auto-publish via `scripts/publish_drafts.py`; With Date stays manual; note the settled API facts (publish body is seven sync flags, economy read-only, variant visibility UI-only).

## Self-Review

- Spec coverage: auto-publish with dated exclusion (Tasks 1 to 4), settings questions answered and recorded (Task 6), duplicate-carried settings verified live (Task 3). Covered.
- Placeholder scan: Task 6 Step 1 has one deliberate fill-in for live results, completed during execution, not left as TBD in the final commit.
- Type consistency: `eligibility` returns `(bool, str)` everywhere; `load_config() -> (token, shop_id)` matches printify_client.py:154.
