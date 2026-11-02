"""--electric-teach: one switch for the stack that makes a QA pair teachable.

The claim a bundle flag has to answer is not "does it set flags" -- it is "is the bundle the
list, and is the list still what each flag was measured to do". Eight flags went into this
stack one at a time, each with its own measurement, and a bundle that quietly changed any of
their behaviour would invalidate the evidence for all of them. So most of what is asserted
here is that the mode BUYS something (a pair, a paraphrase, a restart) while costing nothing
(the guarded admission, the class defaults, the four widening switches).

The eighth is the store-shape guard, and it arrived last for a reason worth keeping straight:
the hole it closes was found BY this mode's live check and pinned here as unfixed, because the
repair is a narrowing at a write site the graded E24 work owns. It is now closed, behind its
own switch, and the pinned tests below were not deleted -- they run in the configuration they
were measured in (guard off) and each has a sibling that measures the closure. A pin that
vanishes when a defect is fixed teaches nobody what the defect was.

Two things this file cannot say and does not try to. That the mode is equivalent to the
hand-spelled list is measured in a real house by tools/qa_teach_mode_live.py, which spells the
eight flags out literally rather than reading them from the table it is checking; and that the
pair survives a restart is measured in a separate PROCESS below, because in-process a restart is
a function call. What the guard costs in a real house -- statements, relative clauses, the
grader's own input -- is tools/qa_teach_hole_live.py.

What a bare organ CAN do turned out to be most of it: it holds a marked ask, pairs it with the
next thing the same speaker says, stores the pair, and answers a phrasing nobody taught it. The
shadow house in the live check is not needed for the teaching, only for the volume.
"""
import json
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

PAIRS = [("what rings the bell?", "the copper bell rings"),
         ("what holds the door?", "the latch holds the door")]
KEY, ANSWER = "what rings the bell", "the copper bell rings"
FOLD = "what ring the bell"                 # never taught, reached by the project's one stemmer
UNTAUGHT = "where is the moon"              # no pair, no tell, nothing to say

# The pair the guarded admission refuses, from tests/test_electric_qa_elicit.py: `lantern` was
# told (it belongs to Mira) but no PLACE was ever told for it.
GUARD_TELLS = ["the lantern belongs to Mira", "the scarf is on the hook"]
GUARD_ASK = "where did i say the lantern is?"

# An unanswerable phrasing: one content word past the pair, so nothing may answer it.
HOLE_ASK = "what rings the bell twice"


def _organ(mode=True, base=True, guard=None):
    """A bare organ with `--electric` (always, in every arm) plus, optionally, the mode.

    `guard` forces the store-shape guard off after the mode has run. It exists for one reason:
    the pinned hole tests below have to be able to reproduce the configuration the hole was
    measured in, and that configuration is now the one the mode does NOT ship.
    """
    o = nl.NeuralLanguage(HybridEngine(graph=build_core_graph()), TokenizerOrgan())
    o.persist = False
    o.cortex.MIN_HEAR_INTERVAL_S = 0.0     # a unit test is not an afternoon
    o.exposure_enabled = False             # no wall-clock-dependent rows in a boolean test
    if base:
        for attr in tm.BASE_ATTRS:
            setattr(o, attr, True)         # what --electric means, in every arm but one
    if mode:
        tm.enable(o, base=base)
    if guard is not None:
        o.ELECTRIC_ASK_SHAPE_STORE = bool(guard)
    for t in GUARD_TELLS:
        o.hear(t, speaker="you")
    return o


def _say(o, text):
    r = o.respond(text, speaker="you") or {}
    return {"held": bool(o._qa_pending),
            "src": str(r.get("source") or ""),
            "ev": str(r.get("ask_evidence") or ""),
            "said": str(r.get("utterance") or r.get("response") or "").strip(),
            "refused": bool(r.get("licensed_refusal"))}


def _teach(o, pairs=PAIRS):
    """Ask, then say the answer, the way a person does it -- and only then clear the pending
    slot. Clearing it after the ASK is the bug that made an earlier probe report that the mode
    could not teach at all: the pair is the ask plus the NEXT utterance."""
    for ask, ans in pairs:
        _say(o, ask)
        _say(o, ans)
        o._qa_pending = None
    return o


