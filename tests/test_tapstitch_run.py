"""Offline tests for the Tapstitch catalogue runner. No network.

Run: ./.venv.nosync/bin/python tests/test_tapstitch_run.py

WHY THIS FILE EXISTS. The runner's write path ends in distribute(), which puts a
product on the live storefront and has no undo, and the six-specialist review of
16 Sep 2026 found that two of its resume branches did the opposite of what its
own docstring promised: a row carrying only a template id rebuilt and orphaned
the first design, and a row that had already been published was distributed a
second time. Both were provable offline, before the code ever ran. This file is
what would have caught them.

WHAT IS PINNED HERE. Which API calls each starting state does and does not make,
and the ledger row each one leaves behind. That is the whole contract: the runner
is a sequencer, so "what did it call, in what order, and what did it write down"
is the behaviour, not an implementation detail.

NOT PINNED: which blanks are in the lineup, their colour codes, prices or print
areas. Those are Evan's choices and have changed repeatedly; the 14 Sep entry in
docs/decisions.md records two tests that failed on correct changes for exactly
that reason. Garment configs here are hand-built literals. The one real thing
they point at is `garment_copy`, because `description_for()` has to read actual
fixed sections to decide a description is complete; that folder is committed and
test_generate_channels.py already depends on it.
"""

import contextlib
import inspect
import io
import json
import shutil
import sys
import tempfile
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import generate
import ledger
import tapstitch_api as T
import tapstitch_run
import tapstitch_variant_images

GARMENT = {"garment_id": "tee", "price_usd": 44.99,
           "garment_copy": "reference/garment-copy/tee",
           "storefront_first_color": "Maroon",
           "naming": {"title": "Test Temple Tee ({place})",
                      "title_parent": "Test Temple Tee"},
           "print_area": {"position": "back"},
           "front_print_area": {"position": "front"},
           "colorways": [{"tapstitch": "Black", "shopify": "Black",
                          "ink": "white", "code": 8079},
                         {"tapstitch": "Wine Red", "shopify": "Maroon",
                          "ink": "white", "code": 8084}]}


# --- pure helpers -----------------------------------------------------------
# lead_color_id returning any field but `code` is a one-token bug that
# mockups_back_first documents as FAIL QUIET: the sort silently keeps Tapstitch's
# own order and every gallery opens on the wrong colour, with no error anywhere.
assert tapstitch_run.lead_color_id(GARMENT) == 8084, "must be the code, not a name"
assert tapstitch_run.ink_color(GARMENT) == "white"

mixed = dict(GARMENT, colorways=[dict(GARMENT["colorways"][0], ink="white"),
                                 dict(GARMENT["colorways"][1], ink="black")])
try:
    tapstitch_run.ink_color(mixed)
    raise AssertionError("colourways disagreeing about ink must raise: one "
                         "template prints ONE design")
except T.TapstitchError:
    pass

for bad in ({"storefront_first_color": "Nope"}, {"storefront_first_color": None}):
    try:
        tapstitch_run.lead_color_id(dict(GARMENT, **bad))
        raise AssertionError(f"{bad} must raise rather than resolve to nothing")
    except T.TapstitchError:
        pass


# --- selected() -------------------------------------------------------------
# What this admits decides what a re-run can touch. card-pushed and live must
# never come back: re-running must not republish a live product.
rows = [{"temple": "A", "garment": "tee", "state": s} for s in ledger.STATES]
rows.append({"temple": "B", "garment": "crew", "state": "file-approved"})
got = [(r["temple"], r["garment"], r["state"])
       for r in tapstitch_run.selected({"rows": rows}, set(), set())]
# card-pushed IS admitted: it means the fixups ran but the variant-image repair
# did not confirm, so the row is a live product still showing the blank front and
# the runner has to be able to finish it. live is never revisited.
assert got == [("A", "tee", "file-approved"), ("A", "tee", "product-created"),
               ("A", "tee", "card-pushed"), ("B", "crew", "file-approved")], got
assert "live" not in [r["state"] for r in tapstitch_run.selected({"rows": rows}, set(), set())]
assert len(tapstitch_run.selected({"rows": rows}, {"B"}, set())) == 1
assert len(tapstitch_run.selected({"rows": rows}, set(), {"tee"})) == 3


