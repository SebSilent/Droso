r"""R1: the shape parser's question-word gate, flag-gated.

docs/answer_path_repair_design.md section 3. The gate was a closed literal tuple
("who","what","where") at neural_language.py:2108, so `which thing turns twice` produced
no shape while `what turns twice` produced subject_unknown and passed -- the cause of the
question-word frame scoring 0/9 across three teaching episodes.

These tests use a stub, not a built house: _question_shape reads only its token list and
the class constants, so the behaviour under test is reachable without 16 seconds of
construction. The flag is restored after every test, because it is a class attribute and
a leaked flag would silently make the next test measure the wrong arm.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import organs.neural_language as nl  # noqa: E402

N = nl.NeuralLanguage


class Stub:
    """Barely enough of an organ to call _question_shape: it touches no instance state.

    The interrogatives are a PROPERTY that reads the flag off the real class at call
    time. The first version copied `N.SHAPE_INTERROGATIVES` and `N.SHAPE_EXTRA_...` into
    the stub as class attributes, which snapshotted them at import -- so the flag fixture
    set N's attribute and the stub never saw it, and every "flag on" test measured the
    control arm. A stub that freezes the thing under test is worse than no stub.
    """
    _question_shape = N._question_shape
    SHAPE_FUNCTION_WORDS = N.SHAPE_FUNCTION_WORDS
    SHAPE_DO_SUPPORT = N.SHAPE_DO_SUPPORT
    SHAPE_COPULAS = N.SHAPE_COPULAS
    SHAPE_LOCATIVE_PREPS = N.SHAPE_LOCATIVE_PREPS

    @property
    def SHAPE_INTERROGATIVES(self):
        return N.SHAPE_BASE_INTERROGATIVES + tuple(N.SHAPE_EXTRA_INTERROGATIVES)

    @property
    def SHAPE_DETERMINER_INTERROGATIVES(self):
        return tuple(N.SHAPE_DETERMINER_INTERROGATIVES)

    @property
    def SHAPE_ALLOW_PASSIVE(self):
        return bool(N.SHAPE_ALLOW_PASSIVE)


def interrogatives():
    """Read through an instance: on the class this name is the property object itself."""
    return Stub().SHAPE_INTERROGATIVES


@pytest.fixture
def flag():
    """Set the flags for one test and put them back. A leaked class attribute is exactly
    the failure mode that would make an A/B measure the same arm twice."""
    old = (N.SHAPE_EXTRA_INTERROGATIVES, N.SHAPE_DETERMINER_INTERROGATIVES,
           N.SHAPE_ALLOW_PASSIVE)
    yield lambda words: setattr(N, "SHAPE_EXTRA_INTERROGATIVES", tuple(words))
    (N.SHAPE_EXTRA_INTERROGATIVES, N.SHAPE_DETERMINER_INTERROGATIVES,
     N.SHAPE_ALLOW_PASSIVE) = old


@pytest.fixture
def r1p(flag):
    """R1 on plus R1': `which` is a question word AND a determiner."""
    flag(("which",))
    N.SHAPE_DETERMINER_INTERROGATIVES = ("which",)


@pytest.fixture
def r2(flag):
    """R2 alone: the passive branch, with no new question words."""
    N.SHAPE_ALLOW_PASSIVE = True


# ------------------------------------------------------------------- R1' ----

def test_r1p_is_off_by_default():
    assert N.SHAPE_DETERMINER_INTERROGATIVES == ()
    assert N.SHAPE_ALLOW_PASSIVE is False


def test_r1p_skips_the_np_head_after_a_determiner_interrogative(flag):
    """THE FIX FOR THE FALSIFIED P2. `which` is a determiner, so a head noun follows it
    and the verb comes after that -- which is why `what turns twice` parsed and
    `which thing turns twice` took "thing" as the verb."""
    flag(("which",))
    N.SHAPE_DETERMINER_INTERROGATIVES = ("which",)
    got = shape("which thing turns twice")
    assert got is not None, "no shape at all"
    assert got["kind"] == "subject_unknown"
    assert got["verb"] == "turns", got
    assert got["tail"] == ["twice"], got
    # and it now matches the form that always worked
    ref = shape("what turns twice")
    assert (got["kind"], got["verb"], got["tail"]) == (ref["kind"], ref["verb"],
                                                       ref["tail"])


