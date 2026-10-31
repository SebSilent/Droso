"""E9: RESONANCE_SESSION_SCOPE -- pinning the mouth-class repair before it exists.

The diagnosis (docs/evidence/mouth_diagnosis.md) is that the `mouth` failures are a
RESONANCE defect: `mates` at organs/neural_language.py:3947 is the entire 11,439-word
taught vocabulary, unscoped, so `max()` picks a static corpus attractor whose identity
barely depends on the question. Measured top resonance across four different asks:
0.5738 / 0.5811 / 0.5722 / 0.5730 -- a range of 0.009 -- with `numbered` top-5 in 4 of 4
and `sold` in 3 of 4, while the wanted words score 0.1134-0.4131.

These tests are written first and pin, in order:
  1. the flag exists as a class attribute and defaults False
  2. flag OFF is line-for-line the old candidate list (no brain required)
  3. flag ON excludes the attractor words -- P3, the load-bearing prediction
  4. empty-session fallback returns the FULL pool, so the flag can never turn a
     speaking organism into a silent one
  5. `_speakable` still rejects multi-word strings -- the rendering limit that puts
     the echo ask outside E9's target set
  6. the four journal rows this diagnosis rests on still carry their verified fields
  7. the empty-window regression: no threshold separates attractor from wanted word

Tests 2-5 run on a stub, so they need no connectome build.
"""

import io
import json
import os

import pytest

from organs.neural_language import NeuralLanguage

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEN10 = os.path.join(ROOT, "state", "selection", "generation_10_asks.jsonl")
PROBE = os.path.join(ROOT, "docs", "evidence", "mouth_probe.json")

# The measured corpus attractors (docs/evidence/mouth_probe.json): top-5 across the
# four mouth asks. P3 requires these to be ABSENT from a scoped pool, not merely
# out-scored -- that is what distinguishes scoping from reweighting.
ATTRACTORS = ["numbered", "sold", "agin", "tears", "composed", "unconsciousness",
              "midnight", "strain", "headway"]

# The wanted words, all confirmed present in the 11,439-word vocabulary.
WANTED = ["scarf", "lantern", "copper", "bell", "turns", "twice"]


class _Stub:
    """Just enough organ surface to exercise the candidate filter with no brain."""

    RESONANCE_SESSION_SCOPE = False

    def __init__(self, vocab, session=()):
        self.word_patterns = {w: None for w in vocab}
        self._session = set(session)

    _speakable = NeuralLanguage._speakable

    def _session_words(self):
        return set(self._session)


def _mates(stub, text):
    return NeuralLanguage._resonance_mates(stub, text)


# ---------------------------------------------------------------- 1. the flag

def test_flag_exists_as_class_attribute_and_defaults_false():
    assert hasattr(NeuralLanguage, "RESONANCE_SESSION_SCOPE")
    assert NeuralLanguage.RESONANCE_SESSION_SCOPE is False


def test_flag_sits_beside_the_other_answer_path_genes():
    # The three answer-path genes are one family and should stay visible together.
    for gene in ("ANSWER_COVERAGE_FLOOR", "RECALL_UNFILTERED_FALLBACK",
                 "RESONANCE_SESSION_SCOPE"):
        assert hasattr(NeuralLanguage, gene), gene


# ------------------------------------------------- 2. flag OFF is the old code

def test_flag_off_returns_exactly_the_old_candidate_list():
    vocab = ATTRACTORS + WANTED + ["36", "8", "a", "wet thing"]
    stub = _Stub(vocab, session=["scarf", "lantern"])
    stub.RESONANCE_SESSION_SCOPE = False
    got = _mates(stub, "which of them is wet and is not on the hook?")
    # Old behaviour: every speakable word, unscoped, attractors included.
    assert "numbered" in got and "sold" in got and "agin" in got
    assert "scarf" in got and "lantern" in got
    assert len(got) == len([w for w in vocab if NeuralLanguage._speakable(stub, w)])


def test_flag_off_ignores_the_session_set_entirely():
    # A non-empty session set must not narrow anything while the flag is off.
    vocab = ATTRACTORS + WANTED
    stub = _Stub(vocab, session=["scarf"])
    stub.RESONANCE_SESSION_SCOPE = False
    assert set(_mates(stub, "name the wet thing")) == set(
        w for w in vocab if NeuralLanguage._speakable(stub, w))