# --- blockers() -------------------------------------------------------------
def with_facts(text, fn):
    """Run fn with temple-facts.html present (or absent when text is None)."""
    real_working, real_print, real_manifest = (
        generate.working_path, tapstitch_run.print_files, generate.load_manifest)
    tmp = Path(tempfile.mkdtemp())
    try:
        facts = tmp / "temple-facts.html"
        if text is not None:
            facts.write_text(text)
        generate.working_path = lambda t, n, **k: facts
        tapstitch_run.print_files = lambda *a: ("back.png", "front.png")
        generate.load_manifest = lambda t: {"place_tokens": {"default": "Logan"}}
        return fn()
    finally:
        generate.working_path = real_working
        tapstitch_run.print_files = real_print
        generate.load_manifest = real_manifest
        shutil.rmtree(tmp, ignore_errors=True)


FACTS = '<section class="temple-facts">\n<h3>Logan Temple</h3>\n</section>'
row = {"temple": "Logan", "garment": "tee", "state": "file-approved"}

reasons = with_facts(FACTS, lambda: tapstitch_run.blockers(row, GARMENT, set()))
assert reasons == [], reasons

# Criterion 1: the intended title already on the store blocks the row. This is
# the guard that the ledger alone would have failed: the Salt Lake tee row said
# file-approved while that product was live.
title = with_facts(FACTS, lambda: generate.title_for("Logan", "tee", GARMENT))
reasons = with_facts(FACTS, lambda: tapstitch_run.blockers(row, GARMENT, {title}))
assert any("already exists on the store" in r for r in reasons), reasons

# ...but NOT once the row has a store product of its own. Its own title being on
# the store is then the expected outcome, and blocking it strands the very
# product this runner published, unable to finish it.
resuming = dict(row, tapstitch_store_product_id="sp1")
reasons = with_facts(FACTS, lambda: tapstitch_run.blockers(resuming, GARMENT, {title}))
assert reasons == [], f"a row that already has a store product must not be blocked by its own title: {reasons}"

# Criterion 4: no facts file, and the file present but carrying no facts section.
# The second case is why the gate reads the file rather than calling .exists():
# compose_description returns the fixed sections alone for empty facts, so the
# product would publish silently missing the section people actually read.
reasons = with_facts(None, lambda: tapstitch_run.blockers(row, GARMENT, set()))
assert any("no temple-facts.html" in r for r in reasons), reasons
for empty in ("", "   \n  ", "<p>notes to self</p>"):
    reasons = with_facts(empty, lambda: tapstitch_run.blockers(row, GARMENT, set()))
    assert any("temple-facts" in r for r in reasons), (empty, reasons)


# --- run_row(): the resume states -------------------------------------------
class FakeClient:
    """Shopify as the runner sees it: a title appears only once it is published.

    `calls` is the same list the Tapstitch fakes append to, so "has this been
    distributed yet" is answered the way reality answers it. Modelling this
    matters: with a client that always found the product, the runner's
    pre-distribute check would skip distribute on a FRESH row and the test would
    pass while proving nothing.

    `already_live` starts it in the state where a product under this title exists
    before the runner ever distributes, which is the hand-published case.

    `visible_after_lookups` models Tapstitch lag: the product exists but Shopify
    has not shown it yet, so the first N lookups answer None and a later one
    finds it. That is the only way to exercise the `distribute_started_at`
    branch, because a product the pre-distribute check can already see is skipped
    before that branch is ever reached.
    """

    def __init__(self, calls, handle="logan-temple-tee", already_live=False,
                 never_appears=False, visible_after_lookups=0):
        self.calls, self.handle = calls, handle
        self.already_live, self.never_appears = already_live, never_appears
        self.visible_after_lookups, self.lookups = visible_after_lookups, 0

    def gql(self, query, variables=None):
        """Answers the two read-backs finish_half does before it says `live`:
        wait_for_import's poll and stale_colorways' option read. Both report a
        finished, correctly renamed product, so these tests keep exercising the
        sequencing they were written for rather than the race."""
        if "options" in query:
            return {"productByHandle": {"options": [
                {"name": "Color", "values": ["Black"]}]}}
        return {"productByHandle": {
            "media": {"nodes": [{"id": "m1"}, {"id": "m2"}]},
            "variants": {"nodes": [
                {"id": "v1", "media": {"nodes": [{"id": "m1"}]}}]}}}

    def find_product_by_title(self, title):
        self.lookups += 1
        if self.never_appears:
            return None
        if self.lookups <= self.visible_after_lookups:
            return None
        if not self.already_live and "distribute" not in self.calls:
            return None
        return {"id": "gid://shopify/Product/1", "title": title,
                "handle": self.handle}