def say_cli(text, state, *extra):
    """One utterance in its own process, JSON on stdout, warnings on stderr."""
    p = subprocess.run([sys.executable, str(TOOL), "--state", str(state),
                        "--say", text, *extra],
                       capture_output=True, text=True, timeout=300, cwd=str(ROOT))
    assert p.returncode == 0, f"exit {p.returncode}\n{p.stdout}\n{p.stderr}"
    line = [l for l in p.stdout.splitlines() if l.startswith("{")][-1]
    return json.loads(line), p.stderr


# ------------------------------------------------------------------ the table ----

def test_the_mode_is_exactly_the_stack_and_the_base():
    o = _organ()
    on = {a for a, v in tm.state(o).items() if v}
    assert on == set(tm.STACK_ATTRS) | set(tm.BASE_ATTRS), \
        f"the mode is not the stack it claims: {sorted(on)}"
    assert len(tm.STACK_ATTRS) == 8 and len(tm.BASE_ATTRS) == 3, \
        "the shape of the mode changed; the help text in serve.py and electric_chat.py describes " \
        "eight stack flags on top of what --electric already means"
    assert "ELECTRIC_ASK_SHAPE_STORE" in tm.STACK_ATTRS, \
        "the mode shipped without the fix for the hole its own live check found"


def test_the_mode_sets_nothing_on_the_class():
    """Battery runs read ELECTRIC off the CLASS, default False. If enable() ever wrote through
    to NeuralLanguage, 'battery runs are ELECTRIC-free' would be a sentence about intent."""
    before = {a: getattr(nl.NeuralLanguage, a, None) for a in tm.ALL_ATTRS}
    assert set(before.values()) == {False}, \
        f"a class default is already on before anything ran: {before}"
    _teach(_organ())
    after = {a: getattr(nl.NeuralLanguage, a, None) for a in tm.ALL_ATTRS}
    assert after == before, f"the mode leaked onto the class: {after}"
    assert nl.NeuralLanguage.ELECTRIC_ASK_SHAPE is False
    assert nl.NeuralLanguage.ELECTRIC_REVERSE is False


def test_the_widening_switches_stay_off():
    """The mode is not "everything ELECTRIC". Each of these lets MORE asks reach MORE matchers,
    and each was measured alone precisely so a run could say which one cost something. Named here
    one by one on purpose: a new widening has to be added to this list, which is the moment
    somebody has to decide whether teach mode should really have it."""
    o = _organ()
    st = tm.state(o)
    assert not any(st[a] for a in tm.EXCLUDED_ATTRS), \
        f"the mode turned on a widening: {sorted(a for a in tm.EXCLUDED_ATTRS if st[a])}"
    assert set(tm.EXCLUDED_ATTRS) == {"ELECTRIC_ASK_SHAPE", "ELECTRIC_REVERSE",
                                      "ELECTRIC_OBJECT_ROLE", "ELECTRIC_ASK_NORMALIZE",
                                      "ELECTRIC_ASK_DO_SUPPORT",
                                      "ELECTRIC_QA_ANSWER_MEMORY"}


def test_enable_without_base_is_the_stack_alone():
    """`base=False` exists to measure the difference, and the difference has to be real: the
    three base flags are what make an untaught ask an ADMITTED ignorance rather than silence."""
    o = _organ(base=False)
    st = tm.state(o)
    assert all(st[a] for a in tm.STACK_ATTRS) and not any(st[a] for a in tm.BASE_ATTRS), st


# ---------------------------------------------------------------- what it buys ----

def test_the_mode_teaches_a_pair_the_control_arm_cannot():
    m = _teach(_organ())
    assert sorted(m.qa_store) == sorted([KEY, "what holds the door"]), sorted(m.qa_store)
    c = _organ(mode=False)
    _teach(c)
    assert c.qa_store == {}, "the control arm formed a pair with the stack off"
    assert c._qa_pending is None, "elicitation ran with its flag off"


