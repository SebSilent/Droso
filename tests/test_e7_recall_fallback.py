"""Pin E7: RECALL_UNFILTERED_FALLBACK, default off, inert by construction.

Two kinds of claim are pinned here.

STRUCTURAL. The fallback branch is guarded by `not hits`, so it cannot fire on any
ask whose retrieval succeeded. That is what makes flag-off inertness a property of
the code rather than an empirical observation about one battery -- the property
E5's R1/R1'/R2 had and E6's floor mutation did not. Also pinned: the flag is a
CLASS attribute beside ANSWER_COVERAGE_FLOOR, so an A/B arm can set it without
touching the module for every other instance in the process.

BEHAVIOURAL. Generation 8 (flag off) must reproduce generation 7's verdicts ask for
ask, and generation 9 (flag on) must move `which thing turns twice?` out of ABSENT.
These compare two published journals, so they are the pre-registered predictions
P1-P5 checked against real runs rather than restated.

The mechanism this repairs is NOT the one the design document first proposed.
`required_words` does not exist; ABSENT means `binder.recall` returned postings and
three filters removed every one. A test pins that the fallback sits after those
filters, so the correction cannot silently regress.
"""

from __future__ import annotations

import io
import json
import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

NL = os.path.join(ROOT, "organs", "neural_language.py")
GEN7 = os.path.join(ROOT, "state", "selection", "generation_7_asks.jsonl")
GEN8 = os.path.join(ROOT, "state", "selection", "generation_8_asks.jsonl")
GEN9 = os.path.join(ROOT, "state", "selection", "generation_9_asks.jsonl")

ABSENT_ASK = "which thing turns twice?"


def _src() -> str:
    return io.open(NL, encoding="utf-8").read()


def _rows(path):
    return [json.loads(l) for l in io.open(path, encoding="utf-8") if l.strip()]


# ------------------------------------------------------------- structural --

def test_the_flag_defaults_off():
    import organs.neural_language as nl
    assert nl.NeuralLanguage.RECALL_UNFILTERED_FALLBACK is False


def test_the_flag_is_a_class_attribute_beside_the_floor():
    """An A/B arm must be able to set it per-class without editing the module.

    If it were module-level, `nl.RECALL_UNFILTERED_FALLBACK = True` would work but
    `self.RECALL_UNFILTERED_FALLBACK` inside the method would not see it -- the
    exact bug the first implementation of this flag had.
    """
    src = _src()
    m = re.search(r"^    RECALL_UNFILTERED_FALLBACK = False$", src, re.M)
    assert m, "flag is not a 4-space-indented class attribute"
    floor = src.index("    ANSWER_COVERAGE_FLOOR = 0.6")
    assert floor < m.start(), "flag should sit after the floor it defers to"


def test_the_use_site_reads_it_through_self():
    src = _src()
    assert "self.RECALL_UNFILTERED_FALLBACK" in src
    # a bare module-level read would silently never see an arm's override
    bare = re.findall(r"(?<!self\.)(?<!\.)\bRECALL_UNFILTERED_FALLBACK\b", src)
    assert len(bare) == 1, (
        f"expected exactly one bare mention (the class attribute definition), "
        f"got {len(bare)}: a use site is reading it without self.")


def test_the_branch_is_guarded_by_not_hits():
    """Structural inertness: it cannot fire when retrieval succeeded."""
    src = _src()
    m = re.search(
        r"if not hits and raw_n and self\.RECALL_UNFILTERED_FALLBACK:", src)
    assert m, "the guard changed; flag-off inertness is no longer structural"


def test_the_fallback_sits_after_all_three_filters():
    """The correction to the design doc, pinned so it cannot regress.

    ABSENT is not `must` coming back empty -- `must` is only computed under
    `if hits and content`. It is the three filters removing every posting. So the
    fallback must be downstream of all three, or it repairs nothing.
    """
    src = _src()
    i_q = src.index("n_after_q = len(hits)")
    i_int = src.index("n_after_interrog = len(hits)")
    i_echo = src.index("n_after_echo = len(hits)")
    i_fb = src.index("self.RECALL_UNFILTERED_FALLBACK")
    assert i_q < i_int < i_echo < i_fb, (
        "fallback is not after all three filters")


