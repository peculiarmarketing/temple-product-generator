"""Offline tests for the Eden Green hoodie rollout. No network.

Run: ./.venv.nosync/bin/python tests/test_eden_green_rollout.py

WHY THIS FILE EXISTS. scripts/eden_green_rollout.py is a sequencer around the
one Tapstitch call with no undo, plus a Shopify cutover that darkens a live
address for the moment between its two writes. Its review on 22 Sep 2026 found
a --limit that let 42 temples through a "bound", a cutover whose first call
could fail without stopping the run, and a repair path that could strand
wrong-temple photos on a live product forever. All provable offline.

WHAT IS PINNED. Which calls each starting state makes and does not make, in what
order, and what it writes to the state file and ledger. The read-back check's
verdict on one correct product and on one mutation at a time. The pixel gates'
direction on synthetic images.

NOT PINNED: the lineup itself. The real hoodie config is used as INPUT, so a
colour added or dropped changes the fixtures with it; nothing here asserts
which colours, prices or sizes Evan chose.
"""

import copy
import json
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import build_product_gallery
import colour_names
import generate
import ledger
import tapstitch_run
import eden_green_rollout as E

TMP = Path(tempfile.mkdtemp(prefix="eden-test-"))
E.STATE_PATH = TMP / "state.json"
ledger.LEDGER_PATH = TMP / "ledger.json"
ledger.LEDGER_MD = TMP / "LEDGER.md"
# Module globals this test replaces. Put back at the end: unittest discover runs
# every test module in one process, and test_tapstitch_run needs the real ones.
_RUN_REAL = {n: getattr(tapstitch_run, n) for n in
             ("SHOPIFY_WAIT_S", "SHOPIFY_POLL_S", "wait_for_import", "stale_colorways")}
tapstitch_run.SHOPIFY_WAIT_S = 0
tapstitch_run.SHOPIFY_POLL_S = 0
SLEEPS = []
E.time.sleep = SLEEPS.append

CFG = generate.load_garment_config("hoodie")
SIZES = ["S", "M", "L", "XL", "2XL"]
ALL = [c["shopify"] for c in CFG["colorways"]]
FIRST = CFG["storefront_first_color"]
NEW_COLOURS = [FIRST] + [c for c in ALL if c != FIRST]
OLD_COLOURS = [c for c in NEW_COLOURS if c != "Eden Green"]
PRICE = f"{CFG['price_usd']:.2f}"
TITLE = "Ultra-soft Oversized Temple Hoodie (Alpha)"
HANDLE = "ultra-soft-oversized-temple-hoodie-alpha"
ALT_T, FOLDER_T, CARD_T = "Alpha", "Alpha", "Alpha"
E.names_for = lambda row, title: (ALT_T, row["temple"], CARD_T)
REAL = {n: getattr(E, n) for n in ("_builder", "check", "wrong_onmodel", "run_temple")}

# The fakes carry fixed 20 Sep 2026 createdAt stamps and find_new() only accepts
# products created after the distribute call, so the clock is pinned just before
# them. Left on the real clock the test started failing once that date passed.
E.now = lambda: "2026-09-20T09:58:00+00:00"

# The fakes below accept whatever they are called with, so pin the real
# signatures they stand in for: a renamed keyword would otherwise surface only
# after distribute(), on the live store.
import inspect
assert {"write_description", "push_art_card"} <= set(inspect.signature(E.finish_on_shopify).parameters)
assert list(inspect.signature(E.ShopifyClient.delete_media).parameters) == ["self", "product_gid", "media_gids"]


def raises(fn, exc, needle=""):
    try:
        fn()
    except exc as e:
        assert needle in str(e), f"{needle!r} not in {e}"
        return e
    raise AssertionError(f"expected {exc.__name__}")


# ---------------------------------------------------------------- fixtures

def gallery_alts():
    # Spelled out rather than taken from gallery_order, so a change to the order
    # breaks this test instead of passing with it. Slot 1 is the on-model back in
    # the flat-lay colour (Evan, 7 Oct 2026).
    fc = build_product_gallery.flat_colour("hoodie")
    return ([build_product_gallery.on_model_alt(ALT_T, "hoodie", fc),
             build_product_gallery.flat_alt(ALT_T, "hoodie", "back", fc),
             build_product_gallery.flat_alt(ALT_T, "hoodie", "front", fc),
             f"Temple line art close-up - {CARD_T}"]
            + [build_product_gallery.on_model_alt(ALT_T, "hoodie", c)
               for c in build_product_gallery.ORDER["hoodie"] if c != fc]
            + [a for _, a in build_product_gallery.detail_alts("hoodie")])


