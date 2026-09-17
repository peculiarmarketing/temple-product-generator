"""Mirror every temple's researched facts fragment into the repo.

WHY THIS EXISTS. `Temples/` is not a git repository and is not tracked by this
one, so until 17 September 2026 the temple-facts.html files existed in exactly
one place: iCloud. They are the one part of this pipeline a machine cannot
regenerate. Everything else is derived. A print file can be re-flattened, a
mockup re-rendered, a ledger rebuilt from the store; a temple's history has to be
researched against a source hierarchy and screened against known folklore, and
that is hours of judgement per temple.

The risk is not theoretical. On 17 September five temples (Logan, Provo,
Kirtland, Cody, Taylorsville) turned out to have been researched already, weeks
earlier, and the only surviving copy was the description of their old Printify
listings. Nobody knew. They were recovered only because those listings still
exist as drafts, and deleting a draft would have destroyed the work silently.

So this copies each fragment into `artifacts/temple-facts/`, which IS tracked,
giving the research version history and a second physical location.

DIRECTION IS ONE WAY, ON PURPOSE. `Temples/` stays the source of truth because
that is where the pipeline reads from and where new research is written. This
mirror is a backup, not a second master, and it never writes back. If the two
disagree the mirror is stale and re-running fixes it; `--check` is what tells you
they disagree without changing anything.

NAMING. Folder names can carry a ref-finder star ("Lehi*"), which is legal but
awkward in git and on other platforms, so the star is stripped. Nothing else is
normalised: "Ogden (original)" stays "Ogden (original).html", so the file maps
back to its folder by eye. No two temple folders differ only by a star, which is
what makes stripping it unambiguous.

Usage:
  python scripts/mirror_facts.py                # copy anything new or newer
  python scripts/mirror_facts.py --report-only  # say what would change
  python scripts/mirror_facts.py --check        # exit 1 if the mirror is stale
"""

import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from layout import PROJECT_ROOT, TEMPLES_DIR, working_path

MIRROR_DIR = PROJECT_ROOT / "artifacts" / "temple-facts"
FACTS_NAME = "temple-facts.html"


def mirror_name(folder_name):
    """The tracked filename for a temple folder. See NAMING above."""
    return f"{folder_name.rstrip('*').strip()}.html"


def sources():
    """Every temple folder holding a facts fragment, sorted.

    `All` is skipped: it is the flat black-art mirror for the digital download,
    not a temple, and any script walking Temples/ has to skip it.

    Resolved with layout.working_path, the same resolver the pipeline reads
    through, rather than a path built here. Fragments normally live in the
    temple's working folder, but the resolver falls back to the folder root for
    a temple whose files have not been moved yet, and a mirror that looked in
    only one of those two places would silently back up a subset.
    """
    out = []
    for folder in sorted(TEMPLES_DIR.iterdir()):
        if not folder.is_dir() or folder.name == "All":
            continue
        facts = working_path(folder.name, FACTS_NAME)
        if facts.exists():
            out.append((folder.name, facts))
    return out


def plan():
    """[(folder, src, dest, reason)] for everything not already mirrored."""
    work = []
    for folder_name, src in sources():
        dest = MIRROR_DIR / mirror_name(folder_name)
        if not dest.exists():
            work.append((folder_name, src, dest, "new"))
        elif dest.read_bytes() != src.read_bytes():
            work.append((folder_name, src, dest, "changed"))
    return work


def orphans():
    """Mirrored files whose temple folder no longer has a fragment.

    Reported, never deleted. A temple folder being renamed looks exactly like a
    temple being removed, and this file is the backup: deleting on a guess is the
    one thing it must not do.
    """
    if not MIRROR_DIR.exists():
        return []
    expected = {mirror_name(name) for name, _ in sources()}
    return sorted(p.name for p in MIRROR_DIR.glob("*.html")
                  if p.name not in expected)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--report-only", action="store_true",
                      help="print what would change, write nothing")
    mode.add_argument("--check", action="store_true",
                      help="exit 1 if the mirror is stale, write nothing")
    a = ap.parse_args()

    found = sources()
    work, stale = plan(), orphans()
    print(f"{len(found)} temple(s) with a facts fragment; "
          f"{len(work)} to mirror; {len(stale)} orphaned in the mirror.")

    for folder_name, _, dest, reason in work:
        print(f"  {reason:8} {folder_name} -> artifacts/temple-facts/{dest.name}")
    for name in stale:
        print(f"  orphan   artifacts/temple-facts/{name} has no temple folder; "
              f"left alone")

    if a.check:
        if work:
            print("\nMirror is STALE. Run scripts/mirror_facts.py and commit.")
            return 1
        print("\nMirror is up to date.")
        return 0
    if a.report_only:
        print("\nReport only. Nothing written.")
        return 0
    if not work:
        print("\nNothing to do.")
        return 0

    MIRROR_DIR.mkdir(parents=True, exist_ok=True)
    for _, src, dest, _ in work:
        shutil.copy2(src, dest)
    print(f"\nMirrored {len(work)} fragment(s) into "
          f"{MIRROR_DIR.relative_to(PROJECT_ROOT)}. Commit them.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
