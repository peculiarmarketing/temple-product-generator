#!/usr/bin/env python
"""The colour swatch registry: one hex per storefront colour name.

  python scripts/swatches.py render    # the block to paste into the theme by hand
  python scripts/swatches.py push      # write the registry straight into the live theme
  python scripts/swatches.py check     # does the live store agree with the registry
  python scripts/swatches.py check --strict-theme   # also require the live theme to match

WHY THIS EXISTS. shrine-theme-pro paints a colour swatch from a single theme
setting, `swatches_predefined_colors_list`, a rich-text list of `Name = #HEX`
lines. snippets/product-variant-options.liquid splits it on '</p><p>', splits
each line on '=', strips both halves and compares the left half to the option
value name with Liquid ==, which is exact and case sensitive. A name that is
not in that list gets custom_color = '', the swatch renders
style="--bg-color: " and the circle comes out white.

The store shipped with the list untouched at its factory default, twenty
generic CSS colours. Black and Maroon happen to be in it. Navy Blue, Coffee and
Dark Gray are not, which is the whole of the white-swatch bug: no product data
is wrong, and no product edit can fix it.

Because the list is keyed on the option value name and nothing else, a colour
name means the same hex everywhere on the store. Two garments cannot hold the
same name and different swatches. That is enforced here: config/swatches.json
is the one place a name gets a hex, and `check` fails if the live store carries
a colour name the registry has never heard of.

WRITING THE THEME. `push` edits ONE value inside the live theme's
config/settings_data.json and leaves every other byte of that file alone. It is
a surgical string replacement rather than a JSON round trip on purpose: that
file is auto-generated, Shopify rewrites it whenever anyone touches the theme
editor, and reserialising it would produce a diff across the whole file for a
one-field change. The result is re-parsed and compared key by key against what
was read, and the write is abandoned if anything but the swatch list moved.

The previous value is written to artifacts/swatches/ before every push, so a
bad list is one file away from being put back. Do not run `push` while the
theme editor is open on the same theme: the editor writes the whole file on
save and whichever of you saves last wins.

THEME READ SCOPE. `check` reads the live theme's own setting when the Admin
token carries `read_themes`, which closes the loop: registry, store and theme
all verified against each other. Without that scope it verifies the store
against the registry and says plainly that the theme half is unverified. Add
read_themes to the custom app in Shopify admin to get the full check.
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from shopify_client import ShopifyClient, ShopifyError  # noqa: E402

REGISTRY = PROJECT_ROOT / "config/swatches.json"
SETTING_ID = "swatches_predefined_colors_list"
COLOR_OPTION = "Color"


def load_registry():
    data = json.loads(REGISTRY.read_text())
    colors = data["colors"]
    for name, hex_value in colors.items():
        if not re.fullmatch(r"#[0-9A-Fa-f]{6}", hex_value):
            raise SystemExit(f"{REGISTRY.name}: {name!r} has a bad hex {hex_value!r}. "
                             f"The theme writes it straight into a CSS custom property, "
                             f"so anything it cannot parse renders as a white swatch, "
                             f"which is the exact failure this file exists to prevent.")
        if name != name.strip():
            raise SystemExit(f"{REGISTRY.name}: {name!r} has leading or trailing space. "
                             f"Liquid strips the list side but not the option value, "
                             f"so it would silently never match.")
    retired = set(data.get("_retired", {}).get("names", []))
    return colors, retired


def render_block(colors):
    """The exact value to paste into the theme setting.

    One <p> per colour because the theme splits on '</p><p>'. In the rich text
    editor that means pressing Enter between lines, not Shift+Enter: a
    Shift+Enter writes <br> inside one paragraph and every colour after the
    first would be swallowed into a single unparseable line."""
    return "".join(f"<p>{name} = {hex_value}</p>" for name, hex_value in colors.items())


def parse_block(raw):
    """Parse a theme setting value back into {name: hex}, the same way the
    theme's own Liquid does, so what this reports is what a shopper sees."""
    out = {}
    for chunk in (raw or "").split("</p><p>"):
        line = chunk.replace("<p>", "").replace("</p>", "")
        if "=" not in line:
            continue
        name, _, hex_value = line.partition("=")
        out[name.strip()] = hex_value.strip()
    return out