def test_a_pair_answers_in_words_nobody_taught_it():
    """The whole point of the fold, and it has to name the evidence that opened the route: an
    answer with no evidence named is a guess that sounds like a memory."""
    o = _teach(_organ())
    exact, fold = _say(o, KEY), _say(o, FOLD)
    assert exact["src"] == "electric_qa_store" and exact["said"] == ANSWER, exact
    assert fold["src"] == "electric_qa_store" and fold["said"] == ANSWER, fold
    assert "paraphrase" in fold["ev"], f"the fold answered as if it were the exact key: {fold}"
    assert "paraphrase" not in exact["ev"], f"an exact key claims a route it did not use: {exact}"


def test_an_untaught_ask_is_not_answered_from_the_store():
    o = _teach(_organ())
    r = _say(o, UNTAUGHT)
    assert r["src"] != "electric_qa_store", f"the store invented a pair: {r}"
    assert r["said"] != UNTAUGHT, f"the house echoed the ask back: {r}"


def test_the_second_pair_earns_the_question_word():
    """INTERROGATIVE_MIN_VOTES is 2, and one elicited pair votes once. This is why the live
    check teaches two: it is the difference between an ask that reaches answer() and an ask
    that is HEARD -- and being heard is what files a question as a tell (see the pinned tests)."""
    one, two = _organ(), _organ()
    _teach(one, PAIRS[:1])
    _teach(two, PAIRS)
    assert one.is_interrogative("what") is False
    assert two.is_interrogative("what") is True, sorted(two.qa_store)


# ------------------------------------------------------ what it must not cost ----

def test_the_guarded_admission_is_untouched_by_the_mode():
    """The graded contract, in one test: `lantern` was told, no place was ever told for it, and
    the house must ADMIT that. Same refusal, same source, same reason, with the stack on as off.
    A bundle that moved this would invalidate the absence evidence, not just its own."""
    outs = {}
    for mode in (False, True):
        o = _organ(mode=mode)
        if mode:
            _teach(o)
        r = o.answer(GUARD_ASK, speaker="you")
        r = r if isinstance(r, dict) else {"response": r}
        outs[mode] = {k: r.get(k) for k in ("spoken", "source", "licensed_refusal", "reason")}
    assert outs[True]["licensed_refusal"] is True, outs
    assert outs[True]["source"] == "electric_absence", outs
    assert outs[True] == outs[False], \
        f"the mode changed what the guard SAYS, not just whether it refuses: {outs}"


def test_the_mode_writes_no_row_the_control_arm_did_not_write():
    """Asking in one phrasing and answering in another must not be a way of making memories.
    Counted before any probing, because probing asks questions and questions are the rows in
    question."""
    m, c = _organ(), _organ(mode=False)
    m0, c0 = len(m.cortex.binder.meta), len(c.cortex.binder.meta)
    assert m0 == c0, f"the arms did not start even: {m0} vs {c0}"
    _teach(m)
    _teach(c)
    dm = len(m.cortex.binder.meta) - m0
    dc = len(c.cortex.binder.meta) - c0
    assert dm == dc, \
        f"the same four utterances wrote {dm} rows under the mode and {dc} without it"


# -------------------------------------------------------------------- inert ----

def test_a_flag_without_its_parent_is_said_out_loud():
    """The symptom of an inert flag is that nothing happens AND nothing is said. Each of these
    four combinations boots, so each has to warn."""
    for attr, (parent, message) in tm.DEPENDS_ON.items():
        on = {a: False for a in tm.ALL_ATTRS}
        on[attr] = True
        assert tm.unmet(on) == [message], f"{attr} with {parent} off is silent"
        # The parent has a parent of its own -- elicitation needs the store, so turning on the
        # immediate parent only moves the warning, it does not clear it. Walk the whole chain.
        chain, cur = [], attr
        while cur in tm.DEPENDS_ON:
            cur = tm.DEPENDS_ON[cur][0]
            assert cur not in chain, f"cyclic dependency in DEPENDS_ON at {cur}"
            chain.append(cur)
        for anc in chain:
            on[anc] = True
        assert tm.unmet(on) == [], f"{attr} with its whole chain on still warns: {tm.unmet(on)}"


def test_the_mode_itself_reports_no_warning():
    assert tm.warnings(_organ()) == [], \
        "the bundle turns on a flag whose parent it does not turn on"


# ---------------------------------------------- pinned: the question-pollution hole ----

