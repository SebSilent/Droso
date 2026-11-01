"""ELECTRIC: teach mode, persistence, keyed direct answer emission, spoken ignorance.

Written against the design in docs/capability_first_plan.md and the abort
conditions C1-C5. The load-bearing test is test_electric_cannot_answer_an_untaught
_question -- it is the shim detector.
"""
import inspect
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import organs.neural_language as nl  # noqa: E402
from connectome.engine import HybridEngine  # noqa: E402
from connectome.substrate import build_core_graph  # noqa: E402
from organs.tokenizer import TokenizerOrgan  # noqa: E402

SAYS = {"scarf": {"place": "the scarf is on the hook"},
        "bell": {"property": "the bell is copper"}}


# ------------------------------------------------------- pure read side
def test_direct_function_is_pure():
    """No self, no binder, no engine -- a lookup the tests can hold still."""
    fn = nl._electric_answer
    # The signature is pinned deliberately. It grew a third parameter for the
    # reverse-role ask, so the pin records that too: a new knob on a pure lookup is
    # fine, a knob that defaults to ON is not.
    params = inspect.signature(fn).parameters
    assert list(params) == ["question", "says", "reverse"], list(params)
    assert params["reverse"].default is False, \
        "reverse-role binding is a permission; defaulting it on would hand it to every caller"
    assert fn.__qualname__ == "_electric_answer", "module level, not an organ method"


def test_answers_a_taught_fact():
    assert nl._electric_answer("where is the scarf?", SAYS) == \
        "the scarf is on the hook"


def test_none_for_untaught_subject():
    """C4 shim detector, subject half."""
    assert nl._electric_answer("where is the hat?", SAYS) is None


def test_none_for_untaught_relation():
    """C4 shim detector, relation half: a known subject with an unknown
    relationship must not be answered from an adjacent one."""
    assert nl._electric_answer("what is the scarf like?", SAYS) is None


def test_none_when_subject_is_ambiguous():
    """Two subjects in the ask -> bind nothing, fall through. E16a measured the
    head-noun rule as mis-binding multi-word subjects, so guessing is banned."""
    two = {"scarf": {"place": "A"}, "bell": {"place": "B"}}
    assert nl._electric_answer("where is the scarf or the bell?", two) is None


def test_no_similarity_search():
    """Keyed lookup only (E24 abort A6). 'scarf' ~ 'scarves' is a real English
    relation and the organ must not guess it."""
    assert nl._electric_answer("where are the scarves?", SAYS) is None


def test_agent_ask_naming_the_object_is_not_claimed():
    """The generation-24 regression, as a test.

    `what bites the latch?` asks about the FROST. `latch` is itself a subject in
    the inventory (the latch holds the door), so a bare keyed bind answers a
    question nobody asked, confidently. The control path got this right; the
    direct path must not make it worse.
    """
    says = {"frost": {"agent": "the frost bites the latch"},
            "latch": {"agent": "the latch holds the door"}}
    # the ask's noun binds to `latch`, whose taught verb is not the asked verb
    assert nl._electric_answer("what bites the latch?", says) is None
    # Asked about the fact it does match, with the taught verb present verbatim.
    assert nl._electric_answer("what bites the latch and holds the door?",
                               {"latch": {"agent": "the latch holds the door"}}) == \
        "the latch holds the door"
    # A morphological variant is NOT guessed. "bite" vs taught "bites" shares no
    # exact content word, so the ask falls through to the pre-ELECTRIC path.
    # This is a deliberate loss: E24 abort A6 bans similarity search, and the
    # safe failure is silence, not a stemmer that decides which fact was meant.
    assert nl._electric_answer("what does the frost bite?", says) is None


def test_taught_facts_survive_teach_mode_being_switched_off(tmp_path):
    """C2's whole finding. Teach mode is a WRITE PERMISSION, and it is the correct
    thing to switch off before consolidation -- consolidate() replays corpus
    sentences through live(learn=True), and with teach mode on every one of them
    becomes a fact the user supposedly told. That safe choice used to erase the
    learner, because the save gate keyed on the permission flag."""
    sp = tmp_path / "s.json"
    a = nl.NeuralLanguage(HybridEngine(graph=build_core_graph()),
                          TokenizerOrgan(), state_path=sp)
    a.ELECTRIC_TEACH = True
    a.ELECTRIC_ANSWER = True
    a.hear("the copper bell turns twice", speaker="you")
    assert len(a._taught_says) == 1
    a.ELECTRIC_TEACH = False            # exactly what consolidation requires
    assert a.save_state(force=True).get("saved")

    b = nl.NeuralLanguage(HybridEngine(graph=build_core_graph()),
                          TokenizerOrgan(), state_path=sp)
    b.ELECTRIC_TEACH = False
    b.ELECTRIC_ANSWER = True
    assert b.load_state().get("loaded") is True
    assert b._taught_says, "teach mode off wiped the taught facts"
    # Keyed on 'copper', NOT 'bell': _absence_frame takes the first content word
    # after the article, so a multi-word noun phrase keys on its MODIFIER. Asserted
    # as measured rather than as I expected it -- the expectation was wrong.
    assert b._taught_says["copper"]["agent"] == "the copper bell turns twice"


