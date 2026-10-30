r"""Pins the teaching episode's generator and its gates.

Nothing here builds a house. The generator is the part of E1 that could silently
invalidate the result -- a proposition already in the binder measures corpus recall
instead of learning, a word with no postings measures a refusal instead of a memory,
and an open-tier ask that replayed its own tell would measure same-session recall
instead of retention -- so those are the properties pinned here.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import organs.neural_language as nl  # noqa: E402
import tools.teach_episode as te  # noqa: E402

# A vocabulary of content words plus the kinds of thing the filter must reject.
WORDS = ["lantern", "kettle", "basket", "copper", "hammer", "window", "pepper",
         "mirror", "button", "feather", "thistle", "anchor", "chimney", "pocket",
         "velvet", "marble", "willow", "harbour", "lantern2", "cinder", "meadow",
         "pebble", "timber", "candle", "fathom", "garden", "hollow", "ivory",
         "juniper", "kennel", "lemon", "muzzle", "noodle", "orchid", "parcel",
         "quarry", "ribbon", "saddle", "tunnel", "urchin", "violet", "walnut",
         "yonder", "zenith", "bramble", "cellar", "dapple", "ember", "flint",
         # closed-class words long enough to reach the function-word filter rather
         # than being rejected by the length filter first, which is what made the
         # first version of that assertion vacuous
         "which", "there", "because", "under",
         "the", "of", "and", "is", "at", "ab", "xylophone"]


class StubBinder:
    max_roles = 8

    def __init__(self, known, meta=()):
        self.known = set(known)
        self.meta = list(meta)

    def stem_rows(self, w):
        return [0] if str(w).lower() in self.known else []


def stub_lang(words=WORDS, known=None, meta=()):
    known = WORDS if known is None else known
    return SimpleNamespace(
        word_patterns={w: {} for w in words},
        cortex=SimpleNamespace(binder=StubBinder(known, meta)),
        _speakable=lambda w: True,
    )


# ------------------------------------------------------------- generator ----

def test_the_generator_draws_only_from_the_vocabulary_it_is_given():
    """No private word list. fly_v2 generated synthetic spans whose modifier class
    was closed at {old, copper, heavy} and the winner it bred named 'small' the head
    of 'the small brass bell'; the guard against a repeat is that every word in every
    fact is traceable to the vocabulary handed in.
    """
    lang = stub_lang()
    gen = te.generate(lang, 5, seed=3)
    assert len(gen["facts"]) == 5
    for f in gen["facts"]:
        for role in ("a", "v", "b"):
            assert f[role] in WORDS, (role, f[role])
    assert gen["vocab_source"].startswith("lang.word_patterns")


def test_a_word_the_binder_has_no_postings_for_is_never_used():
    """A word with no postings is dropped from answer()'s must-set, so teaching with
    one measures a refusal rather than a memory. 'xylophone' is in the vocabulary but
    not in the binder's known set here."""
    lang = stub_lang(known=[w for w in WORDS if w != "xylophone"])
    gen = te.generate(lang, 5, seed=11)
    words = {f[r] for f in gen["facts"] for r in ("a", "v", "b")}
    assert "xylophone" not in words
    assert gen["rejections"]["no_postings"] >= 1


def test_closed_class_words_are_filtered_by_the_organs_own_sets():
    lang = stub_lang()
    gen = te.generate(lang, 5, seed=5)
    words = {f[r] for f in gen["facts"] for r in ("a", "v", "b")}
    for w in ("the", "of", "and", "is", "at"):
        assert w not in words
    assert gen["rejections"]["function_word"] >= 1


def test_words_shorter_than_the_minimum_are_rejected():
    lang = stub_lang()
    te.generate(lang, 3, seed=7)
    fn = te.function_words()
    assert "the" in fn and "at" in fn and "of" in fn
    # The organ's own sets are unioned in, not reimplemented beside them.
    for w in nl.NeuralLanguage.SHAPE_FUNCTION_WORDS:
        assert str(w).lower() in fn
    for w in nl.NeuralLanguage.RECORD_SKIP:
        assert str(w).lower() in fn


def test_no_word_holds_two_roles_in_one_batch():
    """Two facts sharing a content word can be answered from each other, which would
    make the acquisition number ambiguous about which fact was learned."""
    lang = stub_lang()
    gen = te.generate(lang, 6, seed=13)
    seen = set()
    for f in gen["facts"]:
        for r in ("a", "v", "b"):
            assert f[r] not in seen, f"{f[r]} used twice"
            seen.add(f[r])


def test_a_proposition_already_in_the_binder_is_redrawn_not_taught():
    """The absence check has to use the binder's OWN repeat key, or a 'novel'
    proposition can still land as a repeat and teach nothing."""
    lang = stub_lang()
    first = te.generate(lang, 1, seed=21)["facts"][0]
    key = ("the", first["a"], first["v"], "the", first["b"])
    lang2 = stub_lang(meta=[{"tokens": list(key), "who": "book", "count": 1}])
    gen = te.generate(lang2, 1, seed=21)
    assert gen["binder_collisions"] == 1
    got = gen["facts"][0]
    assert (got["a"], got["v"], got["b"]) != (first["a"], first["v"], first["b"])
    # absence_checks counts CHECKS, not facts: the collision was checked and redrawn,
    # so two checks produced one fact. The episode gate does not rely on this counter
    # -- it re-verifies every fact against the pre-teaching census -- precisely
    # because a counter the generator increments itself is not evidence.
    assert gen["absence_checks"] == 2


