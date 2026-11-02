"""ELECTRIC_ASK_SHAPE_STORE: shape authority at the `_taught_says` WRITE.

The hole this closes was measured, not theorised (docs/STATE.md, ELECTRIC_TEACH entry;
tools/qa_teach_hole_live.py in a real house): a question the house has not earned a question
word for is HEARD as a statement, `_absence_note` extracts a frame from its words because its
extractor reads by position, and the question is filed in `_taught_says` -- the one store that
is consulted before every other. The house then answers `what rings the bell` with
`what rings the bell twice`, the other person's unanswered question.

The tests below are the three claims that matter, in the order they cost something:

  * it closes the hole (the question is not filed; the real answer is the one that comes back);
  * it does not eat a STATEMENT to do it -- the relative clauses and the genuine statements
    `question_shape` is documented to reject are still filed, and the cap it inherits from the
    row tagger is proved to be the BINDER's cap and not a length this guard invented;
  * it does not move the graded contract: `_absence_inv`, the licence's reason string, the
    cortex rows and the QA store are identical with the guard on and off.

Plus the two ways a guard like this fails silently: throwing (it must fail OPEN -- a guard that
deletes a fact by crashing is worse than the hole) and the residual `question_shape` cannot
separate (a short free-relative statement), which is pinned as a measured cost rather than
left in a comment.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import organs.neural_language as nl                        # noqa: E402
import tools.electric_teach_mode as tm                     # noqa: E402
from connectome.engine import HybridEngine                 # noqa: E402
from connectome.substrate import build_core_graph          # noqa: E402
from organs.tokenizer import TokenizerOrgan                # noqa: E402

GUARD = "ELECTRIC_ASK_SHAPE_STORE"

PAIRS = [("what rings the bell?", "the copper bell rings"),
         ("what holds the door?", "the latch holds the door")]
KEY, ANSWER = "what rings the bell", "the copper bell rings"
HOLE_ASK = "what rings the bell twice"          # no pair covers it; it used to be filed

# The pair the guarded admission refuses, from tests/test_electric_qa_elicit.py: `lantern` was
# told (it belongs to Mira) but no PLACE was ever told for it.
GUARD_TELLS = ["the lantern belongs to Mira", "the scarf is on the hook"]
GUARD_ASK = "where did i say the lantern is?"

# Rows whose SHAPE is an ask. Each one yields a frame -- asserted below, because a row that
# would file nothing either way proves nothing about a guard that declines filings.
QUESTION_SHAPED = [
    "who rings the bell",
    "what rings the bell twice",
    "who carries droso tomorrow",
    "what bites the latch",
    "who does the lantern belong to",
]

# Rows that are statements. Every one yields a frame; none may be declined.
GENUINE_STATEMENTS = [
    "the copper bell rings",                       # declarative, no interrogative at all
    "he knows who rings the bell",                 # relative clause MID-sentence
    "the man who rings the bell keeps the gate",   # ditto, and longer than the cap
    "what the loop does is measure time",          # subject right after the question word
    "what matters most is the latch",              # copula after the subject clause
    "where the state lives is irrelevant",         # the docstring's own two examples
    "what came next was silence",                  # free relative with a copula in the tail
    "whoever rings the bell keeps the gate",       # `whoever` is not in the arbiter's set
    "when the bell rings twice the keeper wakes",  # `when` is not either
]

# The class the CAP is there for: a relative clause that happens to open a line, long enough
# that the row tagger's own audit found it (`who sacrificed everything for him chimed in the`).
RELATIVE_CLAUSES = [
    "who sacrificed everything for him chimed in the ledger",
    "who carried the lantern down to the gate and never came back",
]


def _organ(guard=None, base=True):
    """A bare organ with `--electric` (always) and, optionally, the store guard.

    `guard=None` means "whatever the class default is", which is OFF: the configuration every
    number in this repo was measured in. True/False set it on the INSTANCE, never on the class.
    """
    o = nl.NeuralLanguage(HybridEngine(graph=build_core_graph()), TokenizerOrgan())
    o.persist = False
    o.cortex.MIN_HEAR_INTERVAL_S = 0.0
    o.exposure_enabled = False
    if base:
        for attr in tm.BASE_ATTRS:
            setattr(o, attr, True)
    if guard is not None:
        setattr(o, GUARD, bool(guard))
    for t in GUARD_TELLS:
        o.hear(t, speaker="you")
    return o


def _filed(o):
    return {v for sub in o._taught_says.values() for v in sub.values()}


def _say(o, text):
    r = o.respond(text, speaker="you") or {}
    return {"held": bool(o._qa_pending),
            "src": str(r.get("source") or ""),
            "said": str(r.get("utterance") or r.get("response") or "").strip(),
            "refused": bool(r.get("licensed_refusal"))}


def _teach(o, pairs=PAIRS):
    for ask, ans in pairs:
        _say(o, ask)
        _say(o, ans)
        o._qa_pending = None
    return o


# --------------------------------------------------------------- the flag itself ----

def test_the_flag_is_off_on_the_class_and_only_ever_set_on_the_instance():
    assert nl.NeuralLanguage.ELECTRIC_ASK_SHAPE_STORE is False, \
        "a battery run reads ELECTRIC off the class; a default of True would be a widening " \
        "nobody opted into"
    o = _organ()
    assert o.ELECTRIC_ASK_SHAPE_STORE is False
    _organ(guard=True)
    assert nl.NeuralLanguage.ELECTRIC_ASK_SHAPE_STORE is False, \
        "turning the guard on for one organ turned it on for the interpreter"


def test_every_battery_row_really_yields_a_frame():
    """The premise of both batteries below. A row that extracts no frame files nothing whether
    the guard runs or not, and a test over it would pass for a reason that has nothing to do
    with the guard -- so the frames are asserted, not assumed."""
    for row in QUESTION_SHAPED + GENUINE_STATEMENTS + RELATIVE_CLAUSES:
        assert nl._absence_frame(row) is not None, f"{row!r} would file nothing either way"


# ------------------------------------------------------------------- the hole ----

def test_off_it_files_the_question_that_answers_itself():
    """The pre-fix configuration, kept as a test rather than deleted: this is what was measured
    in the live house, and if it stops reproducing something else moved the hole."""
    o = _organ(guard=False)
    o.hear(HOLE_ASK, speaker="you")
    assert HOLE_ASK in _filed(o), f"the question was not filed with the guard off: {_filed(o)}"


def test_on_it_refuses_a_question_shaped_tell():
    o = _organ(guard=True)
    o.hear(HOLE_ASK, speaker="you")
    assert HOLE_ASK not in _filed(o), \
        f"the guard let a question be filed as a fact: {_filed(o)}"


def test_on_it_refuses_every_question_shaped_tell_in_the_battery():
    o = _organ(guard=True)
    for row in QUESTION_SHAPED:
        o.hear(row, speaker="you")
    filed = _filed(o)
    lost = [r for r in QUESTION_SHAPED if r in filed]
    assert not lost, f"still filed as taught facts: {lost}"


def test_the_closing_is_the_guard_and_nothing_else():
    """Same organ, same sentence, one switch apart -- and the difference is visible in the
    store, not inferred from a flag read."""
    off, on = _organ(guard=False), _organ(guard=True)
    off.hear(HOLE_ASK, speaker="you")
    on.hear(HOLE_ASK, speaker="you")
    assert HOLE_ASK in _filed(off) and HOLE_ASK not in _filed(on)
    assert _filed(on) == _filed(off) - {HOLE_ASK}, \
        f"the guard changed more than the one filing: off={sorted(_filed(off))} " \
        f"on={sorted(_filed(on))}"


def test_a_closed_hole_leaves_the_real_answer_to_come_back():
    """The symptom, end to end: teach ONE pair (so `what` has one vote and is not yet a
    question word), let the unanswered question be heard, then ask the pair. Before the guard
    the house replies with the other question, from `electric_taught`."""
    outs = {}
    for guard in (False, True):
        o = _organ(guard=guard)
        tm.enable(o)                                   # the mode, minus nothing
        setattr(o, GUARD, guard)                       # the one switch this test is about
        _teach(o, PAIRS[:1])
        _say(o, HOLE_ASK)
        outs[guard] = _say(o, KEY)
    assert not outs[False]["said"].startswith("the copper"), outs[False]
    assert outs[True]["said"] == ANSWER, \
        f"the guard did not return the answer to the store: {outs[True]}"
    assert outs[True]["src"] == "electric_qa_store", outs[True]


def test_a_marked_ask_told_without_elicitation_is_refused_too():
    """`hear` already declines to note a marked ask when elicitation is on. With elicitation OFF
    the same sentence reaches `_absence_note` -- and shape authority is the only thing left that
    can see it. The frame still lands in the inventory; only the sentence is not kept."""
    o = _organ(guard=True)
    o.hear("who rings the bell?", speaker="you")
    assert "who rings the bell?" not in _filed(o), _filed(o)
    assert "rings" in o._absence_inv, "the grader's input moved, which this flag may not do"


# ------------------------------------------------- what it must NOT eat: statements ----

def test_genuine_statements_are_still_filed():
    """Each of these is a sentence somebody told him, and each is a class `question_shape` is
    documented to reject: a relative clause in the middle of a row, a subject right after the
    question word, a copula later, a question word that is not in the arbiter's set at all."""
    o = _organ(guard=True)
    for row in GENUINE_STATEMENTS:
        o.hear(row, speaker="you")
    filed = _filed(o)
    lost = [r for r in GENUINE_STATEMENTS if r not in filed]
    assert not lost, f"the guard ate {len(lost)} statement(s): {lost}"