def test_flag_off_still_applies_the_single_word_exclude():
    # Pre-existing behaviour, unchanged by E9: a one-word utterance cannot
    # resonate with itself.
    stub = _Stub(["scarf", "numbered"], session=[])
    stub.RESONANCE_SESSION_SCOPE = False
    assert _mates(stub, "scarf") == ["numbered"]
    # ...but a multi-word utterance excludes nothing.
    assert set(_mates(stub, "the scarf is wet")) == {"scarf", "numbered"}


# ------------------------------------- 3. flag ON excludes the attractors (P3)

def test_flag_on_excludes_every_measured_attractor_word():
    vocab = ATTRACTORS + WANTED
    stub = _Stub(vocab, session=["scarf", "lantern", "wet", "hook"])
    stub.RESONANCE_SESSION_SCOPE = True
    got = _mates(stub, "which of them is wet and is not on the hook?")
    for a in ATTRACTORS:
        assert a not in got, "attractor %r survived scoping" % a


def test_flag_on_keeps_the_wanted_word_as_a_candidate():
    vocab = ATTRACTORS + WANTED
    stub = _Stub(vocab, session=["scarf", "lantern"])
    stub.RESONANCE_SESSION_SCOPE = True
    got = _mates(stub, "name the wet thing that is not on the hook")
    assert "scarf" in got


def test_flag_on_pool_is_strictly_smaller_than_the_full_vocabulary():
    # P2 in miniature: the pool must actually shrink, or the mechanism did not engage.
    vocab = ATTRACTORS + WANTED + ["corpus%d" % i for i in range(200)]
    stub = _Stub(vocab, session=["scarf"])
    stub.RESONANCE_SESSION_SCOPE = True
    got = _mates(stub, "which of them is wet?")
    assert len(got) < len(vocab)
    assert got == ["scarf"]


def test_flag_on_still_applies_the_single_word_exclude():
    stub = _Stub(["scarf", "lantern"], session=["scarf", "lantern"])
    stub.RESONANCE_SESSION_SCOPE = True
    assert _mates(stub, "scarf") == ["lantern"]


# ------------------------------------------- 4. empty-session fallback (P2 void)

def test_empty_session_falls_back_to_the_full_pool():
    # The flag must never silence an organism that would otherwise speak.
    vocab = ATTRACTORS + WANTED
    stub = _Stub(vocab, session=[])
    stub.RESONANCE_SESSION_SCOPE = True
    got = _mates(stub, "which of them is wet?")
    assert set(got) == set(w for w in vocab if NeuralLanguage._speakable(stub, w))
    assert "numbered" in got          # attractors are back, by design


def test_no_overlap_falls_back_rather_than_going_silent():
    # Session words exist but none is a speakable vocabulary word: narrowing would
    # empty the pool and the mouth path would return "no words it could answer
    # with". That is a silence the flag is not allowed to cause.
    vocab = ATTRACTORS + WANTED
    stub = _Stub(vocab, session=["zzzqqq", "12345"])
    stub.RESONANCE_SESSION_SCOPE = True
    got = _mates(stub, "which of them is wet?")
    assert got, "scoped pool must never be empty when the full pool is not"
    assert "numbered" in got


def test_session_words_reads_the_binder_you_rows_only():
    # The idiom is _ordinal_answer's (:3070-3080): who == "you" and when >= session_t0.
    class _Binder:
        meta = [
            {"who": "you", "when": 200.0, "tokens": ["the", "scarf", "is", "wet"]},
            {"who": "book", "when": 200.0, "tokens": ["numbered", "sold"]},
            {"who": "you", "when": 50.0, "tokens": ["lantern"]},   # before session_t0
            {"who": "you", "when": 300.0, "tokens": "copper bell turns twice"},
        ]

    class _Cortex:
        binder = _Binder()

    class _Organ:
        cortex = _Cortex()
        session_t0 = 100.0

    got = NeuralLanguage._session_words(_Organ())
    assert got == {"the", "scarf", "is", "wet", "copper", "bell", "turns", "twice"}
    assert "numbered" not in got and "sold" not in got   # corpus rows excluded
    assert "lantern" not in got                          # pre-session row excluded


