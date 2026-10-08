#!/usr/bin/env python
"""The temple sweep: a new temple folder in, a finished temple on the live site out.

Evan, 7 Oct 2026: "run a sweep" should find every new temple folder (the only
file he drops in is the original design PNG), make everything the products need,
publish them, and finish every website step, so that when the sweep is over the
live site is complete. Saying "run a sweep" is his go-ahead to publish.

THREE COMMANDS.

  scan     read only, no network. Every temple folder and what it still needs.
           `--json` for the skill. A temple is one of:
             live             every garment is live; nothing to do here
             finishing        live, but a sweep stopped after publishing it
                              (gallery, drawing, ...): `run` finishes it
             needs-research   art is there, but no verified location in
                              temples.json and/or no temple-facts.html. Research
                              is Claude's job (the skill), not this script's.
             ready            art, location and facts all present: `run` takes it
             no-art           no SVG pair and no single source PNG to trace

  run      LIVE, no undo. Takes temples through every step below, in order. Each
           step is idempotent and skips what is already done, so a run that
           stopped anywhere is finished by running it again.

             build      trace the PNG if needed, flatten the print files
             proof      render the proof sheet (kept as the record of what shipped)
             approve    record the approval: the automated gates passed and the
                        sweep itself is Evan's go (decisions.md, 7 Oct 2026)
             publish    tapstitch_run.py --apply --publish: Tapstitch product,
                        description, distribute, product type, art card, colour
                        renames, swatch gate, variant images, facts backup
             tags       temple:, garment:, country: and state: tags, which the
                        marquee, the product band and the state collections read
             gallery    on-model composites (fold C), then the standard gallery:
                        on-model back in the flat-lay colour in slot 1
             drawing    pen drawing and marquee files, written straight into the
                        live theme and read back
             download   the black SVG into Temples/All/ for the Temple Art File
             artfile    the temple as a new option on the Temple Art File product,
                        sold out until its download file is attached
           Then once for the whole run: the Easify dropdown CSV, the facts mirror
           check, and `verify` on every temple it touched.

  verify   read only. Proves each temple is complete on the live site: all three
           products ACTIVE with the right title, type, tags and description, the
           gallery in the standard order with every colour bound to its own
           on-model photo, no Tapstitch colour names, the tee in the marquee
           collection, the drawing files and city line in the live theme, the
           Easify CSV rows, and the download file.

  python scripts/sweep.py scan [--json]
  python scripts/sweep.py run --temple "St. Paul" [--temple ...]   (or --all-ready)
  python scripts/sweep.py verify --temple "St. Paul"               (or --all)

WHAT STAYS MANUAL, because neither app has an API for it:
  - the Easify CSV import. The sweep writes artifacts/easify/option-sets.csv and
    says when it changed.
  - attaching the Temple Art File download in the Digital Products app (it opens
    a file picker for the merchant). The sweep adds the temple's option, sold out
    until then, and names the file to attach (Temples/All/<Temple> black.svg).
"""

import argparse
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import generate  # noqa: E402
import ledger  # noqa: E402
from layout import TEMPLES_DIR, working_path  # noqa: E402

PY = sys.executable
SCRIPTS = ROOT / "scripts"
THEME = ROOT / "theme"
DRAWINGS_OUT = ROOT / "artifacts" / "web_drawings"
COMPOSITES = ROOT / "artifacts" / "photo-mockup-spike" / "composites-lift"
FACTS_MIRROR = ROOT / "artifacts" / "temple-facts"
EASIFY_CSV = ROOT / "artifacts" / "easify" / "option-sets.csv"
# Which temples the sweep has started and which it has verified. Once a temple's
# products are live the ledger calls it done, but the tags, gallery, drawing and
# download steps come after that; this is what tells the next sweep a temple
# still has finishing to do.
SWEEP_STATE = ROOT / "artifacts" / "tapstitch" / "sweep-state.json"
STORE_URL = "https://peculiarpeopleco.com/products/"

STEPS = ("build", "proof", "approve", "publish", "tags", "gallery", "drawing", "download",
         "artfile")
ART_FILE_HANDLE = "temple-art-file"
ART_FILE_PARENT = "Salt Lake"      # first option value; every other temple follows A to Z

