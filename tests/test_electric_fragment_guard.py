"""The arbiter-head fragment leak: a licensed absence falling through to fragment speech.

MEASURED, minimal repro (two asks, one organ, nothing else):

    answer("who does the mouse chase to?")   # heard, and remembered as a proposition
    answer("who does the mouse chase?")      # -> spoken, source 'arbiter head', said 'to?'

The organ remembered a QUESTION and then answered from it. `_shape_matches` reads a hit's
token list without asking what kind of turn it came from, so for the bare ask the stranded
variant matches (verb `chase`, subject `mouse`) and the post-verbal token it returns as the
"filler" is `to?` -- a stranded preposition with the question mark still on it. Line 4147
utters that as an answer.

Two things this file pins that the flag name hides:
  * the leak is NOT an ELECTRIC defect. It reproduces with ELECTRIC off entirely
    (`_m.build(False)`), because the branch is in the recall path. So `--electric-fragment-guard`
    is read outside the --electric block.
  * the leak is NOT reachable in a corpus-backed house. The live check (a real
    `converse.build`) refused at the coverage floor -- "the closest memory of his covers 37%"
    -- before the arbiter branch ran. It needs the corpus-free condition the ELECTRIC demo
    builds. That is why the guard is off by default and why this is a guard, not a rewrite.
"""

import importlib.util as _u
import io
import sys

sys.path.insert(0, ".")

_s = _u.spec_from_file_location("rev_fg", "tools/electric_reverse_ab.py")
_m = _u.module_from_spec(_s)
_s.loader.exec_module(_m)

import organs.neural_language as nl  # noqa: E402

STRANDED = "who does the mouse chase to?"
BARE = "who does the mouse chase?"
FRAGMENT = "to?"


def _organ(electric=True, guard=True):
    o = _m.build(electric)
    o.ELECTRIC_TEACH = False          # no write permission during measurement
    o.ELECTRIC_FRAGMENT_GUARD = guard
    o.answer(STRANDED)                # the precondition: the stranded ask is in memory
    return o


def _said(out):
    out = out or {}
    return str(out.get("utterance") or out.get("response") or "").strip()


# ------------------------------------------------------------------ the hazard, as-is

def test_without_the_guard_a_remembered_question_is_spoken_as_an_answer():
    """Pinned with the guard OFF, so the leak stays visible in the suite rather than
    living only in a doc. If this ever goes silent on its own, that is a real change and
    this test says so loudly."""
    o = _organ(guard=False)
    out = o.answer(BARE)
    assert out.get("spoken") is True, f"expected the fragment, got {out}"
    assert out.get("source") == "arbiter head", out.get("source")
    assert _said(out) == FRAGMENT, _said(out)


def test_the_leak_is_the_houses_not_electrics():
    """Same two asks with ELECTRIC off entirely: still `to?`. This is what makes the
    switch a recall-path guard rather than a fourth ELECTRIC permission."""
    o = _organ(electric=False, guard=False)
    out = o.answer(BARE)
    assert out.get("source") == "arbiter head" and _said(out) == FRAGMENT, \
        "the leak moved or vanished without --electric -- re-read the mechanism"


# ---------------------------------------------------------------------- the guard

def test_the_guard_returns_the_licensed_absence_instead_of_the_fragment():
    o = _organ(guard=True)
    out = o.answer(BARE) or {}
    assert out.get("spoken") is False, f"fragment still spoken: {out}"
    assert out.get("source") != "arbiter head"
    assert "asking" in str(out.get("reason")), out.get("reason")
    assert out.get("answered") is False


def test_the_guard_is_off_by_default():
    assert nl.NeuralLanguage.ELECTRIC_FRAGMENT_GUARD is False, \
        "the guarded battery's outputs include this leak; enabling by default would "


def test_the_guard_does_not_reject_a_content_word():
    """`mouse`, `latch`, `bell` are fragments of speech too, but they are words with a
    referent and some ask wants them. The guard rejects only what could never be a fact."""
    for bad in ("to?", "to", "what", "who", "does", "", "of"):
        assert nl._is_question_fragment(bad), bad
    for good in ("mouse", "latch", "bell", "lantern", "the mouse chases the cat", "twice"):
        assert not nl._is_question_fragment(good), good


def test_the_guard_changes_only_the_row_that_would_have_spoken_a_fragment():
    """An unrelated ask must come out identical with the guard on and off -- the guard is
    a refusal of one utterance shape, not a re-routing of the answer path."""
    a = _organ(guard=False).answer("what turns twice?")
    b = _organ(guard=True).answer("what turns twice?")
    assert (_said(a), (a or {}).get("source")) == (_said(b), (b or {}).get("source"))


# ----------------------------------------------------------------- wiring and contract

def test_serve_reads_the_switch_outside_the_electric_block():
    s = io.open("tools/serve.py", encoding="utf-8").read()
    assign = s.index("agent.language.ELECTRIC_FRAGMENT_GUARD = bool(args.electric_fragment_guard)")
    assert assign < s.index("    if args.electric:"), \
        "inside the --electric block the switch is dead without --electric, which the " \
        "measurement above refutes"
    assert "--electric-fragment-guard" in s
    assert "Independent of --electric" in s, "help text must not claim ELECTRIC scope"
    assert "Within --electric only: when nothing" not in s


def test_the_measured_arms_do_not_see_the_new_switch():
    """C4d/C4e's numbers were produced by these tools. If an arm started setting the guard,
    the recorded result would no longer describe the code that produced it."""
    for p in ("tools/electric_reverse_ab.py", "tools/electric_object_ab.py"):
        s = io.open(p, encoding="utf-8").read()
        assert "ELECTRIC_FRAGMENT_GUARD" not in s, p
    r = io.open("tools/electric_reverse_ab.py", encoding="utf-8").read()
    for verdict in ("correct", "miss", "refusal", "CONFABULATION"):
        assert verdict in r, f"grader verdict {verdict} disappeared from the contract"