def test_session_words_is_empty_without_a_store():
    class _Organ:
        cortex = None
        session_t0 = 0.0

    assert NeuralLanguage._session_words(_Organ()) == set()


# --------------------------------------------------- 5. the rendering limit

@pytest.mark.parametrize("w", ["wet thing", "copper bell turns twice", "a b"])
def test_speakable_rejects_multi_word_strings(w):
    # Why the echo ask is outside E9's target set: no ranking outcome can emit it.
    assert NeuralLanguage._speakable(_Stub([]), w) is False


@pytest.mark.parametrize("w", ["36", "8", "a", "", "  "])
def test_speakable_rejects_digits_and_single_characters(w):
    assert NeuralLanguage._speakable(_Stub([]), w) is False


def test_speakable_accepts_real_words():
    assert NeuralLanguage._speakable(_Stub([]), "scarf") is True


# ------------------------------------------------- 6. the journal evidence

def _gen10_mouth_rows():
    if not os.path.exists(GEN10):
        pytest.skip("generation 10 journal not present")
    rows = [json.loads(l) for l in io.open(GEN10, encoding="utf-8") if l.strip()]
    return [r for r in rows if r.get("stage") == "mouth"]


def test_generation_10_has_four_mouth_rows_all_probe_tier():
    rows = _gen10_mouth_rows()
    assert len(rows) == 4
    assert all(r.get("tier") == "probe" for r in rows)
    assert all(r.get("pass") is False for r in rows)
    assert all(r.get("cause") == "mouth" for r in rows)


def test_mouth_rows_never_reached_the_recall_gate():
    # coverage null is what separates this class from the recall class.
    for r in _gen10_mouth_rows():
        assert r.get("coverage") is None


def test_mouth_rows_answered_by_resonance_not_by_an_arbiter():
    for r in _gen10_mouth_rows():
        assert str(r.get("source") or "").startswith("meaning resonance")


def test_journal_does_not_store_the_utterance():
    # Provenance guard: the babble strings in the diagnosis come from the probe,
    # not from the journal. Any test asserting on `utterance` here would be
    # asserting on a field that is null.
    for r in _gen10_mouth_rows():
        assert r.get("utterance") is None


def test_mouth_class_cannot_move_the_frozen_score():
    rows = _gen10_mouth_rows()
    assert rows and all(r.get("tier") != "frozen" for r in rows)


# ------------------------------------------------- 7. the empty window

def _probe_rows():
    if not os.path.exists(PROBE):
        pytest.skip("mouth probe json not present")
    return json.load(io.open(PROBE, encoding="utf-8"))


def test_no_threshold_separates_attractor_from_wanted_word():
    rows = _probe_rows()
    assert len(rows) == 4
    winners = [r["argmax_score"] for r in rows]
    wanted = [s for r in rows for s in r["wanted_score"].values()]
    # Every winner sits above every wanted score, so the bands do not overlap and
    # no value of reply_threshold can admit one while excluding the other.
    assert min(winners) > max(wanted)
    assert min(winners) >= 0.55          # all four clear the standing threshold
    assert max(wanted) < 0.55            # no wanted word ever clears it


def test_the_resonance_winner_is_ask_independent():
    # The decisive measurement: four different asks, top score range 0.009.
    rows = _probe_rows()
    winners = [r["argmax_score"] for r in rows]
    assert max(winners) - min(winners) < 0.02
    asks = {r["ask"] for r in rows}
    assert len(asks) == 4                # ...on four genuinely different asks


def test_wanted_words_were_present_in_the_vocabulary():
    # Rules out retrieval: nothing was failed to be found.
    rows = _probe_rows()
    for r in rows:
        assert all(r["wanted_in_vocabulary"].values())
        assert r["vocabulary"] > 10000   # the pool is corpus-sized


def test_the_attractor_words_recur_across_asks():
    rows = _probe_rows()
    tops = [t[0] for r in rows for t in r["top5"]]
    assert tops.count("numbered") >= 3
    assert tops.count("sold") >= 3
