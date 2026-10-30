"""Pin the coverage-gate diagnosis and the E6 pre-registration.

These tests exist so that E6's predictions cannot be edited after the result is
known. The window arithmetic, the seed, the floor value and the classification
rules are all asserted here from the recorded artifact, before the run. If E6 comes
back and someone is tempted to reinterpret "exactly one ask moves", these fail first.

They also pin the two methodology bugs that cost runs:
  * `spoken` must classify as SPOKE, never PASS -- the organ answering says nothing
    about whether the content matched the expect block.
  * the in-order turn walk must reproduce part 1's independently measured kettle
    coverage of 0.555, which is the cross-check that the walk is right.
"""

from __future__ import annotations

import io
import json
import os
import random
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

DIAG = os.path.join(ROOT, "docs", "evidence", "coverage_gate_diagnosis.json")
BASELINE = os.path.join(ROOT, "tools", "selection_baseline.json")

# The measured GATE coverages, from the recorded run. Nine harness failures plus one
# invalid contrast row (see EXCLUDED_CONTRAST).
GATE_COVERAGES = {
    "what does the bitten thing hold?": 0.385,
    "how many times does the bell turn?": 0.417,
    "how often did i say the coat is wet?": 0.454,
    "what came before the kettle in what i said?": 0.460,
    "what is held by the thing the frost bites?": 0.510,
    "how often does the bell turn?": 0.514,
    "what number of eggs is left in the basket?": 0.538,
    "what did i tell you about before the kettle?": 0.555,
    "what is bitten by the frost?": 0.592,
}

# Part 1's independently measured thresholds. The scarf ask PASSES BY REFUSING, so
# admitting it loses a guarded pass.
SCARF_GUARD = 0.570
KETTLE = 0.555

# E6's pre-registered mutant: seed 7, floor 0.587206.
E6_SEED = 7
E6_FLOOR = 0.587206
E6_TARGET = "what is bitten by the frost?"

# The contrast ask is not a turn in the script it was asked against, so it could only
# be asked after ALL of that script's tells. Its 0.586 is not comparable with an ask
# the script positions, and it must never be used as evidence about the passing form.
EXCLUDED_CONTRAST = "what turns twice?"


@pytest.fixture(scope="module")
def diag():
    assert os.path.exists(DIAG), "run docs/evidence/coverage_gate_diagnosis.py first"
    return json.load(io.open(DIAG, encoding="utf-8"))


# --------------------------------------------------------------------------
# the recorded artifact is what the design document claims it is
# --------------------------------------------------------------------------

def test_the_recorded_tally_matches_the_document(diag):
    assert diag["tally"] == {"ABSENT": 4, "GATE": 10, "SPOKE": 5, "VETO": 1}


def test_the_floor_in_force_is_the_documented_one(diag):
    assert diag["floor"] == 0.6


def test_every_gate_coverage_in_the_document_is_in_the_artifact(diag):
    got = {r["ask"]: r["reply"].get("coverage")
           for r in diag["rows"] if r["class"] == "GATE"}
    for ask, cov in GATE_COVERAGES.items():
        assert ask in got, f"{ask} not classified GATE in the artifact"
        assert got[ask] == pytest.approx(cov, abs=1e-9), ask


def test_the_gate_class_is_the_largest_cause_of_failure(diag):
    """9 of 19 harness failures. Not a majority -- the document says so plainly."""
    fails = [r for r in diag["rows"] if r["tier"] in ("frozen_fail", "generalisation")]
    assert len(fails) == 19
    by = {}
    for r in fails:
        by[r["class"]] = by.get(r["class"], 0) + 1
    assert by == {"GATE": 9, "SPOKE": 5, "ABSENT": 4, "VETO": 1}
    assert by["GATE"] == max(by.values())
    assert by["GATE"] < len(fails) / 2, "GATE is the largest class but not a majority"


def test_the_invalid_contrast_row_is_labelled_so_it_cannot_be_cited(diag):
    rows = [r for r in diag["rows"] if r["ask"] == EXCLUDED_CONTRAST]
    assert len(rows) == 1
    assert rows[0]["tier"] == "contrast"
    assert rows[0]["position"] == "after-all-tells"
    # every real ask was asked at its own position in the script
    for r in diag["rows"]:
        if r["tier"] != "contrast":
            assert r["position"] == "at-position", r["ask"]


