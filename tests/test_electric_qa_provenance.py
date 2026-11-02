"""ELECTRIC_QA_PROVENANCE: a pair's provenance governs the PAIR, not only its storage.

The audit (`tools/book_qa_store_audit.py`) found the book QA path inert on real novels --
one pair in 2,687 question lines, and a false one -- and sound everywhere else: the store
keeps what it is given, survives a restart, and answers by exact key. What it found UNSAFE
was the order of two operations:

  (1) `learn_qa` casts its vote -- which word asks, which role it asks about, what kind of
      thing answers it -- BEFORE `_qa_keep` decides the pair is not an answer. So the rule
      "a question cannot answer a question" protected his memories and corrupted his
      grammar in the same call. Measured: the refused pair taught an organ that `what`
      asks role 5 and is answered by `whose`, and `qa_pairs_seen` counted a pair the store
      holds zero of.
  (2) A stored pair is reachable only by a typed `?`. Asked without the mark, he answered
      10/10 from recall and 0/10 with the line the book printed, while the provenance-tagged
      answer sat unused in the store.

Both are fixed behind one flag, and the tests below are the ones that matter: that a
refused pair teaches NOTHING, that an admissible pair loses NOTHING, and that the second
route opens only on evidence -- an exact key that is a marked book question, and a word he
learned asks from an admissible pair.
"""
import inspect
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, ".")

import organs.neural_language as nl                       # noqa: E402
from connectome.engine import HybridEngine                # noqa: E402
from connectome.substrate import build_core_graph         # noqa: E402
from organs.tokenizer import TokenizerOrgan               # noqa: E402

# Ten lines, four of them printed as questions, and every one of the four a different
# case. This is a STIMULUS, not a passage: the sentences are shaped to make the arithmetic
# pass or fail on purpose.
BOOK = """who carries droso?
parent carries droso
what bit the latch?
the mouse bit the latch
might a mere warmint ask what property?
might a mere warmint ask whose property?
who fed droso?
parent? fed droso
"who shut the door?"
molly shut the door
who shows droso?
parent shows droso
"""
# Two admissible `who` pairs, and that is not decoration: `is_interrogative` needs
# INTERROGATIVE_MIN_VOTES = 2, and the evidenced lookup route is built on it. With one
# admissible pair the flag would remove a corrupt vote AND the evidence that unlocks the
# answer, which is the interaction `test_the_two_halves...` pins.


def _organ(store=False, marks=False, prov=False, book=None, tmp=None):
    o = nl.NeuralLanguage(HybridEngine(graph=build_core_graph()), TokenizerOrgan(),
                          state_path=None)
    o.persist = False
    o.cortex.MIN_HEAR_INTERVAL_S = 0.0     # a unit test is not an afternoon
    o.EXPOSURE_MIN_REAL_S = 0.0
    o.exposure_speed_s = 0.0
    o.exposure_enabled = True
    o.social_drive = 1.0                   # attends every line: nothing is skipped
    o.ELECTRIC_QA_STORE = bool(store)
    o.ELECTRIC_ASK_MARKS = bool(marks)
    o.ELECTRIC_QA_PROVENANCE = bool(prov)
    if book and tmp is not None:
        p = tmp / "stimulus.txt"
        p.write_text(BOOK, encoding="utf-8")
        o.set_books_dir(tmp)
    return o


def _read(o, lines=12):
    for _ in range(lines):
        o.expose_tick(world_dt=5.0)
    return o


def _grammar(o):
    """Everything the vote writes. Compared as a whole, because the defect is one line
    of it and a test that looks only at the store cannot see the corruption."""
    return {"roles": {w: dict(v) for w, v in o.question_roles.items()},
            "answer_types": {w: dict(v) for w, v in o.answer_types.items()},
            "interrogatives": sorted(o.interrogatives),
            "pairs_seen": o.qa_pairs_seen,
            "store": sorted(o.qa_store)}


PAIR = (["might", "a", "mere", "warmint", "ask", "what", "property"],
        ["might", "a", "mere", "warmint", "ask", "whose", "property"])
PROV_QQ = {"book": "stimulus.txt", "line": 4, "mark": 6, "tokens": 7,
           "answer_is_question": True, "answer_line": 5}
