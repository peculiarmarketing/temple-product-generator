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
from generate import TEMPLES_DIR

ALT_MARKER = "Temple line art close-up"


def card_path(temple):
    return TEMPLES_DIR / temple / f"{temple} art closeup (auto).png"


def override_path(temple):
    hits = [p for p in (TEMPLES_DIR / temple).glob("*art closeup*.png") if "(auto)" not in p.name]
    return hits[0] if hits else None


def make(temple):
    manifest = json.loads((TEMPLES_DIR / temple / "manifest.json").read_text())
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
    return sorted(p.parent.name for p in TEMPLES_DIR.glob("*/manifest.json"))


EXCLUDE_MARKERS = ("copy of", "template", "generator test", "api test")


def temple_tokens():
    """{token: temple folder}. Tokens are folder names plus every manifest
    place token, matched longest-first so Provo City Center beats Provo."""
    tokens = {}
    for mf in TEMPLES_DIR.glob("*/manifest.json"):
        temple = mf.parent.name
        m = json.loads(mf.read_text())
        for tok in {temple, *m.get("place_tokens", {}).values()}:
            tokens[tok] = temple
    return tokens


def match_temple(title, tokens):
    """Longest place token whose 'Token ...' prefix fits a temple-product
    title. 'Salt Lake City Temple Tee' matches Salt Lake; 'Provo City Center
    Temple Tee' matches Provo City Center, not Provo."""
    t = title.strip()
    if any(x in t.lower() for x in EXCLUDE_MARKERS) or " Temple" not in t:
        return None
    for tok in sorted(tokens, key=len, reverse=True):
        if t.startswith(tok + " "):
            return tokens[tok]
    return None


def push_catalog(only_temple=None):
    """Card every temple product on Shopify that is missing one. Scope per
    Evan's rule: ANY temple product, hand-built or generated. Idempotent via
    the alt marker; excludes copies, templates, and test titles."""
    from shopify_client import ShopifyClient
    c = ShopifyClient()
    catalog = c.all_products_with_media()
    tokens = temple_tokens()
    plan, skipped = [], []
    for title, product in sorted(catalog.items()):
        temple = match_temple(title, tokens)
        if temple is None:
            if " Temple" in title and not any(x in title.lower() for x in EXCLUDE_MARKERS):
                skipped.append(title)
            continue
        if only_temple and temple != only_temple:
            continue
        if any(a.startswith(ALT_MARKER) for a in product["alts"]):
            continue
        plan.append((title, product, temple))
    print(f"catalog: {len(catalog)} products; {len(plan)} missing cards; "
          f"{len(skipped)} unmatched temple-like titles")
    for title in skipped:
        print(f"  UNMATCHED (no card): {title!r}")
    cards = {}
    for title, product, temple in plan:
        if temple not in cards:
            cards[temple] = override_path(temple) or \
                (card_path(temple) if card_path(temple).exists() else make(temple))
        media_id = c.upload_media_image(product["id"], cards[temple], f"{ALT_MARKER} - {temple}")
        c.move_media_to_position(product["id"], media_id, 1)  # gallery position 2
        print(f"  {title!r} <- {temple} card, position 2")


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