REBOUND = "logan-temple-tee: rebound 5 variant image(s) to the back"


def drive(row, publish=True, handle="logan-temple-tee", rebind_result=REBOUND,
          already_live=False, visible_after_lookups=0):
    """Run run_row against fakes. Returns (calls, final ledger row, result)."""
    calls = []
    real = {name: getattr(T, name) for name in
            ("create_template", "distribute", "get_template", "print_areas",
             "upload_print_file", "save_design", "store_product_prefill",
             "store_product_payload", "create_store_product")}
    real_finish = tapstitch_run.finish_on_shopify
    real_rebind = tapstitch_variant_images.rebind
    real_print, real_manifest, real_desc = (
        tapstitch_run.print_files, generate.load_manifest, generate.description_for)
    real_cfg = generate.load_garment_config
    real_path, real_md = ledger.LEDGER_PATH, ledger.LEDGER_MD
    real_wait, real_poll = tapstitch_run.SHOPIFY_WAIT_S, tapstitch_run.SHOPIFY_POLL_S
    tmp = Path(tempfile.mkdtemp())
    try:
        def record(name, ret=None):
            def f(*a, **k):
                calls.append(name)
                return ret
            return f

        T.create_template = record("create_template", "tmpl-NEW")
        T.distribute = record("distribute")
        T.get_template = record("get_template", {})
        # The tee's real rectangles, so placement() runs for real rather than
        # being stubbed: its aspect guard is one of the things that should fire
        # if a print file and a print area ever stop matching.
        T.print_areas = record("print_areas", {
            "back": {"x": 214, "y": 194, "width": 260, "height": 327},
            "front": {"x": 214, "y": 194, "width": 260, "height": 327}})
        T.upload_print_file = record("upload", "https://cdn/x.png")
        T.save_design = record("save_design")
        T.store_product_prefill = record("prefill", {})
        T.store_product_payload = record("payload", {})
        T.create_store_product = record("create_store_product", "sp-NEW")
        tapstitch_run.finish_on_shopify = lambda *a, **k: (
            calls.append("finish_on_shopify") or ["finished"])
        tapstitch_variant_images.rebind = lambda *a, **k: (
            calls.append("rebind") or rebind_result)
        # Real (tiny) PNGs: save_design reads each file's size with PIL to build
        # the placement, so stubbing the path is not enough.
        pngs = []
        for name in ("back.png", "front.png"):
            path = tmp / name
            Image.new("RGBA", (4386, 5516)).save(path)
            pngs.append(path)
        tapstitch_run.print_files = lambda *a: tuple(pngs)
        generate.load_manifest = lambda t: {"place_tokens": {"default": "Logan"}}
        generate.description_for = lambda t, c: ("<p>desc</p>", None)
        generate.load_garment_config = lambda gid: GARMENT
        ledger.LEDGER_PATH, ledger.LEDGER_MD = tmp / "l.json", tmp / "l.md"
        # A hang is how a broken scenario hid once already: the marker case polled
        # for the real five minutes. Zero here turns that into an instant failure.
        tapstitch_run.SHOPIFY_WAIT_S = tapstitch_run.SHOPIFY_POLL_S = 0

        # Built from blank_row so the fixture cannot drift from the shape real
        # rows have: write_markdown reads fields (problems, files) that a
        # hand-built dict is easy to forget, and ledger.save writes the markdown.
        data = {"rows": [dict(ledger.blank_row(row["temple"], row["garment"]), **row)]}
        result = tapstitch_run.run_row(
            T.session,
            FakeClient(calls, handle, already_live,
                       visible_after_lookups=visible_after_lookups), data,
                                       data["rows"][0], publish, lambda m: None)
        return calls, data["rows"][0], result
    finally:
        for name, fn in real.items():
            setattr(T, name, fn)
        tapstitch_run.finish_on_shopify = real_finish
        tapstitch_variant_images.rebind = real_rebind
        tapstitch_run.print_files, generate.load_manifest = real_print, real_manifest
        generate.description_for, generate.load_garment_config = real_desc, real_cfg
        ledger.LEDGER_PATH, ledger.LEDGER_MD = real_path, real_md
        tapstitch_run.SHOPIFY_WAIT_S, tapstitch_run.SHOPIFY_POLL_S = real_wait, real_poll
        shutil.rmtree(tmp, ignore_errors=True)


