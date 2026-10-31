"""`cause`: a derived refinement of `stage` that never rewrites it.

Pre-registered in docs/evidence/stage_cause_preregistration.md.  The change is
additive by construction and these tests pin that: `stage_of` is untouched, the
only reclassification `cause_of` may perform is out of `recall`, and every
historical journal keeps the values it was published with.

The defect being corrected: `stage_of` returns "recall" as its DEFAULT for any
unspoken reply whose reason matches no pattern (tools/heldout_eval.py, the
fall-through whose own comment says "a DEFAULT, not a measurement").  For ten
generations that bucket mixed real coverage-gate refusals with asks the organ
never understood, and the tally `{"recall": 10, ...}` was quoted as a memory
problem when one of the ten was not.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.heldout_eval import cause_of, stage_of

ROOT = Path(__file__).resolve().parents[1]
SEL = ROOT / "state" / "selection"

# A turn is unspoken when reply carries no spoken/answered flag or no utterance,
# per tools.converse._spoken.  Every fixture here is unspoken unless it says so.
GATE = "the closest memory of his covers 51% of the question"
COMPREHENSION = "it did not understand and was not in the mood to babble"


def turn(reason=None, *, spoken=False, said="", src=None, error=None, **extra):
    r = dict(extra)
    if reason is not None:
        r["reason"] = reason
    if src is not None:
        r["source"] = src
    if spoken:
        r["spoken"] = True
        r["utterance"] = said
    t = {"reply": r}
    if error:
        t["error"] = error
    return t


def load(gen):
    p = SEL / f"generation_{gen}_asks.jsonl"
    if not p.exists():
        pytest.skip(f"{p.name} not published yet")
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


# --------------------------------------------------------------- unit ----

def test_a_real_gate_refusal_is_recall_gate_and_stage_is_untouched():
    t = turn(GATE)
    assert stage_of(t, "answer slot empty") == "recall"
    assert cause_of(t, "answer slot empty") == "recall_gate"


def test_a_comprehension_failure_is_separated_from_recall():
    t = turn(COMPREHENSION)
    assert stage_of(t, "answer slot empty") == "recall", "stage must not change"
    assert cause_of(t, "answer slot empty") == "comprehension"


def test_an_unmatched_nonempty_reason_is_unclassified_not_recall():
    """The fall-through that made `stage` lie must not be repeated here."""
    t = turn("he wandered off mid sentence")
    assert stage_of(t, "answer slot empty") == "recall"
    assert cause_of(t, "answer slot empty") == "unclassified"


def test_silence_with_no_reason_stays_recall_untraced_in_both():
    """`stage_of` already names this case, so `cause_of` passes it through.

    Pinned because it is why `cause_of` has no "untraced" value of its own: that
    branch would be unreachable, and an unreachable label in a published taxonomy
    is a claim the data can never support.
    """
    t = turn("")
    assert stage_of(t, "answer slot empty") == "recall_untraced"
    assert cause_of(t, "answer slot empty") == "recall_untraced"


@pytest.mark.parametrize("t,why,expected", [
    (turn("he did not feel like speaking"), "answer slot empty", "gating"),
    (turn("the shape arbiter vetoed it"), "answer slot empty", "shape_arbiter"),
    (turn(None, error="KeyError: proposition"), "answer slot empty", "engine_error"),
    (turn("covers 51%", spoken=True, said="the bell", src="mouth"), "wrong", "mouth"),
])
def test_every_non_recall_stage_passes_straight_through(t, why, expected):
    assert stage_of(t, why) == expected
    assert cause_of(t, why) == expected


def test_passing_and_ungraded_turns_are_not_reclassified():
    assert cause_of(turn("x"), "UNGRADED: harness") == "harness-bug"


def test_the_only_reclassification_is_out_of_recall():
    """Property test over a corpus: `cause` differs from `stage` only when
    `stage == "recall"`.  This is the whole non-destructive guarantee."""
    reasons = [GATE, COMPREHENSION, "he wandered off", "",
               "the closest memory of his covers 34% of the question",
               "no memory of that", "nothing he remembers",
               "did not understand the question at all",
               "he did not feel like speaking", "no such slot",
               "no content words to look up", "no word of that is one he knows"]
    for reason in reasons:
        for why in ("answer slot empty", "UNGRADED: x"):
            t = turn(reason)
            s, c = stage_of(t, why), cause_of(t, why)
            if c != s:
                assert s == "recall", f"{reason!r}: reclassified out of {s!r}"
                assert c in {"recall_gate", "comprehension", "unclassified"}


def test_comprehension_wins_over_a_reason_that_matches_both():
    """RECALL_RE contains "empty" and "no candidate", which a comprehension
    string could plausibly also contain.  Comprehension is checked second and
    must win, because "did not understand" is the more specific claim."""
    t = turn("he did not understand and found no candidate")
    assert cause_of(t, "answer slot empty") == "comprehension"


# ---------------------------------------------------- historical rows ----

@pytest.mark.parametrize("gen", [0, 1, 2, 7, 8, 9])
def test_historical_journals_carry_no_cause_key(gen):
    """Non-destructive means the old rows were not rewritten, not merely that
    they still parse.  If a `cause` key appears here, something backfilled it."""
    rows = load(gen)
    assert rows
    assert all("cause" not in r for r in rows), f"generation {gen} was backfilled"


@pytest.mark.parametrize("gen", [7, 8, 9])
def test_historical_stage_values_are_unchanged(gen):
    rows = load(gen)
    fails = [r for r in rows if not r.get("pass")]
    assert fails
    # every failing row still carries a stage, and the tally is the published one
    from collections import Counter
    tally = Counter(r.get("stage") or "unknown" for r in rows)
    assert tally["recall"] == 10
    assert tally["mouth"] == 4 and tally["gating"] == 3 and tally["shape_arbiter"] == 2


# ------------------------------------------------- generation 10 (new) ----

def test_generation_10_records_cause_on_failures_and_none_on_passes():
    rows = load(10)
    assert any("cause" in r for r in rows), "generation 10 has no cause field"
    for r in rows:
        if r.get("pass"):
            assert r.get("cause") is None
        else:
            assert r.get("cause"), f"{r['id']}: failing row with no cause"


def test_generation_10_stage_tally_is_identical_to_generation_9():
    """The point of the exercise: adding `cause` must not move `stage`."""
    from collections import Counter
    g9, g10 = load(9), load(10)
    t9 = Counter(r.get("stage") or "unknown" for r in g9)
    t10 = Counter(r.get("stage") or "unknown" for r in g10)
    assert dict(t9) == dict(t10), f"stage moved: {t9} -> {t10}"


def test_generation_10_per_ask_stage_and_pass_match_generation_9():
    g9 = {r["id"]: r for r in load(9)}
    g10 = {r["id"]: r for r in load(10)}
    assert set(g9) == set(g10)
    for k in g9:
        assert g9[k]["pass"] == g10[k]["pass"], k
        assert g9[k].get("stage") == g10[k].get("stage"), k


def test_generation_10_splits_the_ten_recall_failures_nine_and_one():
    """The measured correction: nine gate refusals, one comprehension failure."""
    from collections import Counter
    rows = load(10)
    rec = [r for r in rows if r.get("stage") == "recall"]
    assert len(rec) == 10
    c = Counter(r["cause"] for r in rec)
    assert c["recall_gate"] == 9, dict(c)
    assert c["comprehension"] == 1, dict(c)
    assert not (set(c) - {"recall_gate", "comprehension"}), dict(c)


def test_the_one_comprehension_failure_is_the_ask_identified_in_E7():
    rows = load(10)
    comp = [r for r in rows if r.get("cause") == "comprehension"]
    assert len(comp) == 1
    assert comp[0]["ask"] == "which thing turns twice?"
    assert comp[0]["coverage"] is None, "it never reached the gate"
    assert "did not understand" in (comp[0].get("reason") or "")


def test_every_recall_gate_failure_carries_a_coverage_number():
    """What separates a measured refusal from an unmeasured silence."""
    rows = load(10)
    for r in rows:
        if r.get("cause") == "recall_gate":
            assert r.get("coverage") is not None, r["id"]
            assert "covers" in (r.get("reason") or "")


GUARDED_PROBES = {"R-count-moon", "R-order-ofthe", "R-disj-reversed",
                  "P-numeral-final"}


def test_generation_10_scores_are_unchanged_by_the_labelling_work():
    """`cause` is derived from the reply; it cannot change a verdict.

    `tier == "probe"` covers BOTH probe populations: 14 unseen paraphrases, of
    which none has ever passed, and 4 guarded invariants, of which all four pass.
    The summary table's "0/14" counts only the first, so asserting 0 over all 18
    rows is wrong -- it was wrong in the first draft of this test, and the failure
    is worth keeping visible as a comment because the two populations look
    identical in the journal apart from their probe names.
    """
    rows = load(10)
    frozen = [r for r in rows if r["tier"] == "frozen"]
    probes = [r for r in rows if r["tier"] == "probe"]
    assert len(frozen) == 24 and sum(r["pass"] for r in frozen) == 19
    assert len(probes) == 18
    guarded = [r for r in probes if r.get("probe") in GUARDED_PROBES]
    paraphrase = [r for r in probes if r.get("probe") not in GUARDED_PROBES]
    assert len(guarded) == 4 and all(r["pass"] for r in guarded)
    assert len(paraphrase) == 14 and not any(r["pass"] for r in paraphrase)