US_STATES = {
    "ALABAMA", "ALASKA", "ARIZONA", "ARKANSAS", "CALIFORNIA", "COLORADO", "CONNECTICUT",
    "DELAWARE", "FLORIDA", "GEORGIA", "HAWAII", "IDAHO", "ILLINOIS", "INDIANA", "IOWA",
    "KANSAS", "KENTUCKY", "LOUISIANA", "MAINE", "MARYLAND", "MASSACHUSETTS", "MICHIGAN",
    "MINNESOTA", "MISSISSIPPI", "MISSOURI", "MONTANA", "NEBRASKA", "NEVADA",
    "NEW HAMPSHIRE", "NEW JERSEY", "NEW MEXICO", "NEW YORK", "NORTH CAROLINA",
    "NORTH DAKOTA", "OHIO", "OKLAHOMA", "OREGON", "PENNSYLVANIA", "RHODE ISLAND",
    "SOUTH CAROLINA", "SOUTH DAKOTA", "TENNESSEE", "TEXAS", "UTAH", "VERMONT", "VIRGINIA",
    "WASHINGTON", "WEST VIRGINIA", "WISCONSIN", "WYOMING",
}


class StepFailed(Exception):
    pass


# ---------------------------------------------------------------- names

def tag_slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def temple_slug(folder):
    """The temple: tag and the theme file name. One rule, web_drawings.slug_for,
    because the product band finds its drawing by this exact string."""
    from web_drawings import slug_for
    return slug_for(folder)


def expected_tags(folder, garment_id, location_line):
    """The four tags every live temple product carries (read off the store,
    7 Oct 2026): temple:boise, garment:tee, country:usa, state:idaho. Outside
    the US there is no state tag and the country is the location line's last part
    (ROME, ITALY -> country:italy). Tapstitch publishes with no tags at all."""
    region = location_line.rsplit(",", 1)[-1].strip().upper()
    tags = [f"temple:{temple_slug(folder)}", f"garment:{garment_id}"]
    if region in US_STATES:
        tags += ["country:usa", f"state:{tag_slug(region)}"]
    else:
        tags.append(f"country:{tag_slug(region)}")
    return sorted(tags)


def place_token(folder):
    """How the product TITLE names the temple; alt text follows the title."""
    return generate.load_manifest(folder)["place_tokens"]["default"]


# ---------------------------------------------------------------- state

def load_state():
    return json.loads(SWEEP_STATE.read_text()) if SWEEP_STATE.exists() else {}


def mark(folder, **fields):
    from datetime import datetime
    st = load_state()
    rec = st.setdefault(folder, {})
    for k, v in fields.items():
        rec[k] = v or datetime.now().isoformat(timespec="seconds")
    SWEEP_STATE.parent.mkdir(parents=True, exist_ok=True)
    SWEEP_STATE.write_text(json.dumps(st, indent=2, sort_keys=True) + "\n")


# ---------------------------------------------------------------- scan

def location_entry(folder):
    data = json.loads((ROOT / "temples.json").read_text())
    return data.get(folder) or data.get(folder.rstrip("*").strip())


def has_location(folder):
    if working_path(folder, "manifest.json").exists():
        return True
    entry = location_entry(folder)
    return bool(entry and entry.get("verified"))


def has_facts(folder):
    path = working_path(folder, "temple-facts.html")
    return path.exists() and generate.FACTS_MARKER in path.read_text()


def has_art(folder):
    path = TEMPLES_DIR / folder
    try:
        generate.detect_art_files(path)
        return True
    except SystemExit:
        pass
    from trace_art import find_source_png
    try:
        return find_source_png(path, folder) is not None
    except SystemExit:
        return False        # several candidate PNGs: Evan has to name one


def classify(folder, rows, garment_ids, art, location, facts, sweep=None):
    """(status, [what is missing]). Pure, so it is tested without a Temples folder.

    `sweep` is this folder's record in sweep-state.json, if any. The 45 temples
    published before the sweep existed have none and count as live."""
    states = {r["garment"]: r["state"] for r in rows if r["temple"] == folder}
    if garment_ids and all(states.get(g) == "live" for g in garment_ids):
        if sweep and not sweep.get("verified_at"):
            return "finishing", ["the steps after publishing"]
        return "live", []
    if not art:
        return "no-art", ["the design PNG (one PNG in the folder, ideally named "
                          f"'{folder.rstrip('*').strip()}.png')"]
    missing = []
    if not location:
        missing.append("location")
    if not facts:
        missing.append("facts")
    return ("needs-research", missing) if missing else ("ready", [])


