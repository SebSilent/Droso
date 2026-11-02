"""ELECTRIC_QA_ELICIT: a PERSON can be a book.

The QA store has so far only ever held lines he was READ. That makes it useless in the one
place it was built for: someone telling him something. This flag pairs a user's marked ask
with the very next thing that user said, stores the pair with provenance, and lets him answer
it later with or without the question mark.

What these tests are mostly about is how little of that is allowed to be a guess. The book
path's whole safety is ADJACENCY, and the audit of it (tools/book_qa_store_audit.py) measured
the cost of loosening adjacency rather than paying it: pair a question with any line he holds
as a statement and you get 175 pairs, 73 of them with the answer BEFORE the question, and the
ones that survive the arithmetic teach inverted roles. So the conversation rule is that same
rule with one substitution -- the next LINE becomes the next UTTERANCE BY THE SAME SPEAKER --
and every route that opens has to name the evidence that opened it.
"""
import inspect
import sys
from pathlib import Path

sys.path.insert(0, ".")

import organs.neural_language as nl                       # noqa: E402
from connectome.engine import HybridEngine                # noqa: E402
from connectome.substrate import build_core_graph         # noqa: E402
from organs.tokenizer import TokenizerOrgan               # noqa: E402

ASK = "who carries droso?"
ANSWER = "parent carries droso"
KEY = "who carries droso"

# A pair whose ANSWER is also a tell the frame extractor recognises, for the test that says
# the same sentence becomes two memories at once.
HOOK_ASK = "who is on the hook?"
HOOK_ANSWER = "the scarf is on the hook"

# The pair the live house answered with the question's own text, kept here as the case.
BELL_ASK = "what rings the bell?"
BELL_ANSWER = "the copper bell rings"

# The three tells the guarded scarf ask refuses on, from tests/test_absence_inventory.py.
SCARF_TELLS = ["the coat is wet", "the coat is on the hook", "the scarf is wet"]
SCARF_ASK = "where did i say the scarf is?"

# A book pair, for proving this flag does not widen the book route.
BOOK_PROV = {"book": "stimulus.txt", "line": 0, "mark": 2, "tokens": 3,
             "answer_is_question": False, "answer_line": 1}


def _organ(elicit=False, store=True, teach=True, answer=True, prov=False,
           absence=False, state_path=None):
    o = nl.NeuralLanguage(HybridEngine(graph=build_core_graph()), TokenizerOrgan(),
                          state_path=state_path)
    o.persist = state_path is not None
    o.cortex.MIN_HEAR_INTERVAL_S = 0.0     # a unit test is not an afternoon
    o.ELECTRIC_QA_STORE = bool(store)
    o.ELECTRIC_TEACH = bool(teach)
    o.ELECTRIC_ANSWER = bool(answer)
    o.ELECTRIC_QA_PROVENANCE = bool(prov)
    o.ELECTRIC_QA_ELICIT = bool(elicit)
    o.ABSENCE_INVENTORY = bool(absence)
    return o


def _say(o, text, speaker="you"):
    r = o.respond(text, speaker=speaker) or {}
    return {"spoken": bool(r.get("spoken")),
            "said": str(r.get("utterance") or r.get("response") or "").strip(),
            "src": str(r.get("source") or ""),
            "evidence": str(r.get("ask_evidence") or ""),
            "raw": r}


def _taught(o, ask=ASK, ans=ANSWER):
    """Ask, then answer, the way a person does it."""
    o.respond(ask, speaker="you")
    o.respond(ans, speaker="you")
    return o


def _routed(o):
    """Replace `answer` with a recorder, so a routing claim is measured as routing and not
    inferred from what came out the other end."""
    seen, real = [], o.answer

    def spy(question, speaker="you"):
        seen.append(question)
        return real(question, speaker=speaker)

    o.answer = spy
    return seen


# ------------------------------------------------------------------ write side

def test_an_ask_and_the_next_thing_said_become_a_stored_pair():
    o = _organ(elicit=True)
    _taught(o)
    rec = o.qa_store.get(KEY)
    assert rec is not None, sorted(o.qa_store)
    assert rec["a"] == ANSWER.split()
    assert rec["q"] == KEY.split(), "the `?` is not part of the key"
    p = rec["prov"]
    assert p["source"] == "conversation" and p["speaker"] == "you"
    assert p["marked"] is True, "the mark is the read side's whole licence"
    assert p["answer_is_question"] is False