def test_electric_off_still_writes_an_empty_inventory(tmp_path):
    """The battery must not move. With ELECTRIC never enabled the inventory is
    empty, so the widened gate writes {} and the state bytes are unchanged."""
    sp = tmp_path / "s.json"
    a = nl.NeuralLanguage(HybridEngine(graph=build_core_graph()),
                          TokenizerOrgan(), state_path=sp)
    a.hear("the copper bell turns twice", speaker="you")
    assert a._taught_says == {}, "ELECTRIC off must not mint taught facts"
    a.save_state(force=True)
    import json
    doc = json.loads(sp.read_text(encoding="utf-8"))
    assert doc.get("taught_says") == {}, "the widened gate must be battery-neutral"


def test_broad_agent_binds_a_held_out_frame():
    """E1's `which thing does the {a} {v}?` is an agent question that never says
    "what", so the phrase-driven detector missed it and the generalisation run
    scored 0/3 with 3/3 confabulated echoes."""
    says = {"dainty": {"agent": "the dainty towns the bottom"}}
    assert nl._electric_answer("which thing does the dainty towns?", says) == \
        "the dainty towns the bottom"
    # Structure, not the literal phrase: `which` + do-support binds, and so does a
    # different auxiliary. Scope is what|which -- `who did the dainty town?` is NOT
    # claimed, because no evidence in E1's frames asked for it and widening on a
    # guess is how the guarded battery silently breaks.
    assert nl._electric_bind("which thing did the dainty town?", says,
                             broad_agent=True) == ("agent", "dainty")
    assert nl._electric_answer("who did the dainty town?", says) is None


def test_licence_keeps_the_narrow_detector():
    """The asymmetry is the point. E24's absence licence is a 24-generation-old
    measured behaviour and must NOT widen: an ask the licence never licensed must
    still fail to bind on the narrow path."""
    inv = {"dainty": {"agent": "bottom"}}
    assert nl._electric_bind("which thing does the dainty towns?", inv) is None
    assert nl._electric_bind("which thing does the dainty towns?", inv,
                             broad_agent=True) == ("agent", "dainty")


def test_bind_is_shared_by_answer_and_refusal():
    """The answer path and the refusal path must agree on the binding, or one ask
    can be refused for a relation and answered for another."""
    bound = nl._electric_bind("what is the bell like?", SAYS)
    assert bound == ("property", "bell")
    src = inspect.getsource(nl._absence_licence)
    assert "_electric_bind(" in src


# ------------------------------------------------------------- organ flags
def test_flags_default_off():
    assert nl.NeuralLanguage.ELECTRIC_TEACH is False
    assert nl.NeuralLanguage.ELECTRIC_ANSWER is False


def test_teach_records_the_verbatim_tell(tmp_path):
    organ = nl.NeuralLanguage(HybridEngine(graph=build_core_graph()),
                              TokenizerOrgan(), state_path=tmp_path / "s.json")
    organ.ELECTRIC_TEACH = True
    organ.hear("the scarf is on the hook", speaker="you")
    assert organ._taught_says["scarf"]["place"] == "the scarf is on the hook"


def test_first_tell_wins_not_the_last(tmp_path):
    """A fact that changes because a later sentence arrived is a recency
    artifact, not a memory."""
    organ = nl.NeuralLanguage(HybridEngine(graph=build_core_graph()),
                              TokenizerOrgan(), state_path=tmp_path / "s.json")
    organ.ELECTRIC_TEACH = True
    organ.hear("the scarf is on the hook", speaker="you")
    organ.hear("the scarf is in the box", speaker="you")
    assert organ._taught_says["scarf"]["place"] == "the scarf is on the hook"


def test_teach_is_inert_when_the_flag_is_off(tmp_path):
    organ = nl.NeuralLanguage(HybridEngine(graph=build_core_graph()),
                              TokenizerOrgan(), state_path=tmp_path / "s.json")
    organ.hear("the scarf is on the hook", speaker="you")
    assert organ._taught_says == {}


