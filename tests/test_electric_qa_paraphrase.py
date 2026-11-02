"""ELECTRIC_QA_PARAPHRASE: a pair a person taught answers when they ask it again in other
words.

`ELECTRIC_QA_ELICIT` keys a taught pair by the exact words that were typed, so the pair is
reachable only by those words. Measured, that is a feature with a demo and no use: taught
`who carries droso?` / `parent carries droso` and the person is answered the next time they
type it, and not when they type `who carries the droso`.

So this connects the elicited lookup to the two pieces of machinery the ELECTRIC read path
already runs for exactly this problem: `organs/stemming.py`, the project's ONE stemmer
("the same bug was found in three places"), and `normalize_ask_variants`, the ask normalizer
that turns a passive into the active key the matchers accept. Nothing new is invented here,
and nothing is widened:

  * a folded hit is only ever sought among records whose PROVENANCE already licenses an
    unmarked answer -- a pair a PERSON typed with a `?` at him (source=conversation,
    marked). A book pair is not a candidate, at any setting of any other flag;
  * the fold may only ever REFUSE. `stem()`'s documented policy is that under-folding
    refuses a question and over-folding gets believed, so the refusals are pinned here as
    loudly as the recoveries, and a future widening of the shared stemmer has to break
    these assertions on purpose;
  * two stored pairs that fold alike answer NOTHING. Ambiguity is not resolved by taking
    the first one;
  * the exact key is still tried first and its behaviour is byte-unchanged, so every
    measurement made before this flag measures the same thing after it.
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

# Phrasings of ASK, measured against the fold. Both lists are assertions, not examples:
# the first is what this flag claims to reach, the second is what it claims NOT to.
FOLDED_EQUIVALENTS = [
    "who carries the droso",       # an article the person did not type
    "who carry droso",             # the verb without its -s
    "who is carrying droso",       # a copula plus the -ing form
    "who does carry droso",        # do-support
    "who was carrying droso",      # past copula
]
FOLDED_REFUSALS = [
    "who carried droso",           # carri  vs carry  -- the shared stemmer does not bridge
    "who carries droso tomorrow",  # a content word nobody taught it
    "who droso carries",           # the same words in a different ORDER
    "who carries the cat",         # a different subject
    "who carries",                 # too little to be the same question
]

# The passive the ask normalizer reaches, and the tell that gives it the warrant to.
DOOR_ASK = "what opens the door?"
DOOR_ANS = "the frost opens the door"
DOOR_PASSIVE = "what was the door opened by"
DOOR_TELL = "the frost opens the door"

# A book pair, for the claim that this does not widen the book route.
BOOK_PROV = {"book": "stimulus.txt", "line": 0, "mark": 2, "tokens": 3,
             "answer_is_question": False, "answer_line": 1}

SCARF_TELLS = ["the coat is wet", "the coat is on the hook", "the scarf is wet"]
SCARF_ASK = "where did i say the scarf is?"


def _organ(elicit=True, paraphrase=False, store=True, teach=True, answer=True,
           prov=False, absence=False, state_path=None):
    o = nl.NeuralLanguage(HybridEngine(graph=build_core_graph()), TokenizerOrgan(),
                          state_path=state_path)
    o.persist = state_path is not None
    o.cortex.MIN_HEAR_INTERVAL_S = 0.0     # a unit test is not an afternoon
    o.ELECTRIC_QA_STORE = bool(store)
    o.ELECTRIC_TEACH = bool(teach)
    o.ELECTRIC_ANSWER = bool(answer)
    o.ELECTRIC_QA_ELICIT = bool(elicit)
    o.ELECTRIC_QA_PARAPHRASE = bool(paraphrase)
    o.ELECTRIC_QA_PROVENANCE = bool(prov)
    o.ABSENCE_INVENTORY = bool(absence)
    return o


def _say(o, text, speaker="you"):
    r = o.respond(text, speaker=speaker) or {}
    return {"spoken": bool(r.get("spoken")),
            "said": str(r.get("utterance") or r.get("response") or "").strip(),
            "src": str(r.get("source") or ""),
            "evidence": str(r.get("ask_evidence") or ""),
            "asked": str(r.get("asked") or ""),
            "raw": r}


def _taught(o, ask=ASK, ans=ANSWER):
    """Ask, then answer, the way a person does it."""
    o.respond(ask, speaker="you")
    o.respond(ans, speaker="you")
    return o


def _routed(o):
    """Replace `answer` with a recorder, so a routing claim is measured as routing."""
    seen, real = [], o.answer

    def spy(question, speaker="you"):
        seen.append(question)
        return real(question, speaker=speaker)

    o.answer = spy
    return seen


# ---------------------------------------------------------------- the fold

def test_the_fold_meets_the_phrasings_it_claims():
    o = _organ()
    want = o.qa_paraphrase_key(ASK)
    assert want == "who carry droso", want
    for a in FOLDED_EQUIVALENTS:
        assert o.qa_paraphrase_key(a) == want, (a, o.qa_paraphrase_key(a))


def test_the_fold_refuses_the_phrasings_it_does_not_claim():
    """The under-folds, pinned. `stem()`'s own docstring says under-folding refuses a
    question and over-folding gets believed, so these refusals are the safe half of the
    policy -- and they are here so that growing the shared stemmer later is a decision
    somebody makes on purpose, not something that arrives with a paraphrase."""
    o = _organ()
    want = o.qa_paraphrase_key(ASK)
    for a in FOLDED_REFUSALS:
        assert o.qa_paraphrase_key(a) != want, (a, o.qa_paraphrase_key(a))


def test_the_fold_is_the_shared_stemmer_and_not_a_fourth_copy():
    """`organs/stemming.py` exists because three lookups each grew their own stemmer. This
    is a fourth lookup, so it uses that one: both STATED folds are visible in the key, and
    the function is built on `stem()` rather than on a suffix strip of its own."""
    from organs.stemming import stem
    assert stem("broke") == "break" and stem("eggs") == "egg"
    o = _organ()
    assert o.qa_paraphrase_key("how many eggs broke") == "how many egg break"
    assert o.qa_paraphrase_key("how many egg broke") == "how many egg break"
    src = inspect.getsource(nl.NeuralLanguage.qa_paraphrase_key)
    assert "stem(" in src, "the paraphrase key grew its own morphology"


def test_the_fold_drops_only_the_words_the_normalizer_already_drops():
    """The removable set is `ASK_NORMALIZE_AUX` -- the copulas and do-support
    `normalize_ask_variants` already removes -- plus the three articles. Not a new list of
    English function words: `never`, `often`, `twice` stay, because a question that says
    `twice` is asking about a frequency and this file has no business deciding otherwise."""
    o = _organ()
    assert o.qa_paraphrase_key("what rings the bell twice") != o.qa_paraphrase_key(
        "what rings the bell")
    assert "the" not in o.qa_paraphrase_key("who carries the droso")
    assert "was" not in o.qa_paraphrase_key("who was carrying droso")
    assert nl.ASK_PARAPHRASE_DROP == (nl.ASK_NORMALIZE_AUX
                                      | frozenset({"the", "a", "an"}))


def test_an_ask_that_folds_to_nothing_matches_nothing():
    """A sentence made only of droppable words folds to the empty key. It must not be
    allowed to match a stored question that also folds to nothing -- that would be an
    answer issued on no evidence at all."""
    o = _organ(paraphrase=True)
    _taught(o)
    assert o.qa_paraphrase_key("is the?") == ""
    r = _say(o, "is the")
    assert r["src"] != "electric_qa_store", r
    assert o._qa_paraphrase_hit("is the") is None


# ---------------------------------------------------------------- recovery

def test_a_taught_pair_answers_a_paraphrase_with_the_words_it_was_given():
    o = _organ(paraphrase=True)
    _taught(o)
    for a in FOLDED_EQUIVALENTS:
        r = _say(o, a)
        assert r["src"] == "electric_qa_store", (a, r)
        assert r["said"] == ANSWER, (a, r)
        assert r["evidence"] == "person_paraphrase", (a, r)
        assert r["asked"] == KEY, (a, r)      # what it decided it was asked


def test_a_marked_paraphrase_is_evidenced_as_typed_and_folded():
    """The person typed a `?` at him right now, so this is not the record carrying the
    questionhood -- but these are still not the words anybody typed before. Two facts, so
    two words, and no claim that a mark was there when it was not."""
    o = _organ(paraphrase=True)
    _taught(o)
    r = _say(o, "who carries the droso?")
    assert r["src"] == "electric_qa_store" and r["said"] == ANSWER
    assert r["evidence"] == "typed_paraphrase", r


def test_the_flag_off_leaves_the_paraphrase_unanswered():
    o = _organ(paraphrase=False)
    _taught(o)
    for a in FOLDED_EQUIVALENTS:
        r = _say(o, a)
        assert r["src"] != "electric_qa_store", (a, r)
        assert r["said"] != ANSWER, (a, r)


def test_the_exact_key_is_still_tried_first_and_unchanged():
    """Ordering is the safety argument: an ask that matched before this flag matched is
    answered by the same code with the same evidence label, and the fold is never consulted
    for it."""
    o = _organ(paraphrase=True)
    _taught(o)
    assert _say(o, ASK)["evidence"] == "typed"
    assert _say(o, KEY)["evidence"] == "person_marked"
    hit = o._qa_paraphrase_hit(ASK)
    assert hit is None, "a folded hit was taken for an ask that is already in the store"


def test_the_answer_is_the_line_verbatim_and_not_a_rebuilt_sentence():
    """The store returns the LINE, not a regeneration of it. `_absence_frame` drops the
    locative preposition, so a rebuilt answer would have to invent `on`. The record is
    stored by hand so this measures the READ path and not whether the pair arithmetic happens
    to accept the same two sentences."""
    o = _organ(paraphrase=True)
    o.qa_store["where is the scarf"] = {
        "q": ["where", "is", "the", "scarf"],
        "a": ["the", "scarf", "is", "on", "the", "hook"],
        "word": "where", "role": 3, "filler": "on",
        "prov": {"source": "conversation", "speaker": "you", "turn": 1,
                 "marked": True, "answer_is_question": False}}
    assert o._taught_says == {}, "the taught path would answer this before the store did"
    r = _say(o, "where the scarf")
    assert r["src"] == "electric_qa_store", r
    assert r["said"] == "the scarf is on the hook", r
    assert r["evidence"] == "person_paraphrase", r


def test_a_paraphrase_stores_nothing_and_writes_no_more_than_answering_always_did():
    """Asking in other words is a lookup, not a lesson: no new record, no pair seen, the
    pending ask untouched. The row claim is the fair version -- answering writes memory, so
    what this flag must not do is write MORE of it than the same ask in the words it was
    taught in, measured against that ask rather than against zero."""
    o = _organ(paraphrase=True)
    _taught(o)
    before, seen = dict(o.qa_store), o.qa_pairs_seen
    rows = len(o.cortex.binder.meta)
    _say(o, "who is carrying droso")
    assert o.qa_store.keys() == before.keys()
    assert o.qa_pairs_seen == seen
    assert o._qa_pending is None
    delta_folded = len(o.cortex.binder.meta) - rows

    a = _organ(paraphrase=True)
    _taught(a)
    rows = len(a.cortex.binder.meta)
    _say(a, KEY)                                  # the ask that worked before this flag
    delta_exact = len(a.cortex.binder.meta) - rows
    assert delta_folded == delta_exact, (delta_folded, delta_exact)


# ---------------------------------------------------------------- the ask normalizer

def test_the_passive_is_recovered_by_the_ask_normalizer():
    """`what was the door opened by` is not the stored question with an article missing --
    the words are in a different ORDER, so the fold alone cannot reach it. This is
    `normalize_ask_variants` doing it, verbatim, with its own warrant: the stem it produces
    has to be a verb a taught tell actually carries."""
    o = _organ(paraphrase=True)
    o.hear(DOOR_TELL, speaker="you")
    _taught(o, DOOR_ASK, DOOR_ANS)
    r = _say(o, DOOR_PASSIVE)
    assert r["src"] == "electric_qa_store", r
    assert r["said"] == DOOR_ANS, r
    assert r["asked"] == "what opens the door", r


def test_the_normalizer_adds_no_variant_without_a_taught_verb():
    """Same ask, same stored pair, no tell carrying `open`: the normalizer emits no variant
    and the paraphrase is refused. The warrant is the house's own inventory, not a table."""
    o = _organ(paraphrase=True, teach=False)
    _taught(o, DOOR_ASK, DOOR_ANS)
    assert nl.normalize_ask_variants(DOOR_PASSIVE, o._taught_says) == []
    r = _say(o, DOOR_PASSIVE)
    assert r["src"] != "electric_qa_store", r


