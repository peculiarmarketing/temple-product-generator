"""Offline tests for the homepage marquee check. No network.

Run: ./.venv.nosync/bin/python tests/test_web_marquee.py

WHY THIS FILE EXISTS. The marquee drops a temple silently when any one of its
website files is missing, so scripts/web_marquee.py is the only thing that notices
a new temple published without them. What is pinned: each missing piece is
reported on its own, a complete temple is not reported, the snippet parser reads
the generated case statement, and a theme that could not be read (token without
read_themes) still reports the repo gaps instead of claiming everything is fine.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import web_marquee as W

# --- the snippet parser reads the generated file ---------------------------
text = W.SNIPPET.read_text()
parsed = W.snippet_slugs(text)
assert "salt-lake" in parsed and "washington-d-c" in parsed, parsed
repo = {p.stem.removeprefix("pp-temple-") for p in (W.THEME / "assets").glob("pp-temple-*.json")}
assert parsed == repo, f"snippet and stroke files disagree: {parsed ^ repo}"

# --- one complete temple, one missing everything ---------------------------
theme = {"assets/pp-temple-logan.webp", "assets/pp-temple-logan.json"}
out = W.gaps({"logan", "new-one"}, {"logan"}, {"logan"}, theme)
assert "logan" not in out, out
assert len(out["new-one"]) == 4, out["new-one"]

# --- uploaded art but no snippet line is still a gap -----------------------
theme_new = theme | {"assets/pp-temple-new-one.webp", "assets/pp-temple-new-one.json"}
out = W.gaps({"new-one"}, {"new-one"}, set(), theme_new)
assert out == {"new-one": ["its city line in snippets/pp-temple-city.liquid (run sync)"]}, out

# --- theme not readable: repo gaps still reported, theme ones not invented --
out = W.gaps({"new-one"}, set(), set(), None)
assert len(out["new-one"]) == 2, out
assert not any("in the theme" in m for m in out["new-one"]), out

print("all tests passed")
