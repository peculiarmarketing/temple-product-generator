"""Art close-up images: generate per-temple cards and push them to published
Shopify products as gallery position 2.

  python scripts/art_images.py make --temple "San Antonio"   # card into the temple folder
  python scripts/art_images.py make --all
  python scripts/art_images.py push --temple "San Antonio"   # needs Shopify token in .env
  python scripts/art_images.py push --all

Push is idempotent: it finds each generated product on Shopify by exact title
(existence there means Evan published it), recognizes an already-attached art
image by its alt marker, and otherwise uploads the card and moves it to
gallery position 2. Unpublished products are reported as waiting.
"""

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import layout
from generate import (PLACE_SUFFIX_RE, TEMPLES_DIR, parent_temple, parent_titles,
                      temple_manifests, title_is_one_off, working_path)

ALT_MARKER = "Temple line art close-up"


def card_path(temple):
    return TEMPLES_DIR / temple / f"{temple} art closeup (auto).png"


def override_path(temple):
    hits = [p for p in (TEMPLES_DIR / temple).glob("*art closeup*.png") if "(auto)" not in p.name]
    return hits[0] if hits else None


def make(temple):
    manifest = json.loads(working_path(temple, "manifest.json").read_text())
    override = override_path(temple)
    if override:
        print(f"{temple}: using Evan's own {override.name}")
        return override
    card = layout.render_art_card(TEMPLES_DIR / temple / manifest["art"]["black"])
    out = card_path(temple)
    card.save(out)
    print(f"{temple}: card rendered -> {out.name}")
    return out


def temples_with_manifests():
    return sorted(temple_manifests())


EXCLUDE_MARKERS = ("copy of", "template", "generator test", "api test", "limited edition")


def temple_tokens():
    """{token: temple folder}. Tokens are folder names plus every manifest
    place token, matched longest-first so Provo City Center beats Provo."""
    tokens = {}
    for temple, mf in temple_manifests().items():
        m = json.loads(mf.read_text())
        for tok in {temple, *m.get("place_tokens", {}).values()}:
            tokens[tok] = temple
    return tokens


def match_temple(title, tokens):
    """Read a product title back to its temple folder.

    The place token is parenthesized at the end of the title ('Essential
    Temple Tee (Provo City Center)'), so this is an exact lookup rather than
    the longest-prefix guess the old '{place} Temple Tee' titles needed. A
    title with no parenthetical is the parent temple's listing."""
    t = title.strip()
    if any(x in t.lower() for x in EXCLUDE_MARKERS) or " Temple" not in t:
        return None
    m = PLACE_SUFFIX_RE.search(t)
    if m:
        return tokens.get(m.group(1).strip())
    return parent_temple() if t in parent_titles() else None


def push_catalog(only_temple=None):
    """Card every temple product on Shopify that is missing one. Scope per
    Evan's rule: ANY temple product, hand-built or generated. Idempotent via
    the alt marker; excludes copies, templates, and test titles."""
    from shopify_client import ShopifyClient
    c = ShopifyClient()
    catalog = c.all_products_with_media()
    tokens = temple_tokens()
    plan, skipped, waiting = [], [], []
    for product in sorted(catalog, key=lambda p: (p["title"], p["id"])):
        title = product["title"]
        temple = match_temple(title, tokens)
        if temple is None:
            if " Temple" in title and not any(x in title.lower() for x in EXCLUDE_MARKERS):
                skipped.append(title)
            continue
        if only_temple and temple != only_temple:
            continue
        if any(a.startswith(ALT_MARKER) for a in product["alts"]):
            continue
        if not product["alts"]:
            # No mockups on the product yet. Position 2 does not exist, so the
            # card would upload and then fail to move. A product can sit
            # empty for minutes while its mockups arrive; wait for it rather
            # than card it now.
            waiting.append(title)
            continue
        plan.append((title, product, temple))
    print(f"catalog: {len(catalog)} products; {len(plan)} missing cards; "
          f"{len(waiting)} waiting on mockups; {len(skipped)} unmatched temple-like titles")
    for title in skipped:
        print(f"  UNMATCHED (no card): {title!r}")
    for title in waiting:
        print(f"  WAITING (no mockups yet, re-run later): {title!r}")
    cards, failed = {}, []
    for title, product, temple in plan:
        # One product's failure must not abandon the rest: this used to raise
        # straight out of the loop and left 51 of 55 products uncarded. Card
        # rendering is inside the guard too, because a temple whose source art
        # is missing raises here and is not the other temples' problem.
        try:
            if temple not in cards:
                cards[temple] = override_path(temple) or \
                    (card_path(temple) if card_path(temple).exists() else make(temple))
            media_id = c.upload_media_image(product["id"], cards[temple], f"{ALT_MARKER} - {temple}")
            c.move_media_to_position(product["id"], media_id, 1)  # gallery position 2
            print(f"  {title!r} <- {temple} card, position 2")
        except Exception as err:
            print(f"  FAILED {title!r}: {err}")
            failed.append(title)
    if failed or waiting:
        print(f"\n{len(plan) - len(failed)} carded, {len(failed)} failed, "
              f"{len(waiting)} waiting on mockups. Re-run to pick them up.")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("command", choices=["make", "push"])
    ap.add_argument("--temple")
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()
    targets = temples_with_manifests() if args.all else [args.temple] if args.temple else None
    if not targets:
        raise SystemExit("Pass --temple NAME or --all")
    if args.command == "make":
        for t in targets:
            make(t)
        return
    push_catalog(only_temple=None if args.all else args.temple)


if __name__ == "__main__":
    main()