def test_the_normalizer_is_not_reached_when_the_flag_is_off():
    o = _organ(paraphrase=False)
    o.hear(DOOR_TELL, speaker="you")
    _taught(o, DOOR_ASK, DOOR_ANS)
    assert _say(o, DOOR_PASSIVE)["src"] != "electric_qa_store"


# ---------------------------------------------------------------- no widening

def test_a_book_pair_is_never_reached_by_a_paraphrase():
    """The provenance rule, in its strongest form: a pair he was READ is not a pair a
    person taught, and folding does not make it one. Not with the flag on, and not with
    `ELECTRIC_QA_PROVENANCE` on beside it -- the book route stays the exact-key route the
    audit measured."""
    for prov in (False, True):
        o = _organ(paraphrase=True, prov=prov)
        o.learn_qa(KEY.split(), ANSWER.split(), provenance=BOOK_PROV)
        assert o.qa_store[KEY]["prov"]["book"] == "stimulus.txt"
        assert str(o.qa_store[KEY]["prov"].get("source") or "") != "conversation"
        for a in FOLDED_EQUIVALENTS:
            r = _say(o, a)
            assert r["src"] != "electric_qa_store", (prov, a, r)
            assert r["evidence"] == "", (prov, a, r)
        assert o._qa_paraphrase_hit("who carries the droso") is None


