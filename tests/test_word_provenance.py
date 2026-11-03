"""G0-prime / R9 -- the word-level provenance grader, pinned against the sealed evidence.

These tests are the validation step of the G0-prime checklist: the grader must flag every says-gap
row, produce ZERO false aborts on the narration-frame rows, and admit every guarded-absence row by
its form. They are pure functions over committed JSON, so they run in well under a second and never
build a house.

Two of them exist because of mistakes made while writing the grader, and are kept for that reason:
one pins the report-frame strip to a single shared source, and one pins `tower` as traceable -- the
word the first version of the grader fired on 15 times because the evidence's `told` set carries only
a taught pair's ANSWER and never its QUESTION.
"""
import json
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import tools.electric_learn_bench as bench                      # noqa: E402
import tools.word_provenance as wp                              # noqa: E402
from organs.neural_language import NeuralLanguage               # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs" / "evidence" / "electric_learn_bench.json"
PRE_FLAG = ROOT / "experiments" / "MP-E9" / "baselines" / "bench_pre_arbiter_tell_HEAD.json"


@pytest.fixture(scope="module")
def doc():
    return json.loads(EVIDENCE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def sets(doc):
    return wp.build_sets(doc)


# ---------------------------------------------------------------- the three pinned row sets

def test_says_gap_rows_are_all_flagged(doc, sets):
    says, _frame, _abs = wp.sets_from(doc)
    assert len(says) == 16, f"expected the 16 published says rows, found {len(says)}"
    audited = [wp.audit_row(r, sets) for _k, r in says]
    assert all(a["verdict"] == "UNTRACEABLE_ASSERTED" for a in audited)
    assert {w for a in audited for w in a["untraceable"]} == {"says"}


def test_says_gap_is_exactly_three_asks(doc, sets):
    says, _f, _a = wp.sets_from(doc)
    assert sorted({r["ask"] for _k, r in says}) == [
        "what the bridge cross", "what the dog guard", "what the nora carry"]
    assert {r["src"] for _k, r in says} == {"arbiter head"}


def test_narration_frame_rows_produce_zero_false_aborts(doc, sets):
    """The 23 `droso says ...` rows must NOT abort. This is the failure mode that would have made
    R9 unusable: 23 false aborts under a one-word-aborts rule reads as a capability collapse."""
    _s, frame, _a = wp.sets_from(doc)
    assert len(frame) == 23, f"expected the 23 narration-frame rows, found {len(frame)}"
    bad = [wp.audit_row(r, sets) for _k, r in frame
           if wp.audit_row(r, sets)["verdict"].startswith("UNTRACEABLE")]
    assert bad == [], f"the frame strip failed on {len(bad)} rows"


def test_every_guarded_absence_row_is_admitted_by_form(doc, sets):
    _s, _f, absence = wp.sets_from(doc)
    assert len(absence) == 24, "the guarded-absence contract is 24 rows on this bench"
    verdicts = {wp.audit_row(r, sets)["verdict"] for _k, r in absence}
    assert verdicts == {"admitted_refusal"}, verdicts


def test_validate_reports_pass(doc):
    assert wp.validate(doc)["PASS"] is True


# ---------------------------------------------------------------- the frame, and why it is one

def test_grader_imports_the_frame_tuple_rather_than_restating_it():
    """The whole reason REPORT_FRAMES was lifted out of norm(). Two copies drift; one cannot."""
    assert wp.REPORT_FRAMES is bench.REPORT_FRAMES
    assert wp.strip_report_frame is bench.strip_report_frame


def test_frame_strip_is_positional_and_that_is_the_whole_distinction():
    # In frame position: a report about speaking.
    assert bench.strip_report_frame("droso says where the bell hang") == "where the bell hang"
    # Not in frame position: the word IS the assertion, so it survives to be graded.
    assert bench.strip_report_frame("says") == "says"


def test_says_alone_is_flagged_while_the_framed_sentence_is_clean(sets):
    flagged = wp.audit_row({"said": "says", "ask": "what the dog guard", "src": "arbiter head",
                            "cls": "partial"}, sets)
    assert flagged["verdict"] == "UNTRACEABLE_ASSERTED"
    clean = wp.audit_row({"said": "droso says where the bell hang",
                          "ask": "where does the bell hang", "src": "recalled proposition",
                          "cls": "echo"}, sets)
    assert clean["verdict"] == "clean"
    assert clean["frame_stripped"] is True


def test_says_mid_sentence_is_graded_not_framed(sets):
    """A frame word used as a verb of an asserted sentence is not a frame."""
    rec = wp.audit_row({"said": "the dog says the latch", "ask": "what bites the latch",
                        "src": "recalled proposition", "cls": "misattrib"}, sets)
    assert rec["frame_stripped"] is False
    assert "says" in rec["untraceable"]


def test_says_is_a_content_word_by_the_organs_own_class():
    """If `says` were in the function set the grader would skip it and the pin would be vacuous."""
    assert "says" not in NeuralLanguage.SHAPE_FUNCTION_WORDS
    assert "say" not in NeuralLanguage.SHAPE_FUNCTION_WORDS


def test_says_is_in_nothing_the_house_was_told(doc, sets):
    assert "says" not in sets["answers"]
    assert "says" not in sets["heard"]      # not in any ask either: it is invented, not echoed


# ---------------------------------------------------------------- the trace-set bug, pinned

def test_tower_is_traceable_to_a_taught_question(doc, sets):
    """The first version read only `told`, which holds pair ANSWERS, and fired 15 rows on `tower` --
    a word from the taught pair `what rings in the tower? / the copper bell rings`. Pinned so a
    future trace-set edit cannot re-lose a taught question."""
    assert "tower" in sets["questions"]
    assert "tower" not in sets["answers"]
    rec = wp.audit_row({"said": "what rings in the tower?", "ask": "what rings",
                        "src": "recalled proposition", "cls": "cross_echo"}, sets)
    assert "tower" not in rec["untraceable"]
    assert rec["traces"]["tower"] == "taught_question"


def test_heard_not_told_is_a_separate_severity(doc, sets):
    """`which` reached the house only inside another question. It is in his experience and it is not
    something he was told, so R9 still fails it -- but it is pool leakage, not an invented fact, and
    collapsing the two classes would let the tool's severity judgement hide in its exit code."""
    rec = wp.audit_row({"said": "which bell rings", "ask": "what rings",
                        "src": "recalled proposition", "cls": "cross_echo"}, sets)
    assert rec["verdict"] == "UNTRACEABLE_HEARD"
    assert "which" in rec["heard_only"]
    assert rec["untraceable"] == []


def test_audit_splits_the_two_severities(doc):
    res = wp.audit(doc)
    assert res["verdict_counts"]["UNTRACEABLE_ASSERTED"] == 16
    assert res["verdict_counts"]["UNTRACEABLE_HEARD"] == 6
    assert res["untraceable_words"]["says"]["severity"] == ["asserted"]


# ---------------------------------------------------------------- the refusal form, as a form

def test_absence_form_admits_only_the_registered_relations(sets):
    ok = wp.audit_row({"said": "i don't know, bell was told but no place was ever told for bell",
                       "ask": "where does the bell hang", "src": "electric_absence",
                       "cls": "absence"}, sets)
    assert ok["verdict"] == "admitted_refusal"


def test_absence_source_speaking_outside_the_form_is_graded_as_speech(sets):
    """A row labelled as a licensed refusal that says something the form cannot say is not excused by
    its label. This is the hole R9 exists to close."""
    rec = wp.audit_row({"said": "i don't know, bell was told but no place was ever told for bell, "
                                 "and the tower rings",
                        "ask": "where does the bell hang", "src": "electric_absence",
                        "cls": "absence"}, sets)
    assert rec["admitted"] == "absence_form_OUTSIDE"
    assert rec["verdict"] != "admitted_refusal"


def test_absence_relation_outside_the_three_classes_is_not_admitted(sets):
    rec = wp.audit_row({"said": "i don't know, bell was told but no colour was ever told for bell",
                        "ask": "where does the bell hang", "src": "electric_absence",
                        "cls": "absence"}, sets)
    assert rec["admitted"] == "absence_form_OUTSIDE"


def test_absence_subject_must_be_something_he_was_told(sets):
    rec = wp.audit_row({"said": "i don't know, griddle was told but no place was ever told for "
                                "griddle",
                        "ask": "where does the bell hang", "src": "electric_absence",
                        "cls": "absence"}, sets)
    assert rec["admitted"] == "absence_form_OUTSIDE"


# ---------------------------------------------------------------- silence, and the refactor proof

def test_silence_is_never_a_confabulation(sets):
    assert wp.audit_row({"said": "", "ask": "what the dog guard", "src": "", "cls": "refused"},
                        sets)["verdict"] == "silent"


def test_refactored_norm_reclassifies_the_current_evidence_identically(doc):
    """norm() moved the frame list into REPORT_FRAMES. R3 freezes what a suite asks, so the
    refactor must be behaviour-preserving: every stored cls re-derived from the stored row."""
    rows = wp.probe_rows(doc)
    bad = [(k, r.get("cls"), bench.classify(r)) for k, r in rows if bench.classify(r) != r.get("cls")]
    assert bad == [], f"{len(bad)} rows reclassify, first: {bad[:3]}"


@pytest.mark.skipif(not PRE_FLAG.exists(),
                    reason="pre-flag baseline not yet derived: tools/derive_pre_flag_snapshot.py")
def test_refactored_norm_reclassifies_the_pre_flag_snapshot_identically():
    """The strong form of the same proof: data classified by the PRE-revision code, re-classified by
    the post-revision code. If norm() had changed meaning, the old rows would move."""
    old = json.loads(PRE_FLAG.read_text(encoding="utf-8"))
    rows = wp.probe_rows(old)
    bad = [(k, r.get("cls"), bench.classify(r)) for k, r in rows if bench.classify(r) != r.get("cls")]
    assert bad == [], f"{len(bad)} of {len(rows)} pre-flag rows reclassify, first: {bad[:3]}"