PROV_OK = {"book": "stimulus.txt", "line": 0, "mark": 2, "tokens": 3,
           "answer_is_question": False, "answer_line": 1}


# ------------------------------------------------------- one rule, used in both places
def test_the_admission_test_is_one_function_not_two_copies():
    o = _organ()
    assert o._qa_admissible(None) == (False, "no provenance")
    assert o._qa_admissible({"answer_is_question": True})[0] is False
    ok, why = o._qa_admissible(PROV_OK)
    assert ok and why == ""


def test_the_store_consults_that_same_function():
    """A call-site pin. Two copies of a rule drift; the day `_qa_keep` grows its own
    check again, this fails instead of silently re-opening the vote leak."""
    src = inspect.getsource(nl.NeuralLanguage._qa_keep)
    assert "_qa_admissible" in src, "the store stopped using the shared admission test"
    assert "answer_is_question" not in src, (
        "_qa_keep re-implemented the rule it is supposed to inherit")


# --------------------------------------------- (1) the defect: the vote runs first
def test_a_refused_pair_teaches_everything_it_should_not_with_the_flag_off():
    """The audited behaviour, pinned so the fix is measured against a fact and not a
    memory of one. The store keeps nothing; the grammar keeps it all."""
    o = _organ(store=True)
    r = o.learn_qa(*PAIR, provenance=PROV_QQ)
    assert r["learned"] is True
    assert r["role"] == 5 and r["interrogative"] == "what"
    assert o.qa_store == {}
    assert o.qa_pairs_seen == 1
    assert o.question_roles["what"] == {"5": 1}
    assert o.answer_types["what"] == {"whose": 1}
    assert "what" in o.interrogatives


def test_a_refused_pair_teaches_nothing_under_the_flag():
    o = _organ(store=True, prov=True)
    r = o.learn_qa(*PAIR, provenance=PROV_QQ)
    assert r["learned"] is False and r["refused_by_provenance"] is True
    assert "not an answer" in r["reason"]
    assert o.qa_store == {}
    assert o.qa_pairs_seen == 0, "the metric still counts a pair that was refused"
    assert o.question_roles == {}
    assert o.answer_types == {}
    assert o.interrogatives == set()


def test_a_pair_with_no_provenance_teaches_nothing_under_the_flag():
    """`learn_qa` has always refused to STORE an unattributed pair. Under the flag it
    also refuses to LEARN from one: a sentence that happens to be shaped like an answer
    is not evidence about which word asks."""
    o = _organ(store=True, prov=True)
    r = o.learn_qa(["who", "feeds", "droso"], ["parent", "feeds", "droso"])
    assert r["learned"] is False and r["refused_by_provenance"] is True
    assert o.question_roles == {} and o.interrogatives == set()


def test_an_admissible_pair_still_votes_and_still_stores_under_the_flag():
    """The other direction, and the one that could quietly over-refuse: a real pair
    must lose nothing."""
    o = _organ(store=True, prov=True)
    r = o.learn_qa(["who", "carries", "droso"], ["parent", "carries", "droso"],
                   provenance=PROV_OK)
    assert r["learned"] is True and r["role"] == 0
    assert r["stored"] == "who carries droso"
    assert o.qa_pairs_seen == 1
    assert o.question_roles["who"] == {"0": 1}
    assert list(o.qa_store) == ["who carries droso"]


# ------------------------------------------------- the pair, read from a real book file
def test_reading_the_stimulus_book_marks_off_store_on(tmp_path):
    """What today's house does with the stimulus: six pairs attempted, five voted, three
    kept. The gap between five and three IS the defect -- two pairs the organ itself
    declares are not answers still taught it which words ask."""
    o = _read(_organ(store=True, book=True, tmp=tmp_path))
    g = _grammar(o)
    assert g["store"] == ["what bit the latch", "who carries droso",
                          "who shows droso"]
    assert g["pairs_seen"] == 5
    assert g["roles"]["what"] == {"1": 1, "5": 1}, "role 5 is the refused pair's vote"
    assert g["roles"]["who"] == {"0": 3}, "one of the three is the refused pair's"
    assert g["answer_types"]["what"] == {"mouse": 1, "whose": 1}