def test_a_conversation_pair_without_the_mark_is_not_a_candidate():
    """`marked` is what makes a person's words a question. A record that says a person
    spoke them without ever typing a `?` has no questionhood to lend a paraphrase."""
    o = _organ(paraphrase=True)
    o.qa_store[KEY] = {"q": KEY.split(), "a": ANSWER.split(), "word": "who",
                       "role": 0, "filler": "parent",
                       "prov": {"source": "conversation", "speaker": "you",
                                "marked": False, "answer_is_question": False}}
    assert o._qa_paraphrase_hit("who carries the droso") is None
    assert _say(o, "who carries the droso")["src"] != "electric_qa_store"


def test_two_pairs_that_fold_alike_answer_nothing():
    """Ambiguity is refused, not resolved. Two pairs a person taught in two phrasings fold
    to one key; an ask that folds to that key could be either, and picking the first would
    be this flag guessing which lesson the person meant."""
    o = _organ(paraphrase=True)
    _taught(o, ASK, ANSWER)
    _taught(o, "who carries the droso?", "parent carries the droso")
    assert sorted(o.qa_store) == [KEY, "who carries the droso"]
    assert o.qa_paraphrase_key("who carries the droso") == o.qa_paraphrase_key(ASK)
    r = _say(o, "who is carrying droso")
    assert r["src"] != "electric_qa_store", r
    assert r["said"] not in (ANSWER, "parent carries the droso"), r
    assert o._qa_paraphrase_hit("who is carrying droso") is None


