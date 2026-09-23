"""Offline tests for scripts/web_drawings.py. No network.

Run: ./.venv.nosync/bin/python tests/test_web_drawings_cli.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.web_drawings import drawing_files, slug_for, temple_folders  # noqa: E402

# Every `temple:` tag on the live store, read 23 Sep 2026. Folder names must map onto
# exactly these, or a product page would look for a drawing file that is never built.
LIVE_TAGS = {
    "albuquerque", "billings", "boise", "bountiful", "brigham-city", "burley", "cedar-city",
    "cody", "deseret-peak", "draper", "ephraim", "heber-valley", "jordan-river", "kirtland",
    "layton", "lehi", "lindon", "logan", "manhattan", "manti", "mexico-city", "monticello",
    "mount-timpanogos", "nauvoo", "oakland", "ogden", "ogden-original", "orem",
    "provo-city-center", "provo-rock-canyon", "provo", "red-cliffs", "rome", "salt-lake",
    "san-antonio", "san-diego", "saratoga-springs", "smithfield", "spanish-fork", "st-george",
    "syracuse", "taylorsville", "vernal", "washington-d-c", "west-jordan",
}

assert slug_for("Salt Lake") == "salt-lake"
assert slug_for("St. George") == "st-george"
assert slug_for("Heber Valley*") == "heber-valley"
assert slug_for("Ogden (original)") == "ogden-original"
assert slug_for("Washington DC") == "washington-d-c"

folders = temple_folders()
assert set(folders) == LIVE_TAGS, (
    f"missing: {sorted(LIVE_TAGS - set(folders))}  extra: {sorted(set(folders) - LIVE_TAGS)}")
assert folders["washington-d-c"] == "Washington DC"

assert drawing_files("logan") == ("assets/pp-temple-logan.json", "assets/pp-temple-logan.webp")

print("ok")
