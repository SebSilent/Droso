"""ELECTRIC_QA_ANSWER_MEMORY -- keep the lesson, cast no vote.

`learn_qa` admits a pair when the answer differs from the question by **exactly one word on each
side**. That is the right rule for discovering what a question word asks about -- `what bites the
latch` over `the dog bites the latch` is one swap, and it says `what` wanted the subject -- and it is
the rule the QA store inherited, which is a different job. `tools/electric_learn_bench.py` taught
sixteen pairs in conversation and counted what reached memory: **ten**, and of the three whose answer
sentence exists nowhere else in the house -- the only three the store is FOR -- **zero**. `where does
the bell hang? / the bell hangs on the wall` is refused at 3 missing / 3 new, so an answer that tells
you something new could not be taught at all.

This flag separates the two rules, and the separation is the whole design. The arithmetic stays the
grammar's: a refused pair votes nothing into `question_roles`, `interrogatives`, `answer_types` and
`qa_pairs_seen`, because a pair that does not pin a role must not teach one -- that is precisely how
the corpus's refused warmint pair once taught this organ that `what` asks role 5. What changes is
only that the pair may be *kept*, with its provenance and its verbatim answer.

Five bounds, one test each, and the last two are the ones that make this safe rather than merely
permissive: an answer that adds nothing is an echo, and two turns that share no content word are not
a question and its answer no matter what order they were typed in.
"""
import shutil
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

# A pair the arithmetic refuses (3 words new on each side) and one it accepts, from the curriculum.
LOOSE = (["where", "does", "the", "bell", "hang"], ["the", "bell", "hangs", "on", "the", "wall"])
STRICT = (["what", "bites", "the", "latch"], ["the", "dog", "bites", "the", "latch"])

CONV = {"source": "conversation", "speaker": "you", "turn": 1, "marked": True,
        "answer_is_question": False}


def _organ(learn=True):
    o = nl.NeuralLanguage(HybridEngine(graph=build_core_graph()), TokenizerOrgan())
    o.persist = False
    o.cortex.MIN_HEAR_INTERVAL_S = 0.0
    o.exposure_enabled = False
    if learn:
        tm.enable_learn(o)
    return o


def _key(o, toks):
    return o.qa_key(toks)


# ------------------------------------------------------------------ the flag ----

def test_the_flag_is_off_on_the_class_and_learn_mode_never_moves_it():
    assert nl.NeuralLanguage.ELECTRIC_QA_ANSWER_MEMORY is False
    before = dict(CLASS_DEFAULTS)
    assert _organ().ELECTRIC_QA_ANSWER_MEMORY is True
    assert _organ(learn=False).ELECTRIC_QA_ANSWER_MEMORY is False, \
        "teach mode is the mode that can only ever refuse"
    assert {a: getattr(nl.NeuralLanguage, a, "<absent>") for a in tm.ALL_ATTRS} == before, \
        "a demo flag moved a class default"


def test_a_refused_pair_is_still_kept_and_the_refusal_is_still_reported():
    o = _organ()
    r = o.learn_qa(*LOOSE, provenance=dict(CONV))
    assert not r["learned"], r
    assert "roles missing" in r["reason"], r
    assert r.get("stored") == _key(o, LOOSE[0]), r
    assert r.get("stored_without_vote") is True, r
    rec = o.qa_store[_key(o, LOOSE[0])]
    assert " ".join(rec["a"]) == "the bell hangs on the wall", rec


def test_the_grammar_does_not_move_at_all():
    """The bound the whole design rests on. Ten accepted pairs vote; this one must not, and the
    check is the state of the grammar before and after, not a count of what this call returned."""
    o = _organ()
    o.learn_qa(*STRICT, provenance=dict(CONV))
    roles = {w: dict(v) for w, v in o.question_roles.items()}
    types = {w: dict(v) for w, v in o.answer_types.items()}
    inter, seen = set(o.interrogatives), o.qa_pairs_seen
    o.learn_qa(*LOOSE, provenance=dict(CONV))
    assert o.question_roles == roles, "a refused pair voted a role"
    assert o.answer_types == types, "a refused pair voted an answer type"
    assert o.interrogatives == inter and o.qa_pairs_seen == seen, \
        "`where` must not become an interrogative because somebody answered a `where` question"


