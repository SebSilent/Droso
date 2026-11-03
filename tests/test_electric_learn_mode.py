"""ELECTRIC LEARN mode -- the FULL teach/learn stack in one switch, and what it must not cost.

`--electric-teach` is the stack that can only ever REFUSE: a row dropped from the evidence, a
fragment left unspoken, a write declined. `--electric-learn` is that stack plus the seven switches
it was built to leave out -- ELECTRIC_ASK_SHAPE, ELECTRIC_REVERSE, ELECTRIC_OBJECT_ROLE,
ELECTRIC_ASK_NORMALIZE, ELECTRIC_ASK_DO_SUPPORT, ELECTRIC_QA_ANSWER_MEMORY,
ELECTRIC_ARBITER_TELL -- each of which can only ever REACH MORE: more
rows counted as an asking, more asks matched against the inventory, more phrasings folded onto one
key, more of what the house already holds spoken as a whole sentence.

Why a test file and not just a wider default. A mode that turns on eighteen switches at once is the
configuration where an interaction is most likely and least attributable, and every one of these
widenings was measured alone precisely so a run could say which one cost something (docs/STATE.md:
C4d for reverse vs object-role, the ELECTRIC_ASK_SHAPE entry for the shape tagger, the
ELECTRIC_ASK_NORMALIZE entry for the fold). So this file asserts three things and only three:

  * the SET is the set -- learn mode is teach mode's superset, exactly the five named widenings
    wider, and nothing is on the class (the graded contract binds `_absence_licence` on the class
    defaults, so a mode that flipped one of them would change the battery's answers while looking
    like a demo flag);
  * the mode cannot LIE about itself -- `_set` checks each name against the class before setting
    any of them, because `setattr` on an instance never raises for an unknown name and a run that
    reports sixteen flags while eleven are real is worse than a run that reports fewer;
  * what it says is still ONLY what it was told -- every reply in every arm is a verbatim taught
    tell, a stored pair answer, or a licensed refusal. That invariant is the one that survives all
    six widenings at once, and it is the one the grader cares about.

What is deliberately NOT asserted here: which widening earned which answer. That is
tools/electric_learn_live.py, which runs the arms side by side in a real house and writes
docs/evidence/electric_learn_live.json. A boolean test that re-derives attribution from a house
boot would be a flake with a docstring attached.
"""
import json
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "electric_chat.py"
sys.path.insert(0, str(ROOT))

import organs.neural_language as nl                        # noqa: E402
import tools.electric_teach_mode as tm                     # noqa: E402
from connectome.engine import HybridEngine                 # noqa: E402
from connectome.substrate import build_core_graph          # noqa: E402
from organs.tokenizer import TokenizerOrgan                # noqa: E402

# Captured at import, before any organ exists: the class defaults the graded contract binds
# against. Every test below that touches the class compares to THIS, not to a remembered value.
CLASS_DEFAULTS = {a: getattr(nl.NeuralLanguage, a, "<absent>") for a in tm.ALL_ATTRS}

PAIRS = [("what rings the bell?", "the copper bell rings"),
         ("what holds the door?", "the latch holds the door")]
ANSWER = "the copper bell rings"
FOLD = "what ring the bell"                  # never taught: the project's one stemmer reaches it
UNTAUGHT = "where is the moon"               # no pair, no tell, nothing to say

# The two asks the widenings were built for, each taken from the flag's own docstring and its own
# test file, so this file is not inventing a shape the mechanism never claimed to reach.
OBJECT_TELL = "the dog bites the latch"
OBJECT_ASK = "what bites the latch?"         # names the tell's OBJECT, wants its SUBJECT
REVERSE_TELL = "the lantern belongs to Mira"
REVERSE_ASK = "who does the lantern belong to?"   # stranded preposition: the only marker

# The SAME asks without the mark, and the reason they exist: elicitation is in the stack, so a
# tell ending in `?` is HELD -- the answer is the next thing the speaker says, not a reply to this
# turn. A test that asked in the marked form and asserted an answer would be asserting that the
# protocol is broken. Unmarked, the ask goes to the answer path, and ELECTRIC_ASK_SHAPE is what
# still lets the organ tell it from a statement -- which is the widening's actual job.
OBJECT_ASK_BARE = "what bites the latch"
REVERSE_ASK_BARE = "who does the lantern belong to"
NORMALIZE_ASKS = ["who is the lantern with?", "what was the door opened by?",
                  "who was the lantern given to?"]

TELLS = [t for p in PAIRS for t in p] + [OBJECT_TELL, REVERSE_TELL]