FRESH = {"temple": "Logan", "garment": "tee", "state": "file-approved"}

# A fresh row builds and, without --publish, stops dead before distribute.
calls, saved, result = drive(FRESH, publish=False)
assert "distribute" not in calls, f"publish=False must never distribute: {calls}"
assert result == "product-created" and saved["state"] == "product-created"
assert saved["tapstitch_template_id"] == "tmpl-NEW"
assert saved["tapstitch_store_product_id"] == "sp-NEW"

# A fresh row with --publish runs the whole sequence, distributing exactly once.
calls, saved, result = drive(FRESH)
assert calls.count("distribute") == 1, calls
assert calls.index("create_store_product") < calls.index("distribute")
assert calls.index("distribute") < calls.index("finish_on_shopify") < calls.index("rebind")
assert result == "live" and saved["state"] == "live"
assert saved["distribute_started_at"], "the distribute marker must be written"

# TEMPLATE ONLY: the crash window between create_template and create_store_product.
# Rebuilding here orphans the first design AND overwrites the only record of it,
# which is what the review caught.
calls, saved, _ = drive(dict(FRESH, tapstitch_template_id="tmpl-OLD"), publish=False)
assert "create_template" not in calls, f"must reuse the recorded template: {calls}"
assert "save_design" in calls, "the design still has to be saved onto it"
assert saved["tapstitch_template_id"] == "tmpl-OLD", saved["tapstitch_template_id"]

# STORE PRODUCT ONLY: resume at distribute, never build a second design.
calls, saved, _ = drive(dict(FRESH, state="product-created",
                             tapstitch_template_id="tmpl-OLD",
                             tapstitch_store_product_id="sp-OLD"))
assert "create_template" not in calls and "create_store_product" not in calls, calls
assert calls.count("distribute") == 1, calls

# BUILT WITH --apply, THEN PUBLISHED BY HAND from the Tapstitch UI. The ledger has
# a store product id and no distribute marker, so the resume path would have
# distributed an id that was already distributed. The last look at the store
# before the no-undo call is what catches it.
calls, saved, result = drive(dict(FRESH, state="product-created",
                                  tapstitch_template_id="tmpl-OLD",
                                  tapstitch_store_product_id="sp-OLD"),
                             already_live=True)
assert "distribute" not in calls, f"must not distribute a product already on the store: {calls}"
assert result == "live"

# ALREADY DISTRIBUTED, confirmation lost, and Shopify has not shown the product
# yet. This is the one path that could put a duplicate on the storefront, and the
# scenario has to be modelled exactly: the product DOES exist (already_live) but
# the pre-distribute lookup cannot see it yet (visible_after_lookups=1, Tapstitch
# lag measured at over a minute). Without the lag the pre-distribute check
# short-circuits and the marker branch below is never reached, which is how an
# earlier version of this test passed with that branch deleted.
calls, saved, _ = drive(dict(FRESH, state="product-created",
                             tapstitch_template_id="tmpl-OLD",
                             tapstitch_store_product_id="sp-OLD",
                             distribute_started_at="2026-09-16T10:00:00"),
                        already_live=True, visible_after_lookups=1)
assert "distribute" not in calls, f"must not distribute twice: {calls}"
assert "finish_on_shopify" in calls, "it should still finish the row"

# ALREADY LIVE: a row that crashed after publishing resumes at the Shopify half
# rather than being stranded, and never goes near distribute.
calls, saved, result = drive(dict(FRESH, state="product-created",
                                  tapstitch_template_id="tmpl-OLD",
                                  tapstitch_store_product_id="sp-OLD",
                                  shopify_handle="logan-temple-tee"))
assert "distribute" not in calls and "create_store_product" not in calls, calls
assert calls == ["finish_on_shopify", "rebind"], calls
assert result == "live"

