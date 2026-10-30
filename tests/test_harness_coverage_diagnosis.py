"""Pin the in-harness recall instrumentation and what generation 7 measured.

Three things are pinned here, in increasing order of how much they cost to get
wrong:

1. The plumbing. `_clean()` keeps `coverage`/`required`/`nearest`, and the journal
   row records them. Without this the harness cannot distinguish "no memory" from
   "memory refused by a threshold" -- all three report stage=recall.

2. The classifier's rules. Each of the four classes must fire on the field pattern
   it claims to, and UNREACHABLE must be distinguishable from both neighbours. This
   is tested against synthetic rows, not just generation 7, because generation 7
   has zero UNREACHABLE asks and a rule that never fires is not a tested rule.

3. The empty window. The single most load-bearing number in
   docs/evidence/harness_coverage_diagnosis.md is that the best failing coverage
   (0.555) is BELOW the passing-by-refusal coverage (0.570), so no floor admits a
   target without first admitting the guard. If a future run changes that ordering
   the conclusion is void and these tests must fail.
"""

from __future__ import annotations

import io
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "docs", "evidence"))

from harness_coverage_classify import classify  # noqa: E402

GEN7 = os.path.join(ROOT, "state", "selection", "generation_7_asks.jsonl")
DIAG = os.path.join(ROOT, "docs", "evidence", "harness_coverage_diagnosis.json")


# ---------------------------------------------------------------- plumbing --

def test_clean_keeps_the_three_recall_fields():
    """The keep-list is the whole change; if it regresses the journal goes blind."""
    from tools.converse import _clean
    out = _clean({"spoken": True, "coverage": 0.555,
                  "required": ["kettle", "before"],
                  "nearest": [{"words": ["kettle"], "score": 0.5}]})
    assert out["coverage"] == 0.555
    assert out["required"] == ["kettle", "before"]
    assert out["nearest"] == [{"words": ["kettle"], "score": 0.5}]


def test_clean_still_drops_what_it_always_dropped():
    """Adding three keys must not turn _clean into a passthrough."""
    from tools.converse import _clean
    out = _clean({"spoken": True, "coverage": 0.5, "retrieval": {"huge": "x" * 999},
                  "brain_vote_dump": "y" * 999})
    assert "brain_vote_dump" not in out
    assert "retrieval" not in out


def test_the_journal_records_the_fields_for_a_real_run():
    assert os.path.exists(GEN7), "generation 7 was not published"
    rows = [json.loads(l) for l in io.open(GEN7, encoding="utf-8") if l.strip()]
    assert len(rows) == 42
    # at least one row must carry a real coverage, or the instrumentation is dead
    with_cov = [r for r in rows if r.get("coverage") is not None]
    assert with_cov, "no ask recorded a coverage: the keep-list is not reaching it"
    for r in with_cov:
        assert isinstance(r["required"], list)
        assert isinstance(r["nearest"], list)


def test_the_fields_are_present_as_keys_even_when_the_gate_never_ran():
    """A shape_arbiter refusal has no coverage, but the key must still exist.

    `cov=-` in the report means "the gate did not run", and that is diagnostic.
    If the key were missing entirely a reader could not tell that from a bug.
    """
    rows = [json.loads(l) for l in io.open(GEN7, encoding="utf-8") if l.strip()]
    arb = [r for r in rows if r.get("stage") == "shape_arbiter"]
    assert arb
    for r in arb:
        assert "coverage" in r and r["coverage"] is None
        assert "required" in r
        assert "nearest" in r


# ------------------------------------------------------- classifier rules --

def _row(**kw):
    base = {"stage": "recall", "pass": False, "coverage": None,
            "required": [], "nearest": [], "spoken": False, "tier": "frozen",
            "script": "s", "id": "i", "ask": "a"}
    base.update(kw)
    return base


def test_absent_needs_both_lists_empty():
    cls, why = classify(_row(required=[], nearest=[]))
    assert cls == "ABSENT"
    assert "no posting" in why


