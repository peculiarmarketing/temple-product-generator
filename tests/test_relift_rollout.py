"""Offline tests for scripts/relift_rollout.py. No network: Shopify, Tapstitch,
the clock and every image are faked. Module-level asserts, the same shape as
test_eden_green_rollout.py.

Run: python tests/test_relift_rollout.py
"""
import copy
import json
import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import build_product_gallery as G   # noqa: E402
import relift_rollout as RR         # noqa: E402

TMP = Path(tempfile.mkdtemp(prefix="relift-test-"))
RR.STATE_PATH = TMP / "state.json"
RR.THUMBS = TMP / "thumbs"
RR.THUMBS.mkdir()
RR.COMPOSITES = TMP / "composites"          # no files: the composite pixel check is skipped
# Shared modules this test replaces functions on. Put back at the end, since
# unittest discover runs every test module in one process.
_REAL = [(RR.time, "sleep"), (RR.T, "store_product_for"), (RR.T, "session"),
         (RR.ledger, "load")]
_REAL = [(mod, n, getattr(mod, n)) for mod, n in _REAL]
RR.time.sleep = lambda s: None


def raises(fn, needle=""):
    try:
        fn()
    except SystemExit as e:
        assert needle in str(e), f"{needle!r} not in {e}"
        return
    raise AssertionError("expected SystemExit")


# ---------------------------------------------------------------- the gallery order

for g in ("tee", "crew", "hoodie"):
    order = G.gallery_order("Alpha", g, "Temple line art close-up - Alpha")
    lead = G.on_model_alt("Alpha", g, G.flat_colour(g))
    assert order[0] == lead, (g, order[:2])                      # the collection thumbnail
    assert order.count(lead) == 1, g
    assert order[1] == G.flat_alt("Alpha", g, "back", G.flat_colour(g))
    assert order[2] == G.flat_alt("Alpha", g, "front", G.flat_colour(g))
    assert order[3] == "Temple line art close-up - Alpha"
    assert len(order) == len(set(order)), g

# ---------------------------------------------------------------- fakes

TEE = "tee"
NAME = "Alpha"
ROW = {"temple": NAME, "garment": TEE, "state": "live",
       "shopify_handle": "essential-heavyweight-temple-tee-alpha",
       "tapstitch_template_id": "T1"}
ALTS = G.gallery_order(NAME, TEE, "Temple line art close-up - Alpha")
COLOURS = ["Black", "Charcoal", "Navy Blue", "Maroon", "Coffee"]


def pic(i):
    """A distinct 32x32 picture per image: a flat field at its own level."""
    return np.full((32, 32), 10.0 + 20 * i, dtype=np.float32)


PIX = {}


def media(prefix, alts, pics=None):
    out = []
    for i, a in enumerate(alts):
        url = f"https://cdn/{prefix}{i}.jpg"
        PIX[url] = pics[i] if pics is not None else pic(i)
        out.append({"id": f"gid://shopify/MediaImage/{prefix}{i}", "alt": a,
                    "status": "READY", "image": {"url": url}})
    return out


def product(nodes):
    by_alt = {m["alt"]: m["id"] for m in nodes}
    variants = []
    for c in COLOURS:
        slug = RR.colour_names.slug_for(TEE, c)
        mid = by_alt.get(G.on_model_alt(NAME, TEE, slug))
        for size in ("S", "M"):
            variants.append({"id": f"v-{c}-{size}", "title": f"{c} / {size}",
                             "media": {"nodes": [{"id": mid}] if mid else []}})
    return {"id": "gid://shopify/Product/1", "title": f"Essential Heavyweight Temple Tee ({NAME})",
            "productType": "T-Shirt", "tags": ["a", "b"], "status": "ACTIVE",
            "descriptionHtml": "<p>d</p>",
            "options": [{"name": "Color", "values": COLOURS}, {"name": "Size", "values": ["S", "M"]}],
            "media": {"nodes": nodes}, "variants": {"nodes": variants}}


