"""Swap the old founder note for the new one on live product descriptions.

Evan, 10 Oct 2026: every product carries the founders' note from the homepage
spec section ("You wear Peculiar People because..."), signed by Evan and
Bailee, in place of the old "You put on a Peculiar People shirt..." note.
The stored copy (reference/garment-copy/{tee,crew,hoodie}/product-intro.html)
already holds the new note, so every product built from here gets it. This
brings the live pages into line.

SURGICAL. Only the collapsed founder row is replaced:

    <details class="product-intro__block"><summary><h3>From the Founder</h3></summary>
    ...old note...
    </details>

and only when its words are one of the three known garment wordings of the
OLD generic note (shirt / sweatshirt / hoodie). The bomber and the Be Peculiar
lines carry their own notes and never match, so they are left alone, as is
every byte outside that row. The replacement is built by the same
collapse_fixed_sections() transform new products get, so a swapped page and a
freshly built one carry identical markup.

Works offline on a bulk export (JSONL of {id, handle, title, descriptionHtml}),
because the cloud session has no API token; the writes go out as a
productUpdate bulk mutation built from --out.

Usage:
  python scripts/founder_note_rollout.py EXPORT.jsonl                # report
  python scripts/founder_note_rollout.py EXPORT.jsonl --out UPD.jsonl
"""

import argparse
import html
import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from description_html import collapse_fixed_sections

NEW_INTRO = PROJECT_ROOT / "reference/garment-copy/tee/product-intro.html"

OLD_ROW_RE = re.compile(
    r'<details class="product-intro__block"><summary><h3>From the Founders?</h3>'
    r'</summary>\n?(.*?)\n?</details>', re.S)
NEW_ROW_RE = re.compile(
    r'<details class="product-intro__block">.*?</details>', re.S)


def words(markup):
    text = html.unescape(re.sub(r"<[^>]+>", " ", markup))
    return " ".join(text.replace("\xa0", " ").split())


OLD_NOTE = (
    "You put on a Peculiar People {g} because it reminds you why we're all here. "
    "Because that building is where you were sealed to your spouse, where you got "
    "an answer to a prayer you'd been carrying for years, where you first felt "
    "something you couldn't explain away. A stepping stone. A day you'll never "
    "forget. You put it on because you want to share that with someone. Because "
    "gospel conversations are hard to start. Harder than they were on your "
    "mission, when the whole day was built around them. It's the new white shirt "
    "and tie. The new dress. The new name tag you don't need a calling to wear. "
    "A {g} you may even feel prompted to wear some days. That's why I started "
    "this company. It doesn't take much for someone who has been prepared to tap "
    "you on the shoulder and ask a question that changes the direction of their "
    "life. No argument, no pitch, no lesson plan. Just an opening. - Evan")
OLD_NOTES = {OLD_NOTE.format(g=g) for g in ("shirt", "sweatshirt", "hoodie")}


def new_row():
    collapsed = collapse_fixed_sections(NEW_INTRO.read_text().strip())
    return NEW_ROW_RE.search(collapsed).group(0)


def swap(desc, row):
    """(new_html, status). Status is 'swap', 'done', 'other-note' or 'no-row'."""
    m = OLD_ROW_RE.search(desc or "")
    if not m:
        return desc, "no-row"
    if m.group(0) == row:
        return desc, "done"
    if words(m.group(1)) not in OLD_NOTES:
        return desc, "other-note"
    return desc[:m.start()] + row + desc[m.end():], "swap"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("export")
    ap.add_argument("--out")
    args = ap.parse_args()
    row = new_row()
    updates, seen = [], {}
    for line in Path(args.export).read_text().splitlines():
        p = json.loads(line)
        out, status = swap(p["descriptionHtml"], row)
        seen.setdefault(status, []).append(p["handle"])
        if status == "swap":
            assert out.count("product-intro__block") == 1, p["handle"]
            updates.append({"product": {"id": p["id"], "descriptionHtml": out}})
    for status, handles in sorted(seen.items()):
        print(f"{status}: {len(handles)}")
        if status != "swap":
            for h in handles:
                print(f"  {h}")
    if args.out:
        Path(args.out).write_text("".join(json.dumps(u) + "\n" for u in updates))
        print(f"wrote {len(updates)} updates to {args.out}")


if __name__ == "__main__":
    main()