def test_relative_clauses_are_still_filed():
    """The measured mis-fire class, and the reason the guard inherits the row tagger's cap
    instead of inventing its own: a line longer than `max_roles` that opens with `who` is prose
    with a relative clause in it, and declining a WRITE loses a fact silently."""
    o = _organ(guard=True)
    mr = int(o.cortex.binder.max_roles)
    for row in RELATIVE_CLAUSES:
        assert len([t for t in o.tokenizer.tokenize(row) if t]) > mr, \
            f"{row!r} is no longer past the cap, so this test no longer tests the cap"
        o.hear(row, speaker="you")
    filed = _filed(o)
    lost = [r for r in RELATIVE_CLAUSES if r not in filed]
    assert not lost, f"the guard ate a relative clause: {lost}"


def test_the_boundary_is_the_binders_cap_not_a_length_this_guard_invented():
    """Same sentence, same flag, one number apart -- and the number is the BINDER's. Lower the
    cap below the row's length and the guard stands off, because the row is now prose-shaped by
    the same rule the row tagger uses; leave the cap where the house puts it and the row is
    short enough to be an ask."""
    row = "who rings the bell keeps the gate"
    keep = _organ(guard=True)
    keep.cortex.binder.max_roles = 3
    keep.hear(row, speaker="you")
    assert row in _filed(keep), \
        "the guard has its own length rule; it is supposed to read the binder's"
    house = _organ(guard=True)
    assert len(row.split()) <= int(house.cortex.binder.max_roles)
    house.hear(row, speaker="you")
    assert row not in _filed(house), "with the house cap the short free relative is declined"


