"""Sync the Easify temple dropdown option sets with the live Shopify catalog.

The canonical option-sets CSV lives at artifacts/easify/option-sets.csv and is
what Evan imports into the Easify app. This script reads the live catalog,
verifies every option value's label and URL against the real product handles,
adds temples whose products Evan has published, creates configured sets that
do not exist yet (cloned from an existing set), and rewrites the CSV only when
something actually changed. Importing into Easify stays manual, like publishing.

  python scripts/easify_options.py sync                  # verify, fix, add
  python scripts/easify_options.py sync --report-only    # print, write nothing
  python scripts/easify_options.py reseed --export PATH  # adopt a fresh Easify
                                                         # export as canonical
                                                         # (one-time, after an
                                                         # import created a set)

Reconciliation is keyed by temple label: the label decides which temple a row
means, and the URL follows the label. Rows are never deleted, only fixed,
added, or reported.
"""

import argparse
import csv
import datetime
import difflib
import io
import json
import shutil
import sys
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from art_images import EXCLUDE_MARKERS, temple_tokens
from shopify_client import ShopifyClient

CANONICAL = PROJECT_ROOT / "artifacts" / "easify" / "option-sets.csv"
SETS_CONFIG = PROJECT_ROOT / "artifacts" / "easify" / "sets.json"
GARMENTS_DIR = PROJECT_ROOT / "garments"
STORE = "https://peculiarpeopleco.com/products/"
BROWSE_LABEL = "Browse other temples"
PLACEHOLDER_SET_ID_BASE = 900001

# Columns whose cells hold JSON; compared as parsed objects so re-quoting
# noise can never register as a change.
JSON_COLUMNS = (
    "customer_tag", "product_condition", "option_set_products", "additional_data",
    "metadata", "live_preview_transform", "quantity_selector",
    "conditions_serialized", "date_time_values", "one_time_charge", "metadata_type",
)


def load_config():
    return json.loads(SETS_CONFIG.read_text())["sets"]


def load_canonical(path=CANONICAL):
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)
    for i, row in enumerate(rows, start=2):
        if None in row or any(v is None for v in row.values()):
            raise SystemExit(f"{Path(path).name} line {i}: field count differs from header")
    return fieldnames, rows


def group_by_set(rows):
    grouped = {}
    for row in rows:
        grouped.setdefault(row["option_set_title"], []).append(row)
    return grouped


def garment_title_pattern(garment_id):
    cfg = json.loads((GARMENTS_DIR / f"{garment_id}.json").read_text())
    return cfg["naming"]["title"]


def parse_products(cell):
    return [d["handle"] for d in json.loads(cell)] if cell else []


def products_cell(handles):
    return json.dumps([{"handle": h} for h in sorted(handles)], separators=(",", ":"))


def value_url(row):
    try:
        return (json.loads(row["metadata_type"]) or {}).get("url") or ""
    except (json.JSONDecodeError, AttributeError):
        return ""


def set_url(row, url):
    try:
        meta = json.loads(row["metadata_type"]) or {}
    except json.JSONDecodeError:
        meta = {}
    meta["url"] = url
    meta.setdefault("disabled", None)
    row["metadata_type"] = json.dumps(meta, separators=(",", ":"))


def handle_of(url):
    return url[len(STORE):] if url.startswith(STORE) else None


def live_temple_products(config, tokens):
    """Match live Shopify products to configured garments by exact title.

    Exact equality against the garment naming pattern is what keeps variants
    like '(front logo)' or '- Limited Edition' out of the dropdowns.
    Returns ({garment: {temple: (label, handle)}}, attention lines)."""
    client = ShopifyClient()
    live = [p for p in client.all_products_summary()
            if p["status"] == "ACTIVE" and p["publishedAt"]]
    expected, attention, matched = {}, [], set()
    for spec in config:
        garment = spec["garment"]
        pattern = garment_title_pattern(garment)
        per_temple = {}
        for token, temple in tokens.items():
            want = pattern.format(place=token)
            for p in live:
                if p["title"].strip() == want:
                    per_temple.setdefault(temple, []).append((token, p["handle"]))
                    matched.add(want)
        chosen = {}
        for temple, hits in sorted(per_temple.items()):
            if len(hits) > 1:
                attention.append(
                    f"{garment}: {len(hits)} live products claim {temple} "
                    f"({', '.join(h for _, h in hits)}); skipped, fix on Shopify first")
                continue
            chosen[temple] = hits[0]
        expected[garment] = chosen
    unmatched = {}
    for p in live:
        t = p["title"].strip()
        if t in matched or " Temple" not in t or any(x in t.lower() for x in EXCLUDE_MARKERS):
            continue
        unmatched[t] = unmatched.get(t, 0) + 1
    for t, n in sorted(unmatched.items()):
        attention.append(f"Live product with no dropdown slot: {t!r}"
                         + (f" (x{n})" if n > 1 else ""))
    return expected, attention