def test_unreachable_when_postings_exist_but_nothing_was_required():
    cls, why = classify(_row(required=[], nearest=[{"score": 0.3}]))
    assert cls == "UNREACHABLE"
    assert "could not bind" in why


def test_unreachable_when_required_but_no_neighbours():
    cls, _ = classify(_row(required=["bell"], nearest=[]))
    assert cls == "UNREACHABLE"


def test_unreachable_when_coverage_is_zero_with_postings():
    cls, why = classify(_row(required=["bell"], nearest=[{"score": 0}],
                             coverage=0.0))
    assert cls == "UNREACHABLE"
    assert "coverage 0" in why


def test_gate_needs_required_and_a_real_coverage():
    cls, why = classify(_row(required=["bell", "turn"], nearest=[{"score": 0.4}],
                             coverage=0.417))
    assert cls == "GATE"
    assert "0.417" in why


def test_gate_is_not_confused_with_unreachable_on_missing_coverage():
    """required + nearest but coverage unset is UNREACHABLE, not GATE."""
    cls, _ = classify(_row(required=["bell"], nearest=[{"score": 0.4}],
                           coverage=None))
    assert cls == "UNREACHABLE"


def test_downstream_covers_every_non_recall_stage():
    for st in ("shape_arbiter", "mouth", "gating", "engine_error",
               "genome_refused"):
        cls, why = classify(_row(stage=st))
        assert cls == "DOWNSTREAM", st
        assert st in why


def test_spoken_but_wrong_content_is_downstream_not_a_pass():
    """The SPOKE lesson: `spoken` says nothing about whether it matched."""
    cls, why = classify(_row(stage=None, spoken=True,
                             said="the coat is on the hook"))
    assert cls == "DOWNSTREAM"
    assert "did not match" in why


def test_a_pass_is_recorded_with_its_coverage():
    # `pass` is a keyword, so it cannot be a kwarg name; build the row directly.
    r = _row(stage=None, coverage=0.570)
    r["pass"] = True
    cls, why = classify(r)
    assert cls == "PASS"
    assert "0.57" in why


# --------------------------------------------- generation 7, the real data --

@pytest.fixture(scope="module")
def diag():
    assert os.path.exists(DIAG)
    return json.load(io.open(DIAG, encoding="utf-8"))


def test_generation7_ran_the_control_genome_only(diag):
    assert diag["genomes"] == ["abffa2b7f101"]
    assert diag["rows"] == 42
    assert diag["passed"] == 23 and diag["failed"] == 19


def test_the_class_tally(diag):
    t = diag["class_tally"]
    assert t == {"ABSENT": 1, "UNREACHABLE": 0, "GATE": 9, "DOWNSTREAM": 9}
    assert sum(t.values()) == 19, "every failure must land in exactly one class"


def test_unreachable_is_genuinely_empty_not_a_rule_that_never_fires(diag):
    """Zero is a result, but only if the gate fields were actually populated.

    All nine GATE asks have 3 neighbours and the one ABSENT ask has 0, so the
    discriminator ran on real data and nothing landed in the middle.
    """
    gate = diag["asks"]["GATE"]
    assert len(gate) == 9
    assert all(len(e["nearest"]) == 3 for e in gate)
    assert all(e["required"] for e in gate)
    absent = diag["asks"]["ABSENT"]
    assert len(absent) == 1
    assert absent[0]["ask"] == "which thing turns twice?"
    # The organ omits the keys entirely on this path, so the journal holds None
    # rather than []. classify() normalises with `or []`; assert the same way,
    # and separately pin that None is what is stored -- a future organ that starts
    # emitting [] must not silently change what ABSENT means.
    assert not (absent[0]["required"] or [])
    assert not (absent[0]["nearest"] or [])
    assert absent[0]["coverage"] is None