def make(gid, handle, colours, status="ACTIVE", created="2026-09-20T10:00:00Z",
         media=None, bind=True):
    media = media if media is not None else []
    nodes = [{"id": f"{gid}/m{i}", "alt": a,
              "image": {"url": f"https://cdn/{i}.jpg", "width": 2048, "height": 2048}}
             for i, a in enumerate(media)]
    by_alt = {m["alt"]: m["id"] for m in nodes}

    def bound(c):
        alt = build_product_gallery.on_model_alt(ALT_T, "hoodie", colour_names.slug_for("hoodie", c))
        return [{"id": by_alt[alt]}] if bind and alt in by_alt else []

    return {"id": gid, "title": TITLE, "handle": handle, "status": status,
            "vendor": "ODMPOD", "productType": "Hoodie", "createdAt": created,
            "tags": ["temple:alpha", "garment:hoodie"], "templateSuffix": None,
            "onlineStoreUrl": f"https://shop.test/products/{handle}" if status == "ACTIVE" else None,
            "descriptionHtml": "<section>a</section>\n\n<section>b  </section>\n",
            "seo": {"title": "Alpha Temple Hoodie", "description": "d"},
            "options": [{"name": "Color", "optionValues": [{"name": c} for c in colours]},
                        {"name": "Size", "optionValues": [{"name": s} for s in SIZES]}],
            "variants": {"nodes": [{"id": f"{gid}/v{c}{s}", "title": f"{c} / {s}",
                                    "price": PRICE, "media": {"nodes": bound(c)}}
                                   for c in colours for s in SIZES]},
            "media": {"nodes": nodes},
            "metafields": {"nodes": [{"key": "temple_name", "type": "single_line_text_field",
                                      "value": "Alpha Temple"},
                                     {"key": "dedicated_on", "type": "date", "value": "2000-01-01"}]},
            "collections": {"nodes": [{"handle": "temple-hoodies"}]}}


OLD = "gid://shopify/Product/1"
NEW = "gid://shopify/Product/2"


class Shop:
    """A fake store. gql answers the three query shapes the script sends."""

    def __init__(self, *products):
        self.p = {x["id"]: x for x in products}
        self.calls, self.meta_errors, self.fail = [], [], None

    def gql(self, q, v=None):
        if "sortKey: CREATED_AT" in q:
            self.calls.append("find")
            nodes = sorted(self.p.values(), key=lambda x: x["createdAt"], reverse=True)
            return {"products": {"nodes": [{k: x[k] for k in ("id", "title", "handle",
                                                              "status", "createdAt")}
                                           for x in nodes]}}
        if "metafieldsSet" in q:
            self.calls.append(("metafieldsSet", len(v["m"]), v["m"][0]["ownerId"]))
            return {"metafieldsSet": {"userErrors": self.meta_errors}}
        if "primaryDomain" in q:
            return {"shop": {"primaryDomain": {"url": "https://shop.test"}}}
        if "product(id:" in q:
            return {"product": copy.deepcopy(self.p.get(v["id"]))}
        raise AssertionError(f"unexpected query {q[:60]}")

    def find_product_by_handle(self, h):
        return next(({"id": x["id"], "handle": h} for x in self.p.values()
                     if x["handle"] == h), None)

    def update_product(self, gid, **f):
        self.calls.append(("update", gid, dict(f)))
        if self.fail and self.fail(gid, f):
            raise RuntimeError("boom")
        self.p[gid].update({k: v for k, v in f.items()})

    def update_media_alt(self, gid, mid, alt):
        self.calls.append(("alt", mid, alt))
        for m in self.p[gid]["media"]["nodes"]:
            if m["id"] == mid:
                m["alt"] = alt

    def delete_media(self, gid, ids):
        self.calls.append(("delete", sorted(ids)))
        self.p[gid]["media"]["nodes"] = [m for m in self.p[gid]["media"]["nodes"]
                                         if m["id"] not in ids]
        return list(ids)

    def upload_media_image(self, gid, path, alt):
        self.calls.append(("upload", alt))
        return "gid://m/card"

    def wait_for_media_ready(self, mid):
        return None


class Comps:
    root = TMP / "comps"

    def folder(self, name):
        return self.root / name

    def close(self):
        pass


