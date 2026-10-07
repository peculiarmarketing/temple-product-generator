"""Shared temple and garment helpers for the Tapstitch pipeline.

Temple manifests, art detection, product titles and description assembly. The
scripts under scripts/ (tapstitch_build, tapstitch_run, tapstitch_publish and
the rest) import these; this module has no command line of its own.

Temple manifest (Temples/{Name}/Working files/manifest.json):
  {
    "slug": "logan",
    "official_name": "Logan Utah Temple",
    "location_line": "LOGAN, UTAH",
    "place_tokens": {"default": "Logan"},
    "art": {"black": "Logan black.svg", "white": "Logan white.svg"},
    "garments": "all"
  }
Manifests scaffold themselves from temples.json when a temple has none.
"""

import json
import re
import shutil

from description_html import compose_description
from layout import PROJECT_ROOT, TEMPLES_DIR, temple_manifests, working_path  # noqa: F401

# Flat folder of every temple's black SVG under its clean place-token name,
# kept for the digital download files. Not a temple folder; every temple scan skips it.
ALL_ART_DIR = TEMPLES_DIR / "All"
GARMENTS_DIR = PROJECT_ROOT / "garments"
CATALOG_CONFIG = PROJECT_ROOT / "config" / "catalog.json"

# Titles carry the temple in parentheses ("Essential Temple Tee (Logan)"),
# except the parent temple's, which carry the bare garment line. Anything
# reading a title back has to cope with both shapes.
PLACE_SUFFIX_RE = re.compile(r"\(([^()]+)\)\s*$")
ONE_OFF_MARKER = "limited edition"


def load_catalog_config():
    return json.loads(CATALOG_CONFIG.read_text())


def parent_temple():
    """The temple whose products are the storefront's parent listings: bare
    garment titles, with every other temple's product reachable through the
    parent page's Easify Temple dropdown. All products publish ACTIVE on
    Shopify (Evan's 26 Aug 2026 decision); children published before that
    date remain UNLISTED but their URLs still resolve."""
    return load_catalog_config()["parent_temple"]


def load_garment_config(garment_id):
    return json.loads((GARMENTS_DIR / f"{garment_id}.json").read_text())


def build_title(garment_cfg, temple_name, place):
    """The one place a product title is composed. The parent temple gets the
    bare garment title; every other temple gets the parenthesized place."""
    if temple_name == parent_temple():
        return garment_cfg["naming"]["title_parent"]
    return garment_cfg["naming"]["title"].format(place=place)


def parent_titles():
    """Every garment's bare parent title, for reading a title back to a temple."""
    return {load_garment_config(p.stem)["naming"]["title_parent"]
            for p in GARMENTS_DIR.glob("*.json")}


def title_is_one_off(title):
    """Limited Edition products are Evan's hand-built one-offs (front-logo
    designs, the Nauvoo limited run). The pipeline never builds over one,
    never publishes one, and never gives one a dropdown row."""
    return ONE_OFF_MARKER in (title or "").lower()


def detect_art_files(folder):
    """Find the black and white temple SVGs in a folder root (never in
    subfolders, never the location text files)."""
    art = {}
    for color in ("black", "white"):
        hits = [p for p in folder.glob("*.svg")
                if color in p.name.lower() and "location text" not in p.name.lower()]
        if len(hits) != 1:
            raise SystemExit(f"Expected exactly one {color} SVG in {folder}, found "
                             f"{[p.name for p in hits] or 'none'}. Fix the folder or write a manifest.")
        art[color] = hits[0].name
    return art


def ensure_art_files(folder, temple_name):
    """SVG pair, tracing it from the source PNG if needed. The trace only
    stands if it passes the tracer skill's health checks."""
    try:
        return detect_art_files(folder)
    except SystemExit:
        from trace_art import find_source_png, trace_temple
        if find_source_png(folder, temple_name) is None:
            raise
        trace_temple(folder, temple_name)
        return detect_art_files(folder)


def scaffold_manifest(temple_name):
    """Build a manifest automatically from temples.json plus the folder's
    art files. New temples need only a folder with two SVGs, provided the
    dataset has a VERIFIED location for them."""
    dataset = json.loads((PROJECT_ROOT / "temples.json").read_text())
    dataset.pop("_comment", None)
    # A trailing '*' is Evan's ref-finder marker on the FOLDER, never part of the
    # temple's name. Left in, it reaches the dataset lookup (which misses), the
    # slug, the Temples/All mirror filename, and worst of all the place token,
    # which is what prints in the product title: "Essential Temple Tee (Lehi*)".
    # Hand-written manifests already strip it (see West Jordan*); scaffolded ones
    # must too.
    clean_name = temple_name.rstrip("*").strip()
    entry = dataset.get(temple_name) or dataset.get(clean_name)
    if entry is None:
        raise SystemExit(
            f"{temple_name!r} has no manifest and is not in temples.json. Add it: look up the "
            f"temple's PHYSICAL city (churchofjesuschristtemples.org), add an entry with "
            f"verified=true, and re-run. Note the physical city can differ from the name "
            f"(Washington D.C. Temple prints KENSINGTON, MARYLAND).")
    if not entry.get("verified"):
        raise SystemExit(
            f"{temple_name!r} is in temples.json but unverified ({entry['location_line']!r}). "
            f"Verify the physical location against churchofjesuschristtemples.org, set "
            f"verified=true, and re-run. Do not guess.")
    folder = TEMPLES_DIR / temple_name
    manifest = {
        "slug": clean_name.lower().replace(" ", "-").replace(".", ""),
        "official_name": entry["official_name"],
        "location_line": entry["location_line"],
        "place_tokens": {"default": clean_name},
        "art": ensure_art_files(folder, temple_name),
        "garments": "all",
        "scaffolded": True,
    }
    working_path(temple_name, "manifest.json", for_write=True).write_text(
        json.dumps(manifest, indent=2))
    print(f"scaffolded manifest for {temple_name}: {entry['location_line']} "
          f"({manifest['art']['black']} / {manifest['art']['white']})")
    return manifest