# ------------------------------------------------- hazard: replay vs teaching
# The C2 hazard arm (docs/electric_c2_hazard.md) found NO pollution path. These two
# tests pin WHY, as behaviour rather than as a grep of the implementation.
def test_live_alone_never_mints_a_taught_fact(tmp_path):
    """The mechanism, isolated: consolidation writes through live(), not hear().

    Teach mode is left ON -- the worst case -- and text is pushed through the exact
    entry point consolidate() uses. If the recording hook were on live(), this would
    put a subject in the inventory and the hazard would be real.
    """
    organ = nl.NeuralLanguage(HybridEngine(graph=build_core_graph()),
                              TokenizerOrgan(), state_path=tmp_path / "s.json")
    organ.ELECTRIC_TEACH = True
    organ.live("the library sentence turns twice", learn=True, speaker="parent")
    organ.live("another corpus line is on the shelf", learn=True, speaker="book")
    assert organ._taught_says == {}, \
        "live() must not record taught facts; only hear(speaker='you') may"
    assert organ._absence_inv == {}


def test_consolidation_with_teach_mode_on_does_not_pollute(tmp_path):
    """The arm itself, at unit scale: teach, consolidate WITH the flag on, re-check.

    Same shape as tools/electric_consolidate.py --arm teachon, which measured 20/20
    retention and zero polluted subjects against the live state.
    """
    organ = nl.NeuralLanguage(HybridEngine(graph=build_core_graph()),
                              TokenizerOrgan(), state_path=tmp_path / "s.json")
    organ.ELECTRIC_TEACH = True
    organ.hear("the scarf is on the hook", speaker="you")
    before = dict(organ._taught_says)
    assert before, "precondition: teaching must have recorded something"

    organ.ELECTRIC_TEACH = True          # NOT switched off -- this is the hazard
    organ.consolidate(budget=8)

    assert set(organ._taught_says) == set(before), \
        "consolidation must not add subjects to the taught inventory"
    assert sum(len(v) for v in organ._taught_says.values()) == \
        sum(len(v) for v in before.values()), \
        "consolidation must not add relations to the taught inventory"


# ------------------------------------------------------------ longevity
def test_three_cycles_do_not_erode_the_inventory(tmp_path):
    """C3's finding as a test: repeated teach/consolidate/restart accumulates, it
    does not erode. Three cohorts of two, each cohort taught over a RESTARTED organ
    (a fresh object over the same file), consolidated and saved.

    Asserts the two things the experiment actually measured: the inventory keeps
    every cohort (no loss), and no cohort's tell is overwritten by a later one
    (no interference). It does NOT assert answer quality -- C3 showed that is a
    frame problem, not a persistence problem.
    """
    sp = tmp_path / "s.json"
    cohorts = [
        [("the scarf is on the hook", "scarf"), ("the bell rings the copper", "bell")],
        [("the lantern lights the porch", "lantern"), ("the kettle boils the water", "kettle")],
        [("the map shows the harbor", "map"), ("the fence guards the garden", "fence")],
    ]
    for tells in cohorts:
        o = nl.NeuralLanguage(HybridEngine(graph=build_core_graph()),
                              TokenizerOrgan(), state_path=sp)
        o.ELECTRIC_TEACH = True
        o.load_state()
        for tell, _ in tells:
            o.hear(tell, speaker="you")
        o.ELECTRIC_TEACH = False
        o.consolidate(budget=8)
        o.save_state(force=True)
        del o

    final = nl.NeuralLanguage(HybridEngine(graph=build_core_graph()),
                              TokenizerOrgan(), state_path=sp)
    final.ELECTRIC_ANSWER = True
    final.load_state()
    expected = [(t, s) for tells in cohorts for t, s in tells]
    # _taught_says is subject -> relation -> verbatim tell (:4347)
    held = {s: dict(v) for s, v in final._taught_says.items()}
    for tell, subj in expected:
        assert subj in held, f"cohort fact lost after repeated cycles: {tell}"
        assert tell in held[subj].values(), f"cohort fact overwritten: {tell}"


# ------------------------------------------------------------- persistence
def test_survives_a_restart(tmp_path):
    """The success criterion, as a test: life 1 teaches, life 2 answers."""
    sp = tmp_path / "s.json"
    a = nl.NeuralLanguage(HybridEngine(graph=build_core_graph()),
                          TokenizerOrgan(), state_path=sp)
    a.ELECTRIC_TEACH = True
    a.hear("the scarf is on the hook", speaker="you")
    a.save_state(force=True)

    b = nl.NeuralLanguage(HybridEngine(graph=build_core_graph()),
                          TokenizerOrgan(), state_path=sp)
    b.ELECTRIC_TEACH = True
    b.ELECTRIC_ANSWER = True
    assert b.load_state().get("loaded") is True
    assert b._taught_says["scarf"]["place"] == "the scarf is on the hook"
    assert b.answer("where is the scarf?").get("source") == "electric_taught"


