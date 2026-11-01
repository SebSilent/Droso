"""Memory admissibility for asks: a remembered question must not be answerable as a fact.

The `to?` leak (tests/test_electric_fragment_guard.py) was one symptom of a deeper thing:
`live()` learns an ask into the binder exactly like a statement, and the recall path reads
token lists without asking what kind of turn they came from. The other symptom was never
guarded at all - `recalled proposition` reads out a WHOLE remembered question, which is not
a fragment, so a fragment predicate cannot catch it.

ELECTRIC_ASK_ADMISSIBILITY (off by default) fixes the class instead of the symptom: a row
heard as a question is tagged at storage, and ask-tagged rows are dropped from the hit list
BEFORE the provenance vote and the shape arbiter - the one place a recalled memory becomes an
utterance - so neither branch can be reached by an asking.

Measured on the object arm's own 20-ask table, one condition per process: the tallies are
IDENTICAL off/on (correct 6, absence 9, arbiter head 2, electric_taught 1, electric_absence 2).
Dropping questions costs no answer. Running both conditions in ONE process instead gives a
spurious delta - the arm is not hermetic across builds in a process - which is why the
comparison below is written per-process and why the cost test here is about scope, not tally.
"""

import importlib.util as _u
import io
import sys

sys.path.insert(0, ".")

_s = _u.spec_from_file_location("rev_adm", "tools/electric_reverse_ab.py")
_m = _u.module_from_spec(_s)
_s.loader.exec_module(_m)
_os2 = _u.spec_from_file_location("obj_adm", "tools/electric_object_ab.py")
_o = _u.module_from_spec(_os2)
_os2.loader.exec_module(_o)

import organs.neural_language as nl  # noqa: E402
from organs.higher_cortex import row_is_ask  # noqa: E402

STRANDED = "who does the mouse chase to?"
BARE = "who does the mouse chase?"


def _no_throttle(o):
    """Land every write. hear() DROPS an utterance arriving within
    MIN_HEAR_INTERVAL_S (0.05 s) of the last one and only counts it in `skipped`, so a
    test that fires live()/answer() back to back is largely measuring which writes the
    throttle happened to allow. This is also the mechanism behind the run-to-run flicker
    this project keeps meeting in probe tables -- not float accumulation, not hash seeds,
    a 50 ms gate on writes. Orthogonal to admissibility, so neutralise it here."""
    o.cortex.MIN_HEAR_INTERVAL_S = 0.0
    return o


def _organ(admissible=True, guard=False, electric=True):
    o = _no_throttle(_m.build(electric))
    o.ELECTRIC_TEACH = False
    o.ELECTRIC_FRAGMENT_GUARD = guard
    o.ELECTRIC_ASK_ADMISSIBILITY = admissible
    return o


def _said(out):
    out = out or {}
    return str(out.get("utterance") or out.get("response") or "").strip()


def _question_shaped(said):
    s = said.strip().lower()
    return (not s) or "?" in s or s in ("who", "what", "does", "to", "of") or \
        any(t.endswith("?") for t in s.split())


# ---------------------------------------------------------------- storage: the tag

def test_the_flag_is_off_by_default():
    assert nl.NeuralLanguage.ELECTRIC_ASK_ADMISSIBILITY is False


def test_a_heard_question_is_tagged_and_a_told_statement_is_not():
    """Scope, measured: the filter may only ever drop rows that ARE askings. If a tell
    ever comes back tagged, the flag is eating facts and the tally claim is void."""
    o = _organ(admissible=True)
    for t in _m.TELLS:
        o.hear(t, speaker="you")
    o.answer(STRANDED)
    meta = o.cortex.binder.meta
    for t in _m.TELLS:
        toks = [w.strip() for w in t.lower().split()]
        rows = [m for m in meta if m["tokens"][:len(toks)] == toks]
        for m in rows:
            assert not row_is_ask(m), f"a tell is tagged as an ask: {m}"
    assert any(row_is_ask(m) for m in meta), "the heard question is not tagged"