def test_the_fallback_keeps_the_exact_question_filter():
    """It relaxes the echo and interrogative filters, never the question itself.

    Dropping the question filter would let a remembered question be retrieved as
    its own answer, which is the failure the filter exists to prevent.
    """
    src = _src()
    i_fb = src.index("self.RECALL_UNFILTERED_FALLBACK")
    body = src[i_fb:i_fb + 1400]
    assert 'if {str(t).lower() for t in h["tokens"]} != qset' in body
    assert "_echoes" not in body, "fallback must not re-apply the echo filter"
    assert "is_interrogative" not in body


def test_the_absent_return_carries_the_filter_counts():
    src = _src()
    for k in ('"recall": raw_n', '"after_question_filter": n_after_q',
              '"after_interrogative_filter": n_after_interrog',
              '"after_echo_filter": n_after_echo',
              '"fallback_applied": fallback_applied'):
        assert k in src, k


def test_the_coverage_floor_did_not_move():
    """E7 is a reachability change, not a threshold change."""
    import organs.neural_language as nl
    assert nl.NeuralLanguage.ANSWER_COVERAGE_FLOOR == 0.6
    assert "ANSWER_COVERAGE_FLOOR = 0.6" in _src()


def test_clean_keeps_the_new_diagnostic_keys():
    from tools.converse import _clean
    out = _clean({"spoken": False, "reason": "nothing remembered about that",
                  "recall": 5, "after_question_filter": 5,
                  "after_interrogative_filter": 3, "after_echo_filter": 0,
                  "fallback_applied": True})
    assert out["recall"] == 5
    assert out["after_echo_filter"] == 0
    assert out["fallback_applied"] is True


def test_clean_still_drops_bulk():
    from tools.converse import _clean
    out = _clean({"spoken": True, "recall": 5,
                  "brain_vote_dump": "y" * 999, "retrieval": {"big": "x" * 999}})
    assert "brain_vote_dump" not in out
    assert "retrieval" not in out


def test_the_cli_flag_is_wired_and_recorded_in_provenance():
    rg = io.open(os.path.join(ROOT, "tools", "run_generation.py"),
                 encoding="utf-8").read()
    assert '"--recall-fallback"' in rg
    assert 'nl.NeuralLanguage.RECALL_UNFILTERED_FALLBACK = True' in rg
    assert 'CODE_FLAGS["recall_unfiltered_fallback"]' in rg
    # both arms must record the flag, on AND off, or an off-arm row is ambiguous
    assert 'CODE_FLAGS["recall_unfiltered_fallback"] = False' in rg


# ------------------------------------------------------------ behavioural --

@pytest.fixture(scope="module")
def g7():
    if not os.path.exists(GEN7):
        pytest.skip("generation 7 not published")
    return _rows(GEN7)


@pytest.fixture(scope="module")
def g8():
    if not os.path.exists(GEN8):
        pytest.skip("generation 8 (flag off) not published")
    return _rows(GEN8)


@pytest.fixture(scope="module")
def g9():
    if not os.path.exists(GEN9):
        pytest.skip("generation 9 (flag on) not published")
    return _rows(GEN9)


def _verdicts(rows):
    return {(r["tier"], r["script"], r["id"]):
            (bool(r.get("pass")), r.get("stage"), r.get("coverage"))
            for r in rows}


def test_P1_flag_off_reproduces_generation7_verdicts(g7, g8):
    """P1, qualified: verdicts identical, not bytes -- the diagnostics are new."""
    assert len(g8) == len(g7) == 42
    a, b = _verdicts(g7), _verdicts(g8)
    assert set(a) == set(b)
    diff = {k: (a[k], b[k]) for k in a if a[k] != b[k]}
    assert not diff, f"flag-off moved {len(diff)} verdict(s): {diff}"


def test_P1_flag_off_keeps_the_score_split(g7, g8):
    assert sum(1 for r in g7 if r.get("pass")) == 23
    assert sum(1 for r in g8 if r.get("pass")) == 23