def test_the_flag_off_pairs_nothing_at_all():
    """Off is the old path, not a quieter new one: no pair, no pending, no store write."""
    o = _organ(elicit=False)
    _taught(o)
    assert o.qa_store == {}
    assert o._qa_pending is None
    assert o.qa_pairs_seen == 0


def test_an_unmarked_ask_is_not_an_ask():
    """Without the `?` nothing separates an ask from a remark, and a stored answer carries
    this person's name. The mark is not decoration, it is the evidence."""
    o = _organ(elicit=True)
    o.respond(KEY, speaker="you")
    o.respond(ANSWER, speaker="you")
    assert o.qa_store == {}
    assert o.qa_pairs_seen == 0, "an unremarked sentence must not teach grammar either"


def test_adjacency_is_the_very_next_utterance_and_nothing_older():
    """A pending ask that survived a turn would pair a question with something the person
    said three sentences later -- the false adjacency the audit measured in the corpus."""
    o = _organ(elicit=True)
    o.respond(ASK, speaker="you")
    o.respond("the kettle whistles twice", speaker="you")   # not an answer
    assert o._qa_pending is None, "the ask should have been spent"
    o.respond(ANSWER, speaker="you")                        # too late
    assert o.qa_store == {}


def test_a_second_ask_spends_the_first():
    o = _organ(elicit=True)
    o.respond("where is the moon?", speaker="you")
    o.respond(ASK, speaker="you")
    o.respond(ANSWER, speaker="you")
    assert sorted(o.qa_store) == [KEY]


def test_only_a_person_teaches():
    """Same permission boundary as `_taught_says`: what the house hears from a stranger is
    not something anyone promised him the answer to."""
    o = _organ(elicit=True)
    o.respond(ASK, speaker="stranger")
    o.respond(ANSWER, speaker="stranger")
    assert o.qa_store == {} and o._qa_pending is None


def test_a_statement_that_is_not_an_answer_teaches_no_grammar():
    o = _organ(elicit=True)
    o.respond(ASK, speaker="you")
    before = (o.qa_pairs_seen, {w: dict(v) for w, v in o.question_roles.items()})
    o.respond("the kettle whistles twice", speaker="you")
    assert (o.qa_pairs_seen, {w: dict(v) for w, v in o.question_roles.items()}) == before


def test_elicit_without_the_store_votes_and_forgets():
    """The two flags stay orthogonal: eliciting is where pairs come from, storing is
    whether they are kept. Nothing elicited is answerable without the store."""
    o = _organ(elicit=True, store=False)
    _taught(o)
    assert o.qa_store == {}
    assert o.qa_pairs_seen == 1 and o.role_for("who") == 0
    assert _say(o, ASK)["src"] != "electric_qa_store"


# ------------------------------------------------------------------- read side

def test_an_elicited_pair_is_answered_when_the_mark_is_typed():
    o = _organ(elicit=True)
    _taught(o)
    r = _say(o, ASK)
    assert r["spoken"] and r["said"] == ANSWER
    assert r["src"] == "electric_qa_store" and r["evidence"] == "typed"


def test_an_elicited_pair_is_answered_when_the_mark_is_missing():
    o = _organ(elicit=True)
    _taught(o)
    r = _say(o, KEY)
    assert r["spoken"] and r["said"] == ANSWER
    assert r["src"] == "electric_qa_store"
    assert r["evidence"] == "person_marked"


def test_the_unmarked_route_is_the_record_not_a_learned_question_word():
    """This is the point of the flag. `is_interrogative` needs two role votes and a person
    who teaches one pair gives one, so the LEARNED route cannot reach this memory. The
    record can, because a person typed the `?` at him once already."""
    o = _organ(elicit=True)
    _taught(o)
    assert o.role_for("who") == 0
    assert not o.is_interrogative("who"), "the stimulus must stay a one-vote word"
    assert o._qa_store_answer(KEY)["ask_evidence"] == "person_marked"
    off = _organ(elicit=False)
    off.learn_qa(KEY.split(), ANSWER.split(), provenance=BOOK_PROV)
    assert off._qa_store_answer(KEY) is None, "without the flag the record is not evidence"