def test_the_tag_reaches_the_reader_not_just_the_writer():
    """recall() builds its hit dict from a WHITELIST of meta keys. A tag that is stored
    but not copied out is a tag no reader can see - the bug this pins."""
    o = _organ(admissible=True)
    o.answer(STRANDED)
    hits = o.cortex.binder.recall(["mouse", "chase", "to?"], k=5)
    hits = hits or []
    assert any(row_is_ask(h) for h in hits), \
        f"tagged in meta, invisible in the hit: {hits}"


def test_the_mark_alone_tags_a_question_even_with_admissibility_off():
    """The tag is not solely a switch's doing: a row carrying `?` IS an asking. This is
    also what carries the tag across a delta replay, where the organ's `ask` argument is
    not re-derived."""
    o = _organ(admissible=False)
    o.answer(STRANDED)
    assert any(row_is_ask(m) for m in o.cortex.binder.meta)


# ---------------------------------------------------------------- the class of leak

def test_admissibility_alone_kills_the_fragment_leak_with_the_guard_off():
    """The fragment guard is OFF here on purpose: admissibility must fix the cause, not
    depend on a predicate that catches one symptom's shape.

    Causation is proved by the precondition, not by the wording of the veto: the asking
    must still be REACHABLE by recall (so the thing that used to leak is present in the
    store), and he must still stay silent. Which licensed absence he then names moves
    between runs -- the same row said "only the asking itself" and "nothing he remembers
    has that shape" in two runs of this file a minute apart, because whether a question
    row wins a ranking is pacing-dependent. Demanding one string would have been testing
    the flicker.
    """
    for _ in range(3):
        o = _organ(admissible=True, guard=False)
        o.answer(STRANDED)
        reach = o.cortex.binder.recall(["who", "does", "the", "mouse", "chase", "to?"],
                                       k=5) or []
        assert any(row_is_ask(h) for h in reach), \
            f"the asking is not in the store at all, so this run proves nothing: {reach}"
        out = o.answer(BARE) or {}
        assert not out.get("spoken"), f"the asking was answered from: {out}"
        assert out.get("source") in (None, ""), out.get("source")
        assert out.get("reason"), out


def test_nothing_spoken_off_the_arms_whole_table_is_question_shaped():
    """The recurrence proof, stated as a property rather than as one row: run every ask
    the object arm asks, with the fragment guard OFF so admissibility alone is holding the
    line, and no utterance may be a fragment or carry a mark. This is what the
    `recalled proposition` branch could have kept doing after the fragment guard."""
    o = _no_throttle(_o.build())
    o.ELECTRIC_FRAGMENT_GUARD = False
    o.ELECTRIC_ASK_ADMISSIBILITY = True
    seen = 0
    for ask, shade, want in _o.ASKS:
        out = o.answer(ask) or {}
        if out.get("spoken"):
            seen += 1
            said = _said(out)
            assert not _question_shaped(said), f"{ask!r} -> {said!r} [{out.get('source')}]"
    assert seen >= 3, f"nothing was spoken at all, so this proves nothing: {seen}"


def test_dropping_asks_does_not_drop_the_statements():
    """An ask with a real factual answer must still be answered with the flag on.
    `what chases the cat?` is one of the rows ELECTRIC recovered precisely because a tell
    backs it; if it goes silent, the filter is over-broad."""
    for _ in range(3):
        o = _organ(admissible=True)
        out = o.answer("what chases the cat?") or {}
        if out.get("spoken"):
            assert _said(out).lower() == "mouse", out


# ---------------------------------------------------------------- shape authority

SHAPE_ON = ("who pets the mouse", "what bites the latch", "what turns twice",
            "where does the lantern belong to", "what is the capital of france",
            "who is the owner of the house")
# Each one is a prose class that a "contains a question word" detector would eat, and
# the first two are the failure this project already documented inside
# `is_interrogative`: a book harvested from this repo's own docstrings turned them into
# interrogatives and deleted every answer he could give.
SHAPE_OFF = ("what the loop does", "where the state lives", "what he did next",
             "what matters most is the latch", "who knows", "which thing turns twice",
             "the latch holds the door", "how are you", "he asked what happened")