def scan():
    if not TEMPLES_DIR.is_dir():
        raise SystemExit(f"No Temples folder at {TEMPLES_DIR}. The sweep runs on the Mac, "
                         f"where the repo sits beside Temples/.")
    garment_ids = generate.all_garment_ids("tapstitch")
    rows = ledger.load()["rows"]
    state = load_state()
    import flatten
    out = []
    for f in flatten.temple_folders():
        name = f.name
        status, missing = classify(name, rows, garment_ids, has_art(name),
                                   has_location(name), has_facts(name), state.get(name))
        out.append({"temple": name, "status": status, "missing": missing})
    return out


def cmd_scan(a):
    found = scan()
    if a.json:
        print(json.dumps(found, indent=2))
        return 0
    todo = [t for t in found if t["status"] != "live"]
    print(f"{len(found)} temple folders, {len(found) - len(todo)} live, {len(todo)} to do.\n")
    for t in todo:
        extra = f"  needs: {', '.join(t['missing'])}" if t["missing"] else ""
        print(f"  {t['status']:<15} {t['temple']}{extra}")
    if not todo:
        print("  Nothing new. Every temple folder is live.")
    return 0


# ---------------------------------------------------------------- run helpers

def sh(args, label, check=True):
    """Run one pipeline script, streaming its output. Returns (code, output)."""
    cmd = [PY, str(SCRIPTS / args[0]), *args[1:]]
    print(f"    $ {' '.join(cmd[1:])}", flush=True)
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    text = (r.stdout or "") + (r.stderr or "")
    for line in text.rstrip().splitlines()[-40:]:
        print(f"      {line}")
    if check and r.returncode != 0:
        raise StepFailed(f"{label}: {args[0]} exited {r.returncode}")
    return r.returncode, text


def rows_for(folder):
    return {r["garment"]: r for r in ledger.load()["rows"] if r["temple"] == folder}


def preflight():
    """Everything that would stop a run halfway, checked before the first write."""
    problems = []
    if not (ROOT / ".env").exists():
        problems.append(".env is missing (SHOPIFY_STORE_DOMAIN, SHOPIFY_ADMIN_TOKEN)")
    if not TEMPLES_DIR.is_dir():
        problems.append(f"no Temples folder at {TEMPLES_DIR}; the sweep runs on the Mac")
    for mod in ("cv2", "scipy", "skimage"):
        if importlib.util.find_spec(mod) is None:
            problems.append(f"python package {mod} is missing (pen_strokes.py needs it): "
                            f"./.venv.nosync/bin/pip install -r requirements.txt")
    photos = ROOT / "artifacts" / "photo-mockup-spike" / "colourway-photos"
    if not any(photos.glob("*.png")):
        problems.append(f"no colourway photos in {photos.relative_to(ROOT)}; the on-model "
                        f"composites need them (gitignored, on the Mac)")
    else:
        # Every colour each garment sells needs a blank to composite onto, from
        # colourway-photos/ or the committed recolours composite_catalog.py also
        # reads (artifacts/onmodel-front/blanks/back_<garment>_<slug>.jpg).
        import build_product_gallery
        extra = ROOT / "artifacts" / "onmodel-front" / "blanks"
        for g, slugs in build_product_gallery.ORDER.items():
            for slug in slugs:
                if not ((photos / f"{g}_{slug}.png").exists()
                        or (extra / f"back_{g}_{slug}.jpg").exists()):
                    problems.append(f"no blank photo for the {g} in {slug}: add "
                                    f"{g}_{slug}.png to {photos.relative_to(ROOT)}")
    if problems:
        return problems
    code, out = sh(["tapstitch_login.py", "--check"], "login", check=False)
    if code != 0:
        problems.append("the Tapstitch session has expired: run "
                        "scripts/tapstitch_login.py and log in once")
    code, out = sh(["tapstitch_publish.py", "check"], "check", check=False)
    if code != 0:
        problems.append("tapstitch_publish.py check reports blockers (output above)")
    return problems