def test_an_exact_key_still_wins_over_a_folding_ambiguity():
    """The pair above is ambiguous only to a folded ask. Asked in the words it was taught
    in, it is answered -- the ambiguity is in the fold, not in the store, and must not
    silence the exact lookups that were working."""
    o = _organ(paraphrase=True)
    _taught(o, ASK, ANSWER)
    _taught(o, "who carries the droso?", "parent carries the droso")
    assert _say(o, KEY)["said"] == ANSWER
    assert _say(o, "who carries the droso")["said"] == "parent carries the droso"


# ---------------------------------------------------------------- routing

def test_a_paraphrase_is_routed_because_the_store_holds_his_pair():
    """`respond` routes on `is_interrogative`, which needs two role votes, and a person who
    taught one pair gave `who` one. Without the route an elicited pair is stored,
    answerable through `answer`, and unreachable in chat -- so the route has to follow the
    fold, or the feature only works for the phrasing it was typed in."""
    o = _organ(paraphrase=True)
    seen = _routed(o)
    _taught(o)
    o.respond("who carries the droso", speaker="you")
    o.respond("who is carrying droso", speaker="you")
    assert "who carries the droso" in seen and "who is carrying droso" in seen, seen
    o.respond("what bites the latch", speaker="you")
    assert "what bites the latch" not in seen, "the route widened past the record"


def test_the_route_needs_its_parent_flag():
    """This is a child of ELECTRIC_QA_ELICIT, not a second way into the store: with the
    parent off nothing is routed on a folded hit, whatever the record says."""
    o = _organ(elicit=False, paraphrase=True)
    seen = _routed(o)
    o.qa_store[KEY] = {"q": KEY.split(), "a": ANSWER.split(), "word": "who",
                       "role": 0, "filler": "parent",
                       "prov": {"source": "conversation", "speaker": "you",
                                "marked": True, "answer_is_question": False}}
    r = o.respond("who carries the droso", speaker="you") or {}
    assert seen == [], seen
    assert str(r.get("source") or "") != "electric_qa_store"