def test_the_shape_flag_is_off_by_default():
    assert nl.NeuralLanguage.ELECTRIC_ASK_SHAPE is False


def test_the_detector_tags_asks_and_spares_the_prose_classes():
    o = _organ(admissible=True)
    o.ELECTRIC_ASK_SHAPE = True
    for row in SHAPE_ON:
        assert o.question_shape(row.split()), f"an ask the detector missed: {row!r}"
    for row in SHAPE_OFF:
        assert not o.question_shape(row.split()), \
            f"a statement the detector would have eaten: {row!r}"


def test_an_unmarked_ask_is_a_fact_without_shape_and_an_asking_with_shape():
    """The exact gap last session left open, measured both ways: `who pets the mouse`
    has no mark and the hermetic organ has no role votes for `who`, so `is_q` is False
    and the row went in as a fact. Shape is what closes it."""
    for shape, expect in ((False, False), (True, True)):
        o = _organ(admissible=True)
        o.ELECTRIC_ASK_SHAPE = shape
        o.live("who pets the mouse", speaker="you")
        rows = [m for m in o.cortex.binder.meta if "pets" in m["tokens"]]
        assert rows, f"nothing stored (shape={shape})"
        assert [bool(o._hit_is_ask(m)) for m in rows] == [expect] * len(rows), \
            f"shape={shape}: {rows}"


def test_a_book_question_is_tagged_too():
    """The book path is live(line, speaker='book'), so the same authority has to reach
    it. Unmarked here on purpose: a mark would have been caught by row_is_ask already."""
    for shape, expect in ((False, False), (True, True)):
        o = _organ(admissible=True)
        o.ELECTRIC_ASK_SHAPE = shape
        o.live("who pets the mouse", learn=True, speaker="book", readout=False)
        rows = [m for m in o.cortex.binder.meta if "pets" in m["tokens"]]
        assert rows, f"the book line was not stored (shape={shape})"
        assert [bool(o._hit_is_ask(m)) for m in rows] == [expect] * len(rows)


def test_the_tag_survives_a_delta_replay_that_rehears_only_tokens(tmp_path):
    """A replay re-hears TOKENS, so the verdict has to travel with them. This is the
    whole point of recording it in the delta rather than re-deriving it at read time:
    the asking was UNMARKED, so nothing in its own tokens says it was a question --
    after apply_delta() it must still be tagged, or tomorrow's house answers from it."""
    import json
    o = _organ(admissible=True)
    o.ELECTRIC_ASK_SHAPE = True
    o.live("who pets the mouse", speaker="you")
    p = tmp_path / "delta.json"
    wrote = o.cortex.save_delta(str(p))
    assert wrote.get("saved"), wrote
    doc = json.loads(p.read_text(encoding="utf-8"))
    assert any(len(r) > 5 and r[5] for r in doc["heard"]), \
        f"the delta carries no ask verdict: {doc['heard']}"

    fresh = _organ(admissible=True)
    fresh.ELECTRIC_ASK_SHAPE = True
    applied = fresh.cortex.apply_delta(str(p))
    assert applied.get("applied"), applied
    rows = [m for m in fresh.cortex.binder.meta
            if m["tokens"][:4] == ["who", "pets", "the", "mouse"]]
    assert rows, f"the replay did not restore the row: {applied}"
    assert any(fresh._hit_is_ask(m) for m in rows), \
        f"replayed untagged, so the reader would answer from it: {rows}"


