"""ELECTRIC_QA_STORE: the book questions he was READ an answer to become a memory.

`learn_qa` has always judged, per pair, whether the line under a question is that question
with its question-word replaced -- and then thrown the pair away, keeping only the role vote.
Audited in tools/book_qa_learn_audit.py: the corpus yields 165 accepted pairs, 164 of them from
the two books WRITTEN as Q/A, and the single pair the 16 real novels produce is Dickens printing
two rhetorical questions back to back. So these tests are mostly about what may NOT be stored,
and about the one thing that makes a store safe rather than a lookup table: an answer is only
ever the line that was actually read under the question, found by exact key.
"""
import sys
from pathlib import Path

sys.path.insert(0, ".")

import organs.neural_language as nl                       # noqa: E402
from connectome.engine import HybridEngine                # noqa: E402
from connectome.substrate import build_core_graph         # noqa: E402
from organs.tokenizer import TokenizerOrgan               # noqa: E402
from organs.higher_cortex import row_is_ask               # noqa: E402

PROV = {"book": "test.txt", "line": 0, "answer_line": 1,
        "answer_is_question": False, "mark": 3, "tokens": 3}
DICKENS = dict(PROV, line=4, answer_line=5, answer_is_question=True)


def _organ(qa_store=False, marks=False, admissible=False, state_path=None):
    o = nl.NeuralLanguage(HybridEngine(graph=build_core_graph()), TokenizerOrgan(),
                          state_path=state_path)
    o.persist = state_path is not None
    o.cortex.MIN_HEAR_INTERVAL_S = 0.0     # a unit test is not an afternoon
    o.ELECTRIC_QA_STORE = bool(qa_store)
    o.ELECTRIC_ASK_MARKS = bool(marks)
    o.ELECTRIC_ASK_ADMISSIBILITY = bool(admissible)
    return o


def _learn(o, q="who feeds droso", a="parent feeds droso", prov=PROV):
    return o.learn_qa(q.split(), a.split(), provenance=prov)


# ---------------------------------------------------------------- write side

def test_flag_off_stores_nothing_and_votes_exactly_as_before():
    """Off must be the old path, not a quieter version of a new one: the vote is what
    the house has always had, and the store must not be half-populated behind the flag."""
    o = _organ(qa_store=False)
    r = _learn(o)
    assert r["learned"] is True and "stored" not in r
    assert o.qa_store == {}
    assert o.role_for("who") == 0, "the vote still happens with the flag off"
    assert o.qa_pairs_seen == 1


def test_an_accepted_pair_is_kept_with_the_line_it_came_from():
    o = _organ(qa_store=True)
    r = _learn(o)
    assert r["stored"] == "who feeds droso"
    rec = o.qa_store["who feeds droso"]
    assert rec["a"] == ["parent", "feeds", "droso"]
    assert rec["filler"] == "parent" and rec["role"] == 0 and rec["word"] == "who"
    assert rec["prov"]["book"] == "test.txt" and rec["prov"]["line"] == 0


def test_no_provenance_no_memory():
    """A pair nobody can say where it came from is a sentence shaped like an answer.
    This is the whole difference between a memory and a guess."""
    o = _organ(qa_store=True)
    r = o.learn_qa(["who", "feeds", "droso"], ["parent", "feeds", "droso"])
    assert r["learned"] is True and not r.get("stored")
    assert o.qa_store == {}


def test_a_question_cannot_answer_a_question():
    """The Dickens case, measured: `Might a mere warmint ask what property?` followed by
    `Might a mere warmint ask whose property?` passes the arithmetic -- what/whose is one
    novel word, one missing role -- and is not an answer. It is the only pair the real
    novels yield, so a store that kept it would be a store of line-wrap artifacts."""
    o = _organ(qa_store=True)
    r = o.learn_qa(["might", "a", "mere", "warmint", "ask", "what", "property"],
                   ["might", "a", "mere", "warmint", "ask", "whose", "property"],
                   provenance=DICKENS)
    assert r["learned"] is True, "the vote still happens; it is the MEMORY that is refused"
    assert not r.get("stored") and o.qa_store == {}


