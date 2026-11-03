"""ELECTRIC_ARBITER_TELL: when the shape arbiter has verified a memory and named the word in it
that answers the ask, say that memory whole -- but only when it adds nothing the ask did not name.

MEASURED, from the committed evidence file (`docs/evidence/electric_learn_bench.json`, learn arm,
depth 3, live phase -- the eight probes the mode still cannot answer):

    python -c "import json,collections; d=json.load(open('docs/evidence/electric_learn_bench.json',encoding='utf-8'));
    c=collections.Counter((a,ph,r['src']) for a in d['arms'] for dep,pr in d['arms'][a]['probes'].items()
    for ph,rows in pr.items() for r in rows if r['mech']=='fallback_fragment'); print(c)"

Of the 8, SEVEN come back `arbiter head`: one word. In seven of seven the row the arbiter chose IS
the tell the person taught, word for word, `who == "you"`, verdict `agree` -- and the only content
word the row adds beyond the ask's own words is the filler it named. He is holding the sentence and
handing over a syllable of it.

Why the branch does that, and why this is not simply a bug fix. The head-only line is deliberate,
and `docs/STATE.md:1504` is the receipt: `what turns twice?` is answered `bell` and **passes in gen
24** because reading its row out loud -- `the copper bell turns twice` -- speaks `copper`, which
nobody asked about and the grader forbids. `docs/archive/experiment_log.md:3804` records exactly
that flip: FAIL saying the sentence, FAIL saying `copper`, PASS saying `bell`. So a flag that said
the sentence whenever the arbiter verified one would regress a graded ask. This one says it only
when the sentence carries no word the ask omitted except the answering word, which is the same
condition in the other direction: the leak is the reason for the branch, so the bound is the leak.

What this file pins, in order of how badly it would hurt to lose it:
  * the leak guard, on the graded ask itself (`what turns twice?` -> `bell`, flag ON);
  * the widening, on the case it exists for (`what guards the gate` -> the whole tell);
  * every bound as a rejection of the pure predicate, on rows shaped like real ones;
  * that OFF leaves THIS BRANCH's reply byte for byte as it was -- a claim about the branch, not about
    the whole run with the flag ON, which is not unchanged (docs/STATE.md, ELECTRIC_ARBITER_TELL);
  * that the mode table calls it a widening and gives it no parent.

The path repros are pinned as deterministic because they were measured that way: 6 fresh organs in
a process, the process run 3 times, one outcome each (`_tmp/determinism_check.py`, findings now in
docs/STATE.md). Where the recall path IS known to be process-nondeterministic
(`tests/test_electric_fragment_guard.py`) this file does not go.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import organs.neural_language as nl                        # noqa: E402
import tools.electric_teach_mode as tm                     # noqa: E402
from connectome.engine import HybridEngine                 # noqa: E402
from connectome.substrate import build_core_graph          # noqa: E402
from organs.tokenizer import TokenizerOrgan                # noqa: E402

CLASS_DEFAULTS = {a: getattr(nl.NeuralLanguage, a, "<absent>") for a in tm.ALL_ATTRS}

# The two tells the collision case needs: they share `the dog ... the`, so the binder's ranking is
# not what decides, and `what guards the gate` reaches the arbiter with a real rival hit.
GUARD = "the dog guards the gate"
BITE = "the dog bites the latch"
# The graded leak, verbatim from the battery: a modifier nobody asked about.
COPPER = "the copper bell turns twice"


def _organ(learn=True):
    o = nl.NeuralLanguage(HybridEngine(graph=build_core_graph()), TokenizerOrgan())
    o.persist = False
    o.cortex.MIN_HEAR_INTERVAL_S = 0.0
    o.exposure_enabled = False
    if learn:
        tm.enable_learn(o)
    return o


def _told(learn=True, tells=(BITE, GUARD), speaker="you"):
    """ORDER IS PART OF THE REPRO, not decoration. Told GUARD first, `what guards the gate` is
    answered by the taught-fact store (`src=electric_taught`, the whole sentence, no arbiter
    involved) and this flag's branch is never reached. Told BITE first -- the order every run in
    `_tmp/determinism_check.py` used, 6 organs x 3 processes, one outcome -- the taught store does
    not answer, the recall path runs, and the arbiter names `dog`. Both outcomes are correct; only
    one of them is the branch under test."""
    o = _organ(learn)
    for t in tells:
        o.hear(t, speaker=speaker)
    return o


def _row(tokens, who="you", ask=False):
    """A memory row with the three keys `_arbiter_tell` reads, shaped like the real ones
    (`tokens`, `who`, `ask`) and nothing else, so the predicate is tested against the row it is
    handed and not against a row this file invented."""
    return {"tokens": list(tokens), "who": who, "ask": ask}


def _said(out):
    out = out or {}
    return str(out.get("utterance") or out.get("response") or "").strip()


# ------------------------------------------------------------------ the flag and the mode

def test_the_flag_is_off_on_the_class_and_learn_mode_turns_it_on():
    assert nl.NeuralLanguage.ELECTRIC_ARBITER_TELL is False
    before = dict(CLASS_DEFAULTS)
    assert _organ(learn=True).ELECTRIC_ARBITER_TELL is True
    assert _organ(learn=False).ELECTRIC_ARBITER_TELL is False, \
        "teach mode is the mode that can only ever refuse; this one lets a sentence out"
    assert {a: getattr(nl.NeuralLanguage, a, "<absent>") for a in tm.ALL_ATTRS} == before, \
        "a demo flag moved a class default"


def test_the_table_lists_it_as_a_widening_and_gives_it_no_parent():
    assert "ELECTRIC_ARBITER_TELL" in tm.EXCLUDED_ATTRS
    assert "ELECTRIC_ARBITER_TELL" in tm.LEARN_ATTRS
    assert "ELECTRIC_ARBITER_TELL" not in tm.STACK_ATTRS, \
        "a widening is not in the mode that can only ever refuse"
    assert len(tm.EXCLUDED) == 7 and len(tm.ALL_ATTRS) == 21, (
        "census: 18 before MP-E9, 20 with its two treatment arms, 21 with F1 (per-entry aliases), "
        "the plan's registered fallback for the morphology defect. CANDIDATE contributes "
        "ELECTRIC_ARBITER_HEAD_BOUND, ELECTRIC_QA_MORPH_NORMALIZE and ELECTRIC_QA_MORPH_ALIASES: "
        "they are in ALL_ATTRS so state() reports their state instead of omitting it, and in no "
        "enable*() so no mode turns them on by accident. Bumping this number is only correct "
        "alongside the composition assertion below.")
    assert tm.ALL_ATTRS == (tm.STACK_ATTRS + tm.BASE_ATTRS + tm.EXCLUDED_ATTRS
                            + tm.CANDIDATE_ATTRS)
    assert "ELECTRIC_ARBITER_TELL" not in tm.CANDIDATE_ATTRS
    assert "ELECTRIC_ARBITER_TELL" not in tm.DEPENDS_ON, \
        "it sits inside the branch the shape arbiter already gates; a claimed parent would be a lie"
    assert any(l.startswith("WIDENS") and "ELECTRIC_ARBITER_TELL" in l
               for l in tm.describe_learn()), tm.describe_learn()


def test_the_narrow_mode_leaves_it_off_and_the_wide_mode_has_it():
    narrow, wide = _organ(learn=False), _organ(learn=True)
    tm.enable(narrow)
    tm.enable_learn(wide)
    assert not narrow.ELECTRIC_ARBITER_TELL
    assert wide.ELECTRIC_ARBITER_TELL


# ---------------------------------------------------------------- the widening, on the path

def test_a_verified_row_that_adds_only_the_answer_is_spoken_whole():
    """The case the flag exists for: the arbiter verified `the dog guards the gate` against
    `what guards the gate`, named `dog`, and said nothing else. Off, this is the one-word branch
    that was there before; on, the person gets the sentence they taught, under a source of its own."""
    base = _told()                       # learn mode, so the flag is ON with the rest of the mode
    base.ELECTRIC_ARBITER_TELL = False   # the one thing this comparison changes
    off = base.answer("what guards the gate") or {}
    assert off.get("source") == "arbiter head", off
    assert _said(off) == "dog", off

    o = _told()
    o.ELECTRIC_ARBITER_TELL = True
    on = o.answer("what guards the gate") or {}
    assert on.get("source") == "arbiter tell", on
    assert _said(on) == GUARD, on


def test_the_widening_does_not_need_learn_mode():
    """No parent switch: teach mode does not turn it on, but a person who asks for the switch gets
    it with the narrow mode, and the sentence comes out the same way."""
    o = _told(learn=False)
    assert o.ELECTRIC_ARBITER_TELL is False
    o.ELECTRIC_ARBITER_TELL = True
    out = o.answer("what guards the gate") or {}
    assert out.get("source") == "arbiter tell", out
    assert _said(out) == GUARD, out


def test_off_is_the_line_that_ran_before():
    """With the flag off, `arbiter tell` is not reachable at all -- not as a source, not as a
    sentence. This is the claim that makes the flag revertible."""
    for asks in (("what guards the gate",), ("what turns twice",), ("what bites the latch",)):
        o = _told(tells=(BITE, GUARD, COPPER))
        o.ELECTRIC_ARBITER_TELL = False
        for a in asks:
            out = o.answer(a) or {}
            assert out.get("source") != "arbiter tell", (a, out)


# ---------------------------------------------------------------- the leak guard, graded

def test_the_graded_leak_stays_guarded():
    """`what turns twice?` answers `bell` in gen 24 BECAUSE the row is not read out loud: the row is
    `the copper bell turns twice` and `copper` is in nobody's question. Flag ON must not change this
    answer by one word. If this test ever fails, the graded battery regresses."""
    for learn in (True, False):
        o = _told(learn=learn, tells=(COPPER, BITE))
        o.ELECTRIC_ARBITER_TELL = True
        out = o.answer("what turns twice") or {}
        assert _said(out) == "bell", (learn, out)
        assert out.get("source") == "arbiter head", (learn, out)
        assert "copper" not in _said(out), out


def test_a_corpus_window_is_never_re_issued_as_a_lesson():
    """Same ask, same row, same arbiter -- but `who == "book"`. Nobody told him that sentence, and a
    window of someone else's prose is not a fact he may re-issue whole. The one-word branch stays."""
    o = _told(speaker="book")
    o.ELECTRIC_ARBITER_TELL = True
    out = o.answer("what guards the gate") or {}
    assert out.get("source") == "arbiter head", out
    assert _said(out) == "dog", out


