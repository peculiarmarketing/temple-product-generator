"""Build every Tapstitch print file from a scan of the Temples folder.

One flattened PNG per temple per garment per ink colour for the back, plus one
front logo file per garment per colour. Files land in each temple's own folder
(front logo files in artifacts/, since they are per garment, not per temple).
Every file is validated before it is written, and the results go into the
migration ledger.

Usage:
  python scripts/tapstitch_build.py --report-only          # scan, build nothing
  python scripts/tapstitch_build.py                        # build everything
  python scripts/tapstitch_build.py --temple "Salt Lake"   # one temple
  python scripts/tapstitch_build.py --colors black         # one ink colour
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import flatten
import generate
import ledger
from layout import PROJECT_ROOT

TEMPLES_DIR = flatten.TEMPLES_DIR


def build_temple(temple, garment_ids, colors, report_only, trace):
    """Returns [(garment, state, files, problems)] for one temple."""
    folder = TEMPLES_DIR / temple
    try:
        if report_only or not trace:
            generate.detect_art_files(folder)
        else:
            generate.ensure_art_files(folder, temple)
    except SystemExit as e:
        reason = "no traced art yet" if "Expected exactly one" in str(e) else str(e)[:80]
        return [(g, "art-missing", {}, [reason]) for g in garment_ids]

    try:
        manifest = generate.load_manifest(temple)
    except SystemExit as e:
        return [(g, "art-missing", {}, [f"manifest: {str(e)[:80]}"]) for g in garment_ids]

    out = []
    for gid in garment_ids:
        cfg = generate.load_garment_config(gid)
        files, problems = {}, []
        try:
            for color in colors:
                r = flatten.build_back(temple, manifest, cfg, color)
                problems += [f"{color}: {p}" for p in
                             flatten.validate(r["image"], cfg, r["sources"], color,
                                              pre_matte=r["raw"])]
                path = flatten.back_file_path(temple, gid, color)
                if not report_only:
                    flatten.save(r["image"], path)
                files[color] = path.name
        except SystemExit as e:
            out.append((gid, "error", files, [str(e)[:160]]))
            continue
        except Exception as e:  # one bad temple must not take the other 45 with it
            out.append((gid, "error", files, [f"{type(e).__name__}: {str(e)[:140]}"]))
            continue
        state = "error" if problems else ("art-ok" if report_only else "file-built")
        out.append((gid, state, files, problems))
    return out


def build_front_logos(garment_ids, colors, report_only):
    rows = []
    for gid in garment_ids:
        cfg = generate.load_garment_config(gid)
        for color in colors:
            try:
                r = flatten.build_front_logo(cfg, color)
                probs = flatten.validate(r["image"], cfg, r["sources"], color,
                                         area_key="front_print_area", pre_matte=r["raw"])
                path = flatten.front_file_path(gid, color)
                if not report_only:
                    flatten.save(r["image"], path)
                rows.append((gid, color, path.name, probs))
            except SystemExit as e:
                rows.append((gid, color, "-", [str(e)[:120]]))
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--temple", help="one temple folder name; default is every temple")
    ap.add_argument("--garments", help="comma-separated garment ids; default is every Tapstitch garment")
    ap.add_argument("--colors", default="black,white", help="ink colours to build")
    ap.add_argument("--report-only", action="store_true", help="scan and validate, write no files")
    ap.add_argument("--no-trace", dest="trace", action="store_false",
                    help="do not trace missing art from a source PNG; just report it")
    ap.add_argument("--verbose", action="store_true", help="also list rows with nothing to say")
    a = ap.parse_args()

    known = generate.all_garment_ids(None)
    garment_ids = a.garments.split(",") if a.garments else generate.all_garment_ids("tapstitch")
    unknown = [g for g in garment_ids if g not in known]
    if unknown:
        raise SystemExit(f"Unknown garment id(s): {', '.join(unknown)}. "
                         f"Known: {', '.join(known)}")
    if not garment_ids:
        raise SystemExit("No Tapstitch garments configured in garments/.")
    colors = a.colors.split(",")
    temples = [a.temple] if a.temple else [f.name for f in flatten.temple_folders()]

    data = ledger.load()
    rows = []
    # Rasterising complex temple art at print resolution is genuinely slow (some
    # temples take several seconds each), so a full sweep runs for minutes. Print
    # progress to stderr as it goes rather than leaving the operator watching a
    # blank terminal wondering whether it hung.
    for n, temple in enumerate(temples, 1):
        print(f"[{n}/{len(temples)}] {temple}", file=sys.stderr, flush=True)
        for gid, state, files, problems in build_temple(temple, garment_ids, colors,
                                                        a.report_only, a.trace):
            rows.append((temple, gid, state, problems))
            ledger.upsert_build(data, temple, gid, state, files, problems)
    ledger.save(data)

    front = build_front_logos(garment_ids, colors, a.report_only)

    print(f"\n{'Temple':<22} {'Garment':<10} State")
    for temple, gid, state, problems in rows:
        if state in ("file-built", "art-ok") and not a.verbose:
            continue
        print(f"{temple:<22} {gid:<10} {state}")
        for p in problems:
            print(f"{'':<33}  - {p}")
    print(f"\nfront logo files:")
    for gid, color, name, probs in front:
        print(f"  {gid:<10} {color:<6} {name}" + (f"  PROBLEMS: {probs}" if probs else ""))

    built = sum(1 for r in rows if r[2] in ("file-built", "art-ok"))
    print(f"\n{built} {'validated clean' if a.report_only else 'built clean'}, "
          f"{sum(1 for r in rows if r[2] == 'error')} with problems, "
          f"{sum(1 for r in rows if r[2] == 'art-missing')} without art, "
          f"of {len(rows)} temple/garment pairs."
          + ("  (report only: ledger updated, no PNGs written)" if a.report_only else ""))


if __name__ == "__main__":
    main()