def fake_tapstitch(shop, calls, appear_after=1, new_product=None):
    """Patch the Tapstitch calls. distribute() makes the new product appear on
    the shop after `appear_after` further lookups, and checks the marker first."""
    codes = ",".join(str(c["code"]) for c in CFG["colorways"])
    E.T.get_template = lambda s, t: calls.append("get_template") or {"colorCode": codes}
    E.T.store_product_prefill = lambda s, st, t: calls.append("prefill") or {
        "options": [{"name": "Color", "values": [{"name": c["tapstitch"]} for c in CFG["colorways"]]},
                    {"name": "Size", "values": [{"name": s} for s in SIZES]}],
        "variants": [{"id": i} for i in range(len(CFG["colorways"]) * len(SIZES))],
        "mockups": [], "costIncludesShipping": False, "shippingProfiles": [],
        "visibility": {"publish": True}}

    def create(s, st, payload):
        calls.append("create")
        calls.append(("description", payload["description"]["content"]))
        return "SP1"

    def distribute(s, ids):
        on_disk = json.loads(E.STATE_PATH.read_text())["temples"]["Alpha"]
        assert on_disk.get("distribute_started_at"), "marker must be saved BEFORE distribute"
        calls.append("distribute")
        prod = new_product or make(NEW, HANDLE + "-1", NEW_COLOURS, created="2026-09-22T23:59:59Z")
        pending = [appear_after]

        orig = shop.gql

        def gql(q, v=None):
            if "sortKey: CREATED_AT" in q and pending[0] > 0:
                pending[0] -= 1
                if pending[0] == 0:
                    shop.p[prod["id"]] = prod
            return orig(q, v)
        shop.gql = gql
        return {}

    E.T.create_store_product = create
    E.T.distribute = distribute


def patch_shopify_half(calls, check=lambda *a, **k: []):
    tapstitch_run.wait_for_import = lambda sc, h: calls.append("wait_import") or "settled"
    tapstitch_run.stale_colorways = lambda sc, g, h: []
    E.finish_on_shopify = lambda *a, **k: calls.append(("finish_on_shopify", k)) or ["type set"]
    E._builder = lambda gid, t, folder, stage, note: calls.append(("builder", stage, str(folder), t))
    E.wrong_onmodel = lambda p, t, folder: []
    E.check = check
    E.art_images.override_path = lambda t: Path("/card.png")


ROW = dict(ledger.blank_row("Alpha", "hoodie"), shopify_handle=HANDLE,
           tapstitch_template_id="TPL1", state="live")


def fresh_state(**entry):
    state = {"temples": {"Alpha": dict(entry)}} if entry else {"temples": {"Alpha": {}}}
    E.save_state(state)
    return state


def drive(entry=None, publish=True, shop=None, appear_after=1, check=lambda *a, **k: []):
    calls = []
    shop = shop or Shop(make(OLD, HANDLE, OLD_COLOURS))
    state = fresh_state(**(entry or {}))
    fake_tapstitch(shop, calls, appear_after)
    patch_shopify_half(calls, check)
    ledger.save({"rows": [dict(ROW)]})
    e = state["temples"]["Alpha"]
    out = E.run_temple(None, shop, state, e, ROW, CFG, Comps(), "https://shop.test",
                       publish, lambda m: None)
    return out, calls, shop, e


# ---------------------------------------------------------------- state helpers

assert E.next_step({}) == "resolved"
assert E.next_step({"resolved": 1, "built": 1}) == "distributed"
assert E.next_step({s: 1 for s in E.STEPS}) is None
seed = json.loads((Path(__file__).resolve().parent.parent
                   / "artifacts/tapstitch/eden-green-rollout.json").read_text())["temples"]["Boise"]
allowed = set(E.STEPS) | {"_seeded", "old_id", "new_id", "handle", "title",
                          "store_product_id", "distribute_started_at", "problem"}
assert set(seed) <= allowed, set(seed) - allowed
# Boise finished on 23 Sep 2026, so its record has every step and nothing is next.
assert E.next_step(seed) is None, E.next_step(seed)

# The gallery's colour list must be the garment's, lead colour first: a colour
# missing from ORDER is built with no photo and ships with its variants unbound.
for g in ("tee", "crew", "hoodie"):
    cfg = generate.load_garment_config(g)
    want = {colour_names.slug_for(g, c["shopify"]) for c in cfg["colorways"]}
    assert set(build_product_gallery.ORDER[g]) == want, (g, build_product_gallery.ORDER[g], want)

# ---------------------------------------------------------------- find_new

s = Shop(make(OLD, HANDLE, OLD_COLOURS), make(NEW, HANDLE + "-1", NEW_COLOURS,
                                              created="2026-09-22T20:00:00Z"))
bare = make("gid://shopify/Product/9", "ultra-soft-oversized-temple-hoodie", OLD_COLOURS,
            created="2026-09-22T21:00:00Z")
bare["title"] = "Ultra-soft Oversized Temple Hoodie"
s.p[bare["id"]] = bare
assert E.find_new(s, TITLE, OLD)["id"] == NEW, "old id excluded, bare prefix not matched"
assert E.find_new(s, TITLE, OLD, "2026-09-22T21:00:00+00:00") is None, "older than since"
s.p["gid://shopify/Product/3"] = make("gid://shopify/Product/3", "x", NEW_COLOURS,
                                      created="2026-09-22T20:30:00Z")
