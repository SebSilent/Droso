"""E8 aborted at its own pre-registered condition — pinned so it cannot drift.

Pre-registered in docs/evidence/e8_preregistration.md.  `POLAR_ABSENCE_MEANS_NO`
was proposed to answer `no` to three polar asks whose expected answer is `no`,
and was ABORTED before implementation because the licence it required — an
inventory the organism actually holds — does not exist.

These tests are unusual in that they pin an ABSENCE.  That is the point: the
abort is a decision with evidence behind it, and without a test the next pass
could add the flag, see the frozen score move 19/24 -> 20/24, and read that as
a repair rather than as the confabulation the abort condition was written to
prevent.  A wrong `no` scores the same as silence on this battery and asserts
something false; only the tests and the pre-registration tell them apart.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from organs.neural_language import NeuralLanguage
from tools.heldout_eval import cause_of, stage_of

ROOT = Path(__file__).resolve().parents[1]
SEL = ROOT / "state" / "selection"
ORGAN = ROOT / "organs" / "neural_language.py"

MOOD = "it understood but did not feel like speaking"

# The three asks E8 targeted: one proposition in three framings, all wanting `no`.
POLAR_ASKS = {
    "does the door hold the frost?",
    "is it true that the door holds the frost?",
    "is the frost held by the door?",
}


def load(gen):
    p = SEL / f"generation_{gen}_asks.jsonl"
    if not p.exists():
        pytest.skip(f"{p.name} not published yet")
    return [json.loads(x) for x in
            p.read_text(encoding="utf-8").splitlines() if x.strip()]


# ------------------------------------------------------- the flag is absent ----

def test_the_organ_has_no_polar_absence_flag():
    """E8 was aborted, so the flag must not exist.

    Checked on the class rather than the module: the two flags that DO ship
    (`ANSWER_COVERAGE_FLOOR`, `RECALL_UNFILTERED_FALLBACK`) are class attributes
    beside each other, so a third would be too.
    """
    assert not hasattr(NeuralLanguage, "POLAR_ABSENCE_MEANS_NO")


def test_the_flag_is_not_present_anywhere_in_the_organ_source():
    """A flag wired in but not exposed as a class attribute still counts."""
    src = ORGAN.read_text(encoding="utf-8")
    assert "POLAR_ABSENCE_MEANS_NO" not in src
    assert "polar-absence" not in src


def test_the_two_flags_that_do_ship_are_still_there_and_default_off():
    """Guard against the abort being implemented by deleting the wrong thing."""
    assert NeuralLanguage.RECALL_UNFILTERED_FALLBACK is False
    assert isinstance(NeuralLanguage.ANSWER_COVERAGE_FLOOR, float)


# ------------------------------------------- the standing prohibition holds ----

def test_the_ordinal_path_still_refuses_rather_than_saying_no():
    """`_ordinal_answer` carries the pre-registered prohibition on `no`.

    Reversing it must require an explicit edit to that docstring, not a silent
    change of behaviour elsewhere.  Defect B is the same defect E8 targeted.
    """
    doc = NeuralLanguage._ordinal_answer.__doc__ or ""
    assert "never says `no`" in doc
    assert "false negative" in doc


def test_the_ordinal_path_has_no_negative_answer_to_give():
    """The prohibition is not merely documented — there is no `no` in the code."""
    src = re.search(r"def _ordinal_answer\(.*?\n    def ",
                    ORGAN.read_text(encoding="utf-8"), re.S)
    assert src, "could not isolate _ordinal_answer"
    body = src.group(0)
    assert '"no"' not in body and "'no'" not in body


# ------------------------------------- the measured basis of the abort ----

@pytest.mark.parametrize("gen", [9, 10])
def test_the_polar_asks_are_refused_on_mood_before_any_retrieval(gen):
    """`coverage: None` and `source: None` are the evidence that no answer formed.

    This is what makes E8 unsound rather than merely unimplemented: there is no
    suppressed negative to unlock.  The mood gate at organs/neural_language.py
    :3956-3977 fires first, so emitting `no` would fabricate a proposition.
    """
    rows = [r for r in load(gen) if r["ask"] in POLAR_ASKS]
    assert len(rows) == 3, f"expected the three polar asks in generation {gen}"
    for r in rows:
        assert r["spoken"] is False
        assert r["reason"] == MOOD
        assert r.get("coverage") is None, "recall gate must not have executed"
        assert r.get("source") is None, "no answer must have been formed"
        assert r["pass"] is False


@pytest.mark.parametrize("gen", [9, 10])
def test_the_mood_refusal_is_gating_not_comprehension_or_recall(gen):
    """`cause` keeps the mood refusal distinct from the two defects it was
    previously conflated with — the whole reason the field exists.

    The value is `gating`, not a renamed `reply_gate`: `cause_of` only ever
    reclassifies OUT OF `recall` and passes every other stage through untouched
    (prediction P5 of the `cause` pre-registration, confirmed).  An earlier draft
    of this test asserted `reply_gate` and failed, which is the correct outcome —
    inventing a second name for a stage that was never mislabelled would have
    been the same error `cause` was added to fix.
    """
    rows = [r for r in load(gen) if r["ask"] in POLAR_ASKS]
    for r in rows:
        turn = {"reply": {"reason": r["reason"], "spoken": False}}
        assert stage_of(turn, "answer slot empty") == "gating"
        assert cause_of(turn, "gating") == "gating"
        # The point of the field: this reason is NOT the comprehension defect and
        # NOT the coverage gate, though all three sat in one bucket before gen 10.
        assert cause_of(turn, "gating") != "comprehension"
        assert cause_of(turn, "gating") != "recall_gate"
        if "cause" in r:                      # generation 10 onward only
            assert r["cause"] == "gating"


def test_the_polar_asks_are_one_proposition_not_three_defects():
    """The census claim that makes `gating` the best ratio: 3 asks, 1 defect.

    All three reduce to `holds(door, frost)`, differing only in framing —
    declarative, `is it true that`, and passive.  A repair that needed three
    mechanisms would not be worth +1 frozen.
    """
    rows = [r for r in load(10) if r["ask"] in POLAR_ASKS]
    assert {r["reason"] for r in rows} == {MOOD}
    assert {r.get("coverage") for r in rows} == {None}
    assert len({r["script"] for r in rows}) == 2, "one taught, one selection variant"


def test_the_taught_inventory_is_two_relations_and_excludes_the_queried_one():
    """The script does establish a closed inventory, so `no` is genuinely correct.

    Recorded because the abort is about the MECHANISM, not the expected answer:
    `holds(door, frost)` is absent from {bites(frost,latch), holds(latch,door)}.
    E8' must reproduce this from session `who == "you"` rows, not from the binder.
    """
    scripts = json.loads(
        (ROOT / "tools" / "scripts_heldout.json").read_text(encoding="utf-8"))
    s = next(x for x in scripts["scripts"] if x["name"] == "hop-and-inventory")
    tells = [t["say"] for t in s["turns"] if "say" in t]
    assert tells == ["the frost bites the latch", "the latch holds the door"]
    polar = next(t for t in s["turns"] if t.get("ask") ==
                 "does the door hold the frost?")
    assert polar["expect"]["answer"] == ["no"]
    assert polar["expect"]["forbid"] == ["yes"]
    assert "the door holds the frost" not in tells