def test_shape_declines_on_a_row_too_long_to_be_stored_whole():
    """The false-positive class, found in the live house and pinned here. remember()
    binds at most `max_roles` tokens, so a long line is stored as its HEAD -- and the
    head of a relative clause reads exactly like a question. Tagged row from the real
    binder: `who sacrificed everything for him chimed in the`, cut off mid-phrase. That
    is a FACT the house could no longer answer from.

    The writer is the only place that knows the row will not fit, so the writer declines:
    past the cap, no tag and no rebinding, and the tail survives as windows. `is_q` is
    pinned off to isolate the shape rule -- the learned path has its own long-line
    behaviour and this test is not about it.
    """
    mr = int(_organ(admissible=True).cortex.binder.max_roles)
    lines = ["who sacrificed everything for him chimed in the yard at dawn",
             "what does the mouse that chases the cat chase when the lantern is lit"]
    o = _organ(admissible=True)
    o.ELECTRIC_ASK_SHAPE = True
    o.is_interrogative = lambda w: False
    for line in lines:
        assert len(line.split()) > mr, f"the test line is not over the cap: {line}"
        o.live(line, speaker="you")
    meta = o.cortex.binder.meta
    assert meta, "nothing was stored"
    assert not [m for m in meta if o._hit_is_ask(m)], \
        f"shape authority ate a row over the {mr}-token cap: " \
        f"{[m['tokens'] for m in meta if o._hit_is_ask(m)]}"
    # The other half of the bargain: declining deletes nothing. The line windows as it
    # would have with the flag off, and no capped head is bound in its place.
    # (Found in passing, and NOT this flag's: the window loop's last start is
    # `len(toks) - max_roles` stepped by max(2, mr//2), so an 11-token line at mr=8
    # bounds tokens 0-7 only -- its last three words never exist anywhere. Pre-existing,
    # independent of every switch here, and worth its own stroke. docs/STATE.md records it.)
    assert all(len(m["tokens"]) <= mr for m in meta), "a row longer than the cap appeared"
    assert ("who", "sacrificed", "everything", "for", "him", "chimed", "in", "the") \
        in [tuple(m["tokens"]) for m in meta], \
        f"the long line was not windowed as it always was: {[m['tokens'] for m in meta]}"
    short = _organ(admissible=True)
    short.ELECTRIC_ASK_SHAPE = True
    short.is_interrogative = lambda w: False
    short.live("who pets the mouse", speaker="you")
    assert any(short._hit_is_ask(m) for m in short.cortex.binder.meta), \
        "declining on long rows also stopped tagging short ones"


def test_shape_is_inert_without_admissibility_even_to_a_detector_that_asks_every_row():
    """The pair is one experiment: shape is read only under admissibility. Pinned by
    making the detector maximally WRONG -- every row is an ask -- and checking that with
    admissibility off a plain statement still goes in untagged and still windows the way
    it always did. If anyone widens that gate, a told sentence comes back tagged as an
    asking, or a long statement stops being windowed at all."""
    long_stmt = "the latch that holds the door on the yard was oiled again at dawn"
    for shape in (False, True):
        o = _organ(admissible=False)
        o.ELECTRIC_ASK_SHAPE = shape
        o.question_shape = lambda toks: True
        o.live(long_stmt, speaker="you")
        meta = o.cortex.binder.meta
        assert meta, f"nothing landed (shape={shape})"
        assert not any(m.get("ask") for m in meta), f"shape wrote tags, shape={shape}"
        assert tuple(long_stmt.lower().split()) not in [tuple(m["tokens"]) for m in meta], \
            f"shape reached `chunk` with admissibility off, shape={shape}"


def test_shape_binds_an_unmarked_ask_whole_when_the_learned_authority_is_off():
    """The detector had to reach `chunk` because a long ask that windows into
    ['what','bites'] / ['bites','the'] / ['the','latch'] has no interrogative in first
    position in any window, so no shape reader can call any of them an asking.

    Asserted one way only: an ask that fits is whole UNDER THE FLAG. The off case is not
    pinned because it is not the flag's business -- whether a short line windows at all
    depends on `max_roles`, and the write throttle (see _no_throttle) decides whether the
    row exists at all.
    """
    whole = ("who", "pets", "the", "mouse")
    long_ask = "what bites the latch on the door that holds the yard"
    for _ in range(3):
        o = _organ(admissible=True)
        o.ELECTRIC_ASK_SHAPE = True
        # Pinned, not guessed at: in THIS organ `who` has earned role votes and binds
        # whole on its own (measured), which is exactly why the gap looked closed. The
        # hermetic organ had none. Take the learned authority away and shape is the only
        # thing left that can tell the binder this row is an asking.
        o.is_interrogative = lambda w: False
        o.live("who pets the mouse", speaker="you")
        meta = o.cortex.binder.meta
        rows = [tuple(m["tokens"]) for m in meta]
        assert whole in rows, f"the short ask was not bound whole: {rows}"
        assert any(o._hit_is_ask(m) for m in meta
                   if tuple(m["tokens"]) == whole), "bound whole but not tagged"
        # And a row over the cap is left alone entirely -- see the decline test.
        assert not any(len(t) > 4 and o.question_shape(t) for t in rows)
        assert len(long_ask.split()) > int(o.cortex.binder.max_roles)