def test_provenance_costs_no_memory_and_removes_exactly_the_refused_vote(tmp_path):
    """The comparison that has to hold: same book, same lines, same store -- and a
    grammar that no longer contains the pair the store threw away."""
    off = _grammar(_read(_organ(store=True, marks=True, book=True, tmp=tmp_path)))
    on = _grammar(_read(_organ(store=True, marks=True, prov=True, book=True,
                               tmp=tmp_path)))
    assert on["store"] == off["store"], "the flag must not lose a single pair"
    assert (off["pairs_seen"], on["pairs_seen"]) == (5, 3)
    assert off["roles"]["what"] == {"1": 1, "5": 1}
    assert on["roles"]["what"] == {"1": 1}, "the refused vote survived"
    assert on["answer_types"].get("what", {}) == {"mouse": 1}
    assert off["answer_types"]["what"] == {"mouse": 1, "whose": 1}
    assert on["roles"]["who"] == {"0": 2}, "the refused interior-mark pair voted too"
    assert off["roles"]["who"] == {"0": 3}


def test_an_answer_line_with_an_interior_mark_is_refused_in_both_arms(tmp_path):
    """`parent? fed droso` ends in a WORD, so `_book_is_q` calls it a statement. The pair
    is still refused, with ELECTRIC_ASK_MARKS off as much as on, because the mark
    POSITIONS are built for every book regardless of the display flag -- the store's
    safety was deliberately made independent of it.

    I expected the opposite when I wrote this test, and the expectation was the bug in my
    reasoning: it is the record of why the audit's DELTA stored_pairs = 0 is a fact about
    the mechanism, not about the sample."""
    for marks in (False, True):
        o = _read(_organ(store=True, marks=marks, book=True, tmp=tmp_path))
        assert "who fed droso" not in o.qa_store, marks
        assert o.qa_pairs_seen == 5, marks     # voted anyway: that is defect (1)
    blind = _read(_organ(store=True, marks=False, book=True, tmp=tmp_path))
    assert blind.learn_qa(["who", "fed", "droso"], ["parent", "fed", "droso"],
                          provenance={"book": "b", "line": 0,
                                      "answer_is_question": True})["learned"] is True


def test_the_two_halves_of_the_flag_do_not_fight(tmp_path):
    """The lookup route is gated on `is_interrogative`, which needs two votes. The vote
    gate REMOVES votes. So a word whose second vote came from a refused pair would lose
    its answer as well as its corruption -- and that interaction is real here, not
    hypothetical: `what` has exactly that shape in this stimulus."""
    o = _read(_organ(store=True, prov=True, book=True, tmp=tmp_path))
    assert o.qa_pairs_seen == 3
    assert o.question_roles["who"] == {"0": 2}, "two admissible votes"
    assert o.question_roles["what"] == {"1": 1}, "one admissible, one refused"
    assert o.is_interrogative("who") and not o.is_interrogative("what")
    assert o._qa_store_answer("who carries droso") is not None
    assert o._qa_store_answer("what bit the latch") is None, \
        "the evidenced route stays shut on a word the flag demoted"
    # ...and the typed route is untouched by any of it.
    assert o._qa_store_answer("what bit the latch?") is not None


def test_a_quoted_ask_is_invisible_to_acquisition_in_both_arms(tmp_path):
    """`"who shut the door?"` ends in a QUOTE. The channel sees a mark on the last token;
    `_book_is_q` does not, and the call site gates on `_book_is_q`. So the pair is never
    attempted -- measured as DELTA stored_pairs = 0 in the audit, and pinned here so that
    claim is a fact in the repo rather than a sentence in a report."""
    blind = _read(_organ(store=True, marks=False, book=True, tmp=tmp_path))
    sees = _read(_organ(store=True, marks=True, book=True, tmp=tmp_path))
    assert "who shut the door" not in blind.qa_store
    assert "who shut the door" not in sees.qa_store
    # The channel's own count says this line IS an ask; acquisition never asks it.
    assert nl.question_mark_positions('"who shut the door?"') == [3]