# ---------------------------------------------------------------- the steps

def step_build(folder, garment_ids):
    rows = rows_for(folder)
    if all(g in rows and rows[g]["state"] not in ledger.BUILD_STATES for g in garment_ids):
        return "print files already built"
    sh(["tapstitch_build.py", "--temple", folder], "build")
    rows = rows_for(folder)
    bad = {g: rows.get(g, {}) for g in garment_ids
           if rows.get(g, {}).get("state") in (None, "art-missing", "error", "art-ok")}
    if bad:
        why = "; ".join(f"{g}: {r.get('state')} {r.get('problems') or ''}" for g, r in bad.items())
        raise StepFailed(f"build did not produce clean print files ({why})")
    return "print files built"


def step_proof(folder, garment_ids):
    rows = rows_for(folder)
    if not any(rows[g]["state"] == "file-built" for g in garment_ids):
        return "already approved earlier"
    sh(["tapstitch_preview.py", "--temple", folder], "proof")
    return "proof sheet in artifacts/tapstitch-previews/"


def step_approve(folder, garment_ids):
    rows = rows_for(folder)
    if not any(rows[g]["state"] == "file-built" for g in garment_ids):
        return "already approved"
    sh(["tapstitch_approve.py", "--temple", folder], "approve")
    return "approved by the sweep"


def step_publish(folder, garment_ids):
    rows = rows_for(folder)
    if all(rows[g]["state"] == "live" for g in garment_ids):
        return "all products already live"
    sh(["tapstitch_run.py", "--apply", "--publish", "--temple", folder], "publish",
       check=False)
    rows = rows_for(folder)
    stuck = [f"{g}: {rows[g]['state']} {rows[g].get('problems') or ''}"
             for g in garment_ids if rows[g]["state"] != "live"]
    if stuck:
        raise StepFailed("not live after the publish run (re-running the sweep "
                         "resumes each row where it stopped): " + "; ".join(stuck))
    return "live"


def step_tags(folder, garment_ids, client):
    location = generate.load_manifest(folder)["location_line"]
    added = []
    for g in garment_ids:
        handle = rows_for(folder)[g]["shopify_handle"]
        p = client.gql("query($h: String!) { productByHandle(handle: $h) { id tags } }",
                       {"h": handle})["productByHandle"]
        if p is None:
            raise StepFailed(f"no product at {handle}")
        want = [t for t in expected_tags(folder, g, location) if t not in p["tags"]]
        if not want:
            continue
        errs = client.gql("""mutation($id: ID!, $t: [String!]!) { tagsAdd(id: $id, tags: $t) {
            userErrors { message } } }""", {"id": p["id"], "t": want})["tagsAdd"]["userErrors"]
        if errs:
            raise StepFailed(f"{handle}: tagsAdd refused: {errs}")
        added.append(f"{g} +{','.join(want)}")
    return "tags added: " + "; ".join(added) if added else "tags already present"


def step_gallery(folder, garment_ids):
    token = place_token(folder)
    for g in garment_ids:
        outdir = COMPOSITES / g
        sh(["composite_catalog.py", "--garment", g, "--outdir", str(outdir),
            "--temple", folder], f"composite {g}")
        if not (outdir / folder).is_dir():
            raise StepFailed(f"no {g} composites were written for {folder}")
        _, out = sh(["build_garment_catalog.py", "--garment", g, "--composites",
                     str(outdir), "--temple", token], f"gallery {g}")
        if ("FAILED" in out or "no composites under" in out
                or re.search(rf"^0 {g} product\(s\)", out, re.M)):
            raise StepFailed(f"{g} gallery build reported a failure (output above)")
    return "on-model photos and standard gallery on all garments"


def md5(b):
    return hashlib.md5(b).hexdigest()