raises(lambda: E.find_new(s, TITLE, OLD), E.StepError, "run twice")

# ---------------------------------------------------------------- resolve / build

raises(lambda: E.step_resolve(Shop(make(OLD, HANDLE, NEW_COLOURS)), {}, ROW, CFG, print),
       E.StepError, "already rolled out")
raises(lambda: E.step_resolve(Shop(make(OLD, HANDLE, OLD_COLOURS, status="DRAFT")), {}, ROW,
                              CFG, print), E.StepError, "not ACTIVE")
e = {}
E.step_resolve(Shop(make(OLD, HANDLE, OLD_COLOURS)), e, ROW, CFG, lambda m: None)
assert e == {"old_id": OLD, "handle": HANDLE, "title": TITLE}, e


def build_with(mutate_old=None, template_codes=None, prefill_colours=None):
    calls, shop = [], Shop(make(OLD, HANDLE, OLD_COLOURS))
    fake_tapstitch(shop, calls)
    if template_codes is not None:
        E.T.get_template = lambda s_, t: {"colorCode": template_codes}
    if prefill_colours is not None:
        real = E.T.store_product_prefill
        E.T.store_product_prefill = lambda *a: dict(real(*a), options=[
            {"name": "Color", "values": [{"name": c} for c in prefill_colours]},
            {"name": "Size", "values": [{"name": x} for x in SIZES]}])
    if mutate_old:
        mutate_old(shop.p[OLD])
    entry = {"old_id": OLD, "title": TITLE}
    E.step_build(None, shop, entry, ROW, CFG, lambda m: None)
    return calls, entry, shop


six = ",".join(str(c["code"]) for c in CFG["colorways"] if c["shopify"] != "Eden Green")
raises(lambda: build_with(template_codes=six), E.StepError, "Eden Green")
raises(lambda: build_with(prefill_colours=[c["tapstitch"] for c in CFG["colorways"]][:-1]),
       E.StepError, "prefill offers")
raises(lambda: build_with(lambda p: p["variants"]["nodes"][0].update(price="69.99")),
       E.StepError, "69.99")
raises(lambda: build_with(lambda p: p.update(descriptionHtml="")), E.StepError, "no description")
calls, entry, shop = build_with()
assert entry["store_product_id"] == "SP1"
assert ("description", shop.p[OLD]["descriptionHtml"]) in calls, "old description, verbatim"

# ---------------------------------------------------------------- distribute once

out, calls, shop, e = drive(publish=False)
assert out is False and "distribute" not in calls, calls
assert e["store_product_id"] == "SP1" and e.get("built") and not e.get("distributed"), e

out, calls, shop, e = drive(publish=True)
assert calls.count("distribute") == 1, calls
assert calls.index("create") < calls.index("distribute")
assert e["new_id"] == NEW and e.get("verified"), e
assert ("update", NEW, {"status": "DRAFT"}) in shop.calls, "hidden the moment it appears"
assert json.loads(ledger.LEDGER_PATH.read_text())["rows"][0]["state"] == "live"

# Marker set, confirmation lost: poll, never call again.
entry = {"resolved": 1, "built": 1, "old_id": OLD, "handle": HANDLE, "title": TITLE,
         "store_product_id": "SP1", "distribute_started_at": "2026-09-22T12:00:00+00:00"}
shop = Shop(make(OLD, HANDLE, OLD_COLOURS))
shop.p[NEW] = make(NEW, HANDLE + "-1", NEW_COLOURS, created="2026-09-22T12:01:00Z")
out, calls, shop, e = drive(entry, shop=shop)
assert "distribute" not in calls and e["new_id"] == NEW, calls

# A second product already there and no marker: refuse, write nothing.
shop = Shop(make(OLD, HANDLE, OLD_COLOURS), make(NEW, HANDLE + "-1", NEW_COLOURS))
entry = {"resolved": 1, "built": 1, "old_id": OLD, "handle": HANDLE, "title": TITLE,
         "store_product_id": "SP1"}
raises(lambda: drive(entry, shop=shop), E.StepError, "already exists")
assert not json.loads(E.STATE_PATH.read_text())["temples"]["Alpha"].get("distribute_started_at")

# Marker set, product never appears: raise, keep the marker.
entry = {"resolved": 1, "built": 1, "old_id": OLD, "handle": HANDLE, "title": TITLE,
         "store_product_id": "SP1", "distribute_started_at": "2026-09-22T12:00:00+00:00"}