def test_measured_the_short_free_relative_statement_is_declined_too():
    """THE RESIDUAL, pinned rather than smoothed over. `who rings the bell keeps the gate` is
    seven tokens, opens with a word in the arbiter's set, and has neither a subject nor a copula
    after it -- `question_shape` has nothing to separate it from the ask `who rings the bell`,
    and neither does this guard. So a statement of that shape is not filed as a taught fact.

    What that costs, measured here rather than argued: the PAIR, not the row and not the
    inventory entry. The cortex still holds the sentence, `_absence_inv` still holds the frame
    the grader reads, and the answer the filing would have given was itself wrong -- the frame
    it files is ('agent','rings','bell keeps gate'), a subject slot holding the verb, which is
    the same misparse the hole is made of. Whoever wants that class back has to give
    `question_shape` a predicate that can see a second predicate, and this test is where they
    will look for it.
    """
    row = "who rings the bell keeps the gate"
    o = _organ(guard=True)
    rows_before = len(o.cortex.binder.meta)
    o.hear(row, speaker="you")
    assert row not in _filed(o), "the residual closed on its own; re-measure this test"
    assert nl._absence_frame(row) == ("agent", "rings", "bell keeps gate"), \
        "the frame the guard declines to file is not the one measured here"
    assert "rings" in o._absence_inv, "the inventory entry went too -- that is the graded store"
    assert len(o.cortex.binder.meta) > rows_before, "the row went too"