STRANDED = "who does the mouse chase to?"    # the row whose remembered form used to speak `to?`
BARE = "who does the mouse chase?"


def _organ(learn=True, base=True):
    """A bare organ with `--electric` plus one of the two modes.

    Same discipline as the teach-mode file's `_organ`: no persistence, no wall-clock throttle, no
    exposure rows, and the mode applied through the table rather than by hand, so a change to the
    table moves these tests and a change to a test does not move the mode.
    """
    o = nl.NeuralLanguage(HybridEngine(graph=build_core_graph()), TokenizerOrgan())
    o.persist = False
    o.cortex.MIN_HEAR_INTERVAL_S = 0.0
    o.exposure_enabled = False
    if base:
        for attr in tm.BASE_ATTRS:
            setattr(o, attr, True)
    if learn:
        tm.enable_learn(o, base=base)
    return o


def _say(o, text):
    r = o.respond(text, speaker="you") or {}
    return {"held": bool(o._qa_pending),
            "src": str(r.get("source") or ""),
            "said": str(r.get("utterance") or r.get("response") or "").strip(),
            "refused": bool(r.get("licensed_refusal"))}


def _ask(o, q):
    """The ANSWER path, not the speaking path. Measured, and the difference matters here:
    `respond` on a bare organ can return `spoken: False, reason: 'heard; no language learned
    yet'` for an ask the inventory answers perfectly, because a bare organ has no corpus behind
    its word knowledge. Every reach claim below is therefore made through `answer()`, which is the
    door the widenings actually open, and the live house check (tools/electric_learn_live.py) is
    where the speaking is checked."""
    r = o.answer(q) or {}
    return {"answered": bool(r.get("answered")), "src": str(r.get("source") or ""),
            "said": str(r.get("utterance") or r.get("response") or "").strip(),
            "reason": str(r.get("reason") or "")}


def _teach(o, pairs=PAIRS, tells=TELLS):
    """Facts first, then the pairs -- a tell is one utterance, a pair is an ask plus the NEXT
    thing the same speaker says, and `_qa_pending` has to be cleared between pairs."""
    for t in tells:
        _say(o, t)
        o._qa_pending = None
    for ask, ans in pairs:
        _say(o, ask)
        _say(o, ans)
        o._qa_pending = None
    return o


def say_cli(text, state, *extra):
    p = subprocess.run([sys.executable, str(TOOL), "--state", str(state),
                        "--say", text, *extra],
                       capture_output=True, text=True, timeout=300, cwd=str(ROOT))
    assert p.returncode == 0, f"exit {p.returncode}\n{p.stdout}\n{p.stderr}"
    line = [l for l in p.stdout.splitlines() if l.startswith("{")][-1]
    return json.loads(line), p.stderr


def _post(base, path, obj):
    req = urllib.request.Request(base + path, data=json.dumps(obj).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read().decode("utf-8"))


# ------------------------------------------------------------------ the set ----

def test_learn_is_the_stack_plus_exactly_the_six_widenings():
    assert tm.LEARN == tm.STACK + tm.EXCLUDED, \
        "the full mode is defined as the stack plus the widenings, not as a third list"
    assert tm.LEARN_ATTRS == tm.STACK_ATTRS + tm.EXCLUDED_ATTRS
    # Every attribute must be ACCOUNTED FOR -- but MP-E9 proved that accounted-for is not the same as
    # reachable. Its three flags live in CANDIDATE, which no enable*() function reads, so they are in
    # ALL_ATTRS and in no mode. That is the mechanical form of "proven, NOT enabled"
    # (experiments/MP-E9/decision.md 7.1, D-MPE9-05), so the invariant is stated with CANDIDATE named
    # as the unreachable set rather than by pretending LEARN and BASE cover everything.
    assert set(tm.LEARN_ATTRS) | set(tm.BASE_ATTRS) | set(tm.CANDIDATE_ATTRS) == set(tm.ALL_ATTRS)
    unreachable = [a for a in tm.ALL_ATTRS
                   if a not in tm.STACK_ATTRS + tm.EXCLUDED_ATTRS + tm.BASE_ATTRS]
    assert set(unreachable) == set(tm.CANDIDATE_ATTRS), \
        f"attributes reachable by no mode: {unreachable}"
    assert set(tm.EXCLUDED_ATTRS) == {"ELECTRIC_ASK_SHAPE", "ELECTRIC_REVERSE",
                                      "ELECTRIC_OBJECT_ROLE", "ELECTRIC_ASK_NORMALIZE",
                                      "ELECTRIC_ASK_DO_SUPPORT",
                                      "ELECTRIC_QA_ANSWER_MEMORY",
                                      "ELECTRIC_ARBITER_TELL"}