# ---------------------------------------------------------------- (2) the lookup route
def test_an_unmarked_ask_cannot_reach_the_store_by_default(tmp_path):
    o = _read(_organ(store=True, book=True, tmp=tmp_path))
    assert o._qa_store_answer("who carries droso") is None
    got = o._qa_store_answer("who carries droso?")
    assert got is not None and got["source"] == "electric_qa_store"
    assert got["ask_evidence"] == "typed"


def test_an_unmarked_ask_reaches_the_store_under_the_flag(tmp_path):
    o = _read(_organ(store=True, prov=True, book=True, tmp=tmp_path))
    got = o._qa_store_answer("who carries droso")
    assert got is not None, "the provenance-tagged answer is still unreachable"
    assert got["utterance"] == "parent carries droso"
    assert got["ask_evidence"] == "learned"
    assert got["provenance"]["book"] == "stimulus.txt"


def test_the_evidence_is_a_learned_word_not_a_punctuation_guess(tmp_path):
    """The gate is `is_interrogative` on the word THIS pair teaches. Strip the votes and
    the route closes again -- an unmarked string is never enough on its own."""
    o = _read(_organ(store=True, prov=True, book=True, tmp=tmp_path))
    assert o._qa_store_answer("who carries droso") is not None
    o.question_roles = {}
    o.interrogatives = set()
    assert o._qa_store_answer("who carries droso") is None
    assert o._qa_store_answer("who carries droso?") is not None, \
        "the typed route must stay open: this flag only ever adds evidence"


def test_a_near_miss_ask_gets_nothing_even_under_the_flag(tmp_path):
    """Exact key or nothing. The flag widens WHICH ASKS may look, never WHAT COUNTS as
    a match -- if it widened the match it would be retrieval, and retrieval is the path
    this whole exercise exists to keep out of the asking business."""
    o = _read(_organ(store=True, prov=True, book=True, tmp=tmp_path))
    for ask in ("who carries the droso", "who carried droso", "parent carries droso",
                "who carries droso tomorrow"):
        assert o._qa_store_answer(ask) is None, ask


def test_the_store_still_answers_after_a_restart_under_the_flag(tmp_path):
    """Persistence is the claim the task asked for, measured through the flag's own
    route: save, reload, ask without a mark, get the line the book printed."""
    sp = Path(str(tmp_path)) / "state.json"
    o = _read(_organ(store=True, prov=True, book=True, tmp=tmp_path))
    o.state_path = sp
    o.persist = True
    assert o.save_state(force=True)["saved"] is True
    o2 = _organ(store=True, prov=True)
    o2.state_path = sp
    o2.load_state()
    assert sorted(o2.qa_store) == sorted(o.qa_store)
    got = o2._qa_store_answer("who carries droso")
    assert got is not None and got["utterance"] == "parent carries droso"
    assert json.dumps(got["provenance"])


# ---------------------------------------------------------------- ordering, untouched
def test_the_answer_ordering_is_untouched_and_the_grader_is_still_blind():
    """The store is consulted after the taught path and before the absence licence, and
    `_absence_licence` still binds the question against the inventory on DEFAULTS -- the
    guarded grader contract. Pinned at the call sites because a reordering here would be
    invisible to every behavioural test above."""
    src = inspect.getsource(nl.NeuralLanguage.answer)
    i_taught = src.index("if self.ELECTRIC_ANSWER:")
    i_store = src.index("if self.ELECTRIC_QA_STORE and self.qa_store:")
    i_abs = src.index("abs_lic = self._absence_licence(text)")
    assert i_taught < i_store < i_abs
    grad = inspect.getsource(nl._absence_licence)
    assert "_electric_bind(question, inventory)" in grad, \
        "the guarded grader started receiving flags"


def test_the_flag_defaults_off_and_the_class_is_the_only_place_it_is_set():
    """A new write-and-read permission on a path the graded batteries touch. Off by
    default is what makes the audit's numbers still true of the deployed house."""
    assert nl.NeuralLanguage.ELECTRIC_QA_PROVENANCE is False
    o = _organ()
    assert o.ELECTRIC_QA_PROVENANCE is False
    assert o.learn_qa(["who", "feeds", "droso"], ["parent", "feeds", "droso"],
                      provenance=PROV_QQ)["learned"] is True