raises(lambda: drive(entry), E.StepError, "not appeared")
assert json.loads(E.STATE_PATH.read_text())["temples"]["Alpha"]["distribute_started_at"]

# Resume after a failure in finish: no rebuild, no redistribute.
entry = {"resolved": 1, "built": 1, "distributed": 1, "hidden": 1, "old_id": OLD,
         "handle": HANDLE, "title": TITLE, "store_product_id": "SP1", "new_id": NEW}
shop = Shop(make(OLD, HANDLE, OLD_COLOURS), make(NEW, HANDLE + "-1", NEW_COLOURS, status="DRAFT"))
out, calls, shop, e = drive(entry, shop=shop)
assert not {"create", "distribute", "wait_import"} & set(c for c in calls if isinstance(c, str))
assert e.get("verified")

# Boise's seeded shape: finish, gallery, verify; no cutover writes.
entry = {k: 1 for k in ("resolved", "built", "distributed", "hidden", "cutover")}
entry.update(old_id=OLD, handle=HANDLE, title=TITLE, new_id=NEW)
shop = Shop(make(OLD, HANDLE + "-retired", OLD_COLOURS, status="DRAFT"),
            make(NEW, HANDLE, NEW_COLOURS))
out, calls, shop, e = drive(entry, shop=shop)
assert [c[1] for c in calls if c[0] == "builder"] == ["add", "reface", "prune"]
assert not any(c[0] == "update" and c[2].get("handle") for c in shop.calls
               if isinstance(c, tuple)), "no cutover on a temple already cut over"

# --apply without --publish on a temple already past distribute is held, not advanced.
entry = {"resolved": 1, "built": 1, "distributed": 1, "old_id": OLD, "new_id": NEW,
         "handle": HANDLE, "title": TITLE, "store_product_id": "SP1"}
out, calls, shop, e = drive(entry, publish=False)
assert out is False and "wait_import" not in calls

# ---------------------------------------------------------------- finish

calls = []
patch_shopify_half(calls)
shop = Shop(make(OLD, HANDLE, OLD_COLOURS), make(NEW, HANDLE + "-1", NEW_COLOURS, status="DRAFT"))
shop.p[OLD]["metafields"]["nodes"] = [{"key": f"k{i}", "type": "single_line_text_field",
                                       "value": str(i)} for i in range(30)]
E.step_finish(shop, {"old_id": OLD, "new_id": NEW, "title": TITLE}, ROW, CFG, lambda m: None)
fin = [c for c in calls if c[0] == "finish_on_shopify"][0][1]
assert fin == {"write_description": False, "push_art_card": False}, fin
upd = [c for c in shop.calls if c[0] == "update" and c[1] == NEW][0][2]
old = shop.p[OLD]
assert upd == {"descriptionHtml": old["descriptionHtml"], "tags": old["tags"],
               "seo": old["seo"], "templateSuffix": old["templateSuffix"]}, upd
assert [c[1:] for c in shop.calls if c[0] == "metafieldsSet"] == [(25, NEW), (5, NEW)]
assert ("upload", f"Temple line art close-up - {CARD_T}") in shop.calls

shop = Shop(make(OLD, HANDLE, OLD_COLOURS), make(NEW, HANDLE + "-1", NEW_COLOURS, status="DRAFT"))
shop.meta_errors = [{"field": "x", "message": "bad"}]
raises(lambda: E.step_finish(shop, {"old_id": OLD, "new_id": NEW, "title": TITLE}, ROW, CFG,
                             lambda m: None), E.StepError, "metafieldsSet")
assert not any(c[0] == "upload" for c in shop.calls), "no card after a failed copy"

# ---------------------------------------------------------------- gallery

argv = []


class _Done:
    returncode, stdout, stderr = 0, "", ""


E._builder = REAL["_builder"]
E.subprocess.run = lambda cmd, **k: argv.append(cmd) or _Done()
folder = Comps().folder("Alpha")
alts = gallery_alts()
onm = build_product_gallery.on_model_alt(ALT_T, "hoodie", "navy-blue")
shop = Shop(make(NEW, HANDLE, NEW_COLOURS, media=alts, bind=False))
wrong_id = [m["id"] for m in shop.p[NEW]["media"]["nodes"] if m["alt"] == onm][0]
E.wrong_onmodel = lambda p, t, f: ([(wrong_id, onm, 0.07)]
                                   if any(m["alt"] == onm for m in p["media"]["nodes"]) else [])
E.step_gallery(shop, {"new_id": NEW, "title": TITLE}, ROW, Comps(), lambda m: None)
assert [c[-1] for c in argv] == ["--add", "--reface", "--prune"], argv
for c in argv:
    assert c[c.index("--onmodel-dir") + 1] == str(folder), c
    assert c[c.index("--temple") + 1] == ALT_T, c
