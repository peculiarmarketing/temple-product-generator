"""Offline tests for the description HTML transforms. No network.

Run: ./.venv.nosync/bin/python tests/test_description_html.py
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from description_html import (COLLAPSIBLE_FIXED_HEADINGS, FACTS_STYLE,
                              collapse_fixed_sections,
                              collapse_temple_facts, compose_description,
                              fix_size_guide_video, trim_size_guide)
import generate
from generate import TEMPLES_DIR, fixed_description, load_garment_config

# How a facts section is read back out of a composed description.
FACTS_RE = re.compile(r'<section class="temple-facts">.*</section>', re.S)

MINI_FRAGMENT = """<section class="temple-facts">
<h3 class="temple-facts__name">Test Utah Temple</h3>
<p class="temple-spec__row"><strong>Status</strong><br>Operating.</p>
<p class="temple-spec__row"><strong>Location</strong><br>Test, Utah.</p>
<h4>Construction Story</h4>
<ul class="temple-facts__list">
<li>Built.</li>
</ul>
<h4>Trivia</h4>
<ul class="temple-facts__list">
<li>Shares its dedication day with another temple, per <time datetime="2026-10-11">October 11, 2026</time>.</li>
</ul>
<p class="temple-facts__asof"><em>Temple facts verified as of <time datetime="2026-08-26">August 26, 2026</time>.</em></p>
</section>"""

VIDEO_HTML = """<section class="size-guide">
<h3>Size Guide</h3>
<video autoplay="autoplay" loop="loop" muted="" playsinline="" preload="none" style="display:block;width:100%">
<source src="https://cdn.example/a.webm" type="video/webm">
<source src="https://cdn.example/b.mp4" type="video/mp4"></source></video>
<h4>Measurements (inches)</h4>
<table><tbody><tr><td>S</td><td>18.25</td></tr></tbody></table>
<p>Width is measured underarm to underarm.</p>
</section>"""


def collapsed_shape(out, fragment):
    h4s = fragment.count("<h4")
    assert out.startswith('<section class="temple-facts">'), "section wrapper must stay outermost"
    assert out.rstrip().endswith("</section>"), "section wrapper must stay outermost"
    assert 'class="temple-facts"' in out, "publish gate substring must survive"
    assert out.count("<details") == 1 + h4s, f"expected {1 + h4s} details blocks, got {out.count('<details')}"
    assert out.count("<details") == out.count("</details>") == out.count("<summary")
    asof_pos = out.find('<p class="temple-facts__asof">')
    assert asof_pos > out.rfind("</details>"), "as-of line must sit after the last details block"
    assert asof_pos < out.rfind("</section>"), "as-of line must sit inside the section"
    assert out.count(FACTS_STYLE) == 1, "exactly one scoped style block"
    assert out.find(FACTS_STYLE) < out.find("<details"), "style block precedes the rows"
    # Heading tags ride inside the summaries, byte-identical.
    for heading in re.findall(r"<h[34][^>]*>.*?</h[34]>", fragment, re.S):
        assert f"<summary>{heading}</summary>" in out, heading


# The mini fragment plus real fragments: one with Changes Over Time, one without.
fragments = {"mini": MINI_FRAGMENT}
with_change = without_change = None
for path in sorted(TEMPLES_DIR.glob("*/temple-facts.html")) + \
            sorted(TEMPLES_DIR.glob("*/Working files/temple-facts.html")):
    text = path.read_text().strip()
    if "Changes Over Time" in text and not with_change:
        with_change = (path.parent.name, text)
    elif "Changes Over Time" not in text and not without_change:
        without_change = (path.parent.name, text)
if with_change:
    fragments[f"real with Changes Over Time ({with_change[0]})"] = with_change[1]
if without_change:
    fragments[f"real without Changes Over Time ({without_change[0]})"] = without_change[1]
assert with_change and without_change, "expected real fragments of both shapes in Temples/"

for name, fragment in fragments.items():
    out = collapse_temple_facts(fragment)
    collapsed_shape(out, fragment)
    assert collapse_temple_facts(out) == out, f"{name}: collapse must be idempotent byte-exact"

# FACTS_RE round trip: extract the facts from a composed description and
# re-collapse; must be byte-identical, so recomposing converges.
fixed = fixed_description(load_garment_config("tee"))
assert fixed, "tee fixed sections missing"
composed = compose_description(fixed, MINI_FRAGMENT)
extracted = FACTS_RE.search(composed).group(0).strip()
assert collapse_temple_facts(extracted) == extracted, "extracted facts must already be canonical"
assert compose_description(fixed, extracted) == composed, "recompose from live extraction must converge"

# Fail open: input that is not a facts section comes back unchanged.
assert collapse_temple_facts("<p>not a facts section</p>") == "<p>not a facts section</p>"
assert collapse_temple_facts('<section class="temple-facts">\n<p>no h3 first</p>\n</section>') \
    == '<section class="temple-facts">\n<p>no h3 first</p>\n</section>'

# Video fix: controls added exactly once, preload upgraded, tails untouched.
fixed_video = fix_size_guide_video(VIDEO_HTML)
assert fixed_video.count('controls="controls"') == 1
assert 'preload="metadata"' in fixed_video and 'preload="none"' not in fixed_video
assert "</source></video>" in fixed_video, "malformed tail must ride through untouched"
assert fix_size_guide_video(fixed_video) == fixed_video, "video fix must be idempotent"

# Size-guide trim: the video IS the size guide; the table and notes go.
trimmed = trim_size_guide(fixed_video)
assert "</video>\n</section>" in trimmed
assert "<table" not in trimmed and "Measurements (inches)" not in trimmed
assert "Width is measured" not in trimmed
assert "<h3>Size Guide</h3>" in trimmed and "</source></video>" in trimmed
assert trim_size_guide(trimmed) == trimmed, "trim must be idempotent"

# --- the collapsed Care Instructions row (Evan, 18 Sep 2026) ----------------
# It collapses in place, inside its own section, with a style scoped to that
# section's own class rather than one global style block.
CARE = (generate.PROJECT_ROOT / generate.CARE_COPY).read_text().strip()
care_out = collapse_fixed_sections(CARE)
assert care_out.startswith('<section class="care-instructions">')
assert care_out.rstrip().endswith("</section>"), "section wrapper stays outermost"
assert care_out.count("<details") == care_out.count("</details>") == 1
assert "<summary><h3>Care Instructions</h3></summary>" in care_out, \
    "the heading rides inside the summary, byte-identical"
assert '<style class="care-instructions__style">' in care_out
assert "section.temple-facts" not in care_out, \
    "the care row must be styled by its OWN class, not the facts scope"
assert care_out.index("<style") < care_out.index("<details"), "style precedes the row"
assert collapse_fixed_sections(care_out) == care_out, "collapse must be idempotent"

# Fail open, like every other transform here: copy that is not the expected
# shape ships open rather than corrupted.
assert collapse_fixed_sections("<p>no care section</p>") == "<p>no care section</p>"

# End to end on the real garments: each line gets exactly one collapsed care row.
for garment in ("crew", "hoodie", "tee"):
    out = compose_description(fixed_description(load_garment_config(garment)), MINI_FRAGMENT)
    assert out.count('<details class="care-instructions__block">') == 1, garment
    assert out.count('<style class="care-instructions__style">') == 1, garment
    assert out.count(FACTS_STYLE) == 1, f"{garment}: the facts style is untouched"
    assert out.index("care-instructions") < out.index("product-intro") \
        < out.index("temple-facts"), garment

# --- the collapsed From the Founder row (Evan, 18 Sep 2026) -----------------
# Same machinery as the care row, scoped to product-intro.
assert "From the Founder" in COLLAPSIBLE_FIXED_HEADINGS
assert "From the Founders" in COLLAPSIBLE_FIXED_HEADINGS
for garment in ("crew", "hoodie", "tee"):
    raw = fixed_description(load_garment_config(garment))
    out = compose_description(raw, MINI_FRAGMENT)
    assert out.count('<details class="product-intro__block">') == 1, garment
    assert out.count('<style class="product-intro__style">') == 1, garment
    assert "<summary><h3>From the Founders</h3></summary>" in out, garment
    # The founder message itself must survive the wrap, every paragraph of it.
    assert out.count("<p>") == raw.count("<p>"), f"{garment}: copy lost in the wrap"
    assert "<p>Evan &amp; Bailee, founders of Peculiar People</p>" in out, \
        f"{garment}: the signoff must survive"
    assert "<ol><li>" in out, f"{garment}: the numbered list must survive"
# Collapsing a LIVE description is the same transform as collapsing the repo's
# assets, which is what lets scripts/collapse_live_sections.py backfill without
# recomposing. Applied twice it must be a no-op, and it must leave a section
# that is ALREADY collapsed alone rather than double-wrapping it.
live = compose_description(fixed_description(load_garment_config("crew")), MINI_FRAGMENT)
assert collapse_fixed_sections(live) == live, "collapsing a composed description is a no-op"

# Empty fixed sections still yield an empty description.
assert compose_description("", MINI_FRAGMENT) == ""
assert compose_description(None) == ""

print("all tests passed")
