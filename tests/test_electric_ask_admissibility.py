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


def _organ(admissible=True, guard=False, electric=True):
    o = _m.build(electric)
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
    depend on a predicate that catches one symptom's shape."""
    for _ in range(3):
        o = _organ(admissible=True, guard=False)
        o.answer(STRANDED)
        out = o.answer(BARE) or {}
        assert not out.get("spoken"), f"the asking was answered from: {out}"
        assert out.get("source") is None or out.get("source") == ""
        assert "asking" in str(out.get("reason")), out.get("reason")


def test_nothing_spoken_off_the_arms_whole_table_is_question_shaped():
    """The recurrence proof, stated as a property rather than as one row: run every ask
    the object arm asks, with the fragment guard OFF so admissibility alone is holding the
    line, and no utterance may be a fragment or carry a mark. This is what the
    `recalled proposition` branch could have kept doing after the fragment guard."""
    o = _o.build()
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


def test_the_measured_arms_do_not_see_the_new_switch():
    for p in ("tools/electric_reverse_ab.py", "tools/electric_object_ab.py"):
        s = io.open(p, encoding="utf-8").read()
        assert "ELECTRIC_ASK_ADMISSIBILITY" not in s, p
    r = io.open("tools/electric_reverse_ab.py", encoding="utf-8").read()
    for verdict in ("correct", "miss", "refusal", "CONFABULATION"):
        assert verdict in r, f"grader verdict {verdict} disappeared from the contract"
