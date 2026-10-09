"""Rebuild the Salt Lake temple hoodie and sweatshirt descriptions.

An old save in the Shopify admin editor rewrote both in the editor's own markup
(ql-ui spans, no <section> wrappers), which dropped every collapsible row: care,
founder and temple facts all render open as flat text. collapse_live_sections.py
selects its targets by those wrappers, so it skips these two by design
(docs/decisions.md, 18 Sep 2026).

This composes each description the way every other temple product gets it
(generate.fixed_description + compose_description over the stored Salt Lake
facts) and writes it only when the visible words are identical to what is live,
so the change is structure and nothing else. The live HTML is backed up first.

Usage:
  python scripts/rebuild_parent_descriptions.py            # report only
  python scripts/rebuild_parent_descriptions.py --apply    # write (Evan initiates)
"""

import argparse
import difflib
import html
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import generate
from description_html import compose_description
from shopify_client import ShopifyClient

FACTS = PROJECT_ROOT / "artifacts/temple-facts/Salt Lake.html"
BACKUP_DIR = PROJECT_ROOT / "artifacts/descriptions/backup-2026-10-08"
TARGETS = {"cloud-temple-hoodie": "hoodie", "salt-lake-temple-sweatshirt": "crew"}


def visible_words(markup):
    """What a shopper reads: styles and tags dropped, entities decoded. The
    <time> tags in the facts split a date from its comma, so whitespace before
    punctuation is closed up to compare like with like."""
    text = re.sub(r"<style.*?</style>", " ", markup, flags=re.S)
    text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    return re.sub(r"\s+([,.;:])", r"\1", text).split()


def live_description(client, handle):
    data = client.gql("""query($h: String!) {
        productByHandle(handle: $h) { id descriptionHtml } }""", {"h": handle})
    return data["productByHandle"]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="write to the live store")
    args = ap.parse_args()

    facts = FACTS.read_text().strip()
    client = ShopifyClient()
    failed = False
    for handle, garment_id in TARGETS.items():
        new = compose_description(generate.fixed_description(
            generate.load_garment_config(garment_id)), facts)
        product = live_description(client, handle)
        live = product["descriptionHtml"]
        old_words, new_words = visible_words(live), visible_words(new)
        # Shopify reformats HTML on save, so a byte compare never matches again.
        if old_words == new_words and live.count("<details") == new.count("<details") \
                and "ql-ui" not in live:
            print(f"{handle}: already current")
            continue
        if old_words != new_words:
            failed = True
            print(f"{handle}: REFUSED, visible text would change:")
            for line in difflib.unified_diff(old_words, new_words, lineterm="", n=2):
                print("   ", line)
            continue
        rows = new.count("<details")
        print(f"{handle}: {len(new_words)} words unchanged, {rows} collapsible rows")
        if not args.apply:
            continue
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        (BACKUP_DIR / f"{handle}.html").write_text(live)
        client.update_product(product["id"], descriptionHtml=new)
        back = live_description(client, handle)["descriptionHtml"]
        if visible_words(back) != new_words or back.count("<details") != rows:
            raise SystemExit(f"{handle}: read-back does not match what was sent")
        print(f"  written and read back; backup in {BACKUP_DIR.relative_to(PROJECT_ROOT)}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