assert ("alt", wrong_id, E.SUPERSEDED + onm) in shop.calls
assert ("delete", [wrong_id]) in shop.calls

# A superseded photo left by an earlier, interrupted run is still cleaned up.
argv.clear()
shop = Shop(make(NEW, HANDLE, NEW_COLOURS, media=alts[:3] + [E.SUPERSEDED + onm], bind=False))
E.wrong_onmodel = lambda p, t, f: []
E.step_gallery(shop, {"new_id": NEW, "title": TITLE}, ROW, Comps(), lambda m: None)
assert any(c[0] == "delete" for c in shop.calls), "orphan from an earlier run must go"

# ...but never while a variant still shows it.
shop = Shop(make(NEW, HANDLE, NEW_COLOURS, media=[E.SUPERSEDED + onm], bind=False))
sid = shop.p[NEW]["media"]["nodes"][0]["id"]
shop.p[NEW]["variants"]["nodes"][0]["media"]["nodes"] = [{"id": sid}]
raises(lambda: E.step_gallery(shop, {"new_id": NEW, "title": TITLE}, ROW, Comps(),
                              lambda m: None), E.StepError, "still bound")
assert not any(c[0] == "delete" for c in shop.calls)

# ---------------------------------------------------------------- check

E.check = REAL["check"]
E.wrong_onmodel = lambda p, t, f: []
E.build_garment_catalog.verify = lambda p, t, g: []


class _Page:
    def __init__(self, gid, ok=True):
        self.ok, self.status_code, self._id = ok, 200 if ok else 404, gid.split("/")[-1]

    def json(self):
        return {"id": int(self._id)}


PAGE = {"gid": NEW}
E.requests.get = lambda url, **k: _Page(PAGE["gid"])


def pair():
    return Shop(make(OLD, HANDLE + "-retired", OLD_COLOURS, status="DRAFT"),
                make(NEW, HANDLE, NEW_COLOURS, media=alts))


ENTRY = {"old_id": OLD, "new_id": NEW, "handle": HANDLE, "title": TITLE}
good = pair()
assert E.check(good, ENTRY, ROW, CFG, Comps(), "https://shop.test") == [], \
    E.check(good, ENTRY, ROW, CFG, Comps(), "https://shop.test")


def one_problem(mutate, needle, domain="https://shop.test"):
    shop = pair()
    mutate(shop)
    probs = E.check(shop, ENTRY, ROW, CFG, Comps(), domain)
    assert len(probs) >= 1 and any(needle in p for p in probs), (needle, probs)


N = lambda sh: sh.p[NEW]
O = lambda sh: sh.p[OLD]
one_problem(lambda sh: N(sh).update(status="DRAFT"), "new product is DRAFT")
one_problem(lambda sh: N(sh).update(handle=HANDLE + "-1"), "new product is ACTIVE at")
one_problem(lambda sh: N(sh).update(onlineStoreUrl=None), "Online Store")
one_problem(lambda sh: O(sh).update(status="ACTIVE"), "old product is ACTIVE")
one_problem(lambda sh: O(sh).update(handle=HANDLE), "old product is DRAFT at")
one_problem(lambda sh: N(sh)["options"][0].update(optionValues=[{"name": c} for c in OLD_COLOURS]),
            "colours are")
one_problem(lambda sh: N(sh)["options"][0]["optionValues"].reverse(), "colours are")
one_problem(lambda sh: N(sh)["variants"].update(nodes=N(sh)["variants"]["nodes"][:30]), "30 variants")
one_problem(lambda sh: N(sh)["variants"]["nodes"][0].update(price="69.99"), "prices")
one_problem(lambda sh: N(sh).update(descriptionHtml=N(sh)["descriptionHtml"] + "\n"), "descriptionHtml")
one_problem(lambda sh: N(sh).update(seo={"title": "x", "description": "d"}), "seo")
one_problem(lambda sh: N(sh).update(tags=["temple:alpha"]), "tags")
one_problem(lambda sh: N(sh)["metafields"]["nodes"][0].update(value="Other"), "metafields")
one_problem(lambda sh: N(sh)["metafields"]["nodes"][1].update(type="single_line_text_field"),
            "metafields")
one_problem(lambda sh: N(sh).update(collections={"nodes": []}), "collections")
one_problem(lambda sh: N(sh)["media"]["nodes"].reverse(), "gallery is")
one_problem(lambda sh: N(sh)["media"]["nodes"][0]["image"].update(height=1200), "not square")
one_problem(lambda sh: N(sh)["media"]["nodes"][5].update(alt=E.SUPERSEDED + "x"), "superseded")
one_problem(lambda sh: N(sh)["variants"]["nodes"][0]["media"].update(
    nodes=[{"id": N(sh)["media"]["nodes"][1]["id"]}]), "is bound to")   # the flat back lay
