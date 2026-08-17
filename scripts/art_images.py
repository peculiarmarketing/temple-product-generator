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


def push(temple):
    from shopify_client import ShopifyClient, ShopifyError
    c = ShopifyClient()
    status_path = TEMPLES_DIR / temple / "status.json"
    if not status_path.exists():
        print(f"{temple}: no generated products, skipping")
        return
    titles = [r["title"] for r in json.loads(status_path.read_text()).get("results", []) if r.get("title")]
    png = override_path(temple) or (card_path(temple) if card_path(temple).exists() else make(temple))
    for title in titles:
        product = c.find_product_by_title(title)
        if product is None:
            print(f"  {title!r}: not on Shopify yet (unpublished), waiting")
            continue
        if any((m.get("alt") or "").startswith(ALT_MARKER) for m in product["media"]["nodes"]):
            print(f"  {title!r}: art image already present")
            continue
        alt = f"{ALT_MARKER} - {temple}"
        media_id = c.upload_media_image(product["id"], png, alt)
        c.move_media_to_position(product["id"], media_id, 1)  # gallery position 2
        print(f"  {title!r}: art image uploaded and moved to position 2")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("command", choices=["make", "push"])
    ap.add_argument("--temple")
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()
    targets = temples_with_manifests() if args.all else [args.temple] if args.temple else None
    if not targets:
        raise SystemExit("Pass --temple NAME or --all")
    for t in targets:
        make(t) if args.command == "make" else push(t)


if __name__ == "__main__":
    main()