def test_with_the_flag_off_the_same_pair_is_not_kept():
    o = _organ()
    o.ELECTRIC_QA_ANSWER_MEMORY = False
    r = o.learn_qa(*LOOSE, provenance=dict(CONV))
    assert not r.get("stored") and not o.qa_store, o.qa_store


# ------------------------------------------------------------------ the bounds ----

def test_no_provenance_no_memory():
    o = _organ()
    assert not o.learn_qa(*LOOSE, provenance=None).get("stored")
    assert not o.qa_store


def test_an_answer_that_is_itself_a_question_is_never_kept():
    o = _organ()
    r = o.learn_qa(*LOOSE, provenance=dict(CONV, answer_is_question=True))
    assert not r.get("stored"), r
    assert not o.qa_store, "a question answering a question is not a lesson"


def test_only_a_person_marked_conversation_pair_qualifies():
    """This flag is about someone teaching him, not about a corpus line that happened to sit in
    question order. A book pair, or an ask whose `?` did not survive, is not its business."""
    for prov, why in (({"source": "book", "marked": True}, "a book line"),
                      ({"source": "conversation", "marked": False}, "an unmarked ask")):
        o = _organ()
        r = o.learn_qa(*LOOSE, provenance=dict(prov, answer_is_question=False, speaker="you"))
        assert not r.get("stored"), f"{why} was kept: {r}"
        assert not o.qa_store, why


def test_an_answer_that_adds_nothing_is_an_echo_and_is_refused():
    o = _organ()
    q = ["where", "does", "the", "bell", "hang"]
    r = o.learn_qa(q, list(q), provenance=dict(CONV))
    assert not r.get("stored"), "the question repeated back is not a memory worth having"
    assert not o.qa_store


def test_two_unrelated_turns_do_not_become_a_pair():
    """Adjacency is not aboutness. The strict rule enforced that implicitly by demanding one word
    swapped; a looser admission has to say it out loud, or `what is your name?` paired with
    `the sky is blue` is a memory, and he would answer a question about you with the weather."""
    o = _organ()
    q = ["what", "is", "your", "name"]
    a = ["the", "sky", "is", "blue"]
    r = o.learn_qa(q, a, provenance=dict(CONV))
    assert not r.get("stored"), r
    assert not o.qa_store, "shared function words are not a shared subject"


def test_first_tell_wins_across_the_two_admissions():
    """A loose keep must never overwrite a strict one -- the same rule `_qa_keep` already applies
    to a pair re-read, and the widening must not become a way to edit a stored answer."""
    o = _organ()
    o.learn_qa(*STRICT, provenance=dict(CONV))
    kept = _key(o, STRICT[0])
    r = o.learn_qa(STRICT[0], ["the", "cat", "bites", "the", "latch"], provenance=dict(CONV))
    assert not r.get("stored"), r
    assert " ".join(o.qa_store[kept]["a"]) == "the dog bites the latch", o.qa_store[kept]


# ------------------------------------------------------------------ the read side ----

def test_a_kept_pair_answers_only_the_words_that_were_asked():
    o = _organ()
    o.learn_qa(*LOOSE, provenance=dict(CONV))
    assert (o.answer("where does the bell hang") or {}).get("utterance") \
        == "the bell hangs on the wall"
    for other in ("where should the bell hang", "does the bell hang"):
        r = o.answer(other) or {}
        assert not r.get("answered") or r.get("source") != "electric_qa_store", (other, r)
    # And one that DOES answer, pinned because it is surprising: under learn mode the ask-shape
    # normalizer canonicalizes a question typed without its mark or its auxiliary onto the stored
    # key. That is the widening already measured and already behind its own two flags -- this flag
    # did not open the door, it just put something worth answering behind it.
    r = o.answer("where the bell hangs") or {}
    assert r.get("source") == "electric_qa_store", r
    assert r.get("utterance") == "the bell hangs on the wall", r


