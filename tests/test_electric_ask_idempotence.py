"""Pinning the order-dependence claim that was raised and then REFUTED.

The first run of tools/electric_object_ab.py appeared to show the organ answering
`what bites the latch?` on one row and saying nothing to the SAME question on a later row.
That would have been state mutation inside `answer()` -- questions changing what the organ
knows -- and it would have been serious.

It was not real. My appended rows were built as `(shade, ask, want)` while the table I
appended to is `(ask, shade, want)`, so the "repeated question" was the literal string
`"object-role"`. The organ was asked a nonsense word and correctly said nothing.

These tests pin BOTH halves: the property that was doubted (asking does not change answers),
and the harness shape that manufactured the phantom, because a phantom this plausible will
be believed again by the next reader of this file.
"""

import importlib.util as _u
import io
import sys

sys.path.insert(0, ".")

_s = _u.spec_from_file_location("rev_ab_pin", "tools/electric_reverse_ab.py")
_m = _u.module_from_spec(_s)
_s.loader.exec_module(_m)
_o = _u.spec_from_file_location("obj_ab_pin", "tools/electric_object_ab.py")
_obj = _u.module_from_spec(_o)
_o.loader.exec_module(_obj)

import organs.neural_language as nl  # noqa: E402

ASK = "what bites the latch?"
WANT = "the frost bites the latch"


def _said(out):
    if not isinstance(out, dict):
        return ""
    if not out.get("spoken"):
        return ""
    return str(out.get("utterance") or out.get("response") or "").strip()


def _organ(teach):
    o = _m.build(True)
    o.ELECTRIC_OBJECT_ROLE = True
    o.ELECTRIC_TEACH = teach
    return o


def _facts(o):
    return sum(len(v) for v in o._taught_says.values())


# ------------------------------------------------- the property that was doubted

def test_asking_the_same_question_three_times_speaks_the_same_words():
    o = _organ(teach=True)
    got = [_said(o.answer(ASK)) for _ in range(3)]
    assert got == [WANT, WANT, WANT], f"answers drifted across repeats: {got}"


def test_asking_does_not_change_what_the_organ_knows():
    """`answer()` never calls `hear()`, and `hear()` is the only call site of
    `_absence_note` -- so the write side cannot be reached by asking. Pinned, because the
    whole ELECTRIC safety story rests on questions not becoming facts."""
    o = _organ(teach=True)
    before = _facts(o)
    for _ in range(3):
        o.answer(ASK)
    assert _facts(o) == before, "asking changed the taught inventory"
    leaked = [t for v in o._taught_says.values() for t in v.values() if "?" in t]
    assert not leaked, f"questions were stored as facts: {leaked}"


def test_a_repeated_ask_matches_a_fresh_organ_asked_once():
    """The strongest form: no amount of prior questioning moves the answer, so the
    result of an arm does not depend on where in the table a row sits."""
    warm = _organ(teach=True)
    for q in ("where is the scarf?", "what does the frost bite?", ASK,
              "what is the scarf like?", "who does the mouse chase?"):
        warm.answer(q)
    fresh = _organ(teach=True)
    assert _said(warm.answer(ASK)) == _said(fresh.answer(ASK)) == WANT


def test_the_answer_is_the_same_with_teach_open_or_closed():
    assert _said(_organ(True).answer(ASK)) == _said(_organ(False).answer(ASK)) == WANT


# ------------------------------------- the harness shape that manufactured the phantom

def test_every_arm_row_asks_a_question_and_no_ask_is_repeated():
    """The bug: rows appended as (shade, ask, want) into an (ask, shade, want) table make a
    shade label become the question, and the resulting silence reads exactly like
    order-dependence. So: every row's first element must be question-shaped, and no ask may
    appear twice -- a duplicate is what made this look like the SAME question answering
    differently twice."""
    asks = []
    for row in _obj.ASKS:
        ask, shade, want = row          # unpacking is the contract
        assert isinstance(ask, str) and " " in ask, f"not a question: {ask!r}"
        assert ask.split()[0].lower() in (
            "what", "who", "where", "how", "is", "does"), f"not a question: {ask!r}"
        assert isinstance(shade, str) and " " not in shade.strip(), f"swapped columns: {row}"
        assert want is None or want in _obj.TELLS, f"want is not a taught tell: {row}"
        assert ask not in asks, f"duplicate ask would pose as order-dependence: {ask!r}"
        asks.append(ask)


def test_the_object_role_expectation_is_corrected_here_not_in_c4d():
    """C4d recorded `what bites the latch?` with want=None, which was RIGHT for the question
    C4d asked. This arm overrides it locally. The reverse tool's table must stay untouched,
    or a later arm silently rewrites an earlier measurement."""
    s = io.open("tools/electric_object_ab.py", encoding="utf-8").read()
    assert "_OVERRIDES" in s and '"what bites the latch?": "the frost bites the latch"' in s
    r = io.open("tools/electric_reverse_ab.py", encoding="utf-8").read()
    assert ('("what bites the latch?", "c3-h1-reverse", None)' in r), \
        "C4d's expectation was edited -- its measured result must stay reportable as asked"