def test_learn_mode_turns_on_everything_and_nothing_on_the_class():
    before = dict(CLASS_DEFAULTS)
    o = _organ()
    st = tm.state(o)
    assert all(st[a] for a in tm.LEARN_ATTRS + tm.BASE_ATTRS), \
        {a: st[a] for a in tm.LEARN_ATTRS + tm.BASE_ATTRS if not st[a]}
    # The graded contract: the class is what `_absence_licence` binds on, and a battery run in the
    # same interpreter reads it, not this organ.
    assert {a: getattr(nl.NeuralLanguage, a, "<absent>") for a in tm.ALL_ATTRS} == before, \
        "a demo mode moved a class default; every battery number after this is suspect"


def test_learn_mode_is_teach_mode_wider_by_exactly_the_widenings():
    # Both arms built through the table, from the same base, so the difference is the mode and
    # not the order in which the flags were set.
    a, b = _organ(learn=False), _organ(learn=False)
    tm.enable(a)
    tm.enable_learn(b)
    narrow, full = tm.state(a), tm.state(b)
    diff = sorted(a for a in tm.ALL_ATTRS if narrow[a] != full[a])
    assert diff == sorted(tm.EXCLUDED_ATTRS), \
        f"the two modes differ by something other than the widenings the table names: {diff}"


def test_a_flag_the_organ_does_not_read_raises_instead_of_lying():
    """`setattr` on an instance accepts ANY name. A mode that turns on eighteen switches must not
    be able to report seventeen and behave like the eleven that are real, so an unknown name raises
    before a single attribute is set, so a half-applied mode cannot exist."""
    o = _organ(learn=False)
    before = o.ELECTRIC_TEACH
    try:
        tm._set(o, ("ELECTRIC_TEACH", "ELECTRIC_NOT_A_FLAG"))
    except AttributeError as exc:
        assert "ELECTRIC_NOT_A_FLAG" in str(exc), exc
    else:
        raise AssertionError("an invented flag was accepted; the mode can report what is not there")
    assert o.ELECTRIC_TEACH == before, "the raise came after the write: a half-applied mode"
    assert not hasattr(o, "ELECTRIC_NOT_A_FLAG")


def test_the_full_mode_leaves_no_flag_inert():
    o = _organ()
    assert tm.warnings(o) == [], \
        f"the combination has a dangling dependency: {tm.warnings(o)}"


def test_describe_learn_marks_which_lines_reach_more():
    lines = tm.describe_learn()
    assert len(lines) == len(tm.STACK) + len(tm.EXCLUDED)
    widens = [l for l in lines if l.startswith("WIDENS")]
    assert len(widens) == len(tm.EXCLUDED), \
        "a count written here instead of read from the table is how a widening goes unmarked"
    for attr in tm.EXCLUDED_ATTRS:
        assert any(attr in l for l in widens), f"{attr} is on and not marked as a widening"
    assert not any(l.startswith("WIDENS") for l in tm.describe()), \
        "the narrow mode must not claim a widening it refuses"


# ---------------------------------------------------------------- the wiring ----

def test_both_doors_read_the_one_table_and_neither_re_lists_it():
    serve = (ROOT / "tools" / "serve.py").read_text(encoding="utf-8")
    chat = (ROOT / "tools" / "electric_chat.py").read_text(encoding="utf-8")
    for src, name in ((serve, "serve.py"), (chat, "electric_chat.py")):
        assert 'add_argument("--electric-learn", action="store_true"' in src, name
        assert "electric_teach_mode.enable_learn(" in src, \
            f"{name} wires the mode by hand instead of through the table"
        # No door may keep its own copy of the widening list: that is the failure this project
        # keeps hitting, and it is the reason the table exists.
        assert not re.search(r"\(\s*\"ELECTRIC_ASK_SHAPE\"", src), \
            f"{name} duplicates the mode's attribute list"
    assert "electric_teach_mode.enable_learn(agent.language)" in serve
    assert "electric_teach_mode.enable_learn(lang)" in chat