def test_P1_flag_off_never_applies_the_fallback(g8):
    assert all(r.get("fallback_applied") in (False, None) for r in g8)


def test_P2_flag_on_moves_the_absent_ask_out_of_ABSENT(g9):
    row = [r for r in g9 if r.get("ask") == ABSENT_ASK]
    assert row, f"{ABSENT_ASK!r} is not in the battery"
    r = row[0]
    assert r.get("fallback_applied") is True, (
        "fallback did not fire: raw binder recall was 0, so no posting exists at "
        "all and ABSENT is correct rather than repairable")
    assert (r.get("required") or []), "required is still empty"
    assert (r.get("nearest") or []), "nearest is still empty"
    assert r.get("coverage") is not None, "coverage still unset: gate never scored"


def test_P2_the_absent_ask_records_why_it_was_absent(g9):
    """Whether it left ABSENT or not, the filter counts must explain it."""
    r = [x for x in g9 if x.get("ask") == ABSENT_ASK][0]
    assert "recall" in r and "after_echo_filter" in r
    assert isinstance(r["recall"], int)


def test_P3_flag_on_changes_no_other_ask(g8, g9):
    a, b = _verdicts(g8), _verdicts(g9)
    assert set(a) == set(b)
    moved = {k: (a[k], b[k]) for k in a
             if a[k] != b[k] and a[k][0] is not None}
    # the only ask allowed to move is the ABSENT one
    allowed = {k for k in a if any(
        r.get("ask") == ABSENT_ASK and (r["tier"], r["script"], r["id"]) == k
        for r in g9)}
    unexpected = {k: v for k, v in moved.items() if k not in allowed}
    assert not unexpected, f"fallback fired where it should not: {unexpected}"


def test_P3_the_nine_gate_coverages_are_unchanged(g8, g9):
    gate8 = {r["ask"]: r["coverage"] for r in g8
             if r.get("stage") == "recall" and r.get("coverage") is not None}
    gate9 = {r["ask"]: r["coverage"] for r in g9
             if r.get("stage") == "recall" and r.get("coverage") is not None}
    for ask, cov in gate8.items():
        if ask == ABSENT_ASK:
            continue
        assert ask in gate9, f"{ask} left the GATE class"
        assert gate9[ask] == pytest.approx(cov), ask


def test_P3_the_guard_ask_coverage_is_unchanged(g8, g9):
    """0.570 is the number the empty-window result rests on."""
    def guard(rows):
        return [r["coverage"] for r in rows
                if r.get("pass") and r.get("coverage") is not None]
    assert guard(g8) == guard(g9) == [pytest.approx(0.570)]


def test_P5_zero_erosion_both_arms(g8, g9):
    for rows, name in ((g8, "flag off"), (g9, "flag on")):
        frozen = [r for r in rows if r["tier"] == "frozen"]
        assert sum(1 for r in frozen if r.get("pass")) == 19, name
        guarded = [r for r in rows if r.get("guard")]
        if guarded:
            assert all(r.get("pass") for r in guarded), name


def test_both_arms_ran_the_control_genome(g8, g9):
    for rows in (g8, g9):
        assert {r.get("genome_id") for r in rows} == {"abffa2b7f101"}


def test_the_arms_differ_only_in_the_recorded_flag():
    def flags(gen):
        p = os.path.join(ROOT, "state", "selection", f"generation_{gen}.jsonl")
        if not os.path.exists(p):
            pytest.skip(f"generation {gen} not published")
        row = json.loads(io.open(p, encoding="utf-8").read().strip())
        return row["provenance"]["code_flags"]
    off, on = flags(8), flags(9)
    assert off.get("recall_unfiltered_fallback") is False
    assert on.get("recall_unfiltered_fallback") is True
    # same genome, same battery seals: the flag is the ONLY difference
    for gen in (8, 9):
        p = os.path.join(ROOT, "state", "selection", f"generation_{gen}.jsonl")
        row = json.loads(io.open(p, encoding="utf-8").read().strip())
        assert row["genome_id"] == "abffa2b7f101"