def live_theme_colors(client):
    """{name: hex} from the live theme, or None when the token cannot read themes."""
    try:
        data = client.gql("""
          query { themes(first: 1, roles: [MAIN]) { nodes { id name
            files(filenames: ["config/settings_data.json"], first: 1) { nodes {
              body { ... on OnlineStoreThemeFileBodyText { content } } } } } } }""")
    except ShopifyError as exc:
        if "read_themes" in str(exc):
            return None
        raise
    nodes = data["themes"]["nodes"]
    if not nodes:
        raise SystemExit("no published theme found.")
    content = nodes[0]["files"]["nodes"][0]["body"]["content"]
    settings = json.loads(re.sub(r"^\s*/\*.*?\*/", "", content, flags=re.S))
    return parse_block(settings["current"].get(SETTING_ID, ""))


def live_store_colors(client):
    """{colour name: [product titles]} across every product on the store."""
    out, cursor = {}, None
    while True:
        block = client.gql("""
          query($after: String) { products(first: 50, after: $after) {
            pageInfo { hasNextPage endCursor }
            nodes { title status options { name optionValues { name } } } } }""",
            {"after": cursor})["products"]
        for product in block["nodes"]:
            for option in product["options"]:
                if option["name"] != COLOR_OPTION:
                    continue
                for value in option["optionValues"]:
                    out.setdefault(value["name"], []).append(
                        f"{product['title']} [{product['status']}]")
        if not block["pageInfo"]["hasNextPage"]:
            return out
        cursor = block["pageInfo"]["endCursor"]


def missing_for(colors, names):
    """The colour names in `names` that the registry cannot paint. The gate."""
    return sorted(set(names) - set(colors))


def assert_ready(colors, names, where):
    """Hard gate, for the publish path. Raises SystemExit on any unpaintable
    colour rather than letting a product go live with white swatches."""
    missing = missing_for(colors, names)
    if missing:
        raise SystemExit(
            f"SWATCH GATE: {where} carries colour name(s) with no swatch defined: "
            f"{', '.join(repr(m) for m in missing)}.\n"
            f"The theme paints a swatch only for names in config/swatches.json, and an "
            f"undefined name renders a white circle on the live product page.\n"
            f"Fix: add the name and its hex to config/swatches.json, run "
            f"`python scripts/swatches.py render`, and paste the result into "
            f"Shopify admin > Online Store > Themes > Customize > Theme settings > "
            f"Color swatches > Predefined custom colors. Then re-run.")


def theme_file(client, filename):
    """(theme gid, raw file content) for the live theme."""
    nodes = client.gql("""
      query($f: [String!]) { themes(first: 1, roles: [MAIN]) { nodes { id name
        files(filenames: $f, first: 1) { nodes {
          body { ... on OnlineStoreThemeFileBodyText { content } } } } } } }""",
        {"f": [filename]})["themes"]["nodes"]
    if not nodes:
        raise SystemExit("no published theme found.")
    files = nodes[0]["files"]["nodes"]
    if not files:
        raise SystemExit(f"the live theme has no {filename}.")
    return nodes[0]["id"], files[0]["body"]["content"]


def settings_json(content):
    """The settings object, with the file's leading comment banner stripped."""
    return json.loads(re.sub(r"^\s*/\*.*?\*/", "", content, flags=re.S))


def cmd_push(args):
    colors, _ = load_registry()
    client = ShopifyClient()
    theme_gid, content = theme_file(client, "config/settings_data.json")
    before = settings_json(content)
    old_value = before["current"].get(SETTING_ID, "")
    new_value = render_block(colors)

    if old_value == new_value:
        print("the live theme already carries exactly this list. Nothing to do.")
        return 0

    # Surgical: replace only this key's value, so every other byte of an
    # auto-generated file survives untouched.
    pattern = re.compile(r'("' + SETTING_ID + r'"\s*:\s*)"(?:[^"\\]|\\.)*"')
    matches = pattern.findall(content)
    if len(matches) != 1:
        raise SystemExit(f"expected exactly one {SETTING_ID} in settings_data.json, "
                         f"found {len(matches)}. Refusing to guess which one to write.")
    patched = pattern.sub(lambda m: m.group(1) + json.dumps(new_value), content, count=1)

    # Prove nothing else moved before sending it.
    after = settings_json(patched)
    moved = [k for k in set(before["current"]) | set(after["current"])
             if before["current"].get(k) != after["current"].get(k)]
    if moved != [SETTING_ID]:
        raise SystemExit(f"the patch would change {moved}, not just {SETTING_ID}. "
                         f"Nothing sent.")
    if {k: v for k, v in before.items() if k != "current"} != \
       {k: v for k, v in after.items() if k != "current"}:
        raise SystemExit("the patch would change something outside `current`. Nothing sent.")

    print(f"theme  : {theme_gid}")
    for name in sorted(set(colors) | set(parse_block(old_value))):
        was = parse_block(old_value).get(name)
        now = colors.get(name)
        if was != now:
            print(f"  {name!r}  {was or '(absent)'} -> {now or '(removed)'}")

    if args.dry_run:
        print("\nDRY RUN, nothing sent.")
        return 0

    backup_dir = PROJECT_ROOT / "artifacts/swatches"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    backup = backup_dir / f"settings_data.{stamp}.before.json"
    backup.write_text(content)
    print(f"\nprevious file saved to {backup.relative_to(PROJECT_ROOT)}")

    result = client.gql("""
      mutation($themeId: ID!, $files: [OnlineStoreThemeFilesUpsertFileInput!]!) {
        themeFilesUpsert(themeId: $themeId, files: $files) {
          upsertedThemeFiles { filename }
          userErrors { filename code message } } }""",
        {"themeId": theme_gid,
         "files": [{"filename": "config/settings_data.json",
                    "body": {"type": "TEXT", "value": patched}}]})
    errs = result["themeFilesUpsert"]["userErrors"]
    if errs:
        raise SystemExit(f"theme write refused: {errs}")
    print(f"written: {len(colors)} colours into the live theme.")
    print("Verify with `python scripts/swatches.py check --strict-theme`.")
    return 0


