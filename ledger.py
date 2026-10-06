"""The Tapstitch migration ledger: what is built, what is live, what is stuck.

One row per temple per garment. The migration recreates roughly 140 products
through a web editor, which is slow and will be done across many sessions, so
the run has to be able to lose its place and find it again.

`old_shopify_handle` records the address each row's old listing had, which
was captured by the pull-down snapshot while the old catalogue was still intact
and cannot be reliably read afterwards.

It is no longer an address the replacement takes over. That was the 14 Sep 2026
plan, retired on 16 Sep (Evan, asked and confirmed) once it turned out not to
work: Shopify builds a new product's address from its title and ignores whatever
address a deletion just freed. Replacements now take their own address, old
listings stay DRAFT, and the Easify dropdown links are repointed by
scripts/easify_options.py sync. The field is kept because it is the only record
of what each product used to be reachable at.
"""

import json
from datetime import datetime
from pathlib import Path

from layout import PROJECT_ROOT

LEDGER_PATH = PROJECT_ROOT / "artifacts" / "tapstitch" / "ledger.json"
LEDGER_MD = PROJECT_ROOT / "artifacts" / "tapstitch" / "LEDGER.md"

# Ordered worst to best. A build pass may only move a row within the BUILD
# states; once a product exists in Tapstitch, the build no longer owns the
# row's state and re-running the build must not walk it backwards.
STATES = ["art-missing", "error", "art-ok", "file-built", "file-approved",
          "product-created", "description-written", "card-pushed", "live"]
BUILD_STATES = {"art-missing", "error", "art-ok", "file-built"}
# art-ok and file-built differ on one thing only: whether a PNG is on disk. A
# report-only sweep can prove a design validates without writing 240 files into
# Evan's iCloud folders, and recording that as "file-built" would be a lie the
# publish step would later trip over.


def _key(row):
    return (row["temple"], row["garment"])


def load():
    if not LEDGER_PATH.exists():
        return {"rows": []}
    return json.loads(LEDGER_PATH.read_text())


def save(data):
    data["updated_at"] = datetime.now().isoformat(timespec="seconds")
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    LEDGER_PATH.write_text(json.dumps(data, indent=2) + "\n")
    write_markdown(data)


def blank_row(temple, garment):
    return {"temple": temple, "garment": garment, "state": "art-missing",
            "files": {}, "problems": [],
            "old_shopify_handle": None, "old_shopify_id": None, "old_title": None,
            "tapstitch_product_url": None, "shopify_handle": None,
            "updated_at": None}


def upsert_build(data, temple, garment, state, files, problems):
    """Record a build result without ever walking a downstream row backwards.

    A row that has already reached product-created or beyond keeps its state:
    rebuilding a print file does not un-publish a product. Files and problems
    are always refreshed, because they describe what is on disk right now.
    """
    rows = {_key(r): r for r in data["rows"]}
    row = rows.get((temple, garment)) or blank_row(temple, garment)
    row["files"] = files
    row["problems"] = problems
    if row["state"] in BUILD_STATES:
        row["state"] = state
    row["updated_at"] = datetime.now().isoformat(timespec="seconds")
    rows[(temple, garment)] = row
    data["rows"] = [rows[k] for k in sorted(rows)]
    return row


def set_state(data, temple, garment, state, **fields):
    rows = {_key(r): r for r in data["rows"]}
    row = rows.get((temple, garment)) or blank_row(temple, garment)
    row["state"] = state
    row.update(fields)
    row["updated_at"] = datetime.now().isoformat(timespec="seconds")
    rows[(temple, garment)] = row
    data["rows"] = [rows[k] for k in sorted(rows)]
    return row


def counts(data):
    out = {s: 0 for s in STATES}
    for r in data["rows"]:
        out[r["state"]] = out.get(r["state"], 0) + 1
    return out


def write_markdown(data):
    c = counts(data)
    lines = ["# Tapstitch migration ledger", "",
             f"Updated {data.get('updated_at', 'never')}. "
             f"{len(data['rows'])} rows.", "",
             "| State | Count |", "|---|---|"]
    lines += [f"| {s} | {c[s]} |" for s in STATES if c.get(s)]
    lines += ["", "| Temple | Garment | State | Old web address | Problems |",
              "|---|---|---|---|---|"]
    for r in data["rows"]:
        probs = "; ".join(r["problems"]) if r["problems"] else ""
        lines.append(f"| {r['temple']} | {r['garment']} | {r['state']} | "
                     f"{r['old_shopify_handle'] or ''} | {probs} |")
    LEDGER_MD.parent.mkdir(parents=True, exist_ok=True)
    LEDGER_MD.write_text("\n".join(lines) + "\n")