def test_r1p_does_not_skip_when_there_is_no_head_noun(flag):
    """The threshold is structural, not a word list: with only two content words after a
    determiner there is no head-plus-verb-plus-tail to disambiguate, so nothing is skipped
    and the R1 behaviour is preserved."""
    flag(("which",))
    N.SHAPE_DETERMINER_INTERROGATIVES = ("which",)
    got = shape("which turns twice")
    assert got is not None and got["verb"] == "turns" and got["tail"] == ["twice"]


def test_r1p_leaves_the_pronoun_interrogatives_alone(flag):
    """`what`/`who`/`where` are pronouns and stand in for the missing constituent, so the
    next content word IS the verb. Skipping a head after them would break every question
    that already works."""
    flag(("which",))
    N.SHAPE_DETERMINER_INTERROGATIVES = ("which",)
    assert shape("what turns twice")["verb"] == "turns"
    assert shape("what does the frost bite")["kind"] == "object_unknown"
    assert shape("where is the box kept")["kind"] == "locative_unknown"
    assert shape("who holds the light")["verb"] == "holds"


def test_r1p_handles_the_other_failing_which_form(flag):
    flag(("which",))
    N.SHAPE_DETERMINER_INTERROGATIVES = ("which",)
    got = shape("which of them is wet and is not on the hook")
    # `of them` are function words, so the content words are wet/not/on/the/hook...
    # Whatever it returns, it must not be a shape whose verb is "of" or "them".
    assert got is None or got.get("verb") not in ("of", "them"), got


# -------------------------------------------------------------------- R2 ----

def test_r2_parses_the_passive_into_the_existing_object_unknown_kind(r2):
    """No fourth shape kind: reusing object_unknown is what lets _shape_matches,
    _arbitrate_shape, _provenance_vote and the mouth all work unchanged. That is the
    difference between a repair and a refactor."""
    got = shape("what is bitten by the frost")
    assert got is not None, "passive still has no parse"
    assert got["kind"] == "object_unknown"
    assert got["verb"] == "bitten"
    assert got["subject"] == ["frost"]
    assert got["tail"] == []


def test_r2_parses_the_two_hop_passive(r2):
    got = shape("what is held by the thing the frost bites")
    assert got is not None and got["kind"] == "object_unknown"
    assert got["verb"] == "held"
    assert got["subject"][0] == "thing" and "frost" in got["subject"]


def test_r2_preserves_the_abstain_that_prevents_confabulation(r2):
    """`what is the box` must still get NO shape. That abstain is the guard against
    answering a copula question with a confabulated filler, and R2 is gated on a `by`
    with content after it precisely so this case is untouched."""
    assert shape("what is the box") is None
    assert shape("what is wet") is None
    assert shape("what is the coat") is None


def test_r2_does_not_fire_without_an_agent(r2):
    assert shape("what is bitten") is None
    assert shape("what is by the door") is None


def test_r2_leaves_the_active_forms_exactly_as_they_were(r2):
    a = shape("what does the frost bite")
    assert a["kind"] == "object_unknown" and a["verb"] == "bite"
    assert a["subject"] == ["frost"]
    assert shape("what turns twice")["kind"] == "subject_unknown"


def test_r2_does_not_make_a_polar_question_answerable(r2):
    """Class C is R3 and is deliberately not proposed: a polar path is a new capability
    with a new failure mode, confabulated negation."""
    assert shape("is the frost held by the door") is None
    assert shape("does the door hold the frost") is None


def test_the_two_flags_are_independent():
    """A result must be attributable to one cut, so neither flag may imply the other."""
    N.SHAPE_ALLOW_PASSIVE = True
    try:
        assert N.SHAPE_EXTRA_INTERROGATIVES == ()
        assert shape("what is bitten by the frost") is not None
        assert shape("which thing turns twice") is None
    finally:
        N.SHAPE_ALLOW_PASSIVE = False


def shape(text):
    return Stub()._question_shape(text.split())


def test_the_flag_is_off_by_default_and_the_live_behaviour_is_unchanged():
    assert N.SHAPE_EXTRA_INTERROGATIVES == ()
    assert interrogatives() == ("who", "what", "where")
    assert shape("what turns twice")["kind"] == "subject_unknown"
    assert shape("which thing turns twice") is None


def test_the_flag_is_read_at_call_time_not_frozen_at_class_definition(flag):
    """The trap this exists to catch: a class-level `BASE + EXTRA` is evaluated once when
    the class body runs, so setting the flag afterwards would do nothing and the
    experiment would measure the control arm twice while reporting that it had not.
    """
    assert shape("which thing turns twice") is None
    flag(("which",))
    assert interrogatives() == ("who", "what", "where", "which")
    got = shape("which thing turns twice")
    assert got is not None and got["kind"] == "subject_unknown"
    flag(())
    assert shape("which thing turns twice") is None