def test_an_ambiguous_pair_is_never_stored():
    """Two roles missing or two new words: learn_qa refuses, and the refusal must not
    be a half-written record."""
    o = _organ(qa_store=True)
    r = o.learn_qa(["who", "feeds", "droso", "today"],
                   ["parent", "feeds", "droso", "quickly"], provenance=PROV)
    assert r["learned"] is False and o.qa_store == {}


def test_a_re_read_pair_does_not_overwrite_the_answer_it_already_had():
    """First wins, exactly as in `_taught_says`: if a later line could rewrite an answer,
    what he says would depend on reading ORDER, and a book he re-reads would change."""
    o = _organ(qa_store=True)
    _learn(o)
    r2 = _learn(o, a="stranger feeds droso")
    assert r2["learned"] is True and not r2.get("stored")
    assert o.qa_store["who feeds droso"]["a"] == ["parent", "feeds", "droso"]


# ------------------------------------------------------------------ read side

def test_an_ask_he_was_read_an_answer_to_is_answered_from_the_pair():
    o = _organ(qa_store=True)
    _learn(o)
    r = o.answer("who feeds droso?")
    assert r["answered"] is True
    assert r["response"] == "parent feeds droso"
    assert r["source"] == "electric_qa_store"
    assert r["provenance"]["book"] == "test.txt"


def test_an_ask_the_store_has_no_pair_for_is_answered_by_nothing_new():
    """The store must not be a retrieval wearing a key. `who feeds the mouse` shares two
    words with a stored pair and is not in it."""
    o = _organ(qa_store=True)
    _learn(o)
    r = o.answer("who feeds the mouse?")
    assert r.get("source") != "electric_qa_store"


def test_a_question_without_its_mark_is_not_answered_from_the_store():
    """The ask has to be an asking in the same sense the book's line was: the store keys
    questions, and a sentence typed without `?` is not evidence anyone wants an answer.
    It falls through to the paths that already exist."""
    o = _organ(qa_store=True)
    _learn(o)
    r = o.answer("who feeds droso")
    assert r.get("source") != "electric_qa_store"


def test_the_flag_off_house_cannot_reach_the_store_even_if_it_had_one():
    """A store left on disk by an earlier session must not answer with the flag off --
    the guard is the read, not only the write."""
    o = _organ(qa_store=False)
    o.qa_store = {"who feeds droso": {"q": ["who", "feeds", "droso"],
                                      "a": ["parent", "feeds", "droso"],
                                      "word": "who", "role": 0, "filler": "parent",
                                      "prov": PROV}}
    r = o.answer("who feeds droso?")
    assert r.get("source") != "electric_qa_store"


def test_the_two_normalizers_agree_or_the_store_answers_nothing():
    """The key is built from a BOOK LINE's tokens and looked up from a TYPED ASK. If the
    two normalizations disagree the store is silently dead -- it stores, it never hits,
    and every count of stored pairs still looks healthy."""
    assert nl.NeuralLanguage.qa_key("Who feeds  Droso?") == "who feeds droso"
    assert nl.NeuralLanguage.qa_key(["who", "feeds", "droso"]) == "who feeds droso"
    assert nl.NeuralLanguage.qa_key("it's the latch!") == "it s the latch"
    o = _organ(qa_store=True)
    _learn(o)
    assert o.answer("  WHO feeds DROSO ?  ")["response"] == "parent feeds droso"


def test_an_answer_is_never_the_question_it_was_keyed_by():
    """The leak this project just closed was a remembered question recited as a fact. A
    store keyed by questions must speak the ANSWER line and nothing else."""
    o = _organ(qa_store=True, marks=True, admissible=True)
    _learn(o)
    r = o.answer("who feeds droso?")
    assert r["response"] == "parent feeds droso"
    assert r["response"] != "who feeds droso"
    assert not row_is_ask({"tokens": r["response"].split(), "ask": False,
                           "ask_marks": []}), "the spoken line is not an asking"


# ------------------------------------------------------------------- restart

