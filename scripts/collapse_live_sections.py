"""Bring live Shopify descriptions up to the current fixed-section rules.

Two operations, both surgical, run in this order on every product in scope:

  SPLICE   sections the pipeline now composes that a live page predates, which
           today means the shared Care Instructions section. Inserted between
           the specs and the founder message: where Evan put it by hand.
  COLLAPSE every section listed in description_html.COLLAPSIBLE_FIXED_HEADINGS
           that is still sitting open on the live page. This is the SAME
           transform new products get, applied to the live HTML instead of to
           the repo's assets, so a backfilled page and a freshly built one carry
           byte-identical markup.

WHY IT SPLICES AND COLLAPSES INSTEAD OF RECOMPOSING. scripts/write_description.py
rebuilds a description from scratch: repo copy plus the product's own temple
facts. That is right for the retiring Printify line, whose descriptions this
pipeline has always owned end to end. It is wrong here. The live Tapstitch-line
pages have drifted from the repo's assets by hand, and published copy is not
retroactively rewritten unless Evan asks (CLAUDE.md). So this makes the smallest
change that can be made and leaves every other byte alone.

WHAT IT TARGETS. Products whose description has both a
<section class="product-details"> and a <section class="product-intro">, which
on 18 Sep 2026 is 133 of 176 products and nothing else. The two line-parent
products are excluded by that rule on their own, because an admin save stripped
their section wrappers and they no longer have one to splice against; the 40
retiring dated-tee drafts are excluded because they never had one. Both
exclusions are Evan's 18 Sep 2026 scope, and both happen to be what the shape
test selects anyway, which is the safest kind of agreement.

The retiring lines are safe from the collapse pass for a second, independent
reason: COLLAPSIBLE_FIXED_HEADINGS matches on heading TEXT, and their intro
sections open with <h3>The Tee</h3> rather than <h3>From the Founder</h3>.

IDEMPOTENT, BOTH WAYS. A description that already carries a care section is not
spliced again, and collapse_fixed_sections() does not match a section that is
already collapsed (its <h3> no longer sits directly after the section tag), so
it fails open and leaves it alone. Re-running after a partial failure resumes
rather than duplicating. The one historical exception is the Albuquerque crew,
where Evan pasted a care block by hand INSIDE the product-details section on
18 Sep 2026: that copy is cut out first so the page ends with one row, not two.

Usage:
  python scripts/collapse_live_sections.py --report-only   # say what would change
  python scripts/collapse_live_sections.py --handle X      # one product
  python scripts/collapse_live_sections.py                 # write (Evan initiates)
"""

import argparse
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import generate
from description_html import COLLAPSIBLE_FIXED_HEADINGS, collapse_fixed_sections
from shopify_client import ShopifyClient

DETAILS_OPEN = '<section class="product-details">'
INTRO_OPEN = '<section class="product-intro">'
CARE_MARKER = 'class="care-instructions"'

# The hand-pasted block on the Albuquerque crew: an <h3>Care Instructions</h3>
# sitting INSIDE the details section, and everything after it up to that
# section's close. Anchored to the details section so it can never reach into
# the founder message or the temple facts below.
_HAND_PASTED_RE = re.compile(
    r'(' + re.escape(DETAILS_OPEN) + r'.*?)\n<h3>Care Instructions</h3>.*?(\n</section>)',
    re.S)


def care_block():
    """The collapsed care row, composed by the same code path new products use."""
    care = (PROJECT_ROOT / generate.CARE_COPY).read_text().strip()
    out = collapse_fixed_sections(care)
    if CARE_MARKER not in out or "<details" not in out:
        raise SystemExit("care copy did not collapse into a row; refusing to write "
                         "an uncollapsed section onto live pages.")
    return out


def rewrite(html, block):
    """This description with care spliced in and the listed sections collapsed,
    or None when there is nothing to do.

    Fails closed, unlike the assembly-time transforms: a live page that does not
    match the expected shape is skipped and reported, never half-edited."""
    if not html or DETAILS_OPEN not in html or INTRO_OPEN not in html:
        return None
    if html.count(INTRO_OPEN) != 1:
        return None
    out, n = _HAND_PASTED_RE.subn(r'\1\2', html)
    if not n and CARE_MARKER in out:
        pass  # care already backfilled; the collapse pass may still have work
    else:
        out = out.replace(INTRO_OPEN, block + "\n" + INTRO_OPEN, 1)
    out = collapse_fixed_sections(out)
    if out == html:
        return None
    # Never let a rewrite drop copy: the only sections that may appear or vanish
    # are the ones this script adds, and no section may be left unbalanced.
    if out.count("<section") != out.count("</section>") or \
            out.count("<details") != out.count("</details>"):
        return None
    return out


def summarize(html, out):
    """What changed, for the report line."""
    did = []
    if CARE_MARKER not in html and CARE_MARKER in out:
        did.append("care spliced")
    if "<h3>Care Instructions</h3>" in html and CARE_MARKER not in html:
        did = ["hand-pasted care replaced"]
    for title in COLLAPSIBLE_FIXED_HEADINGS:
        open_before = f'<h3>{title}</h3>' in html and \
            f'<summary><h3>{title}</h3></summary>' not in html
        if open_before and f'<summary><h3>{title}</h3></summary>' in out:
            did.append(f"{title} collapsed")
    return ", ".join(did) or "changed"


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--report-only", action="store_true", help="print, write nothing")
    ap.add_argument("--handle", help="restrict to one product handle")
    args = ap.parse_args()

    block = care_block()
    shopify = ShopifyClient()
    products, cursor = [], None
    while True:
        data = shopify.gql("""
          query($after: String) { products(first: 50, after: $after) {
            pageInfo { hasNextPage endCursor }
            nodes { id title handle status descriptionHtml } } }""", {"after": cursor})
        page = data["products"]
        products += page["nodes"]
        if not page["pageInfo"]["hasNextPage"]:
            break
        cursor = page["pageInfo"]["endCursor"]

    written = skipped = done = 0
    for product in sorted(products, key=lambda p: p["title"]):
        if args.handle and product["handle"] != args.handle:
            continue
        html = product["descriptionHtml"] or ""
        wanted = rewrite(html, block)
        if wanted is None:
            if DETAILS_OPEN in html and CARE_MARKER in html:
                done += 1
            else:
                skipped += 1
            continue
        what = summarize(html, wanted)
        if args.report_only:
            print(f"  would write  {product['title']}  ({what})")
            written += 1
            continue
        try:
            shopify.update_product(product["id"], descriptionHtml=wanted)
            print(f"  {product['title']}  ({what})")
            written += 1
        except Exception as err:
            print(f"  FAILED {product['title']}: {err}")
    verb = "would write" if args.report_only else "written"
    print(f"\n{written} {verb}, {done} already current, {skipped} out of scope.")


if __name__ == "__main__":
    main()