def cmd_render(_args):
    colors, _ = load_registry()
    print("Paste this into Shopify admin > Online Store > Themes > Customize >")
    print("Theme settings > Color swatches > Predefined custom colors.")
    print("Clear the existing contents first. One line per colour, Enter between")
    print("lines (not Shift+Enter): the theme splits on paragraph breaks.\n")
    for name, hex_value in colors.items():
        print(f"{name} = {hex_value}")
    print(f"\n--- raw setting value, {len(colors)} colours ---")
    print(render_block(colors))


def cmd_check(args):
    colors, retired = load_registry()
    client = ShopifyClient()
    store = live_store_colors(client)
    print(f"registry : {len(colors)} colours in {REGISTRY.name}")
    print(f"store    : {len(store)} distinct colour names across the catalog\n")

    problems = []
    unpaintable = [n for n in missing_for(colors, store) if n not in retired]
    ignored = [n for n in missing_for(colors, store) if n in retired]
    if unpaintable:
        problems.append("store colours with no swatch")
        print("WHITE SWATCHES ON THE LIVE STORE:")
        for name in unpaintable:
            products = store[name]
            print(f"  {name!r}  on {len(products)} product(s), e.g. {products[0]}")
        print()
    if ignored:
        print(f"knowingly ignored (retired line): {', '.join(ignored)}\n")

    unused = sorted(set(colors) - set(store))
    if unused:
        print(f"defined but not on any product: {', '.join(unused)}")
        print("  Harmless. A name no product uses is simply never looked up.\n")

    theme = live_theme_colors(client)
    if theme is None:
        print("theme    : NOT VERIFIED. The Admin token has no read_themes scope, so")
        print("           what is actually pasted into the live theme could not be read.")
        print("           Add read_themes to the custom app to close this loop.")
        if args.strict_theme:
            problems.append("theme unreadable under --strict-theme")
    else:
        drift = {n: (colors[n], theme.get(n)) for n in colors if theme.get(n) != colors[n]}
        extra = sorted(set(theme) - set(colors))
        if drift:
            problems.append("theme does not match the registry")
            print("THEME DRIFT, registry vs what is live:")
            for name, (want, got) in sorted(drift.items()):
                print(f"  {name!r}  registry {want}  theme {got or '(absent)'}")
            print("  Fix: re-run `render` and paste the result into the theme.\n")
        else:
            print(f"theme    : matches the registry on all {len(colors)} colours.")
        if extra:
            print(f"theme also carries {len(extra)} name(s) no product uses: "
                  f"{', '.join(extra)}. Harmless.")

    if problems:
        print(f"\nFAIL: {'; '.join(problems)}")
        return 1
    print("\nOK: every colour on the store has a swatch.")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("render", help="print the block to paste into the theme")
    check = sub.add_parser("check", help="verify the live store against the registry")
    check.add_argument("--strict-theme", action="store_true",
                       help="fail when the live theme cannot be read, instead of warning")
    push = sub.add_parser("push", help="write the registry into the live theme setting")
    push.add_argument("--dry-run", action="store_true",
                      help="show what would change and send nothing")
    args = parser.parse_args()
    sys.exit({"render": cmd_render, "check": cmd_check,
          "push": cmd_push}[args.command](args) or 0)


if __name__ == "__main__":
    main()