def new_value_row(template, label, url):
    row = dict(template)
    row["option_value_id"] = str(uuid.uuid4())
    row["option_value_label"] = label
    row["option_value_number_color"] = "1"
    row["option_value_is_default"] = "FALSE"
    row["option_value_is_hidden"] = "FALSE"
    row["option_value_image_url"] = ""
    row["option_value_image_id"] = "default_id_image"
    row["swatch_shape"] = "circle"
    row["image_canvas_id"] = ""
    row["image_canvas_url"] = ""
    row["option_value_color_code"] = ""
    row["option_value_add_on_price"] = "0"
    row["product_id"] = ""
    row["variant_id"] = ""
    row["product_handle"] = ""
    row["product_name"] = ""
    row["use_price"] = "FALSE"
    row["is_created"] = "FALSE"
    row["metadata_type"] = json.dumps({"url": url, "disabled": None}, separators=(",", ":"))
    return row


def reconcile_set(title, rows, expected, tokens):
    """Reconcile one existing set against {temple: (label, handle)}.

    Binding is by label first (the label says which temple the row means, so a
    swapped URL gets corrected, not relabeled). Unknown labels are rescued by
    their URL's handle, then by fuzzy match. Rows are never deleted."""
    rows = [dict(r) for r in rows]
    changes, attention = [], []
    default_rows = [r for r in rows if r["option_value_is_default"] == "TRUE"]
    if len(default_rows) != 1:
        raise SystemExit(f"Set {title!r}: expected exactly one default row, found {len(default_rows)}")
    default_row = default_rows[0]
    handle_to_temple = {h: t for t, (_, h) in expected.items()}

    bound, stale = {}, []
    for row in rows:
        if row is default_row:
            continue
        label = row["option_value_label"]
        temple = tokens.get(label)
        if temple is None:
            temple = handle_to_temple.get(handle_of(value_url(row)))
        if temple is None:
            close = difflib.get_close_matches(label, list(tokens), n=1, cutoff=0.8)
            temple = tokens[close[0]] if close else None
        if temple is None:
            attention.append(f"{title}: unknown option {label!r}, left untouched")
            continue
        if temple in bound:
            attention.append(f"{title}: {label!r} duplicates {temple}, left untouched")
            continue
        bound[temple] = row
        if temple not in expected:
            stale.append(row)

    for temple, row in bound.items():
        if temple not in expected:
            continue
        label, handle = expected[temple]
        url = STORE + handle
        old_label, old_url = row["option_value_label"], value_url(row)
        if old_label != label:
            row["option_value_label"] = label
            changes.append(f"Fixed label: {old_label} -> {label}")
        if old_url != url:
            set_url(row, url)
            changes.append(f"Fixed URL for {label}: {handle_of(old_url) or old_url or '(empty)'} -> {handle}")

    out_rows = list(rows)
    template = next((r for r in rows if r is not default_row), default_row)
    for temple, (label, handle) in sorted(expected.items(), key=lambda kv: kv[1][0]):
        if temple in bound:
            continue
        new_row = new_value_row(template, label, STORE + handle)
        idx = len(out_rows)
        for i, r in enumerate(out_rows):
            if r["option_value_is_default"] != "TRUE" and r["option_value_label"] > label:
                idx = i
                break
        out_rows.insert(idx, new_row)
        changes.append(f"Added {label}: {handle}")

    for row in stale:
        attention.append(f"{title}: {row['option_value_label']!r} has no live product on Shopify; kept as is")

    want = sorted(h for _, h in expected.values())
    have = parse_products(default_row["option_set_products"])
    for h in want:
        if h not in have:
            changes.append(f"Now applies to {h}")
    for h in have:
        if h not in want:
            changes.append(f"No longer applies to {h} (product not live)")
    cell = products_cell(want)
    for r in out_rows:
        r["option_set_products"] = cell
    return out_rows, changes, attention