# ------------------------------------------------- the bounds, as rejections of the predicate

def test_a_row_that_adds_a_word_the_ask_omitted_is_refused():
    """The leak, stated as one predicate rather than as a battery outcome."""
    o = _organ()
    assert o._arbiter_tell(_row(COPPER.split()), "bell", ["what", "turns", "twice"]) is None


def test_a_row_that_adds_nothing_but_the_answer_is_taken():
    o = _organ()
    said = o._arbiter_tell(_row(GUARD.split()), "dog", ["what", "guards", "the", "gate"])
    assert said == GUARD, said


def test_function_words_the_ask_did_not_use_are_not_leaks():
    """The bound is on CONTENT words, set aside by the organ's own `SHAPE_FUNCTION_WORDS`. A row that
    adds an article the ask happened not to use is still the sentence the person said."""
    o = _organ()
    assert o._arbiter_tell(_row(["the", "dog", "guards", "a", "gate"]), "dog",
                           ["what", "guards", "the", "gate"]) == "the dog guards a gate"


def test_the_row_is_folded_by_the_projects_one_stemmer():
    """`what guard the gate` and `the dog guards the gate` are the same content words. The predicate
    uses `organs.stemming.stem`, the same fold ELECTRIC_QA_PARAPHRASE was built from -- it does not
    grow a second idea of what a word-match is."""
    o = _organ()
    assert o._arbiter_tell(_row(GUARD.split()), "dog",
                           ["what", "guard", "the", "gate"]) == GUARD