class Shop:
    def __init__(self, p):
        self.p, self.alts, self.deleted = p, [], []

    def update_media_alt(self, pid, mid, alt):
        self.alts.append((mid, alt))
        for m in self.p["media"]["nodes"]:
            if m["id"] == mid:
                m["alt"] = alt

    def delete_media(self, pid, ids):
        self.deleted += ids


RR.fetch = lambda sc, handle: sc.p
RR.thumb = lambda url: PIX[url]
STORE = {"commits": {("T1", "C2")}}
RR.T.store_product_for = lambda s, gid, title: {
    "uniqueId": "SP1",
    "variants": [{"productionItems": [{"templateId": t, "commitId": c}]}
                 for t, c in STORE["commits"]]}


def snapshot_rec():
    """A record as step_snapshot leaves it, with thumbnails on disk."""
    nodes = media("old", ALTS)
    rec = {"product_id": "gid://shopify/Product/1", "title": product(nodes)["title"],
           "fingerprint": RR.fingerprint(product(nodes)), "media": [],
           "template_id": "T1", "commit_after": "C2"}
    for i, m in enumerate(nodes):
        f = RR.THUMBS / f"old{i}.npy"
        np.save(f, PIX[m["image"]["url"]])
        rec["media"].append({"id": m["id"], "alt": m["alt"], "thumb": f.name})
    return rec


# ---------------------------------------------------------------- restore

rec = snapshot_rec()
# Tapstitch sends the same pictures back with new ids, no alts, in another order.
order = list(reversed(range(len(ALTS))))
back = media("new", [""] * len(ALTS), [pic(i) for i in order])
shop = Shop(product(back))
RR.step_restore(shop, ROW, rec)
assert [a for _, a in shop.alts] == [ALTS[i] for i in order], "alts must follow pixels, not position"
assert rec["worst_match"] == 0.0

# A picture that matches nothing: stop before writing a single alt.
rec = snapshot_rec()
pics = [pic(i) for i in range(len(ALTS))]
pics[3] = np.full((32, 32), 250.0, dtype=np.float32)
shop = Shop(product(media("bad", [""] * len(ALTS), pics)))
raises(lambda: RR.step_restore(shop, ROW, rec), "cannot match")
assert shop.alts == [] and "restored_at" not in rec

# Two returned pictures that both look like the same snapshot image.
rec = snapshot_rec()
pics = [pic(i) for i in range(len(ALTS))]
pics[4] = pic(3)
shop = Shop(product(media("dup", [""] * len(ALTS), pics)))
raises(lambda: RR.step_restore(shop, ROW, rec), "cannot match")
assert shop.alts == []

# One picture did not come back.
rec = snapshot_rec()
shop = Shop(product(media("short", [""] * (len(ALTS) - 1))))
raises(lambda: RR.step_restore(shop, ROW, rec), "did not come back")
assert shop.alts == []

# ---------------------------------------------------------------- resync


class Seq:
    """A product that changes on every read, ending on the last state."""
    def __init__(self, states):
        self.states, self.i = states, 0

    @property
    def p(self):
        st = self.states[min(self.i, len(self.states) - 1)]
        self.i += 1
        return st


# A re-sent image that FAILED (Tapstitch pointed it at a file Shopify no longer
# has, measured on Albuquerque and Billings): a fabric detail is deleted and left
# for --add to upload again; everything else gets its alt back.
DETAIL = [a for _, a in G.detail_alts(TEE)][0]
di = ALTS.index(DETAIL)
rec = snapshot_rec()
nodes = media("fail", [""] * len(ALTS))
nodes[di]["status"] = "FAILED"
nodes[di]["image"] = None
shop = Shop(product(nodes))
RR.step_restore(shop, ROW, rec)
assert shop.deleted == [nodes[di]["id"]], shop.deleted
assert [a for _, a in shop.alts] == [a for i, a in enumerate(ALTS) if i != di]
assert rec["failed_in_resend"] == [DETAIL]

