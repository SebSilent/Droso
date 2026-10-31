"""E25 -- `v_synt` coverage exclusion. Tests written BEFORE the organ change,
per docs/evidence/e25_preregistration.md.

`v_synt` removes function words from `must`, the set whose size is the coverage
DENOMINATOR. It must not touch the retrieval cue, must not exclude any content
word (abort B7), and must not disturb the relocated absence guard (abort B4).

Like the E24 tests these need no brain build: the exclusion is a module-level
pure predicate, and the structural claims are source inspections.
"""
from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import organs.neural_language as nl  # noqa: E402

NL = nl.NeuralLanguage
FW = NL.SHAPE_FUNCTION_WORDS

# Content words drawn from the frozen+probe battery. None of these may ever be
# excluded -- that is abort condition B7.
CONTENT_WORDS = [
    "coat", "wet", "hook", "scarf", "kettle", "lantern", "bell", "turns",
    "twice", "frost", "bites", "bitten", "latch", "door", "holds", "hold",
    "eggs", "broke", "basket", "copper", "metal", "moon", "dry", "left",
    "mention", "mentioned", "tell", "told", "say", "said", "break",
]


# ------------------------------------------------------------------ 1. the flag
def test_e25_flag_default_off():
    """The gene is default-off, so nothing changes unless a run asks for it."""
    assert NL.COVERAGE_EXCLUDE_SYNT is False


def test_e25_flag_not_persisted():
    """A code flag, not state: it must never be restored from a saved brain."""
    assert "COVERAGE_EXCLUDE_SYNT" not in inspect.getsource(NL.save_state)
    assert "COVERAGE_EXCLUDE_SYNT" not in inspect.getsource(NL.load_state)


def test_e25_predicate_is_module_level():
    """It must be a pure function so it is testable without a brain build."""
    assert callable(nl._coverage_excluded)
    sig = inspect.signature(nl._coverage_excluded)
    assert list(sig.parameters) == ["w", "exclude_synt", "function_words"]


# ------------------------------------------------- 2. the predicate's behaviour
def test_e25_off_excludes_nothing():
    """With the flag off the denominator is byte-identical to the control."""
    for w in list(FW) + CONTENT_WORDS:
        assert nl._coverage_excluded(w, False, FW) is False


def test_e25_on_excludes_function_words():
    for w in ("the", "of", "is", "does", "by", "what", "a", "in"):
        if w in FW:
            assert nl._coverage_excluded(w, True, FW) is True


def test_e25_never_excludes_content_words():
    """ABORT B7: the exclusion set is closed-class only."""
    for w in CONTENT_WORDS:
        assert nl._coverage_excluded(w, True, FW) is False, w


def test_e25_function_words_are_closed_class():
    """B7, checked from the other side: no noun or main verb from the battery
    leaked into SHAPE_FUNCTION_WORDS."""
    overlap = set(CONTENT_WORDS) & set(FW)
    assert not overlap, f"content words inside the function set: {overlap}"


def test_e25_predicate_is_pure():
    """No attribute access on self, no binder, no retrieval -- it cannot reach
    for memory, which is what keeps it out of the recall path (abort B6)."""
    src = inspect.getsource(nl._coverage_excluded)
    # The docstring explains the prohibition and so contains the banned words.
    # Assert on the executable body only -- the same artifact E24's no-retrieval
    # test hit.
    body = src.split('"""', 2)[2]
    for banned in ("self.", "binder", "recall", "stem_rows"):
        assert banned not in body, banned
    # And the signature proves it: no `self`, so it cannot be a method.
    assert "self" not in inspect.signature(nl._coverage_excluded).parameters


# ------------------------------------------- 3. it shrinks `must` and nothing else
def test_e25_exclusion_is_subtractive_only():
    """The hook must be a `continue` inside the must-building loop. It may only
    remove candidates from the denominator, never add one."""
    src = inspect.getsource(NL.answer)
    i = src.index("_coverage_excluded")
    j = src.index("must.add(w)", i)
    between = src[i:j]
    # The excluded branch must bail out before the add, not fall through to it.
    assert "continue" in between, "the exclusion does not skip the add"
    # And it must not be an alternative route INTO the denominator.
    assert "must.add" not in between
    # `known` bookkeeping is upstream of the exclusion, so the "no word of that
    # is one he knows" guard still sees every recognised word.
    assert src.index("known.add(w)") < i


def test_e25_exclusion_is_after_retrieval():
    """ABORT B6/the cue invariant: `recall(content, ...)` must run on the
    UNFILTERED content list. If the exclusion came first it would change what is
    retrieved, not merely how it is scored -- a different and larger intervention
    than the one pre-registered."""
    src = inspect.getsource(NL.answer)
    cue = src.index("binder.recall(content")
    exc = src.index("_coverage_excluded")
    assert cue < exc, "exclusion must not precede the retrieval cue"


def test_e25_exclusion_is_inside_the_must_loop():
    """It must sit in the loop that builds `must`, so the denominator is the only
    thing affected."""
    src = inspect.getsource(NL.answer)
    loop = src.index("must = set()")
    exc = src.index("_coverage_excluded")
    add = src.index("must.add(w)")
    assert loop < exc < add, (loop, exc, add)


# --------------------------------------------- 4. the relocated guard is intact
def test_e25_absence_inventory_still_preempts_the_gate():
    """ABORT B4: with both flags on the scarf ask must still refuse on inventory
    grounds with coverage None. The inventory check has to come BEFORE the
    coverage block, or v_synt could reach the guarded ask."""
    src = inspect.getsource(NL.answer)
    inv = src.index("_absence_licence")
    cov = src.index("must = set()")
    assert inv < cov, "the inventory must pre-empt the coverage gate"