def test_r1_alone_gives_which_thing_the_WRONG_shape_so_p2_is_falsified(flag):
    """THE PRE-REGISTERED PREDICTION P2, FALSIFIED BY THIS TEST BEFORE ANY COMPUTE WAS
    SPENT. P2 said `which thing turns twice?` would move from fail to pass because it
    would parse like `what turns twice?`. It does not.

    The subject_unknown branch takes the FIRST non-function word after the interrogative
    as the verb. `what` is followed directly by the verb, so `what turns twice` gives
    verb="turns". But `which thing` is a two-word question phrase and "thing" is a
    content word, so it is taken as the verb:

        what turns twice        -> verb="turns"  tail=["twice"]        correct
        which thing turns twice -> verb="thing"  tail=["turns","twice"] wrong

    The arbiter then looks for a memory with "thing" as its verb, finds none, and vetoes.
    So R1 converts a `recall` failure into a `shape_arbiter` failure: a stage change with
    no score change, which is exactly hazard 1 in the design and exactly what P6 predicted
    -- but P2 predicted a pass, and P2 is wrong.

    This is recorded as a failing prediction rather than fixed by widening the cut. The
    obvious repair -- skip "thing"/"one" after `which` -- is a closed word class, which is
    the fly_v2 failure mode (a modifier class closed at {old, copper, heavy} whose winner
    named "small" the head of "the small brass bell"). R1' needs a principled rule for
    question-phrase length, not a list, and it is designed in section 3 rather than
    smuggled in here.
    """
    flag(("which",))
    a = shape("what turns twice")
    b = shape("which thing turns twice")
    assert a["kind"] == b["kind"] == "subject_unknown"
    assert a["verb"] == "turns" and a["tail"] == ["twice"]
    assert b["verb"] == "thing" and b["tail"] == ["turns", "twice"]
    assert a["verb"] != b["verb"], "if this ever matches, R1' has landed"


def test_a_single_word_which_question_does_parse_correctly(flag):
    """What R1 actually buys: `which` followed directly by a verb parses like `what`.
    The frame that fails in the battery is `which thing ...`, not this one, which is why
    R1 is necessary and not sufficient."""
    flag(("which",))
    got = shape("which turns twice")
    assert got is not None and got["kind"] == "subject_unknown"
    assert got["verb"] == "turns" and got["tail"] == ["twice"]


def test_the_base_three_are_unaffected_by_the_flag(flag):
    flag(("which",))
    assert shape("what does the frost bite")["kind"] == "object_unknown"
    assert shape("what turns twice")["kind"] == "subject_unknown"
    assert shape("where is the box kept")["kind"] == "locative_unknown"


def test_how_is_deliberately_not_widened_by_the_repair_itself(flag):
    """`how many`/`how often` are quantity and count questions with their own cue sets.
    Giving them a shape would put them before the arbiter with no filler to arbitrate, so
    R1 does not add `how` -- and this test fails if someone adds it casually."""
    flag(("which",))
    assert shape("how many times does the bell turn") is None
    assert shape("how often does the bell turn") is None


def test_the_passive_still_has_no_parse_because_r1_is_not_r2(flag):
    """E5's P5: a repair that moves forms it was not aimed at is a repair nobody
    understands. R2 is a separate flag and a separate experiment."""
    flag(("which",))
    assert shape("what is bitten by the frost") is None
    assert shape("what is held by the door") is None


def test_polar_and_imperative_forms_are_untouched(flag):
    flag(("which",))
    assert shape("does the door hold the frost") is None
    assert shape("is the frost held by the door") is None
    assert shape("name the wet thing") is None


def test_what_is_the_box_still_abstains_with_the_flag_on(flag):
    """The copula-abstain branch is what stops `what is the box` from being answered with
    a confabulated filler. Widening the question words must not reach it."""
    flag(("which",))
    assert shape("what is the box") is None
    assert shape("which is the box") is None


def test_the_learned_interrogative_set_is_not_what_r1_changes():
    """Hazard 2 from the design: answer() blacklists memories containing any learned
    interrogative, so teaching the organ that `which` is a question word would also start
    suppressing every stored proposition containing it. R1 is a shape-parser constant and
    must not be wired to the learned set."""
    import inspect
    src = inspect.getsource(N._question_shape)
    assert "SHAPE_INTERROGATIVES" in src
    assert "self.interrogatives" not in src
    assert "is_interrogative" not in src
