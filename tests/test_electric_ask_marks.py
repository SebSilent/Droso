"""The question-mark CHANNEL: positions recorded, tokens untouched, book asks recognised.

The claim is narrow and the second half of it is the safety: a line that a book printed as
a question must become a row the house calls an asking, and NOTHING about which rows exist
may change. So most of these tests compare two row sets, not one row set against a hope.

Tokenization is deliberately NOT changed. `you` and `you?` are different tokens to the
binder key, the cue and the concept vector, so putting the mark back would re-key every row
he has ever heard -- which is why this is a side-channel of positions instead.
"""
import importlib.util as _u
import io
import sys

import pytest

sys.path.insert(0, ".")

import organs.neural_language as nl                       # noqa: E402
from organs.higher_cortex import row_is_ask, marks_cover   # noqa: E402
from connectome.engine import HybridEngine                # noqa: E402
from connectome.substrate import build_core_graph         # noqa: E402
from organs.tokenizer import TokenizerOrgan               # noqa: E402

_s = _u.spec_from_file_location("rev_nmz", "tools/electric_reverse_ab.py")
_m = _u.module_from_spec(_s)
_s.loader.exec_module(_m)

# The book tokenizer, verbatim from _load_next_book: an index from
# question_mark_positions must mean a token this function produced, or the whole
# channel points at the wrong word.
book_toks = lambda s: [w for w in "".join(  # noqa: E731
    c if c.isalnum() else " " for c in s.lower()).split() if w]


def _organ(marks=False, admissible=False):
    o = nl.NeuralLanguage(HybridEngine(graph=build_core_graph()), TokenizerOrgan(),
                          state_path=None)
    o.persist = False
    o.cortex.MIN_HEAR_INTERVAL_S = 0.0     # a unit test is not an afternoon
    o.ELECTRIC_ASK_MARKS = bool(marks)
    o.ELECTRIC_ASK_ADMISSIBILITY = bool(admissible)
    return o


LONG_Q = "are you coming with us tomorrow or is it too far to walk there?"
SHORT_Q = "are you well today?"
STATEMENT = "the dog ran across the road twice today and sat down"


def rows(o):
    return [(tuple(m.get("tokens")), row_is_ask(m)) for m in o.cortex.binder.meta]


# ------------------------------------------------------------------ the position math

def test_a_mark_is_recorded_as_a_position_and_never_as_a_token():
    """The index must mean the SAME token the book tokenizer produced -- an off-by-one
    here would tag a statement and spare a question, and nothing downstream would notice."""
    for line, expect in (("who are you?", [2]),
                         ("are you well ?", [2]),          # mark after a space
                         ("he asked who? and left", [2]),  # INTERIOR mark
                         ("what? where? why?", [0, 1, 2]),  # three in one line
                         ("the cat sat", []),
                         ("? alone", []),                  # no token to attach to
                         ('she said "is it done?" and went', [4])):
        got = nl.question_mark_positions(line)
        assert got == expect, (line, got, expect)
        toks = book_toks(line)
        for i in got:
            assert 0 <= i < len(toks), (line, i, toks)
        if expect:
            # the token a mark trailed is the one that would carry it if it survived
            assert toks[expect[0]] in line.replace("?", " ").lower()


def test_a_trailing_mark_scopes_the_utterance_and_an_interior_one_scopes_its_span():
    """A sentence-final `?` punctuates the SENTENCE, not its last word: 1,618 of the
    corpus's 2,687 question lines are longer than the 8-role window, so a rule that tagged
    only the window the mark sat in would leave 60% of a question quotable as fact. An
    interior mark is different -- `he asked who? and left` is a statement with a question
    inside it, and the windows around it are not all asks."""
    assert marks_cover(0, 8, [11], 12) is True
    assert marks_cover(4, 12, [11], 12) is True     # trailing: every window
    assert marks_cover(0, 8, [3], 12) is True       # interior: its own window
    assert marks_cover(4, 12, [3], 12) is False     # ...and not the next one
    assert marks_cover(0, 8, [], 12) is False
    assert marks_cover(0, 8, None, 12) is False
    assert marks_cover(0, 8, [0], 0) is False


# --------------------------------------------------------------------- write-side effect

def test_the_channel_tags_every_row_a_question_line_made_and_no_other():
    o = _organ(marks=True, admissible=True)
    for ln in (LONG_Q, SHORT_Q, STATEMENT):
        o.live(" ".join(book_toks(ln)), speaker="book", learn=True,
               ask_marks=nl.question_mark_positions(ln))
    got = rows(o)
    q = [(t, a) for t, a in got
         if " ".join(t).startswith(("are you coming", "us tomorrow", "are you well"))]
    assert len(q) >= 3, f"the long question windowed into too few rows: {q}"
    assert all(a for _t, a in q), [t for t, a in q if not a]
    assert not any(a for t, a in got if " ".join(t).startswith("the dog ran")), \
        "an unmarked line got tagged"