PAGE["gid"] = OLD
one_problem(lambda sh: None, "storefront")
PAGE["gid"] = NEW
tags_reordered = pair()
tags_reordered.p[NEW]["tags"].reverse()
assert E.check(tags_reordered, ENTRY, ROW, CFG, Comps(), "https://shop.test") == []
hidden = pair()
hidden.p[NEW].update(status="DRAFT", handle=HANDLE + "-1", onlineStoreUrl=None)
assert E.check(hidden, ENTRY, ROW, CFG, Comps()) == [], "pre-cutover skips the live checks"

# ---------------------------------------------------------------- verify

def verify_with(answers):
    seq = list(answers)
    E.check = lambda *a, **k: seq.pop(0) if len(seq) > 1 else seq[0]
    SLEEPS.clear()
    ledger.save({"rows": [dict(ROW, state="description-written")]})
    state = fresh_state(finished=1, gallery=1, **ENTRY)
    e = state["temples"]["Alpha"]
    E.step_verify(pair(), state, e, ROW, CFG, Comps(), "https://shop.test", lambda m: None)
    return e


e = verify_with([["live, settling: storefront x"], ["live, settling: storefront x"], []])
assert len(SLEEPS) == 2
row = json.loads(ledger.LEDGER_PATH.read_text())["rows"][0]
assert row["state"] == "live" and row["shopify_handle"] == HANDLE, row
raises(lambda: verify_with([["colours are wrong"]]), E.StepError, "colours")
assert SLEEPS == [], "a real defect is not waited on"
reopened = json.loads(E.STATE_PATH.read_text())["temples"]["Alpha"]
assert "finished" not in reopened and "gallery" not in reopened, "a defect re-opens the repair steps"
raises(lambda: verify_with([["live, settling: storefront x"]]), E.StepError, "storefront")
assert json.loads(ledger.LEDGER_PATH.read_text())["rows"][0]["state"] == "description-written"
assert json.loads(E.STATE_PATH.read_text())["temples"]["Alpha"].get("gallery"), \
    "a live-only problem does not re-open the gallery"

# ---------------------------------------------------------------- cutover

def cutover(shop, gate=()):
    E.check = lambda *a, **k: list(gate)
    state = fresh_state(finished=1, gallery=1, **ENTRY)
    E.step_cutover(shop, state, state["temples"]["Alpha"], ROW, CFG, Comps(), lambda m: None)
    return state


def staged():
    return Shop(make(OLD, HANDLE, OLD_COLOURS), make(NEW, HANDLE + "-1", NEW_COLOURS, status="DRAFT"))


shop = staged()
cutover(shop)
ups = [c for c in shop.calls if c[0] == "update"]
assert ups[0][1] == OLD and ups[0][2]["status"] == "DRAFT" and "-retired-" in ups[0][2]["handle"]
assert ups[1] == ("update", NEW, {"handle": HANDLE, "status": "ACTIVE"}), ups

shop = staged()
raises(lambda: cutover(shop, gate=["gallery is wrong"]), E.StepError, "not cutting over")
assert not [c for c in shop.calls if c[0] == "update"]
st = json.loads(E.STATE_PATH.read_text())["temples"]["Alpha"]
assert "gallery" not in st and "finished" not in st

shop = staged()
shop.fail = lambda gid, f: gid == NEW
raises(lambda: cutover(shop), E.CutoverError, "may be dark")

shop = staged()
shop.fail = lambda gid, f: gid == OLD           # refused outright: nothing moved
raises(lambda: cutover(shop), E.StepError, "did not start")


def applied_then_lost(gid, f):
    if gid == OLD:
        shop.p[OLD].update(f)
        return True


shop = staged()
shop.fail = applied_then_lost
raises(lambda: cutover(shop), E.CutoverError, "may be dark")

shop = Shop(make(OLD, HANDLE + "-retired", OLD_COLOURS, status="DRAFT"),
            make(NEW, HANDLE + "-1", NEW_COLOURS, status="DRAFT"))
cutover(shop)
assert [c[1] for c in shop.calls if c[0] == "update"] == [NEW], "retired old is left alone"

shop = Shop(make(OLD, "elsewhere", OLD_COLOURS), make(NEW, HANDLE + "-1", NEW_COLOURS, status="DRAFT"))
cutover(shop)
assert ("update", OLD, {"status": "DRAFT"}) in shop.calls, "ACTIVE elsewhere: draft, no rename"

# ---------------------------------------------------------------- pixels

