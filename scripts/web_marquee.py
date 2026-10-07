"""Keep the homepage temple marquee in step with the catalogue.

The marquee (theme/sections/pp-temple-marquee.liquid) shows one tile per tee in
the temple-tees collection, but only for a temple that has all three of:

  1. its art in the theme:    assets/pp-temple-<slug>.webp
  2. its stroke file there:   assets/pp-temple-<slug>.json (the city line lives here)
  3. a city line in snippets/pp-temple-city.liquid, generated from (2) by
     scripts/temple_city_snippet.py

A temple missing any of them is left off the marquee silently, so a new temple
published without its website files would simply never appear. This script is
the step that catches that. Run it after every publish run (tapstitch_run.py
runs `check` itself on the way out).

  check   read only. Lists every live tee's temple and what it is missing, in the
          repo and in the theme. Exit 1 if any temple is missing anything.
  sync    regenerates the snippet from theme/assets/, then runs check and prints
          the upload command for whatever the theme still lacks.

  --theme ID   the theme to compare against; default is the published one.

`scripts/sweep.py run` makes a new temple's two files (web_drawings.py build,
then pen_strokes.py), regenerates the snippet and uploads all three to the live
theme through the pipeline app's write_themes token. The upload command printed
below is the fallback for anything done outside a sweep.
"""
import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
THEME = ROOT / "theme"
SNIPPET = THEME / "snippets" / "pp-temple-city.liquid"
COLLECTION = "temple-tees"


def live_tee_slugs(client):
    """Slugs of every ACTIVE product in the tee collection, from its temple: tag."""
    q = """query($h: String!, $after: String) {
      collectionByHandle(handle: $h) {
        products(first: 100, after: $after) {
          nodes { handle status tags }
          pageInfo { hasNextPage endCursor }
        }
      }
    }"""
    slugs, after = {}, None
    while True:
        col = client.gql(q, {"h": COLLECTION, "after": after})["collectionByHandle"]
        if not col:
            raise SystemExit(f"No collection with handle {COLLECTION!r}.")
        page = col["products"]
        for p in page["nodes"]:
            if p["status"] != "ACTIVE":
                continue
            for t in p["tags"]:
                if t.startswith("temple:"):
                    slugs[t.removeprefix("temple:")] = p["handle"]
                    break
        if not page["pageInfo"]["hasNextPage"]:
            return slugs
        after = page["pageInfo"]["endCursor"]


def theme_files(client, theme_id):
    """(theme name, set of pp-temple asset filenames, snippet md5) or None if the
    token cannot read themes (it needs read_themes)."""
    if theme_id:
        q = 'query($id: ID!) { theme(id: $id) { id name } }'
        theme = client.gql(q, {"id": f"gid://shopify/OnlineStoreTheme/{theme_id}"})["theme"]
    else:
        q = '{ themes(first: 1, roles: [MAIN]) { nodes { id name } } }'
        nodes = client.gql(q)["themes"]["nodes"]
        theme = nodes[0] if nodes else None
    if not theme:
        raise SystemExit("Theme not found.")
    q = """query($id: ID!, $after: String) {
      theme(id: $id) {
        files(first: 250, after: $after,
              filenames: ["assets/pp-temple-*", "snippets/pp-temple-city.liquid"]) {
          nodes { filename checksumMd5 }
          pageInfo { hasNextPage endCursor }
        }
      }
    }"""
    names, snippet_md5, after = set(), None, None
    while True:
        files = client.gql(q, {"id": theme["id"], "after": after})["theme"]["files"]
        for f in files["nodes"]:
            if f["filename"].startswith("snippets/"):
                snippet_md5 = f["checksumMd5"]
            else:
                names.add(f["filename"])
        if not files["pageInfo"]["hasNextPage"]:
            return theme["name"], names, snippet_md5
        after = files["pageInfo"]["endCursor"]


def snippet_slugs(text):
    return {line.split("'")[1] for line in text.splitlines()
            if line.strip().startswith("when '")}


def gaps(slugs, repo_json, snippet, theme_names):
    """{slug: [what is missing]}. theme_names None means the theme was not read."""
    out = {}
    for slug in sorted(slugs):
        missing = []
        if slug not in repo_json:
            missing.append(f"theme/assets/pp-temple-{slug}.json (build it with pen_strokes.py)")
        if slug not in snippet:
            missing.append("its city line in snippets/pp-temple-city.liquid (run sync)")
        if theme_names is not None:
            for ext in ("webp", "json"):
                if f"assets/pp-temple-{slug}.{ext}" not in theme_names:
                    missing.append(f"assets/pp-temple-{slug}.{ext} in the theme (upload)")
        if missing:
            out[slug] = missing
    return out


def file_md5(path):
    import hashlib
    return hashlib.md5(path.read_bytes()).hexdigest()


def check(theme_id):
    from shopify_client import ShopifyClient, ShopifyError
    client = ShopifyClient()
    slugs = live_tee_slugs(client)
    repo_json = {p.stem.removeprefix("pp-temple-") for p in (THEME / "assets").glob("pp-temple-*.json")}
    snippet = snippet_slugs(SNIPPET.read_text()) if SNIPPET.exists() else set()
    try:
        theme_name, theme_names, theme_snippet_md5 = theme_files(client, theme_id)
    except ShopifyError as e:
        print(f"Could not read the theme ({str(e)[:120]}). The token needs read_themes; "
              "checking the repo only.")
        theme_name, theme_names, theme_snippet_md5 = None, None, None

    found = gaps(slugs, repo_json, snippet, theme_names)
    stale_snippet = (theme_names is not None and SNIPPET.exists()
                     and theme_snippet_md5 != file_md5(SNIPPET))
    where = f' against "{theme_name}"' if theme_name else ""
    print(f"Marquee check{where}: {len(slugs)} live tee temple(s), "
          f"{len(slugs) - len(found)} on the marquee.")
    for slug, missing in found.items():
        print(f"  MISSING {slug} ({slugs[slug]})")
        for m in missing:
            print(f"          - {m}")
    if stale_snippet:
        print("  The theme's snippets/pp-temple-city.liquid differs from the repo's. Upload it.")
    uploads = sorted({f"assets/pp-temple-{s}.{e}" for s, ms in found.items()
                      for e in ("webp", "json") if any(f".{e} in the theme" in m for m in ms)})
    if stale_snippet:
        uploads.append("snippets/pp-temple-city.liquid")
    if uploads:
        target = theme_id or "<published theme id>"
        print("\n`scripts/sweep.py run --temple <folder>` uploads these. By hand, from the Mac:")
        print(f"  shopify theme push --path theme --theme {target} --nodelete \\")
        print("    " + " \\\n    ".join(f"--only '{u}'" for u in uploads))
    return 1 if found or stale_snippet else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("command", choices=["check", "sync"])
    ap.add_argument("--theme", help="theme id; default is the published theme")
    a = ap.parse_args()
    if a.command == "sync":
        subprocess.run([sys.executable, str(ROOT / "scripts/temple_city_snippet.py")], check=True)
    return check(a.theme)


if __name__ == "__main__":
    sys.exit(main())