def test_the_channel_renames_rows_without_making_or_losing_any():
    """THE central safety claim: same text, same rows, same tokens, different NAME. If a
    single key differed, this flag would be changing memory, not describing it."""
    a, b = _organ(marks=False, admissible=True), _organ(marks=True, admissible=True)
    for o in (a, b):
        for ln in (LONG_Q, SHORT_Q, STATEMENT):
            o.live(" ".join(book_toks(ln)), speaker="book", learn=True,
                   ask_marks=nl.question_mark_positions(ln) if o is b else None)
    ka = [t for t, _x in rows(a)]
    kb = [t for t, _x in rows(b)]
    assert ka == kb, "the channel changed WHICH rows exist"
    assert all("?" not in " ".join(t) for t in kb), "a mark leaked into a token"
    assert sum(1 for _t, x in rows(a) if x) < sum(1 for _t, x in rows(b) if x), \
        "the channel tagged nothing -- it is not reaching hear()"


def test_the_channel_is_inert_when_the_flag_is_off():
    o = _organ(marks=False, admissible=True)
    o.live(" ".join(book_toks(LONG_Q)), speaker="book", learn=True,
           ask_marks=nl.question_mark_positions(LONG_Q))
    assert not any(a for _t, a in rows(o)), "rows tagged with the switch off"


def test_marks_alone_change_nothing_anyone_can_hear():
    """The tag is only CONSULTED under admissibility. With admissibility off, an organ that
    recorded every mark and an organ that recorded none must answer the same ask with the
    same words -- otherwise this flag silently moves the recall path it claims not to."""
    base = _organ(marks=False, admissible=False)
    marked = _organ(marks=True, admissible=False)
    for o in (base, marked):
        for ln in (LONG_Q, SHORT_Q, _m.TELLS[2]):
            o.live(" ".join(book_toks(ln)), speaker="you", learn=True,
                   ask_marks=nl.question_mark_positions(ln) if o is marked else None)
    assert any(a for _t, a in rows(marked)), "the channel wrote no tag at all"
    assert not any(a for _t, a in rows(base)), "tags appeared without the channel"
    for q in ("who does the mouse chase", "where is the scarf"):
        assert (base.answer(q) or {}).get("utterance") == \
            (marked.answer(q) or {}).get("utterance"), q


def test_junk_positions_are_ignored_not_guessed():
    """A bool is not index 1, a string is not index 3, and an index past the last token is
    not the last token. The channel is fed by a caller that could be wrong; the failure mode
    must be no tag, never a tag on the wrong row."""
    o = _organ(marks=True, admissible=True)
    o.live("the dog ran across the road", speaker="book", learn=True,
           ask_marks=["3", True, 99, -1, None])
    assert not any(a for _t, a in rows(o)), rows(o)


# --------------------------------------------------------------------- the delta path

def test_the_positions_survive_a_delta_replay_and_tag_the_same_rows(tmp_path):
    """A row tagged in one session must be tagged in the next. The 6th delta element says
    WHETHER, the 7th says WHERE -- without it a replay of a long question would tag every
    window or none, and an interior mark would silently widen."""
    o = _organ(marks=True, admissible=True)
    for ln in (LONG_Q, "he asked who? and left then went away outside the gate today"):
        o.live(" ".join(book_toks(ln)), speaker="book", learn=True,
               ask_marks=nl.question_mark_positions(ln))
    heard = [list(r) for r in o.cortex._heard]
    assert all(len(r) == 7 for r in heard), heard
    p = tmp_path / "delta.json"
    assert o.cortex.save_delta(p)["saved"], "the session wrote no delta"
    fresh = _organ(marks=True, admissible=True)
    fresh.cortex.apply_delta(p)
    before = {t: a for t, a in rows(o)}
    after = {t: a for t, a in rows(fresh)}
    assert after, "the replay stored nothing"
    for t, a in before.items():
        assert after.get(t) == a, f"replay moved a tag: {' '.join(t)!r} {a} -> {after.get(t)}"


# --------------------------------------------------------------------- the book path

def test_the_book_loader_keeps_marks_parallel_to_lines(tmp_path):
    """_book_marks must line up with _book_lines index for index -- expose_tick indexes
    them together and a dropped append would attribute one line's mark to another."""
    src = tmp_path / "b.txt"
    src.write_text("the gate was open\nwho are you?\nhe asked who? and left\n"
                   "are you well ?\n", encoding="utf-8")
    o = _organ()
    o.books_dir = tmp_path
    assert o._load_next_book()
    assert len(o._book_marks) == len(o._book_lines)
    assert [bool(m) for m in o._book_marks] == [False, True, True, True]
    assert o._book_is_q == [False, True, False, True], \
        "the third line carries an interior mark that endswith('?') cannot see"
    assert o._book_marks[2] == [2]


def test_expose_tick_hands_the_marks_it_already_had_to_live(tmp_path, monkeypatch):
    """The exposure path has ALWAYS known a line was a question -- for learn_qa. This is
    the one hop that was missing, so it is the one hop asserted: live() must receive the
    positions of the line being read, and nothing else."""
    seen = []
    o = _organ(marks=True)
    o.exposure_enabled = True
    o.exposure_speed_s = 0.0
    o.EXPOSURE_MIN_REAL_S = 0.0
    o.social_drive = 1.0
    o.books_dir = tmp_path
    (tmp_path / "b.txt").write_text("who are you?\nthe gate was open\n",
                                    encoding="utf-8")
    monkeypatch.setattr(o, "live",
                        lambda text, **kw: seen.append((text, kw.get("ask_marks"))))
    for _ in range(2):
        o.expose_tick(world_dt=5.0)
    assert seen[0] == ("who are you", [2]), seen
    assert seen[1] == ("the gate was open", []), seen