# ------------------------------------------------------------------ fail open ----

def test_the_guard_fails_open_when_its_inputs_cannot_answer():
    """A guard that can delete a fact by crashing is worse than the hole it closes, so every
    failure mode answers "not an ask". Tested on the guard's own predicate rather than through
    `hear`, because the two dependencies it reads are the organ's OWN: a tokenizer that throws
    takes down the whole turn, guard or no guard, and that is a different claim than this one.

    The third case is not a failure mode and is asserted the other way on purpose: no binder
    means no CAP, not no guard. A house with nothing to measure the row against runs the
    detector, which is what the row tagger does with the same missing number.
    """
    boom = lambda toks: (_ for _ in ()).throw(RuntimeError("boom"))  # noqa: E731
    o = _organ(guard=True)
    o.question_shape = boom
    assert o._shape_files_as_ask(HOLE_ASK) is False
    assert o.hear(HOLE_ASK, speaker="you") and HOLE_ASK in _filed(o), \
        "a throwing detector deleted a fact from the turn it was guarding"

    p = _organ(guard=True)
    p.tokenizer.tokenize = boom
    assert p._shape_files_as_ask(HOLE_ASK) is False, "a throwing tokenizer must not delete"

    q = _organ(guard=True)
    q.cortex.binder = None
    assert q._shape_files_as_ask(HOLE_ASK) is True, "no binder is no cap, not no guard"


def test_hearing_a_question_shaped_tell_does_not_throw():
    """`hear` calls `_absence_note` outside any try of its own. If the guard could raise, the
    whole turn would die -- so the turn is what is asserted here, not the store."""
    o = _organ(guard=True)
    r = o.hear(HOLE_ASK, speaker="you")
    assert isinstance(r, dict) and "thought" in r, r


# --------------------------------------------------- what it must not move: the rest ----

def test_the_graders_input_is_identical_with_the_guard_on_and_off():
    """`_absence_inv` is what E24's licence reads, and the guard sits AFTER it. Same battery of
    utterances, same inventory, key for key, in both arms -- the graded contract is untouched."""
    battery = QUESTION_SHAPED + GENUINE_STATEMENTS + RELATIVE_CLAUSES + [GUARD_ASK]
    inv = {}
    for guard in (False, True):
        o = _organ(guard=guard)
        for row in battery:
            o.hear(row, speaker="you")
        inv[guard] = {s: {r: set(v) for r, v in d.items()}
                      for s, d in o._absence_inv.items()}
    assert inv[True] == inv[False], \
        "the guard moved the inventory the graded absence work reads"