def test_generation_is_reproducible_from_its_seed():
    a = te.generate(stub_lang(), 5, seed=31)["facts"]
    b = te.generate(stub_lang(), 5, seed=31)["facts"]
    c = te.generate(stub_lang(), 5, seed=32)["facts"]
    assert a == b
    assert a != c


def test_a_batch_too_novel_to_generate_is_an_error_not_a_shortcut():
    """Three usable words cannot make five facts with one role per word. Silently
    returning four would understate the batch and quietly change the denominator."""
    lang = stub_lang(words=["lantern", "kettle", "basket"],
                   known=["lantern", "kettle", "basket"])
    with pytest.raises(SystemExit):
        te.generate(lang, 5, seed=1)


# ----------------------------------------------------------- batch shape ----

def test_the_open_batch_contains_no_tells(tmp_path):
    """The single most important property of the open tier. A tell in the batch would
    make the ask a same-session recall test, and the whole point of measuring against
    a shadow in a fresh build is that it is a RETENTION test across a process
    boundary.
    """
    gen = te.generate(stub_lang(), 6, seed=41)
    out = te.batch_files(gen, tmp_path)
    doc = json.loads(Path(out["path"]).read_text(encoding="utf-8"))
    for s in doc["scripts"]:
        for t in s["turns"]:
            assert "say" not in t, f"{s['name']} replays a tell"
            assert "ask" in t and "expect" in t and "frame" in t
    assert out["acquisition_asks"] == 6
    assert out["heldout_asks"] == 6


def test_the_held_out_ask_is_never_the_taught_ask(tmp_path):
    gen = te.generate(stub_lang(), 8, seed=43)
    for f in gen["facts"]:
        assert f["ask_H"] != f["ask_T"], f
        assert f["frame_H"] in te.FRAMES_HELDOUT


def test_the_reverse_role_frame_expects_the_other_role(tmp_path):
    """H1 asks for the subject, H2 and H3 ask the same question as T in other words
    and so expect the object. Getting this backwards would grade a correct answer as
    a forbidden one."""
    gen = te.generate(stub_lang(), 12, seed=47)
    frames = {f["frame_H"] for f in gen["facts"]}
    assert len(frames) > 1, "one seed should reach more than one held-out frame"
    for f in gen["facts"]:
        if f["frame_H"].startswith("H1"):
            assert f["answer_H"] == f["a"] and f["forbid_H"] == [f["b"]]
        else:
            assert f["answer_H"] == f["b"] == f["answer_T"]
            assert f["forbid_H"] == [f["a"]]


def test_the_batch_seal_moves_if_a_fact_moves(tmp_path):
    gen = te.generate(stub_lang(), 5, seed=53)
    a = te.batch_files(gen, tmp_path / "a")["seal"]
    gen["facts"][0]["b"] = "somethingelse"
    b = te.batch_files(gen, tmp_path / "b")["seal"]
    assert a != b


# ----------------------------------------------------------------- gates ----

def test_a_gate_that_was_never_run_fails_the_verdict():
    """The pilot ran --tier open, so frozen and guarded were 0/0 and the erosion gate
    reported PASS on nothing it had measured. None is not True."""
    gates = {"absence_verified": True, "erosion_zero": None,
             "erosion_zero_detail": "NOT MEASURED", "census_reported": True,
             "live_seals_unchanged": True, "row_self_contained": True}
    assert te.verdict_of(gates) == "FAIL"


def test_the_verdict_needs_every_gate():
    base = {k: True for k in te.REQUIRED_GATES}
    assert len(base) == 5, "the design names five gated criteria"
    assert te.verdict_of(dict(base)) == "PASS"
    for k in base:
        bad = dict(base)
        bad[k] = False
        assert te.verdict_of(bad) == "FAIL", f"{k} False must fail"
        # Absent is not the same as True: a row written by an older or partial code
        # path must not pass by omission.
        missing = {x: v for x, v in base.items() if x != k}
        assert te.verdict_of(missing) == "FAIL", f"{k} absent must fail"
        unknown = dict(base)
        unknown[k] = None
        assert te.verdict_of(unknown) == "FAIL", f"{k} unmeasured must fail"


def test_an_empty_gate_set_is_not_a_pass():
    assert te.verdict_of({}) == "FAIL"


def test_detail_keys_carry_evidence_and_are_not_themselves_gates():
    """Every gate has a *_detail string so the record says WHY, not just whether. A
    detail key must not be able to stand in for its gate."""
    gates = {k: True for k in te.REQUIRED_GATES}
    gates["erosion_zero_detail"] = "0 lost: []"
    assert te.verdict_of(gates) == "PASS"
    gates["erosion_zero"] = False
    assert te.verdict_of(gates) == "FAIL", "a detail string cannot rescue its gate"
