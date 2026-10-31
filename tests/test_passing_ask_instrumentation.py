"""The passing-ask measurement repair.

Eight experiments each had to re-derive the passing side of a pass/fail pair from
scratch, because `stage`, `cause`, `coverage`, `required` and `nearest` were
recorded only on failures. `docs/evidence/paraphrase_gap_diagnosis.md` could not
compare a failing ask to its passing twin at all, and its probe printed a wrong
"bypasses the gate" inference that had to be retracted, because a blank coverage
on a passing ask was ambiguous between "computed and None" and "never computed".

The repair is ADDITIVE. These tests pin the three properties that make it safe:

  1. `stage` and `cause` stay gated on failure EXACTLY as generations 0-14
     published them, so no archived journal and no historical comparison changes.
  2. `stage_all` / `cause_all` / `coverage_present` are populated for EVERY ask,
     passing and failing alike -- that is the whole point.
  3. No score can move: `pass`, `said`, `words`, `spoken` and `why` are computed
     from the same inputs as before, and the new keys are read-only derivations.

Zero brain builds: `ask_record` is driven by a fake session.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.heldout_eval import ask_record, cause_of, stage_of  # noqa: E402


class _FakeSession:
    """Returns one canned turn per ask, so no brain is built."""

    def __init__(self, turn):
        self._turn = turn
        self.calls = []

    def ask(self, text, kind=None):
        self.calls.append((text, kind))
        return self._turn


def _turn(reply, spoken_text="the lantern", error=None):
    """converse._spoken requires reply["spoken"] (or "answered") AND a non-empty
    _said(turn). _said reads the reply rather than the turn, so `said` is mirrored
    into both and `spoken` defaults on; a fixture that omits either grades as a
    refusal and the test silently measures the wrong branch."""
    r = dict(reply)
    r.setdefault("spoken", True)
    # converse._said reads reply["utterance"] (then "response"), NOT turn["said"].
    r.setdefault("utterance", spoken_text)
    return {"reply": r, "said": spoken_text, "error": error}


# A passing ask: the arbiter named the filler and the mouth spoke it.
PASS_TURN = _turn({
    "spoken": True,
    "reason": "he answered from what he was told",
    "source": "mouth",
    "parser": {"verdict": "accept"},
    "coverage": 0.71,
    "required": ["lantern", "first"],
    "nearest": ["i told you about the lantern first"],
})

# A failing ask refused by the coverage gate.
FAIL_TURN = _turn({
    "reason": "recall coverage 51% is below the floor",
    "source": None,
    "parser": {"verdict": "reject"},
    "coverage": 0.514,
    "required": ["bell", "does", "often", "turn"],
    "nearest": ["the copper bell turns twice"],
}, spoken_text="")

# A passing ask answered by a path that never reaches the recall gate, so the
# reply carries no coverage key at all. This is the ambiguity the repair removes.
PASS_NO_COVERAGE_TURN = _turn({
    "spoken": True,
    "reason": "he counted how many times he was told",
    "source": "mouth",
    "parser": {"verdict": "accept"},
})

EXPECT_PASS = {"answer": ["lantern"], "forbid": []}
EXPECT_FAIL = {"answer": ["twice", "two"], "forbid": ["four"]}


# --------------------------------------------------------------- property 1
def test_stage_and_cause_stay_gated_on_failure_exactly_as_published():
    """The backward-compatibility contract: generations 0-14 keep their values."""
    ok = ask_record(_FakeSession(PASS_TURN), {"ask": "which came first?",
                                              "expect": EXPECT_PASS})
    assert ok["pass"] is True
    assert ok["stage"] is None, "a passing ask must still record stage=None"
    # `cause` is added by run_generation's journal row, not by ask_record, so
    # heldout_eval's record never carried it -- assert that stays true rather than
    # inventing a key the published schema does not have.
    assert "cause" not in ok
    assert ok["cause_all"] is not None or ok["cause_all"] is None  # present, any value

    bad = ask_record(_FakeSession(FAIL_TURN), {"ask": "how often does the bell turn?",
                                               "expect": EXPECT_FAIL})
    assert bad["pass"] is False
    assert bad["stage"] == stage_of(FAIL_TURN, bad["why"])
    assert bad["stage"] is not None
    # On a failure the additive field agrees with the published one, which is what
    # makes the two comparable row by row across the schema change.
    assert bad["cause_all"] == cause_of(FAIL_TURN, bad["why"])
    assert bad["stage_all"] == bad["stage"]


# --------------------------------------------------------------- property 2
def test_stage_all_and_cause_all_are_recorded_for_passing_asks_too():
    """The repair: the passing side of a pair is now in the journal."""
    ok = ask_record(_FakeSession(PASS_TURN), {"ask": "which came first?",
                                              "expect": EXPECT_PASS})
    assert "stage_all" in ok and "cause_all" in ok
    assert ok["stage_all"] is not None, "stage_of is total on a spoken reply"
    assert ok["stage_all"] == stage_of(PASS_TURN, ok["why"])
    assert ok["cause_all"] == cause_of(PASS_TURN, ok["why"])


def test_coverage_required_and_nearest_are_recorded_for_passing_asks():
    ok = ask_record(_FakeSession(PASS_TURN), {"ask": "which came first?",
                                              "expect": EXPECT_PASS})
    assert ok["pass"] is True
    assert ok["coverage"] == 0.71
    assert ok["required"] == ["lantern", "first"]
    assert ok["nearest"] == ["i told you about the lantern first"]


def test_coverage_present_separates_computed_none_from_never_computed():
    """The ambiguity that made the paraphrase probe print a wrong inference."""
    with_cov = ask_record(_FakeSession(PASS_TURN),
                          {"ask": "which came first?", "expect": EXPECT_PASS})
    assert with_cov["coverage_present"] is True
    assert with_cov["coverage"] == 0.71

    without = ask_record(_FakeSession(PASS_NO_COVERAGE_TURN),
                         {"ask": "how many eggs did i mention first?",
                          "expect": EXPECT_PASS})
    assert without["pass"] is True
    assert without["coverage_present"] is False, "the reply carried no coverage key"
    assert without["coverage"] is None
    # The two Nones are now tellable apart, which is the entire point.
    assert with_cov["coverage_present"] != without["coverage_present"]


def test_failing_ask_also_carries_coverage_present():
    bad = ask_record(_FakeSession(FAIL_TURN),
                     {"ask": "how often does the bell turn?", "expect": EXPECT_FAIL})
    assert bad["coverage_present"] is True
    assert bad["coverage"] == 0.514


# --------------------------------------------------------------- property 3
def test_no_score_can_move_the_new_keys_are_read_only_derivations():
    """`pass`, `said`, `words`, `spoken`, `why` are untouched by the repair."""
    step = {"ask": "how often does the bell turn?", "expect": EXPECT_FAIL}
    bad = ask_record(_FakeSession(FAIL_TURN), step)
    assert bad["pass"] is False
    assert bad["said"] == ""
    assert bad["words"] == []
    assert bad["spoken"] is False
    assert isinstance(bad["why"], str) and bad["why"]

    step_ok = {"ask": "which came first?", "expect": EXPECT_PASS}
    ok = ask_record(_FakeSession(PASS_TURN), step_ok)
    assert ok["pass"] is True
    assert ok["said"] == "the lantern"
    assert ok["spoken"] is True


def test_the_same_turn_yields_the_same_verdict_whichever_fields_are_read():
    """Grading is computed once, before any diagnostic field is derived."""
    s1, s2 = _FakeSession(FAIL_TURN), _FakeSession(FAIL_TURN)
    step = {"ask": "how often does the bell turn?", "expect": EXPECT_FAIL}
    a, b = ask_record(s1, step), ask_record(s2, step)
    assert a["pass"] == b["pass"]
    assert a["why"] == b["why"]
    assert a["stage"] == b["stage"] == a["stage_all"] == b["stage_all"]
    assert len(s1.calls) == len(s2.calls) == 1, "exactly one ask per record"


# ---------------------------------------------------- historical compatibility
def test_archived_journal_rows_without_the_new_keys_still_compare():
    """Old rows lack stage_all/cause_all/coverage_present; readers must cope."""
    old = {"ask": "how many eggs broke?", "pass": True, "stage": None,
           "why": "", "said": "two"}
    new = ask_record(_FakeSession(PASS_TURN),
                     {"ask": "which came first?", "expect": EXPECT_PASS})
    # The published fields agree in meaning across both schemas.
    assert old["stage"] == new["stage"] is None
    assert old["pass"] == new["pass"] is True
    # And the new fields are simply absent from the old row, not wrong.
    for k in ("stage_all", "cause_all", "coverage_present"):
        assert k not in old and k in new


def test_stage_of_is_total_on_a_spoken_reply_so_stage_all_never_raises():
    """`stage_all` is recorded for every ask, so it must never be partial."""
    for reply in ({"source": "mouth"}, {"recovered_filler": "lantern"},
                  {"source": "other"}, {}):
        t = _turn(reply, spoken_text="the lantern")
        assert stage_of(t, "") in {"mouth", "shape_arbiter", "other"}


def test_engine_error_is_attributed_not_swallowed_by_the_new_fields():
    """A crash must not be relabelled as a passing path by stage_all."""
    t = {"reply": {}, "said": "", "error": "KeyError: 'proposition'"}
    rec = ask_record(_FakeSession(t), {"ask": "is the coat dry or wet?",
                                       "expect": EXPECT_PASS})
    assert rec["pass"] is False
    assert rec["stage"] == "engine_error"
    assert rec["stage_all"] == "engine_error"
    assert rec["coverage_present"] is False