def test_the_store_survives_a_restart_and_still_answers(tmp_path):
    sp = tmp_path / "nl_state.json"
    o = _organ(qa_store=True, state_path=sp)
    _learn(o)
    assert o.save_state(force=True)["saved"]
    o2 = _organ(qa_store=True, state_path=sp)
    o2.load_state()
    assert o2.qa_store["who feeds droso"]["a"] == ["parent", "feeds", "droso"]
    assert o2.answer("who feeds droso?")["response"] == "parent feeds droso"


def test_a_restored_record_with_no_provenance_is_dropped_not_answered_from(tmp_path):
    """The file is on disk and can be old, edited or half-written. A record that cannot
    say where it came from is not a memory, and load must not resurrect one."""
    import json
    sp = tmp_path / "nl_state.json"
    o = _organ(qa_store=True, state_path=sp)
    _learn(o)
    assert o.save_state(force=True)["saved"]
    doc = json.loads(sp.read_text(encoding="utf-8"))
    doc["questions"]["qa_store"]["who pets droso"] = {
        "q": ["who", "pets", "droso"], "a": ["nobody", "pets", "droso"],
        "word": "who", "role": 0, "filler": "nobody", "prov": {}}
    sp.write_text(json.dumps(doc), encoding="utf-8")
    o2 = _organ(qa_store=True, state_path=sp)
    o2.load_state()
    assert "who pets droso" not in o2.qa_store
    assert "who feeds droso" in o2.qa_store, "a bad record must not void the good ones"


# ------------------------------------------------- the path, end to end, on a book

BOOK = """who feeds droso?
parent feeds droso.
who pets droso?
parent pets droso.
might a mere warmint ask what property?
might a mere warmint ask whose property?
what opens the file?
"""


def _reader(tmp_path, qa_store, marks=True, admissible=True, text=None, beats=20):
    (tmp_path / "book.txt").write_text(text if text is not None else BOOK,
                                       encoding="utf-8")
    o = _organ(qa_store=qa_store, marks=marks, admissible=admissible)
    o.books_dir = Path(tmp_path)
    o.EXPOSURE_MIN_REAL_S = 0.0
    o.exposure_speed_s = 0.0
    o.exposure_enabled = True
    o.social_drive = 1.0
    o._book_idx = 0
    for _ in range(beats):
        o.expose_tick(world_dt=5.0)
    return o


def test_an_answer_with_a_question_inside_it_is_not_stored(tmp_path):
    """`_book_is_q` is trailing-only: `parent? fed droso` does not end in `?`, so the old
    boolean calls it a statement. The admission guard reads the CHANNEL for that line, not
    the boolean -- otherwise a stored answer could be a question the book printed inside a
    sentence, which is the exact leak the marks work closed."""
    o = _reader(tmp_path, True, text="who fed droso?\nparent? fed droso\n", beats=8)
    assert o.qa_store == {}, "the pair passes the arithmetic and is still refused"
    clean = _reader(tmp_path, True, text="who fed droso?\nparent fed droso.\n", beats=8)
    assert "who fed droso" in clean.qa_store, "the same pair with a mark-free answer is kept"


def test_reading_a_q_a_book_builds_the_store_and_costs_no_rows(tmp_path):
    """The pair has to arrive from READING, not from a test calling learn_qa -- and it
    must not eat a row: the same lines are heard either way."""
    off = _reader(tmp_path, qa_store=False)
    on = _reader(tmp_path, qa_store=True)
    rows_off = [(tuple(m.get("tokens")), row_is_ask(m)) for m in off.cortex.binder.meta]
    rows_on = [(tuple(m.get("tokens")), row_is_ask(m)) for m in on.cortex.binder.meta]
    assert rows_off == rows_on, "the store renames nothing and drops nothing"
    assert off.qa_store == {}, "flag off: nothing is kept"
    assert set(on.qa_store) == {"who feeds droso", "who pets droso"}
    assert "might a mere warmint ask what property" not in on.qa_store


def test_what_he_says_after_reading_a_book_is_the_line_the_book_printed(tmp_path):
    on = _reader(tmp_path, qa_store=True)
    r = on.answer("who feeds droso?")
    assert r["source"] == "electric_qa_store"
    assert r["response"] == "parent feeds droso"
    assert r["provenance"]["book"] == "book.txt"
    assert r["provenance"]["line"] == 0