# A failed chest-logo flat lay is rebuilt by --reface from its archived original,
# so it is accepted only when that file exists.
FRONT = ALTS.index(G.flat_alt(NAME, TEE, "front", G.flat_colour(TEE)))
G_ORIG = G.originals_dir
for has_archive in (True, False):
    arch = TMP / f"orig-{has_archive}"
    arch.mkdir()
    if has_archive:
        (arch / f"{TEE}_{G.flat_colour(TEE)}_front.png").write_bytes(b"png")
    G.originals_dir = lambda name, _a=arch: _a
    rec = snapshot_rec()
    nodes = media(f"failfront{has_archive}", [""] * len(ALTS))
    nodes[FRONT]["status"] = "FAILED"
    nodes[FRONT]["image"] = None
    shop = Shop(product(nodes))
    if has_archive:
        RR.step_restore(shop, ROW, rec)
        assert shop.deleted == [nodes[FRONT]["id"]]
    else:
        raises(lambda: RR.step_restore(shop, ROW, rec), "cannot rebuild")
        assert shop.alts == [] and shop.deleted == []
G.originals_dir = G_ORIG

# The art card cannot be rebuilt here, so a failed one stops before any write.
ART = ALTS.index("Temple line art close-up - Alpha")
rec = snapshot_rec()
nodes = media("failart", [""] * len(ALTS))
nodes[ART]["status"] = "FAILED"
nodes[ART]["image"] = None
shop = Shop(product(nodes))
raises(lambda: RR.step_restore(shop, ROW, rec), "cannot rebuild")
assert shop.alts == [] and shop.deleted == []

# Resync treats FAILED as final rather than waiting for it forever.
rec = snapshot_rec()
rec["saved_at"] = RR.now()
nodes = media("fin2", [""] * len(ALTS))
nodes[di]["status"] = "FAILED"
seq = Seq([product(nodes)])
RR.step_resync(seq, ROW, rec)
assert rec.get("resynced_at")