def test_this_flag_does_not_widen_the_book_route():
    """A book pair stays behind ELECTRIC_QA_PROVENANCE's own evidence. If eliciting opened
    it too, the flag measured in the audit would no longer be the flag that ships."""
    o = _organ(elicit=True, prov=False)
    o.learn_qa(["where", "is", "the", "kettle"], ["the", "kettle", "is", "warm"],
               provenance=BOOK_PROV)
    assert sorted(o.qa_store) == ["where is the kettle"]
    assert not o.is_interrogative("where")
    assert o._qa_store_answer("where is the kettle") is None
    assert o._qa_store_answer("where is the kettle?")["ask_evidence"] == "typed"


def test_a_book_pair_answers_unmarked_only_through_provenance():
    """The two unmarked routes are separate and each names itself: `learned` for a book
    pair whose word he earned, `person_marked` only for a pair a person typed."""
    o = _organ(elicit=True, prov=True)
    o.learn_qa(["where", "is", "the", "kettle"], ["the", "kettle", "is", "warm"],
               provenance=BOOK_PROV)
    o.learn_qa(["where", "is", "the", "kettle"], ["the", "kettle", "is", "warm"],
               provenance=BOOK_PROV)      # two votes, so `where` is learned
    assert o.is_interrogative("where")
    got = o._qa_store_answer("where is the kettle")
    assert got["ask_evidence"] == "learned"


def test_a_near_miss_ask_gets_nothing_even_under_the_flag():
    """Exact key or nothing. Adding or changing one word is not a question he was answered."""
    o = _organ(elicit=True)
    _taught(o)
    for ask in ["who carries the droso", "who carried droso", "who carries droso now",
                "who carries droso and when", "who carries"]:
        assert o._qa_store_answer(ask) is None, ask


def test_the_pair_survives_a_restart_and_is_still_answerable_unmarked(tmp_path):
    """The store persists with its provenance; the PENDING ask does not, and must not: a
    question left hanging across a boot is not evidence that whatever is typed next is its
    answer."""
    sp = Path(str(tmp_path)) / "state.json"
    o = _organ(elicit=True)
    _taught(o)
    o.respond("what bites the latch?", speaker="you")      # left hanging on purpose
    assert o._qa_pending is not None
    o.state_path = sp
    o.persist = True
    assert o.save_state(force=True)["saved"] is True
    b = _organ(elicit=True)
    b.state_path = sp
    b.load_state()
    assert sorted(b.qa_store) == [KEY]
    assert b.qa_store[KEY]["prov"]["source"] == "conversation"
    assert b._qa_pending is None, "a pending ask must not come back from a file"
    assert _say(b, KEY)["said"] == ANSWER


# ---------------------------------------------------------------- routing

def test_the_route_opens_only_for_a_key_he_holds():
    """The routing widening is keyed on the RECORD, not on the punctuation: an ask with no
    pair under it keeps the path it always took, so this cannot hand the recall path a new
    way to speak. Measured as routing, by watching which utterances reach `answer`."""
    o = _organ(elicit=True)
    seen = _routed(o)
    _taught(o)                                  # ask, then answer: neither is routed
    assert seen == [], "a statement must not be routed to answering"
    o.respond(KEY, speaker="you")               # unmarked, pair held -> routed
    o.respond(ASK, speaker="you")               # marked, pair held   -> routed
    o.respond("what bites the latch?", speaker="you")   # marked, no pair -> NOT routed
    assert seen == [KEY, ASK], seen
    assert "what bites the latch?" not in seen


def test_the_route_is_inert_when_the_flag_is_off():
    o = _organ(elicit=False)
    seen = _routed(o)
    o.learn_qa(KEY.split(), ANSWER.split(), provenance=BOOK_PROV)
    o.respond(KEY, speaker="you")
    assert seen == []


def test_both_memories_exist_and_the_store_is_what_answers():
    """The same sentence becomes a taught fact AND a paired answer, and the audited ordering
    between them holds: the taught path is consulted first and cannot bind this ask, because
    the ask has no subject in it -- that is what it is asking for."""
    o = _organ(elicit=True)
    _taught(o, HOOK_ASK, HOOK_ANSWER)
    assert o._taught_says["scarf"]["place"] == HOOK_ANSWER
    assert sorted(o.qa_store) == ["who is on the hook"]
    r = _say(o, HOOK_ASK)
    assert r["src"] == "electric_qa_store" and r["said"] == HOOK_ANSWER