def step_drawing(folder, client):
    """The pen drawing and marquee files, uploaded to the published theme.

    Uploads ONLY this temple's two files and the city-line snippet. Never
    `web_drawings.py push`: it uploads every first-generation stroke file left in
    artifacts/web_drawings/ whose checksum differs from the live theme, and the
    live theme holds the version 2 files from pen_strokes.py, so a push would
    quietly put all 45 temples back on the old random-order drawing.

    The PP Pipeline app token carries write_themes (decisions.md, 18 Sep 2026)
    and themeFilesUpsert accepts the published theme from it, which swatches.py
    push already relies on. The Shopify CLI upload from the Mac is not needed.
    """
    import web_drawings as WD
    slug = temple_slug(folder)
    repo_json = THEME / "assets" / f"pp-temple-{slug}.json"
    first_json = DRAWINGS_OUT / f"pp-temple-{slug}.json"
    webp = DRAWINGS_OUT / f"pp-temple-{slug}.webp"
    notes = []
    if not repo_json.exists() or not webp.exists():
        sh(["web_drawings.py", "build", "--temple", folder], "drawing build")
        notes.append("drawing built")
    if not repo_json.exists():
        sh(["pen_strokes.py", str(webp), str(first_json), str(repo_json)], "pen strokes")
        notes.append("strokes ordered")
    sh(["temple_city_snippet.py"], "city line")

    files = {f"assets/pp-temple-{slug}.json": repo_json.read_bytes(),
             "snippets/pp-temple-city.liquid":
                 (THEME / "snippets" / "pp-temple-city.liquid").read_bytes()}
    if webp.exists():
        files[f"assets/pp-temple-{slug}.webp"] = webp.read_bytes()
    theme = WD.main_theme_id(client)
    remote = WD.remote_checksums(client, theme, list(files))
    todo = {n: b for n, b in files.items() if remote.get(n) != md5(b)}
    if todo:
        WD.upsert_theme_files(client, theme, todo)
        after = WD.remote_checksums(client, theme, list(todo))
        wrong = [n for n in todo if after.get(n) != md5(todo[n])]
        if wrong:
            raise StepFailed(f"theme read-back mismatch on {wrong}")
        notes.append(f"uploaded {', '.join(sorted(todo))}")
    if f"assets/pp-temple-{slug}.webp" not in remote and not webp.exists():
        raise StepFailed(f"no pp-temple-{slug}.webp locally or in the theme")
    return "; ".join(notes) or "theme already has the drawing"


def step_download(folder):
    before = (generate.ALL_ART_DIR / f"{place_token(folder)} black.svg").exists()
    generate.mirror_black_art(folder, generate.load_manifest(folder))
    return "already in Temples/All" if before else "copied to Temples/All"


def art_file_order(values):
    """Salt Lake first, every other temple A to Z: the order the live product uses."""
    rest = sorted((v for v in values if v != ART_FILE_PARENT), key=str.casefold)
    return ([ART_FILE_PARENT] if ART_FILE_PARENT in values else []) + rest


def step_artfile(folder, client):
    """Add this temple to the Temple Art File's Temple option.

    The new variant copies the parent's price and shipping setting, and is set to
    DENY at zero stock so it shows sold out rather than selling a download that
    has no file yet. Attaching the file in the Digital Products app is the one
    part no API reaches; that app then makes it purchasable.
    """
    token = place_token(folder)
    p = client.gql("""query($h: String!) { productByHandle(handle: $h) { id
        options { name optionValues { name } }
        variants(first: 250) { nodes { title price taxable
          inventoryItem { requiresShipping } } } } }""", {"h": ART_FILE_HANDLE})["productByHandle"]
    if p is None:
        raise StepFailed(f"no product at {ART_FILE_HANDLE}")
    opt = p["options"][0]
    values = [v["name"] for v in opt["optionValues"]]
    note = f"{token} already an option"
    if token not in values:
        ref = next(v for v in p["variants"]["nodes"] if v["title"] == ART_FILE_PARENT)
        res = client.gql("""mutation($id: ID!, $v: [ProductVariantsBulkInput!]!) {
            productVariantsBulkCreate(productId: $id, variants: $v) {
              userErrors { field message } } }""",
            {"id": p["id"], "v": [{
                "optionValues": [{"optionName": opt["name"], "name": token}],
                "price": ref["price"], "taxable": ref["taxable"],
                "inventoryPolicy": "DENY",
                "inventoryItem": {"requiresShipping": ref["inventoryItem"]["requiresShipping"]},
            }]})["productVariantsBulkCreate"]
        if res["userErrors"]:
            raise StepFailed(f"Art File variant refused: {res['userErrors']}")
        values.append(token)
        note = f"{token} added, sold out until its file is attached"
    order = art_file_order(values)
    if order != values:
        res = client.gql("""mutation($id: ID!, $o: [OptionReorderInput!]!) {
            productOptionsReorder(productId: $id, options: $o) { userErrors { field message } } }""",
            {"id": p["id"], "o": [{"name": opt["name"],
                                   "values": [{"name": v} for v in order]}]})["productOptionsReorder"]
        if res["userErrors"]:
            raise StepFailed(f"Art File reorder refused: {res['userErrors']}")
    return note