E.BLANKS = TMP / "blanks"
E.BLANKS.mkdir(exist_ok=True)
base = Image.new("RGB", (512, 512), (60, 90, 70))
base.save(E.BLANKS / "hoodie_eden-green.png")


def painted(colour, box=(200, 200, 300, 300)):
    im = base.copy()
    ImageDraw.Draw(im).rectangle(box, fill=colour)
    return im


assert E.print_share(base, "eden-green") == 0.0
assert E.print_share(painted((255, 255, 255)), "eden-green") > E.MIN_PRINT
assert E.print_share(painted((0, 0, 0)), "eden-green") == 0.0, "white ink only"
a = painted((255, 255, 255))
assert E.off_share(a, a) == 0.0
assert E.off_share(a, painted((255, 255, 255), (150, 260, 250, 360))) > E.MAX_OFF_COMPOSITE


def composites_with(write, rc=0):
    c = E.Composites()

    class R:
        returncode, stdout, stderr = rc, "tail of log", ""

    def run(cmd, **k):
        out = Path(cmd[cmd.index("--outdir") + 1]) / "Alpha"
        out.mkdir(parents=True, exist_ok=True)
        write(out)
        return R()
    E.subprocess.run = run
    try:
        return c.folder("Alpha")
    finally:
        c.close()


for slug in build_product_gallery.ORDER["hoodie"]:
    base.save(E.BLANKS / f"hoodie_{slug}.png")
full = lambda out: [painted((255, 255, 255)).save(out / f"hoodie_{c}.jpg")
                    for c in build_product_gallery.ORDER["hoodie"]]
composites_with(full)
raises(lambda: composites_with(lambda out: [painted((255, 255, 255)).save(out / f"hoodie_{c}.jpg")
                                            for c in build_product_gallery.ORDER["hoodie"][1:]]),
       E.StepError, "composite for Alpha")
raises(lambda: composites_with(lambda out: [(base if c == "eden-green" else painted((255, 255, 255)))
                                            .save(out / f"hoodie_{c}.jpg")
                                            for c in build_product_gallery.ORDER["hoodie"]]),
       E.StepError, "carries no print")
raises(lambda: composites_with(lambda out: None, rc=1), E.StepError, "tail of log")

# ---------------------------------------------------------------- command line

ledger.save({"rows": [dict(ROW, temple=t, shopify_handle=f"h-{t}") for t in ("Alpha", "Beta", "Gamma")]})
E.save_state({"temples": {}})


def boom(*a, **k):
    raise AssertionError("must not open a session")


E.ShopifyClient = boom
E.T.session = boom
for argv_, needle in ((["--publish"], "needs --apply"),
                      (["--apply", "--publish"], "needs a bound"),
                      (["--apply", "--publish", "--limit", "0"], "--limit 0"),
                      (["--apply", "--publish", "--limit", "-3"], "--limit -3"),
                      (["--apply", "--limit", "0"], "--limit 0"),
                      (["--temple", "Nowhere"], "no temple named")):
    raises(lambda: E.main(argv_), SystemExit, needle)
assert E.main([]) == 0, "plan mode opens no session"

E.ShopifyClient = lambda: Shop()
E.Composites = Comps
E.check = lambda *a, **k: []
E.save_state({"temples": {"Alpha": {"cutover": 1, **ENTRY}}})
assert E.main(["--verify"]) == 0, "--verify never opens Tapstitch"

# The run stops on a cutover failure and after two failures in a row.
entered = []


def scripted(results):
    seq = iter(results)

    def run_temple(s_, sc, state, entry, row, *a):
        entered.append(row["temple"])
        r = next(seq)
        if isinstance(r, Exception):
            raise r
        return True
    return run_temple


E.T.session = lambda: None
E.colour_names.check_against_garments = lambda *a: []
for results, want in (([E.CutoverError("dark"), True, True], ["Alpha"]),
                      ([E.StepError("a"), E.StepError("b"), True], ["Alpha", "Beta"]),
                      ([E.StepError("a"), True, E.StepError("c")], ["Alpha", "Beta", "Gamma"])):
    entered.clear()
    E.save_state({"temples": {}})
    E.run_temple = scripted(results)
    E.main(["--apply", "--publish", "--limit", "3"])
    assert entered == want, (results, entered)

# A temple held back by the gates keeps the reason it stopped last time.
E.save_state({"temples": {"Alpha": {"problem": "gallery timed out"}}})
E.run_temple = lambda *a: False
E.main(["--apply", "--temple", "Alpha"])
assert json.loads(E.STATE_PATH.read_text())["temples"]["Alpha"]["problem"] == "gallery timed out"

for _n, _v in _RUN_REAL.items():
    setattr(tapstitch_run, _n, _v)

print("all tests passed")