def test_the_learn_flag_is_not_an_abbreviation_accident():
    """`--electric-teach` once swallowed `--electric` through argparse prefix matching. A new
    mode flag has to be checked through the real parser, not by reading the source."""
    for tool in (TOOL, ROOT / "tools" / "serve.py"):
        p = subprocess.run([sys.executable, str(tool), "--help"],
                           capture_output=True, text=True, timeout=300, cwd=str(ROOT))
        assert p.returncode == 0, p.stderr
        assert "--electric-learn" in p.stdout, tool.name
    for probe in ("--electric-l", "--electric-lea"):
        p = subprocess.run([sys.executable, str(TOOL), probe, "--say", "hello"],
                           capture_output=True, text=True, timeout=300, cwd=str(ROOT))
        assert "ambiguous" not in (p.stderr + p.stdout).lower(), (probe, p.stderr)


# --------------------------------------------------------------- what it says ----

def test_the_object_role_ask_returns_the_whole_tell_and_not_a_word_of_it():
    """The A/B is measured, not asserted: the narrow arm answers this shape from the SHAPE
    ARBITER -- `dog`, one word lifted out of the proposition -- while the full mode answers it
    from the tell it was actually given. Neither is invented; only one is a sentence."""
    full = _teach(_organ(), pairs=[], tells=[OBJECT_TELL])
    got = _ask(full, OBJECT_ASK_BARE)
    assert got["said"] == OBJECT_TELL, f"the widening that exists for this shape: {got}"
    assert got["src"] == "electric_taught", got
    narrow = _teach(_organ(learn=False), pairs=[], tells=[OBJECT_TELL])
    tm.enable(narrow)
    back = _ask(narrow, OBJECT_ASK_BARE)
    assert back["said"] != OBJECT_TELL, \
        f"the widening bought nothing here, so it should not be in the mode: {back}"


def test_the_reverse_ask_is_answered_with_the_verbatim_tell():
    full = _teach(_organ(), pairs=[], tells=[REVERSE_TELL])
    got = _ask(full, REVERSE_ASK_BARE)
    assert got["said"] == REVERSE_TELL, f"not the verbatim tell: {got}"
    assert got["said"] in ("", REVERSE_TELL), f"invented or echoed: {got}"
    narrow = _teach(_organ(learn=False), pairs=[], tells=[REVERSE_TELL])
    tm.enable(narrow)
    assert _ask(narrow, REVERSE_ASK_BARE)["said"] != REVERSE_TELL, \
        "reverse reached the same answer without the reverse flag"


def test_the_verbatim_answer_survives_a_house_full_of_remembered_questions():
    """Pinned because of what `tools/electric_restart_qrow.py` found: a narrow arm that has spent a
    life asking and being asked lifts ONE WORD out of this tell (`mira`) after a restart, where the
    same arm said nothing before it -- a reachability effect of accumulated question rows, reproduced
    in the CONTROL arm with no ELECTRIC flag on at all, and therefore not this mode's to fix.

    The claim that IS this mode's, and the only one pinned here, is that the full mode never takes
    that path: the keyed inventory answers first, before the questions pile up and after."""
    full = _teach(_organ(), pairs=[], tells=[REVERSE_TELL])
    before = _ask(full, REVERSE_ASK_BARE)
    assert before["said"] == REVERSE_TELL, before
    for q in ("who does the mouse chase to", "who does the bell report to",
              "where is the moon", REVERSE_ASK_BARE):
        _say(full, q)              # each of these leaves a question-shaped row in the pool
    after = _ask(full, REVERSE_ASK_BARE)
    assert after["said"] == REVERSE_TELL, \
        f"a pool of remembered questions moved the answer off the tell: {after}"
    assert after["src"] == "electric_taught", after


def test_a_marked_ask_is_held_and_the_next_sentence_becomes_its_answer():
    """The protocol interaction, pinned rather than assumed away: in the FULL mode a marked ask is
    held (elicitation is in the stack), so the widening tests above had to ask unmarked -- and if
    this ever stops holding, those tests are measuring the wrong turn."""
    o = _organ()
    got = _say(o, OBJECT_ASK)
    assert got["held"] and got["said"] == "", f"a marked ask was answered instead of held: {got}"
    _say(o, OBJECT_TELL)
    o._qa_pending = None
    out = _ask(o, OBJECT_ASK_BARE)
    assert out["said"] in ("", OBJECT_TELL), f"the pair it just formed invented something: {out}"


def test_a_pair_taught_in_learn_mode_answers_the_folded_ask():
    o = _teach(_organ())
    got = _ask(o, FOLD)
    assert got["said"] == ANSWER, got
    assert got["src"] == "electric_qa_store", got