def test_a_loose_record_makes_no_claim_about_which_word_asks():
    """`word` empty and `role` -1 are not placeholders, they are the assertion: the grammar does
    not know what `where` asks about here, so the `learned` route is closed on this record and only
    a typed or person-marked ask can open it."""
    o = _organ()
    o.learn_qa(*LOOSE, provenance=dict(CONV))
    rec = o.qa_store[_key(o, LOOSE[0])]
    assert rec["word"] == "" and rec["role"] == -1, rec
    assert "where" not in o.question_roles, "the vote leaked"


def test_the_only_sentences_this_path_can_speak_are_sentences_a_person_said():
    """The sweep, stated as the invariant rather than hoped: whatever these bounds admit, the answer
    is the person's own tokens, so a confabulation is not reachable through this flag at all."""
    o = _organ()
    pairs = [LOOSE,
             (["what", "rings", "in", "the", "tower"], ["the", "copper", "bell", "rings"]),
             (["how", "many", "dogs", "sleep"], ["two", "dogs", "sleep"]),
             (["what", "does", "mira", "love", "most"], ["she", "loves", "the", "lantern", "most"])]
    said = set()
    for q, a in pairs:
        said.add(" ".join(a))
        o.learn_qa(q, a, provenance=dict(CONV))
    for q, a in pairs:
        r = o.answer(" ".join(q)) or {}
        got = str(r.get("utterance") or "").strip()
        if r.get("source") == "electric_qa_store":
            assert got in said, (q, got)


def test_a_loose_pair_survives_a_restart_and_still_answers():
    """The store is the persisted part, and a memory that dies on reload is not a memory. Written
    and read through the same files the server uses."""
    tmp = ROOT / "_tmp" / "ansmem_restart"
    if tmp.exists():
        shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True, exist_ok=True)
    o = _organ()
    o.state_path = tmp / "lang.json"
    o.persist = True          # `_organ` turns persistence off; this test is about writing it down
    o.learn_qa(*LOOSE, provenance=dict(CONV))
    assert o.save_state(force=True).get("saved"), "the state was never written"
    o2 = _organ()
    o2.state_path = tmp / "lang.json"
    o2.persist = True
    assert (o2.load_state() or {}).get("loaded"), "nothing was read back"
    assert _key(o2, LOOSE[0]) in o2.qa_store, sorted(o2.qa_store)
    assert (o2.answer("where does the bell hang") or {}).get("utterance") \
        == "the bell hangs on the wall"
    shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------ the table ----

def test_the_table_lists_it_as_a_widening_and_declares_its_parent():
    assert "ELECTRIC_QA_ANSWER_MEMORY" in tm.EXCLUDED_ATTRS
    assert "ELECTRIC_QA_ANSWER_MEMORY" in tm.LEARN_ATTRS
    assert "ELECTRIC_QA_ANSWER_MEMORY" not in tm.STACK_ATTRS
    assert len(tm.EXCLUDED) == 6 and len(tm.ALL_ATTRS) == 17
    assert any(l.startswith("WIDENS") and "ELECTRIC_QA_ANSWER_MEMORY" in l
               for l in tm.describe_learn()), tm.describe_learn()
    assert tm.DEPENDS_ON["ELECTRIC_QA_ANSWER_MEMORY"][0] == "ELECTRIC_QA_STORE"


def test_inert_without_the_store_and_says_so():
    o = _organ()
    o.ELECTRIC_QA_STORE = False
    r = o.learn_qa(*LOOSE, provenance=dict(CONV))
    assert not r.get("stored"), "it kept something in a store that is switched off"
    assert any("answer-memory" in line or "answer memory" in line
               for line in tm.unmet(tm.state(o))), tm.unmet(tm.state(o))


def test_serve_wires_it_before_the_mode_tables_so_the_mode_can_only_add():
    """Order is load-bearing in that file: an individual assignment placed after `enable_learn`
    takes the mode's own widening back off, which is how `--electric-learn` once ran as teach mode
    plus one. This one is wired with the other QA flags, above both."""
    serve = (ROOT / "tools" / "serve.py").read_text(encoding="utf-8")
    at = serve.index("ELECTRIC_QA_ANSWER_MEMORY = bool(args.electric_qa_answer_memory)")
    assert at < serve.index("electric_teach_mode.enable_learn(agent.language)"), \
        "wired after the mode table: the flag would be switched back off"
    assert "--electric-qa-answer-memory" in serve