def art_file_needs_upload(client, tokens):
    """The tokens whose Art File variant still cannot sell (no file attached)."""
    p = client.gql("""query($h: String!) { productByHandle(handle: $h) {
        variants(first: 250) { nodes { title inventoryPolicy inventoryQuantity } } } }""",
        {"h": ART_FILE_HANDLE})["productByHandle"]
    by = {v["title"]: v for v in (p or {}).get("variants", {}).get("nodes", [])}
    return [t for t in tokens if t in by and by[t]["inventoryPolicy"] == "DENY"
            and (by[t]["inventoryQuantity"] or 0) <= 0]


def run_temple(folder, garment_ids, client):
    """[(step, ok, note)] for one temple. Stops at the first failed step."""
    done = []
    for step in STEPS:
        print(f"  [{step}]", flush=True)
        try:
            if step == "build":
                note = step_build(folder, garment_ids)
            elif step == "proof":
                note = step_proof(folder, garment_ids)
            elif step == "approve":
                note = step_approve(folder, garment_ids)
            elif step == "publish":
                note = step_publish(folder, garment_ids)
            elif step == "tags":
                note = step_tags(folder, garment_ids, client)
            elif step == "gallery":
                note = step_gallery(folder, garment_ids)
            elif step == "drawing":
                note = step_drawing(folder, client)
            elif step == "download":
                note = step_download(folder)
            else:
                note = step_artfile(folder, client)
        except (Exception, SystemExit) as e:
            # SystemExit too: the pipeline modules raise it for user-facing stops.
            msg = f"{type(e).__name__}: {e}" if not isinstance(e, StepFailed) else str(e)
            print(f"    FAILED {msg}")
            done.append((step, False, msg[:400]))
            return done
        print(f"    ok: {note}")
        done.append((step, True, note))
    return done


def cmd_run(a):
    garment_ids = generate.all_garment_ids("tapstitch")
    found = {t["temple"]: t for t in scan()}
    if a.all_ready:
        wanted = [n for n, t in found.items() if t["status"] in ("ready", "finishing")]
    else:
        wanted = []
        for name in a.temple:
            hit = next((n for n in found if n.rstrip("*").strip().casefold()
                        == name.rstrip("*").strip().casefold()), None)
            if hit is None:
                raise SystemExit(f"no temple folder named {name!r}")
            wanted.append(hit)
    not_ready = [(n, found[n]) for n in wanted if found[n]["status"] in ("no-art", "needs-research")]
    if not_ready:
        for n, t in not_ready:
            print(f"  skipped {n}: {t['status']} ({', '.join(t['missing'])})")
        wanted = [n for n in wanted if n not in dict(not_ready)]
    if not wanted:
        print("Nothing ready to run. `sweep.py scan` lists what each temple needs.")
        return 0

    print(f"Preflight for {len(wanted)} temple(s): {', '.join(wanted)}")
    problems = preflight()
    if problems:
        print("\nSTOPPED before any write:")
        for p in problems:
            print(f"  - {p}")
        return 1

    from shopify_client import ShopifyClient
    client = ShopifyClient()
    easify_before = md5(EASIFY_CSV.read_bytes()) if EASIFY_CSV.exists() else None
    results = {}
    for n, folder in enumerate(wanted, 1):
        print(f"\n[{n}/{len(wanted)}] {folder}")
        if not load_state().get(folder, {}).get("started_at"):
            mark(folder, started_at=None)
        results[folder] = run_temple(folder, garment_ids, client)

    print("\n[whole run]")
    sh(["easify_options.py", "sync"], "easify", check=False)
    sh(["mirror_facts.py"], "facts mirror", check=False)
    easify_after = md5(EASIFY_CSV.read_bytes()) if EASIFY_CSV.exists() else None

    print("\n[verify]")
    verified = {}
    for folder, steps in results.items():
        if all(ok for _, ok, _ in steps):
            verified[folder] = verify_temple(folder, garment_ids, client)
            if not verified[folder]:
                mark(folder, verified_at=None)

    print("\n" + "=" * 70 + "\nSWEEP SUMMARY\n")
    failed = False
    for folder, steps in results.items():
        bad = next(((s, note) for s, ok, note in steps if not ok), None)
        probs = verified.get(folder)
        if bad:
            failed = True
            print(f"  STOPPED  {folder}: at {bad[0]}: {bad[1]}")
        elif probs:
            failed = True
            print(f"  CHECK    {folder}: published, but verify found:")
            for p in probs:
                print(f"             - {p}")
        else:
            print(f"  DONE     {folder}: live and verified on the site")
    if easify_after != easify_before:
        print("\nMANUAL: artifacts/easify/option-sets.csv changed. Import it in the Easify "
              "app so the new temples appear in every product's Temple dropdown.")
    finished = [f for f, steps in results.items() if all(ok for _, ok, _ in steps)]
    try:
        waiting = art_file_needs_upload(client, [place_token(f) for f in finished])
    except Exception:
        waiting = []
    if waiting:
        print("\nMANUAL: attach each download in the Digital Products app (Temple Art File), "
              "which makes the option purchasable:")
        for t in waiting:
            print(f"  - {t}: Temples/All/{t} black.svg")
    print("\nCommit and push: the ledger and sweep-state.json, temples.json, artifacts/temple-facts/, "
          "artifacts/description-ledgers/, artifacts/easify/, theme/assets/, theme/snippets/.")
    return 1 if failed else 0