# A rebind that reports a failure must NOT be recorded as live. rebind returns
# its failures as strings rather than raising, so a truthy return is not success,
# and the repo's own history calls a front-bound variant "the one that would have
# failed quietly".
live_row = dict(FRESH, state="product-created", tapstitch_store_product_id="sp-OLD",
                shopify_handle="logan-temple-tee")
for failure in ("logan-temple-tee: no such Shopify product",
                "logan-temple-tee: Tapstitch returned no front/back mockup pairs"):
    try:
        drive(live_row, rebind_result=failure)
        raise AssertionError(f"a failed variant rebind must not reach live: {failure}")
    except T.TapstitchError:
        pass

# None means rebind found nothing to change, which IS success: the variants were
# already on the back.
_, saved, result = drive(live_row, rebind_result=None)
assert result == "live" and saved["state"] == "live"


# --- wait_for_shopify -------------------------------------------------------
# A product that never appears must raise and say the row is already recorded as
# distributed, because the alternative reading (retry the distribute) is the one
# that duplicates a live listing.
try:
    tapstitch_run.wait_for_shopify(FakeClient([], never_appears=True), "Nope", timeout_s=0)
    raise AssertionError("a product that never appears must raise")
except T.TapstitchError as e:
    assert "distributed" in str(e), str(e)


# --- the command-line gates -------------------------------------------------
# These are the whole safety story for the one call with no undo, so they are
# pinned at the argparse layer too, not just at run_row's. Each must refuse
# BEFORE a Shopify client or a Tapstitch session is constructed: a refusal that
# happens after the catalogue is fetched still works, but it means the guard is
# sitting downstream of network calls it was meant to precede.
def refuses(argv, needle):
    real_argv, real_client, real_session = sys.argv, tapstitch_run.ShopifyClient, T.session

    def boom(*a, **k):
        raise AssertionError(f"{argv}: built a client/session before refusing")

    try:
        sys.argv = ["tapstitch_run.py"] + argv
        tapstitch_run.ShopifyClient, T.session = boom, boom
        try:
            tapstitch_run.main()
            raise AssertionError(f"{argv} must refuse")
        except SystemExit as e:
            assert needle in str(e), f"{argv}: expected {needle!r}, got {str(e)!r}"
    finally:
        sys.argv, tapstitch_run.ShopifyClient, T.session = real_argv, real_client, real_session


def plan_only_opens_no_session():
    """A bare run must return 0 without ever opening a Tapstitch session.

    This is the invocation Evan runs casually. The plausible regression is the
    `if not a.apply: return` block drifting below `T.session()`, which would turn
    a plan into a write run with no flag change at all.
    """
    real_argv, real_client, real_session = sys.argv, tapstitch_run.ShopifyClient, T.session
    real_load, real_blockers = ledger.load, tapstitch_run.blockers

    def boom(*a, **k):
        raise AssertionError("plan mode opened a Tapstitch session")

    class Catalogue:
        def all_products_summary(self):
            return []

    try:
        sys.argv = ["tapstitch_run.py"]
        T.session = boom
        tapstitch_run.ShopifyClient = lambda *a, **k: Catalogue()
        ledger.load = lambda: {"rows": [
            {"temple": "Logan", "garment": "tee", "state": "file-approved"}]}
        tapstitch_run.blockers = lambda *a, **k: []
        with contextlib.redirect_stdout(io.StringIO()):
            assert tapstitch_run.main() == 0, "plan mode must exit 0"
    finally:
        sys.argv, tapstitch_run.ShopifyClient, T.session = real_argv, real_client, real_session
        ledger.load, tapstitch_run.blockers = real_load, real_blockers


plan_only_opens_no_session()

# The runner passes write_description=False so the description is not written
# twice. The fake below accepts **kwargs, so a rename would sail past it and
# only fail on a live run, in finish_half, AFTER distribute has published the
# product. Assert against the real signature instead.
assert "write_description" in inspect.signature(
    tapstitch_run.finish_on_shopify).parameters, \
    "finish_on_shopify lost write_description; the runner would double-write"

refuses(["--publish"], "needs --apply")
refuses(["--apply", "--publish"], "needs a bound")
refuses(["--apply", "--limit", "0"], "would not build anything")
refuses(["--apply", "--limit", "-3"], "would not build anything")
refuses(["--garments", "hoody"], "Unknown garment id")
refuses(["--temple", "Nowhere"], "no temple named")