def test_a_one_word_row_has_no_sentence_to_speak():
    o = _organ()
    assert o._arbiter_tell(_row(["dog"]), "dog", ["what", "guards", "the", "gate"]) is None


def test_a_row_that_is_itself_an_asking_is_not_a_fact():
    """The recorded verdict, not a guess from shape -- the same `_hit_is_ask` the admissibility entry
    uses, on both halves of it: the tag, and a mark still riding on a token."""
    o = _organ()
    asked = ["what", "bites", "the", "latch"]
    tagged = _row(["the", "dog", "bites", "the", "latch"], ask=True)
    assert o._arbiter_tell(tagged, "dog", asked) is None
    marked = _row(["what", "bites", "the", "latch?"])
    assert o._arbiter_tell(marked, "what", asked) is None


def test_the_named_word_must_be_a_word_of_the_row():
    """The arbiter named `cat`; this row does not contain it, so this row is not where the answer
    came from and it is not the answer's sentence."""
    o = _organ()
    assert o._arbiter_tell(_row(GUARD.split()), "cat",
                           ["what", "guards", "the", "gate"]) is None


def test_a_mark_on_the_named_word_is_not_part_of_the_word():
    o = _organ()
    assert o._arbiter_tell(_row(GUARD.split()), "dog?",
                           ["what", "guards", "the", "gate"]) == GUARD


def test_the_predicate_is_given_the_row_the_arbiter_actually_chose():
    """The unit rows above are faithful: a real run hands `_arbiter_tell` a row whose keys include
    exactly these three, so a test that invented a richer row would be testing a shape that does
    not occur."""
    seen = {}
    original = nl.NeuralLanguage._arbiter_tell

    def spy(self, best, filler, q):
        seen["keys"] = set(best)
        seen["filler"] = filler
        return original(self, best, filler, q)

    nl.NeuralLanguage._arbiter_tell = spy
    try:
        o = _told()
        o.ELECTRIC_ARBITER_TELL = True
        o.answer("what guards the gate")
    finally:
        nl.NeuralLanguage._arbiter_tell = original
    assert {"tokens", "who", "ask"} <= seen["keys"], seen["keys"]
    assert seen["filler"] == "dog", seen


# ------------------------------------------------------------------ the inert-flag warning

def test_a_run_with_it_on_alone_is_not_reported_as_inert():
    """`warnings()` exists to tell a person a switch they turned on cannot fire because its parent is
    off. This one has no parent, so it must never appear there -- and the mode's own warnings must
    still be about the switches that DO have parents."""
    o = _organ(learn=False)
    o.ELECTRIC_ARBITER_TELL = True
    assert not [w for w in tm.warnings(o) if "ARBITER_TELL" in w], tm.warnings(o)