def test_pinned_an_unclassified_ask_is_filed_as_a_tell():
    """THE HOLE, REPRODUCED IN THE CONFIGURATION IT WAS MEASURED IN -- store guard OFF.

    `_absence_note` in neural_language.py files a frame from ANYTHING it is told, and a
    question's words yield a frame. While the question word is unlearned (one pair = one vote,
    min 2) the ask is HEARD, so `what rings the bell twice` enters `_taught_says` as if it were
    a fact. The store refuses exactly this pair -- `answer_is_question` is checked in learn_qa --
    and the taught inventory has no such check. That asymmetry was the defect.

    It stays as a test with the guard forced off, for two reasons: the fix is a switch, so the
    configuration it replaces has to stay reproducible on demand, and if this ever stops failing
    without anyone touching the guard then something else moved the hole. The mode as it now
    ships does not file it -- the next test is that.
    """
    o = _teach(_organ(guard=False), PAIRS[:1])   # one pair: `what` has one vote, is not learned
    assert not o.is_interrogative("what")
    before = {v for sub in o._taught_says.values() for v in sub.values()}
    _say(o, HOLE_ASK)
    filed = {v for sub in o._taught_says.values() for v in sub.values()} - before
    assert HOLE_ASK in filed, f"the question was NOT filed as a tell -- re-measure: {filed}"
    assert o.qa_store and HOLE_ASK not in o.qa_store, \
        "the store started holding the question too; then the defect moved, it did not fix"


def test_the_mode_as_it_ships_refuses_the_filing_that_used_to_answer_itself():
    """Same script, guard on -- which is what `--electric-teach` now means. The question is not
    filed, and the pair that was being drowned by it is what answers the follow-up ask. This is
    the closure, asserted where the hole was pinned, so the two sit side by side."""
    o = _teach(_organ(), PAIRS[:1])
    assert o.ELECTRIC_ASK_SHAPE_STORE is True, "the mode does not carry the guard"
    before = {v for sub in o._taught_says.values() for v in sub.values()}
    _say(o, HOLE_ASK)
    filed = {v for sub in o._taught_says.values() for v in sub.values()} - before
    assert not filed, f"the mode still files an unanswered question as a tell: {filed}"
    r = _say(o, KEY)
    assert r["said"] == ANSWER and r["src"] == "electric_qa_store", \
        f"the guard closed the filing but the pair did not get the turn back: {r}"


def test_pinned_the_store_refuses_what_the_inventory_files():
    """The same sentence, two doors, opposite answers -- with the guard OFF, which is the
    disagreement that was measured. `learn_qa` refuses a pair whose answer is a question -- the
    Dickens warmint case -- while `hear` of that very text teaches it into the inventory that
    answers BEFORE the store. Kept as two assertions in one test because the point is the
    disagreement, not either half."""
    o = _organ(guard=False)
    r = o.learn_qa(["who", "carries", "droso"], ["who", "carries", "droso", "tomorrow"],
                   provenance={"book": "t.txt", "line": 0, "mark": 2, "tokens": 3,
                               "answer_is_question": True, "answer_line": 1})
    assert not r.get("stored"), f"the store took a question as an answer: {r}"
    o.hear("who carries droso tomorrow", speaker="you")
    filed = [v for sub in o._taught_says.values() for v in sub.values()]
    assert "who carries droso tomorrow" in filed, \
        f"the inventory stopped filing it -- the asymmetry moved or closed: {filed}"


def test_the_guard_removes_the_disagreement_it_was_pinned_for():
    """The other half of the pair above, and the reason the two are the same sentence: the store
    refused it then and still does, and the inventory no longer files it. The asymmetry was the
    defect; there is now one answer between the two doors, and it is the store's."""
    o = _organ()
    r = o.learn_qa(["who", "carries", "droso"], ["who", "carries", "droso", "tomorrow"],
                   provenance={"book": "t.txt", "line": 0, "mark": 2, "tokens": 3,
                               "answer_is_question": True, "answer_line": 1})
    assert not r.get("stored"), f"the store started taking a question as an answer: {r}"
    o.hear("who carries droso tomorrow", speaker="you")
    filed = [v for sub in o._taught_says.values() for v in sub.values()]
    assert "who carries droso tomorrow" not in filed, \
        f"both doors now agree in the wrong direction: {filed}"
    assert "carries" in o._absence_inv, \
        "the guard took the inventory entry with it -- that is the graded store, not this flag"


