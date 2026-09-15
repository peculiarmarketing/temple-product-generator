"""Assembly-time transforms for product description HTML.

The fixed sections are vendored claude.ai skill exports (reference/skills/*/
assets/) that must stay byte-identical to their claude.ai copies, and the
per-temple facts fragments (Temples/{Name}/Working files/temple-facts.html)
are canonical research output. Neither is ever edited for presentation, so
presentation changes live here and are applied when a description is composed
(Evan's 26 Aug 2026 decisions: temple facts render as collapsed <details>
rows, and the size-guide video gets controls so a phone that declines autoplay
still shows a play button instead of a frozen frame).

Idempotency is by full re-derivation: facts re-extracted from a live product
(write_description.FACTS_RE) unwrap back to the canonical fragment before
rewrapping, so composing twice is byte-identical and --normalize converges.
Every transform fails open: input that does not match the expected shape is
returned unchanged, never corrupted.
"""

import re

# Fixed sections to collapse, keyed by their <h3> text. Empty means the fixed
# sections stay open (Evan's 26 Aug 2026 scope: temple facts only; widening
# to e.g. ("Size Guide",) is a one-line flip). "Personalization" must never
# be listed: is_broken() requires dated descriptions to START with that
# section, visible.
COLLAPSIBLE_FIXED_HEADINGS = ()

_FACTS_SECTION_RE = re.compile(
    r'^(<section class="temple-facts">)\n?(.*)(</section>)\s*$', re.S)
_ASOF_RE = re.compile(r'<p class="temple-facts__asof">.*?</p>\s*$', re.S)
_HEADING_RE = re.compile(r'\s*(<h([34])[^>]*>.*?</h\2>)', re.S)
_VIDEO_TAG_RE = re.compile(r'<video [^>]*>')
_SIZE_GUIDE_TAIL_RE = re.compile(
    r'(<section class="size-guide">.*?</video>).*?(</section>)', re.S)
_STYLE_RE = re.compile(r'<style class="temple-facts__style">.*?</style>\n?', re.S)

# Scoped styling for the collapsed rows, shipped inside the facts section so
# it rides every description without theme work. Evan's theme hides the
# default disclosure markers and gives headings tall margins, so this adds
# dividing lines, tight row padding, and a +/- indicator. Literal characters
# only: the Printify connector decodes entities on push.
FACTS_STYLE = (
    '<style class="temple-facts__style">'
    'section.temple-facts details{border-top:1px solid #d8d8d8}'
    'section.temple-facts details:last-of-type{border-bottom:1px solid #d8d8d8}'
    'section.temple-facts summary{cursor:pointer;display:flex;'
    'justify-content:space-between;align-items:center;gap:12px;'
    'padding:12px 0;list-style:none}'
    'section.temple-facts summary::-webkit-details-marker{display:none}'
    'section.temple-facts summary::after{content:"+";flex:none;'
    'font-size:1.5em;line-height:1}'
    'section.temple-facts details[open]>summary::after{content:"−"}'
    'section.temple-facts summary h3,section.temple-facts summary h4{margin:0}'
    '</style>')


def fix_size_guide_video(html):
    """Make the sizing video recoverable when a browser declines autoplay.

    iPhones decline autoplay in Low Power Mode, and without controls the
    video sits as a frozen frame with no way to start it; preload="none"
    leaves an empty box besides. Only the opening <video ...> tag is edited,
    so the cc1717 asset's deliberately odd </source></video> tail rides
    through untouched."""
    html = html.replace('preload="none"', 'preload="metadata"')

    def add_controls(m):
        tag = m.group(0)
        if re.search(r'\bcontrols\b', tag):
            return tag
        return tag.replace('<video ', '<video controls="controls" ', 1)

    return _VIDEO_TAG_RE.sub(add_controls, html)


def trim_size_guide(html):
    """Drop everything after the video inside the size-guide section (the
    measurements table and its notes): the video IS the size guide (Evan's
    26 Aug 2026 call). The vendored asset keeps the table; it just never
    reaches a product."""
    return _SIZE_GUIDE_TAIL_RE.sub(r'\1\n\2', html)


def _unwrap(body):
    """Strip the style block and any details/summary markers this module
    previously emitted. Safe on canonical fragments: none contain style,
    details, or summary tags."""
    body = _STYLE_RE.sub('', body)
    body = re.sub(r'<details[^>]*><summary[^>]*>', '', body)
    body = body.replace('</summary>', '')
    body = re.sub(r'\n?</details>', '', body)
    return body


def _details_block(heading, rest):
    return ('<details class="temple-facts__block">'
            f'<summary>{heading}</summary>\n'
            f'{rest}\n</details>')


def collapse_temple_facts(fragment):
    """Rewrap the facts fragment so each block renders as a collapsed row:
    one for the temple name (h3) with its spec rows, one per h4 block. The
    <section class="temple-facts"> wrapper stays outermost (the publish gate
    and FACTS_RE key on it) and the as-of line stays visible at the end."""
    match = _FACTS_SECTION_RE.match(fragment.strip())
    if not match:
        return fragment
    open_tag, body, close_tag = match.groups()
    body = _unwrap(body)

    asof = _ASOF_RE.search(body)
    tail = asof.group(0).strip() if asof else ""
    wrappable = body[:asof.start()] if asof else body

    chunks = [c for c in re.split(r'(?=<h4[^>]*>)', wrappable) if c.strip()]
    if not chunks or not chunks[0].lstrip().startswith("<h3"):
        return fragment
    blocks = []
    for chunk in chunks:
        m = _HEADING_RE.match(chunk)
        if not m:
            return fragment
        blocks.append(_details_block(m.group(1), chunk[m.end():].strip()))
    return "\n".join([open_tag, FACTS_STYLE] + blocks
                     + ([tail] if tail else []) + [close_tag])


def collapse_fixed_sections(html):
    """Collapse fixed sections whose <h3> text is listed in
    COLLAPSIBLE_FIXED_HEADINGS. A no-op while that tuple is empty."""
    if not COLLAPSIBLE_FIXED_HEADINGS:
        return html
    if "Personalization" in COLLAPSIBLE_FIXED_HEADINGS:
        raise ValueError("Personalization must stay visible: is_broken() "
                         "requires dated descriptions to start with it.")
    for title in COLLAPSIBLE_FIXED_HEADINGS:
        pattern = re.compile(r'(<section class="[^"]*">\n)(<h3>' + re.escape(title)
                             + r'</h3>)\n(.*?)(\n</section>)', re.S)
        html = pattern.sub(
            lambda m: m.group(1) + _details_block(m.group(2), _unwrap(m.group(3)).strip())
                      + m.group(4),
            html)
    return html


def compose_description(fixed, facts=None):
    """The one place a description's final HTML is shaped. Empty fixed
    sections yield an empty description (empty beats a page carrying another
    temple's history); missing facts yield the fixed sections alone."""
    if not fixed:
        return ""
    polished = collapse_fixed_sections(trim_size_guide(fix_size_guide_video(fixed)))
    if not facts:
        return polished
    return polished + "\n\n" + collapse_temple_facts(facts.strip())