def mirror_black_art(temple_name, manifest):
    """Duplicate the temple's black SVG into Temples/All/ under its clean
    place-token name (folder names can carry ref-finder stars and old
    spellings; the token is the customer-facing name). Refreshes the copy
    when the source art is newer; the source is never touched. scripts/sweep.py
    calls this for every new temple (its download step)."""
    src = TEMPLES_DIR / temple_name / manifest["art"]["black"]
    dest = ALL_ART_DIR / f"{manifest['place_tokens']['default']} black.svg"
    if dest.exists() and dest.stat().st_mtime >= src.stat().st_mtime:
        return
    ALL_ART_DIR.mkdir(exist_ok=True)
    shutil.copy2(src, dest)
    print(f"  mirrored {src.name} -> Temples/All/{dest.name}")


def load_manifest(temple_name):
    path = working_path(temple_name, "manifest.json")
    if not path.exists():
        return scaffold_manifest(temple_name)
    m = json.loads(path.read_text())
    for color in ("black", "white"):
        art = TEMPLES_DIR / temple_name / m["art"][color]
        if not art.exists():
            raise SystemExit(f"Manifest names missing art file: {art}")
    return m


def fixed_description(garment_cfg):
    """The garment's verbatim fixed sections, assembled as details -> care ->
    intro (Evan, 16 Sep 2026: the product-specific details lead and the size
    guide drops out of the description entirely; care instructions joined
    18 Sep 2026, between the specs and the founder message, which is where Evan
    first placed them by hand). compose_description() appends temple facts last.

    Copy lives per garment in reference/garment-copy/{garment_id}/. A
    size-guide.html beside the other files is ignored.

    CARE_COPY is shared by all three lines rather than duplicated per garment
    (Evan, 18 Sep 2026): the five instructions and the symbol strip are the same
    for the 350gsm fleece and the 7.7oz cotton tee. A line that needs its own
    wording gets a care-instructions.html in its own folder; nothing else
    changes.

    A garment whose copy is missing returns empty, which is the point: an empty
    description beats the wrong garment's specifications on a live page. A
    MISSING care file is the one case that hard-stops instead: it is one
    checked-in file shared by every line, so it cannot go missing for one
    garment, and blanking the catalogue over it would be a wildly
    disproportionate answer to a file that is simply not there."""
    assets = PROJECT_ROOT / (garment_cfg.get("garment_copy")
                             or f"reference/garment-copy/{garment_cfg['garment_id']}")
    intro = assets / "product-intro.html"
    details = assets / "product-details.html"
    if not (details.exists() and intro.exists()):
        return ""  # empty beats a wrong temple's history on a live page
    care = assets / "care-instructions.html"
    if not care.exists():
        care = PROJECT_ROOT / CARE_COPY
    if not care.exists():
        raise SystemExit(f"{garment_cfg['garment_id']}: {CARE_COPY} is missing; "
                         f"refusing to write a description with no care instructions.")
    return "\n\n".join([details.read_text().strip(), care.read_text().strip(),
                         intro.read_text().strip()])


# The care instructions every current line shares. A garment folder may still
# carry its own care-instructions.html, which wins; none does today.
CARE_COPY = "reference/garment-copy/care-instructions.html"


FACTS_MARKER = '<section class="temple-facts"'


def title_for(temple_name, garment_id, garment_cfg=None):
    """This temple and garment's product title, place token resolved.

    build_title() is "the one place a product title is composed", but the
    manifest lookup that feeds it was being inlined at every call site, which
    is how a third copy ended up in the runner. This is that lookup.
    """
    garment_cfg = garment_cfg or load_garment_config(garment_id)
    manifest = load_manifest(temple_name)
    place = manifest["place_tokens"].get(garment_id,
                                         manifest["place_tokens"]["default"])
    return build_title(garment_cfg, temple_name, place)


def description_for(temple_name, garment_cfg):
    """(html, reason). One of them is always None.

    The one place that decides what a product's description is, and whether it
    is complete enough to publish. Three callers had grown their own version of
    this by 16 Sep 2026 and they had already drifted: two tested
    `facts_path.exists()` while one stripped the text first, so a blank
    temple-facts.html was publishable through one path and not another.

    A facts file that exists but carries no facts section is treated as missing.
    compose_description() returns the fixed sections alone for empty facts, so
    the difference is invisible downstream: the product would simply publish
    without the section people actually read.
    """
    fixed = fixed_description(garment_cfg)
    if not fixed:
        return None, f"garment copy missing ({garment_cfg['garment_copy']})"
    facts_path = working_path(temple_name, "temple-facts.html")
    if not facts_path.exists():
        return None, f"no temple-facts.html for {temple_name}"
    facts = facts_path.read_text().strip()
    if FACTS_MARKER not in facts:
        return None, (f"{facts_path.name} for {temple_name} carries no "
                      f"{FACTS_MARKER}> section")
    return compose_description(fixed, facts), None


def all_garment_ids(channel="tapstitch"):
    """Garment ids for one channel, or every id when channel is None.

    Tapstitch is the only channel. The filter stays so a config without
    "channel": "tapstitch" (a half-written new garment, say) is never swept
    into a run by accident."""
    ids = []
    for path in GARMENTS_DIR.glob("*.json"):
        cfg = json.loads(path.read_text())
        if channel is None or cfg.get("channel") == channel:
            ids.append(path.stem)
    return sorted(ids)