def test_pinned_the_learned_word_closes_the_filing():
    """Once the word is earned the ask routes to answer() and is never heard, so there is no
    frame to file. This is the mode's own second pair doing the repair, and it holds in BOTH
    arms -- with the guard off it is the only thing that closed the hole, and with the guard on
    the two mechanisms agree. The write-site guard is the cheaper fix and now ships in the mode;
    this is the one the mode always had."""
    for guard in (False, True):
        o = _teach(_organ(guard=guard), PAIRS)
        assert o.is_interrogative("what")
        before = {v for sub in o._taught_says.values() for v in sub.values()}
        r = _say(o, HOLE_ASK)
        filed = {v for sub in o._taught_says.values() for v in sub.values()} - before
        assert not filed, f"an unanswerable ask was still filed (guard={guard}): {filed}"
        assert r["src"] != "electric_qa_store", \
            f"the store answered a question it holds no pair for (guard={guard})"
        assert r["said"] != HOLE_ASK, \
            f"the house repeated the person's question at them (guard={guard}): {r}"


# ------------------------------------------------------------------ the CLI ----

def test_cli_flag_turns_the_stack_on_and_implies_electric(tmp_path):
    st = tmp_path / "neural_lang.json"
    out, _err = say_cli("+" + ANSWER, st, "--electric-teach")
    assert out["boot"]["teach"] is True, out["boot"]
    assert out["boot"]["electric"] is True, out["boot"]

    # --no-electric is the CONTROL arm; the mode sits on top of the flags it turns off, so
    # asking for both is a contradiction that has to be announced, not quietly resolved.
    out, err = say_cli("+" + ANSWER, st, "--electric-teach", "--no-electric")
    assert out["boot"]["electric"] is True, out["boot"]
    assert "not the control arm" in err, err


def test_cli_one_shot_holds_the_ask_and_says_so(tmp_path):
    """A held ask is memory-only BY DESIGN -- a question from a previous life must not pair with
    an unrelated sentence in this one -- which means two `--say` calls cannot teach a pair. That
    is invisible unless the tool says it, and the silence once read as a broken feature."""
    st = tmp_path / "neural_lang.json"
    out, err = say_cli("?" + PAIRS[0][0], st, "--electric-teach")
    assert out["door"] == "respond", out
    assert out["ask_held"] is True, out
    assert "holding your question" in err, err


def _post(base, path, obj):
    req = urllib.request.Request(base + path, data=json.dumps(obj).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read().decode("utf-8"))


def test_cli_teach_a_pair_and_ask_it_in_other_words_after_a_real_restart(tmp_path):
    """The headline claim, end to end, across two processes that share nothing but the file:
    ask, answer, shut down cleanly, come back, ask in words nobody used, get the line the
    person gave. /shutdown rather than terminate() -- on Windows terminate() skips the finally
    block, and a persistence claim that rested on it would be testing nothing."""
    st = tmp_path / "neural_lang.json"
    proc = subprocess.Popen([sys.executable, str(TOOL), "--state", str(st),
                             "--electric-teach", "--port", "0"],
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
        assert port, f"the teach-mode server never came up: {line!r}"
        assert "teach=on" in line, line

        base = f"http://127.0.0.1:{port}"
        with urllib.request.urlopen(base + "/health", timeout=120) as h:
            health = json.loads(h.read().decode())
        assert health["teach"] is True and health["electric"] is True, health

        for text in [u for pair in PAIRS for u in pair]:
            _post(base, "/chat", {"text": text})
        s = _post(base, "/shutdown", {})
        assert s["saved"] is True, s
    finally:
        proc.wait(timeout=240)

    assert st.exists(), "the teach session left no state file behind"
    out, _err = say_cli(FOLD, st, "--electric-teach")
    assert out["boot"]["qa_pairs_at_boot"] >= 2, out["boot"]
    assert out["source"] == "electric_qa_store", out
    assert out["reply"] == ANSWER, f"lost across a real restart: {out}"
    assert out["taught_this_turn"] == 0, f"asking taught something: {out}"