# ------------------------------------------------------------------------- the wiring

def test_the_switch_defaults_off_on_the_class_and_the_organ():
    assert nl.NeuralLanguage.ELECTRIC_ASK_MARKS is False
    assert _organ().ELECTRIC_ASK_MARKS is False


def test_serve_wires_it_outside_the_electric_block():
    """Read OUTSIDE --electric, like admissibility and shape: the rows it tags come out of
    the recall path, which runs whatever else is on. A test that only checked the flag
    exists would pass if it were wired into the ELECTRIC block and never reached a house."""
    s = io.open("tools/serve.py", encoding="utf-8").read()
    assert '"--electric-ask-marks"' in s
    assign = s.index("agent.language.ELECTRIC_ASK_MARKS = bool(args.electric_ask_marks)")
    block = s.index("    if args.electric:")
    assert assign < block, "must be read outside the --electric block, like admissibility"
    assert s.index('"--electric-ask-marks"') < s.index('"--electric",')


def test_live_does_not_feed_the_channel_into_chunking():
    """`chunk` stays whatever is_q made it. Binding a 14-word book question whole stores
    its first eight words and loses the rest -- measured, and the reason shape authority
    declines past the cap. The channel says what a row IS; it must not say how many there
    are."""
    src = io.open("organs/neural_language.py", encoding="utf-8").read()
    i = src.index("res = self.cortex.hear(toks, who=str(speaker), chunk=not is_ask,")
    block = src[i:i + 400]
    assert "ask_marks=(ask_marks if self.ELECTRIC_ASK_MARKS" in block
    assert "chunk=not is_ask" in block and "ask_marks" not in \
        block[:block.index("chunk=not is_ask") + len("chunk=not is_ask")]


# ------------------------------------------------------------------ the leak itself

# A line the book printed as a question, and an asking near enough to it that the row
# out-matches everything else he has. Both were measured speaking before being written
# down here, in both directions: the leak happens with the channel off, and does not
# happen with it on.
LEAK = [("Why have I alluded to this man?", "why have i alluded to that man"),
        ("What were you doing behind the curtain?", "what were you doing behind the door")]


def _leak_arm(line, ask, marks, admissible):
    o = _organ(marks=marks, admissible=admissible)
    o.live(" ".join(book_toks(line)), speaker="book", learn=True,
           ask_marks=nl.question_mark_positions(line) if marks else None)
    return o.answer(ask)


def test_a_remembered_book_question_cannot_leak_as_a_fact():
    """Four arms, because each half of the pair is blind without the other.

    The leak is not a hypothesis: with the channel OFF the house recites the book's own
    question back as an answer, source `recalled proposition`. Admissibility ON does not
    stop it -- the mark was stripped at tokenization, so the gate has no idea what it is
    looking at. The channel alone tags the row and still speaks it: a tag is not a
    refusal, it is knowledge the mouth may or may not consult. Only the pair refuses, and
    refuses with the reason that names the asking.
    """
    for line, ask in LEAK:
        quoted = " ".join(book_toks(line))
        naked = _leak_arm(line, ask, marks=False, admissible=False)
        assert naked.get("spoken") and naked.get("utterance") == quoted, naked
        gate_only = _leak_arm(line, ask, marks=False, admissible=True)
        assert gate_only.get("utterance") == quoted, \
            "admissibility alone stopped something, so this is not the pair's doing"
        tag_only = _leak_arm(line, ask, marks=True, admissible=False)
        assert tag_only.get("utterance") == quoted, \
            "the tag alone was already refusing -- the gate is not what closes this"
        closed = _leak_arm(line, ask, marks=True, admissible=True)
        assert not closed.get("spoken"), closed
        assert closed.get("reason") == "what he remembers there is only the asking itself"


def test_the_tag_reaches_the_hit_dict_the_mouth_reads():
    """The store is not the mouth. A tag that dies between a cortex row and the binder's
    hit dict would leave every row-level count green while the house went on reciting
    questions -- precisely the hole a malformed probe fell into by accident while this
    was being written, and why the propagation is pinned rather than assumed.
    """
    line = LEAK[0][0]
    o = _organ(marks=True, admissible=True)
    o.live(" ".join(book_toks(line)), speaker="book", learn=True,
           ask_marks=nl.question_mark_positions(line))
    content = [w for w in book_toks(line)
               if not o.is_interrogative(w) and o._speakable(w)]
    hits = o.cortex.binder.recall(content, k=40)
    assert hits, "nothing was recalled, so this test would prove nothing"
    assert all(o._hit_is_ask(h) for h in hits), [h["tokens"] for h in hits]
    assert all(h.get("ask") for h in hits), "the binder dropped the tag"