def test_the_licensed_refusal_is_the_same_words_in_both_arms():
    outs = {}
    for guard in (False, True):
        o = _organ(guard=guard)
        r = o.answer(GUARD_ASK, speaker="you")
        r = r if isinstance(r, dict) else {"response": r}
        outs[guard] = {k: r.get(k) for k in ("spoken", "source", "licensed_refusal", "reason")}
    assert outs[True]["licensed_refusal"] is True, outs
    assert outs[True]["source"] == "electric_absence", outs
    assert outs[True] == outs[False], f"the guard changed what the house ADMITS: {outs}"


def test_the_guard_writes_no_row_and_no_pair_the_other_arm_did_not():
    """Both arms, same battery, deltas compared -- and the same battery is what makes the
    comparison mean anything: two organs built the same way start even (asserted), so a row
    difference can only come from the turns between the two counts."""
    battery = QUESTION_SHAPED + GENUINE_STATEMENTS + RELATIVE_CLAUSES
    delta, stores = {}, {}
    for guard in (False, True):
        o = _organ(guard=guard)
        tm.enable(o)
        setattr(o, GUARD, guard)
        n0 = len(o.cortex.binder.meta)
        for row in battery:
            o.hear(row, speaker="you")
        delta[guard] = len(o.cortex.binder.meta) - n0
        stores[guard] = dict(o.qa_store)
        assert not o.qa_store, "a told question reached the QA store, which is not this flag"
    assert delta[True] == delta[False], \
        f"the guard changed the number of rows: on={delta[True]} off={delta[False]}"


def test_the_teach_write_still_happens_for_the_answer_turn():
    """The guard must not become a rule about turns. A pair taught in chat: the ASK is refused
    (it is a question), the ANSWER is filed (it is a tell) -- with the mode on, which is the
    configuration users actually run."""
    o = _organ(guard=True)
    tm.enable(o)
    _teach(o, PAIRS[:1])
    filed = _filed(o)
    assert ANSWER in filed, f"the answer turn was not taught: {sorted(filed)}"
    assert KEY not in filed and not any(k.endswith("?") for k in filed), \
        f"a question was filed after all: {sorted(filed)}"


# ------------------------------------------------------------------ the wiring ----

def test_teach_mode_carries_the_guard_and_warns_without_electric():
    assert GUARD in tm.STACK_ATTRS, "the mode does not carry the fix; the hole is still open"
    o = tm.enable(nl.NeuralLanguage(HybridEngine(graph=build_core_graph()), TokenizerOrgan()))
    assert o is not None
    on = tm.state(_organ())
    assert on[GUARD] is False, "the base --electric bundle turns the guard on by itself"
    assert GUARD in tm.DEPENDS_ON and tm.DEPENDS_ON[GUARD][0] == "ELECTRIC_TEACH"
    bare = {a: False for a in tm.ALL_ATTRS}
    bare[GUARD] = True
    assert tm.unmet(bare) == [tm.DEPENDS_ON[GUARD][1]], "an inert guard is silent"


def _serve_text():
    return (ROOT / "tools" / "serve.py").read_text(encoding="utf-8")


def test_serve_wires_the_guard_inside_the_electric_block_and_cannot_clobber_the_mode():
    """Two contracts in the wiring, both of which a tidy refactor would break:

  * the assignment sits AFTER `if args.electric:` set ELECTRIC_TEACH, because the guard is
    inert without it -- wiring it outside, like the QA switches, would make `--electric
    --electric-ask-shape-store` print a warning about a parent that is on;
  * it is `bool(args...) or teach`, not `bool(args...)`: the mode already turned the guard on
    several lines earlier, and a plain assignment would switch the mode's own fix back off.
    """
    src = _serve_text()
    line = next((l for l in src.splitlines()
                 if "ELECTRIC_ASK_SHAPE_STORE" in l and "args" in l), None)
    assert line, "serve.py never wires the flag"
    assert "or teach" in line, line
    block = src[src.index("    if args.electric:"):]
    assert "ELECTRIC_ASK_SHAPE_STORE" in block, \
        "the guard is wired outside --electric, where its parent is not yet set"
    assert src.index(line) > src.index("        lang.ELECTRIC_TEACH = True"), \
        "the guard is wired before its parent, so the inert-flag warning would lie"