def test_THE_WINDOW_IS_EMPTY(diag):
    """The load-bearing result. Best failing coverage < passing-by-refusal coverage.

    A floor F admits an ask when coverage >= F. To admit the best GATE ask needs
    F <= 0.555; to keep the 0.570 ask refusing needs F > 0.570. Contradiction, so
    no floor admits a target without first admitting the guard. If a future run
    reorders these two numbers the conclusion in the diagnosis document is void.
    """
    pc = diag["pass_coverage"]
    fc = diag["failed_recall_coverage"]
    assert pc["n"] == 1 and pc["max"] == pytest.approx(0.570)
    assert fc["n"] == 9
    assert fc["max"] == pytest.approx(0.555)
    assert fc["max"] < pc["min"], (
        "a failing ask now scores at or above the passing-by-refusal ask, so a "
        "window may exist and the empty-window conclusion must be re-derived")


def test_no_floor_in_the_declared_bounds_admits_a_target_and_keeps_the_guard(diag):
    """Brute-force the claim over the gene's own bounds, at real precision."""
    pc = diag["pass_coverage"]["min"]
    best = diag["failed_recall_coverage"]["max"]
    lo, hi = 0.45, 0.75          # the pre-registered bounds on the gene
    step = 0.0001
    n = int(round((hi - lo) / step))
    admitting = [round(lo + i * step, 4) for i in range(n + 1)
                 if round(lo + i * step, 4) <= best]
    assert admitting, "sanity: some floor in bounds admits the best target"
    for f in admitting:
        assert f <= best < pc, f
        # every such floor also admits the guard ask, which passes by refusing
        assert pc >= f, f"a floor of {f} admits the 0.570 ask and loses the guard"


def test_the_probe_contradiction_is_recorded(diag):
    """The ask E6 was built on: probe said 0.592, the harness says 0.340.

    Pinned so the falsification of E6's P2 has an in-harness number attached
    rather than resting on a null result.
    """
    gate = {e["ask"]: e for e in diag["asks"]["GATE"]}
    target = "what is bitten by the frost?"
    assert target in gate
    assert gate[target]["coverage"] == pytest.approx(0.340)
    assert gate[target]["coverage"] < 0.587206, (
        "at the harness's own coverage E6's floor could never have admitted it")


def test_the_kettle_and_scarf_numbers_still_transfer(diag):
    """The two asks the probe got right, re-measured inside the harness."""
    gate = {e["ask"]: e for e in diag["asks"]["GATE"]}
    assert gate["what did i tell you about before the kettle?"][
        "coverage"] == pytest.approx(0.555)
    assert diag["pass_coverage"]["max"] == pytest.approx(0.570)


def test_the_gating_failures_are_one_proposition_in_three_forms(diag):
    """Failure counts overstate distinct defects; pin the collapse."""
    dn = diag["asks"]["DOWNSTREAM"]
    gating = [e for e in dn if e["stage"] == "gating"]
    assert len(gating) == 3
    assert all("door" in e["ask"] and "frost" in e["ask"] for e in gating)


def test_the_mouth_failures_produced_noise_not_wrong_content(diag):
    dn = diag["asks"]["DOWNSTREAM"]
    mouth = [e for e in dn if e["stage"] == "mouth"]
    assert len(mouth) == 4
    said = [e["said"] for e in mouth if e["said"]]
    assert said, "mouth failures should have rendered something"
    # none of the rendered text is a word from any script's tell set
    for s in said:
        assert s.lower() not in ("the copper bell turns twice", "the coat is wet")


def test_no_threshold_or_answer_path_code_changed():
    """This change records; it must not tune."""
    nl = io.open(os.path.join(ROOT, "organs", "neural_language.py"),
                 encoding="utf-8").read()
    assert "ANSWER_COVERAGE_FLOOR = 0.6" in nl
    assert "RECALL_EMPTY_REQUIRED_FALLBACK" not in nl, (
        "the proposed experiment was implemented before it was pre-registered")


def test_the_diagnosis_document_states_the_empty_window():
    doc = io.open(os.path.join(ROOT, "docs", "evidence",
                               "harness_coverage_diagnosis.md"),
                  encoding="utf-8").read()
    assert "empty" in doc
    assert "0.555" in doc and "0.570" in doc
    assert "no floor exists" in doc.lower() or "No floor exists" in doc
    # and it must carry the pre-registered predictions for the next experiment
    for p in ("P1", "P2", "P3", "P4"):
        assert f"**{p}**" in doc, p
