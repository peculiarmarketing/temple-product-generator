"""One map from a colourway's file slug to the name the storefront shows.

WHY IT IS ONE MODULE AND NOT A DICT PER SCRIPT. Three scripts carried their own
copy of this map and every copy said `"gray": "Gray"`. That was fine only while
one slug meant one colour. It does not: crew_gray.jpg is a #B4B3B5 light heather
and hoodie_gray.jpg is a #6E7168 warm sage, two different garments' colourways
sharing a slug. A flat map cannot tell them apart, which is how both shipped to
the storefront under the same name, and a colour name on this store is not free:
shrine-theme-pro paints its swatch from one global list keyed on the name, so one
name can only ever have one hex. See config/swatches.json.

So the map is per garment, and it lives here so a rename is one edit rather than
three that can drift.

THESE NAMES ARE LOAD-BearING beyond the label a shopper reads:
  - they are written into on-model photo alt text, and bind_variants_to_onmodel.py
    pairs a variant to its photo by matching the variant's colour against the tail
    of that string. A name changed in one place and not the other binds nothing.
  - they must match the `shopify` field of the matching garment config's
    colorways, which is what shopify_fixups renames a freshly published product
    to. check_against_garments() below asserts exactly that.
  - every one of them must have a hex in config/swatches.json or its swatch
    renders as a white circle on the live product page.
"""
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
TRUE_COLORS = PROJECT_ROOT / "artifacts/photo-mockup-spike/true_colors_all.json"

# garment -> {file slug: storefront colour name}
NAMES = {
    "tee": {"black": "Black", "dark-gray": "Charcoal", "navy-blue": "Navy Blue",
            "maroon": "Maroon", "coffee": "Coffee",
            # Evan, 8 Oct 2026: Tapstitch 8082 Pink, 8083 "Blue", 8087 "Apricot"
            "pink": "Pink", "light-blue": "Light Blue", "cream": "Cream"},
    "crew": {"gray": "Heather Gray", "black": "Black"},
    "hoodie": {"navy-blue": "Navy Blue", "gray": "Gray", "black": "Black",
               "coffee": "Coffee", "mauve": "Mauve", "royal-blue": "Royal Blue",
               "eden-green": "Eden Green"},
}

# The key a colourway carries inside true_colors_all.json, where it differs from
# the storefront name. That file was measured before the 18 Sep 2026 renames and
# is deliberately left alone: it is a record of a measurement, not a naming
# decision, and rewriting it would break build_colourways.py in the spike folder.
_TRUE_KEY = {
    "tee": {"dark-gray": "Dark Gray"},
    "crew": {"gray": "Gray"},
}


def name_for(garment, slug):
    """The storefront colour name for one garment's colourway file slug."""
    try:
        return NAMES[garment][slug]
    except KeyError:
        raise KeyError(f"no storefront name for {garment!r} colourway {slug!r}. "
                       f"Known for {garment!r}: {sorted(NAMES.get(garment, {}))}")


def slug_for(garment, name):
    """The file slug for a storefront colour name, or None.

    Per garment on purpose: 'Black' is a slug-for-name lookup that only makes
    sense once you know which garment's black is meant."""
    return next((s for s, n in NAMES.get(garment, {}).items() if n == name), None)


def true_rgb(garment, slug):
    """The measured fabric RGB of one colourway, or None if never measured.

    Median fabric colour of the real Tapstitch mockup, white print excluded.
    Not the on-model photo, which is a lit recolour and reads lighter."""
    table = json.loads(TRUE_COLORS.read_text()).get(garment, {})
    key = _TRUE_KEY.get(garment, {}).get(slug, NAMES.get(garment, {}).get(slug))
    rgb = table.get(key)
    return tuple(rgb) if rgb else None


def check_against_garments(load_garment_config, garments=("tee", "crew", "hoodie")):
    """Assert this map and the garment configs name the same colours.

    They are two halves of one fact: this map names the PHOTO of a colourway and
    the config names the PRODUCT OPTION, and a product whose swatch photo and
    option value disagree binds no image for that colour. Drift between them is
    silent otherwise, which is the whole reason this function exists."""
    problems = []
    for garment in garments:
        cfg = load_garment_config(garment)
        declared = {c["shopify"] for c in cfg.get("colorways", []) if c.get("shopify")}
        mapped = set(NAMES.get(garment, {}).values())
        for missing in sorted(declared - mapped):
            problems.append(f"{garment}: garments/{garment}.json sells {missing!r} "
                            f"but colour_names.NAMES has no slug for it")
        for extra in sorted(mapped - declared):
            problems.append(f"{garment}: colour_names.NAMES has {extra!r} "
                            f"but garments/{garment}.json does not sell it")
    return problems