def test_the_walk_reproduces_part_ones_independent_kettle_measurement(diag):
    """The cross-check that says the in-order walk is right.

    coverage_exact.py replays turns[:idx] and measured 0.555. This probe walks the
    turns in order and must agree exactly on the one ask they share.
    """
    rows = [r for r in diag["rows"]
            if r["ask"] == "what did i tell you about before the kettle?"]
    assert len(rows) == 1
    assert rows[0]["reply"]["coverage"] == pytest.approx(KETTLE, abs=1e-9)


def test_absent_class_holds_the_four_asks_no_threshold_can_fix(diag):
    got = sorted(r["ask"] for r in diag["rows"] if r["class"] == "ABSENT")
    assert got == sorted([
        "does the door hold the frost?",
        "name the wet thing that is not on the hook",
        "which thing turns twice?",
        "is the frost held by the door?",
    ])


def test_e5s_target_ask_is_absent_not_gated(diag):
    """Why R1/R1'/R2 were inert, restated as a measurement.

    `which thing turns twice?` has an EMPTY `required`: informative() found no
    binder posting for any content word. The memory is not below threshold, it is
    not there in a form the cue can reach. No floor and no shape repair can help.
    """
    rows = [r for r in diag["rows"] if r["ask"] == "which thing turns twice?"]
    assert len(rows) == 1
    assert rows[0]["class"] == "ABSENT"
    assert not rows[0]["reply"].get("required")


# --------------------------------------------------------------------------
# classification rules -- pinned so a future edit cannot relabel a failure
# --------------------------------------------------------------------------

def _classify():
    from docs.evidence.coverage_gate_diagnosis import classify
    return classify


def test_a_spoken_reply_is_never_called_a_pass():
    classify = _classify()
    assert classify({"spoken": True, "reason": "answered"}) == "SPOKE"
    assert classify({"answered": True}) == "SPOKE"
    assert classify({"ok": True}) == "SPOKE"
    # and SPOKE is not PASS, whatever the harness decided about the content
    assert classify({"spoken": True}) != "PASS"


def test_an_empty_required_list_is_absent_not_gated():
    classify = _classify()
    assert classify({"reason": "covers 0%", "required": [], "coverage": 0.0}) == "ABSENT"
    assert classify({"reason": "nothing to recall"}) == "ABSENT"


def test_a_scored_refusal_below_the_floor_is_gated():
    classify = _classify()
    assert classify({"reason": "covers 55%", "required": ["kettle"],
                     "coverage": 0.555}) == "GATE"


def test_a_shape_veto_is_its_own_class():
    classify = _classify()
    assert classify({"reason": "shape veto", "required": ["frost"],
                     "coverage": 0.9}) == "VETO"


def test_an_unclassified_refusal_is_other_not_silently_dropped():
    classify = _classify()
    assert classify({"reason": "something new", "required": ["x"]}) == "OTHER"


# --------------------------------------------------------------------------
# the E6 window, pre-registered
# --------------------------------------------------------------------------

def test_the_window_admits_exactly_one_ask():
    """(0.570, 0.592] buys one ask and keeps the guard. This is the whole finding."""
    admitted = [a for a, c in GATE_COVERAGES.items() if c >= E6_FLOOR]
    assert admitted == [E6_TARGET]


def test_the_window_keeps_the_guarded_scarf_refusal():
    """Scarf PASSES BY REFUSING at 0.570. Admitting it loses a guarded pass."""
    assert SCARF_GUARD < E6_FLOOR, "the mutant would admit the scarf guard"


def test_the_window_keeps_the_kettle_refusal():
    assert KETTLE < E6_FLOOR


def test_eight_of_nine_gate_failures_need_a_floor_that_costs_the_guard():
    """Why the lever cannot fix the class, only buy one member of it."""
    below = [a for a, c in GATE_COVERAGES.items() if c < SCARF_GUARD]
    assert len(below) == 8
    assert E6_TARGET not in below


def test_no_floor_admits_the_kettle_target_and_keeps_the_scarf_guard():
    """Part 1's result, restated: kettle 0.555 < scarf 0.570, so they are not separable."""
    assert KETTLE < SCARF_GUARD