def new_set_rows(spec, clone_rows, expected, set_id):
    """Build a brand-new set, cloned column-for-column from clone_rows.

    Placeholder set id and fresh UUIDs mirror Easify's own import sample,
    which is the evidence that importing an unknown set id creates the set."""
    clone_default = next(r for r in clone_rows if r["option_value_is_default"] == "TRUE")
    clone_value = next(r for r in clone_rows if r["option_value_is_default"] != "TRUE")
    old_unique, old_browse = clone_default["option_id_unique"], clone_default["option_value_id"]
    new_unique, browse_id = str(uuid.uuid4()), str(uuid.uuid4())

    def rebrand(row):
        row = {k: v.replace(old_unique, new_unique).replace(old_browse, browse_id)
               if isinstance(v, str) else v for k, v in row.items()}
        row["option_set_id"] = str(set_id)
        row["option_set_title"] = spec["set_title"]
        row["option_name"] = spec["option_name"]
        row["option_id"] = ""
        row["option_id_unique"] = new_unique
        row["default_value"] = browse_id
        return row

    rows = [rebrand(dict(clone_default))]
    rows[0]["option_value_id"] = browse_id
    for label, handle in sorted(expected.values()):
        rows.append(rebrand(new_value_row(clone_value, label, STORE + handle)))
    cell = products_cell([h for _, h in expected.values()])
    for r in rows:
        r["option_set_products"] = cell
    return rows


def _sem_value(v):
    if not v:
        return v
    try:
        return ("json", json.dumps(json.loads(v), sort_keys=True))
    except (json.JSONDecodeError, TypeError):
        return ("str", v)


def semantically_equal(a, b):
    return a.keys() == b.keys() and all(_sem_value(a[k]) == _sem_value(b[k]) for k in a)


def validate_output(fieldnames, out_rows, in_sets, touched, expected_by_title):
    """Serialize, re-parse, and assert structural soundness before any write.
    Returns the exact text to write."""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames, lineterminator="\r\n")
    writer.writeheader()
    writer.writerows(out_rows)
    text = buf.getvalue()

    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames != fieldnames:
        raise SystemExit("Validation failed: header changed on round trip")
    rows2 = list(reader)
    if len(rows2) != len(out_rows):
        raise SystemExit("Validation failed: row count changed on round trip")
    for title, rows in group_by_set(rows2).items():
        defaults = [r for r in rows if r["option_value_is_default"] == "TRUE"]
        if len(defaults) != 1:
            raise SystemExit(f"Validation failed: {title!r} has {len(defaults)} default rows")
        browse_id = defaults[0]["option_value_id"]
        labels = [r["option_value_label"] for r in rows]
        if len(labels) != len(set(labels)):
            raise SystemExit(f"Validation failed: duplicate labels in {title!r}")
        if len({r["option_set_products"] for r in rows}) != 1:
            raise SystemExit(f"Validation failed: option_set_products not uniform in {title!r}")
        for r in rows:
            if r["default_value"] != browse_id:
                raise SystemExit(f"Validation failed: default_value mismatch in {title!r}")
            for col in JSON_COLUMNS:
                if r[col]:
                    try:
                        json.loads(r[col])
                    except json.JSONDecodeError:
                        raise SystemExit(f"Validation failed: {title!r} column {col} is not valid JSON")
        for temple, (label, handle) in expected_by_title.get(title, {}).items():
            hits = [r for r in rows if r["option_value_label"] == label]
            if len(hits) != 1 or value_url(hits[0]) != STORE + handle:
                raise SystemExit(f"Validation failed: {title!r} value {label!r} URL wrong or missing")
        if title not in touched:
            orig = in_sets.get(title)
            if orig is None or len(orig) != len(rows) or not all(
                    semantically_equal(a, b) for a, b in zip(orig, rows)):
                raise SystemExit(f"Validation failed: untouched set {title!r} changed")
    return text


def print_report(changes, attention, set_order):
    print(f"Easify option sets: change report ({datetime.date.today():%d %B %Y})\n")
    if not changes:
        print("No content changes.")
    for title in set_order:
        if title in changes:
            print(title)
            for line in changes[title]:
                print(f"  {line}")
    if attention:
        print("\nNeeds your attention")
        for line in attention:
            print(f"  {line}")