def test_state_shaped_garbage_is_dropped(tmp_path):
    """A corrupt or hand-edited state file must not become a source of answers."""
    sp = tmp_path / "s.json"
    a = nl.NeuralLanguage(HybridEngine(graph=build_core_graph()),
                          TokenizerOrgan(), state_path=sp)
    a.ELECTRIC_TEACH = True
    a.hear("the scarf is on the hook", speaker="you")
    a.save_state(force=True)
    import json
    doc = json.loads(sp.read_text(encoding="utf-8"))
    doc["taught_says"] = {"scarf": "not a dict", "bell": {"place": 3}}
    sp.write_text(json.dumps(doc), encoding="utf-8")

    b = nl.NeuralLanguage(HybridEngine(graph=build_core_graph()),
                          TokenizerOrgan(), state_path=sp)
    b.ELECTRIC_TEACH = True
    b.load_state()
    assert b._taught_says.get("scarf") in (None, {})
    assert "place" not in b._taught_says.get("bell", {}) or \
        b._taught_says["bell"]["place"] == "3"


# ------------------------------------------------------------ answer path
def test_direct_answer_bypasses_the_arbiter(tmp_path):
    """The claimed ask must never reach the shape arbiter or the resonance
    competition -- that is the point of the change."""
    sp = tmp_path / "s.json"
    a = nl.NeuralLanguage(HybridEngine(graph=build_core_graph()),
                          TokenizerOrgan(), state_path=sp)
    a.ELECTRIC_TEACH = True
    a.hear("the scarf is on the hook", speaker="you")
    b = nl.NeuralLanguage(HybridEngine(graph=build_core_graph()),
                          TokenizerOrgan(), state_path=tmp_path / "t.json")
    b.ELECTRIC_TEACH = True
    b.ELECTRIC_ANSWER = True
    b._taught_says = {"scarf": {"place": "the scarf is on the hook"}}
    r = b.answer("where is the scarf?")
    assert r.get("spoken") is True
    assert r.get("answered") is True
    assert r.get("direct") is True
    assert r.get("stage") is None, "a claimed ask must not be staged downstream"
    assert "coverage" not in r, "the coverage gate must not have been consulted"


def test_absence_is_admitted_out_loud(tmp_path):
    """E24 phase 2: the refusal is now SPOKEN, warranted by a keyed fact."""
    b = nl.NeuralLanguage(HybridEngine(graph=build_core_graph()),
                          TokenizerOrgan(), state_path=tmp_path / "s.json")
    b.ABSENCE_INVENTORY = True
    b.ELECTRIC_ANSWER = True
    b._absence_inv = {"scarf": {"place": "hook"}}
    r = b.answer("what is the scarf like?")
    assert r.get("licensed_refusal") is True
    assert r.get("spoken") is True
    assert "don't know" in r.get("utterance", "")


def test_control_path_is_unchanged(tmp_path):
    """With every flag off, the refusal stays SILENT -- E24's phase 1 behaviour
    is preserved, so the battery baseline keeps its meaning."""
    b = nl.NeuralLanguage(HybridEngine(graph=build_core_graph()),
                          TokenizerOrgan(), state_path=tmp_path / "s.json")
    # E24's phase 1 exactly: the inventory is on, ELECTRIC's voice is not.
    b.ABSENCE_INVENTORY = True
    b.ELECTRIC_ANSWER = False
    b._absence_inv = {"scarf": {"place": "hook"}}
    r = b.answer("what is the scarf like?")
    assert r.get("licensed_refusal") is True
    assert r.get("spoken") is False, \
        "phase 1 licenses a REASON TO STAY SILENT, never speech"
    assert "don't know" not in str(r.get("utterance", ""))


def test_harness_flag_exists():
    """--electric must be declared and both flags stamped on every path, so a
    missing key can never be read as a deliberate off (E25 invariant)."""
    src = (ROOT / "tools" / "run_generation.py").read_text(encoding="utf-8")
    decl = [ln for ln in src.splitlines() if '"--electric"' in ln]
    assert decl, "--electric not declared"
    assert "action=" in "".join(decl)
    assert 'CODE_FLAGS["electric_teach"] = bool(args.electric)' in src
    assert 'CODE_FLAGS["electric_answer"] = bool(args.electric)' in src