# --- the error text written to a tracked file -------------------------------
# requests puts the whole URL in transport errors and the upload's URL is a
# signed OSS one carrying the account login id and signature in its query string.
# ledger.json and LEDGER.md are both tracked in git.
err = RuntimeError("HTTPSConnectionPool: Max retries with url: "
                   "/tapstitch/material/custom_printing/12345/abc.png?Signature=SECRET&x=1")
assert "Signature" not in tapstitch_run.safe_error(err), tapstitch_run.safe_error(err)
assert "SECRET" not in tapstitch_run.safe_error(err)
assert len(tapstitch_run.safe_error(err)) <= 200

# --- the import race that published a near-blank garment on 16 Sep 2026 -----
# wait_for_shopify returns as soon as the product record exists, but Tapstitch
# keeps pushing variants and media after that. Running the fixups inside that
# window cost one product of 102: its colour rename was overwritten and all ten
# variants stayed bound to the FRONT mockup, and both steps logged success.

class _FakeClient:
    """Replays a sequence of productByHandle payloads, one per poll."""
    def __init__(self, payloads):
        self.payloads, self.calls = list(payloads), 0
    def gql(self, query, variables=None):
        i = min(self.calls, len(self.payloads) - 1)
        self.calls += 1
        return {"productByHandle": self.payloads[i]}


def _product(n_variants, n_bound, n_media):
    return {"media": {"nodes": [{"id": f"m{i}"} for i in range(n_media)]},
            "variants": {"nodes": [
                {"id": f"v{i}",
                 "media": {"nodes": [{"id": "m0"}] if i < n_bound else []}}
                for i in range(n_variants)]}}


tapstitch_run.SHOPIFY_POLL_S = 0  # no real sleeping in tests

# Settles only after the counts repeat with every variant bound.
c = _FakeClient([_product(10, 0, 0), _product(10, 4, 2), _product(10, 10, 20),
                 _product(10, 10, 20)])
note = tapstitch_run.wait_for_import(c, "h", timeout_s=5)
assert "settled" in note and "10 variants" in note, note
assert c.calls == 4, c.calls

# A product whose variants never get images must RAISE, not be called ready.
c = _FakeClient([_product(10, 0, 0)])
try:
    tapstitch_run.wait_for_import(c, "h", timeout_s=0)
    raise AssertionError("expected a raise for a product still importing")
except T.TapstitchError as e:
    assert "still importing" in str(e), e

# One poll where everything looks bound is NOT enough: an import that has
# delivered the first colourway looks complete when it is not. The counts have
# to be seen twice, and a change between polls resets the confirmation.
c = _FakeClient([_product(5, 5, 10), _product(10, 10, 20), _product(10, 10, 20)])
note = tapstitch_run.wait_for_import(c, "h", timeout_s=5)
assert "10 variants" in note, note
assert c.calls == 3, c.calls

# rebind must not report "nothing needed changing" for a product with no images.
import tapstitch_variant_images


class _RebindClient:
    def __init__(self, variants):
        self.variants = variants
    def find_product_by_handle(self, handle):
        return {"id": "gid://shopify/Product/1"}
    def gql(self, query, variables=None):
        return {"product": {"media": {"nodes": [{"id": "m1", "image": {"url": "http://x/front.png"}}]},
                            "variants": {"nodes": self.variants}}}


_saved = tapstitch_variant_images.T.store_product_prefill, tapstitch_variant_images.T.back_for_front_mockups
tapstitch_variant_images.T.store_product_prefill = lambda *a, **k: {}
tapstitch_variant_images.T.back_for_front_mockups = lambda pre: {"front.png": "back.png"}
try:
    unbound = [{"id": "v1", "title": "Black / L", "media": {"nodes": []}}]
    out = tapstitch_variant_images.rebind(_RebindClient(unbound), None, "h", "t")
    assert out is not None, "a variant with no image must not read as 'already correct'"
    assert "carry no image yet" in out, out
finally:
    tapstitch_variant_images.T.store_product_prefill, tapstitch_variant_images.T.back_for_front_mockups = _saved


print("all tests passed")