def test_cli_flag_turns_the_guard_on_and_the_mode_implies_it(tmp_path):
    st = tmp_path / "neural_lang.json"

    def say(text, *flags):
        p = subprocess.run([sys.executable, str(ROOT / "tools" / "electric_chat.py"),
                            "--state", str(st), "--say", text, *flags],
                           capture_output=True, text=True, timeout=600, cwd=str(ROOT))
        assert p.returncode == 0, f"exit {p.returncode}\n{p.stdout}\n{p.stderr}"
        return json.loads([l for l in p.stdout.splitlines() if l.startswith("{")][-1])

    # This tool's ELECTRIC switch is the ABSENCE of --no-electric; there is no `--electric`.
    out = say("+" + HOLE_ASK)
    assert out["boot"]["electric"] is True and out["boot"]["ask_shape_store"] is False, out
    assert out["taught_this_turn"] == 1, \
        "the control arm stopped reproducing the hole, so this test no longer pins anything"

    out = say("+" + HOLE_ASK, "--electric-ask-shape-store")
    assert out["boot"]["ask_shape_store"] is True, out["boot"]
    assert out["taught_this_turn"] == 0, \
        f"the guard was wired but the question was still filed: {out}"

    out = say("+" + HOLE_ASK, "--electric-teach")
    assert out["boot"]["ask_shape_store"] is True and out["boot"]["teach"] is True, out["boot"]
    assert out["taught_this_turn"] == 0, f"the mode does not carry the fix: {out}"


def test_typing_electric_in_the_chat_tool_now_means_electric(tmp_path):
    """`--electric` was never an option of electric_chat.py. Argparse resolved it as a PREFIX of
    `--electric-teach`, so a person typing the ELECTRIC switch got the whole teach stack and had
    no say in it -- and once a second `--electric-*` option existed, that prefix was ambiguous and
    the same typing was exit 2. Both outcomes are wrong, so the name is now declared exactly: it
    affirms the default and teaches nothing. Pinned because the silent version was a trap and the
    loud version was a regression, and a repair that leaves neither is the whole point."""
    st = tmp_path / "neural_lang.json"

    def run(*flags):
        p = subprocess.run([sys.executable, str(ROOT / "tools" / "electric_chat.py"),
                            "--state", str(st), "--say", "+the bell rings", *flags],
                           capture_output=True, text=True, timeout=600, cwd=str(ROOT))
        assert p.returncode == 0, f"exit {p.returncode}\n{p.stdout}\n{p.stderr}"
        return p, json.loads([l for l in p.stdout.splitlines() if l.startswith("{")][-1])

    p, out = run("--electric")
    assert out["boot"]["electric"] is True, out["boot"]
    assert out["boot"]["teach"] is False, f"`--electric` is still an abbreviation of teach: {out}"
    assert out["boot"]["ask_shape_store"] is False, out
    assert "ambiguous" not in p.stderr, p.stderr

    # An affirmation of what is already on carries no information, so the CONTROL wins a conflict
    # and the person is told about it -- typing both can never lose the arm you asked for.
    p, out = run("--electric", "--no-electric")
    assert out["boot"]["electric"] is False, f"the control arm was overridden: {out}"
    assert "--electric with --no-electric" in p.stderr, p.stderr

    # serve.py always had the exact name; nothing about its behaviour moved with this.
    src = (ROOT / "tools" / "serve.py").read_text(encoding="utf-8")
    assert 'add_argument("--electric", action="store_true"' in src, \
        "serve.py no longer declares --electric exactly, so its abbreviation story changed too"
    help_out = subprocess.run([sys.executable, str(ROOT / "tools" / "electric_chat.py"),
                               "--help"], capture_output=True, text=True, timeout=600,
                              cwd=str(ROOT))
    assert "--electric-ask-shape-store" in help_out.stdout, help_out.stdout