def test_e25_does_not_touch_the_floor():
    """v_synt changes the denominator, never the threshold. E23 was refuted on
    the denominator; moving the floor would be a different experiment."""
    assert NL.ANSWER_COVERAGE_FLOOR == 0.6


def test_e25_does_not_touch_the_absence_inventory():
    """E24 phase 1 is accepted and frozen for this experiment."""
    assert NL.ABSENCE_INVENTORY is False
    assert "ABSENCE_INVENTORY" not in inspect.getsource(nl._coverage_excluded)


# ------------------------------------------------------- 5. the harness wiring
def test_e25_harness_flag_exists():
    src = (ROOT / "tools" / "run_generation.py").read_text(encoding="utf-8")
    assert "--coverage-exclude" in src
    assert "coverage_exclude_synt" in src


def test_e25_harness_records_the_flag_in_provenance():
    """Every line must be stamped with the flag, or the two arms are not
    distinguishable after the fact."""
    src = (ROOT / "tools" / "run_generation.py").read_text(encoding="utf-8")
    # provenance.code_flags is published as dict(CODE_FLAGS), so the invariant is
    # that the flag is written into CODE_FLAGS on BOTH branches -- an unset flag
    # must still be stamped False, or a missing key is indistinguishable from off.
    # E26 collapsed the two branches into one unconditional assignment driven by
    # `_syn` / `_frm`, which is strictly stronger than the old True/False pair:
    # the key is now written on EVERY path, so it can never be missing.
    assert 'CODE_FLAGS["coverage_exclude_synt"] = _syn' in src
    assert 'CODE_FLAGS["coverage_exclude_frame"] = _frm' in src
    assert '"code_flags": dict(CODE_FLAGS)' in src


def test_e25_harness_flag_is_default_off():
    src = (ROOT / "tools" / "run_generation.py").read_text(encoding="utf-8")
    # Index the add_argument call, not the first mention of the string -- that one
    # is inside a warning message.
    i = src.index('ap.add_argument("--coverage-exclude"')
    decl = src[i: i + 300]
    assert "default=None" in decl
    # E26 added "frame". Default stays None, so neither variant is on unless asked.
    assert 'choices=["synt", "frame"]' in decl


# ------------------------------------------------------------- 6. integration
@pytest.mark.integration
def test_e25_arms_differ_only_in_the_flag():
    """Gen 21 (control) and gen 22 (treatment) must be the same genome on the
    same battery, differing in exactly one code flag."""
    sel = ROOT / "state" / "selection"
    c, t = sel / "generation_21.jsonl", sel / "generation_22.jsonl"
    if not (c.exists() and t.exists()):
        pytest.skip("generation 22 not run yet")
    gc = json.loads(c.read_text(encoding="utf-8"))
    gt = json.loads(t.read_text(encoding="utf-8"))
    assert gc["genome_id"] == gt["genome_id"]
    fc = gc["provenance"]["code_flags"]
    ft = gt["provenance"]["code_flags"]
    assert fc["absence_inventory"] is True and ft["absence_inventory"] is True
    # Gen 21 ran before this flag existed, so it has no such key. A missing key
    # means off -- which is why the harness now stamps False explicitly on both
    # branches, so the two can never be confused again.
    assert fc.get("coverage_exclude_synt", False) is False
    assert ft["coverage_exclude_synt"] is True
    differing = {k for k in set(fc) | set(ft)
                 if fc.get(k, False) != ft.get(k, False)}
    assert differing == {"coverage_exclude_synt"}, differing


@pytest.mark.integration
def test_e25_abort_conditions():
    """B1/B2/B3/B4/B5, read straight off the published journals."""
    sel = ROOT / "state" / "selection"
    c, t = sel / "generation_21_asks.jsonl", sel / "generation_22_asks.jsonl"
    if not (c.exists() and t.exists()):
        pytest.skip("generation 22 not run yet")

    def load(p):
        return {(r["script"], r["ask"]): r
                for r in (json.loads(x) for x in
                          p.read_text(encoding="utf-8").splitlines() if x.strip())}

    kc, kt = load(c), load(t)
    assert set(kc) == set(kt), "the two arms must run the same battery"

    # B1 -- the scarf ask must still refuse.
    scarf = [k for k in kt if k[1] == "where did i say the scarf is?"]
    assert len(scarf) == 1
    s = scarf[0]
    assert kt[s]["pass"] is True, "B1: the scarf ask stopped refusing"

    # B4 -- still inventory-licensed: no coverage measured, same reason.
    assert kt[s].get("coverage") is None, "B4: the coverage gate was reached"
    assert kt[s]["reason"] == kc[s]["reason"], "B4: the refusal reason changed"

    # B2/B3 -- guarded and frozen floors.
    def score(rows, tier):
        sub = [r for r in rows.values() if r.get("tier") == tier]
        return sum(1 for r in sub if r.get("pass")), len(sub)

    for rows, name in ((kc, "control"), (kt, "treatment")):
        f = score(rows, "frozen")
        assert f[0] >= 19, f"B3: {name} frozen fell to {f[0]}/{f[1]}"

    # B5 -- no ask the control ANSWERED may start refusing.
    lost = [k for k in kc if kc[k].get("pass") and not kt[k].get("pass")]
    assert not lost, f"B5: v_synt subtracted answers: {[k[1] for k in lost]}"
