"""E24 phase 1 -- session-scoped absence inventory. Tests written BEFORE the organ
change, per docs/evidence/absence_inventory_design.md section 8.

Phase 1 licenses REFUSAL ONLY (design section 2.2 as amended by E24a section 5).
The inventory can only add a reason to stay silent, never a reason to speak.

Most tests exercise module-level pure functions so they need no brain build.
"""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import organs.neural_language as nl  # noqa: E402

frame = nl._absence_frame
licence = nl._absence_licence

SCARF_TELLS = ["the coat is wet", "the coat is on the hook", "the scarf is wet"]
SCARF_INV = {"coat": {"property": "wet", "place": "hook"},
             "scarf": {"property": "wet"}}


def build_inv(tells):
    inv = {}
    for t in tells:
        f = frame(t)
        if f:
            rel, subj, obj = f
            inv.setdefault(subj, {}).setdefault(rel, obj)
    return inv


# ---------------------------------------------------------------- 1. flag off
def test_e24_flag_default_off():
    """A1/design section 5: the gene is default-off, so nothing changes unless asked."""
    assert nl.NeuralLanguage.ABSENCE_INVENTORY is False


def test_e24_flag_is_a_module_gene():
    """It must be a scalar set once at construction, never restored from state."""
    src = inspect.getsource(nl)
    assert "ABSENCE_INVENTORY" in src
    # not persisted: save_state/load_state must not mention it
    assert "ABSENCE_INVENTORY" not in inspect.getsource(nl.NeuralLanguage.save_state)
    assert "ABSENCE_INVENTORY" not in inspect.getsource(nl.NeuralLanguage.load_state)


# ------------------------------------------------------- 2. session scoping
def test_e24_inventory_is_session_scoped():
    """Design section 2.1: append-only within a session, not persisted, not merged."""
    src = inspect.getsource(nl.NeuralLanguage._absence_note)
    assert "_absence_inv" in src
    init = inspect.getsource(nl.NeuralLanguage.__init__)
    assert "_absence_inv" in init, "inventory must start empty per instance"
    # never written to disk
    assert "_absence_inv" not in inspect.getsource(nl.NeuralLanguage.save_state)


# --------------------------------------------------------- 3. write-side frames
def test_e24_write_side_frames():
    """Design section 2.1: the three in-scope relation classes."""
    assert frame("the scarf is wet") == ("property", "scarf", "wet")
    assert frame("the coat is on the hook") == ("place", "coat", "hook")
    assert frame("the frost bites the latch") == ("agent", "frost", "bites latch")


def test_e24_quantity_frames_never_license():
    """E24a section 3: the quantity-frame defect is real -- `there are four eggs in
    the basket` yields the garbage subject `four`. E24a measured it as HARMLESS
    because every ask in that script fell through, so the entry was never consulted.

    The invariant is therefore not "no garbage entries" but "garbage entries never
    license anything". A missing or malformed entry must never be read as evidence
    of absence -- that is the rule separating E24 from E15.
    """
    inv = build_inv(["there are four eggs in the basket", "then two eggs break"])
    for ask in ("how many eggs did i mention first?", "how many eggs broke?",
                "did any egg break?", "how many eggs are left in the basket?",
                "where are the eggs?", "what is four?"):
        assert licence(ask, inv) is None, (ask, inv)


def test_e24_inventory_builds_from_tells():
    assert build_inv(SCARF_TELLS) == SCARF_INV


# ------------------------------------------------- 4. scarf licensed refusal
def test_e24_scarf_licensed_refusal():
    """The guard, relocated. Subject present, queried relation absent -> refusal,
    for a reason that is not a coverage ratio (design section 4, abort A5)."""
    lic = licence("where did i say the scarf is?", SCARF_INV)
    assert lic is not None
    kind, reason = lic
    assert kind == "refusal"
    assert "scarf" in reason and "place" in reason
    # the reason must not be a ratio
    assert "%" not in reason and "coverage" not in reason.lower()


# ------------------------------------------------- 5. no cross-subject licence
def test_e24_no_cross_subject_licence():
    """The E15 failure mode. The coat's `place` is present in the inventory and the
    lookup must still not reach it (design section 3.3, abort A3)."""
    assert "place" in SCARF_INV["coat"]
    lic = licence("where did i say the scarf is?", SCARF_INV)
    assert lic[0] == "refusal"
    assert "hook" not in lic[1]


def test_e24_no_cross_subject_licence_paraphrases():
    """Same invariant under rewording -- E24a could not test these (section 6)."""
    for ask in ("where is the scarf?", "where did i say the scarf was?",
                "the scarf is where?", "where's the scarf"):
        lic = licence(ask, SCARF_INV)
        if lic is not None:
            assert lic[0] == "refusal", ask
            assert "hook" not in lic[1], ask