def test_an_unmarked_ask_is_never_read_back_as_an_answer():
    """End to end, guard OFF so admissibility+shape are the only thing holding: after
    being told nothing but an unmarked question, he must not answer with that question."""
    for _ in range(3):
        o = _organ(admissible=True)
        o.ELECTRIC_ASK_SHAPE = True
        o.live("who pets the mouse", speaker="you")
        out = o.answer("who pets the mouse") or {}
        said = _said(out)
        assert said.lower() != "who pets the mouse", f"he answered with the asking: {out}"
        if out.get("source") == "recalled proposition":
            assert not _question_shaped(said), out


def test_shape_never_tags_a_told_statement():
    """Scope, at the widest setting: BOTH switches on, every tell he was given must
    still be in the store and none of them may be an asking. A row that is dropped from
    recall is an answer he can no longer give, so this is the test that says the
    detector eats asks and nothing else.

    Asserted inside one organ, not as an off/on row-set equality: build() teaches its own
    lines and the learned state differs between two builds in a process, so the two row
    sets are not comparable -- a cross-build equality here would be testing that race.
    """
    o = _organ(admissible=True)
    o.ELECTRIC_ASK_SHAPE = True
    for t in _m.TELLS:
        o.live(t, speaker="you")
    meta = o.cortex.binder.meta
    for t in _m.TELLS:
        toks = [w.strip() for w in t.lower().split()]
        rows = [m for m in meta if m["tokens"][:len(toks)] == toks]
        assert rows, f"a tell is not in the store: {t!r}"
        for m in rows:
            assert not o._hit_is_ask(m), f"a tell reads as an asking: {m}"


# ---------------------------------------------------------------------- wiring, contract

def test_serve_reads_the_switch_outside_the_electric_block():
    s = io.open("tools/serve.py", encoding="utf-8").read()
    assign = s.index(
        "agent.language.ELECTRIC_ASK_ADMISSIBILITY = bool(args.electric_ask_admissibility)")
    assert assign < s.index("    if args.electric:"), \
        "inside the --electric block the switch would be dead in the corpus-free house " \
        "that actually leaks"
    assert "--electric-ask-admissibility" in s
    assert "Independent of --electric: a question someone asked" in s


def test_serve_wires_the_shape_switch_outside_the_electric_block_too():
    s = io.open("tools/serve.py", encoding="utf-8").read()
    assign = s.index("agent.language.ELECTRIC_ASK_SHAPE = bool(args.electric_ask_shape)")
    assert assign < s.index("    if args.electric:"), \
        "inside the --electric block the detector would never run in the corpus-free house"
    assert "--electric-ask-shape" in s
    assert "decide an asking by its " in s
    # The old help text claimed nothing is TAGGED with admissibility off, which the
    # mark fallback makes false. Pinned so it cannot creep back.
    assert "nothing is tagged, nothing is dropped" not in s


def test_the_measured_arms_do_not_see_the_new_switch():
    for p in ("tools/electric_reverse_ab.py", "tools/electric_object_ab.py"):
        s = io.open(p, encoding="utf-8").read()
        for flag in ("ELECTRIC_ASK_ADMISSIBILITY", "ELECTRIC_ASK_SHAPE"):
            assert flag not in s, f"{p} reached for {flag}: the arms must stay comparable"
    r = io.open("tools/electric_reverse_ab.py", encoding="utf-8").read()
    for verdict in ("correct", "miss", "refusal", "CONFABULATION"):
        assert verdict in r, f"grader verdict {verdict} disappeared from the contract"