def test_seed_7_reproduces_the_pre_registered_floor():
    """The draw was chosen by enumerating seeds, not cherry-picked after a result."""
    import tools.run_generation as G
    parent = json.load(io.open(os.path.join(ROOT, "state", "selection",
                                            "base_genome.json"), encoding="utf-8"))
    _genome, mv = G.mutate(parent, "answer.ANSWER_COVERAGE_FLOOR", random.Random(E6_SEED))
    assert mv["value"] == pytest.approx(E6_FLOOR, abs=1e-6)
    assert mv["draw"] == pytest.approx(-0.0128, abs=1e-4)
    assert mv["sigma"] == 0.05
    assert mv["clipped"] is False
    lo, hi = mv["bounds"]
    assert lo <= mv["value"] <= hi


def test_the_pre_registered_floor_is_inside_the_window():
    assert SCARF_GUARD < E6_FLOOR <= 0.592


def test_the_target_ask_is_in_the_generalisation_tier(diag):
    rows = [r for r in diag["rows"] if r["ask"] == E6_TARGET]
    assert len(rows) == 1
    assert rows[0]["tier"] == "generalisation"
    assert rows[0]["class"] == "GATE"


def test_the_target_ask_is_in_the_recorded_paraphrase_set():
    """P2 must be checkable against the harness's own battery, not just this probe."""
    base = json.load(io.open(BASELINE, encoding="utf-8"))
    hits = [k for k in base["paraphrase_set"] if k.endswith("::" + E6_TARGET)]
    assert hits, f"{E6_TARGET} is not in paraphrase_set"


# --------------------------------------------------------------------------
# E6, RECORDED. These pin the outcome, not the prediction.
#
# The window tests above are kept exactly as they were written BEFORE the run: they
# are the pre-registration, and deleting them now that P2 is falsified would erase
# the record of what was predicted. What follows is what actually happened.
# --------------------------------------------------------------------------

GEN6 = os.path.join(ROOT, "state", "selection", "generation_6.jsonl")
E6_CONTROL = "abffa2b7f101"
E6_MUTANT = "ebe00da7aabc"


@pytest.fixture(scope="module")
def gen6():
    assert os.path.exists(GEN6), "generation 6 was not published"
    rows = [json.loads(l) for l in io.open(GEN6, encoding="utf-8") if l.strip()]
    assert len(rows) == 2, "E6 was pre-registered as 1 control + 1 mutant"
    return {r.get("line") or r.get("line_id"): r for r in rows}


def _row(gen6, genome):
    for r in gen6.values():
        if r.get("genome_id") == genome:
            return r
    raise AssertionError(f"no line carries genome {genome}")


def test_e6_ran_the_pre_registered_arms(gen6):
    assert _row(gen6, E6_CONTROL) is not None
    assert _row(gen6, E6_MUTANT) is not None


def test_e6_mutant_carries_exactly_the_pre_registered_floor(gen6):
    r = _row(gen6, E6_MUTANT)
    mv = r["mutation"]
    assert mv["gene"] == "answer.ANSWER_COVERAGE_FLOOR"
    assert mv["parent_value"] == 0.6
    assert mv["raw"] == pytest.approx(E6_FLOOR, abs=1e-6)
    assert mv["delta"] == pytest.approx(-0.012794, abs=1e-6)
    assert mv["clipped"] is False
    assert mv["bounds"] == [0.45, 0.75]
    assert r["genome_verified"] is True, "the genome was not verified after apply"
    # the control must NOT carry a mutation
    assert not _row(gen6, E6_CONTROL).get("mutation")


def test_p1_held_the_guard_and_the_frozen_floor(gen6):
    for genome in (E6_CONTROL, E6_MUTANT):
        r = _row(gen6, genome)
        cap = r["fitness"]["capability"]
        reg = r["fitness"]["regression"]
        assert cap["tier"] == "frozen", genome
        assert (cap["passed"], cap["asked"]) == (19, 24), genome
        assert reg["frozen_lost_n"] == 0, genome
        assert not reg["frozen_lost"], genome
        assert reg["probe_guard_passed"] == 4, genome
        assert not reg["probe_guard_lost"], genome
        assert reg["verdict"] == "clean", genome


def test_p3_held_nothing_moved(gen6):
    """Both arms identical, so no ask changed verdict between them."""
    a = _row(gen6, E6_CONTROL)["fitness"]
    b = _row(gen6, E6_MUTANT)["fitness"]
    assert a["select_key"] == b["select_key"] == [1, 19, 4]
    assert a["stages"] == b["stages"]
    assert a["generalisation"]["passed"] == b["generalisation"]["passed"] == 0
    assert a["capability"]["pass_set"] == b["capability"]["pass_set"]
    assert a["seals"] == b["seals"], "the batteries differed between arms"