# --------------------------------------------------- 6. subject-absent fall-through
def test_e24_subject_absent_falls_through():
    """Design section 2.2 branch 3: no licence either way (abort A4)."""
    for ask in ("where did i say the moon is?", "what does the raven eat?",
                "how many eggs are left in the basket?"):
        assert licence(ask, SCARF_INV) is None, ask


def test_e24_ambiguous_subject_falls_through():
    """Two inventory subjects in one ask -> no licence. Conservative by construction."""
    assert licence("is the coat wet or is the scarf wet?", SCARF_INV) is None


def test_e24_no_queried_relation_falls_through():
    """Interrogatives outside the three relation classes get no licence."""
    for ask in ("how many times did i tell you the coat is wet?",
                "what did i tell you about before the kettle?",
                "which did i tell you first the lantern or the gate?"):
        assert licence(ask, SCARF_INV) is None, ask


def test_e24_empty_inventory_never_licenses():
    """Absence is licensed only by a positively-built inventory, never by a failure
    to find something -- the rule that separates E24 from E15."""
    for ask in ("where did i say the scarf is?", "what does the frost bite?"):
        assert licence(ask, {}) is None, ask


# ------------------------------------------------- 7. phase 1 never speaks
def test_e24_phase1_never_licenses_an_answer():
    """E24a section 2: 2 of 3 answer licences were wrong, one on a passing ask.
    Phase 1 must return only 'refusal' or None -- never 'answer' (abort A3 clause)."""
    inv = build_inv(["the frost bites the latch", "the latch holds the door",
                     "the coat is on the hook", "the scarf is wet"])
    asks = ["what does the frost bite?", "what bites the latch?",
            "what does the thing the frost bites hold?",
            "where did i say the scarf is?", "where is the coat?"]
    for ask in asks:
        lic = licence(ask, inv)
        assert lic is None or lic[0] == "refusal", (ask, lic)


def test_e24_no_negative_answers():
    """Abort A7: phase 1 produces no assertion of absence in language. The refusal
    reason is internal; it must not be a speakable negative."""
    lic = licence("where did i say the scarf is?", SCARF_INV)
    reason = lic[1].lower()
    for banned in ("no", "neither", "nothing", "never"):
        assert not reason.startswith(banned + " "), reason
    src = inspect.getsource(nl.NeuralLanguage._absence_licence)
    assert "spoken" not in src or '"spoken": False' in src


# ------------------------------------------------- 8. keyed lookup, not retrieval
def test_e24_keyed_lookup_not_retrieval():
    """Abort A6: no binder.recall, no similarity search on the read path."""
    # Assert on CALLS, not on the word appearing in a docstring that explains the
    # prohibition.
    src = inspect.getsource(nl._absence_licence)
    body = src.split('"""', 2)[-1]
    for banned in (".recall(", "binder", "stem_rows(", ".nearest", "cosine",
                   "cortex"):
        assert banned not in body, banned


def test_e24_read_side_preempts_the_coverage_gate():
    """The point of E24: the inventory check must run BEFORE the coverage floor, so
    the guard no longer depends on the denominator (design section 1, section 6)."""
    src = inspect.getsource(nl.NeuralLanguage.answer)
    i_lic = src.find("_absence_licence")
    i_floor = src.find("ANSWER_COVERAGE_FLOOR")
    assert i_lic != -1, "answer() must consult the inventory"
    assert i_floor != -1
    assert i_lic < i_floor, "inventory licence must pre-empt the coverage floor"


# ------------------------------------------------- 10. E23 stays unimplemented
def test_e24_e23_still_off():
    """Design section 5: the coverage denominator is unchanged. E23's exclusion sets
    must not be present in the organ."""
    src = inspect.getsource(nl)
    for banned in ("COVERAGE_ANSWERABLE_TERMS", "COVERAGE_EXCLUDE_SYNTAX",
                   "v_synt", "v_frame"):
        assert banned not in src, banned
    assert nl.NeuralLanguage.ANSWER_COVERAGE_FLOOR == 0.6


# ------------------------------------------------- integration (needs a brain)
@pytest.mark.integration
def test_e24_control_battery_unchanged():
    """A1: with the flag OFF, generation 20 must reproduce generation 19 exactly.
    Recorded result, asserted from the journal -- no brain build in the suite."""
    import json
    g19 = ROOT / "state" / "selection" / "generation_19_asks.jsonl"
    g20 = ROOT / "state" / "selection" / "generation_20_asks.jsonl"
    if not g20.exists():
        pytest.skip("generation 20 not run yet")
    a = [json.loads(l) for l in g19.read_text(encoding="utf-8").splitlines() if l.strip()]
    b = [json.loads(l) for l in g20.read_text(encoding="utf-8").splitlines() if l.strip()]
    ka = {(r["script"], r["ask"]): (r["pass"], r["stage"]) for r in a}
    kb = {(r["script"], r["ask"]): (r["pass"], r["stage"]) for r in b}
    assert ka == kb, "flag-off control must be byte-identical to generation 19"
