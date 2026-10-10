"""Delete named files from an unpublished Shopify theme.

Cloud sessions cannot do this: the Shopify connector blocks themeFilesDelete. This
runs on the Mac with the PP Pipeline token in .env. It refuses the live (MAIN)
theme and only lists what it would delete unless --apply is given.

    python scripts/theme_delete_files.py --theme 194532671860 FILE [FILE ...]
    python scripts/theme_delete_files.py --theme 194532671860 --apply FILE [FILE ...]

Defaults to the seven unused spec-preview and debug files left on "Claude Code V4"
on 10 Oct 2026 when no FILE is given.
"""
import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from shopify_client import ShopifyClient  # noqa: E402

V4_LEFTOVERS = [
    "templates/index.spec-a.json",
    "templates/index.spec-b.json",
    "templates/index.spec-c.json",
    "templates/index.spec-light.json",
    "templates/index.dbg-tmp.json",
    "templates/search.dbg-tmp.json",
    "sections/pp-debug-tmp.liquid",
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--theme", required=True, help="numeric theme id")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("files", nargs="*")
    args = ap.parse_args()
    files = args.files or V4_LEFTOVERS
    gid = f"gid://shopify/OnlineStoreTheme/{args.theme}"

    client = ShopifyClient()
    theme = client.gql(
        """query($id: ID!, $f: [String!]) { theme(id: $id) { name role
           files(first: 50, filenames: $f) { nodes { filename } } } }""",
        {"id": gid, "f": files})["theme"]
    if not theme:
        raise SystemExit(f"no theme {args.theme}")
    if theme["role"] == "MAIN":
        raise SystemExit(f"{theme['name']} is the live theme; refusing.")
    present = [n["filename"] for n in theme["files"]["nodes"]]
    missing = sorted(set(files) - set(present))
    print(f"{theme['name']} ({theme['role']}): {len(present)} to delete")
    for f in present:
        print(f"  {f}")
    for f in missing:
        print(f"  (already gone) {f}")
    if not present or not args.apply:
        if present:
            print("Dry run. Add --apply to delete.")
        return 0

    out = client.gql(
        """mutation($id: ID!, $f: [String!]!) { themeFilesDelete(themeId: $id, files: $f) {
           deletedThemeFiles { filename } userErrors { filename code message } } }""",
        {"id": gid, "f": present})["themeFilesDelete"]
    for e in out["userErrors"]:
        print(f"  error {e['filename']}: {e['message']}")
    print(f"deleted {len(out['deletedThemeFiles'] or [])}")
    return 1 if out["userErrors"] else 0


if __name__ == "__main__":
    sys.exit(main())
