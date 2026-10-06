"""Offline tests for the Easify option-set sync. No network.

Run: ./.venv.nosync/bin/python tests/test_easify_options.py

WHY THIS FILE EXISTS. cmd_sync writes the CSV that drives the Temple dropdown on
every live product page, and one guard stands between a bad catalogue read and a
CSV that blanks that dropdown everywhere: a populated set whose garment has no
live products hard-stops the run. On 16 Sep 2026 the catalogue sweep published
102 products and then could not run the sync at all, because that guard fired on
a line that was PAUSED and therefore had zero live products by design. The fix put a hole in the guard, keyed on one config field. A hole in the
only safety check on a catalogue-wide write is worth pinning, and until this file
there was no test importing easify_options at all.

WHAT IS PINNED HERE. The three behaviours at that seam: the guard still fires for
an active line, a paused line passes through untouched rather than stopping the
run, and a paused line that turns out to HAVE live products is an error rather
than a silent skip. That last one is what keeps the flag load-bearing: without
it, relaunching a paused line without clearing the flag would produce a clean
looking run and a dropdown still pointing at drafted pages.

NOT PINNED: which lines are actually paused. That is a lineup fact that can flip
any day, and the 14 Sep
entry in docs/decisions.md records two tests that went red on correct changes for
exactly that reason. The config here is a hand-built literal and the CSV is a
trimmed fixture with fake handles.
"""

import contextlib
import copy
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import easify_options as E

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "easify" / "option-sets.csv"

# Two sets, each a default row plus temple rows labelled Aaa and Bbb whose URLs
# point at old-<set>-<temple> handles. Alpha is the active line, Beta stands in
# for the paused one.
CONFIG = [
    {"garment": "tee", "set_title": "Alpha", "option_name": "Temple Alpha"},
    {"garment": "crew", "set_title": "Beta", "option_name": "Temple Beta"},
]
TOKENS = {"Aaa": "Aaa", "Bbb": "Bbb"}


def run(config, live, report_only=True):
    """Drive cmd_sync with the Shopify read and the real files patched out.

    Patch the loader functions rather than the CANONICAL constant:
    load_canonical binds its default argument at definition time, so rebinding
    the constant would not change what it reads.

    Returns (stdout, captured) where captured records what validate_output was
    handed, which is the only view of the rows the run would have written.
    """
    captured = {}
    originals = (E.load_config, E.load_canonical, E.temple_tokens,
                 E.live_temple_products, E.validate_output)

    def fake_live(cfg, tokens):
        expected = {s["garment"]: dict(live.get(s["garment"], {})) for s in cfg}
        conflicted = {s["garment"]: set() for s in cfg}
        return expected, conflicted, []

    def spy_validate(fieldnames, out_rows, in_sets, touched, expected_by_title):
        captured["out_rows"] = copy.deepcopy(out_rows)
        captured["touched"] = set(touched)
        return originals[4](fieldnames, out_rows, in_sets, touched, expected_by_title)

    E.load_config = lambda: copy.deepcopy(config)
    E.load_canonical = lambda *a, **k: originals[1](FIXTURE)
    E.temple_tokens = lambda: dict(TOKENS)
    E.live_temple_products = fake_live
    E.validate_output = spy_validate
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            E.cmd_sync(report_only=report_only)
    finally:
        (E.load_config, E.load_canonical, E.temple_tokens,
         E.live_temple_products, E.validate_output) = originals
    return buf.getvalue(), captured


def fixture_rows(set_title):
    _, rows = E.load_canonical(FIXTURE)
    return E.group_by_set(rows)[set_title]


def paused(config, set_title):
    out = copy.deepcopy(config)
    for s in out:
        if s["set_title"] == set_title:
            s["paused"] = True
    return out


# --- the guard still fires for an ACTIVE line with an empty catalogue --------
# This is the whole reason the guard exists: zero live products for a populated
# set means a broken read (wrong store domain, bad filter), and rewriting the
# CSV from it would blank the dropdown on every product page.
live_ok = {"tee": {"Aaa": ("Aaa", "new-alpha-aaa")}, "crew": {"Aaa": ("Aaa", "new-beta-aaa")}}

try:
    run(CONFIG, {"tee": {}, "crew": live_ok["crew"]})
    raise AssertionError("expected SystemExit for an active set with no live products")
except SystemExit as e:
    assert "Refusing to blank" in str(e), e

# Every garment empty is the wrong-store-domain case, and must also stop.
try:
    run(CONFIG, {"tee": {}, "crew": {}})
    raise AssertionError("expected SystemExit when the whole catalogue reads empty")
except SystemExit as e:
    assert "Refusing to blank" in str(e), e



# "paused": false must behave exactly like no flag at all. Pinned because the
# obvious loosening of the check, `"paused" in spec`, passes every other test in
# this file while silently disabling the guard for an active line.
explicitly_not_paused = copy.deepcopy(CONFIG)
for _s in explicitly_not_paused:
    if _s["set_title"] == "Alpha":
        _s["paused"] = False
try:
    run(explicitly_not_paused, {"tee": {}, "crew": live_ok["crew"]})
    raise AssertionError('"paused": false must not disable the guard')
except SystemExit as e:
    assert "Refusing to blank" in str(e), e

# --- a PAUSED line passes through instead of stopping the run ---------------
# Alpha is repointed in this same run, which matters for two reasons: it is the
# point of not letting a paused set stop everything, and it clears the "No
# changes" early return so Beta's rows genuinely reach validate_output.
out, captured = run(paused(CONFIG, "Beta"), {"tee": live_ok["tee"], "crew": {}})
assert "Beta: crew is paused, set left untouched" in out, out
assert "Refusing to blank" not in out

alpha = [r for r in captured["out_rows"] if r["option_set_title"] == "Alpha"]
alpha_urls = {r["option_value_label"]: E.value_url(r) for r in alpha}
assert alpha_urls["Aaa"] == E.STORE + "new-alpha-aaa", alpha_urls
assert "Alpha" in captured["touched"]

# The paused set reaches the writer as the SAME rows, not merely equivalent
# ones, which is why this is dict equality rather than semantically_equal. It
# fails if the paused branch ever moves below reconcile_set. Staying out of
# `touched` is asserted separately, directly.
beta_out = [r for r in captured["out_rows"] if r["option_set_title"] == "Beta"]
assert beta_out == fixture_rows("Beta"), "paused set was modified"
assert "Beta" not in captured["touched"], "paused set must stay untouched"


# --- a paused flag that has outlived its pause is an ERROR, not a skip -------
# The flag asserts "no live products by design". Once that stops being true,
# skipping quietly would leave the dropdown on the old drafted handles and say
# nothing, which is the failure the guard exists to prevent.
try:
    run(paused(CONFIG, "Beta"), {"tee": live_ok["tee"], "crew": live_ok["crew"]})
    raise AssertionError("expected SystemExit for a paused set with live products")
except SystemExit as e:
    assert "marked paused" in str(e), e
    assert "Beta" in str(e), e


# --- a paused set that is not in the CSV at all is not created --------------
out, captured = run(paused(CONFIG, "Beta") + [{"garment": "hoodie", "set_title": "Gamma",
                                              "option_name": "Temple Gamma",
                                              "clone_from": "Alpha", "paused": True}],
                    {"tee": live_ok["tee"], "crew": {}, "hoodie": {}})
assert all(r["option_set_title"] != "Gamma" for r in captured["out_rows"]), "Gamma was created"
assert "set not created" in out, out

print("all tests passed")