# ---------------------------------------------------------------- verify

PRODUCT_Q = """query($h: String!) { productByHandle(handle: $h) {
  id title status productType tags descriptionHtml
  media(first: 60) { nodes { id alt } }
  variants(first: 100) { nodes { title media(first: 1) { nodes { id } } } } } }"""


def verify_product(client, folder, garment_id, row):
    import art_images
    import build_product_gallery as gallery
    import colour_names
    from tapstitch_run import stale_colorways

    cfg = generate.load_garment_config(garment_id)
    handle = row.get("shopify_handle")
    if row.get("state") != "live" or not handle:
        return [f"{garment_id}: ledger says {row.get('state')}, not live"]
    p = client.gql(PRODUCT_Q, {"h": handle})["productByHandle"]
    if p is None:
        return [f"{garment_id}: no product at {handle}"]
    probs = []
    say = lambda m: probs.append(f"{garment_id}: {m}")  # noqa: E731
    if p["status"] != "ACTIVE":
        say(f"status {p['status']}")
    title = generate.title_for(folder, garment_id, cfg)
    if p["title"].strip() != title:
        say(f"title {p['title']!r}, expected {title!r}")
    ptype = cfg.get("shopify_product_type") or cfg.get("product_type")
    if ptype and p["productType"] != ptype:
        say(f"product type {p['productType']!r}, expected {ptype!r}")
    location = generate.load_manifest(folder)["location_line"]
    missing_tags = [t for t in expected_tags(folder, garment_id, location) if t not in p["tags"]]
    if missing_tags:
        say(f"missing tags {missing_tags}")
    if generate.FACTS_MARKER not in (p["descriptionHtml"] or ""):
        say("description has no temple facts section")

    name = place_token(folder)
    have = [m.get("alt") or "" for m in p["media"]["nodes"]]
    if any(not a for a in have):
        say(f"{sum(1 for a in have if not a)} image(s) without alt text")
    art_alt = next((a for a in have if a.startswith(art_images.ALT_MARKER)), None)
    if not art_alt:
        say("no art close-up card")
    want = [a for a in gallery.gallery_order(name, garment_id, art_alt) if a in have]
    if have != want:
        say("gallery is not in the standard order")
    lead = gallery.on_model_alt(name, garment_id, gallery.flat_colour(garment_id))
    if not have or have[0] != lead:
        say(f"slot 1 (the collection thumbnail) is not {lead!r}")
    by_alt = {m.get("alt"): m["id"] for m in p["media"]["nodes"]}
    for v in p["variants"]["nodes"]:
        colour = v["title"].split(" / ")[0]
        slug = colour_names.slug_for(garment_id, colour)
        target = by_alt.get(gallery.on_model_alt(name, garment_id, slug)) if slug else None
        cur = (v["media"]["nodes"] or [{}])[0].get("id")
        if not target or cur != target:
            say(f"variant {v['title']} is not bound to its on-model photo")
            break
    stale = stale_colorways(client, garment_id, handle)
    if stale:
        say(f"Tapstitch colour names still on the product: {stale}")
    return probs