def test_the_mutant_was_eligible_and_still_bought_nothing(gen6):
    """Eligible but not better: the rule kept the parent on a tie, not on a loss.

    This distinction matters. The mutant did not fail the guard -- it passed
    everything and gained nothing, which is `no_gain`, not a cull for erosion.
    """
    c = _row(gen6, E6_MUTANT)["culling"]
    assert c["outcome"] == "no_gain"
    assert c["eligible"] == ["g6-2"]
    assert c["ineligible"] == []
    assert c["better_than_control"] == []
    assert c["survivor_genome_id"] == E6_CONTROL
    assert c["survivor_line"] == "g6-1"
    assert c["control_key"] == [1, 19, 4]


def test_p2_was_falsified_the_target_ask_still_dies_at_recall():
    """The pre-registered prediction that failed, pinned from the ask journal.

    The probe measured this ask at cov=0.592 and the floor was set to 0.587206, so
    the gate should have opened. It did not: the ask still fails at `recall` under
    the mutant. That is the falsification, and it is the reason the window in the
    design document is withdrawn rather than merely unconfirmed.
    """
    asks = os.path.join(ROOT, "state", "selection", "generation_6_asks.jsonl")
    assert os.path.exists(asks)
    rows = [json.loads(l) for l in io.open(asks, encoding="utf-8") if l.strip()]
    hits = [r for r in rows if r.get("q") == E6_TARGET or r.get("ask") == E6_TARGET]
    assert hits, f"{E6_TARGET} is not in the generation-6 ask journal"
    mutant = [r for r in hits if r.get("genome_id") == E6_MUTANT]
    assert mutant, "no mutant row for the target ask"
    for r in mutant:
        assert not (r.get("passed") or r.get("ok")), "P2 would have held"
        assert r.get("stage") == "recall", (
            "the ask left the recall refusal, which is what P2 predicted")


def test_the_state_guard_alarm_is_the_known_hardlink_set_not_a_new_one(gen6):
    """The guard fires, and this test pins WHAT it fires on.

    `live_files_untouched` is false in every run that touches a brain, listing the
    hardlinked `banc_brain.npz` copies under `state/live_learner/`. It fired
    identically in E5's two arms and in the read-only diagnosis probe, which wrote
    nothing at all. Pinning the exact set means a genuinely new file appearing in
    `moved` fails here instead of hiding inside a known-benign list. It is still not
    verified by sha256, and this test does not claim it is benign -- only that it is
    the same alarm as before.
    """
    for genome in (E6_CONTROL, E6_MUTANT):
        g = _row(gen6, genome)["guard"]
        assert g["live_files_untouched"] is False, genome
        moved = [m.replace("\\", "/") for m in g["moved"]]
        assert moved, genome
        # Two distinct populations, and conflating them hid the second one for three
        # runs. (a) the harness's OWN published artifacts, which it writes during the
        # run and the guard then reports as moved -- the same self-write false alarm
        # episode 3 had to be corrected for. (b) the hardlinked banc_brain.npz copies
        # under state/live_learner/. Anything in neither population is a real alarm.
        own = [m for m in moved if m.startswith("selection/")]
        hardlink = [m for m in moved if m.startswith("live_learner/")]
        assert own, f"the run published nothing? {moved}"
        assert all(m.startswith("selection/generation_6") for m in own), own
        assert hardlink, moved
        assert all(m.endswith("banc_brain.npz") for m in hardlink), hardlink
        assert set(own) | set(hardlink) == set(moved), (
            f"a file outside both known populations moved: "
            f"{set(moved) - set(own) - set(hardlink)}")


def test_the_window_is_withdrawn_not_silently_kept():
    """The design document must say the window does not exist.

    A future reader who finds §3's arithmetic and not §5b's retraction would run
    this mutant again. This test fails if the retraction is removed.
    """
    doc = io.open(os.path.join(ROOT, "docs", "coverage_gate_repair_design.md"),
                  encoding="utf-8").read()
    assert "P2 falsified" in doc or "FALSIFIED" in doc
    assert "withdrawn" in doc
    assert "not established" in doc
