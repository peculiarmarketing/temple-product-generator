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

from scripts.web_drawings import md5, plan_uploads  # noqa: E402

local = {"assets/a.json": b"one", "assets/b.webp": b"two", "assets/c.js": b"three"}
remote = {"assets/a.json": md5(b"one"), "assets/b.webp": md5(b"old"), "assets/zzz.json": "x"}
assert plan_uploads(local, remote) == ["assets/b.webp", "assets/c.js"], plan_uploads(local, remote)
assert plan_uploads(local, {k: md5(v) for k, v in local.items()}) == []


# --- build: retry ladder, and nothing (not even an old copy) survives a failed gate ---
import json as _json  # noqa: E402
import shutil  # noqa: E402
import tempfile  # noqa: E402
import types  # noqa: E402

import scripts.web_drawings as wds  # noqa: E402

GOOD = {"strokes": 1, "uncovered_pct": 0.1, "json_gz_bytes": 10, "image_bytes": 10}
BAD = {**GOOD, "uncovered_pct": 5.0}


def fake_build(pass_from):
    calls = []

    def build(svg, city, trace_width, art_px):
        calls.append((trace_width, art_px))
        ok = len(calls) >= pass_from
        return {"data": {"city": city}, "image": b"webp", "stats": GOOD if ok else BAD}
    return build, calls


real_build, real_out = wds.web_drawing.build, wds.OUT_DIR
tmp = Path(tempfile.mkdtemp())
try:
    wds.OUT_DIR = tmp
    wds.web_drawing.build, calls = fake_build(pass_from=2)
    _, problems, used = wds.build_one("Logan")
    assert problems == [] and used == wds.ATTEMPTS[1] and calls == wds.ATTEMPTS[:2], (problems, used, calls)

    # a previous good build of Logan is on disk; a new build fails every gate
    (tmp / "pp-temple-logan.json").write_text("{}")
    (tmp / "pp-temple-logan.webp").write_bytes(b"old")
    (tmp / "build-report.json").write_text(_json.dumps({"logan": {"folder": "Logan"}}))
    wds.web_drawing.build, _ = fake_build(pass_from=99)
    rc = wds.cmd_build(types.SimpleNamespace(all=False, temple=["Logan"]))
    assert rc == 1
    assert not list(tmp.glob("pp-temple-logan.*")), "a failed build left the old drawing to be pushed"
    assert "logan" not in _json.loads((tmp / "build-report.json").read_text())

    # push only picks up the temples asked for, plus the theme code
    for slug in ("logan", "rome"):
        (tmp / f"pp-temple-{slug}.json").write_text("{}")
        (tmp / f"pp-temple-{slug}.webp").write_bytes(b"x")
    files = wds.local_theme_files({"logan"})
    assert set(files) == set(wds.THEME_CODE) | set(drawing_files("logan")), sorted(files)
finally:
    wds.web_drawing.build, wds.OUT_DIR = real_build, real_out
    shutil.rmtree(tmp, ignore_errors=True)

# a mistyped folder gets the same readable message from build and push
assert wds.slugs_for_folders(["Logan", "Salt Lake"]) == {"logan": "Logan", "salt-lake": "Salt Lake"}
try:
    wds.slugs_for_folders(["Salt Lake City"])
    raise AssertionError("an unknown folder should be refused")
except SystemExit as e:
    assert "Salt Lake City" in str(e)

print("ok")