# ---------------------------------------------------------------- persistence

def test_a_paraphrase_still_answers_after_a_restart(tmp_path):
    """The store persists; the FOLD is derived from it at lookup time and is not itself a
    memory. A pair taught in one life answers a phrasing first typed in the next."""
    sp = Path(str(tmp_path)) / "state.json"
    o = _organ(paraphrase=True)
    _taught(o)
    o.state_path = sp
    o.persist = True
    assert o.save_state(force=True)["saved"] is True
    b = _organ(paraphrase=True)
    b.state_path = sp
    b.load_state()
    assert sorted(b.qa_store) == [KEY]
    r = _say(b, "who carries the droso")
    assert r["src"] == "electric_qa_store" and r["said"] == ANSWER, r
    assert r["evidence"] == "person_paraphrase", r


def test_the_fold_adds_no_field_to_the_saved_state(tmp_path):
    """No new memory, no new key: what is on disk after this flag is what was on disk
    before it, and a state file written by an older build is still readable."""
    sp = Path(str(tmp_path)) / "state.json"
    o = _organ(paraphrase=True)
    _taught(o)
    _say(o, "who carries the droso")
    o.state_path = sp
    o.persist = True
    o.save_state(force=True)
    import json
    doc = json.loads(sp.read_text(encoding="utf-8"))
    assert not any("paraphrase" in k or "parity" in k for k in doc), sorted(doc)
    # The store lives under `questions`, where it has lived since the audit put it there.
    assert doc["questions"]["qa_store"][KEY]["prov"]["marked"] is True
    assert not any("paraphrase" in k or "parity" in k
                   for k in doc["questions"]["qa_store"][KEY]), sorted(
                       doc["questions"]["qa_store"][KEY])


# ---------------------------------------------------------------- safety

def test_the_guarded_scarf_ask_still_refuses_with_the_flag_on():
    """ABORT B4, re-run for this flag: the battery's guarded ask must still refuse, and
    must still refuse for the reason the guard gives, not because a fold found something."""
    o = _organ(paraphrase=True, absence=True)
    for t in SCARF_TELLS:
        o.hear(t, speaker="you")
    _taught(o)
    r = o.answer(SCARF_ASK) or {}
    assert r.get("licensed_refusal") is True, r
    assert r.get("source") != "electric_qa_store"
    assert not r.get("answered")


def test_an_ask_is_never_answered_with_its_own_text():
    """The leak the parent flag closed, asked in other words: a folded hit returns an
    ANSWER LINE, and a paraphrase that matches nothing must not fall back to reciting the
    question it was just asked."""
    o = _organ(paraphrase=True)
    _taught(o)
    for a in FOLDED_EQUIVALENTS + FOLDED_REFUSALS:
        r = _say(o, a)
        assert r["said"].rstrip("?").strip() != a.rstrip("?").strip(), (a, r)


def test_the_grader_contract_is_untouched():
    src = inspect.getsource(nl.NeuralLanguage.answer)
    i_taught = src.index("if self.ELECTRIC_ANSWER:")
    i_store = src.index("if self.ELECTRIC_QA_STORE and self.qa_store:")
    i_abs = src.index("abs_lic = self._absence_licence(text)")
    assert i_taught < i_store < i_abs
    grad = inspect.getsource(nl._absence_licence)
    assert "_electric_bind(question, inventory)" in grad, \
        "the guarded grader started receiving flags"
    for forbidden in ("ELECTRIC_QA_ELICIT", "ELECTRIC_QA_STORE", "ELECTRIC_ANSWER",
                      "ELECTRIC_QA_PARAPHRASE", "qa_store", "paraphrase"):
        assert forbidden not in grad, f"the grader now reads {forbidden}"
    assert "abs_lic = self._absence_licence(text)" in src
    assert "self._absence_licence(text, " not in src


def test_the_flag_defaults_off_and_is_a_class_attribute():
    """Class attribute, not a module global: a `setattr` on the module would be a silent
    no-op, and an arm that quietly ran with the flag off is how a measurement dies."""
    assert "ELECTRIC_QA_PARAPHRASE" in nl.NeuralLanguage.__dict__
    assert nl.NeuralLanguage.ELECTRIC_QA_PARAPHRASE is False
    assert not hasattr(nl, "ELECTRIC_QA_PARAPHRASE")
    assert _organ().ELECTRIC_QA_PARAPHRASE is False
    assert _organ(paraphrase=True).ELECTRIC_QA_PARAPHRASE is True