def test_an_untaught_ask_is_refused_and_says_so():
    o = _teach(_organ())
    got = _ask(o, UNTAUGHT)
    assert not got["answered"], f"answered something it was never told: {got}"
    assert got["said"] == "" and got["said"] not in TELLS, got
    assert got["reason"], "a refusal with no reason is silence, not an admission"


def test_the_fragment_never_comes_out_of_the_learn_mode():
    """The leak the fragment guard was written for, end to end: remember the stranded variant,
    then ask the bare one. With the guard on -- and it is in the stack, so learn mode has it --
    the house may refuse, but it may not speak `to?`."""
    o = _organ()
    _say(o, STRANDED)
    o._qa_pending = None
    got = _ask(o, BARE)
    assert got["said"].strip() not in ("to?", "to"), f"the fragment spoke: {got}"
    assert not got["said"].endswith("?"), f"spoke the ask back at the asker: {got}"


def test_no_widening_invents_a_sentence():
    """The invariant that has to survive FOUR widenings at once: anything this mode says was said
    to it first. Every ask below is one the mechanism was not taught in that form."""
    o = _teach(_organ())
    bare = lambda q: q.rstrip("?")            # marked asks are HELD; see the note on *_BARE
    asks = [FOLD, OBJECT_ASK_BARE, REVERSE_ASK_BARE, UNTAUGHT,
            "what rings the bell tomorrow", "who does the bell report to",
            "where is the moon tonight"] + [bare(q) for q in NORMALIZE_ASKS]
    allowed = set(TELLS)
    for q in asks:
        got = _ask(o, q)
        if not got["answered"] or not got["said"]:
            continue
        assert got["said"] in allowed, f"{q!r} -> {got['said']!r}: a sentence nobody told it"


# ------------------------------------------------------------------ restart ----

def test_learn_mode_survives_a_real_restart_and_the_narrow_mode_can_read_it(tmp_path):
    """Two processes sharing nothing but the state file: teach facts and pairs under the full
    mode, shut down cleanly, come back -- and ask the three shapes the widenings exist for, plus
    one nobody ever taught. The restart half is checked in BOTH modes, because the store is the
    mode-independent part: a pair saved by learn mode must still answer under teach mode, and an
    untaught ask must still be refused there.

    /shutdown rather than terminate(): on Windows terminate() skips the `finally` block, and a
    persistence claim that rested on it would be testing nothing."""
    st = tmp_path / "neural_lang.json"
    proc = subprocess.Popen([sys.executable, str(TOOL), "--state", str(st),
                             "--electric-learn", "--port", "0"],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, cwd=str(ROOT))
    try:
        port, line = None, ""
        t0 = time.time()
        while time.time() - t0 < 240:
            line = proc.stdout.readline()
            if not line:
                break
            if "ready port=" in line:
                port = int(line.split("ready port=")[1].split()[0])
                break
        assert port, f"the learn-mode server never came up: {line!r}"
        assert "learn=on" in line, line
        base = f"http://127.0.0.1:{port}"
        with urllib.request.urlopen(base + "/health", timeout=120) as h:
            health = json.loads(h.read().decode())
        assert health.get("learn") is True and health.get("teach") is True, health
        assert health.get("electric") is True, health

        for text in [OBJECT_TELL, REVERSE_TELL] + [u for p in PAIRS for u in p]:
            _post(base, "/chat", {"text": text})
        s = _post(base, "/shutdown", {})
        assert s["saved"] is True, s
    finally:
        proc.wait(timeout=240)

    assert st.exists(), "the learn session left no state file behind"
    try:
        for mode, expect_fold in (("--electric-learn", ANSWER), ("--electric-teach", ANSWER)):
            out, _err = say_cli(FOLD, st, mode)
            assert out["boot"]["learn"] is (mode == "--electric-learn"), out["boot"]
            assert out["boot"]["flags_on"]["ELECTRIC_REVERSE"] is (mode == "--electric-learn")
            assert out["boot"]["qa_pairs_at_boot"] >= 2, out["boot"]
            assert out["reply"] == expect_fold, f"lost across a restart ({mode}): {out}"

        out, _err = say_cli(OBJECT_ASK_BARE, st, "--electric-learn")
        assert out["reply"] in ("", OBJECT_TELL), f"the restart lost the tell: {out}"
        out, _err = say_cli(UNTAUGHT, st, "--electric-learn")
        assert out["reply"] not in TELLS, f"an untaught ask answered from a restarted store: {out}"
    finally:
        st.unlink(missing_ok=True)
        for extra in (Path(str(st) + ".cortex.delta.json"), Path(str(st) + ".tmp")):
            extra.unlink(missing_ok=True)