def test_the_guarded_scarf_ask_still_refuses_with_the_flag_on():
    """ABORT B4. Nothing here may license an answer, and the guard's own ask keeps refusing
    when no person ever paired it. Reached through `answer` because that is where the guard
    lives; the route above does not, and must not, take it over."""
    o = _organ(elicit=True, absence=True)
    for t in SCARF_TELLS:
        o.hear(t, speaker="you")
    _taught(o)
    r = o.answer(SCARF_ASK) or {}
    assert r.get("licensed_refusal") is True, r
    assert r.get("source") != "electric_qa_store"
    assert not r.get("answered")


def test_the_grader_contract_and_the_answer_ordering_are_untouched():
    src = inspect.getsource(nl.NeuralLanguage.answer)
    i_taught = src.index("if self.ELECTRIC_ANSWER:")
    i_store = src.index("if self.ELECTRIC_QA_STORE and self.qa_store:")
    i_abs = src.index("abs_lic = self._absence_licence(text)")
    assert i_taught < i_store < i_abs
    grad = inspect.getsource(nl._absence_licence)
    assert "_electric_bind(question, inventory)" in grad, \
        "the guarded grader started receiving flags"
    for forbidden in ("ELECTRIC_QA_ELICIT", "ELECTRIC_QA_STORE", "ELECTRIC_ANSWER",
                      "qa_store"):
        assert forbidden not in grad, f"the grader now reads {forbidden}"
    # The call site passes the ask and nothing else. Pinned as text because a widened
    # guard would still refuse in every behavioural test above -- it would just refuse
    # for a different set of reasons than the ones that were audited.
    assert "abs_lic = self._absence_licence(text)" in src
    assert "self._absence_licence(text, " not in src


def test_a_marked_answer_is_never_taken_as_an_answer():
    """By construction the answer line of an elicited pair cannot be a question: a marked
    utterance always becomes the NEXT pending ask, so `answer_is_question` is never True
    here. The shared admission test still refuses such a pair if one is handed to it."""
    o = _organ(elicit=True, prov=True)
    o.respond(ASK, speaker="you")
    o.respond("might a mere warmint ask what property?", speaker="you")
    assert o.qa_store == {} and o.qa_pairs_seen == 0
    assert o._qa_pending["tokens"] == ["might", "a", "mere", "warmint", "ask",
                                      "what", "property"]
    # A pair that PASSES the arithmetic and is labelled as a question answering a question:
    # the shared admission test, not the shape gate, is what has to stop it.
    r = o.learn_qa(["who", "feeds", "droso"], ["parent", "feeds", "droso"],
                   provenance={"source": "conversation", "marked": True,
                               "answer_is_question": True})
    assert r.get("refused_by_provenance") is True and o.qa_store == {}
    assert o.qa_pairs_seen == 0, "a refused pair must not teach grammar either"


def test_a_marked_ask_is_not_recorded_as_a_tell():
    """The defect the live house found, and the one line that closes it. `_absence_frame`
    reads a sentence by position, so `what rings the bell?` used to land in the tell
    inventory under subject "rings" -- and the taught path, which runs BEFORE the store,
    then answered that ask with the ask's own text. Off, that is still what happens: the
    fix is gated on this flag, because this flag is what routes the ask there."""
    off = _organ(elicit=False)
    off.respond(BELL_ASK, speaker="you")
    assert "rings" in off._taught_says, \
        "the pre-existing write changed under a flag that should not have changed it"
    on = _organ(elicit=True)
    on.respond(BELL_ASK, speaker="you")
    assert "rings" not in on._taught_says, "a question was noted as a tell"


def test_an_unmarked_ask_is_still_recorded_as_a_tell():
    """Scope limit, stated rather than hidden. Without the `?` there is nothing in the
    sentence saying it was a question, and this flag does not invent one: it pairs what a
    person MARKED. The echo above is closed for marked asks only."""
    o = _organ(elicit=True)
    o.respond("who feeds the dog", speaker="you")
    assert "feeds" in o._taught_says


def test_an_ask_is_never_answered_with_its_own_text():
    o = _organ(elicit=True)
    _taught(o, BELL_ASK, BELL_ANSWER)
    for ask in (BELL_ASK, BELL_ASK.rstrip("?")):
        r = _say(o, ask)
        assert r["said"] != ask.rstrip("?"), f"echoed the question back: {r}"
        assert r["said"] == BELL_ANSWER and r["src"] == "electric_qa_store"


def test_the_flag_defaults_off_and_is_a_class_attribute():
    assert nl.NeuralLanguage.ELECTRIC_QA_ELICIT is False
    o = _organ()
    assert o.ELECTRIC_QA_ELICIT is False and o._qa_pending is None