rec = snapshot_rec()
rec["saved_at"] = RR.now()
old_nodes = media("old", ALTS)
new_nodes = media("new", [""] * len(ALTS))
half = new_nodes[: len(ALTS) // 2]
uploading = copy.deepcopy(new_nodes)
uploading[0]["status"] = "UPLOADED"
seq = Seq([product(old_nodes), product([]), product(half), product(uploading), product(new_nodes)])
RR.step_resync(seq, ROW, rec)
assert seq.i == 5 and rec.get("resynced_at"), "must wait for every image, all READY"

rec = snapshot_rec()
rec["saved_at"] = "2000-01-01T00:00:00+00:00"            # long past the timeout
raises(lambda: RR.step_resync(Seq([product(old_nodes)]), ROW, rec), "no complete re-send")

# ---------------------------------------------------------------- check


def good():
    nodes = media("fin", ALTS)
    p = product(nodes)
    rec = snapshot_rec()
    rec["fingerprint"] = RR.fingerprint(p)
    return Shop(p), rec


shop, rec = good()
assert RR.check(None, shop, ROW, rec) == [], RR.check(None, shop, ROW, rec)


def one_problem(mutate, needle):
    shop, rec = good()
    mutate(shop.p, rec)
    probs = RR.check(None, shop, ROW, rec)
    assert any(needle in p for p in probs), (needle, probs)


N = lambda p: p["media"]["nodes"]
one_problem(lambda p, r: N(p)[5].update(alt=""), "without alt text")
one_problem(lambda p, r: N(p)[5].update(alt=RR.SUPERSEDED + N(p)[5]["alt"]), "superseded")
one_problem(lambda p, r: N(p).reverse(), "slot 1")
one_problem(lambda p, r: N(p).insert(1, N(p).pop(4)), "gallery is")
one_problem(lambda p, r: N(p)[6].update(alt=N(p)[5]["alt"]), "share an alt")
one_problem(lambda p, r: p["variants"]["nodes"][0]["media"].update(nodes=[{"id": N(p)[1]["id"]}]),
            "not bound")
one_problem(lambda p, r: N(p).pop(1), "no back flat lay")
one_problem(lambda p, r: p.update(title="x"), "title changed")
one_problem(lambda p, r: p.update(tags=["a"]), "tags changed")
one_problem(lambda p, r: p.update(descriptionHtml="<p>e</p>"), "description_sha changed")
one_problem(lambda p, r: p["options"][0]["values"].reverse(), "options changed")
one_problem(lambda p, r: r.update(commit_after="C3"), "not the new design")
DET = [a for _, a in G.detail_alts(TEE)][1]
one_problem(lambda p, r: (r.update(failed_in_resend=[DET]),
                          N(p).remove(next(m for m in N(p) if m["alt"] == DET))), "not rebuilt")
shop, rec = good()
rec["failed_in_resend"] = [DET]                              # rebuilt: present again
assert RR.check(None, shop, ROW, rec) == []
STORE["commits"] = {("T1", "C1"), ("T1", "C2")}            # some variants still on the old design
one_problem(lambda p, r: None, "Tapstitch prints from")
STORE["commits"] = {("T1", "C2")}
shop, rec = good()
shop.p["tags"].reverse()                                    # order of tags is not a change
assert RR.check(None, shop, ROW, rec) == []

# ---------------------------------------------------------------- driver

assert RR.next_step({}) == "snapshot_at"
assert RR.next_step({"snapshot_at": 1, "saved_at": 1}) == "resynced_at"
assert RR.next_step({s: 1 for s in RR.STEPS}) is None

CALLS = []
RR.ledger.load = lambda: {"rows": [ROW, dict(ROW, garment="crew"), dict(ROW, garment="hoodie")]}
RR.T.session = lambda: CALLS.append("session") or "S"
RR.ShopifyClient = lambda: CALLS.append("shopify") or "SC"

raises(lambda: RR.main(["--apply"]), "needs --temple or --limit")
assert CALLS == [], "the gate must refuse before opening any session"
RR.main([])                                                 # plan only
assert CALLS == [] and not RR.STATE_PATH.exists(), "plan mode writes nothing and opens nothing"

STEPLOG = []
for name in ("snapshot", "save", "resync", "restore", "gallery"):
    def fake(*a, _n=name):
        rec = a[-1]
        STEPLOG.append((_n, a[-2]["garment"]))
        rec[{"snapshot": "snapshot_at", "save": "saved_at", "resync": "resynced_at",
             "restore": "restored_at", "gallery": "gallery_at"}[_n]] = "t"
        if _n == "save":
            rec["commit_after"] = "C2"
        if _n == "restore":
            rec["worst_match"] = 0.0
    setattr(RR, f"step_{name}", fake)

FAIL = {"crew"}
RR.check = lambda s, sc, row, rec: ["boom"] if row["garment"] in FAIL else []
raises(lambda: RR.main(["--apply", "--limit", "3"]), "crew: verify failed")
state = json.loads(RR.STATE_PATH.read_text())["products"]
assert [n for n, _ in STEPLOG[:6]] == ["snapshot", "save"] * 3, "all saves before any re-send wait"
assert state["Alpha|tee"].get("verified_at")
assert "verified_at" not in state["Alpha|crew"], "a failed check must not mark the product verified"
assert state["Alpha|crew"].get("gallery_at")

# Resume: nothing saved twice, the crew goes straight to its check.
STEPLOG.clear()
FAIL.clear()
RR.main(["--apply", "--limit", "3"])
assert ("save", "tee") not in STEPLOG and ("save", "crew") not in STEPLOG and \
    ("save", "hoodie") not in STEPLOG, STEPLOG
state = json.loads(RR.STATE_PATH.read_text())["products"]
assert all(state[k].get("verified_at") for k in state), state

for _mod, _n, _v in _REAL:
    setattr(_mod, _n, _v)

print("all tests passed")