def cmd_sync(report_only):
    config = load_config()
    fieldnames, in_rows = load_canonical()
    in_sets = group_by_set(in_rows)
    tokens = temple_tokens()
    expected, attention = live_temple_products(config, tokens)
    cfg_by_title = {s["set_title"]: s for s in config}

    set_order = list(dict.fromkeys(r["option_set_title"] for r in in_rows))
    out_sets, changes, touched = {}, {}, set()
    for title in set_order:
        if title in cfg_by_title:
            garment = cfg_by_title[title]["garment"]
            new_rows, ch, att = reconcile_set(title, in_sets[title], expected[garment], tokens)
            out_sets[title] = new_rows
            attention += att
            touched.add(title)
            if ch:
                changes[title] = ch
        else:
            out_sets[title] = in_sets[title]

    n_created = 0
    for spec in config:
        title = spec["set_title"]
        if title in out_sets:
            continue
        exp = expected[spec["garment"]]
        if not exp:
            attention.append(f"{title}: no live {spec['garment']} products, set not created")
            continue
        clone = in_sets.get(spec.get("clone_from"))
        if not clone:
            raise SystemExit(f"{title}: clone_from {spec.get('clone_from')!r} not found in the CSV")
        out_sets[title] = new_set_rows(spec, clone, exp, PLACEHOLDER_SET_ID_BASE + n_created)
        n_created += 1
        set_order.append(title)
        touched.add(title)
        labels = sorted(label for label, _ in exp.values())
        changes[title] = [
            f"New set with a placeholder id; the Easify import should create it",
            f"Added {len(labels)} temples: {', '.join(labels)}",
            f"Applies to {len(exp)} products",
        ]

    out_rows = [r for title in set_order for r in out_sets[title]]
    if len(out_rows) == len(in_rows) and all(
            semantically_equal(a, b) for a, b in zip(out_rows, in_rows)):
        print_report({}, attention, set_order)
        print("\nNo changes. CSV not written.")
        return

    expected_by_title = {s["set_title"]: expected[s["garment"]] for s in config
                         if s["set_title"] in touched}
    text = validate_output(fieldnames, out_rows, in_sets, touched, expected_by_title)
    print_report(changes, attention, set_order)
    if report_only:
        print("\nReport only. CSV not written.")
        return
    with open(CANONICAL, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    print(f"\nWrote {CANONICAL.relative_to(PROJECT_ROOT)}")
    print("Next: import that file in the Easify app (import stays manual).")
    if n_created:
        print("This run created a new set. After importing, export fresh from Easify and run:")
        print("  python scripts/easify_options.py reseed --export <downloaded file>")


def cmd_reseed(export_path):
    export_path = Path(export_path)
    fieldnames, cur_rows = load_canonical()
    export_fields, new_rows = load_canonical(export_path)
    if export_fields != fieldnames:
        raise SystemExit("Export header differs from the canonical CSV; refusing to reseed.")
    cur_sets, new_sets = group_by_set(cur_rows), group_by_set(new_rows)
    problems, id_notes = [], []
    for spec in load_config():
        title = spec["set_title"]
        if title not in new_sets:
            problems.append(f"Set {title!r} is missing from the export")
            continue
        new = new_sets[title]
        if not new[0]["option_set_id"].isdigit():
            problems.append(f"{title}: export set id {new[0]['option_set_id']!r} is not numeric")
        if title not in cur_sets:
            continue
        cur = cur_sets[title]
        cur_map = {r["option_value_label"]: value_url(r) for r in cur}
        new_map = {r["option_value_label"]: value_url(r) for r in new}
        for label in sorted(set(cur_map) | set(new_map)):
            if cur_map.get(label) != new_map.get(label):
                problems.append(f"{title} / {label}: canonical has {cur_map.get(label)!r}, "
                                f"export has {new_map.get(label)!r}")
        if set(parse_products(cur[0]["option_set_products"])) != \
                set(parse_products(new[0]["option_set_products"])):
            problems.append(f"{title}: option_set_products differs from canonical")
        if cur[0]["option_set_id"] != new[0]["option_set_id"]:
            id_notes.append(f"{title}: set id {cur[0]['option_set_id']} -> {new[0]['option_set_id']}")
    if problems:
        print("Refusing to reseed. The export does not match the canonical CSV:")
        for p in problems:
            print(f"  {p}")
        print("If the export is right and the canonical is stale, fix the canonical first "
              "or rerun sync after reseeding manually.")
        raise SystemExit(1)
    shutil.copyfile(export_path, CANONICAL)
    print(f"Reseeded {CANONICAL.relative_to(PROJECT_ROOT)} from {export_path.name}")
    for note in id_notes:
        print(f"  {note}")
    if not id_notes:
        print("  No id changes.")


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command")
    sync = sub.add_parser("sync", help="reconcile the CSV with the live catalog")
    sync.add_argument("--report-only", action="store_true", help="print changes, write nothing")
    reseed = sub.add_parser("reseed", help="adopt a fresh Easify export as canonical")
    reseed.add_argument("--export", required=True, help="path to the downloaded Easify export")
    args = ap.parse_args()
    if args.command == "reseed":
        cmd_reseed(args.export)
    else:
        cmd_sync(getattr(args, "report_only", False))


if __name__ == "__main__":
    main()