def verify_temple(folder, garment_ids, client):
    """Every problem left on the live site for this temple. Empty means done."""
    import web_marquee as WM
    rows = rows_for(folder)
    probs = []
    for g in garment_ids:
        try:
            probs += verify_product(client, folder, g, rows.get(g, {}))
        except (Exception, SystemExit) as e:
            probs.append(f"{g}: could not verify ({type(e).__name__}: {str(e)[:160]})")

    slug = temple_slug(folder)
    if slug not in WM.live_tee_slugs(client):
        probs.append(f"the tee is not in the {WM.COLLECTION} collection (marquee source)")
    _, names, theme_snippet = WM.theme_files(client, None)
    for ext in ("webp", "json"):
        if f"assets/pp-temple-{slug}.{ext}" not in names:
            probs.append(f"theme is missing assets/pp-temple-{slug}.{ext}")
    if slug not in WM.snippet_slugs(WM.SNIPPET.read_text()):
        probs.append("no city line in snippets/pp-temple-city.liquid")
    elif theme_snippet != WM.file_md5(WM.SNIPPET):
        probs.append("the theme's city-line snippet is older than the repo's")

    csv_text = EASIFY_CSV.read_text() if EASIFY_CSV.exists() else ""
    for g in garment_ids:
        handle = rows.get(g, {}).get("shopify_handle")
        if handle and f"{STORE_URL}{handle}" not in csv_text:
            probs.append(f"{g}: not in the Easify CSV")
    art = client.gql("""query($h: String!) { productByHandle(handle: $h) {
        options { optionValues { name } } } }""", {"h": ART_FILE_HANDLE})["productByHandle"]
    if art and place_token(folder) not in [v["name"] for v in art["options"][0]["optionValues"]]:
        probs.append("not an option on the Temple Art File")
    if not (generate.ALL_ART_DIR / f"{place_token(folder)} black.svg").exists():
        probs.append("no download file in Temples/All")
    if not (FACTS_MIRROR / f"{folder.rstrip('*').strip()}.html").exists():
        probs.append("facts not mirrored into artifacts/temple-facts/")
    for p in probs:
        print(f"    - {folder}: {p}")
    if not probs:
        print(f"    {folder}: verified")
    return probs


def cmd_verify(a):
    garment_ids = generate.all_garment_ids("tapstitch")
    found = [t["temple"] for t in scan()]
    if a.all:
        wanted = found
    else:
        wanted = []
        for name in a.temple:
            hit = next((n for n in found if n.rstrip("*").strip().casefold()
                        == name.rstrip("*").strip().casefold()), None)
            if hit is None:
                raise SystemExit(f"no temple folder named {name!r}")
            wanted.append(hit)
    from shopify_client import ShopifyClient
    client = ShopifyClient()
    bad = {f: verify_temple(f, garment_ids, client) for f in wanted}
    bad = {f: p for f, p in bad.items() if p}
    print(f"\n{len(wanted) - len(bad)} of {len(wanted)} temple(s) verified complete.")
    return 1 if bad else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan")
    s.add_argument("--json", action="store_true")
    r = sub.add_parser("run")
    g = r.add_mutually_exclusive_group(required=True)
    g.add_argument("--temple", action="append", help="temple folder name; repeatable")
    g.add_argument("--all-ready", action="store_true", help="every temple scan calls ready")
    v = sub.add_parser("verify")
    g = v.add_mutually_exclusive_group(required=True)
    g.add_argument("--temple", action="append")
    g.add_argument("--all", action="store_true")
    a = ap.parse_args(argv)
    return {"scan": cmd_scan, "run": cmd_run, "verify": cmd_verify}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
